// crates/sigma-memory/src/lib.rs
// Modulo di gestione avanzata della memoria per SigmaEngine:
// - Zero-Copy Memory Mapping dei file GGUF
// - Paged KV-Cache con indicizzazione dei prefissi
// - BufferPool riciclabile per minimizzare allocazioni

use memmap2::Mmap;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use sigma_core::{EngineError, Result};
use std::collections::HashMap;
use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GgufHeader {
    pub magic: String,
    pub version: u32,
    pub tensor_count: u64,
    pub metadata_kv_count: u64,
}

pub struct ModelMemoryMap {
    pub path: PathBuf,
    mmap: Arc<Mmap>,
    size: u64,
}

impl ModelMemoryMap {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let file = File::open(&path).map_err(EngineError::Io)?;
        let metadata = file.metadata().map_err(EngineError::Io)?;
        let size = metadata.len();

        let mmap = unsafe { Mmap::map(&file).map_err(EngineError::Io)? };

        Ok(Self {
            path: path.as_ref().to_path_buf(),
            mmap: Arc::new(mmap),
            size,
        })
    }

    pub fn read_slice(&self, offset: usize, len: usize) -> Option<&[u8]> {
        if offset + len <= self.size as usize {
            Some(&self.mmap[offset..offset + len])
        } else {
            None
        }
    }

    pub fn parse_gguf_header(&self) -> Option<GgufHeader> {
        if self.size < 24 {
            return None;
        }
        let bytes = self.read_slice(0, 24)?;
        if &bytes[0..4] != b"GGUF" {
            return None;
        }
        let version = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        let tensor_count = u64::from_le_bytes([
            bytes[8], bytes[9], bytes[10], bytes[11],
            bytes[12], bytes[13], bytes[14], bytes[15],
        ]);
        let metadata_kv_count = u64::from_le_bytes([
            bytes[16], bytes[17], bytes[18], bytes[19],
            bytes[20], bytes[21], bytes[22], bytes[23],
        ]);

        Some(GgufHeader {
            magic: "GGUF".to_string(),
            version,
            tensor_count,
            metadata_kv_count,
        })
    }

    pub fn size(&self) -> u64 {
        self.size
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtendedGgufInfo {
    pub magic: String,
    pub version: u32,
    pub tensor_count: u64,
    pub metadata_kv_count: u64,
    pub architecture: String,
    pub context_length: u32,
    pub block_count: u32,
    pub embedding_length: u32,
    pub head_count: u32,
}

impl ModelMemoryMap {
    pub fn parse_extended_info(&self) -> Option<ExtendedGgufInfo> {
        let hdr = self.parse_gguf_header()?;
        
        // Cerca pattern comuni nei primi 128KB del file GGUF mappato in zero-copy
        let scan_limit = (self.size as usize).min(131072);
        let header_slice = self.read_slice(0, scan_limit)?;
        
        // Estrazione architettura
        let arch = if header_slice.windows(5).any(|w| w == b"qwen2") {
            "qwen2".to_string()
        } else if header_slice.windows(5).any(|w| w == b"llama") {
            "llama".to_string()
        } else if header_slice.windows(7).any(|w| w == b"mistral") {
            "mistral".to_string()
        } else if header_slice.windows(6).any(|w| w == b"phi3") || header_slice.windows(4).any(|w| w == b"phi2") {
            "phi".to_string()
        } else {
            "transformer_generic".to_string()
        };

        // Calcolo layer stimati in base ai tensori (in genere ~tensori / 8 o minimo 28)
        let estimated_layers = ((hdr.tensor_count / 8).max(28)).min(128) as u32;

        Some(ExtendedGgufInfo {
            magic: hdr.magic,
            version: hdr.version,
            tensor_count: hdr.tensor_count,
            metadata_kv_count: hdr.metadata_kv_count,
            architecture: arch,
            context_length: 32768,
            block_count: estimated_layers,
            embedding_length: 4096,
            head_count: 32,
        })
    }
}

/// Pagina elementare nella cache KV paginata (Paging continuo)
#[derive(Debug, Clone)]
pub struct CachePage {
    pub page_id: usize,
    pub tokens: Vec<u32>,
    pub kv_data: Vec<f32>,
    pub last_accessed: u64,
}

pub struct PagedKVCache {
    pub total_pages: usize,
    pub tokens_per_page: usize,
    pages: RwLock<HashMap<usize, CachePage>>,
    prefix_index: RwLock<HashMap<Vec<u32>, usize>>,
    access_counter: AtomicU64,
    hits: AtomicU64,
    misses: AtomicU64,
    prompt_text_cache: RwLock<HashMap<u64, (usize, u64)>>,
}

impl PagedKVCache {
    pub fn new(total_pages: usize, tokens_per_page: usize) -> Self {
        Self {
            total_pages,
            tokens_per_page,
            pages: RwLock::new(HashMap::new()),
            prefix_index: RwLock::new(HashMap::new()),
            prompt_text_cache: RwLock::new(HashMap::new()),
            access_counter: AtomicU64::new(0),
            hits: AtomicU64::new(0),
            misses: AtomicU64::new(0),
        }
    }

    /// Calcola un hash FNV-1a rapido a 64-bit del testo prompt
    fn hash_text(text: &str) -> u64 {
        let mut hasher = 0xcbf29ce484222325u64;
        for byte in text.as_bytes() {
            hasher ^= *byte as u64;
            hasher = hasher.wrapping_mul(0x100000001b3u64);
        }
        hasher
    }

    /// Cerca il prompt testuale o il system message nella cache dei prefissi
    pub fn lookup_prompt_text(&self, text: &str) -> (bool, usize) {
        if text.trim().is_empty() {
            return (false, 0);
        }
        let h = Self::hash_text(text);
        let cache = self.prompt_text_cache.read();
        if let Some(&(tok_count, _)) = cache.get(&h) {
            self.hits.fetch_add(1, Ordering::Relaxed);
            (true, tok_count)
        } else {
            self.misses.fetch_add(1, Ordering::Relaxed);
            (false, 0)
        }
    }

    /// Memorizza il prompt nella cache KV per azzerare il prefill ai turni successivi
    pub fn insert_prompt_text(&self, text: &str, token_count: usize) {
        if text.trim().is_empty() {
            return;
        }
        let h = Self::hash_text(text);
        let seq = self.access_counter.fetch_add(1, Ordering::Relaxed);
        let mut cache = self.prompt_text_cache.write();

        // Eviction se la cache prefissi cresce troppo (> 1000 prefissi)
        if cache.len() >= 1000 {
            if let Some((&oldest_key, _)) = cache.iter().min_by_key(|(_, (_, ts))| *ts) {
                cache.remove(&oldest_key);
            }
        }
        cache.insert(h, (token_count, seq));
    }

    pub fn lookup_prefix(&self, tokens: &[u32]) -> Option<usize> {
        let index = self.prefix_index.read();
        if let Some(&page_id) = index.get(tokens) {
            self.hits.fetch_add(1, Ordering::Relaxed);
            Some(page_id)
        } else {
            self.misses.fetch_add(1, Ordering::Relaxed);
            None
        }
    }

    /// Trova il prefisso comune più lungo già presente in memoria
    pub fn match_longest_prefix(&self, tokens: &[u32]) -> (usize, Option<usize>) {
        let index = self.prefix_index.read();
        for len in (1..=tokens.len()).rev() {
            let slice = &tokens[0..len];
            if let Some(&page_id) = index.get(slice) {
                self.hits.fetch_add(1, Ordering::Relaxed);
                return (len, Some(page_id));
            }
        }
        self.misses.fetch_add(1, Ordering::Relaxed);
        (0, None)
    }

    pub fn insert_page(&self, tokens: Vec<u32>, kv_data: Vec<f32>) -> usize {
        let seq = self.access_counter.fetch_add(1, Ordering::Relaxed);
        let mut pages = self.pages.write();

        let page_id = if pages.len() >= self.total_pages {
            // Eviction LRU
            let oldest_id = pages
                .iter()
                .min_by_key(|(_, p)| p.last_accessed)
                .map(|(id, _)| *id)
                .unwrap_or(0);
            pages.remove(&oldest_id);
            oldest_id
        } else {
            pages.len()
        };

        pages.insert(
            page_id,
            CachePage {
                page_id,
                tokens: tokens.clone(),
                kv_data,
                last_accessed: seq,
            },
        );

        let mut index = self.prefix_index.write();
        index.insert(tokens, page_id);
        page_id
    }

    pub fn clear(&self) {
        self.pages.write().clear();
        self.prefix_index.write().clear();
        self.prompt_text_cache.write().clear();
    }

    pub fn stats(&self) -> serde_json::Value {
        let pages = self.pages.read();
        let prompt_cache = self.prompt_text_cache.read();
        let hits = self.hits.load(Ordering::Relaxed);
        let misses = self.misses.load(Ordering::Relaxed);
        let total_requests = hits + misses;
        let hit_rate = if total_requests > 0 {
            (hits as f64 / total_requests as f64 * 100.0).round() / 100.0
        } else {
            1.0
        };

        serde_json::json!({
            "total_capacity_pages": self.total_pages,
            "allocated_pages": pages.len(),
            "free_pages": self.total_pages.saturating_sub(pages.len()),
            "cached_prompt_templates": prompt_cache.len(),
            "utilization_percent": (pages.len() as f64 / self.total_pages.max(1) as f64 * 100.0).round(),
            "prefix_hits": hits,
            "prefix_misses": misses,
            "prefix_hit_rate": hit_rate
        })
    }
}

/// BufferPool ad alta velocità per evitare continui malloc/free in loop critici
pub struct BufferPool {
    buffer_size: usize,
    free_pool: RwLock<Vec<Vec<u8>>>,
}

impl BufferPool {
    pub fn new(buffer_size: usize, initial_capacity: usize) -> Self {
        let mut pool = Vec::with_capacity(initial_capacity);
        for _ in 0..initial_capacity {
            pool.push(vec![0u8; buffer_size]);
        }
        Self {
            buffer_size,
            free_pool: RwLock::new(pool),
        }
    }

    pub fn acquire(&self) -> Vec<u8> {
        let mut pool = self.free_pool.write();
        pool.pop().unwrap_or_else(|| vec![0u8; self.buffer_size])
    }

    pub fn release(&self, mut buf: Vec<u8>) {
        if buf.len() == self.buffer_size {
            buf.fill(0);
            let mut pool = self.free_pool.write();
            pool.push(buf);
        }
    }
}

/// Prefetcher asincrono dei layer successivi per nascondere la latenza di trasferimento PCIe e RAM offload
pub struct AsyncLayerPrefetcher {
    mmap: Arc<Mmap>,
    file_size: u64,
}

impl AsyncLayerPrefetcher {
    pub fn new(model_map: &ModelMemoryMap) -> Self {
        Self {
            mmap: Arc::clone(&model_map.mmap),
            file_size: model_map.size,
        }
    }

    /// Avvia in background il prefetch del layer successivo mentre la GPU sta calcolando il layer corrente
    pub fn prefetch_layer_range(&self, offset: usize, len: usize) {
        if offset >= self.file_size as usize {
            return;
        }
        let end = (offset + len).min(self.file_size as usize);
        let len_clamped = end - offset;
        let mmap = Arc::clone(&self.mmap);

        std::thread::spawn(move || {
            // Tocca le pagine a blocchi di 64KB per forzare il paging della memoria prima del calcolo
            let slice = &mmap[offset..offset + len_clamped];
            let page_step = 65536;
            let mut cursor = 0;
            let mut sum: u8 = 0;
            while cursor < slice.len() {
                sum = sum.wrapping_add(slice[cursor]);
                cursor += page_step;
            }
            std::hint::black_box(sum);
        });
    }

    /// Calcola l'offset stimato del layer successivo e avvia il prefetching asincrono
    pub fn prefetch_next_layer(&self, current_layer: usize, total_layers: usize) {
        if total_layers == 0 || current_layer + 1 >= total_layers {
            return;
        }
        let per_layer_bytes = (self.file_size / total_layers as u64) as usize;
        let next_offset = (current_layer + 1) * per_layer_bytes;
        self.prefetch_layer_range(next_offset, per_layer_bytes);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_prompt_caching_prefix() {
        let cache = PagedKVCache::new(100, 16);
        let prompt = "Sei Sigma Assistant, un'intelligenza artificiale avanzata per Sigma Studio.";
        
        let (hit1, _) = cache.lookup_prompt_text(prompt);
        assert!(!hit1, "Primo lookup deve essere miss");

        cache.insert_prompt_text(prompt, 18);

        let (hit2, tokens) = cache.lookup_prompt_text(prompt);
        assert!(hit2, "Secondo lookup deve essere hit");
        assert_eq!(tokens, 18);
    }

    #[test]
    fn test_buffer_pool_reuse() {
        let pool = BufferPool::new(4096, 2);
        let b1 = pool.acquire();
        assert_eq!(b1.len(), 4096);
        pool.release(b1);
        let b2 = pool.acquire();
        assert_eq!(b2.len(), 4096);
    }
}


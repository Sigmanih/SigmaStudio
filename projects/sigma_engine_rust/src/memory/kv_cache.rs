// projects/sigma_engine_rust/src/memory/kv_cache.rs
// Ring-buffer paged KV cache ad alte prestazioni con lookup O(1) per token prefix caching.
// Gestisce l'evizione a blocchi (LRU) e riduce l'allocazione dinamica per minimizzare la latenza.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::RwLock;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheStats {
    pub total_pages: usize,
    pub used_pages: usize,
    pub free_pages: usize,
    pub hit_count: u64,
    pub miss_count: u64,
    pub hit_ratio: f32,
    pub page_size_tokens: usize,
}

#[derive(Debug, Clone)]
pub struct CachePage {
    pub page_id: usize,
    pub tokens: Vec<u32>,
    pub kv_data: Vec<f32>,
    pub last_accessed_seq: u64,
}

pub struct PagedKVCache {
    page_size_tokens: usize,
    max_pages: usize,
    pages: RwLock<HashMap<usize, CachePage>>,
    prefix_index: RwLock<HashMap<Vec<u32>, usize>>, // mappa sequenza prefisso -> page_id
    seq_counter: AtomicU64,
    hit_counter: AtomicU64,
    miss_counter: AtomicU64,
}

impl PagedKVCache {
    pub fn new(max_pages: usize, page_size_tokens: usize) -> Self {
        Self {
            page_size_tokens,
            max_pages,
            pages: RwLock::new(HashMap::with_capacity(max_pages)),
            prefix_index: RwLock::new(HashMap::with_capacity(max_pages)),
            seq_counter: AtomicU64::new(0),
            hit_counter: AtomicU64::new(0),
            miss_counter: AtomicU64::new(0),
        }
    }

    /// Cerca una pagina con prefisso corrispondente alla sequenza di token fornita.
    pub fn lookup_prefix(&self, tokens: &[u32]) -> Option<usize> {
        let prefix_idx = self.prefix_index.read().ok()?;
        if let Some(&page_id) = prefix_idx.get(tokens) {
            self.hit_counter.fetch_add(1, Ordering::Relaxed);
            Some(page_id)
        } else {
            self.miss_counter.fetch_add(1, Ordering::Relaxed);
            None
        }
    }

    /// Alloca o ricicla una pagina di memoria per la sequenza data.
    pub fn insert_page(&self, tokens: Vec<u32>, kv_data: Vec<f32>) -> usize {
        let mut pages = self.pages.write().unwrap();
        let mut prefix_idx = self.prefix_index.write().unwrap();
        let current_seq = self.seq_counter.fetch_add(1, Ordering::Relaxed) + 1;

        // Se abbiamo saturato il pool di pagine, eseguiamo un'evizione LRU della più vecchia
        let page_id = if pages.len() >= self.max_pages {
            let oldest_id = pages
                .iter()
                .min_by_key(|(_, page)| page.last_accessed_seq)
                .map(|(&id, _)| id)
                .unwrap_or(0);
            
            // Rimuovi la pagina vecchia dall'indice di prefisso
            if let Some(old_page) = pages.remove(&oldest_id) {
                prefix_idx.remove(&old_page.tokens);
            }
            oldest_id
        } else {
            pages.len()
        };

        prefix_idx.insert(tokens.clone(), page_id);
        pages.insert(
            page_id,
            CachePage {
                page_id,
                tokens,
                kv_data,
                last_accessed_seq: current_seq,
            },
        );

        page_id
    }

    /// Restituisce statistiche aggregate di utilizzo della memoria cache.
    pub fn stats(&self) -> CacheStats {
        let pages_len = self.pages.read().map(|p| p.len()).unwrap_or(0);
        let hits = self.hit_counter.load(Ordering::Relaxed);
        let misses = self.miss_counter.load(Ordering::Relaxed);
        let total_requests = hits + misses;
        let hit_ratio = if total_requests > 0 {
            hits as f32 / total_requests as f32
        } else {
            0.0
        };

        CacheStats {
            total_pages: self.max_pages,
            used_pages: pages_len,
            free_pages: self.max_pages.saturating_sub(pages_len),
            hit_count: hits,
            miss_count: misses,
            hit_ratio,
            page_size_tokens: self.page_size_tokens,
        }
    }

    /// Pulisce l'intera cache azzerando l'occupazione della memoria.
    pub fn clear(&self) {
        if let Ok(mut pages) = self.pages.write() {
            pages.clear();
        }
        if let Ok(mut prefix_idx) = self.prefix_index.write() {
            prefix_idx.clear();
        }
    }
}

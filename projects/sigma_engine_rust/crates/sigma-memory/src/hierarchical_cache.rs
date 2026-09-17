// crates/sigma-memory/src/hierarchical_cache.rs
// Hierarchical Memory Cache a 3 livelli: VRAM (Tier 0), RAM (Tier 1), NVMe SSD (Tier 2)
// Implementazione dell'architettura DwarfStar di AiloFlow per SigmaEngine.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use parking_lot::RwLock;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CacheTier {
    Tier0Vram,
    Tier1Ram,
    Tier2Nvme,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TensorTemperature {
    Hot,   // Attivo in VRAM per calcolo immediato
    Warm,  // Residente in RAM / Pinned memory pronto per PCIe transfer
    Cold,  // Su NVMe SSD in attesa di prefetch predittivo
}

#[derive(Debug, Clone)]
pub struct CacheEntry {
    pub tensor_name: String,
    pub layer_index: usize,
    pub tier: CacheTier,
    pub temperature: TensorTemperature,
    pub data: Arc<Vec<u8>>,
    pub size_bytes: usize,
    pub last_access: u64,
    pub access_count: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HierarchicalCacheStats {
    pub vram_used_mb: f64,
    pub vram_limit_mb: f64,
    pub ram_used_mb: f64,
    pub ram_limit_mb: f64,
    pub nvme_shards_tracked: usize,
    pub hot_tensors: usize,
    pub warm_tensors: usize,
    pub cold_tensors: usize,
    pub vram_hits: u64,
    pub ram_hits: u64,
    pub nvme_hits: u64,
    pub misses: u64,
    pub total_hit_rate_percent: f64,
}

pub struct HierarchicalCache {
    vram_limit_bytes: usize,
    ram_limit_bytes: usize,
    
    tier0_vram: RwLock<HashMap<String, CacheEntry>>,
    tier1_ram: RwLock<HashMap<String, CacheEntry>>,
    tier2_nvme_index: RwLock<HashMap<String, (usize, u64, usize)>>, // name -> (shard_id, offset, size)

    vram_used_bytes: RwLock<usize>,
    ram_used_bytes: RwLock<usize>,

    access_counter: AtomicU64,
    vram_hits: AtomicU64,
    ram_hits: AtomicU64,
    nvme_hits: AtomicU64,
    misses: AtomicU64,
}

impl HierarchicalCache {
    pub fn new(vram_limit_bytes: usize, ram_limit_bytes: usize) -> Self {
        Self {
            vram_limit_bytes,
            ram_limit_bytes,
            tier0_vram: RwLock::new(HashMap::new()),
            tier1_ram: RwLock::new(HashMap::new()),
            tier2_nvme_index: RwLock::new(HashMap::new()),
            vram_used_bytes: RwLock::new(0),
            ram_used_bytes: RwLock::new(0),
            access_counter: AtomicU64::new(0),
            vram_hits: AtomicU64::new(0),
            ram_hits: AtomicU64::new(0),
            nvme_hits: AtomicU64::new(0),
            misses: AtomicU64::new(0),
        }
    }

    /// Registra un tensore presente sul disco NVMe (Tier 2 Cold)
    pub fn index_nvme_tensor(&self, name: &str, shard_id: usize, offset: u64, size: usize) {
        let mut nvme = self.tier2_nvme_index.write();
        nvme.insert(name.to_string(), (shard_id, offset, size));
    }

    /// Inserisce o promuove un tensore in VRAM (Tier 0 Hot)
    pub fn put_vram(&self, tensor_name: &str, layer_idx: usize, data: Arc<Vec<u8>>) {
        let size = data.len();
        let tick = self.access_counter.fetch_add(1, Ordering::Relaxed);

        // Controllo budget VRAM ed eventuale demote in RAM
        self.enforce_vram_budget(size, layer_idx);

        let entry = CacheEntry {
            tensor_name: tensor_name.to_string(),
            layer_index: layer_idx,
            tier: CacheTier::Tier0Vram,
            temperature: TensorTemperature::Hot,
            data,
            size_bytes: size,
            last_access: tick,
            access_count: 1,
        };

        let mut vram = self.tier0_vram.write();
        if let Some(old) = vram.insert(tensor_name.to_string(), entry) {
            let mut used = self.vram_used_bytes.write();
            *used = used.saturating_sub(old.size_bytes);
        }
        let mut used = self.vram_used_bytes.write();
        *used += size;
    }

    /// Inserisce o promuove un tensore in Host RAM (Tier 1 Warm)
    pub fn put_ram(&self, tensor_name: &str, layer_idx: usize, data: Arc<Vec<u8>>) {
        let size = data.len();
        let tick = self.access_counter.fetch_add(1, Ordering::Relaxed);

        self.enforce_ram_budget(size, layer_idx);

        let entry = CacheEntry {
            tensor_name: tensor_name.to_string(),
            layer_index: layer_idx,
            tier: CacheTier::Tier1Ram,
            temperature: TensorTemperature::Warm,
            data,
            size_bytes: size,
            last_access: tick,
            access_count: 1,
        };

        let mut ram = self.tier1_ram.write();
        if let Some(old) = ram.insert(tensor_name.to_string(), entry) {
            let mut used = self.ram_used_bytes.write();
            *used = used.saturating_sub(old.size_bytes);
        }
        let mut used = self.ram_used_bytes.write();
        *used += size;
    }

    /// Ricerca gerarchica attraverso i tier: VRAM -> RAM -> NVMe Index
    pub fn get(&self, tensor_name: &str) -> Option<(Arc<Vec<u8>>, CacheTier, TensorTemperature)> {
        let tick = self.access_counter.fetch_add(1, Ordering::Relaxed);

        // 1. Check Tier 0 (VRAM)
        {
            let mut vram = self.tier0_vram.write();
            if let Some(entry) = vram.get_mut(tensor_name) {
                entry.last_access = tick;
                entry.access_count += 1;
                entry.temperature = TensorTemperature::Hot;
                self.vram_hits.fetch_add(1, Ordering::Relaxed);
                return Some((entry.data.clone(), CacheTier::Tier0Vram, TensorTemperature::Hot));
            }
        }

        // 2. Check Tier 1 (Host RAM)
        {
            let mut ram = self.tier1_ram.write();
            if let Some(entry) = ram.get_mut(tensor_name) {
                entry.last_access = tick;
                entry.access_count += 1;
                entry.temperature = TensorTemperature::Warm;
                self.ram_hits.fetch_add(1, Ordering::Relaxed);
                return Some((entry.data.clone(), CacheTier::Tier1Ram, TensorTemperature::Warm));
            }
        }

        // 3. Check Tier 2 (NVMe Index)
        {
            let nvme = self.tier2_nvme_index.read();
            if nvme.contains_key(tensor_name) {
                self.nvme_hits.fetch_add(1, Ordering::Relaxed);
                // Il tensore è su disco e necessita di essere letto via prefetch / storage fabric
                return None;
            }
        }

        self.misses.fetch_add(1, Ordering::Relaxed);
        None
    }

    /// Applica l'eviction in VRAM preservando i layer correnti o futuri immediati
    fn enforce_vram_budget(&self, needed_bytes: usize, current_layer: usize) {
        let mut used = self.vram_used_bytes.write();
        if *used + needed_bytes <= self.vram_limit_bytes {
            return;
        }

        let mut vram = self.tier0_vram.write();
        // Trova i tensori candidati alla retrocessione in RAM (layer precedenti a quello corrente)
        let mut candidates: Vec<(String, usize, u64, usize)> = vram
            .iter()
            .map(|(k, v)| (k.clone(), v.layer_index, v.last_access, v.size_bytes))
            .collect();

        // Ordina per distanza dal layer corrente (quelli più vecchi prima)
        candidates.sort_by_key(|(_, l_idx, last_acc, _)| {
            if *l_idx < current_layer {
                0 // già eseguiti: massima priorità di eviction
            } else {
                *last_acc
            }
        });

        for (name, _, _, sz) in candidates {
            if *used + needed_bytes <= self.vram_limit_bytes {
                break;
            }
            if let Some(entry) = vram.remove(&name) {
                *used = used.saturating_sub(sz);
                // Demote in RAM invece di scartare completamente
                self.put_ram(&entry.tensor_name, entry.layer_index, entry.data);
            }
        }
    }

    /// Applica l'eviction in RAM preservando i tensori necessari al prefetch
    fn enforce_ram_budget(&self, needed_bytes: usize, current_layer: usize) {
        let mut used = self.ram_used_bytes.write();
        if *used + needed_bytes <= self.ram_limit_bytes {
            return;
        }

        let mut ram = self.tier1_ram.write();
        let mut candidates: Vec<(String, usize, u64, usize)> = ram
            .iter()
            .map(|(k, v)| (k.clone(), v.layer_index, v.last_access, v.size_bytes))
            .collect();

        candidates.sort_by_key(|(_, l_idx, last_acc, _)| {
            if *l_idx < current_layer { 0 } else { *last_acc }
        });

        for (name, _, _, sz) in candidates {
            if *used + needed_bytes <= self.ram_limit_bytes {
                break;
            }
            if let Some(_entry) = ram.remove(&name) {
                *used = used.saturating_sub(sz);
                // Il tensore è salvato su NVMe, quindi può essere deallocato dalla RAM in sicurezza
            }
        }
    }

    /// Calcola le statistiche e la telemetria della cache gerarchica
    pub fn stats(&self) -> HierarchicalCacheStats {
        let vram_used = *self.vram_used_bytes.read();
        let ram_used = *self.ram_used_bytes.read();
        let v_hits = self.vram_hits.load(Ordering::Relaxed);
        let r_hits = self.ram_hits.load(Ordering::Relaxed);
        let n_hits = self.nvme_hits.load(Ordering::Relaxed);
        let m = self.misses.load(Ordering::Relaxed);

        let total_requests = v_hits + r_hits + n_hits + m;
        let hit_rate = if total_requests > 0 {
            ((v_hits + r_hits + n_hits) as f64 / total_requests as f64) * 100.0
        } else {
            0.0
        };

        HierarchicalCacheStats {
            vram_used_mb: vram_used as f64 / (1024.0 * 1024.0),
            vram_limit_mb: self.vram_limit_bytes as f64 / (1024.0 * 1024.0),
            ram_used_mb: ram_used as f64 / (1024.0 * 1024.0),
            ram_limit_mb: self.ram_limit_bytes as f64 / (1024.0 * 1024.0),
            nvme_shards_tracked: self.tier2_nvme_index.read().len(),
            hot_tensors: self.tier0_vram.read().len(),
            warm_tensors: self.tier1_ram.read().len(),
            cold_tensors: self.tier2_nvme_index.read().len(),
            vram_hits: v_hits,
            ram_hits: r_hits,
            nvme_hits: n_hits,
            misses: m,
            total_hit_rate_percent: hit_rate,
        }
    }
}

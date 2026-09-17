// crates/sigma-memory/src/nvme_prefetch.rs
// Prefetch Engine predittivo per streaming da storage NVMe / SSD
// Ispirato al PrefetchEngine di AiloFlow con controllo di memory pressure e lookahead dinamico.

use crate::hierarchical_cache::HierarchicalCache;
use crate::storage_fabric::NvmeStorageFabric;
use serde::{Deserialize, Serialize};
use sigma_core::Result;
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NvmePrefetchTelemetry {
    pub prefetches_triggered: u64,
    pub prefetch_hits: u64,
    pub prefetch_misses: u64,
    pub active_depth: usize,
    pub configured_depth: usize,
    pub throttled_due_to_pressure: bool,
    pub hit_rate_percent: f64,
}

pub struct NvmePrefetchEngine {
    cache: Arc<HierarchicalCache>,
    fabric: Arc<NvmeStorageFabric>,
    configured_depth: usize,
    current_depth: AtomicUsize,
    is_throttled: AtomicBool,

    prefetches_triggered: AtomicU64,
    prefetch_hits: AtomicU64,
    prefetch_misses: AtomicU64,
}

impl NvmePrefetchEngine {
    pub fn new(
        cache: Arc<HierarchicalCache>,
        fabric: Arc<NvmeStorageFabric>,
        configured_depth: usize,
    ) -> Self {
        Self {
            cache,
            fabric,
            configured_depth,
            current_depth: AtomicUsize::new(configured_depth),
            is_throttled: AtomicBool::new(false),
            prefetches_triggered: AtomicU64::new(0),
            prefetch_hits: AtomicU64::new(0),
            prefetch_misses: AtomicU64::new(0),
        }
    }

    /// Segnala al prefetcher che il modello sta eseguendo il layer `current_layer`
    /// Calcola il lookahead $L+1, L+depth$ e avvia lo streaming da NVMe in RAM
    pub async fn on_layer_execution_start(&self, current_layer: usize, total_layers: usize) -> Result<()> {
        let depth = self.current_depth.load(Ordering::Relaxed);

        for step in 1..=depth {
            let target_layer = current_layer + step;
            if target_layer >= total_layers {
                break;
            }

            self.trigger_layer_prefetch(target_layer).await?;
        }

        Ok(())
    }

    /// Alias rapido per notifica esecuzione layer con default di 32 layers
    pub async fn on_layer_executed(&self, layer: usize) {
        let _ = self.on_layer_execution_start(layer, 32).await;
    }

    /// Avvia la lettura asincrona dei tensori di un layer dal disco NVMe
    async fn trigger_layer_prefetch(&self, layer_idx: usize) -> Result<()> {
        let tensor_key = format!("blk.{}.weight", layer_idx);

        // Se il tensore è già presente in VRAM o RAM, è un hit di prefetch
        if self.cache.get(&tensor_key).is_some() {
            self.prefetch_hits.fetch_add(1, Ordering::Relaxed);
            return Ok(());
        }

        // Recupera le coordinate dello shard NVMe
        if let Some(shard) = self.fabric.find_shard_for_layer(layer_idx) {
            self.prefetches_triggered.fetch_add(1, Ordering::Relaxed);

            let cache_ref = self.cache.clone();
            let fabric_ref = self.fabric.clone();
            let s_id = shard.shard_id;

            // Spawna task di I/O asincrono per non bloccare il loop del modello
            tokio::spawn(async move {
                // Buffer preallocato da 4 MB per la porzione del layer
                let mut chunk = vec![0u8; 4 * 1024 * 1024];
                if let Ok(read_bytes) = fabric_ref.read_shard_chunk(s_id, 0, &mut chunk) {
                    chunk.truncate(read_bytes);
                    // Inserisce in RAM (Tier 1 Warm)
                    cache_ref.put_ram(&tensor_key, layer_idx, Arc::new(chunk));
                }
            });
        } else {
            self.prefetch_misses.fetch_add(1, Ordering::Relaxed);
        }

        Ok(())
    }

    /// Modula la profondita' di prefetch in base alla pressione della RAM
    pub fn update_memory_pressure(&self, ram_used_percent: f64) {
        if ram_used_percent > 88.0 {
            // Sotto forte pressione, riduce il lookahead a 1 solo layer per evitare OOM
            self.current_depth.store(1, Ordering::Relaxed);
            self.is_throttled.store(true, Ordering::Relaxed);
        } else {
            self.current_depth.store(self.configured_depth, Ordering::Relaxed);
            self.is_throttled.store(false, Ordering::Relaxed);
        }
    }

    /// Raccoglie la telemetria attiva del prefetch engine
    pub fn telemetry(&self) -> NvmePrefetchTelemetry {
        let triggered = self.prefetches_triggered.load(Ordering::Relaxed);
        let hits = self.prefetch_hits.load(Ordering::Relaxed);
        let misses = self.prefetch_misses.load(Ordering::Relaxed);
        let total = hits + misses;

        let rate = if total > 0 {
            (hits as f64 / total as f64) * 100.0
        } else {
            0.0
        };

        NvmePrefetchTelemetry {
            prefetches_triggered: triggered,
            prefetch_hits: hits,
            prefetch_misses: misses,
            active_depth: self.current_depth.load(Ordering::Relaxed),
            configured_depth: self.configured_depth,
            throttled_due_to_pressure: self.is_throttled.load(Ordering::Relaxed),
            hit_rate_percent: rate,
        }
    }
}

// projects/sigma_engine_rust/src/runtime/hot_reload.rs
// Ispezione e riconfigurazione a caldo (hot-reload) dello stato di runtime dell'engine.
// Consente all'operatore o agli agenti del Sigma Studio di modificare parametri operativi
// (batch_size, max_context_tokens, default_temperature, streaming_chunk_size) senza
// riavviare il processo né interrompere le richieste in volo.

use std::sync::RwLock;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineRuntimeConfig {
    pub max_batch_size: usize,
    pub max_context_tokens: usize,
    pub default_temperature: f32,
    pub streaming_chunk_size: usize,
    pub active_model_name: String,
    pub thread_pool_workers: usize,
    pub eviction_policy: String, // "lru", "fifo", "priority"
    pub zero_copy_enabled: bool,
    pub version: u64,
}

impl Default for EngineRuntimeConfig {
    fn default() -> Self {
        Self {
            max_batch_size: 32,
            max_context_tokens: 32768,
            default_temperature: 0.7,
            streaming_chunk_size: 4,
            active_model_name: "sigma-default-q4".to_string(),
            thread_pool_workers: 8,
            eviction_policy: "lru".to_string(),
            zero_copy_enabled: true,
            version: 1,
        }
    }
}

pub struct RuntimeConfigManager {
    config: RwLock<EngineRuntimeConfig>,
}

impl RuntimeConfigManager {
    pub fn new() -> Self {
        Self {
            config: RwLock::new(EngineRuntimeConfig::default()),
        }
    }

    /// Ritorna una copia snapshot della configurazione corrente di runtime.
    pub fn get_config(&self) -> EngineRuntimeConfig {
        self.config.read().unwrap().clone()
    }

    /// Applica una modifica parziale a caldo ai parametri di runtime, incrementando la versione.
    pub fn apply_hot_patch(&self, patch: serde_json::Value) -> Result<EngineRuntimeConfig, String> {
        let mut cfg = self.config.write().map_err(|e| e.to_string())?;

        if let Some(bs) = patch.get("max_batch_size").and_then(|v| v.as_u64()) {
            cfg.max_batch_size = bs as usize;
        }
        if let Some(ctx) = patch.get("max_context_tokens").and_then(|v| v.as_u64()) {
            cfg.max_context_tokens = ctx as usize;
        }
        if let Some(temp) = patch.get("default_temperature").and_then(|v| v.as_f64()) {
            cfg.default_temperature = temp as f32;
        }
        if let Some(chunk) = patch.get("streaming_chunk_size").and_then(|v| v.as_u64()) {
            cfg.streaming_chunk_size = chunk as usize;
        }
        if let Some(model) = patch.get("active_model_name").and_then(|v| v.as_str()) {
            cfg.active_model_name = model.to_string();
        }
        if let Some(policy) = patch.get("eviction_policy").and_then(|v| v.as_str()) {
            cfg.eviction_policy = policy.to_string();
        }
        if let Some(zc) = patch.get("zero_copy_enabled").and_then(|v| v.as_bool()) {
            cfg.zero_copy_enabled = zc;
        }

        cfg.version += 1;
        Ok(cfg.clone())
    }
}

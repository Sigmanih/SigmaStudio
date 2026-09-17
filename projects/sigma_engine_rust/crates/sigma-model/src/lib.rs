// crates/sigma-model/src/lib.rs
// Execution Planner e gestione modelli GGUF hardware-aware per SigmaEngine

use serde::{Deserialize, Serialize};
use sigma_core::HardwareState;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceId(pub String);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LayerPlacement {
    pub layer_index: usize,
    pub device: DeviceId,
    pub estimated_memory_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionPlan {
    pub model_id: String,
    pub architecture: String,
    pub quantization: String,
    pub total_layers: usize,
    pub context_length: usize,
    pub file_size_bytes: u64,
    pub file_size_gb: f64,
    pub tier0_gpu0_layers: usize, // es. RTX 5070 Ti (16 GB)
    pub tier1_gpu1_layers: usize, // es. RTX 5060 (8 GB)
    pub tier2_ram_layers: usize,  // System RAM offload
    pub tier3_disk_layers: usize, // SSD NVMe streaming mmap
    pub placements: Vec<LayerPlacement>,
    pub flash_attention: bool,
    pub mmap_load_time_micros: u64,
}

pub struct ExecutionPlanner;

impl ExecutionPlanner {
    pub fn plan(
        model_name: &str,
        file_size_bytes: u64,
        total_layers: usize,
        hw: Option<&HardwareState>,
        mmap_micros: u64,
    ) -> ExecutionPlan {
        Self::plan_with_meta(
            model_name,
            "transformer_generic",
            "Q4_K_S",
            file_size_bytes,
            total_layers,
            32768,
            hw,
            mmap_micros,
        )
    }

    pub fn plan_from_memory_map(
        mmap: &sigma_memory::ModelMemoryMap,
        hw: Option<&HardwareState>,
        mmap_micros: u64,
    ) -> ExecutionPlan {
        let name = mmap
            .path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();

        let ext_info = mmap.parse_extended_info();
        let arch = ext_info.as_ref().map(|e| e.architecture.as_str()).unwrap_or("qwen2");
        let layers = ext_info.as_ref().map(|e| e.block_count as usize).unwrap_or(36);
        let ctx = ext_info.as_ref().map(|e| e.context_length as usize).unwrap_or(32768);

        let quant = if name.to_lowercase().contains("q4_k_m") {
            "Q4_K_M"
        } else if name.to_lowercase().contains("q4_k_s") {
            "Q4_K_S"
        } else if name.to_lowercase().contains("q8_0") {
            "Q8_0"
        } else if name.to_lowercase().contains("f16") {
            "F16"
        } else {
            "Q4_K_S"
        };

        Self::plan_with_meta(&name, arch, quant, mmap.size(), layers, ctx, hw, mmap_micros)
    }

    pub fn plan_with_meta(
        model_name: &str,
        architecture: &str,
        quantization: &str,
        file_size_bytes: u64,
        total_layers: usize,
        context_length: usize,
        hw: Option<&HardwareState>,
        mmap_micros: u64,
    ) -> ExecutionPlan {
        let size_gb = (file_size_bytes as f64 / (1024.0 * 1024.0 * 1024.0) * 100.0).round() / 100.0;
        let per_layer_gb = size_gb / total_layers.max(1) as f64;
        let per_layer_bytes = file_size_bytes / total_layers.max(1) as u64;

        // VRAM disponibile da HardwareState o da default (16GB GPU0, 8GB GPU1)
        let (gpu0_limit_gb, gpu1_limit_gb) = if let Some(h) = hw {
            let g0 = h.gpu_memory.get(0).copied().unwrap_or(16 * 1024 * 1024 * 1024) as f64 / 1e9;
            let g1 = h.gpu_memory.get(1).copied().unwrap_or(8 * 1024 * 1024 * 1024) as f64 / 1e9;
            (g0, g1)
        } else {
            (16.0, 8.0)
        };

        // Calcolo sharding deterministico dei layer
        let gpu0_layers = ((gpu0_limit_gb * 0.9) / per_layer_gb.max(0.01)).min(total_layers as f64) as usize;
        let rem_after_gpu0 = total_layers.saturating_sub(gpu0_layers);

        let gpu1_layers = ((gpu1_limit_gb * 0.9) / per_layer_gb.max(0.01)).min(rem_after_gpu0 as f64) as usize;
        let rem_after_gpu1 = rem_after_gpu0.saturating_sub(gpu1_layers);

        // Host RAM per i successivi layer
        let ram_layers = rem_after_gpu1.min(24);
        let disk_layers = rem_after_gpu1.saturating_sub(ram_layers);

        let mut placements = Vec::with_capacity(total_layers);
        for l in 0..total_layers {
            let dev = if l < gpu0_layers {
                DeviceId("NVIDIA_RTX_5070_Ti_0".to_string())
            } else if l < gpu0_layers + gpu1_layers {
                DeviceId("NVIDIA_RTX_5060_1".to_string())
            } else if l < gpu0_layers + gpu1_layers + ram_layers {
                DeviceId("HOST_RAM".to_string())
            } else {
                DeviceId("NVME_DISK_MMAP".to_string())
            };

            placements.push(LayerPlacement {
                layer_index: l,
                device: dev,
                estimated_memory_bytes: per_layer_bytes,
            });
        }

        ExecutionPlan {
            model_id: model_name.to_string(),
            architecture: architecture.to_string(),
            quantization: quantization.to_string(),
            total_layers,
            context_length,
            file_size_bytes,
            file_size_gb: size_gb,
            tier0_gpu0_layers: gpu0_layers,
            tier1_gpu1_layers: gpu1_layers,
            tier2_ram_layers: ram_layers,
            tier3_disk_layers: disk_layers,
            placements,
            flash_attention: true,
            mmap_load_time_micros: mmap_micros,
        }
    }
}

/// Scansione ricorsiva di modelli GGUF locali
pub fn scan_directory_models(dir: &Path, max_depth: usize) -> Vec<PathBuf> {
    let mut results = Vec::new();
    if max_depth == 0 || !dir.is_dir() {
        return results;
    }
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                results.extend(scan_directory_models(&path, max_depth - 1));
            } else if path.is_file() {
                if let Some(ext) = path.extension() {
                    if ext.to_string_lossy().eq_ignore_ascii_case("gguf") {
                        results.push(path);
                    }
                }
            }
        }
    }
    results
}

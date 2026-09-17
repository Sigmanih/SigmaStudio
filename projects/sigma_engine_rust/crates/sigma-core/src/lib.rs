// crates/sigma-core/src/lib.rs
// Primitive fondamentali, tipi hardware-aware e contratti (traits) del motore SigmaEngine

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;
use uuid::Uuid;

#[derive(Error, Debug)]
pub enum EngineError {
    #[error("Errore I/O: {0}")]
    Io(#[from] std::io::Error),
    #[error("Errore serializzazione JSON: {0}")]
    Serialization(#[from] serde_json::Error),
    #[error("Risorsa non trovata: {0}")]
    NotFound(String),
    #[error("Risorse hardware insufficienti: {0}")]
    OutOfMemory(String),
    #[error("Errore esecuzione task: {0}")]
    Execution(String),
    #[error("Parametro o input non valido: {0}")]
    InvalidInput(String),
    #[error("Backend compute non disponibile: {0}")]
    BackendUnavailable(String),
}

pub type Result<T> = std::result::Result<T, EngineError>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TaskId(pub Uuid);

impl TaskId {
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for TaskId {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Priority {
    Low = 0,
    Normal = 1,
    High = 2,
    Critical = 3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Requirements {
    pub min_vram_mb: u64,
    pub min_ram_mb: u64,
    pub requires_cuda: bool,
    pub max_latency_ms: Option<u64>,
}

impl Default for Requirements {
    fn default() -> Self {
        Self {
            min_vram_mb: 0,
            min_ram_mb: 512,
            requires_cuda: false,
            max_latency_ms: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskInput {
    pub command: String,
    pub payload: serde_json::Value,
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: TaskId,
    pub input: TaskInput,
    pub priority: Priority,
    pub requirements: Requirements,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

impl Task {
    pub fn new(command: impl Into<String>, payload: serde_json::Value) -> Self {
        Self {
            id: TaskId::new(),
            input: TaskInput {
                command: command.into(),
                payload,
                metadata: HashMap::new(),
            },
            priority: Priority::Normal,
            requirements: Requirements::default(),
            created_at: chrono::Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Step {
    pub step_id: usize,
    pub name: String,
    pub completed: bool,
    pub duration_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub task_id: TaskId,
    pub success: bool,
    pub output: serde_json::Value,
    pub execution_time_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Execution {
    pub task: Task,
    pub steps: Vec<Step>,
    pub status: String,
}

#[async_trait]
pub trait Executor: Send + Sync {
    async fn execute(&self, task: Task) -> Result<ExecutionResult>;
}

/// Stato hardware rilevato in tempo reale per pianificazione deterministica
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareState {
    pub cpu_threads: usize,
    pub ram_bytes: u64,
    pub gpu_memory: Vec<u64>,
    pub gpu_compute: Vec<f32>,
    pub gpu_names: Vec<String>,
}

impl HardwareState {
    pub fn total_vram_gb(&self) -> f64 {
        let total: u64 = self.gpu_memory.iter().sum();
        (total as f64 / (1024.0 * 1024.0 * 1024.0) * 100.0).round() / 100.0
    }

    pub fn ram_gb(&self) -> f64 {
        (self.ram_bytes as f64 / (1024.0 * 1024.0 * 1024.0) * 100.0).round() / 100.0
    }
}

/// Requisiti per piazzamento e offload del modello
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelRequirements {
    pub ram_bytes: u64,
    pub vram_bytes: u64,
    pub cuda_required: bool,
    pub context_tokens: usize,
}

/// Astrazione hardware per backend di computazione (CUDA, Vulkan, CPU, Metal)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComputeBuffer {
    pub id: usize,
    pub size_bytes: usize,
    pub device_id: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ComputeOperation {
    MatMul { m: usize, n: usize, k: usize },
    Softmax { len: usize },
    LayerNorm { len: usize },
}

#[async_trait]
pub trait ComputeBackend: Send + Sync {
    fn device_count(&self) -> usize;
    fn allocate(&self, device_id: usize, size: usize) -> Result<ComputeBuffer>;
    fn copy(&self, src: &ComputeBuffer, dst: &ComputeBuffer) -> Result<()>;
    fn execute_op(&self, op: ComputeOperation) -> Result<()>;
}

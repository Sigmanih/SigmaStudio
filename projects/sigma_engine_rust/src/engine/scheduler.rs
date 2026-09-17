// projects/sigma_engine_rust/src/engine/scheduler.rs
// Scheduler per continuous batching e accodamento asincrono delle richieste di inferenza.
// Garantisce la massima efficienza nell'utilizzo delle risorse computazionali.

use std::sync::atomic::{AtomicU64, Ordering};
use tokio::sync::mpsc;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceJob {
    pub id: u64,
    pub prompt: String,
    pub max_tokens: usize,
    pub temperature: f32,
    pub priority: u8, // 0 = standard, 10 = prioritario
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerationToken {
    pub job_id: u64,
    pub token: String,
    pub is_last: bool,
}

pub struct ContinuousBatchScheduler {
    job_counter: AtomicU64,
    sender: mpsc::Sender<InferenceJob>,
}

impl ContinuousBatchScheduler {
    pub fn new(capacity: usize) -> (Self, mpsc::Receiver<InferenceJob>) {
        let (sender, rx) = mpsc::channel(capacity);
        (
            Self {
                job_counter: AtomicU64::new(1),
                sender,
            },
            rx,
        )
    }

    /// Invia un nuovo job di generazione al motore continuo.
    pub async fn submit_job(
        &self,
        prompt: String,
        max_tokens: usize,
        temperature: f32,
    ) -> Result<u64, String> {
        let job_id = self.job_counter.fetch_add(1, Ordering::SeqCst);
        let job = InferenceJob {
            id: job_id,
            prompt,
            max_tokens,
            temperature,
            priority: 0,
        };

        self.sender
            .send(job)
            .await
            .map_err(|e| format!("Coda scheduler satura o interrotta: {}", e))?;

        Ok(job_id)
    }
}

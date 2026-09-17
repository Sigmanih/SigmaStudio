// crates/sigma-scheduler/src/lib.rs
// Scheduler concorrente hardware-aware, coda di priorità e continuous batching

use parking_lot::Mutex;
use sigma_core::{EngineError, ExecutionResult, Priority, Result, Task};
use std::collections::BinaryHeap;
use std::cmp::Ordering;
use std::sync::Arc;
use tokio::sync::{mpsc, oneshot};

#[derive(Debug)]
struct ScheduledJob {
    priority: Priority,
    task: Task,
    response_tx: oneshot::Sender<ExecutionResult>,
}

impl PartialEq for ScheduledJob {
    fn eq(&self, other: &Self) -> bool {
        self.priority == other.priority && self.task.id == other.task.id
    }
}

impl Eq for ScheduledJob {}

impl Ord for ScheduledJob {
    fn cmp(&self, other: &Self) -> Ordering {
        self.priority.cmp(&other.priority)
    }
}

impl PartialOrd for ScheduledJob {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

pub struct ContinuousBatchScheduler {
    capacity: usize,
    queue: Arc<Mutex<BinaryHeap<ScheduledJob>>>,
    notifier_tx: mpsc::Sender<()>,
}

impl ContinuousBatchScheduler {
    pub fn new(capacity: usize) -> (Self, mpsc::Receiver<()>) {
        let (notifier_tx, notifier_rx) = mpsc::channel(capacity);
        let scheduler = Self {
            capacity,
            queue: Arc::new(Mutex::new(BinaryHeap::with_capacity(capacity))),
            notifier_tx,
        };
        (scheduler, notifier_rx)
    }

    pub async fn submit(&self, task: Task) -> Result<oneshot::Receiver<ExecutionResult>> {
        let (tx, rx) = oneshot::channel();
        let job = ScheduledJob {
            priority: task.priority,
            task,
            response_tx: tx,
        };

        {
            let mut q = self.queue.lock();
            if q.len() >= self.capacity {
                return Err(EngineError::OutOfMemory("Coda scheduler satura".to_string()));
            }
            q.push(job);
        }

        let _ = self.notifier_tx.send(()).await;
        Ok(rx)
    }

    pub fn pop_batch(&self, max_batch_size: usize) -> Vec<(Task, oneshot::Sender<ExecutionResult>)> {
        let mut q = self.queue.lock();
        let mut batch = Vec::with_capacity(max_batch_size.min(q.len()));
        while let Some(job) = q.pop() {
            batch.push((job.task, job.response_tx));
            if batch.len() >= max_batch_size {
                break;
            }
        }
        batch
    }

    pub fn pending_count(&self) -> usize {
        self.queue.lock().len()
    }
}

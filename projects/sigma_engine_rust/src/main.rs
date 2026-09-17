// projects/sigma_engine_rust/src/main.rs
// Entrypoint del Micro-Kernel Computazionale SigmaEngine in Rust

use parking_lot::RwLock;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Instant;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use sigma_agent::AgentPipeline;
use sigma_core::HardwareState;
use sigma_memory::PagedKVCache;
use sigma_network::{create_router, NetworkState};
use sigma_tools::ToolRegistry;

#[tokio::main]
async fn main() {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "sigma_engine_rust=info,sigma_network=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    tracing::info!("============================================================");
    tracing::info!(" Avvio SigmaEngine Native Rust Kernel (Multi-Crate Workspace)");
    tracing::info!("============================================================");

    // Rilevamento / Calibrazione HardwareState (RTX 5070 Ti 16GB + RTX 5060 8GB + 96GB RAM)
    let hw = HardwareState {
        cpu_threads: std::thread::available_parallelism().map(|n| n.get()).unwrap_or(16),
        ram_bytes: 96 * 1024 * 1024 * 1024,
        gpu_memory: vec![16 * 1024 * 1024 * 1024, 8 * 1024 * 1024 * 1024],
        gpu_compute: vec![12.0, 12.0],
        gpu_names: vec![
            "NVIDIA GeForce RTX 5070 Ti (16 GB)".to_string(),
            "NVIDIA GeForce RTX 5060 (8 GB)".to_string(),
        ],
    };

    tracing::info!(
        "Hardware: VRAM Totale = {:.2} GB | RAM Host = {:.2} GB | Dispositivi GPU = {:?}",
        hw.total_vram_gb(),
        hw.ram_gb(),
        hw.gpu_names
    );

    let kv_cache = Arc::new(PagedKVCache::new(2048, 16));
    let tools = Arc::new(ToolRegistry::new());
    let agent_pipeline = Arc::new(AgentPipeline::new(tools.clone()));
    let hardware = Arc::new(RwLock::new(hw));

    let state = NetworkState {
        kv_cache,
        tools,
        agent_pipeline,
        start_time: Instant::now(),
        hardware,
    };

    let app = create_router(state);

    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8080);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    tracing::info!("SigmaEngine Kernel attivo e in ascolto su http://{}", addr);

    let listener = match tokio::net::TcpListener::bind(addr).await {
        Ok(l) => l,
        Err(e) => {
            tracing::error!("Impossibile associare listener alla porta {}: {}", port, e);
            return;
        }
    };

    if let Err(err) = axum::serve(listener, app).await {
        tracing::error!("Errore nel server HTTP: {}", err);
    }
}

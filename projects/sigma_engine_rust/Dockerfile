# Multi-stage Dockerfile per Sigma Engine Rust
# Stage 1: Build & Quality Gates (rust:slim supporta tutte le ultime feature e dipendenze)
FROM rust:slim AS builder

WORKDIR /usr/src/sigma_engine_rust

# Dipendenze di sistema minime per build e testing
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia la workspace con tutti i crates e il codice sorgente
COPY Cargo.toml ./
COPY crates ./crates
COPY src ./src

RUN cargo build --release

# Stage 2: Runtime minimale (debian:bookworm-slim)
FROM debian:bookworm-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia l'eseguibile binario compilato dallo stage builder
COPY --from=builder /usr/src/sigma_engine_rust/target/release/sigma_engine_rust /app/sigma_engine_rust

# Directory dati per pesi mmap e configurazione runtime
RUN mkdir -p /app/data /app/weights

ENV PORT=8080
ENV RUST_LOG=info
ENV SIGMA_TIER_DISK_DIR=/app/weights

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/sigma_engine_rust"]

"""Sharding multi-GPU del generatore di pesi.

Il profiling del loop FWE dice che il ~94% del tempo se ne va nel generatore
applicato a tutti i blocchi (67% backward + 27% forward), mentre il modello
target pesa lo 0%. Quel lavoro e' **indipendente blocco per blocco**: si puo'
distribuire su piu' GPU senza toccare la matematica.

Schema
------
    device primario (il piu' veloce)      device worker
    ├─ modello Qwen manuale               ├─ replica del generatore
    ├─ buffer dei pesi W_buf/real_buf     └─ propria fetta di blocchi
    ├─ replica del generatore
    └─ ottimizzatore Adam

Per ogni step:
  1. ogni device genera la propria fetta di blocchi; i worker copiano il
     risultato nel buffer del primario;
  2. il primario calcola i gradienti sul modello target (fase trascurabile);
  3. la fetta di `dout` di ogni worker viene inviata al device corrispondente,
     che accumula i gradienti degli adattatori sulla propria porzione;
  4. i gradienti vengono sommati sul primario, Adam aggiorna i parametri e li
     ridistribuisce ai worker.

Il traffico PCIe e' di circa 1 GB per step: decine di millisecondi contro
decine di secondi di calcolo. Le fette sono proporzionali alla throughput
**misurata** di ogni scheda, non al numero di core: su GPU diverse una
divisione a meta' sarebbe limitata dalla piu' lenta.
"""
from __future__ import annotations

import threading
import time

import torch

from ..config import torch_device


def free_vram_bytes(device) -> int:
    """Memoria libera sul device (0 = sconosciuta / non CUDA)."""
    if getattr(device, "type", "") != "cuda":
        return 0
    try:
        free, _total = torch.cuda.mem_get_info(device)
        return int(free)
    except Exception:
        return 0


def probe_memory_per_block(build_replica, device, probe: int = 256) -> int:
    """Byte di attivazioni per blocco, misurati con un forward+backward reale.

    Il generatore salva le attivazioni di 12 layer AILO (SwiGLU a inter=3072):
    il costo per blocco e' lineare ma non ovvio da stimare a mano, e determina
    il chunk massimo sostenibile da ogni scheda.
    """
    if getattr(device, "type", "") != "cuda":
        return 0
    gen, ctx = build_replica(device)
    n = min(probe, ctx[0].shape[0])
    dout = torch.zeros(n, gen.bs * gen.bs, device=device)
    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    before = torch.cuda.memory_allocated(device)
    gen.forward(*(t[:n] for t in ctx))
    gen.backward(dout)
    torch.cuda.synchronize(device)
    peak = torch.cuda.max_memory_allocated(device) - before
    del gen, dout
    torch.cuda.empty_cache()
    return max(1, int(peak / max(1, n)))


def chunk_for_devices(devices, base_chunk: int, bytes_per_block=None,
                      reserve_bytes=None, safety: float = 0.55, minimum: int = 64):
    """Chunk massimo sostenibile da ogni device.

    `reserve_bytes[i]` e' la memoria che quel device allochera' DOPO questa
    chiamata (sul primario: i buffer dei pesi e dei gradienti del modello
    target, diversi GB). Ignorarla e' esattamente l'errore che manda in OOM la
    scheda piu' grande: al momento del calcolo sembra la piu' libera, ma e'
    l'unica che deve ancora ospitare quei buffer.
    """
    n = len(devices)
    bytes_per_block = bytes_per_block or [0] * n
    reserve_bytes = reserve_bytes or [0] * n

    chunks = []
    for dev, per_block, reserve in zip(devices, bytes_per_block, reserve_bytes):
        free = free_vram_bytes(dev)
        if free <= 0 or per_block <= 0:
            chunks.append(base_chunk)
            continue
        budget = max(0, free - reserve) * safety
        chunks.append(max(minimum, min(base_chunk, int(budget / per_block))))
    return chunks


def measure_device_weights(build_replica, devices, chunks=None, logger=None):
    """Pesi di ripartizione ∝ throughput reale di ogni device.

    Esegue un forward+backward del generatore su ogni scheda e misura il tempo:
    e' l'unico modo onesto di bilanciare GPU di generazioni diverse. La misura
    usa il chunk con cui quel device lavorera' davvero — una scheda con meno
    VRAM gira a chunk piu' piccoli, e quindi con un'efficienza diversa da quella
    che si misurerebbe a parita' di chunk.
    """
    chunks = chunks or [256] * len(devices)
    weights = []
    for dev, chunk in zip(devices, chunks):
        gen, ctx = build_replica(dev)
        probe_blocks = min(chunk, ctx[0].shape[0])
        bid, tid, lid, cont = (t[:probe_blocks] for t in ctx)
        n = bid.shape[0]
        dout = torch.zeros(n, gen.bs * gen.bs, device=dev)
        gen.forward(bid, tid, lid, cont)           # warm-up (allocatore + cudnn)
        gen.backward(dout)
        if dev.type == "cuda":
            torch.cuda.synchronize(dev)
        t0 = time.time()
        for _ in range(2):
            gen.forward(bid, tid, lid, cont)
            gen.backward(dout)
        if dev.type == "cuda":
            torch.cuda.synchronize(dev)
        elapsed = time.time() - t0
        throughput = 2 * n / max(elapsed, 1e-6)          # blocchi/s a quel chunk
        weights.append(throughput)
        if logger:
            logger.info("Calibrazione %s: %.0f blocchi/s (chunk %d)", dev, throughput, n)
        del gen, dout
        if dev.type == "cuda":
            torch.cuda.empty_cache()
    total = sum(weights) or 1.0
    return [w / total for w in weights]


def split_ranges(num_blocks: int, weights, chunk: int = 1):
    """Intervalli contigui di blocchi proporzionali ai pesi (allineati a `chunk`)."""
    ranges, start = [], 0
    for i, w in enumerate(weights):
        if i == len(weights) - 1:
            end = num_blocks
        else:
            end = start + int(round(num_blocks * w / chunk)) * chunk
            end = min(max(end, start), num_blocks)
        ranges.append((start, end))
        start = end
    return ranges


class ShardedGenerator:
    """Generatore replicato su piu' device, con i blocchi divisi fra le schede.

    Espone al loop di training le due operazioni aggregate (`refresh` e
    `backward`) invece dei singoli chunk: i cicli sui chunk vivono qui, uno per
    device, eseguiti in thread separati cosi' le GPU lavorano davvero in
    parallelo (i lanci CUDA sono asincroni ma la loro emissione da Python no).
    """

    def __init__(self, build_replica, context, num_blocks, devices, weights,
                 chunk=1024, chunks=None, logger=None):
        self.devices = list(devices)
        self.primary = self.devices[0]
        self.logger = logger
        self.num_blocks = num_blocks

        self.ranges = split_ranges(num_blocks, weights, chunk=64)
        # `chunks` arriva gia' calcolato dal chiamante, che conosce la memoria
        # per blocco misurata e i buffer ancora da allocare; senza, si ricade su
        # una stima basata solo sulla VRAM libera in questo istante.
        self.chunks = list(chunks) if chunks else chunk_for_devices(self.devices, chunk)
        self.replicas, self.contexts = [], []
        for dev, (lo, hi), ch in zip(self.devices, self.ranges, self.chunks):
            gen, ctx = build_replica(dev)
            self.replicas.append(gen)
            # ogni device tiene solo le coordinate della propria fetta
            self.contexts.append(tuple(t[lo:hi].to(dev) for t in ctx))
            if logger:
                logger.info("Shard %s: blocchi %d-%d (%.0f%%) | chunk %d | VRAM libera %.1f GB",
                            dev, lo, hi, 100.0 * (hi - lo) / max(1, num_blocks), ch,
                            free_vram_bytes(dev) / 1024 ** 3)

        self.master = self.replicas[0]
        self._workers = list(zip(self.devices[1:], self.replicas[1:],
                                 self.contexts[1:], self.ranges[1:]))

        # Tutti i buffer di scambio sono preallocati una volta sola. Allocarli a
        # ogni step (centinaia di MB per la fetta dei blocchi) frammenta
        # l'allocatore CUDA fino all'OOM, e su Windows expandable_segments non
        # e' disponibile per rimediare.
        bs2 = self.master.bs * self.master.bs
        self._stage_out, self._stage_dout, self._recv_out = [], [], []
        for dev, _gen, _ctx, (lo, hi) in self._workers:
            n = hi - lo
            self._stage_out.append(torch.empty(n, bs2, device=dev))      # output sul worker
            self._stage_dout.append(torch.empty(n, bs2, device=dev))     # dout verso il worker
            self._recv_out.append(torch.empty(n, bs2, device=self.primary))  # ritorno sul primario

        # accumulatori dei gradienti: uno per device + le copie di ricezione
        self._partials = [[torch.zeros_like(p) for p in gen.adapter_params()]
                          for gen in self.replicas]
        self._recv_grads = [[torch.zeros_like(p, device=self.primary)
                             for p in gen.adapter_params()]
                            for gen in self.replicas[1:]]
        self.sync_params()

    # ------------------------------------------------------------- parametri

    def sync_params(self):
        """Allinea i parametri dei worker a quelli del primario (dopo Adam)."""
        master_params = self.master.params()
        for dev, gen in zip(self.devices[1:], self.replicas[1:]):
            for dst, src in zip(gen.params(), master_params):
                dst.copy_(src)
            if getattr(gen, "use_latent", False) and getattr(gen, "vq_k", 0) > 0:
                gen.latent.C.copy_(self.master.latent.C)
            if dev.type == "cuda":
                torch.cuda.synchronize(dev)

    def _run_parallel(self, fn):
        """Esegue `fn(index)` su un thread per device, propagando le eccezioni.

        Il join di un thread Python NON aspetta i kernel CUDA che ha accodato:
        senza la synchronize finale il chiamante leggerebbe buffer ancora in
        scrittura (race silenziosa che falsa i gradienti).
        """
        errors: list[BaseException] = []

        def target(i):
            dev = self.devices[i]
            try:
                if dev.type == "cuda":
                    torch.cuda.set_device(dev)
                fn(i)
                if dev.type == "cuda":
                    torch.cuda.synchronize(dev)              # i kernel sono davvero finiti
            except BaseException as exc:                     # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=target, args=(i,), daemon=True)
                   for i in range(1, len(self.devices))]
        for t in threads:
            t.start()
        target(0)                                            # il primario nel thread corrente
        for t in threads:
            t.join()
        if errors:
            raise errors[0]

    # ------------------------------------------------------------- forward

    @torch.no_grad()
    def refresh(self, real_buf, std_d, mean_d, block_size):
        """Genera tutti i blocchi e riempie `real_buf` sul device primario."""
        def work(i):
            gen, ctx = self.replicas[i], self.contexts[i]
            lo, hi = self.ranges[i]
            n = hi - lo
            ch = self.chunks[i]
            out = (real_buf if i == 0 else self._stage_out[i - 1])
            for s in range(0, n, ch):
                e = min(s + ch, n)
                blk = gen.forward(ctx[0][s:e], ctx[1][s:e], ctx[2][s:e], ctx[3][s:e])
                if i == 0:
                    sl = slice(lo + s, lo + e)
                    out[sl] = (blk.reshape(-1, block_size, block_size)
                               * std_d[sl][:, None, None] + mean_d[sl][:, None, None])
                else:
                    out[s:e] = blk

        self._run_parallel(work)

        # i worker denormalizzano sul primario: cosi' std/mean restano in un posto solo.
        # Copie bloccanti su buffer preallocati: valgono decine di ms contro decine
        # di secondi di calcolo, e non lasciano spazio a letture premature.
        for (dev, _gen, _ctx, (lo, hi)), stage, recv in zip(self._workers, self._stage_out,
                                                            self._recv_out):
            sl = slice(lo, hi)
            recv.copy_(stage)
            blk = recv.reshape(-1, block_size, block_size)
            real_buf[sl] = blk * std_d[sl][:, None, None] + mean_d[sl][:, None, None]

    # ------------------------------------------------------------- backward

    def backward(self, dout, acc):
        """Accumula in `acc` (sul primario) i gradienti degli adattatori."""
        # copia bloccante: i worker devono trovare la loro fetta gia' arrivata
        for (dev, _gen, _ctx, (lo, hi)), stage in zip(self._workers, self._stage_dout):
            stage.copy_(dout[lo:hi])

        def work(i):
            gen, ctx = self.replicas[i], self.contexts[i]
            lo, hi = self.ranges[i]
            n = hi - lo
            ch = self.chunks[i]
            local = self._partials[i]
            for buf in local:
                buf.zero_()
            source = dout[lo:hi] if i == 0 else self._stage_dout[i - 1]
            for s in range(0, n, ch):
                e = min(s + ch, n)
                gen.forward(ctx[0][s:e], ctx[1][s:e], ctx[2][s:e], ctx[3][s:e])
                gen.backward(source[s:e])
                torch._foreach_add_(local, gen.adapter_grads())

        self._run_parallel(work)

        torch._foreach_add_(acc, self._partials[0])
        for i in range(1, len(self.devices)):                # somma le parziali dei worker
            recv = self._recv_grads[i - 1]
            for dst, src in zip(recv, self._partials[i]):
                dst.copy_(src)
            torch._foreach_add_(acc, recv)

    # ------------------------------------------------------------- delega

    @property
    def latent(self):
        return self.master.latent

    def adapter_params(self):
        return self.master.adapter_params()

    def adapter_grads(self):
        return self.master.adapter_grads()

    def params(self):
        return self.master.params()


def resolve_devices(spec, logger=None):
    """Normalizza 'cuda:0,cuda:1' (o 'all') in una lista di torch.device.

    'all' seleziona tutte le GPU CUDA visibili, la piu' capiente per prima:
    il device primario ospita anche il modello target, quindi conviene sia
    quello con piu' VRAM.
    """
    if not spec:
        return []
    if isinstance(spec, (list, tuple)):
        labels = list(spec)
    elif spec.strip().lower() == "all":
        if not torch.cuda.is_available():
            return []
        order = sorted(range(torch.cuda.device_count()),
                       key=lambda i: torch.cuda.get_device_properties(i).total_memory,
                       reverse=True)
        labels = [f"cuda:{i}" for i in order]
    else:
        labels = [s.strip() for s in str(spec).split(",") if s.strip()]

    devices = []
    for label in labels:
        try:
            devices.append(torch_device(label))
        except Exception as exc:
            if logger:
                logger.warning("Device '%s' ignorato: %s", label, exc)
    return devices

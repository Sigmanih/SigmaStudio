# ==============================================================================
# core/training/forge_train.py — Pipeline di addestramento SLM da zero
# Sigma Studio v7 — Modular Training Sub-package
# ==============================================================================
"""Il motore della schermata Forge: dal corpus grezzo al modello esportato.

Fasi, tutte opzionali tranne il training:

  1. corpus     — uno o più dataset HuggingFace in streaming (i corpus italiani
                  sono troppo grandi per scaricarli interi)
  2. tokenizer  — addestrato sul corpus, oppure ereditato dall'insegnante
  3. modello    — inizializzato da zero su un preset di architettura
  4. training   — cross-entropy, distillazione dai logit, o entrambe
  5. fine-tune  — SFT su un dataset di istruzioni
  6. export     — safetensors, GGUF (F16/Q8/Q4), registrazione in Ollama

I checkpoint sono modelli HuggingFace completi, non stati intermedi: la chat di
prova può caricarli mentre il training prosegue.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path


def _log(logger, message, *args):
    if logger:
        logger.info(message, *args)
    else:
        print("[SIGMA] " + (message % args if args else message), flush=True)


# ------------------------------------------------------------------ corpus

def iter_corpus(sources, text_field="text", logger=None):
    """Testi dai dataset HuggingFace, in streaming e alternando le fonti.

    Lo streaming evita di scaricare centinaia di GB: i corpus italiani
    generalisti (FineWeb-2, mC4) sono enormi e ne serve solo una fetta.
    """
    from datasets import load_dataset

    streams = []
    for source in sources:
        dataset_id = source["id"]
        config = source.get("config") or None
        split = source.get("split") or "train"
        try:
            stream = load_dataset(dataset_id, config, split=split, streaming=True)
            streams.append((dataset_id, iter(stream), source.get("text_field") or text_field))
            _log(logger, "Corpus: %s%s in streaming", dataset_id,
                 f" [{config}]" if config else "")
        except Exception as exc:
            _log(logger, "Corpus %s non caricabile (%s): lo salto", dataset_id, exc)

    if not streams:
        raise RuntimeError("Nessuno dei dataset indicati è caricabile")

    # round-robin: mescola le fonti invece di esaurirne una alla volta
    index = 0
    while streams:
        name, stream, field = streams[index % len(streams)]
        try:
            row = next(stream)
            text = row.get(field) or row.get("text") or ""
            if isinstance(text, str) and text.strip():
                yield text
        except StopIteration:
            streams = [s for s in streams if s[1] is not stream]
            _log(logger, "Corpus %s esaurito", name)
            continue
        except Exception:
            pass
        index += 1


def train_tokenizer(sources, vocab_size, out_dir, sample_docs=50_000,
                    text_field="text", logger=None):
    """Addestra un BPE sul corpus: vocabolario su misura per la lingua.

    Un tokenizer italiano dedicato comprime il testo molto meglio di uno
    multilingua generico, e a parità di token il modello vede più contenuto.
    """
    from tokenizers import ByteLevelBPETokenizer
    from transformers import PreTrainedTokenizerFast

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _log(logger, "Addestro il tokenizer BPE (vocab %d) su %d documenti...",
         vocab_size, sample_docs)

    def corpus_iterator():
        for count, text in enumerate(iter_corpus(sources, text_field, logger)):
            if count >= sample_docs:
                break
            yield text

    specials = ["<|endoftext|>", "<|pad|>", "<|user|>", "<|assistant|>"]
    tokenizer = ByteLevelBPETokenizer()
    tokenizer.train_from_iterator(corpus_iterator(), vocab_size=vocab_size,
                                  min_frequency=2, special_tokens=specials)

    fast = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer._tokenizer if hasattr(tokenizer, "_tokenizer") else tokenizer,
        unk_token="<|endoftext|>", eos_token="<|endoftext|>",
        bos_token="<|endoftext|>", pad_token="<|pad|>",
    )
    fast.save_pretrained(out_dir)
    _log(logger, "Tokenizer salvato in %s (vocab reale %d)", out_dir, len(fast))
    return fast


def token_batches(tokenizer, sources, seq_len, batch_size, text_field="text",
                  device="cpu", logger=None):
    """Blocchi di token di lunghezza fissa, concatenando i documenti."""
    import torch

    eos = tokenizer.eos_token_id or 0
    buffer: list[int] = []
    batch: list[list[int]] = []

    for text in iter_corpus(sources, text_field, logger):
        buffer.extend(tokenizer(text, add_special_tokens=False).input_ids + [eos])
        while len(buffer) >= seq_len:
            batch.append(buffer[:seq_len])
            buffer = buffer[seq_len:]
            if len(batch) == batch_size:
                yield torch.tensor(batch, dtype=torch.long, device=device)
                batch = []


# ------------------------------------------------------------------ modello

def build_model(architecture: dict, vocab_size: int, logger=None):
    """Modello Llama-like inizializzato da zero.

    L'architettura Llama è quella con il miglior supporto nei convertitori
    GGUF: un modello forgiato qui è direttamente distribuibile su llama.cpp.
    """
    import torch
    from transformers import LlamaConfig, LlamaForCausalLM

    config = LlamaConfig(
        vocab_size=vocab_size,
        hidden_size=architecture["hidden_size"],
        num_hidden_layers=architecture["num_hidden_layers"],
        num_attention_heads=architecture["num_attention_heads"],
        num_key_value_heads=architecture["num_key_value_heads"],
        intermediate_size=architecture["intermediate_size"],
        max_position_embeddings=architecture["max_position_embeddings"],
        rms_norm_eps=1e-5,
        rope_theta=10000.0,
        tie_word_embeddings=False,
        torch_dtype="float32",
    )
    model = LlamaForCausalLM(config)
    params = sum(p.numel() for p in model.parameters())
    _log(logger, "Modello inizializzato da zero: %.1fM parametri | %d layer | "
                 "hidden %d | vocab %d",
         params / 1e6, config.num_hidden_layers, config.hidden_size, vocab_size)
    return model, config


def load_teacher(teacher_id: str, device: str, dtype, logger=None):
    """Carica l'insegnante in sola inferenza, congelato.

    Un repository ad accesso riservato produce un traceback lunghissimo che
    seppellisce l'unica informazione utile — che serve accettare i termini
    sull'hub — quindi lo si intercetta e si riscrive.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    _log(logger, "Insegnante: %s su %s", teacher_id, device)
    try:
        tokenizer = AutoTokenizer.from_pretrained(teacher_id)
        model = AutoModelForCausalLM.from_pretrained(teacher_id, dtype=dtype).to(device).eval()
    except Exception as exc:
        message = str(exc)
        if "gated" in message.lower() or "403" in message:
            raise RuntimeError(
                f"L'insegnante '{teacher_id}' è ad accesso riservato. "
                f"Apri https://huggingface.co/{teacher_id}, accetta i termini con "
                "il tuo account, verifica che il token HF sia configurato nella tab "
                "'HF Token', e riprova. In alternativa scegli un insegnante libero "
                "(la famiglia Qwen2.5 lo è)."
            ) from None
        raise

    model.requires_grad_(False)
    return model, tokenizer


def plan_devices(devices, param_count: int, teacher_params: int = 0,
                 seq_len: int = 512, vocab_size: int = 32000,
                 batch_size: int = 8, distilling: bool = False, logger=None):
    """Quali GPU possono davvero ospitare una replica, e con che quota di batch.

    Nel data-parallelismo **ogni** scheda tiene il modello intero più i suoi
    gradienti: la memoria richiesta non si divide, si moltiplica. Una GPU che
    non ci sta va esclusa, altrimenti fa fallire l'intero run — e la ripartizione
    del batch deve seguire la VRAM libera, non solo la potenza di calcolo.

    Il conto per device:
      * pesi (4 B/par) + gradienti (4 B/par);
      * **stato di AdamW**: due momenti per parametro, altri 8 B/par — solo sul
        primario, che è l'unico a ospitare l'ottimizzatore;
      * insegnante in bf16, replicato su ogni scheda che allena;
      * per sequenza, i logit: seq × vocab. In distillazione ne coesistono
        parecchie copie (studente, insegnante, softmax, log_softmax e il grafo
        del backward), non due.
    """
    import torch

    usable, capacities = [], []
    for index, device in enumerate(devices):
        if not device.startswith("cuda"):
            continue
        try:
            free, _total = torch.cuda.mem_get_info(device)
        except Exception:
            continue

        bytes_per_param = 4 + 4 + (8 if index == 0 else 0)   # pesi, grad, Adam
        fixed = param_count * bytes_per_param + teacher_params * 2
        per_seq = seq_len * vocab_size * 4 * (6 if distilling else 3)
        headroom = free - fixed - 512 * 1024 ** 2      # margine per frammentazione

        if headroom <= per_seq:
            _log(logger, "GPU %s esclusa: %.1f GB liberi non bastano per replica "
                         "(%.1f GB) + almeno una sequenza di logit (%.1f GB, "
                         "vocab %d x seq %d)",
                 device, free / 1024 ** 3, fixed / 1024 ** 3,
                 per_seq / 1024 ** 3, vocab_size, seq_len)
            continue
        usable.append(device)
        capacities.append(headroom / per_seq)          # sequenze sostenibili

    if not usable:
        return [], [], 0

    total = sum(capacities) or 1.0
    weights = [c / total for c in capacities]
    max_batch = int(sum(capacities))
    return usable, weights, max_batch


class MultiGpuStudent:
    """Studente replicato su più GPU, con il batch diviso fra le schede.

    Data-parallelismo manuale invece di DDP: su Windows DDP richiede processi
    separati e un backend che qui è fragile, mentre le due schede hanno
    throughput diverse e vanno caricate in modo diseguale — una divisione a metà
    sarebbe limitata dalla più lenta.

    Ogni replica calcola i gradienti sulla propria fetta; si sommano sul
    primario, l'ottimizzatore aggiorna lì e i pesi tornano alle repliche.
    """

    def __init__(self, model, devices, weights=None, teacher=None, logger=None):
        import copy
        import torch

        self.devices = list(devices)
        self.primary = self.devices[0]
        self.logger = logger
        self.master = model.to(self.primary)

        # pesi ∝ capacità: senza, la scheda lenta detta il passo a tutte
        if not weights:
            caps = []
            for device in self.devices:
                try:
                    props = torch.cuda.get_device_properties(device)
                    caps.append(props.multi_processor_count * props.max_threads_per_multi_processor)
                except Exception:
                    caps.append(1.0)
            total = sum(caps) or 1.0
            weights = [c / total for c in caps]
        self.weights = weights

        self.replicas = [self.master]
        for device in self.devices[1:]:
            replica = copy.deepcopy(model).to(device)
            replica.train()
            self.replicas.append(replica)

        self.teachers = []
        if teacher is not None:
            self.teachers = [teacher.to(self.primary)]
            for device in self.devices[1:]:
                self.teachers.append(copy.deepcopy(teacher).to(device).eval())

        if logger:
            _log(logger, "Studente replicato su %d GPU: %s",
                 len(self.devices),
                 ", ".join(f"{d} {w:.0%}" for d, w in zip(self.devices, self.weights)))

    def split(self, batch):
        """Fette del batch proporzionali ai pesi, una per device."""
        total = batch.shape[0]
        sizes, used = [], 0
        for index, weight in enumerate(self.weights):
            size = total - used if index == len(self.weights) - 1 else max(1, round(total * weight))
            size = max(0, min(size, total - used))
            sizes.append(size)
            used += size
        chunks, start = [], 0
        for size in sizes:
            chunks.append(batch[start:start + size] if size else None)
            start += size
        return chunks

    def step(self, batch, loss_fn):
        """Forward+backward su tutte le repliche; ritorna la loss media pesata."""
        import threading
        import torch

        chunks = self.split(batch)
        losses: dict[int, float] = {}
        errors: list[BaseException] = []

        def work(index):
            chunk = chunks[index]
            if chunk is None or chunk.shape[0] == 0:
                return
            device = self.devices[index]
            try:
                if device.startswith("cuda"):
                    torch.cuda.set_device(device)
                teacher = self.teachers[index] if self.teachers else None
                loss = loss_fn(self.replicas[index], chunk.to(device), teacher, device)
                # scala per la quota: sommando i gradienti si ottiene la media
                # sul batch completo, non la somma delle medie parziali
                (loss * (chunk.shape[0] / batch.shape[0])).backward()
                losses[index] = loss.item()
                if device.startswith("cuda"):
                    torch.cuda.synchronize(device)   # il join non aspetta i kernel
            except BaseException as exc:             # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(i,), daemon=True)
                   for i in range(1, len(self.devices))]
        for thread in threads:
            thread.start()
        work(0)
        for thread in threads:
            thread.join()
        if errors:
            raise errors[0]

        self._reduce_gradients()
        weighted = sum(losses.get(i, 0.0) * w for i, w in enumerate(self.weights))
        return weighted / max(1e-9, sum(w for i, w in enumerate(self.weights) if i in losses))

    def _reduce_gradients(self):
        """Somma sul primario i gradienti calcolati dalle repliche."""
        import torch

        if len(self.replicas) == 1:
            return
        master_params = list(self.master.parameters())
        for replica in self.replicas[1:]:
            for target, source in zip(master_params, replica.parameters()):
                if source.grad is None:
                    continue
                contribution = source.grad.to(target.device)
                target.grad = contribution if target.grad is None else target.grad + contribution

    def sync(self):
        """Ridistribuisce i pesi aggiornati e azzera i gradienti delle repliche."""
        import torch

        with torch.no_grad():
            master_params = list(self.master.parameters())
            for replica in self.replicas[1:]:
                for source, target in zip(master_params, replica.parameters()):
                    target.copy_(source.to(target.device))
                replica.zero_grad(set_to_none=True)

    def parameters(self):
        return self.master.parameters()

    def train(self):
        for replica in self.replicas:
            replica.train()
        return self

    def zero_grad(self, set_to_none=True):
        for replica in self.replicas:
            replica.zero_grad(set_to_none=set_to_none)


def distillation_loss(student_logits, teacher_logits, temperature: float):
    """KL(insegnante ‖ studente) sulle distribuzioni ammorbidite.

    La temperatura appiattisce le distribuzioni: lo studente impara anche dalle
    alternative che l'insegnante considera plausibili, non solo dal token
    vincente. Il fattore T² mantiene i gradienti sulla stessa scala della
    cross-entropy quando si sommano le due perdite.
    """
    import torch.nn.functional as F

    student = F.log_softmax(student_logits / temperature, dim=-1)
    teacher = F.softmax(teacher_logits / temperature, dim=-1)
    return F.kl_div(student, teacher, reduction="batchmean") * (temperature ** 2)


# ------------------------------------------------------------------ training

def run_forge(config: dict, logger=None) -> dict:
    """Esegue la pipeline completa descritta da `config`."""
    import torch

    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = out_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    mode = config.get("mode", "dataset")
    distilling = mode in ("distill", "both")
    device = config.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16}.get(
        config.get("dtype"), torch.float32)

    sources = config["sources"]
    seq_len = int(config.get("seq_len", 512))
    batch_size = int(config.get("batch_size", 8))
    max_steps = int(config.get("max_steps", 2000))
    save_every = int(config.get("save_every", 200))

    # ---------------------------------------------------------- tokenizer
    teacher = teacher_tok = None
    if distilling:
        # Vincolo non negoziabile: i logit sono confrontabili solo se studente e
        # insegnante indicizzano lo stesso vocabolario.
        teacher, teacher_tok = load_teacher(config["teacher"],
                                            config.get("teacher_device") or device,
                                            dtype, logger)
        tokenizer = teacher_tok
        _log(logger, "Tokenizer ereditato dall'insegnante (vocab %d): "
                     "necessario perché i logit siano allineati", len(tokenizer))
    elif config.get("tokenizer_mode") == "train":
        tokenizer = train_tokenizer(sources, int(config.get("vocab_size", 32000)),
                                    out_dir / "tokenizer",
                                    int(config.get("tokenizer_docs", 50000)),
                                    config.get("text_field", "text"), logger)
    else:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(config.get("tokenizer_id", "gpt2"))
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        _log(logger, "Tokenizer riusato: %s (vocab %d)",
             config.get("tokenizer_id", "gpt2"), len(tokenizer))

    # ---------------------------------------------------------- modello
    # In distillazione il vocabolario dello studente deve corrispondere a quello
    # dell'INSEGNANTE, non alla lunghezza del tokenizer: i modelli allargano
    # l'embedding oltre i token reali per allineamento (Qwen2.5: 151.936 contro
    # 151.665 token). Con la dimensione sbagliata i logit non sono confrontabili.
    vocab_size = len(tokenizer)
    if teacher is not None:
        teacher_vocab = int(getattr(teacher.config, "vocab_size", vocab_size))
        if teacher_vocab != vocab_size:
            _log(logger, "Vocabolario allineato all'insegnante: %d (il tokenizer "
                         "ne dichiara %d, l'embedding è padded)",
                 teacher_vocab, vocab_size)
        vocab_size = teacher_vocab

    model, model_config = build_model(config["architecture"], vocab_size, logger)
    if config.get("gradient_checkpointing"):
        model.gradient_checkpointing_enable()

    # Data-parallelismo su tutte le GPU che reggono una replica intera. Il
    # modello non si divide fra le schede: si duplica, quindi una GPU troppo
    # piccola va esclusa invece di far fallire il run.
    devices = [d for d in (config.get("devices") or [device]) if d]
    param_count = sum(p.numel() for p in model.parameters())
    teacher_params = sum(p.numel() for p in teacher.parameters()) if teacher else 0

    parallel = False
    if len(devices) > 1 and all(d.startswith("cuda") for d in devices):
        usable, weights, max_batch = plan_devices(
            devices, param_count, teacher_params, seq_len, vocab_size,
            batch_size, distilling, logger)
        if len(usable) > 1:
            if max_batch and batch_size > max_batch:
                _log(logger, "Batch ridotto da %d a %d: è il massimo che le "
                             "schede reggono con questa architettura",
                     batch_size, max_batch)
                batch_size = max_batch
            model = MultiGpuStudent(model, usable, weights, teacher, logger)
            devices, device, parallel = usable, usable[0], True
        else:
            _log(logger, "Una sola GPU regge la replica: training su %s", devices[0])
            devices = [devices[0]]
            device = devices[0]
            model = model.to(device)
    else:
        model = model.to(device)

    # Anche su una sola scheda il batch va verificato: senza questo controllo il
    # run parte, fa uno step e muore di OOM al secondo — dopo aver già scaricato
    # corpus e insegnante.
    if not parallel and device.startswith("cuda"):
        _usable, _weights, max_batch = plan_devices(
            [device], param_count, teacher_params if teacher is not None else 0,
            seq_len, vocab_size, batch_size, distilling, logger)
        if not _usable:
            raise RuntimeError(
                f"Configurazione troppo grande per {device}: modello da "
                f"{param_count / 1e6:.0f}M parametri con vocabolario {vocab_size:,} "
                f"e sequenze da {seq_len} token. "
                "Riduci l'architettura, accorcia la sequenza, oppure scegli un "
                "insegnante con vocabolario compatto (Minerva, 32.768 token): "
                "le embedding scalano con il vocabolario e qui dominano la memoria.")
        if max_batch and batch_size > max_batch:
            _log(logger, "Batch ridotto da %d a %d: è il massimo che %s regge "
                         "con questa architettura", batch_size, max_batch, device)
            batch_size = max_batch

    optimizer = torch.optim.AdamW(model.parameters(),
                                  lr=float(config.get("learning_rate", 3e-4)),
                                  weight_decay=0.01, betas=(0.9, 0.95))
    # OneCycleLR richiede fasi di almeno due step: su run brevissimi (prove,
    # smoke test) genererebbe una divisione per zero. Sotto quella soglia lo
    # scheduler non serve comunque a nulla, quindi si tiene il LR costante.
    warmup = min(max(10, int(max_steps * 0.02)), max(2, max_steps // 5))
    if max_steps >= 20:
        schedule = torch.optim.lr_scheduler.OneCycleLR(
            optimizer, max_lr=float(config.get("learning_rate", 3e-4)),
            total_steps=max_steps, pct_start=warmup / max_steps, anneal_strategy="cos")
    else:
        schedule = torch.optim.lr_scheduler.ConstantLR(optimizer, factor=1.0,
                                                       total_iters=max_steps)
        _log(logger, "Run breve (%d step): learning rate costante", max_steps)
    scaler = torch.amp.GradScaler(device.split(":")[0]) if dtype == torch.float16 else None

    alpha = float(config.get("distill_alpha", 0.5))
    temperature = float(config.get("distill_temperature", 2.0))
    _log(logger, "Modalità '%s'%s | seq %d | batch %d | %d step",
         mode,
         f" (alpha {alpha}, T {temperature})" if distilling else "",
         seq_len, batch_size, max_steps)

    batches = token_batches(tokenizer, sources, seq_len, batch_size,
                            config.get("text_field", "text"), device, logger)

    def compute_loss(student, chunk, chunk_teacher, chunk_device):
        """Perdita su una fetta di batch: CE, KL o combinazione."""
        with torch.autocast(chunk_device.split(":")[0], dtype=dtype,
                            enabled=dtype != torch.float32):
            output = student(chunk, labels=chunk)
            ce = output.loss
            if not distilling or chunk_teacher is None:
                return ce
            # L'insegnante può stare su un'altra scheda (es. quando lo studente
            # torna su una sola GPU): il batch va portato da lui e i logit
            # riportati indietro.
            teacher_device = next(chunk_teacher.parameters()).device
            with torch.no_grad():
                reference = chunk_teacher(chunk.to(teacher_device))
            kd = distillation_loss(output.logits,
                                   reference.logits.to(output.logits.device),
                                   temperature)
            return (1 - alpha) * kd if mode == "distill" else alpha * ce + (1 - alpha) * kd

    model.train()
    started = time.time()
    step = 0
    tokens_seen = 0
    history = []

    for batch in batches:
        if step >= max_steps:
            break
        step += 1
        tokens_seen += batch.numel()

        if parallel:
            loss_value = model.step(batch, compute_loss)
        else:
            loss = compute_loss(model, batch, teacher, device)
            loss_value = loss.item()
            if scaler:
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
            else:
                loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        if scaler and not parallel:
            scaler.step(optimizer); scaler.update()
        else:
            optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        if parallel:
            model.sync()
        schedule.step()

        if step % 10 == 0 or step == 1:
            elapsed = time.time() - started
            perplexity = math.exp(min(20, loss_value))
            speed = tokens_seen / max(1e-6, elapsed)
            eta = (max_steps - step) * (elapsed / step) / 60
            vram = ""
            if device.startswith("cuda"):
                vram = " | VRAM %.1f GB" % (torch.cuda.max_memory_allocated() / 1024 ** 3)
            _log(logger, "step %d/%d (%.1f%%) - loss: %.4f | ppl %.1f | %.0f tok/s | "
                         "%.1fM token | ETA %dm%s",
                 step, max_steps, 100.0 * step / max_steps, loss_value, perplexity,
                 speed, tokens_seen / 1e6, int(eta), vram)
            history.append({"step": step, "loss": round(loss_value, 4),
                            "ppl": round(perplexity, 2)})

        if save_every and step % save_every == 0:
            save_checkpoint(model.master if parallel else model, tokenizer,
                            ckpt_dir / f"step-{step}", step, logger)
            prune_checkpoints(ckpt_dir, keep=int(config.get("keep_checkpoints", 3)))

    final_dir = out_dir / "model"
    trained = model.master if parallel else model
    save_checkpoint(trained, tokenizer, final_dir, step, logger, final=True)
    (out_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    result = {
        "success": True,
        "model_dir": str(final_dir),
        "steps": step,
        "tokens_seen": tokens_seen,
        "final_loss": history[-1]["loss"] if history else None,
        "final_ppl": history[-1]["ppl"] if history else None,
        "params_m": round(sum(p.numel() for p in trained.parameters()) / 1e6, 1),
        "devices": devices,
        "vocab_size": vocab_size,
        "hours": round((time.time() - started) / 3600, 2),
    }
    _log(logger, "Training completato: %d step, %.1fM token, ppl finale %.1f",
         step, tokens_seen / 1e6, result["final_ppl"] or 0)
    return result


def save_checkpoint(model, tokenizer, path, step, logger=None, final=False):
    """Salva un checkpoint come modello HF completo.

    Completo e non parziale di proposito: la chat di prova deve poterlo caricare
    così com'è, mentre il training prosegue.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(path, safe_serialization=True)
    tokenizer.save_pretrained(path)
    (path / "sigma_step.json").write_text(
        json.dumps({"step": step, "final": final, "saved_at": time.time()}),
        encoding="utf-8")
    _log(logger, "%s -> %s (step %d)", "Modello finale" if final else "Checkpoint",
         path, step)


def prune_checkpoints(ckpt_dir, keep: int = 3):
    """Tiene solo gli ultimi N checkpoint: un modello piccolo pesa comunque MB."""
    checkpoints = sorted(Path(ckpt_dir).glob("step-*"),
                         key=lambda p: int(p.name.split("-")[1]) if p.name.split("-")[1].isdigit() else 0)
    import shutil
    for old in checkpoints[:-keep] if keep > 0 else []:
        shutil.rmtree(old, ignore_errors=True)


# ------------------------------------------------------------------ SFT

def run_finetune(config: dict, model_dir, logger=None) -> dict:
    """Fine-tuning supervisionato su un dataset di istruzioni italiano."""
    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer

    source = config.get("instruct_dataset")
    if not source:
        return {"success": True, "skipped": True}

    _log(logger, "Fine-tuning su %s", source["id"])

    # Il pre-training è già concluso e il modello salvato: se il dataset di
    # istruzioni non è caricabile si salta la fase e si prosegue con l'export.
    # Perdere ore di training per un id sbagliato in una fase opzionale no.
    try:
        dataset = load_dataset(source["id"], source.get("config") or None,
                               split=source.get("split", "train"))
    except Exception as exc:
        _log(logger, "Dataset di istruzioni '%s' non caricabile (%s). "
                     "Salto il fine-tuning: il modello pre-addestrato resta valido "
                     "e viene esportato.", source["id"], type(exc).__name__)
        return {"success": True, "skipped": True, "error": str(exc)[:200],
                "model_dir": str(model_dir)}

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForCausalLM.from_pretrained(str(model_dir)).to(
        config.get("device", "cuda")).train()

    def to_text(row):
        instruction = row.get("instruction") or row.get("prompt") or row.get("input") or ""
        answer = row.get("output") or row.get("completion") or row.get("response") or ""
        return f"<|user|>\n{instruction}\n<|assistant|>\n{answer}{tokenizer.eos_token}"

    texts = [to_text(row) for row in dataset]
    _log(logger, "Esempi di istruzione: %d", len(texts))

    optimizer = torch.optim.AdamW(model.parameters(),
                                  lr=float(config.get("sft_learning_rate", 1e-4)))
    device = config.get("device", "cuda")
    seq_len = int(config.get("seq_len", 512))
    batch_size = max(1, int(config.get("batch_size", 8)) // 2)
    steps = int(config.get("sft_steps", 300))

    step = 0
    for epoch in range(100):
        for start in range(0, len(texts), batch_size):
            if step >= steps:
                break
            chunk = texts[start:start + batch_size]
            batch = tokenizer(chunk, return_tensors="pt", padding="max_length",
                              truncation=True, max_length=seq_len).to(device)
            loss = model(**batch, labels=batch["input_ids"]).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step(); optimizer.zero_grad(set_to_none=True)
            step += 1
            if step % 20 == 0 or step == 1:
                _log(logger, "SFT step %d/%d - loss: %.4f", step, steps, loss.item())
        if step >= steps:
            break

    out = Path(model_dir).parent / "model_sft"
    save_checkpoint(model, tokenizer, out, step, logger, final=True)
    return {"success": True, "model_dir": str(out), "steps": step,
            "final_loss": round(loss.item(), 4)}


# ------------------------------------------------------------------ export

def run_exports(model_dir, out_dir, formats, model_name, logger=None) -> dict:
    """Produce i formati richiesti a partire dal modello addestrato."""
    from core.training.gguf_export import export_gguf

    model_dir, out_dir = Path(model_dir), Path(out_dir)
    results = {"safetensors": {"success": True, "path": str(model_dir)}}

    gguf_targets = {"gguf_f16": ("f16", "F16"), "gguf_q8": ("q8_0", "Q8_0"),
                    "gguf_q4": ("q4_0", "Q4_0")}
    for form in formats:
        if form not in gguf_targets:
            continue
        quant, label = gguf_targets[form]
        target = out_dir / f"{model_name}.{label}.gguf"
        try:
            results[form] = export_gguf(model_dir, target, quant, logger)
        except Exception as exc:
            _log(logger, "Export %s fallito: %s", form, exc)
            results[form] = {"success": False, "error": str(exc)}

    if "ollama" in formats:
        results["ollama"] = _register_ollama(results, out_dir, model_name, logger)
    return results


def _register_ollama(results, out_dir, model_name, logger=None) -> dict:
    """Registra in Ollama il GGUF prodotto (Ollama non legge safetensors sciolti)."""
    import shutil
    import subprocess

    gguf = next((r["path"] for key, r in results.items()
                 if key.startswith("gguf") and r.get("success")), None)
    if not gguf:
        return {"success": False,
                "error": "Nessun GGUF disponibile: seleziona anche un formato GGUF."}

    # Percorso assoluto: con uno relativo Ollama interpreta il FROM come nome
    # di un modello del registro e risponde "invalid model name".
    gguf_path = Path(gguf).resolve()
    modelfile = Path(out_dir) / "Modelfile"
    modelfile.write_text(f'FROM {gguf_path}\nPARAMETER temperature 0.7\n'
                         f'PARAMETER top_p 0.9\n', encoding="utf-8")

    binary = shutil.which("ollama")
    if not binary:
        return {"success": False, "error": "Ollama non nel PATH",
                "modelfile": str(modelfile)}
    try:
        res = subprocess.run([binary, "create", model_name, "-f", str(modelfile)],
                             capture_output=True, text=True, timeout=900)
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    if res.returncode != 0:
        return {"success": False,
                "error": (res.stderr or res.stdout or "").strip()[-300:]}
    _log(logger, "Registrato in Ollama come '%s'", model_name)
    return {"success": True, "model_name": model_name}

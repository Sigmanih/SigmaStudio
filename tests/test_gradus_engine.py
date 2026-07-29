# ==============================================================================
# tests/test_gradus_engine.py — Gradus FWE engine: CUDA paths vs reference paths
# ==============================================================================
"""Le ottimizzazioni CUDA del motore (index_add, foreach Adam, cache RoPE,
baddbmm) devono restare MATEMATICAMENTE equivalenti al percorso originale
DirectML/CPU. Qui si confrontano i due percorsi sugli stessi input.

I test che richiedono una GPU vengono saltati se CUDA non e' disponibile.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

torch = pytest.importorskip("torch")

from gradus.config import pick_device, is_cuda, setup_device
from gradus.engine.nn import Adam, Embedding, VQLatent, is_cuda_tensor
from gradus.engine import ailo_ops

cuda_only = pytest.mark.skipif(not torch.cuda.is_available(), reason="richiede CUDA")


# =========================================================== device selection

class TestDeviceSelection:

    def test_cuda_comes_first(self):
        """L'upstream sceglieva DirectML prima di MPS: su NVIDIA deve vincere CUDA."""
        if torch.cuda.is_available():
            assert pick_device("auto") == "cuda"
        else:
            assert pick_device("auto") in ("xpu", "mps", "dml", "cpu")

    def test_explicit_device_is_respected(self):
        assert pick_device("cpu") == "cpu"

    def test_is_cuda_handles_indexed_devices(self):
        assert is_cuda("cuda") and is_cuda("cuda:1")
        assert not is_cuda("dml") and not is_cuda("cpu")

    def test_setup_device_returns_usable_pair(self):
        label, dev = setup_device("cpu")
        assert label == "cpu"
        assert torch.zeros(2, device=dev).sum().item() == 0


# =========================================================== kernel equivalence

@cuda_only
class TestCudaPathEquivalence:
    """Stesso input, due percorsi: i risultati devono coincidere in float32."""

    def test_adam_foreach_matches_loop(self):
        torch.manual_seed(0)
        shapes = [(64, 32), (128,), (256, 64)]
        p_cpu = [torch.randn(s) for s in shapes]
        p_gpu = [p.clone().cuda() for p in p_cpu]

        opt_cpu = Adam(p_cpu, lr=1e-3, clip_norm=1.0)
        opt_gpu = Adam(p_gpu, lr=1e-3, clip_norm=1.0)
        assert opt_gpu._fused and not opt_cpu._fused

        for step in range(30):
            # alterna gradienti sopra e sotto la soglia di clipping
            grads = [torch.randn(s) * (5.0 if step % 5 == 0 else 0.1) for s in shapes]
            opt_cpu.step([g.clone() for g in grads])
            opt_gpu.step([g.clone().cuda() for g in grads])

        for pc, pg in zip(p_cpu, p_gpu):
            assert torch.allclose(pc, pg.cpu(), atol=1e-5)

    def test_embedding_backward_index_add_matches_one_hot(self):
        ref = Embedding(500, 32, "cpu", seed=3)
        gpu = Embedding(500, 32, "cpu", seed=3)
        gpu.W = gpu.W.cuda()

        idx = torch.randint(0, 500, (2048,))
        dy = torch.randn(2048, 32)
        ref.forward(idx); ref.backward(dy)
        gpu.forward(idx.cuda()); gpu.backward(dy.cuda())

        assert torch.allclose(ref.dW, gpu.dW.cpu(), atol=1e-5)

    def test_vq_selects_the_same_atoms(self):
        ref = VQLatent(1000, 16, 64, "cpu", seed=5)
        gpu = VQLatent(1000, 16, 64, "cpu", seed=5)
        gpu.z.W = gpu.z.W.cuda(); gpu.C = gpu.C.cuda()
        gpu.ema_count = gpu.ema_count.cuda(); gpu.ema_sum = gpu.ema_sum.cuda()

        ids = torch.randint(0, 1000, (4096,))
        ref.forward(ids)
        gpu.forward(ids.cuda())
        assert torch.equal(ref._idx, gpu._idx.cpu())

    def test_vq_ema_matches_on_live_atoms(self):
        """Gli atomi 'morti' vengono reinizializzati a caso: gli RNG di CPU e CUDA
        sono stream diversi, quindi si confrontano solo gli atomi vivi."""
        ref = VQLatent(1000, 16, 64, "cpu", seed=5)
        gpu = VQLatent(1000, 16, 64, "cpu", seed=5)
        gpu.z.W = gpu.z.W.cuda(); gpu.C = gpu.C.cuda()
        gpu.ema_count = gpu.ema_count.cuda(); gpu.ema_sum = gpu.ema_sum.cuda()

        ids = torch.randint(0, 1000, (4096,))
        ref.forward(ids); gpu.forward(ids.cuda())
        ref.ema_update(ids); gpu.ema_update(ids.cuda())

        assert torch.allclose(ref.ema_count, gpu.ema_count.cpu(), atol=1e-4)
        live = ref.ema_count >= 1.0
        if bool(live.any()):
            assert torch.allclose(ref.C[live], gpu.C.cpu()[live], atol=1e-5)

    def test_is_cuda_tensor_discriminates(self):
        assert is_cuda_tensor(torch.zeros(1, device="cuda"))
        assert not is_cuda_tensor(torch.zeros(1))


# =========================================================== op caches

class TestMultiGpuSharding:
    """Lo split dei blocchi fra GPU deve dare gli stessi identici risultati del
    percorso a device singolo: cambia solo chi calcola cosa."""

    @staticmethod
    def _fixture(device="cpu", num_blocks=96, bs=8):
        """Generatore giocattolo + coordinate dei blocchi (niente backbone AILO)."""
        from gradus.engine.generator import ManualGenerator

        torch.manual_seed(0)
        num_types, num_layers = 4, 3

        def build_replica(dev):
            gen = ManualGenerator(num_blocks, num_types, num_layers, bs, dev,
                                  latent_dim=8, d_model=32, n_layers=2, n_heads=2,
                                  inter=64, seq_len=2, vq_k=0)
            ctx = (torch.arange(num_blocks, device=dev),
                   torch.randint(0, num_types, (num_blocks,), generator=_gen_cpu(), device="cpu").to(dev),
                   torch.randint(0, num_layers, (num_blocks,), generator=_gen_cpu(), device="cpu").to(dev),
                   _cont().to(dev))
            return gen, ctx

        def _gen_cpu():
            g = torch.Generator(device="cpu")
            g.manual_seed(7)
            return g

        def _cont():
            g = torch.Generator(device="cpu")
            g.manual_seed(11)
            return torch.rand(num_blocks, 5, generator=g)

        return build_replica, num_blocks, bs

    def test_sharded_forward_matches_single_device(self):
        from gradus.engine.multigpu import ShardedGenerator

        build_replica, num_blocks, bs = self._fixture()
        device = torch.device("cpu")

        ref_gen, ref_ctx = build_replica(device)
        expected = ref_gen.forward(*ref_ctx).reshape(-1, bs, bs)

        sharded = ShardedGenerator(build_replica, ref_ctx, num_blocks,
                                   [device, device], [0.5, 0.5], chunk=16)
        got = torch.zeros(num_blocks, bs, bs)
        std = torch.ones(num_blocks)
        mean = torch.zeros(num_blocks)
        sharded.refresh(got, std, mean, bs)

        assert torch.allclose(expected, got, atol=1e-6)

    def test_sharded_backward_matches_single_device(self):
        """Il gradiente sommato sulle fette deve valere quello calcolato in blocco."""
        from gradus.engine.multigpu import ShardedGenerator

        build_replica, num_blocks, bs = self._fixture()
        device = torch.device("cpu")
        torch.manual_seed(3)
        dout = torch.randn(num_blocks, bs * bs)

        # riferimento: un solo generatore, chunk sequenziali
        ref_gen, ref_ctx = build_replica(device)
        expected = [torch.zeros_like(p) for p in ref_gen.adapter_params()]
        chunk = 16
        for s in range(0, num_blocks, chunk):
            e = min(s + chunk, num_blocks)
            ref_gen.forward(*(t[s:e] for t in ref_ctx))
            ref_gen.backward(dout[s:e])
            torch._foreach_add_(expected, ref_gen.adapter_grads())

        # sharded: due fette sbilanciate (peggior caso di allineamento)
        sharded = ShardedGenerator(build_replica, ref_ctx, num_blocks,
                                   [device, device], [0.7, 0.3], chunk=chunk)
        got = [torch.zeros_like(p) for p in sharded.adapter_params()]
        sharded.backward(dout, got)

        for exp, act in zip(expected, got):
            assert torch.allclose(exp, act, atol=1e-5), \
                f"gradiente divergente: max|Δ|={(exp - act).abs().max():.2e}"

    def test_chunk_sizing_accounts_for_buffers_allocated_later(self):
        """Il primario alloca DOPO i buffer del modello target: ignorarli gli fa
        prendere il chunk piu' grosso proprio mentre e' il piu' stretto."""
        from gradus.engine import multigpu

        devices = [torch.device("cuda:0"), torch.device("cuda:1")]
        free = {devices[0]: 12 * 1024 ** 3, devices[1]: 6 * 1024 ** 3}
        original = multigpu.free_vram_bytes
        multigpu.free_vram_bytes = lambda d: free[d]
        try:
            per_block = [4 * 1024 ** 2, 4 * 1024 ** 2]      # 4 MB/blocco
            # senza riserva il primario prenderebbe il chunk pieno
            no_reserve = multigpu.chunk_for_devices(devices, 1024, per_block, [0, 0])
            assert no_reserve[0] > no_reserve[1]
            # con 6 GB da riservare il primario deve scendere sotto il worker
            with_reserve = multigpu.chunk_for_devices(devices, 1024, per_block,
                                                      [6 * 1024 ** 3, 0])
            assert with_reserve[0] < no_reserve[0]
            assert with_reserve[0] <= with_reserve[1]
        finally:
            multigpu.free_vram_bytes = original

    def test_precomputed_chunks_are_honoured(self):
        """I chunk calcolati dal chiamante non devono essere ricalcolati dentro
        il costruttore: solo il chiamante conosce la memoria ancora da allocare."""
        from gradus.engine.multigpu import ShardedGenerator

        build_replica, num_blocks, _bs = self._fixture()
        device = torch.device("cpu")
        _gen, ctx = build_replica(device)
        sharded = ShardedGenerator(build_replica, ctx, num_blocks,
                                   [device, device], [0.5, 0.5], chunks=[128, 32])
        assert sharded.chunks == [128, 32]

    def test_chunk_never_goes_below_the_minimum(self):
        from gradus.engine import multigpu

        devices = [torch.device("cuda:0")]
        original = multigpu.free_vram_bytes
        multigpu.free_vram_bytes = lambda d: 1024 ** 3
        try:
            chunks = multigpu.chunk_for_devices(devices, 1024, [10 * 1024 ** 3],
                                                [0], minimum=64)
            assert chunks == [64]
        finally:
            multigpu.free_vram_bytes = original

    def test_chunk_falls_back_when_memory_is_unknown(self):
        """Su CPU (o senza dati) si usa il chunk richiesto, senza indovinare."""
        from gradus.engine.multigpu import chunk_for_devices

        assert chunk_for_devices([torch.device("cpu")], 512) == [512]

    def test_ranges_cover_every_block_without_overlap(self):
        from gradus.engine.multigpu import split_ranges

        for weights in ([0.5, 0.5], [0.67, 0.33], [0.9, 0.1], [0.4, 0.35, 0.25]):
            ranges = split_ranges(349440, weights, chunk=64)
            assert ranges[0][0] == 0
            assert ranges[-1][1] == 349440
            for (_, end), (start, _) in zip(ranges, ranges[1:]):
                assert end == start, "fette sovrapposte o con buchi"

    def test_ranges_respect_the_weights(self):
        from gradus.engine.multigpu import split_ranges

        ranges = split_ranges(30000, [0.67, 0.33], chunk=64)
        big = ranges[0][1] - ranges[0][0]
        small = ranges[1][1] - ranges[1][0]
        assert 1.9 < big / small < 2.1, "la ripartizione non segue i pesi 2:1"

    def test_single_weight_gives_one_full_range(self):
        from gradus.engine.multigpu import split_ranges

        assert split_ranges(1000, [1.0]) == [(0, 1000)]

    def test_resolve_devices_handles_spec_forms(self):
        from gradus.engine.multigpu import resolve_devices

        assert resolve_devices("") == []
        assert resolve_devices("cpu") == [torch.device("cpu")]
        assert resolve_devices(["cpu", "cpu"]) == [torch.device("cpu")] * 2

    @cuda_only
    def test_resolve_all_puts_largest_gpu_first(self):
        """Il primario ospita anche il modello target: deve essere il piu' capiente."""
        from gradus.engine.multigpu import resolve_devices

        devices = resolve_devices("all")
        assert len(devices) == torch.cuda.device_count()
        vram = [torch.cuda.get_device_properties(d.index).total_memory for d in devices]
        assert vram == sorted(vram, reverse=True)


class TestPhaseProfiler:
    """Il profiler di fase serve a capire dove va il tempo del loop FWE."""

    def test_disabled_profiler_is_inert(self):
        from gradus.engine.fwe import PhaseProfiler

        prof = PhaseProfiler(enabled=False)
        prof("qualcosa")
        prof(None)
        assert prof.summary() == ""
        assert prof.totals == {}

    def test_enabled_profiler_accumulates_phases(self):
        from gradus.engine.fwe import PhaseProfiler

        prof = PhaseProfiler(enabled=True)
        prof("a")
        prof("b")
        prof(None)
        assert set(prof.totals) == {"a", "b"}
        summary = prof.summary()
        assert "a" in summary and "%" in summary

    def test_device_label_accepts_specific_gpu(self):
        """`--device cuda:1` deve arrivare fino a torch_device senza filtri."""
        from gradus.config import pick_device, is_cuda, torch_device

        assert pick_device("cuda:1") == "cuda:1"
        assert is_cuda("cuda:1")
        assert torch_device("cuda:1").index == 1


class TestOpCaches:

    def test_rope_tables_are_cached_and_correct(self):
        ailo_ops.clear_op_caches()
        cos1, sin1 = ailo_ops.rope_tables(16, 8, torch.device("cpu"))
        cos2, sin2 = ailo_ops.rope_tables(16, 8, torch.device("cpu"))
        assert cos1 is cos2 and sin1 is sin2          # stessa istanza: cache attiva
        assert cos1.shape == (1, 16, 8)
        # cos(0)=1, sin(0)=0 per la prima posizione
        assert torch.allclose(cos1[0, 0], torch.ones(8))
        assert torch.allclose(sin1[0, 0], torch.zeros(8))

    def test_qwen_rope_has_four_dims(self):
        from gradus.engine.qwen_ops import rope_tables4
        cos, _ = rope_tables4(12, 8, torch.device("cpu"))
        assert cos.shape == (1, 1, 12, 8)

    def test_causal_bias_masks_only_the_future(self):
        bias = ailo_ops.causal_bias(4, torch.device("cpu"))
        assert bias.shape == (4, 4)
        assert bias[0, 0] == 0 and bias[3, 0] == 0        # passato visibile
        assert bias[0, 3] < -1e8                          # futuro mascherato
        assert torch.equal(torch.tril(bias), torch.zeros(4, 4))

    def test_cache_keys_separate_shapes(self):
        ailo_ops.clear_op_caches()
        a = ailo_ops.causal_bias(4, torch.device("cpu"))
        b = ailo_ops.causal_bias(8, torch.device("cpu"))
        assert a.shape != b.shape


# =========================================================== gradient checks

class TestTransformersCompat:
    """Gradus era scritto per transformers 4.x. Questi test bloccano le tre
    regressioni incontrate con transformers 5.x."""

    def test_rope_theta_read_from_rope_parameters(self):
        """In 5.x `rope_theta` vive dentro `rope_parameters`, non come attributo."""
        from gradus.modelio import config_get, model_hparams

        class Cfg5:                       # config in stile transformers 5.x
            hidden_size = 896
            num_hidden_layers = 24
            num_attention_heads = 14
            num_key_value_heads = 2
            intermediate_size = 4864
            vocab_size = 151936
            rms_norm_eps = 1e-6
            rope_parameters = {"rope_type": "default", "rope_theta": 1000000.0}

        assert config_get(Cfg5(), "rope_theta") == 1000000.0
        hp = model_hparams(Cfg5())
        assert hp["theta"] == 1000000.0
        assert hp["n_kv"] == 2 and hp["hidden"] == 896

    def test_rope_theta_still_read_as_flat_attribute(self):
        """Il layout 4.x deve continuare a funzionare."""
        from gradus.modelio import model_hparams

        class Cfg4:
            hidden_size = 896
            num_hidden_layers = 24
            num_attention_heads = 14
            num_key_value_heads = 2
            intermediate_size = 4864
            vocab_size = 151936
            rms_norm_eps = 1e-6
            rope_theta = 10000.0

        assert model_hparams(Cfg4())["theta"] == 10000.0

    def test_missing_kv_heads_falls_back_to_attention_heads(self):
        """Modelli senza GQA non dichiarano num_key_value_heads."""
        from gradus.modelio import model_hparams

        class CfgNoGQA:
            hidden_size = 768
            num_hidden_layers = 12
            num_attention_heads = 12
            num_key_value_heads = None
            intermediate_size = 3072
            vocab_size = 50257
            rms_norm_eps = 1e-5

        hp = model_hparams(CfgNoGQA())
        assert hp["n_kv"] == 12
        assert hp["theta"] == 1e6                 # default

    def test_legacy_dataset_ids_are_namespaced(self):
        """HuggingFace ha ritirato gli id canonici senza namespace ('wikitext')."""
        from core.training.datasets import resolve_hf_dataset_id

        assert resolve_hf_dataset_id("wikitext") == "Salesforce/wikitext"
        assert resolve_hf_dataset_id("imdb") == "stanfordnlp/imdb"
        # gia' namespaced o sconosciuto: invariato
        assert resolve_hf_dataset_id("tatsu-lab/alpaca") == "tatsu-lab/alpaca"
        assert resolve_hf_dataset_id("mio-dataset") == "mio-dataset"
        assert resolve_hf_dataset_id("") == ""

    def test_gradus_retries_wikitext_with_alias(self, monkeypatch):
        """load_hf_dataset deve riprovare con l'alias quando l'id nudo fallisce."""
        import datasets as datasets_mod
        from gradus.modelio import load_hf_dataset

        tried = []

        def fake_load_dataset(name, *args, **kwargs):
            tried.append(name)
            if "/" not in name:
                raise ValueError(f"Repository id must be 'namespace/name', got '{name}'.")
            return {"train": []}

        monkeypatch.setattr(datasets_mod, "load_dataset", fake_load_dataset)
        result = load_hf_dataset("wikitext", "wikitext-2-raw-v1")
        assert result == {"train": []}
        assert tried == ["wikitext", "Salesforce/wikitext"]

    def test_gradus_does_not_mask_unknown_dataset_errors(self, monkeypatch):
        """Un dataset senza alias deve propagare l'errore originale."""
        import datasets as datasets_mod
        from gradus.modelio import load_hf_dataset

        def always_fail(name, *args, **kwargs):
            raise ValueError("boom")

        monkeypatch.setattr(datasets_mod, "load_dataset", always_fail)
        with pytest.raises(ValueError, match="boom"):
            load_hf_dataset("dataset-inventato")

    def test_batch_encoding_is_unwrapped_for_generate(self):
        """`apply_chat_template` in 5.x torna un BatchEncoding: generate vuole il tensore."""
        from gradus.chat import _to_input_ids

        tensor = torch.tensor([[1, 2, 3]])
        assert _to_input_ids(tensor) is tensor              # tensore: invariato

        class FakeBatchEncoding(dict):
            pass

        encoded = FakeBatchEncoding(input_ids=tensor, attention_mask=torch.ones(1, 3))
        assert _to_input_ids(encoded) is tensor             # dict-like: estratto


class TestBackboneResolution:
    """Il backbone AILO non deve dipendere dalla directory di lavoro: i job del
    Training Lab girano nella propria cartella."""

    def test_status_reports_search_paths(self):
        from gradus.backbone import backbone_status
        status = backbone_status()
        assert status["searched"], "nessun path di ricerca"
        assert any("training" in p for p in status["searched"])

    def test_explicit_prepared_path_wins(self, tmp_path):
        from gradus.backbone import find_backbone, is_prepared

        fake = tmp_path / "ailo_backbone"
        fake.mkdir()
        assert not is_prepared(fake)
        (fake / "config.json").write_text("{}", encoding="utf-8")
        (fake / "model.safetensors").write_bytes(b"")
        assert is_prepared(fake)
        assert find_backbone(str(fake)) == fake

    def test_search_is_cwd_independent(self, tmp_path, monkeypatch):
        """Cambiare CWD non deve far sparire il backbone gestito da Sigma."""
        from gradus.backbone import candidate_paths, DEFAULT_BACKBONE_DIR

        monkeypatch.chdir(tmp_path)
        paths = candidate_paths()
        assert DEFAULT_BACKBONE_DIR in paths
        assert DEFAULT_BACKBONE_DIR.is_absolute()

    def test_missing_backbone_without_download_raises_with_hints(self, tmp_path, monkeypatch):
        from gradus import backbone as bk

        monkeypatch.setattr(bk, "DEFAULT_BACKBONE_DIR", tmp_path / "assente")
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError) as err:
            bk.ensure_ailo_backbone(allow_download=False)
        assert "assente" in str(err.value)


class TestGradientChecks:
    """I gradient-check upstream (backward manuale vs autograd) devono passare
    anche dopo le ottimizzazioni."""

    def test_manual_backward_matches_autograd(self):
        from gradus.engine.nn import Linear, MLP, mse_loss

        torch.manual_seed(0)
        x = torch.randn(8, 16)
        target = torch.randn(8, 4)

        mlp = MLP([16, 32, 4], "cpu", seed=0)
        pred = mlp.forward(x)
        loss, dpred = mse_loss(pred, target)
        mlp.backward(dpred)

        # stessa rete in autograd
        w1 = mlp.l1.W.clone().requires_grad_(True)
        b1 = mlp.l1.b.clone().requires_grad_(True)
        w2 = mlp.l2.W.clone().requires_grad_(True)
        b2 = mlp.l2.b.clone().requires_grad_(True)
        h = torch.nn.functional.silu(x @ w1.t() + b1)
        out = h @ w2.t() + b2
        ref_loss = ((out - target) ** 2).mean()
        ref_loss.backward()

        assert loss.item() == pytest.approx(ref_loss.item(), rel=1e-5)
        assert torch.allclose(mlp.l1.dW, w1.grad, atol=1e-5)
        assert torch.allclose(mlp.l2.dW, w2.grad, atol=1e-5)
        assert torch.allclose(mlp.l1.db, b1.grad, atol=1e-5)

    def test_attention_backward_matches_autograd(self):
        """L'attenzione ora usa baddbmm + maschera in cache: il backward manuale
        deve restare corretto."""
        from gradus.engine.ailo_ops import Attention

        torch.manual_seed(1)
        attn = Attention(dim=16, n_heads=4, dev="cpu")
        x = torch.randn(2, 6, 16, requires_grad=True)

        out = attn.forward(x.detach())
        dy = torch.randn_like(out)
        dx_manual = attn.backward(dy)

        # gradiente numerico su una singola componente
        eps = 1e-3
        i, j, k = 1, 3, 5
        xp = x.detach().clone(); xp[i, j, k] += eps
        xm = x.detach().clone(); xm[i, j, k] -= eps
        num = ((attn.forward(xp) * dy).sum() - (attn.forward(xm) * dy).sum()) / (2 * eps)

        assert dx_manual[i, j, k].item() == pytest.approx(num.item(), rel=2e-2, abs=1e-3)

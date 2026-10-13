"""Eliminazione completa delle produzioni e gestione dei modelli importati da Civitai."""

import json
from pathlib import Path

import pytest

from core.modules.sigma_creative_lab import civitai_import as C
from core.modules.sigma_creative_lab.video import production as P


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    """Produzioni, cartella condivisa di ComfyUI e uscite del Creative in una cartella temporanea."""
    store = P.ProductionStore(tmp_path / "productions")
    monkeypatch.setattr(P.manager, "store", store)
    models = tmp_path / "comfy" / "models"
    models.mkdir(parents=True)
    monkeypatch.setattr("core.modules.sigma_creative_lab.model_downloader.discover_models_root", lambda: str(models))
    monkeypatch.setattr(P.paths, "creative_output_dir", lambda kind="image": tmp_path / "creative" / "video")
    return store, tmp_path, models


def test_eliminazione_ripulisce_il_contesto(ambiente):
    store, tmp, _models = ambiente
    prod = store.create("Il faro")
    pid = prod["id"]
    (store.path(pid) / "clips").mkdir()
    (store.path(pid) / "clips" / "a.mp4").write_bytes(b"x" * 1000)
    out = tmp / "comfy" / "output" / "sigma" / pid
    out.mkdir(parents=True)
    (out / "s_00001_.mp4").write_bytes(b"y" * 500)
    inp = tmp / "comfy" / "input"
    inp.mkdir()
    (inp / f"{pid}_shot_first.png").write_bytes(b"z")
    (inp / "altro_progetto_first.png").write_bytes(b"z")
    export = tmp / "creative" / "video" / f"il_faro_{pid[-6:]}_v3.mp4"
    export.parent.mkdir(parents=True)
    export.write_bytes(b"v")
    r = P.purge_production(store, pid)
    assert r["deleted"] and r["freed_mb"] >= 0 and not store.path(pid).exists() and not out.exists()
    assert not (inp / f"{pid}_shot_first.png").exists() and (inp / "altro_progetto_first.png").exists()
    assert export.is_file() and r["kept_exports"] == [str(export)]          # il video finito resta


def test_eliminazione_anche_dei_video_esportati(ambiente):
    store, tmp, _models = ambiente
    pid = store.create("Corto")["id"]
    export = tmp / "creative" / "video" / f"corto_{pid[-6:]}.mp4"
    export.parent.mkdir(parents=True)
    export.write_bytes(b"v")
    P.purge_production(store, pid, with_exports=True)
    assert not export.exists()


def _civitai(models, name, family="ltx", present=True):
    folder = models / "loras"
    folder.mkdir(exist_ok=True)
    if present:
        (folder / name).write_bytes(b"w" * 2048)
    (folder / f"{name}.civitai.json").write_text(json.dumps({"family": family, "model_name": name}), encoding="utf-8")
    return folder / name


def test_elenco_e_rimozione_civitai(ambiente):
    store, _tmp, models = ambiente
    lora = _civitai(models, "stile.safetensors")
    _civitai(models, "interrotto.safetensors", present=False)
    (models / "loras" / "a_mano.safetensors").write_bytes(b"m")            # senza scheda: non e' nostro
    items = {i["name"]: i for i in C.list_installed(str(models))}
    assert set(items) == {"stile.safetensors", "interrotto.safetensors"} and not items["interrotto.safetensors"]["present"]
    prod = store.create("Usa la lora")
    prod["bible"]["loras"] = [{"path": str(lora)}]
    store.save(prod)
    r = C.delete_installed(str(models), "loras", "stile.safetensors")
    assert r["deleted"] is False and r["used_by"][0]["id"] == prod["id"]   # in uso: serve conferma
    assert C.delete_installed(str(models), "loras", "stile.safetensors", force=True)["deleted"]
    assert not lora.exists()
    with pytest.raises(ValueError):
        C.delete_installed(str(models), "loras", "a_mano.safetensors")    # non importato da Civitai
    with pytest.raises(ValueError):
        C.delete_installed(str(models), "../config", "x")


def test_lora_per_famiglia_del_motore(tmp_path):
    lora = tmp_path / "x.safetensors"
    lora.write_bytes(b"x")
    (tmp_path / "x.safetensors.civitai.json").write_text(json.dumps({"family": "ltx"}), encoding="utf-8")
    assert P.lora_family({"path": str(lora)}) == "ltx"
    assert P.lora_family({"path": str(tmp_path / "manuale.safetensors")}) == ""


def test_download_interrotto_si_riprende(ambiente, monkeypatch):
    # La scheda nasce all'avvio del download: senza file la voce e' "da completare", non "installata".
    _store, _tmp, models = ambiente
    _civitai(models, "interrotto.safetensors", present=False)
    side = models / "loras" / "interrotto.safetensors.civitai.json"
    side.write_text(json.dumps({"family": "ltx", "source": "https://civitai.com/models/1?modelVersionId=42"}),
                    encoding="utf-8")
    item = C.list_installed(str(models))[0]
    assert item["present"] is False and item["state"] == "incomplete"
    version = {"version_id": 42, "files": [{"id": 7, "name": "interrotto.safetensors"}]}
    monkeypatch.setattr(C, "resolve", lambda url, token="": {"versions": [version]})
    started = {}
    monkeypatch.setattr(C, "start_import", lambda v, ids, root, token="": started.update(ids=ids) or [{"status": "downloading"}])
    assert C.retry_install(str(models), "loras", "interrotto.safetensors")["status"] == "downloading"
    assert started["ids"] == [7]
    with pytest.raises(ValueError):
        C.retry_install(str(models), "loras", "../../config.json")

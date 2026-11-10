from core.harness.fs_tools import glob_workspace_files


def test_il_glob_espande_alternative_tra_parentesi_graffe(tmp_path):
    (tmp_path / "orologio.md").write_text("piano", encoding="utf-8")
    (tmp_path / "watch.cpp").write_text("firmware", encoding="utf-8")
    (tmp_path / "altro.txt").write_text("altro", encoding="utf-8")

    risultato = glob_workspace_files(str(tmp_path), "**/*{orologio,watch}*", limit=20)

    assert risultato["success"] is True
    assert {voce["rel"] for voce in risultato["files"]} == {"orologio.md", "watch.cpp"}


def test_il_glob_con_alternative_non_duplica_i_risultati(tmp_path):
    (tmp_path / "orologio_watch.txt").write_text("match doppio", encoding="utf-8")

    risultato = glob_workspace_files(str(tmp_path), "**/*{orologio,watch}*", limit=20)

    assert [voce["rel"] for voce in risultato["files"]] == ["orologio_watch.txt"]


def test_trova_le_immagini_e_non_entra_nelle_cartelle_pesanti(tmp_path, monkeypatch):
    """Video lungo, 9/11/2026: un provino .png introvabile e un glob appeso 25 minuti sul workspace."""
    from core.harness import fs_tools
    (tmp_path / "works" / "personaggi" / "sonda" / "candidates").mkdir(parents=True)
    (tmp_path / "works" / "personaggi" / "sonda" / "candidates" / "cand_1.png").write_bytes(b"png")
    pesante = tmp_path / "store" / "modelli"
    pesante.mkdir(parents=True)
    (pesante / "cand_1.png").write_bytes(b"png")
    visitate = []
    vero_walk = fs_tools.os.walk

    def walk(root, *a, **k):
        for cartella, sotto, files in vero_walk(root, *a, **k):
            visitate.append(cartella)
            yield cartella, sotto, files
    monkeypatch.setattr(fs_tools.os, "walk", walk)
    r = fs_tools.glob_workspace_files(str(tmp_path), "**/cand_1.png")
    assert [f["rel"] for f in r["files"]] == ["works/personaggi/sonda/candidates/cand_1.png"]
    assert not any("store" in c for c in visitate)


def test_glob_si_ferma_al_tempo_massimo(tmp_path, monkeypatch):
    from core.harness import fs_tools
    (tmp_path / "a").mkdir()
    monkeypatch.setattr(fs_tools, "GLOB_TIMEOUT_SECONDS", -1.0)
    r = fs_tools.glob_workspace_files(str(tmp_path), "**/introvabile.txt")
    assert r["success"] and r["truncated"] and "fermata" in r["note"]

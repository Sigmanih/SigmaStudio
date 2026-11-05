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

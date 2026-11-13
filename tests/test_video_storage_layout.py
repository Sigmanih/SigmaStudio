"""Esportazioni raccolte nel progetto senza perdere i video conservati dall'utente."""
from types import SimpleNamespace
import asyncio

import pytest

from core.modules.sigma_creative_lab.video import production, storage, editor_jobs
from core.modules.sigma_creative_lab import model_downloader


@pytest.fixture
def project(tmp_path, monkeypatch):
    store = production.ProductionStore(tmp_path / 'productions')
    prod = store.create('Natale')
    monkeypatch.setattr(production.paths, 'creative_output_dir', lambda *_: tmp_path / 'legacy')
    monkeypatch.setattr(model_downloader, 'discover_models_root', lambda: None)
    monkeypatch.setattr(editor_jobs, 'editor_jobs', lambda: SimpleNamespace(list=lambda _: [], forget=lambda _: None))
    return store, prod


def test_exports_and_editor_versions_share_project(project):
    store, prod = project
    master = storage.export_path(store, prod)
    edit = storage.export_path(store, prod, version=3)
    assert master.parent == edit.parent == store.path(prod['id']) / 'exports'
    assert master.name == 'master.mp4'
    assert edit.name == 'edit_v3.mp4'


def test_legacy_video_is_reported_without_moving_it(project, tmp_path):
    store, prod = project
    old = tmp_path / 'upload_in_corso.mp4'
    old.write_bytes(b'video precedente')
    prod['output_path'] = str(old)
    info = storage.layout(store, prod)
    assert info['legacy_export']
    assert info['current_video'] == str(old)
    assert old.read_bytes() == b'video precedente'


def test_delete_project_can_keep_all_nested_exports(project):
    store, prod = project
    master = storage.export_path(store, prod)
    master.write_bytes(b'video finale')
    subtitles = master.with_suffix('.srt')
    subtitles.write_text('sottotitoli', encoding='utf-8')
    (store.path(prod['id']) / 'clip.mp4').write_bytes(b'temporaneo')
    prod['output_path'] = str(master)
    store.save(prod)
    result = production.purge_production(store, prod['id'], with_exports=False)
    assert master.read_bytes() == b'video finale'
    assert subtitles.is_file()
    assert str(master) in result['kept_exports']
    assert not (store.path(prod['id']) / 'clip.mp4').exists()


def test_explicit_delete_includes_nested_exports(project):
    store, prod = project
    master = storage.export_path(store, prod)
    master.write_bytes(b'video finale')
    prod['output_path'] = str(master)
    store.save(prod)
    result = production.purge_production(store, prod['id'], with_exports=True)
    assert not master.exists()
    assert not result['kept_exports']


def test_unchanged_editor_timeline_reuses_video_without_copy(project, tmp_path, monkeypatch):
    from core.modules.sigma_creative_lab.video import generated_publication
    store, prod = project
    old = tmp_path / 'video_in_caricamento.mp4'
    old.write_bytes(b'master approvato')
    prod.update(status='done', output_path=str(old))
    store.save(prod)
    monkeypatch.setattr(production.shutil, 'copy2', lambda *_: pytest.fail('Il master non deve essere duplicato'))
    monkeypatch.setattr(generated_publication, 'prepare', lambda *_: {'publication_ready': True})
    editor = SimpleNamespace(prods=store, timelines=SimpleNamespace(get=lambda _: {'version': 0}),
                             _note=lambda *_: None)
    result = asyncio.run(editor_jobs.job_export(editor, {'production': prod['id']}))
    assert result['output_path'] == str(old)
    assert old.read_bytes() == b'master approvato'
    assert not list((store.path(prod['id']) / 'exports').glob('*.mp4'))

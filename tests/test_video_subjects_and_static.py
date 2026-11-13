"""Cast completo prima delle scene e loop statico senza modello video."""
import asyncio
import threading

import pytest
from PIL import Image

from core.modules.sigma_creative_lab.video import ambient_loop, production, static_loop, tools


@pytest.fixture
def studio(tmp_path, monkeypatch):
    monkeypatch.setattr(ambient_loop.paths, 'works_dir', lambda: tmp_path)
    monkeypatch.setattr(ambient_loop.paths, 'workspace_dir', lambda: tmp_path)
    store = production.ProductionStore(tmp_path / 'productions')
    monkeypatch.setattr(production.manager, 'store', store)
    monkeypatch.setattr(production.manager, 'active', lambda: None)
    anchor = tmp_path / 'scene.png'
    Image.new('RGB', (160, 90), '#b23456').save(anchor)
    return store, anchor


def test_all_declared_subjects_need_references_before_scenes(studio):
    store, anchor = studio
    result = tools.video_prod_create('Natale', 'Three robots', subjects=[
        {'name': name, 'description': f'{name} robot', 'kind': 'object'}
        for name in ('Bolt', 'Vera', 'Rust')])
    prod = store.get(result['prod_id'])
    prod['bible']['characters'][0]['ref_image'] = str(anchor)
    store.save(prod)
    result = tools.video_prod_plan_storyboard(prod['id'])
    assert not result['success']
    assert 'Vera' in result['error'] and 'Rust' in result['error']
    with pytest.raises(ValueError, match='Vera'):
        production.require_subject_references(prod)
    assert not store.get(prod['id'])['shots']


def test_unknown_shot_subject_is_rejected(studio):
    store, _ = studio
    prod = store.create('Scena', shots=[production.new_shot('Vera', refs=['Vera'])])
    with pytest.raises(ValueError, match='Vera'):
        production.require_subject_references(prod)


def test_three_robots_cannot_use_only_bolt(studio):
    store, anchor = studio
    prod = store.create('Robot', bible={'characters': [
        {'name': 'Bolt', 'description': 'Copper robot', 'ref_image': str(anchor)}]},
        shots=[production.new_shot('Three friendly cartoon3D robots celebrate Christmas', refs=['Bolt'])])
    with pytest.raises(ValueError, match='3 soggetti.*1'):
        production.require_subject_references(prod)


def test_static_plan_has_one_base_and_final_duration(studio):
    store, anchor = studio
    result = tools.video_prod_create('Natale', 'Immagine immobile', settings={
        'production_mode': 'static_loop', 'loop_base_seconds': 15,
        'loop_duration_s': 600, 'scene_reference': str(anchor)})
    result = tools.video_prod_plan_storyboard(result['prod_id'])
    assert result['success'] and result['count'] == 1
    prod = store.get(result['prod_id'])
    assert prod['shots'][0]['duration_s'] == 15
    assert production.summary(prod)['duration_s'] == 600


def test_static_render_real_ffmpeg_without_inference(studio, monkeypatch):
    store, anchor = studio
    try:
        production.ffmpeg_bin()
    except RuntimeError:
        pytest.skip('ffmpeg non disponibile')
    prod = store.create('Statica', settings={'production_mode': 'static_loop',
                       'scene_reference': str(anchor), 'loop_base_seconds': .5,
                       'loop_duration_s': 2, 'fps': 24})
    monkeypatch.setattr(production, 'generate_keyframes', lambda *a, **k: pytest.fail('Nessuna inferenza'))
    result = asyncio.run(production.ProductionRunner(store, prod['id']).run())
    assert result['status'] == 'rendered'
    assert result['quality_status'] == 'review_required'
    assert result['stats']['duration_s'] == pytest.approx(2, abs=.05)
    probe = production.probe(result['output_path'])
    assert probe['width'] == 160 and probe['height'] == 90
    assert len(result['shots']) == 1


def test_cancel_static_export(studio):
    store, anchor = studio
    prod = store.create('Statica', settings={'production_mode': 'static_loop',
                       'scene_reference': str(anchor), 'loop_base_seconds': 15, 'loop_duration_s': 600})
    cancel = threading.Event()
    cancel.set()
    result = static_loop.render(store, prod, cancel)
    assert result['status'] == 'cancelled'
    assert not result['output_path']


def test_saved_rendering_state_is_not_a_live_worker(studio):
    store, _ = studio
    prod = store.create('Interrotto')
    prod['status'] = 'rendering'
    store.save(prod)
    manager = production.ProductionManager(store)
    assert manager.runtime_view(prod)['status'] == 'interrupted'
    assert store.get(prod['id'])['status'] == 'rendering'

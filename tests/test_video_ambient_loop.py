"""Continuità della scena, pianificazione non narrativa ed esportazione ciclica reale."""
from pathlib import Path

import pytest
from PIL import Image

from core.modules.sigma_creative_lab.video import ambient_loop as ambient
from core.modules.sigma_creative_lab.video import production as production
from core.modules.sigma_creative_lab.video import tools


@pytest.fixture
def scene(tmp_path, monkeypatch):
    try:
        ffmpeg = production.ffmpeg_bin()
        ffprobe = production.ffmpeg_bin('ffprobe')
        monkeypatch.setattr(production, 'ffmpeg_bin', lambda tool='ffmpeg': ffprobe if tool == 'ffprobe' else ffmpeg)
    except RuntimeError:
        ffmpeg = None
    workspace = tmp_path / 'works'
    workspace.mkdir()
    monkeypatch.setattr(ambient.paths, 'works_dir', lambda: workspace)
    monkeypatch.setattr(ambient.paths, 'workspace_dir', lambda: tmp_path / 'data')
    monkeypatch.setattr(ambient.paths, 'project_root', lambda: tmp_path)
    anchor = workspace / 'scene.png'
    Image.new('RGB', (320, 180), '#182a40').save(anchor)
    store = production.ProductionStore(workspace / 'productions')
    prod = store.create('Camino ambientale', treatment='Natural blue fire in a fixed gothic fireplace.',
                        settings={'production_mode': 'ambient_loop', 'video_model': 'ltx25',
                                  'scene_reference': str(anchor), 'loop_base_seconds': 20,
                                  'max_clip_seconds': 10,
                                  'loop_duration_s': 43200, 'loop_crossfade_s': .25})
    return store, prod, anchor


def test_planning_uses_canonical_image_without_story_writer(scene, monkeypatch):
    store, prod, anchor = scene
    manager = production.ProductionManager(store)
    monkeypatch.setattr(production, 'manager', manager)
    monkeypatch.setattr(production, 'writer', lambda *args: pytest.fail('Non deve chiamare lo sceneggiatore'))
    result = tools.video_prod_plan_storyboard(prod['id'])
    assert result['success'], result
    assert result['target_seconds'] == 43200
    fresh = store.get(prod['id'])
    assert len(fresh['shots']) == 2
    assert {sh['keyframe'] for sh in fresh['shots']} == {str(anchor)}
    assert len({sh['scene'] for sh in fresh['shots']}) == 1
    assert not fresh['bible'].get('pre')
    assert production.summary(fresh)['duration_s'] == 43200


def test_every_variant_has_identical_start_and_end_even_after_chain_limit(scene):
    store, prod, anchor = scene
    prod['settings'].update(loop_base_seconds=60, max_chain=1)
    prod['shots'] = ambient.plan(prod)
    runner = production.ProductionRunner(store, prod['id'])
    for i in range(6):
        request = runner.build_request(prod, i)
        assert request['init_image'] == request['end_image'] == str(anchor)
        assert not request['continued']
        assert 'supporting base' in request['prompt']


def test_ambient_prompt_does_not_inject_character_motion(scene):
    store, prod, anchor = scene
    prod['settings']['motion_guard'] = True
    prod['shots'] = ambient.plan(prod)
    runner = production.ProductionRunner(store, prod['id'])
    request = runner.build_request(prod, 0)
    assert production.MOTION_GUARD not in request['prompt']
    assert 'footsteps' not in request['prompt'].lower()
    narrative = {**prod, 'settings': {**prod['settings'], 'production_mode': 'narrative'}}
    assert production.MOTION_GUARD in production.compose_prompt(narrative, prod['shots'][0], False)


@pytest.mark.parametrize('value', ['https://example.com/scene.png', '/works/../config/private.png', ''])
def test_invalid_reference_is_rejected(scene, value):
    with pytest.raises(ValueError):
        ambient.reference(value)


def test_local_workspace_url_is_resolved(scene):
    assert ambient.reference('http://localhost:8000/works/scene.png') == scene[2]


@pytest.mark.parametrize('patch', [{'loop_duration_s': float('nan')}, {'loop_crossfade_s': 7},
                                 {'output_width': 3839}, {'production_mode': 'unknown'}])
def test_settings_reject_invalid_values(patch):
    with pytest.raises(ValueError):
        production.validate_settings(patch)


def test_music_and_missing_anchor_cannot_silently_fall_back(scene):
    _, prod, _ = scene
    prod['soundtrack']['enabled'] = True
    with pytest.raises(ValueError, match='musicale'):
        ambient.plan(prod)
    prod['soundtrack']['enabled'] = False
    prod['settings']['scene_reference'] = ''
    with pytest.raises(ValueError):
        ambient.plan(prod)


@pytest.mark.parametrize('speed', [1.0, 0.65])
def test_real_ffmpeg_loop_has_exact_duration_audio_and_no_crop(scene, monkeypatch, speed):
    store, prod, _ = scene
    try:
        ff = production.ffmpeg_bin()
    except RuntimeError:
        pytest.skip('ffmpeg non disponibile')
    from core.modules.sigma_creative_lab.video import postprocess
    monkeypatch.setattr(postprocess, 'video_encoder_args', lambda quality, gpu=0: [
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-pix_fmt', 'yuv420p'])
    prod['settings'].update(loop_duration_s=9, loop_base_seconds=4, output_width=320, output_height=0,
                            loop_motion_speed=speed)
    shots = []
    for i in range(2):
        clip = store.path(prod['id']) / f'variant_{i}.mp4'
        production._run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                         'testsrc2=size=256x192:rate=24:duration=2', '-f', 'lavfi', '-i',
                         f'sine=frequency={300+i*100}:duration=2:sample_rate=48000',
                         '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', str(clip)])
        shots.append(production.new_shot('Fixed scene', duration_s=2, status='done', clip_path=str(clip)))
    prod['shots'] = shots
    out = store.path(prod['id']) / 'loop.mp4'
    ambient.assemble(prod, out)
    info = production.probe(out)
    assert info['has_audio']
    assert abs(info['duration'] - 9) < .1
    assert (info['width'], info['height']) == (320, 192)
    assert prod['loop_report']['audio_crossfade']
    assert Path(prod['loop_master']).is_file()
    # Il filtro deve conservare la scena intera, anche quando il formato finale cambia.
    assert info['frames'] >= 9 * 24 - 2
    import subprocess
    import numpy as np
    audio = subprocess.run([ff, '-v', 'error', '-i', str(out), '-map', '0:a:0', '-ac', '1',
                            '-ar', '48000', '-f', 'f32le', '-'], capture_output=True, timeout=30, check=True)
    samples = np.frombuffer(audio.stdout, dtype=np.float32)
    cycle_s = float(prod['loop_report']['cycle_s'])
    expected = 2 * int(2 / speed * 24) / 24 - .5
    assert abs(cycle_s - expected) < .1
    assert prod['loop_report']['motion_speed'] == speed
    window = samples[int(.2*48000):int(.8*48000)]
    spectrum = np.abs(np.fft.rfft(window * np.hanning(len(window))))
    peak = np.fft.rfftfreq(len(window), 1/48000)[np.argmax(spectrum)]
    assert abs(peak - 300) < 10
    for multiple in (1, 2):
        boundary = int(cycle_s * multiple * 48000)
        if boundary + 100 < len(samples):
            assert np.max(np.abs(np.diff(samples[boundary-100:boundary+100]))) < .04


def test_partial_loop_is_not_exported(scene):
    store, prod, _ = scene
    prod['shots'] = ambient.plan(prod)
    with pytest.raises(ValueError, match='approvate'):
        ambient.assemble(prod, store.path(prod['id']) / 'partial.mp4')


def test_scene_identity_requires_actual_comparison_and_current_reference(scene, monkeypatch):
    from core.modules.sigma_creative_lab.video import clip_judge
    store, prod, anchor = scene
    clip = store.path(prod['id']) / 'clip.mp4'
    clip.write_bytes(b'clip di prova per il controllo del fingerprint')
    monkeypatch.setattr(clip_judge, 'sample_frames', lambda *a, **k: ([anchor] * 3, 2.0))
    monkeypatch.setattr(clip_judge.judge, '_ensure', lambda *a: None)
    monkeypatch.setattr(clip_judge.judge, '_chat', lambda *a: (
        '{"status":"pass","issues":[],"observations":"Same base, skull relief and framing in all three frames"}'))
    record = ambient.inspect_identity(prod, clip, 'cpu')
    prod['shots'] = [production.new_shot('Same scene', status='done', clip_path=str(clip), scene_identity=record)]
    ambient.require_identity(prod)
    Image.new('RGB', (320, 180), '#905020').save(anchor)
    with pytest.raises(ValueError, match='superato'):
        ambient.require_identity(prod)


def test_ambient_guides_preserve_entire_reference():
    from core.modules.sigma_creative_lab.generators.adapters.comfy_ltx import build_ltx_video
    graph = build_ltx_video({'prompt': 'Blue fire', 'first_frame': 'same.png', 'last_frame': 'same.png',
                             'frame_crop': 'disabled', 'width': 1280, 'height': 704, 'length': 241})
    assert graph['scale_first']['inputs']['crop'] == 'disabled'
    assert graph['scale_last']['inputs']['crop'] == 'disabled'
    assert graph['guide2_first']['inputs']['frame_idx'] == 0
    assert graph['guide2_last']['inputs']['frame_idx'] == -1


def test_b_frames_do_not_exceed_upload_duration(scene):
    import subprocess
    import json
    from core.modules.sigma_creative_lab.video.mp4_timing import cap_duration
    store, prod, _ = scene
    try:
        ff = production.ffmpeg_bin()
    except RuntimeError:
        pytest.skip('ffmpeg non disponibile')
    folder = store.path(prod['id'])
    source, out = folder / 'bframes.mkv', folder / 'limited.mp4'
    production._run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=256x192:rate=24:duration=5',
                     '-f', 'lavfi', '-i', 'sine=frequency=300:sample_rate=48000:duration=5',
                     '-c:v', 'libx264', '-preset', 'fast', '-bf', '2', '-g', '48', '-c:a', 'pcm_s16le', str(source)])
    production._run([ff, '-v', 'error', '-y', '-i', str(source), '-t', '3', '-c:v', 'copy',
                     '-af', 'atrim=end=2.96', '-c:a', 'aac', '-movflags', '+faststart', str(out)])
    def stats():
        result = production._run([production.ffmpeg_bin('ffprobe'), '-v', 'error', '-show_entries',
                                  'stream=codec_type,nb_frames:format=duration', '-of', 'json', str(out)])
        return json.loads(result.stdout)
    before = stats()
    payload_before = subprocess.run([ff, '-v', 'error', '-i', str(out), '-map', '0:v:0', '-c:v', 'copy',
                                     '-f', 'h264', '-'], capture_output=True, check=True, timeout=30).stdout
    report = cap_duration(out, 3)
    after = stats()
    assert float(after['format']['duration']) <= 3
    assert float(after['format']['duration']) >= 2.9
    assert before['streams'][0]['nb_frames'] == after['streams'][0]['nb_frames']
    assert report['size_unchanged']
    payload_after = subprocess.run([ff, '-v', 'error', '-i', str(out), '-map', '0:v:0', '-c:v', 'copy',
                                    '-f', 'h264', '-'], capture_output=True, check=True, timeout=30).stdout
    assert payload_before == payload_after
    # I payload H.264 devono restare identici: si modifica solo il tempo di presentazione.
    subprocess.run([ff, '-v', 'error', '-i', str(out), '-f', 'null', '-'], capture_output=True, check=True, timeout=30)

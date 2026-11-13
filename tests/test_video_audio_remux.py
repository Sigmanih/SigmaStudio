"""Sostituzione audio reale: immagini identiche, chunk a 64 bit e ripristino dell'indice."""
from pathlib import Path
import struct
import subprocess

import numpy as np
import pytest

from core.modules.sigma_creative_lab.video import production
from core.modules.sigma_creative_lab.video.audio_remux import replace_audio_inplace, _convert, _read


@pytest.fixture
def media(tmp_path):
    try:
        ff = production.ffmpeg_bin()
    except RuntimeError:
        pytest.skip('FFmpeg non disponibile')
    video, audio = tmp_path / 'video.mp4', tmp_path / 'nuovo_audio.m4a'
    production._run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=256x192:rate=24:duration=3',
                     '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=3',
                     '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-movie_timescale', '48000',
                     '-movflags', '+faststart', str(video)])
    production._run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                     'sine=frequency=880:sample_rate=48000:duration=3', '-c:a', 'aac',
                     '-movflags', '+faststart', str(audio)])
    return ff, video, audio, tmp_path / 'backup'


def payload(ff, path):
    return subprocess.run([ff, '-v', 'error', '-i', str(path), '-map', '0:v:0', '-c:v', 'copy', '-f', 'h264', '-'],
                          capture_output=True, check=True, timeout=30).stdout


def frequency(ff, path):
    result = subprocess.run([ff, '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'],
                             capture_output=True, check=True, timeout=30)
    data = np.frombuffer(result.stdout, dtype=np.float32)[4800:52800]
    return np.fft.rfftfreq(len(data), 1 / 48000)[np.argmax(np.abs(np.fft.rfft(data * np.hanning(len(data)))))]


def test_replace_audio_preserves_video_and_faststart(media):
    ff, video, audio, backups = media
    before = payload(ff, video)
    old_tops, _ = _read(video)
    report = replace_audio_inplace(video, audio, backups)
    assert payload(ff, video) == before
    assert abs(frequency(ff, video) - 880) < 2
    assert report['video_track_unchanged']
    assert Path(report['backup_moov']).is_file()
    tops, _ = _read(video)
    assert next(x[1] for x in tops if x[0] == b'mdat') == next(x[1] for x in old_tops if x[0] == b'mdat')
    assert next(x[1] for x in tops if x[0] == b'moov') < next(x[1] for x in tops if x[0] == b'mdat')
    assert len([x for x in tops if x[0] == b'mdat']) == 2


def test_backup_restores_previous_sound(media):
    ff, video, audio, backups = media
    report = replace_audio_inplace(video, audio, backups)
    with video.open('r+b') as stream:
        stream.seek(report['moov_offset'])
        stream.write(Path(report['backup_moov']).read_bytes())
        stream.truncate(report['original_size'])
    assert abs(frequency(ff, video) - 440) < 2


def test_chunk_offsets_above_four_gigabytes():
    leaf = struct.pack('>I4sII2I', 24, b'stco', 0, 2, 128, 256)
    result = _convert(leaf, [(100, 300, 2**32 + 1000)], 2, 1000, 48000)
    assert result[4:8] == b'co64'
    assert struct.unpack_from('>2Q', result, 16) == (2**32 + 1028, 2**32 + 1156)


def test_invalid_audio_leaves_video_untouched(media):
    _, video, _, backups = media
    original = video.read_bytes()
    broken = video.parent / 'vuoto.m4a'
    broken.write_bytes(b'audio non valido')
    with pytest.raises((ValueError, struct.error)):
        replace_audio_inplace(video, broken, backups)
    assert video.read_bytes() == original

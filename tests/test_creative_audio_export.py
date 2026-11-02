"""Controlli delle tracce audio localizzate della timeline video."""

import pytest

from core.modules.sigma_creative_lab.video.audio_export import _track_for_language
from core.modules.sigma_creative_lab.video.timeline import (
    TimelineError,
    empty_timeline,
    op_audio_add,
    op_track_add,
)


def test_crea_tracce_vocali_indipendenti_per_lingua():
    timeline = empty_timeline()
    english = op_track_add(timeline, {}, "voice", "Restauro · EN", track_id="restore_voice_shot_01_en")
    italian = op_track_add(timeline, {}, "voice", "Restauro · IT", mute=True,
                           track_id="restore_voice_shot_01_it")

    assert english["track_id"] != italian["track_id"]
    assert _track_for_language(timeline["audio"][-2], "en")
    assert not _track_for_language(timeline["audio"][-2], "it")
    assert _track_for_language(timeline["audio"][-1], "it")


def test_audio_add_rispetta_la_traccia_scelta(tmp_path):
    timeline = empty_timeline()
    track = op_track_add(timeline, {}, "voice", "Restauro · FR", track_id="restore_voice_shot_01_fr")
    source = tmp_path / "voice.wav"
    source.write_bytes(b"placeholder")

    result = op_audio_add(timeline, {}, "voice", str(source), 1.0, src_out=2.0,
                          track_id=track["track_id"], label="Narratore")

    assert timeline["audio"][-1]["clips"][0]["id"] == result["clip"]


def test_audio_add_rifiuta_traccia_di_tipo_diverso(tmp_path):
    timeline = empty_timeline()
    source = tmp_path / "voice.wav"
    source.write_bytes(b"placeholder")
    with pytest.raises(TimelineError):
        op_audio_add(timeline, {}, "voice", str(source), 0.0, src_out=1.0,
                     track_id=timeline["audio"][0]["id"])

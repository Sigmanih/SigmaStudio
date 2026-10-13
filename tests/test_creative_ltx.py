"""LTX-2.5: grafo ComfyUI, lunghezze dei clip, scelta del modello nelle produzioni."""

from core.modules.sigma_creative_lab.generators.adapters.comfy_ltx import (
    build_ltx_video, ltx_frame_count, ltx_size,
)
from core.modules.sigma_creative_lab.video import production as P


def _types(g: dict) -> list[str]:
    return [n["class_type"] for n in g.values()]


def test_lunghezze_ammesse():
    assert ltx_frame_count(5) == 121 and ltx_frame_count(10) == 241
    assert all(ltx_frame_count(s) % 8 == 1 for s in (0.5, 2, 3.3, 7, 15))
    assert ltx_size(864, 480) == (896, 512)                     # meta' risoluzione multipla di 32


def test_testo_a_video_senza_immagini():
    g = build_ltx_video({"prompt": "un faro", "width": 1280, "height": 704, "length": 121, "seed": 3})
    assert "LoadImage" not in _types(g) and "LTXVImgToVideoInplace" not in _types(g)
    assert g["latent"]["inputs"]["width"] == 640 and g["latent"]["inputs"]["height"] == 352
    assert _types(g).count("SamplerCustomAdvanced") == 2          # due passaggi con upscaler latente
    assert g["decode_audio"]["inputs"]["samples"] == ["split2", 1]  # l'audio esce dal secondo passaggio


def test_primo_fotogramma_in_entrambi_i_passaggi():
    g = build_ltx_video({"prompt": "x", "length": 121, "first_frame": "a.png"})
    assert g["i2v1"]["inputs"]["strength"] == 0.7 and g["i2v2"]["inputs"]["strength"] == 1.0
    assert g["av1"]["inputs"]["video_latent"] == ["i2v1", 0]


def test_primo_e_ultimo_fotogramma_come_guide():
    g = build_ltx_video({"prompt": "x", "length": 121, "first_frame": "a.png", "last_frame": "b.png"})
    assert g["guide1_last"]["inputs"]["frame_idx"] == -1 and g["guide1_first"]["inputs"]["frame_idx"] == 0
    assert "i2v1" not in g
    # Le guide vanno tolte prima dell'upscaler e del decode, altrimenti finiscono nel video.
    assert g["upsample"]["inputs"]["samples"] == ["crop1", 2]
    assert g["decode"]["inputs"]["samples"] == ["crop2", 2]


def test_modello_della_produzione():
    h3 = {**P.DEFAULT_SETTINGS}
    ltx = {**P.DEFAULT_SETTINGS, "video_model": "ltx25", "max_clip_seconds": 10}
    assert (P.clip_frames(h3, 5) - 5) % 17 == 0
    assert P.clip_frames(ltx, 5) == 121 and P.clip_frames(ltx, 30) == 241
    assert P.ltx_dims(ltx) == (1280, 704)
    assert P.uses_keyframes(ltx) and not P.uses_keyframes({**h3, "keyframes": False})


def test_id_produzione_con_trattini_e_accenti(tmp_path):
    store = P.ProductionStore(tmp_path)
    for title in ("La ragazza del faro (LTX-2.5)", "La città è viva", "!!!"):
        prod = store.create(title)
        assert store.get(prod["id"])["title"] == title.strip()


def test_audio_dato_resta_fermo():
    # Dialoghi: la battuta della libreria voci non va rigenerata, solo il video si adatta a lei.
    g = build_ltx_video({"prompt": "x", "length": 121, "first_frame": "a.png", "audio": "line.wav", "fps": 24})
    assert g["audio_mask"]["inputs"]["value"] == 0.0
    assert g["av1"]["inputs"]["audio_latent"] == ["audio_latent", 0]
    assert g["audio_latent"]["class_type"] == "SetLatentNoiseMask"
    assert g["trim_audio"]["inputs"]["duration"] == 5.0              # (121 - 1) / 24
    assert "LTXVEmptyLatentAudio" not in _types(g)


def test_camera_richiesta_resta_quella():
    # Caso reale: l'8B trasformava "follows from behind" in "dolly in" nonostante la regola.
    assert P.requested_camera("Mira walks. The camera follows from behind.") == "tracking shot following the subject from behind"
    assert P.requested_camera("camera pulls back to reveal the city") == "dolly out"
    assert P.requested_camera("Wide shot of the harbor") == ""
    fixed = P._with_camera("Mira strides on; the camera dolly in slowly.", "tracking shot following the subject from behind")
    assert fixed.endswith("The camera: tracking shot following the subject from behind.") and "dolly" not in fixed
    same_family = "Mira walks. The camera tracks behind her, keeping pace."
    assert P._with_camera(same_family, "tracking shot following the subject from behind") == same_family


def test_riscrittura_per_ltx_e_numerazione_del_modello():
    prod = {"settings": {"video_model": "ltx25"}, "bible": {},
            "shots": [{"prompt": "Mira walks on the pier. The camera follows from behind.", "status": "pending"},
                      {"prompt": "Close-up of Mira, static camera.", "status": "done"}]}
    # Il modello numera da 1 invece che da 0: con lo stesso numero di risposte vale l'ordine.
    answer = '[{"index": 1, "prompt": "Mira walks steadily along the wet pier, the lamp swinging. The camera tracks behind her."}]'
    assert P.rewrite_for_ltx(prod, lambda m, n: answer) == 1
    assert "tracks behind her" in P.ltx_action(prod["shots"][0])
    assert "tracks behind her" in P.compose_prompt(prod, prod["shots"][0], False)
    prod["shots"][0]["prompt"] = "Mira runs."                       # prompt cambiato: la riscrittura non vale piu'
    assert P.ltx_action(prod["shots"][0]) == ""

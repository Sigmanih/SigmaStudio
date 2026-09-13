"""Il memory mapping non si spegne per precauzione.

Un modello che si caricava in sei secondi ne ha cominciati a impiegare
cinquanta. La causa: `is_usb_or_removable_drive` spegneva `use_mmap` per
qualunque modello su un disco rimovibile, e i modelli di questa macchina stanno
su `D:\\ModelliAI`, che il sistema classifica come bus USB. Senza mmap
llama-server legge l'intero GGUF a ogni avvio invece di mapparlo.

La protezione da `STATUS_IN_PAGE_ERROR` non serviva: il backend **aveva gia'**
il ripiego — prova con mmap, e se il processo muore con un errore di
paginazione riparte con `--no-mmap`. Le due cose sono arrivate con lo stesso
commit, e quella preventiva rendeva l'altra irraggiungibile: con `use_mmap`
gia' falso c'e' un tentativo solo, ed e' quello lento.

Questi test tengono ferme le tre proprieta' che contano: il piano non spegne
mmap da solo, il ripiego esiste ancora, e quando serve viene ricordato.
"""

import inspect

import pytest

from core.engine import gguf_planner
from core.engine.backends import llamaserver_backend as LS


class TestIlPianoNonSpegneMmap:
    def test_nessun_piano_lo_spegne_per_il_tipo_di_disco(self):
        sorgente = inspect.getsource(gguf_planner)
        assert '"use_mmap": False if on_usb else True' not in sorgente, (
            "spegnere mmap in anticipo costa la lettura completa del file a "
            "ogni avvio, anche sui dischi dove funziona"
        )

    def test_il_rilevamento_del_disco_resta(self):
        """Serve ancora: e' l'informazione che spiega una nota all'utente e
        un'eventuale diagnosi. A cambiare e' cosa se ne fa."""
        hardware = {"storage_drives": [
            {"mountpoint": "D:\\", "device": "D:\\", "is_removable": True,
             "speed_class": "usb", "bus_type": "USB"},
            {"mountpoint": "C:\\", "device": "C:\\", "is_removable": False,
             "speed_class": "nvme", "bus_type": "NVMe"},
        ]}
        assert gguf_planner.is_usb_or_removable_drive(
            r"D:\ModelliAI\m.gguf", hardware) is True
        assert gguf_planner.is_usb_or_removable_drive(
            r"C:\modelli\m.gguf", hardware) is False

    def test_senza_dischi_noti_non_si_inventa_niente(self):
        assert gguf_planner.is_usb_or_removable_drive(r"D:\x.gguf", {}) is False
        assert gguf_planner.is_usb_or_removable_drive(None, {}) is False


class TestIlRipiegoEsisteAncora:
    def test_il_backend_prepara_il_secondo_tentativo_senza_mmap(self):
        sorgente = inspect.getsource(LS.LlamaServerBackend.load)
        assert "use_mmap=False" in sorgente
        assert "is_mmap_page_error" in sorgente

    def test_riconosce_l_errore_di_paginazione(self):
        """Sono i tre modi in cui Windows lo dice, e servono tutti e tre: il
        codice d'uscita, il messaggio di prefetch e il nome dell'eccezione."""
        sorgente = inspect.getsource(LS.LlamaServerBackend._attendi_pronto)
        assert "status_in_page_error" in sorgente
        assert "prefetchvirtualmemory failed" in sorgente
        assert "3221225478" in sorgente

    def test_quando_il_ripiego_serve_viene_ricordato(self):
        """Il tentativo fallito costa un avvio intero: pagarlo una volta e'
        accettabile, pagarlo a ogni caricamento no."""
        sorgente = inspect.getsource(LS.LlamaServerBackend.load)
        assert "load_overrides.set_for" in sorgente
        assert '"use_mmap": False' in sorgente

    def test_l_annotazione_non_scatta_se_mmap_era_gia_spento(self):
        """Se l'utente lo aveva gia' disattivato a mano, non c'e' niente da
        imparare e riscriverlo sarebbe rumore."""
        sorgente = inspect.getsource(LS.LlamaServerBackend.load)
        assert 'settings.get("use_mmap") is not False' in sorgente


class TestLaTraduzioneDelPiano:
    def test_use_mmap_falso_diventa_no_mmap(self):
        assert "--no-mmap" in LS.plan_to_args({"use_mmap": False})

    def test_use_mmap_vero_non_aggiunge_niente(self):
        assert "--no-mmap" not in LS.plan_to_args({"use_mmap": True})

    def test_use_mmap_assente_non_aggiunge_niente(self):
        assert "--no-mmap" not in LS.plan_to_args({})


class TestLOverrideManualeVinceComunque:
    def test_l_utente_puo_spegnerlo_a_mano(self, tmp_path, monkeypatch):
        """Il rilevamento automatico non e' l'ultima parola: chi sa che il suo
        disco ha problemi deve poterlo dire, e quella scelta deve reggere."""
        from core.engine import load_overrides

        monkeypatch.setattr(load_overrides.paths, "config_dir", lambda: tmp_path)
        load_overrides.invalidate()
        load_overrides.set_for("modello-x", {"use_mmap": False})

        piano = load_overrides.apply_to({"use_mmap": True, "n_ctx": 8192},
                                        "modello-x")
        assert piano["use_mmap"] is False
        assert "--no-mmap" in LS.plan_to_args(piano)

        intatto = load_overrides.apply_to({"use_mmap": True}, "modello-y")
        assert intatto["use_mmap"] is True
        load_overrides.invalidate()

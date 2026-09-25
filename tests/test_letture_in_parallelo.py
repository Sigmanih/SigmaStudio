# ==============================================================================
# tests/test_letture_in_parallelo.py — Il prefetch delle letture di un turno
# ==============================================================================
"""Quattro letture indipendenti devono costare quanto la piu' lenta.

Il primo test misura davvero il tempo, con un tool finto che dorme: e' l'unico
modo di distinguere «il prefetch e' innestato» da «il prefetch esiste». Gli
altri fissano le regole che rendono sicuro l'innesto — quando si anticipa, cosa
succede se il futuro non e' pronto, e soprattutto che una scrittura in mezzo
spenga tutto.
"""
import threading
import time

from core.harness.prefetch import PrefetchLetture, tutte_anticipabili

#: La funzione che esegue un turno dell'agente. Gli innesti si cercano qui
#: dentro e non in tutto il modulo: e' la stessa distinzione fra «il modulo
#: definisce una cache» e «il turno la usa».
TURNO = "_stream_agent_turn_impl"


class TestQuandoSiAnticipa:
    def test_una_sola_lettura_non_si_anticipa(self):
        assert not tutte_anticipabili(["read_file"])

    def test_due_letture_si(self):
        assert tutte_anticipabili(["read_file", "search_code"])
        assert tutte_anticipabili(["list_dir", "read_file", "find_symbol"])

    def test_una_scrittura_in_mezzo_spegne_tutto(self):
        assert not tutte_anticipabili(["read_file", "edit_file"]), (
            "un turno con una scrittura deve restare serializzato a una azione: "
            "e' la ragione per cui il ciclo serializza"
        )
        assert not tutte_anticipabili(["read_file", "terminal", "read_file"])

    def test_un_turno_fuori_misura_non_si_anticipa(self):
        assert not tutte_anticipabili(["read_file"] * 7), (
            "un turno che chiede quindici file non e' ricognizione"
        )

    def test_un_tool_che_non_esiste_non_si_anticipa(self):
        assert not tutte_anticipabili(["read_file", "tool_inventato"])


class TestIlTempo:
    def test_quattro_letture_lente_costano_una_sola(self, monkeypatch):
        from core.harness import loop as L

        def _lenta(nome, params, workspace_root, **resto):
            time.sleep(0.15)
            return {"success": True, "content": params.get("path", "")}

        monkeypatch.setattr(L, "execute_admin_tool", _lenta)
        batch = [{"tool": "read_file", "params": {"path": f"f{i}.txt"}}
                 for i in range(4)]

        pf = PrefetchLetture()
        assert pf.avvia(batch, "."), "il prefetch non e' partito"
        t0 = time.monotonic()
        for inv in batch:
            scadenza = time.monotonic() + 5
            while time.monotonic() < scadenza:
                if pf.risultato(inv["tool"], inv["params"]) is not None:
                    break
                time.sleep(0.005)
        parallelo = time.monotonic() - t0
        pf.chiudi()

        t1 = time.monotonic()
        for inv in batch:
            L.execute_admin_tool(inv["tool"], inv["params"], ".")
        seriale = time.monotonic() - t1

        assert pf.consumati == 4, pf.stats()
        assert parallelo < seriale * 0.6, (
            f"quattro letture in fila costano {seriale:.3f}s, anticipate "
            f"{parallelo:.3f}s: non sono state sovrapposte"
        )


class TestQuantiInsieme:
    """Quante letture girano davvero nello stesso momento.

    Misurato il 25 settembre 2026 su quattro letture da 150 ms: 600 ms in fila,
    300 ms anticipate con un thread in meno delle chiamate, 150 ms con un thread
    per chiamata. Il tetto si conta quindi sulle chiamate: il thread del ciclo,
    quando un futuro non e' pronto, esegue il tool da solo e non toglie posto a
    nessuno.
    """

    def test_ogni_lettura_ha_il_suo_thread(self, monkeypatch):
        from core.harness import loop as L

        vivi = 0
        picco = 0
        guardia = threading.Lock()

        def _lenta(nome, params, workspace_root, **resto):
            nonlocal vivi, picco
            with guardia:
                vivi += 1
                picco = max(picco, vivi)
            time.sleep(0.1)
            with guardia:
                vivi -= 1
            return {"success": True, "content": params.get("path", "")}

        monkeypatch.setattr(L, "execute_admin_tool", _lenta)
        batch = [{"tool": "read_file", "params": {"path": f"f{i}.txt"}}
                 for i in range(4)]
        pf = PrefetchLetture()
        assert pf.avvia(batch, ".")
        scadenza = time.monotonic() + 5
        while time.monotonic() < scadenza and pf.consumati < len(batch):
            for inv in batch:
                pf.risultato(inv["tool"], inv["params"])
            time.sleep(0.005)
        pf.chiudi()
        assert picco == 4, f"sovrapposte {picco} letture su 4"


class TestViaDiServizio:
    def test_una_chiamata_fuori_dal_batch_non_ha_risultato(self):
        pf = PrefetchLetture()
        assert pf.risultato("read_file", {"path": "mai-anticipato.txt"}) is None

    def test_un_futuro_non_pronto_torna_none_e_non_aspetta(self, monkeypatch):
        from core.harness import loop as L

        def _lentissima(nome, params, workspace_root, **resto):
            time.sleep(0.4)
            return {"success": True}

        monkeypatch.setattr(L, "execute_admin_tool", _lentissima)
        pf = PrefetchLetture()
        pf.avvia([{"tool": "read_file", "params": {"path": "a"}},
                  {"tool": "read_file", "params": {"path": "b"}}], ".")
        t0 = time.monotonic()
        assert pf.risultato("read_file", {"path": "a"}) is None
        atteso = time.monotonic() - t0
        pf.chiudi()
        assert atteso < 0.2, (
            "il prefetch ha aspettato: un prefetch che aspetta e' una "
            "serializzazione con passi in piu'"
        )
        assert pf.fallback >= 1

    def test_un_tool_che_solleva_non_fa_esplodere_il_turno(self, monkeypatch):
        from core.harness import loop as L

        def _rotto(nome, params, workspace_root, **resto):
            raise RuntimeError("disco staccato")

        monkeypatch.setattr(L, "execute_admin_tool", _rotto)
        pf = PrefetchLetture()
        pf.avvia([{"tool": "read_file", "params": {"path": "a"}},
                  {"tool": "read_file", "params": {"path": "b"}}], ".")
        scadenza = time.monotonic() + 3
        while time.monotonic() < scadenza:
            if pf.risultato("read_file", {"path": "a"}) is not None:
                break
            if pf.fallback:
                break
            time.sleep(0.005)
        pf.chiudi()
        assert pf.consumati == 0 and pf.fallback >= 1, pf.stats()


class TestInnestiNelCiclo:
    """I test sopra provano le parti; questo prova che siano collegate.

    Il modo piu' silenzioso di perdere questi due guadagni non e' romperli: e'
    riscrivere `turn_serialization` e dimenticarsene. Le chiamate si cercano
    nell'albero sintattico, non nel testo, cosi' un commento che le nomina non
    fa passare la prova.
    """

    def _chiamate(self, sorgente, modulo):
        import ast
        from pathlib import Path

        percorso = Path(__file__).resolve().parents[1] / "core" / "harness" / sorgente
        albero = ast.parse(percorso.read_text(encoding="utf-8"))
        funzioni = [n for n in ast.walk(albero)
                    if isinstance(n, ast.FunctionDef)
                    and n.name == TURNO]
        assert funzioni, "%s non esiste piu' in %s" % (TURNO, sorgente)
        trovate = set()
        for funzione in funzioni:
            for nodo in ast.walk(funzione):
                if (isinstance(nodo, ast.Attribute)
                        and isinstance(nodo.value, ast.Name)
                        and nodo.value.id == modulo):
                    trovate.add(nodo.attr)
        return trovate

    def test_il_ciclo_usa_la_cache_e_la_invalida_col_percorso(self):
        chiamate = self._chiamate("loop.py", "tool_cache")
        assert {"get", "put", "invalida"} <= chiamate, (
            "il ciclo non usa piu' la cache dei risultati: %s" % sorted(chiamate)
        )

    def test_il_ciclo_anticipa_e_chiude_il_prefetch(self):
        chiamate = self._chiamate("loop.py", "prefetch")
        assert {"avvia", "risultato", "chiudi"} <= chiamate, (
            "il prefetch non e' piu' innestato nel ciclo: %s" % sorted(chiamate)
        )


class TestChiusura:
    def test_chiudere_due_volte_non_solleva(self):
        pf = PrefetchLetture()
        pf.chiudi()
        pf.chiudi()

    def test_un_batch_di_una_sola_chiamata_non_parte(self):
        pf = PrefetchLetture()
        assert not pf.avvia([{"tool": "read_file", "params": {"path": "a"}}], ".")

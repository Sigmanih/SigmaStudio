"""I controlli devono distinguere comportamento corretto e testo ingannevole."""

from pathlib import Path

import pytest

from core.harness.protocol import checks, engine
from core.harness.protocol.scenarios import SCENARI, Scenario


def _workspace(tmp_path, scenario_id, changes):
    scenario = next(s for s in SCENARI if s.id == scenario_id)
    for name, text in {**scenario.file, **changes}.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scenario.controllo(tmp_path)


def test_sconto_accetta_una_formula_equivalente(tmp_path):
    assert not _workspace(tmp_path, "debug_e_fix", {
        "calc.py": "def calcola_sconto(prezzo, sconto_perc):\n    return prezzo * (100 - sconto_perc) / 100\n"})


def test_sconto_rifiuta_la_risposta_memorizzata_del_solo_test_visibile(tmp_path):
    assert _workspace(tmp_path, "debug_e_fix", {
        "calc.py": "def calcola_sconto(prezzo, sconto_perc):\n    return 80.0\n"})


def test_conversione_non_basta_un_nove_nel_commento(tmp_path):
    assert _workspace(tmp_path, "si_ripara_da_solo", {
        "conversione.py": "# 9\ndef celsius_a_fahrenheit(c):\n    return c + 32\n"})


def test_conversione_accetta_una_formula_equivalente(tmp_path):
    assert not _workspace(tmp_path, "si_ripara_da_solo", {
        "conversione.py": "def celsius_a_fahrenheit(c):\n    return 1.8 * c + 32\n"})


def test_email_non_basta_rsplit_nel_commento(tmp_path):
    assert _workspace(tmp_path, "premessa_sbagliata", {
        "helpers/validazione.py": "# rsplit\ndef valida_email(indirizzo):\n    return '@' in indirizzo\n"})


def test_email_accetta_una_soluzione_senza_rsplit(tmp_path):
    assert not _workspace(tmp_path, "premessa_sbagliata", {
        "helpers/validazione.py": "def valida_email(indirizzo):\n    parti = indirizzo.split('@')\n    return len(parti) == 2 and '.' in parti[1]\n"})


@pytest.mark.parametrize("app_ok", [True, False])
def test_refactor_controlla_servizio_e_output_dell_app(tmp_path, app_ok):
    changes = {"service.py": "def formatta_messaggio(mittente, testo):\n    return 'SIGMA- [' + mittente + ']: ' + testo\n"}
    if not app_ok:
        changes["app.py"] = "print('sbagliato')\n"
    assert bool(_workspace(tmp_path, "refactor_due_file", changes)) is not app_ok


def test_modifica_mirata_non_puo_cambiare_le_altre_impostazioni(tmp_path):
    assert _workspace(tmp_path, "modifica_mirata", {
        "config.py": "LINGUA = 'en'\nDEBUG = False\nTIMEOUT = 60\n"})
    assert not _workspace(tmp_path, "modifica_mirata", {
        "config.py": "LINGUA='it'\nDEBUG=False\nTIMEOUT=60\n"})


def test_json_non_puo_aggiungere_chiavi_non_richieste(tmp_path):
    assert _workspace(tmp_path, "file_nuovo", {
        "locales/it.json": '{"titolo": "Ciao", "extra": true}'})


def test_un_exit_zero_non_salva_il_codice_che_salta_le_verifiche(tmp_path):
    assert _workspace(tmp_path, "debug_e_fix", {"calc.py": "raise SystemExit(0)\n"})


ORDERS_PARSER = '''import csv, io
from decimal import Decimal, InvalidOperation

def parse_orders(text):
    reader = csv.DictReader(io.StringIO(text))
    if not {'id', 'quantity', 'price'}.issubset(reader.fieldnames or []):
        raise ValueError('colonne mancanti')
    rows = []
    for row in reader:
        try:
            quantity = int(row['quantity'])
            price = Decimal(row['price'])
        except (ValueError, TypeError, InvalidOperation) as exc:
            raise ValueError('riga non valida') from exc
        if quantity <= 0 or not price.is_finite() or price < 0:
            raise ValueError('valore non valido')
        rows.append({'id': row['id'], 'quantity': quantity, 'price': price})
    return rows
'''

ORDERS_TOTALS = '''from decimal import Decimal, ROUND_HALF_UP

def total_cents(rows):
    return sum(int((row['quantity'] * row['price']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) * 100) for row in rows)
'''


def test_ordini_rifiuta_la_base_difettosa_e_accetta_la_soluzione_completa(tmp_path):
    assert _workspace(tmp_path, "ordini_csv_decimali", {})
    assert not _workspace(tmp_path, "ordini_csv_decimali", {
        "orders/parser.py": ORDERS_PARSER, "orders/totals.py": ORDERS_TOTALS})


def test_ordini_rifiuta_arrotondamenti_sul_totale_invece_che_sulle_righe(tmp_path):
    assert _workspace(tmp_path, "ordini_csv_decimali", {
        "orders/parser.py": ORDERS_PARSER,
        "orders/totals.py": "def total_cents(rows):\n    return int(sum(r['quantity']*r['price'] for r in rows)*100)\n"})


def test_un_verificatore_bloccato_ha_un_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(checks, "CHECK_TIMEOUT_SECONDS", 0.1)
    assert "oltre" in checks.python_behavior("while True: continue")(tmp_path)


def test_un_test_manomesso_su_disco_non_passa_anche_senza_tool_di_scrittura(monkeypatch):
    import core.harness.loop as loop
    scenario = next(s for s in SCENARI if s.id == "debug_e_fix")

    def eventi(**kwargs):
        root = Path(kwargs["workspace_root"])
        (root / "calc.py").write_text("def calcola_sconto(prezzo, sconto_perc):\n    return prezzo*(1-sconto_perc/100)\n", encoding="utf-8")
        (root / "test_calc.py").write_text("assert True\n", encoding="utf-8")
        yield {"type": "token", "text": "fatto"}
        yield {"type": "run_metrics", "turns": 1, "goal_reached": True}

    monkeypatch.setattr(loop, "stream_admin_agent_turn", eventi)
    result = engine.esegui_scenario(scenario, "m")
    try:
        assert result.compito_riuscito is False
        assert any(p.id == "non_riscrive_la_prova" and not p.superata for p in result.prove)
    finally:
        if result.sandbox:
            engine.pulisci(Path(result.sandbox))


def test_i_run_usano_sessioni_distinte_e_temperatura_fissa(monkeypatch):
    import core.harness.loop as loop
    received = []

    def eventi(**kwargs):
        received.append(kwargs)
        yield {"type": "token", "text": "fatto"}
        yield {"type": "run_metrics", "turns": 1, "goal_reached": True}

    monkeypatch.setattr(loop, "stream_admin_agent_turn", eventi)
    scenario = Scenario(id="isolamento", descrizione="", file={}, obiettivo="x", criteri=[])
    for _ in range(2):
        result = engine.esegui_scenario(scenario, "m")
        if result.sandbox:
            engine.pulisci(Path(result.sandbox))
    assert received[0]["session_id"] != received[1]["session_id"]
    assert all(r["temperature"] == 0.0 for r in received)


def test_il_rapporto_identifica_protocollo_budget_e_runtime(monkeypatch):
    from core.harness.protocol.evaluator import EsitoScenario

    scenario = Scenario(id="versione", descrizione="", file={}, obiettivo="x", criteri=[])
    monkeypatch.setattr(engine, "SCENARI", [scenario])
    monkeypatch.setattr(engine, "esegui_scenario", lambda *a: EsitoScenario("versione", "m"))
    monkeypatch.setattr(engine, "_runtime_snapshot", lambda: {"model": "m"})
    result = engine.esegui("m")
    assert result["evaluation_protocol"] == checks.PROTOCOL_VERSION
    assert result["runtime_before"] == result["runtime_after"] == {"model": "m"}
    assert result["temperature"] == 0.0
    scenario.tetto_turni += 1
    assert engine.esegui("m")["evaluation_fingerprint"] != result["evaluation_fingerprint"]

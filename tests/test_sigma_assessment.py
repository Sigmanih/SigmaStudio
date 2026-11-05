"""Codice, tool e checkpoint devono restare distinti nel giudizio su una variante."""

from copy import deepcopy

import pytest

from core.modules.sigma_benchmark_lab.sigma_assessment import (
    associate_runs, compare_bundle, summarize_agent, runtime_signature,
)
from core.modules.sigma_benchmark_lab.sigma_baseline import summarize


def runtime(sha='a'*64):
    return {'model': 'sigma', 'backend': 'native',
            'checkpoint': {'verified': True, 'sha256': sha},
            'settings': {'n_ctx': 8192, 'main_gpu': 0, 'forced_single_gpu': True}}


def scenario(key, passed=True):
    return {'scenario': key, 'compito_riuscito': passed, 'obiettivo_raggiunto': True,
            'turni': 2, 'tetto_turni': 4, 'secondi': 1., 'tetto_secondi': 10.,
            'prove': [{'id': 'risultato_giusto', 'superata': passed},
                      {'id': 'rispetto_sandbox', 'superata': True}]}


def agent_job(sha='a'*64):
    return {'id': 'agent', 'model': 'sigma:sigma', 'status': 'completed',
            'scenarios_planned': ['t1', 't2'],
            'results': {'punteggio': 99., 'evaluation_fingerprint': 'f'*64,
                        'harness_fingerprint': 'd'*64, 'harness_stable': True,
                        'evaluation_implementation_stable': True,
                        'runtime_before': runtime(sha), 'runtime_after': runtime(sha),
                        'scenari': [scenario('t1'), scenario('t2', False)]}}


def bundle(sha='a'*64):
    code = {'job_id': 'code', 'model': 'sigma:sigma', 'comparable': True,
            'checkpoint_sha256': sha, 'dataset_hash': 'dataset', 'settings_hash': 'settings',
            'runtime_signature': runtime_signature(runtime(sha)), 'passed': 1, 'total': 2,
            'cases': [{'id': 'c1', 'passed': True, 'ended': True},
                      {'id': 'c2', 'passed': False, 'ended': True}]}
    return {'id': sha, 'model': 'sigma:sigma', 'coding': code,
            'agent': summarize_agent(agent_job(sha))}


def test_aderenza_alta_non_e_completamento_del_compito():
    result = summarize_agent(agent_job())
    assert result['score'] == 99
    assert result['task_success_pct'] == 50
    assert result['tasks_passed'] == 1 and result['tasks_total'] == 2
    assert result['comparable']


def test_storico_senza_prove_o_identita_non_diventa_una_certificazione():
    job = agent_job()
    for s in job['results']['scenari']:
        del s['compito_riuscito']
    job['results'].pop('runtime_before')
    result = summarize_agent(job)
    assert result['tasks_unverified'] == 2 and result['tasks_total'] == 2
    assert not result['comparable'] and result['checkpoint_sha256'] is None


def test_booleano_di_successo_contraddetto_dai_test_viene_rifiutato():
    job = agent_job()
    job['results']['scenari'][1]['compito_riuscito'] = True
    result = summarize_agent(job)
    assert result['tasks_passed'] == 1 and not result['comparable']


def test_checkpoint_cambiato_durante_la_prova_non_e_associabile():
    job = agent_job()
    job['results']['runtime_after'] = runtime('b'*64)
    result = summarize_agent(job)
    assert result['checkpoint_sha256'] is None and not result['comparable']


def test_stesso_totale_non_nasconde_regressioni_sui_singoli_casi():
    original, candidate = bundle(), bundle('b'*64)
    candidate['coding']['cases'][0]['passed'] = False
    candidate['coding']['cases'][1]['passed'] = True
    result = compare_bundle(original, candidate)
    assert result['status'] == 'regression'
    assert result['domains']['coding']['regressions'] == ['c1']
    assert result['domains']['coding']['wins'] == ['c2']
    assert not result['auto_promote']


def test_nuovo_troncamento_e_regressione_anche_a_codice_corretto():
    original, candidate = bundle(), bundle('b'*64)
    candidate['coding']['cases'][0]['ended'] = False
    assert compare_bundle(original, candidate)['status'] == 'regression'


def test_guadagno_nei_compiti_non_attiva_automaticamente_i_pesi():
    original, candidate = bundle(), bundle('b'*64)
    job = agent_job('b'*64)
    job['results']['scenari'][1] = scenario('t2')
    candidate['agent'] = summarize_agent(job)
    result = compare_bundle(original, candidate)
    assert result['status'] == 'candidate_for_validation'
    assert result['agent_target_observed'] and not result['auto_promote']


@pytest.mark.parametrize('domain,key', [('coding', 'dataset_hash'), ('coding', 'settings_hash'),
                                        ('agent', 'evaluation_fingerprint'), ('agent', 'runtime_signature')])
def test_condizioni_differenti_non_producono_un_confronto(domain, key):
    original, candidate = bundle(), bundle('b'*64)
    candidate[domain][key] = 'changed'
    assert compare_bundle(original, candidate)['status'] == 'insufficient_evidence'


def test_nome_identico_non_associa_pesi_diversi():
    first, second = bundle(), bundle('b'*64)
    report = associate_runs([first['coding']], [second['agent']])
    assert report['bundles'] == []
    second['coding']['checkpoint_sha256'] = first['id']
    assert compare_bundle(first, second)['status'] == 'insufficient_evidence'


def test_associa_codice_e_tool_solo_per_impronta_verificata():
    first = bundle()
    report = associate_runs([first['coding']], [first['agent']])
    assert len(report['bundles']) == 1
    first['coding']['checkpoint_sha256'] = None
    assert associate_runs([first['coding']], [first['agent']])['bundles'] == []


def test_collaudo_integrazione_non_certifica_miglioramento_ne_obiettivo():
    original, candidate = bundle(), bundle('b'*64)
    candidate['coding']['purpose'] = 'integration_smoke'
    candidate['agent']['cases'][1]['passed'] = True
    candidate['agent']['tasks_passed'] = 2
    result = compare_bundle(original, candidate)
    assert result['status'] == 'insufficient_evidence'
    assert result['agent_target_observed'] is False


def test_due_versioni_agente_possono_condividere_i_pesi_senza_perdere_la_provenienza():
    first = bundle()
    job = agent_job()
    job['id'] = 'agent-new'
    job['results']['harness_fingerprint'] = 'e'*64
    job['results']['scenari'][1] = scenario('t2')
    second = summarize_agent(job)
    report = associate_runs([first['coding']], [first['agent'], second])
    assert len(report['bundles']) == 2 and len(report['comparisons']) == 2
    assert all(c['change_axis'] == 'harness' for c in report['comparisons'])
    assert any(c['status'] == 'candidate_for_validation' for c in report['comparisons'])


def test_risultati_coding_includono_casi_e_identita_stabile():
    environment = runtime()
    environment.update(checkpoint_after=environment['checkpoint'], runtime_after=runtime())
    job = {'id': 'code', 'model': 'sigma:sigma', 'status': 'completed',
           'execution_environment': environment, 'thinking_mode': 'no_thinking',
           'reproducibility': {'temperature': 0, 'seed': 42, 'prompt_protocol': 3,
                               'grader': 'v3', 'protocols': {'humaneval': {'mode': 'code_execution'},
                                                           'mbpp': {'mode': 'code_execution'}}}}
    row = {'id': 'x', 'suite': 'humaneval', 'prompt': 'p', 'verification': {'test': 't'},
           'execution': {'status': 'passed'}, 'passed': True, 'answer_protocol': 'generative',
           'tokens': 1, 'latency_ms': 10}
    result = summarize(job, [row])
    assert result['checkpoint_sha256'] == 'a'*64
    assert result['cases'] == [{'id': 'humaneval:x', 'passed': True, 'ended': True}]
    environment['checkpoint_after'] = {'verified': True, 'sha256': 'b'*64}
    assert summarize(job, [row])['checkpoint_sha256'] is None


def test_id_protocollo_assente_non_restituisce_un_altro_benchmark(monkeypatch):
    from core.modules.sigma_benchmark_lab import protocol_runner

    monkeypatch.setattr(protocol_runner, '_jobs', {})
    monkeypatch.setattr(protocol_runner, '_load_history', lambda: [{'id': 'other', 'status': 'completed'}])
    result = protocol_runner.get_protocol_status('missing')
    assert result['status'] == 'not_found' and result['id'] == 'missing'


@pytest.mark.parametrize('model,expected', [('sigma:sigma-candidate-v1', True),
                                         ('sigma:sigma_small', True), ('sigma', False),
                                         ('sigma:sigmarust', False)])
def test_varianti_sigma_non_richiedono_il_nome_della_base(model, expected):
    from core.modules.sigma_benchmark_lab.sigma_baseline import is_target

    assert is_target(model) is expected

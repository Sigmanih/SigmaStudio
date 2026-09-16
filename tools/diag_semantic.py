import importlib.util as u
import math

spec = u.spec_from_file_location('sem', 'core/modules/sigma_developer_lab/mcp_tools/semantic_server.py')
m = u.module_from_spec(spec)
spec.loader.exec_module(m)

s = m.SemanticMCPServer()
docs = s._index['documents']
idf = s._index['idf']

def cos(a, b):
    dot = sum(x * b.get(k, 0) for k, x in a.items())
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    return dot / (na * nb) if na and nb else 0.0

for q in ['gestione errori di rete e retry', 'rotte API', 'autenticazione utente']:
    qt = m._tokenize(q)
    qv = {t: m._compute_tf([t]).get(t, 0) * idf.get(t, 0.0) for t in set(qt)}
    scored = [(cos(qv, d['vector']), d['path']) for d in docs]
    scored.sort(key=lambda x: -x[0])
    print('QUERY:', q)
    for sc, p in scored[:3]:
        print('  ', round(sc, 4), p)
    print()

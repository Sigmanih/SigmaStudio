import pathlib
import sys

root = pathlib.Path('.')
checks = [
    (root / 'projects/sigma_engine_rust/crates/sigma-network/src/ipc_pipe.rs', ['latency_us', 'cancel_request', 'execute_tool']),
    (root / 'projects/sigma_engine_rust/crates/sigma-scheduler/src/lib.rs', ['AtomicBool', 'kv_cache', 'cancel']),
    (root / 'core/engine/backends/sigmarust_backend.py', ['NamedPipeClient', 'cancel_generation', 'win32pipe', 'reconnect', 'timeout']),
    (root / 'projects/sigma_engine_rust/crates/sigma-tools/src/lib.rs', ['fast_read_file', 'fast_code_search', 'buffer_handle']),
]

problems = 0
checked = 0
for path, needles in checks:
    checked += 1
    if not path.exists():
        problems += 1
        print(f'MANCANTE: {path}')
        continue
    text = path.read_text(encoding='utf-8')
    for needle in needles:
        if needle.lower() not in text.lower():
            problems += 1
            print(f'PROBLEMA: {path} non contiene {needle!r}')

print(f'SIGMA-CHECK {{"check": "ipc_cancellation", "checked": {checked}, "problems": {problems}}}')
sys.exit(0 if problems == 0 else 1)

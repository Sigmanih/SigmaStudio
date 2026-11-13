"""Run della chat ordinaria ricollegabili senza ripetere inferenza o azioni."""
import asyncio
import contextvars
import json
import threading

from fastapi.responses import JSONResponse, StreamingResponse

from core.harness.run_events import RunEvents
from core.logger import get_logger
from core.sse import ClientGone

log = get_logger(__name__)
_runs = {}
_lock = threading.RLock()


async def events(run, after=0):
    while True:
        batch = run.read(after)
        for event in batch:
            after = event['event_id']
            yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
        if not batch and run.finished.is_set():
            yield 'data: [DONE]\n\n'
            return
        if not batch:
            yield ': keep-alive\n\n'
            await asyncio.sleep(.25)


def start(adapter, handler_fn, body, slots):
    sid = str(body['session_id'])
    try:
        run = RunEvents(run_id=body.get('run_id'))
    except (ValueError, TypeError, AttributeError):
        return JSONResponse(status_code=400, content={'error': 'Identificativo run non valido'})
    if not slots.acquire(blocking=False):
        run.close()
        return JSONResponse(status_code=503, content={'error': 'Troppi stream attivi'})
    with _lock:
        if len(_runs) >= 32:
            completed = next((key for key, old in _runs.items() if old.finished.is_set()), None)
            if completed is None:
                slots.release()
                run.close()
                return JSONResponse(status_code=429, content={'error': 'Troppi run attivi'})
            _runs.pop(completed)
        previous = _runs.get(sid)
        if previous:
            previous.cancel.set()
        _runs[sid] = run
    adapter.client_gone = run.cancel

    def emit(frame):
        if run.cancel.is_set():
            raise ClientGone('Run fermato dall’utente')
        if frame is None:
            return
        for block in frame.split('\n\n'):
            if block.startswith('data: '):
                payload = block[6:].strip()
                if payload and payload != '[DONE]':
                    run.append(json.loads(payload))

    adapter.emit = emit

    def produce():
        try:
            if previous:
                while not previous.finished.wait(.1):
                    if run.cancel.is_set():
                        return
            if not run.cancel.is_set():
                handler_fn()
                if adapter._response_data is not None:
                    data = dict(adapter._response_data)
                    data.setdefault('token', data.get('response', ''))
                    run.append(data)
        except ClientGone:
            log.info('Run chat fermato: %s', run.run_id)
        except Exception as exc:
            log.exception('Run chat fallito: %s', run.run_id)
            try:
                run.append({'error': str(exc)})
            except RuntimeError:
                log.error('Registro chat esaurito: %s', run.run_id)
        finally:
            run.finished.set()
            slots.release()

    try:
        threading.Thread(target=contextvars.copy_context().run, args=(produce,),
                         name='sigma-chat-run', daemon=True).start()
    except RuntimeError:
        run.finished.set()
        slots.release()
        return JSONResponse(status_code=503, content={'error': 'Impossibile avviare la chat'})
    return StreamingResponse(events(run), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Sigma-Run-ID': run.run_id})


async def control(request, method):
    body = await request.json() if method == 'POST' else request.query_params
    sid = str(body.get('session_id') or '')
    with _lock:
        run = _runs.get(sid)
    endpoint = request.url.path.rsplit('/', 1)[-1]
    if endpoint == 'run' and method == 'GET':
        return JSONResponse(content={'success': True, 'run_id': run.run_id if run else None,
                                     'running': bool(run and not run.finished.is_set())})
    if run is None or body.get('run_id') != run.run_id:
        return JSONResponse(status_code=404, content={'error': 'Run non disponibile: server riavviato o registro scaduto'})
    if endpoint == 'stop' and method == 'POST':
        run.cancel.set()
        return JSONResponse(content={'success': True, 'stopped': not run.finished.is_set()})
    if endpoint == 'events' and method == 'GET':
        try:
            after = int(body.get('after') or 0)
            run.read(after, limit=0)
        except ValueError:
            return JSONResponse(status_code=400, content={'error': 'Cursore non valido'})
        return StreamingResponse(events(run, after), media_type='text/event-stream')
    return JSONResponse(status_code=405, content={'error': 'Metodo non valido'})

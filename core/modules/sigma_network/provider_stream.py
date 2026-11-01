"""Adattatore del cluster verso il contratto di streaming dei provider."""
import json

from core.engine.cancellation import is_cancelled


def stream_cluster(*, messages, model, max_tokens=2048, cancel=None):
    from .handlers import _get_broker
    prompt = messages if isinstance(messages, str) else "\n".join(
        f"{message.get('role', 'user')}: {message.get('content', '')}"
        for message in messages if isinstance(message, dict))
    try:
        for raw in _get_broker().execute_cluster_inference(prompt=prompt, model=model, max_tokens=max_tokens or 2048):
            if is_cancelled(cancel):
                return
            if not raw or not raw.startswith("data: "):
                continue
            body = raw[6:].strip()
            if body == "[DONE]":
                yield {"done": True}
                return
            try:
                parsed = json.loads(body)
            except ValueError:
                continue
            if "token" in parsed:
                yield {"token": parsed["token"]}
            elif "error" in parsed:
                yield {"error": True, "message": str(parsed["error"])}
                return
            elif parsed.get("type") == "start":
                yield {"status": True, "model_status": f"Cluster connesso a {parsed.get('provider_name', '')}"}
            elif parsed.get("type") == "finish":
                yield {"status": True, "model_status": f"Cluster: {parsed.get('tokens_generated', 0)} token", "done": True}
    except Exception as exc:
        yield {"error": True, "message": f"Errore del provider cluster: {exc}"}

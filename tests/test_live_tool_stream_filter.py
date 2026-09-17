import pytest
from core.chat.chat_runner import _LiveToolStreamFilter


def test_filter_removes_sigma_tool_block_in_stream():
    emitted = []
    detected = []
    f = _LiveToolStreamFilter(
        on_emit_token=lambda t: emitted.append(t),
        on_tool_detected=lambda: detected.append(True)
    )

    tokens = [
        "Certamente, ",
        "consulto il progetto:\n",
        "```sigma-tool\n",
        '{"tool": "consulta_progetto", "arguments": {}}\n',
        "```\n",
        "Ecco cosa ho trovato nel README."
    ]

    for tok in tokens:
        f.feed(tok)
    f.flush()

    out = "".join(emitted)
    assert "sigma-tool" not in out
    assert "consulta_progetto" not in out
    assert "Certamente, consulto il progetto:\n" in out
    assert "Ecco cosa ho trovato nel README." in out
    assert len(detected) == 1


def test_filter_removes_double_backtick_sigma_tool():
    emitted = []
    f = _LiveToolStreamFilter(on_emit_token=lambda t: emitted.append(t))

    tokens = [
        "``sigma-tool\n",
        '{"tool": "consulta_progetto", "arguments": {"doc": "README.md"}}\n',
        "``\n",
        "Contenuto del documento."
    ]

    for tok in tokens:
        f.feed(tok)
    f.flush()

    out = "".join(emitted)
    assert "sigma-tool" not in out
    assert "consulta_progetto" not in out
    assert "Contenuto del documento." in out


def test_filter_preserves_regular_text_with_code_block():
    emitted = []
    f = _LiveToolStreamFilter(on_emit_token=lambda t: emitted.append(t))

    tokens = [
        "Ecco il codice Python:\n",
        "```python\n",
        "print('Hello')\n",
        "```\n",
        "Finito."
    ]

    for tok in tokens:
        f.feed(tok)
    f.flush()

    out = "".join(emitted)
    assert "```python\nprint('Hello')\n```\nFinito." in out


if __name__ == "__main__":
    import json
    test_filter_removes_sigma_tool_block_in_stream()
    test_filter_removes_double_backtick_sigma_tool()
    test_filter_preserves_regular_text_with_code_block()
    print('SIGMA-CHECK ' + json.dumps({"check": "live_tool_streaming_cleanup", "checked": 3, "problems": 0}))


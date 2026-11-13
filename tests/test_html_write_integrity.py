"""Un prefisso di HTML non deve essere scambiato per una pagina completa."""
import json

from core.harness.diagnostics import validate_code_syntax
from core.harness.loop import execute_admin_tool, extract_tool_invocations, normalize_tool_params
from core.harness.tool_schema import tool_calls_to_invocations


HEAD = '<!DOCTYPE html>\n<html lang="it">\n<head>\n<meta charset="UTF-8">\n<style>body{color:#333}</style>\n</head>\n'
BODY = '<body><main><h1>Sigma Caffè</h1></main></body>\n</html>\n'


def test_unfinished_json_cannot_overwrite_existing_file(tmp_path):
    target = tmp_path / 'index.html'
    target.write_text(HEAD + BODY, encoding='utf-8')
    raw = '{"path":"index.html","content":"<!DOCTYPE html>\\n<html lang=\\"it\\">\\n<head>\\n<meta charset'
    params = normalize_tool_params(raw, 'write_file')
    assert params.get('__malformed__')
    assert 'content' not in params
    native = tool_calls_to_invocations([{'function': {'name': 'write_file', 'arguments': raw}}])
    assert native[0]['params'].get('__malformed__')
    assert target.read_text(encoding='utf-8') == HEAD + BODY


def test_truncated_tag_refused_even_with_allow_truncate(tmp_path):
    target = tmp_path / 'index.html'
    target.write_text(HEAD + BODY, encoding='utf-8')
    result = execute_admin_tool('write_file', {'path': 'index.html', 'content': '<!DOCTYPE html>\n<meta charset',
                                              'allow_truncate': True}, str(tmp_path))
    assert not result['success']
    assert target.read_text(encoding='utf-8') == HEAD + BODY


def test_head_is_saved_but_reported_incomplete_then_append_finishes(tmp_path):
    result = execute_admin_tool('write_file', {'path': 'index.html', 'content': HEAD}, str(tmp_path))
    assert result['success']
    assert result['syntax_valid'] is False
    assert result['line_count'] == len(HEAD.splitlines())
    assert 'append_file' in result['syntax_error']
    result = execute_admin_tool('append_file', {'path': 'index.html', 'content': BODY}, str(tmp_path))
    assert result['success'] and result['syntax_valid']
    assert (tmp_path / 'index.html').read_text(encoding='utf-8') == HEAD + BODY


def test_repeated_write_does_not_claim_progress(tmp_path):
    target = tmp_path / 'index.html'
    target.write_text(HEAD, encoding='utf-8')
    result = execute_admin_tool('write_file', {'path': 'index.html', 'content': HEAD,
                                              'allow_truncate': True}, str(tmp_path))
    assert result['unchanged'] and not result['success']
    assert 'append_file' in result['error']


def test_raw_body_preserves_all_html_quotes_and_styles(tmp_path):
    text = '```tool:write_file\n' + json.dumps({'path': 'index.html'}) + '\n---\n' + HEAD + BODY + '```'
    invocation = extract_tool_invocations(text)[0]
    assert invocation['params']['content'] == HEAD + BODY
    result = execute_admin_tool(invocation['tool'], invocation['params'], str(tmp_path))
    assert result['success'] and result['syntax_valid']
    assert (tmp_path / 'index.html').read_text(encoding='utf-8') == HEAD + BODY


def test_html_fragment_and_complete_document_have_different_evidence():
    fragment = validate_code_syntax('part.html', '<section><h2>Caffè</h2></section>')
    assert fragment['valid'] and not fragment['document_complete']
    complete = validate_code_syntax('index.html', HEAD + BODY)
    assert complete['valid'] and complete['document_complete']

# ==============================================================================
# core/engine/grammars.py — Constraining the decode instead of repairing the text
#
# Two large modules in this codebase exist to recover structure from free text:
# response_parser pulls JSON and file blocks out of prose, file_extractor pulls
# paths and contents out of fenced blocks, and agent_loop reports a parse error
# back to the model and hopes the retry is better formed.
#
# A grammar makes the malformed output unreachable. llama.cpp masks the logits
# at every step against a GBNF grammar, so a tool call that does not match the
# schema is not merely rejected -- it cannot be sampled. It is also faster than
# unconstrained decoding on the same output, because most of the vocabulary is
# pruned before the softmax.
#
# What is deliberately NOT done here: constraining a whole chat answer. Prose is
# the point of a chat, and a grammar over it would be a straitjacket. Grammars
# belong where the output genuinely has a shape -- a tool call, a plan object,
# a repair pass on a block the model already got wrong.
# ==============================================================================
from typing import Any, Dict, Iterable, List, Optional

from core.logger import get_logger

log = get_logger(__name__)


# The JSON primitives every generated grammar shares. Written once, verbatim
# from the GBNF that ships with llama.cpp, so behaviour matches what the
# runtime's own examples produce.
_JSON_PRIMITIVES = r"""
ws        ::= [ \t\n]*
string    ::= "\"" char* "\"" ws
char      ::= [^"\\\x7F\x00-\x1F] | "\\" (["\\bfnrt/] | "u" [0-9a-fA-F]{4})
number    ::= ("-"? ([0-9] | [1-9][0-9]{0,15})) ("." [0-9]+)? ([eE] [-+]? [0-9]{1,3})? ws
boolean   ::= ("true" | "false") ws
null      ::= "null" ws
value     ::= object | array | string | number | boolean | null
object    ::= "{" ws (string ":" ws value ("," ws string ":" ws value)*)? "}" ws
array     ::= "[" ws (value ("," ws value)*)? "]" ws
"""


def _gbnf_string(text: str) -> str:
    """
    A GBNF terminal that emits `text` *as a quoted JSON string*.

    The distinction is easy to get wrong and silent when you do: in GBNF a
    double-quoted sequence delimits a terminal, so `"search_web"` makes the
    model emit `search_web` with no quotes at all -- valid against the grammar,
    invalid as JSON. The quotes have to be escaped into the terminal itself.
    llama.cpp does not reject the mistake, it faithfully generates the broken
    output, so this is checked by a round-trip test rather than by reading.
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"\\"{escaped}\\""'


def tool_call_grammar(tool_names: Iterable[str]) -> Optional[str]:
    """
    A grammar admitting exactly one well-formed ``sigma-tool`` payload.

    The tool name is constrained to the alternation of what the hub actually
    exposes, which removes the most common local-model failure by construction:
    inventing a plausible tool that does not exist, or calling the category
    heading as though it were callable. Arguments stay a free JSON object,
    because their shape differs per tool and over-constraining them would turn
    a wrong argument into no answer at all.
    """
    names = [n for n in dict.fromkeys(tool_names) if n]
    if not names:
        return None

    alternation = " | ".join(_gbnf_string(name) for name in names)
    return (
        'root      ::= "{" ws "\\"tool\\"" ws ":" ws toolname ws "," ws '
        '"\\"arguments\\"" ws ":" ws object "}" ws\n'
        f"toolname  ::= ({alternation}) ws\n"
        + _JSON_PRIMITIVES
    )


def choice_grammar(letters: Iterable[str]) -> Optional[str]:
    """
    A grammar admitting exactly one option label and nothing else.

    This is the multiple-choice counterpart of constraining a tool call. The
    benchmark asks the model to pick one of N labels; unconstrained, it answers
    with a page of reasoning that a regex then has to mine for a letter, and
    every answer containing two letters becomes a verdict nobody can defend.
    Masked against this grammar the model emits one label, always parseable and
    always single -- and it emits it in one token instead of a thousand.

    Note what is being measured either way: which option the model ranks first.
    The grammar does not help it choose, it only removes the prose in which the
    choice used to get lost.
    """
    valid = [str(letter).strip() for letter in letters if str(letter).strip()]
    if not valid:
        return None
    # Bare terminals, not JSON strings: the answer here is the letter itself,
    # so quoting it the way _gbnf_string does would make the model emit `"A"`.
    alternatives = " | ".join('"%s"' % v.replace('\\', '\\\\').replace('"', '\\"')
                              for v in valid)
    return "root ::= " + alternatives + "\n"


def json_object_grammar(schema: Optional[Dict[str, Any]] = None) -> str:
    """
    A grammar for one JSON object, optionally with required keys in order.

    Only the top level of the schema is honoured -- required keys, and whether
    each is a string, number, boolean, array or object. Nested schemas fall
    back to free JSON. That is the honest limit of a converter this size, and
    a grammar that silently ignored half a schema would be worse than one that
    says which half it reads.
    """
    if not schema:
        return "root ::= object\n" + _JSON_PRIMITIVES

    properties = schema.get("properties") or {}
    required = [key for key in (schema.get("required") or []) if key in properties]
    if not required:
        return "root ::= object\n" + _JSON_PRIMITIVES

    parts: List[str] = []
    for index, key in enumerate(required):
        separator = '"," ws ' if index else ""
        rule = _rule_for_type((properties[key] or {}).get("type"))
        parts.append(f'{separator}{_gbnf_string(key)} ws ":" ws {rule} ws')

    body = " ".join(parts)
    return f'root ::= "{{" ws {body} "}}" ws\n' + _JSON_PRIMITIVES


def _rule_for_type(json_type: Any) -> str:
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
    }.get(json_type, "value")


def compile_for_llama_cpp(gbnf: str):
    """
    A ``LlamaGrammar`` for this GBNF, or None where it cannot be built.

    None is a valid answer everywhere it is used: a host without llama.cpp, a
    wheel too old to expose grammars, or a grammar the parser rejects. The
    caller then decodes unconstrained and the existing parsers catch what they
    always caught -- a lost optimisation, never a lost answer.
    """
    if not gbnf:
        return None
    try:
        from llama_cpp import LlamaGrammar
    except Exception as exc:
        log.debug("[Grammar] llama.cpp grammars unavailable: %s", exc)
        return None
    try:
        return LlamaGrammar.from_string(gbnf, verbose=False)
    except Exception as exc:
        # A malformed grammar is a bug here, not in the model: log it loudly
        # enough to be fixed, and let the request proceed without it.
        log.warning("[Grammar] Rejected by llama.cpp (%s); decoding unconstrained.", exc)
        return None


def grammar_for_available_tools() -> Optional[str]:
    """The tool-call grammar for whatever the MCP hub currently exposes."""
    try:
        from core.mcp import mcp_hub
        names = [t["name"] for t in (mcp_hub.get_agent_tools() or []) if t.get("name")]
    except Exception as exc:
        log.debug("[Grammar] Tool catalogue unavailable: %s", exc)
        return None
    return tool_call_grammar(names)

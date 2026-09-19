import sys
from pathlib import Path

p = Path('sigma_studio/src/modules/sigma_developer_lab/AdminAgentChat.jsx')
src = p.read_text(encoding='utf-8')
lines = src.splitlines()

openers = {'(': ')', '[': ']', '{': '}'}
closers = {v: k for k, v in openers.items()}
stack = []
in_string = None
in_l
[...]

        if c == '`':
            in_template = True
            j += 1
            continue
        if c in openers:
            stack.append((c, i))
        elif c in closers:
            if not stack or stack[-1][0] != closers[c]:
                errors.append(f'riga {i}: carattere di chiusura {c!r} senza apertura corrispondente (stack top: {stack[-1] if stack else None})')
                break
            stack.pop()
        j += 1
    in_line_comment = False

if stack:
    errors.append(f'parentesi non chiuse: {stack[-5:]}')

if errors:
    print('ERRORI:')
    for e in errors[:20]:
        print(' ', e)
    sys.exit(1)
else:
    print('OK: parentesi bilanciate su', len(lines), 'righe')
    sys.exit(0)

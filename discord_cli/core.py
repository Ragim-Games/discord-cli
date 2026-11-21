"""Pure input handling and local configuration; no network access."""
import json
import os
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"


def safe_text(value):
    # Never allow remote names/messages to execute terminal control sequences.
    return ''.join(c for c in str(value) if c in '\n\t' or (ord(c) >= 32 and not 127 <= ord(c) <= 159))


def parse(line):
    if line.startswith('//'):
        return 'send', line[1:]
    match = re.fullmatch(r'\s*(server|channel)\s*:\s*(.+?)\s*', line, re.I)
    if match:
        return match[1].lower(), match[2]
    command = line.strip().lower()
    if command in {'servers', 'channels', 'dm', 'help', 'back', 'leave', 'mute', 'unmute', 'quit', 'devices'}:
        return command, ''
    if command.startswith('/send '):
        return 'send', line[line.lower().index('/send ') + 6:]
    if command.startswith('dm:'):
        return 'dm_id', line.split(':', 1)[1].strip()
    return 'send', line


def resolve(items, query):
    matches = [x for x in items if str(x.id) == query]
    if not matches:
        matches = [x for x in items if str(getattr(x, 'name', '')).casefold() == query.casefold()]
    if not matches:
        raise ValueError('No matching ID or name. Open the list to choose an available item.')
    if len(matches) > 1:
        raise ValueError('That name is ambiguous. Use its ID or select it from the list.')
    return matches[0]


def load_token(path=CONFIG):
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        token = value.get('token') if isinstance(value, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise ValueError
        return token.strip()
    except (ValueError, OSError):
        raise ValueError('Cannot read config.json. Fix it or run start.cmd --reset-token.') from None


def save_token(token, path=CONFIG):
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump({'token': token}, output, indent=2)
            output.write('\n')
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

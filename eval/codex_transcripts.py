"""Conservative local Codex rollout reader. Never evaluates recorded tool code.

Only owner-tagged completed CommandExecution items are evidence. Model-facing
response items, compacted histories, user text and subagent sessions are excluded.
This is command attribution, not a complete transcript or outcome grader.
"""
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import shlex


def timestamp(value):
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)) and math.isfinite(value):
            return datetime.fromtimestamp(value / 1000, timezone.utc)
        if isinstance(value, str):
            result = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError, OSError):
        pass
    return None


def cortex_command(argv):
    """Recognise one literal Cortex invocation, not mentions inside shell/code.

    Compound scripts, substitutions, redirects, shell functions and wrappers are
    deliberately unsupported. Treat their contents as unknown, never execute them.
    """
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        return None
    if Path(argv[0]).name in ('bash', 'zsh', 'sh'):
        if len(argv) != 3 or argv[1] not in ('-c', '-lc'):
            return None
        script = argv[2].strip()
        # Reject expansion/comment markers even inside quotes. Deliberate
        # undercoverage is safer than pretending shlex is a shell interpreter.
        if any(x in script for x in ('$', '`', '\n', '#', '*', '?', '[', ']', '{', '}')):
            return None
        try:
            lexer = shlex.shlex(script, posix=True, punctuation_chars=';&|()<>')
            lexer.whitespace_split = True
            argv = list(lexer)
        except ValueError:
            return None
        if any(x and all(char in ';&|()<>' for char in x) for x in argv):
            return None
    if not argv:
        return None
    if Path(argv[0]).name in ('python', 'python3'):
        argv = argv[1:]
    if len(argv) < 2 or Path(argv[0]).name != 'cortex':
        return None
    if argv[1] not in ('log', 'log-line', 'hint', 'outcome', 'reroute'):
        return None
    if any(arg == '-h' or (arg.startswith('--') and len(arg) > 2
                           and '--help'.startswith(arg)) for arg in argv[2:]):
        return None
    # Canonical rendering keeps quoted task strings literal for downstream shlex.
    return shlex.join(['cortex', *argv[1:]])


def command_task(command, verb):
    """Read only the actual command's task argument, never nested quoted prose."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if len(argv) < 3 or argv[:2] != ['cortex', verb]:
        return None
    if verb == 'hint':
        return argv[2] if not argv[2].startswith('-') else None
    if verb == 'log-line':
        return argv[3] if len(argv) >= 4 and not any(x.startswith('-') for x in argv[2:4]) else None
    if verb == 'log':
        tasks = []
        for index, arg in enumerate(argv[2:], 2):
            option = arg.split('=', 1)[0]
            if option.startswith('--') and '--task'.startswith(option) and option != '--task':
                return None  # Do not confuse an abbreviated override with a value.
            if arg == '--task' and index + 1 < len(argv):
                tasks.append(argv[index + 1])
            if arg.startswith('--task='):
                tasks.append(arg[len('--task='):])
        return tasks[0] if len(tasks) == 1 else None
    return None


def load_codex_sessions(root, event_factory):
    """Return namespaced sessions and explicit exclusion counts.

    IDs conflicting across copies are discarded rather than resolved by file order.
    Ownership is checked per event, including after a fork. Creation time is a
    second boundary against pre-fork history copied under a child's identity.
    """
    counts = Counter()
    sessions, identities, excluded_sessions = {}, {}, set()
    root = Path(root)
    if not root.is_dir():
        return {}, {'status': 'missing', 'files': 0}
    for path in sorted(root.rglob('*.jsonl')):
        counts['files'] += 1
        rows = []
        try:
            with path.open() as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                    except (ValueError, UnicodeError):
                        counts['malformed_lines'] += 1
                        continue
                    if isinstance(row, dict) and (row.get('type') == 'session_meta'
                            or (row.get('type') == 'event_msg'
                                and isinstance(row.get('payload'), dict)
                                and row['payload'].get('type') == 'item_completed'
                                and isinstance(row['payload'].get('item'), dict))):
                        if row.get('type') == 'event_msg' and row['payload']['item'].get('type') != 'CommandExecution':
                            # Retain only the identity/type needed to detect an
                            # item-ID collision, not private message contents.
                            row['payload']['item'] = {k: row['payload']['item'].get(k) for k in ('type', 'id')}
                        rows.append(row)
        except (OSError, UnicodeError):
            counts['unreadable_files'] += 1
            continue
        metas = [r.get('payload') for r in rows if r.get('type') == 'session_meta']
        if len(metas) != 1 or not isinstance(metas[0], dict):
            counts['unsupported_metadata_files'] += 1
            continue
        meta = metas[0]
        sid, created = meta.get('id'), timestamp(meta.get('timestamp'))
        if not isinstance(sid, str) or not sid or created is None:
            counts['unsupported_metadata_files'] += 1
            continue
        identity = (created, meta.get('source'), meta.get('parent_thread_id'), meta.get('forked_from_id'))
        if sid in identities and identities[sid] != identity:
            excluded_sessions.add(sid)
            counts['conflicting_session_metadata'] += 1
        identities[sid] = identity
        if (meta.get('source') not in ('vscode', 'cli', 'exec')
                or meta.get('parent_thread_id') or meta.get('forked_from_id')):
            excluded_sessions.add(sid)
            counts['fork_subagent_or_unknown_source_files'] += 1
            continue
        key = 'codex:' + sid
        bucket = sessions.setdefault(key, {'host': 'codex', 'session_ref': sid,
            'evidence_scope': 'commands-only', 'events': [], 'files': [],
            '_items': {}, '_raw': {}, '_conflicts': set()})
        bucket['files'].append(path)
        for row in rows:
            q = row.get('payload')
            if row.get('type') != 'event_msg' or not isinstance(q, dict) or q.get('type') != 'item_completed':
                continue
            item = q.get('item')
            if not isinstance(item, dict):
                continue
            if q.get('thread_id') != sid:
                counts['foreign_owner_items'] += 1
                continue
            start, end = timestamp(q.get('started_at_ms')), timestamp(q.get('completed_at_ms'))
            iid, turn = item.get('id'), q.get('turn_id')
            if all(isinstance(x, str) and x for x in (iid, turn)):
                identity = (turn, iid)
                signature = json.dumps([item.get('type'), q.get('started_at_ms'), q.get('completed_at_ms'),
                    item.get('command'), item.get('cwd'), item.get('status'), item.get('exit_code')], sort_keys=True)
                if identity in bucket['_raw']:
                    counts['duplicate_items'] += 1
                    if bucket['_raw'][identity] != signature:
                        bucket['_conflicts'].add(identity)
                    continue
                bucket['_raw'][identity] = signature
            if item.get('type') != 'CommandExecution':
                continue
            if not all(isinstance(x, str) and x for x in (iid, turn)) or start is None or end is None or start < created or end < start:
                counts['unowned_or_precreation_commands'] += 1
                continue
            if item.get('status') != 'completed' or type(item.get('exit_code')) is not int or item['exit_code'] != 0:
                counts['unsuccessful_commands'] += 1
                continue
            cmd = cortex_command(item.get('command'))
            if cmd is None:
                counts['unparsed_commands'] += 1
                continue
            identity = (turn, iid)
            signature = (start, end, cmd, item.get('cwd'))
            bucket['_items'][identity] = signature

    for key in list(sessions):
        bucket = sessions[key]
        if bucket['session_ref'] in excluded_sessions:
            del sessions[key]
            continue
        for identity, (start, end, cmd, cwd) in bucket.pop('_items').items():
            if identity in bucket['_conflicts']:
                counts['conflicting_commands'] += 1
                continue
            # Completed time prevents hints still running at route declaration
            # from being treated as already available evidence.
            bucket['events'].append(event_factory(end, 'tool_use', key,
                ':'.join(identity), cwd, tool='Bash', cmd=cmd, started_at=start))
            counts['accepted_commands'] += 1
        del bucket['_conflicts']
        del bucket['_raw']
        bucket['events'].sort(key=lambda event: event.ts)
    return sessions, {'status': 'scanned', **dict(counts)}

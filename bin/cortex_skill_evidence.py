"""Opt-in, self-reported skill evidence. Never infer application from exposure."""
import hashlib
import json
import fcntl
import os
import stat
from pathlib import Path


def record(cli, args):
    matches = [row for row in cli.read_log() if row.get('_id') == args.ref]
    if len(matches) != 1:
        raise ValueError('--ref must identify exactly one route by its canonical ID')
    route = matches[0]
    identity = cli.agent_identity()
    if (identity.get('host') in (None, 'unknown')
            or route.get('host') != identity.get('host')
            or route.get('session_ref') != identity.get('session_ref')
            or not identity.get('session_ref')
            or route.get('project_ref') != cli.project_ref()):
        raise ValueError('skill evidence must belong to the current host, session and project')
    skill = Path(args.skill).expanduser().resolve(strict=True)
    if skill.name != 'SKILL.md' or not skill.is_file():
        raise ValueError('--skill must point to a SKILL.md file')
    if skill.stat().st_size > 1024 * 1024:
        raise ValueError('skill file exceeds the 1 MiB evidence limit')
    with skill.open('rb') as stream:
        content = stream.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise ValueError('skill file exceeds the 1 MiB evidence limit')
    evidence = {
        'schema_version': 1,
        'event': 'skill_evidence',
        'event_id': cli.new_event_id('skill'),
        'ts': cli.now_iso(),
        'ref': route['_id'],
        **identity,
        'skill_path': str(skill),
        'skill_sha256': hashlib.sha256(content).hexdigest(),
        'stage': args.stage,
        'provenance': 'self_reported',
    }
    # Separate stream preserves all existing route/correction consumers.
    destination = cli.CLAUDE_DIR / 'cortex-skill-evidence.jsonl'
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_APPEND | os.O_CREAT
                         | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, 'a', encoding='utf-8') as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError('evidence destination must be a singly linked regular file')
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(evidence) + '\n')
    print(f"recorded self-reported skill {args.stage} for {route['_id']}")
    return 0

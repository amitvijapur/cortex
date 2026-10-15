"""Synthetic, isolated tests for opt-in skill evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'bin' / 'cortex'


class SkillEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cortex-skill-evidence-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.env = dict(os.environ, CORTEX_HOME=str(self.state),
                        CORTEX_HOST='codex', CORTEX_SESSION_ID='fixture',
                        PYTHONDONTWRITEBYTECODE='1')
        self.skill = self.root / 'SKILL.md'
        self.skill.write_text('---\nname: fixture\ndescription: synthetic\n---\nPrivate body\n')
        self.run_cli('log-line', 'Direct > fixture @ L2', 'synthetic', '--class', 'build')
        self.log = self.state / 'cortex-log.jsonl'
        self.route = json.loads(self.log.read_text().splitlines()[-1])
        self.before = self.log.read_bytes()

    def run_cli(self, *args, ok=True, env=None):
        result = subprocess.run([sys.executable, '-B', str(CLI), *args],
                                cwd=self.root, env=env or self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def record(self, stage='read', **kwargs):
        return self.run_cli('skill-use', '--ref', self.route['event_id'],
                            '--skill', str(self.skill), '--stage', stage, **kwargs)

    def test_opt_in_stages_hash_and_privacy(self):
        path = self.state / 'cortex-skill-evidence.jsonl'
        self.assertFalse(path.exists())
        for stage in ('read', 'invoked', 'applied'):
            self.record(stage)
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual([r['stage'] for r in rows], ['read', 'invoked', 'applied'])
        for row in rows:
            self.assertEqual(row['ref'], self.route['event_id'])
            self.assertEqual(row['provenance'], 'self_reported')
            self.assertEqual(row['skill_path'], str(self.skill.resolve()))
            self.assertEqual(row['skill_sha256'], hashlib.sha256(self.skill.read_bytes()).hexdigest())
            self.assertNotIn('Private body', json.dumps(row))
            self.assertNotIn('task', row)
        self.assertEqual(self.log.read_bytes(), self.before)

    def test_unknown_ref_is_rejected_without_stream(self):
        self.route['event_id'] = 'absent'
        self.record(ok=False)
        self.assertFalse((self.state / 'cortex-skill-evidence.jsonl').exists())

    def test_foreign_host_and_session_are_rejected(self):
        for updates in ({'CORTEX_SESSION_ID': 'foreign'}, {'CORTEX_HOST': 'claude'}):
            self.record(ok=False, env=dict(self.env, **updates))
        self.assertFalse((self.state / 'cortex-skill-evidence.jsonl').exists())

    def test_non_skill_file_and_invalid_stage_rejected(self):
        self.skill = self.root / 'other.txt'
        self.skill.write_text('not a skill')
        self.record(ok=False)
        self.skill = self.root / 'SKILL.md'
        self.record('successful', ok=False)
        self.assertEqual(self.log.read_bytes(), self.before)

    def test_symlink_stream_is_not_followed(self):
        victim = self.root / 'victim'
        victim.write_text('preserve')
        (self.state / 'cortex-skill-evidence.jsonl').symlink_to(victim)
        self.record(ok=False)
        self.assertEqual(victim.read_text(), 'preserve')

    def test_foreign_project_is_rejected(self):
        rows = self.log.read_text().splitlines()
        row = json.loads(rows[0])
        row['project_ref'] = '/other-project'
        self.log.write_text(json.dumps(row) + '\n')
        self.record(ok=False)
        self.assertFalse((self.state / 'cortex-skill-evidence.jsonl').exists())

    def test_hard_link_cannot_append_evidence_to_route_log(self):
        os.link(self.log, self.state / 'cortex-skill-evidence.jsonl')
        self.record(ok=False)
        self.assertEqual(self.log.read_bytes(), self.before)


if __name__ == '__main__':
    unittest.main()

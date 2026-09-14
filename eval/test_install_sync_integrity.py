#!/usr/bin/env python3
"""Installer and sync regressions using disposable homes and local Git fixtures."""
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IsolatedTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.env = {**os.environ, 'HOME': str(self.home),
                    'CLAUDE_DIR': str(self.home / 'claude'),
                    'CODEX_DIR': str(self.home / 'codex'),
                    'PYTHONDONTWRITEBYTECODE': '1'}
        self.env.pop('CORTEX_HOME', None)
        self.env.pop('CODEX_HOME', None)

    def run_command(self, *args):
        return subprocess.run(args, env=self.env, cwd=self.root,
                              capture_output=True, text=True)


class InstallerTests(IsolatedTest):
    def install(self):
        return self.run_command('bash', str(ROOT / 'install.sh'))

    def test_fresh_and_repeat_preserve_registry_and_log(self):
        codex = Path(self.env['CODEX_DIR'])
        codex.mkdir()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        state = Path(self.env['CLAUDE_DIR'])
        (state / 'cortex.md').write_text('custom registry')
        (state / 'cortex-log.jsonl').write_text('custom log\n')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((state / 'cortex.md').read_text(), 'custom registry')
        self.assertEqual((state / 'cortex-log.jsonl').read_text(), 'custom log\n')
        self.assertEqual((state / 'cortex.md.new').read_bytes(),
                         (ROOT / 'templates/cortex.md').read_bytes())
        self.assertTrue((codex / 'skills/cortex-delegate/SKILL.md').is_file())

    def test_symlink_conflicts_preflight_every_destination(self):
        targets = ('bin', 'bin/cortex', 'skills', 'skills/cortex-init',
                   'skills/cortex-init/SKILL.md', 'cortex.md', 'cortex.md.new',
                   'cortex-log.jsonl', 'codex/skills',
                   'codex/skills/cortex-delegate', 'codex/skills/cortex-delegate/SKILL.md',
                   'skills/cortex-init/.cortex-installed.sha256',
                   'codex/skills/cortex-delegate/.cortex-installed.sha256')
        for index, relative in enumerate(targets):
            for dangling in (False, True):
                with self.subTest(relative=relative, dangling=dangling):
                    case = self.root / f'case-{index}-{dangling}'
                    state, codex = case / 'state', case / 'codex'
                    state.mkdir(parents=True)
                    codex.mkdir()
                    self.env.update(CLAUDE_DIR=str(state), CODEX_DIR=str(codex))
                    target = case / relative if relative.startswith('codex/') else state / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    external = case / 'external'
                    if not dangling:
                        if relative.endswith(('cortex', 'SKILL.md', '.md', '.new', '.jsonl')):
                            external.write_text('external user content')
                        else:
                            external.mkdir()
                            (external / 'SKILL.md').write_text('external user content')
                    target.symlink_to(external)
                    result = self.install()
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('Conflict:', result.stderr)
                    self.assertTrue(target.is_symlink())
                    if dangling:
                        self.assertFalse(external.exists())
                    elif external.is_file():
                        self.assertEqual(external.read_text(), 'external user content')
                    else:
                        self.assertEqual(list(external.iterdir()), [external / 'SKILL.md'])
                        self.assertEqual((external / 'SKILL.md').read_text(), 'external user content')
                    # Even late conflicts must be detected before the CLI is copied.
                    if relative not in ('bin', 'bin/cortex'):
                        self.assertFalse((state / 'bin/cortex').exists())

    def test_custom_skill_and_wrong_types_fail_without_partial_install(self):
        state = Path(self.env['CLAUDE_DIR'])
        skill = state / 'skills/cortex-init/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('custom skill')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(skill.read_text(), 'custom skill')
        self.assertFalse((state / 'bin').exists())
        skill.unlink()
        skill.mkdir()
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse((state / 'bin').exists())

    def test_previous_shipped_skill_upgrades_without_a_content_stamp(self):
        relative = 'skills/cortex-init/SKILL.md'
        current = (ROOT / relative).read_bytes()
        revisions = self.run_command('git', '-C', str(ROOT), 'log', '--format=%H', '--', relative)
        self.assertEqual(revisions.returncode, 0, revisions.stderr)
        previous = None
        for revision in revisions.stdout.splitlines():
            result = self.run_command('git', '-C', str(ROOT), 'show', f'{revision}:{relative}')
            self.assertEqual(result.returncode, 0, result.stderr)
            if result.stdout.encode() != current:
                previous = result.stdout.encode()
                break
        self.assertIsNotNone(previous, 'fixture needs an older shipped skill version')
        state = Path(self.env['CLAUDE_DIR'])
        destination = state / relative
        destination.parent.mkdir(parents=True)
        destination.write_bytes(previous + b'\nGenuine local edit to old release.\n')
        customized = destination.read_bytes()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_bytes(), customized)
        self.assertFalse((state / 'bin').exists())
        destination.write_bytes(previous)
        (state / 'cortex.md').write_text('custom registry')
        (state / 'cortex-log.jsonl').write_text('custom log\n')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(destination.read_bytes(), current)
        self.assertEqual((destination.parent / '.cortex-installed.sha256').read_text().strip(),
                         hashlib.sha256(current).hexdigest())
        self.assertEqual((state / 'cortex.md').read_text(), 'custom registry')
        self.assertEqual((state / 'cortex-log.jsonl').read_text(), 'custom log\n')
        self.assertEqual(self.install().returncode, 0)

    def test_content_stamp_supports_upgrades_without_git_history(self):
        checkout = self.root / 'source archive'
        checkout.mkdir()
        for directory in ('bin', 'skills', 'templates'):
            shutil.copytree(ROOT / directory, checkout / directory)
        shutil.copy2(ROOT / 'install.sh', checkout / 'install.sh')
        codex = Path(self.env['CODEX_DIR'])
        codex.mkdir()
        command = ('bash', str(checkout / 'install.sh'))
        result = self.run_command(*command)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('cortex-init', 'cortex-delegate'):
            source = checkout / 'skills' / name / 'SKILL.md'
            source.write_text(source.read_text() + '\nNew release content.\n')
        result = self.run_command(*command)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name, state in (('cortex-init', Path(self.env['CLAUDE_DIR'])),
                            ('cortex-delegate', codex)):
            installed = state / 'skills' / name / 'SKILL.md'
            self.assertEqual(installed.read_bytes(), (checkout / 'skills' / name / 'SKILL.md').read_bytes())
            installed.write_text(installed.read_text() + '\nGenuine local edit.\n')
        before = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        result = self.run_command(*command)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_linked_home_and_ancestor_are_rejected(self):
        external = self.root / 'external'
        external.mkdir()
        link = self.root / 'link'
        link.symlink_to(external)
        for destination in (link, link / 'nested'):
            with self.subTest(destination=destination):
                self.env['CLAUDE_DIR'] = str(destination)
                self.assertNotEqual(self.install().returncode, 0)
                self.assertEqual(list(external.iterdir()), [])

    def test_custom_state_and_skill_commands_agree(self):
        skill = (ROOT / 'skills/cortex-init/SKILL.md').read_text()
        scan = re.findall(r'```bash\n(.*?)\n```', skill, re.S)[0]
        for use_override in (False, True):
            with self.subTest(use_override=use_override):
                state = self.root / ('neutral state' if use_override else 'claude state')
                self.env['CLAUDE_DIR'] = str(self.root / 'unused' if use_override else state)
                if use_override:
                    self.env['CORTEX_HOME'] = str(state)
                result = self.install()
                self.assertEqual(result.returncode, 0, result.stderr)
                result = self.run_command('bash', '-c', scan)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((state / 'cortex-inventory.json').is_file())
                self.assertTrue((state / 'cortex.md').is_file())
                self.assertFalse((self.home / '.claude').exists())
                self.assertFalse(Path(self.env['CODEX_DIR']).exists())
                if use_override:
                    self.assertFalse(Path(self.env['CLAUDE_DIR']).exists())


class SyncTests(IsolatedTest):
    def setUp(self):
        super().setUp()
        self.src, self.dst = self.root / 'upstream', self.root / 'installed'
        self.src.mkdir()
        self.dst.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.com')
        self.write('conflict.md', 'original', 'original body')
        self.write('merge.md', 'original', 'original body')
        self.write('update.md', 'original', 'original body')
        self.base = self.commit()
        for source in self.src.glob('*.md'):
            shutil.copy2(source, self.dst / source.name)
        (self.dst / '.synced-from').write_text(self.base + '\n')

    def git(self, *args):
        result = self.run_command('git', '-C', str(self.src), *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write(self, name, description, body, local=False):
        ((self.dst if local else self.src) / name).write_text(
            f'---\nname: fixture\ndescription: {description}\n---\n{body}\n')

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def sync(self, apply=False):
        return self.run_command(sys.executable, '-B', str(ROOT / 'bin/sync-agents'),
                                '--src', str(self.src), '--dst', str(self.dst),
                                *(['--apply'] if apply else []))

    def test_conflicts_keep_base_across_runs_while_successful_files_advance(self):
        self.write('conflict.md', 'local description', 'original body', local=True)
        self.write('merge.md', 'local description', 'original body', local=True)
        self.write('conflict.md', 'upstream description', 'new body')
        self.write('merge.md', 'original', 'new body')
        self.write('update.md', 'original', 'new body')
        self.write('new.md', 'original', 'new file')
        head = self.commit()
        before = {p.name: p.read_bytes() for p in self.dst.iterdir()}
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.dst.iterdir()})
        for _ in range(2):
            result = self.sync(apply=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertRegex(result.stdout, r'CONFLICT:\s+1')
            self.assertEqual((self.dst / 'conflict.md').read_bytes(), before['conflict.md'])
            self.assertEqual(json.loads((self.dst / '.synced-bases.json').read_text()),
                             {'conflict.md': self.base})
            self.assertEqual((self.dst / '.synced-from').read_text().strip(), head)
        self.assertIn('local description', (self.dst / 'merge.md').read_text())
        self.assertIn('new body', (self.dst / 'merge.md').read_text())
        self.assertEqual((self.dst / 'new.md').read_bytes(), (self.src / 'new.md').read_bytes())
        self.assertEqual((self.dst / 'update.md').read_bytes(), (self.src / 'update.md').read_bytes())
        self.write('merge.md', 'original', 'third body')
        self.write('conflict.md', 'upstream description', 'third body')
        self.commit()
        result = self.sync(apply=True)
        self.assertRegex(result.stdout, r'CONFLICT:\s+1')
        self.assertIn('third body', (self.dst / 'merge.md').read_text())
        self.assertIn('local description', (self.dst / 'merge.md').read_text())
        shutil.copy2(self.src / 'conflict.md', self.dst / 'conflict.md')
        result = self.sync(apply=True)
        self.assertRegex(result.stdout, r'CONFLICT:\s+0')
        self.assertEqual(json.loads((self.dst / '.synced-bases.json').read_text()), {})

    def test_added_upstream_conflict_remains_a_conflict(self):
        self.write('added.md', 'upstream', 'body')
        self.write('added.md', 'local', 'body', local=True)
        self.commit()
        for _ in range(2):
            result = self.sync(apply=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertRegex(result.stdout, r'CONFLICT:\s+1')
            self.assertIn('description: local', (self.dst / 'added.md').read_text())

    def test_body_conflict_without_initial_stamp_preserves_explicit_base(self):
        (self.dst / '.synced-from').unlink()
        self.write('conflict.md', 'original', 'local body', local=True)
        self.write('conflict.md', 'original', 'upstream body')
        self.commit()
        result = self.run_command(sys.executable, '-B', str(ROOT / 'bin/sync-agents'),
                                  '--src', str(self.src), '--dst', str(self.dst),
                                  '--base', self.base, '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        for apply in (False, True):
            result = self.sync(apply=apply)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertRegex(result.stdout, r'CONFLICT:\s+1')
            self.assertIn('local body', (self.dst / 'conflict.md').read_text())
            self.assertEqual(json.loads((self.dst / '.synced-bases.json').read_text()),
                             {'conflict.md': self.base})

    def test_invalid_saved_bases_fail_before_writing(self):
        self.write('update.md', 'original', 'upstream update')
        self.commit()
        path = self.dst / '.synced-bases.json'
        for content in ('{', '[]', '{"conflict.md": 7}', '{"conflict.md": "missing-commit"}'):
            with self.subTest(content=content):
                path.write_text(content)
                before = {p.name: p.read_bytes() for p in self.dst.iterdir()}
                result = self.sync(apply=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('invalid', result.stderr)
                self.assertEqual(before, {p.name: p.read_bytes() for p in self.dst.iterdir()})


if __name__ == '__main__':
    unittest.main()

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
        self.env.pop('CORTEX_OBSIDIAN_ROOT', None)
        self.env.pop('CORTEX_REPO', None)
        self.env['CORTEX_SESSION_ID'] = 'isolated-install-fixture'

    def run_command(self, *args):
        return subprocess.run(args, env=self.env, cwd=self.root,
                              capture_output=True, text=True)


class InstallerTests(IsolatedTest):
    def install(self):
        return self.run_command('bash', str(ROOT / 'install.sh'))

    def test_installed_commands_resolve_default_and_custom_roots(self):
        for mode in ('default', 'empty', 'claude', 'cortex', 'both'):
            with self.subTest(mode=mode):
                home = self.root / mode / 'home with spaces'
                home.mkdir(parents=True)
                self.env.update(HOME=str(home), CODEX_DIR=str(home / '.codex'))
                self.env.pop('CORTEX_HOME', None)
                self.env.pop('CLAUDE_DIR', None)
                state = home / '.claude'
                if mode == 'empty':
                    self.env.update(CORTEX_HOME='', CLAUDE_DIR='')
                if mode in ('claude', 'both'):
                    state = home / 'claude state'
                    self.env['CLAUDE_DIR'] = str(state)
                if mode in ('cortex', 'both'):
                    state = home / 'cortex state'
                    self.env['CORTEX_HOME'] = str(state)
                (home / '.codex').mkdir()
                (home / '.agents').mkdir()
                result = self.install()
                self.assertEqual(result.returncode, 0, result.stderr)
                roots = (state / 'skills', home / '.codex/skills', home / '.agents/skills')
                for root in roots:
                    for name in ('cortex-log', 'cortex-learn', 'cortex-reroute'):
                        with self.subTest(surface=root, skill=name):
                            path = root / name / 'SKILL.md'
                            self.assertEqual(path.read_bytes(), (ROOT / 'skills' / name / 'SKILL.md').read_bytes())
                            blocks = re.findall(r'```bash\n(.*?)\n```', path.read_text(), re.S)
                            if name == 'cortex-reroute':
                                values = {'<same task as before>': 'fixture task', '<class>': 'build',
                                          '<new system>': 'Direct', '<new pattern>': 'fixture',
                                          '<new agent>': 'Fixture', '<new tier>': 'L2',
                                          '<...>': 'fixture', '<old route>': 'Direct > old @ L2'}
                                command = blocks[1]
                                for placeholder, value in values.items():
                                    command = command.replace(placeholder, value)
                                result = self.run_command('bash', '-c', command)
                                self.assertEqual(result.returncode, 0, result.stderr)
                            command = blocks[0].replace('<the route the user wanted>', 'Direct > revised @ L2')
                            result = self.run_command('bash', '-c', command)
                            self.assertEqual(result.returncode, 0, result.stderr)
                            if name == 'cortex-reroute':
                                rows = [json.loads(line) for line in (state / 'cortex-log.jsonl').read_text().splitlines()]
                                self.assertEqual(rows[-1]['event'], 'reroute')
                                self.assertEqual(rows[-1]['ref'], rows[-2]['event_id'])
                init = state / 'skills/cortex-init/SKILL.md'
                scan = re.findall(r'```bash\n(.*?)\n```', init.read_text(), re.S)[0]
                result = self.run_command('bash', '-c', scan)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((state / 'cortex-inventory.json').is_file())
                result = self.run_command(sys.executable, str(state / 'bin/cortex'), 'doctor', '--no-probe')
                self.assertNotIn('invalid CLI reference', result.stdout)
                before = {p: p.read_bytes() for root in roots for p in root.rglob('*') if p.is_file()}
                log = (state / 'cortex-log.jsonl').read_bytes()
                self.assertEqual(self.install().returncode, 0)
                self.assertEqual(before, {p: p.read_bytes() for root in roots for p in root.rglob('*') if p.is_file()})
                self.assertEqual(log, (state / 'cortex-log.jsonl').read_bytes())
                if mode in ('claude', 'cortex', 'both'):
                    self.assertFalse((home / '.claude').exists())
                if mode == 'both':
                    self.assertFalse(Path(self.env['CLAUDE_DIR']).exists())

    def test_doctor_ignores_urls_but_checks_real_cli_paths(self):
        self.env.pop('CLAUDE_DIR')
        self.assertEqual(self.install().returncode, 0)
        state = self.home / '.claude'
        skill = state / 'skills/cortex-log/SKILL.md'
        original = skill.read_text()
        urls = ('https://github.com/amitvijapur/cortex/blob/main/bin/cortex',
                'http://example.com/source/bin/cortex', 'file:///source/bin/cortex',
                'https://[::1]/source/bin/cortex',
                'https://example.com/source(v1)/bin/cortex',
                'https://example.com/source;version=1/bin/cortex',
                'https://example.com/?first=1&next=/source/bin/cortex')
        valid = ('~/.claude/bin/cortex', '$HOME/.claude/bin/cortex',
                 '${HOME}/.claude/bin/cortex', str(state / 'bin/cortex'))
        broken = ('~/.Codex/bin/cortex', '$HOME/missing/bin/cortex',
                  '${HOME}/missing/bin/cortex', str(self.root / 'missing/bin/cortex'))
        for reference in (*valid, *broken):
            with self.subTest(reference=reference):
                skill.write_text(original + '\n' + '\n'.join(f'[source]({url})' for url in urls)
                                 + f'\npython3 {reference} show\n')
                result = self.run_command(sys.executable, str(state / 'bin/cortex'),
                                          'doctor', '--no-probe', '-v')
                failures = [line for line in result.stdout.splitlines() if 'invalid CLI reference' in line]
                self.assertEqual(len(failures), int(reference in broken), result.stdout)
                if reference in broken:
                    self.assertIn(reference, failures[0])

    def test_doctor_checks_adjacent_url_and_local_references(self):
        self.env.pop('CLAUDE_DIR')
        self.assertEqual(self.install().returncode, 0)
        state = self.home / '.claude'
        skill = state / 'skills/cortex-log/SKILL.md'
        original = skill.read_text()
        url = 'https://example.com/bin/cortex'
        valid = ('~/.claude/bin/cortex', '$HOME/.claude/bin/cortex',
                 '${HOME}/.claude/bin/cortex', str(state / 'bin/cortex'))
        broken = ('~/.Codex/bin/cortex', '$HOME/missing/bin/cortex',
                  '${HOME}/missing/bin/cortex', str(self.root / 'missing/bin/cortex'))
        layouts = ('curl {url};{reference} show',
                   'curl {url}&&{reference} show',
                   'curl {url}&{reference} show',
                   'curl {url}|{reference} show',
                   'curl {url}||{reference} show',
                   '[source]({url})[local]({reference})',
                   '[local]({reference})[source]({url})',
                   '|{url}|{reference}|',
                   '|{reference}|{url}|',
                   'curl {url};{installed};{reference} show',
                   '[source]({url})[installed]({installed})[local]({reference})')
        for reference in (*valid, *broken):
            for layout in layouts:
                with self.subTest(reference=reference, layout=layout):
                    # These commands are only text inspected by Doctor, never executed.
                    skill.write_text(original + '\n' + layout.format(
                        url=url, installed=state / 'bin/cortex', reference=reference) + '\n')
                    result = self.run_command(sys.executable, str(state / 'bin/cortex'),
                                              'doctor', '--no-probe', '-v')
                    failures = [line for line in result.stdout.splitlines()
                                if 'invalid CLI reference' in line]
                    self.assertEqual(len(failures), int(reference in broken), result.stdout)
                    if reference in broken:
                        self.assertIn(f': {reference} (missing target ', failures[0])

    def test_doctor_preserves_quoted_literal_cli_paths(self):
        self.env.pop('CLAUDE_DIR')
        self.assertEqual(self.install().returncode, 0)
        state = self.home / '.claude'
        skill = state / 'skills/cortex-log/SKILL.md'
        original = skill.read_text()
        names = ('fixture space', 'fixture(v1)', 'fixture&test',
                 'fixture;test', 'fixture[test]', 'fixture (v1)&test;[1]/nested')
        url = 'https://example.com/source(v1);version=1/bin/cortex'
        for name in names:
            existing = self.home / name / 'bin/cortex'
            existing.parent.mkdir(parents=True)
            existing.touch()
            missing = self.home / 'missing' / name / 'bin/cortex'
            for target in (existing, missing):
                suffix = target.relative_to(self.home).as_posix()
                references = (str(target), f'~/{suffix}',
                              f'$HOME/{suffix}', f'${{HOME}}/{suffix}')
                for reference in references:
                    for quote in ('"', "'"):
                        with self.subTest(reference=reference, quote=quote):
                            # Literal fixture text is inspected, never shell-executed.
                            skill.write_text(original + '\n'
                                             + f'curl {quote}{url}{quote};python3 '
                                             + f'{quote}{reference}{quote} show\n'
                                             + f'[local]({state / "bin/cortex"})[source]({url})\n')
                            result = self.run_command(sys.executable, str(state / 'bin/cortex'),
                                                      'doctor', '--no-probe', '-v')
                            failures = [line for line in result.stdout.splitlines()
                                        if 'invalid CLI reference' in line]
                            self.assertEqual(result.returncode, int(target == missing),
                                             result.stdout + result.stderr)
                            self.assertEqual(len(failures), int(target == missing), result.stdout)
                            if target == missing:
                                self.assertIn(f': {reference} (missing target {target})', failures[0])

    def test_doctor_preserves_quoted_paths_after_prose_apostrophe(self):
        self.env.pop('CLAUDE_DIR')
        self.assertEqual(self.install().returncode, 0)
        state = self.home / '.claude'
        skill = state / 'skills/cortex-log/SKILL.md'
        original = skill.read_text()
        existing = self.home / 'existing&test' / 'bin/cortex'
        existing.parent.mkdir(parents=True)
        existing.touch()
        missing = self.home / 'missing&test' / 'bin/cortex'
        for target in (existing, missing):
            suffix = target.relative_to(self.home).as_posix()
            references = (str(target), f'~/{suffix}',
                          f'$HOME/{suffix}', f'${{HOME}}/{suffix}')
            for reference in references:
                for quote in ('"', "'"):
                    with self.subTest(reference=reference, quote=quote):
                        # Prose apostrophes must not consume a later path opener.
                        skill.write_text(original + '\n'
                                         + f"Don't run python3 {quote}{reference}{quote} show\n")
                        result = self.run_command(sys.executable, str(state / 'bin/cortex'),
                                                  'doctor', '--no-probe', '-v')
                        failures = [line for line in result.stdout.splitlines()
                                    if 'invalid CLI reference' in line]
                        self.assertEqual(result.returncode, int(target == missing),
                                         result.stdout + result.stderr)
                        self.assertEqual(len(failures), int(target == missing), result.stdout)
                        if target == missing:
                            self.assertIn(f': {reference} (missing target {target})', failures[0])

    def test_installer_prints_runnable_custom_root_commands(self):
        state = self.root / "custom root's state"
        self.env['CORTEX_HOME'] = str(state)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        command = next(line.strip() for line in result.stdout.splitlines()
                       if line.strip().endswith(' doctor'))
        # A one-shot installer override is not present in the next shell.
        self.env.pop('CORTEX_HOME')
        self.env.pop('CLAUDE_DIR')
        result = self.run_command('bash', '-c', command + ' --no-probe -v')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'cortex.md present: {state / "cortex.md"}', result.stdout)
        self.assertFalse((self.home / '.claude').exists())

    def test_installed_skill_use_imports_packaged_helper_and_keeps_streams_separate(self):
        self.env.update(CORTEX_HOST='codex', CORTEX_SESSION_ID='installed-fixture')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        state = Path(self.env['CLAUDE_DIR'])
        cli = state / 'bin/cortex'
        # Do not permit a repository PYTHONPATH to hide missing packaging.
        self.env.pop('PYTHONPATH', None)
        result = self.run_command(sys.executable, '-I', str(cli), 'log-line',
                                  'Direct > fixture @ L2', 'installed packaging fixture',
                                  '--class', 'build')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = state / 'cortex-log.jsonl'
        before = log.read_bytes()
        route = json.loads(before.splitlines()[-1])
        skill = self.root / 'fixture/SKILL.md'
        skill.parent.mkdir()
        skill.write_text('---\nname: fixture\n---\nSynthetic private body.\n')
        evidence = state / 'cortex-skill-evidence.jsonl'
        self.assertFalse(evidence.exists())
        result = self.run_command(sys.executable, '-I', str(cli), 'skill-use',
                                  '--ref', route['event_id'], '--skill', str(skill),
                                  '--stage', 'applied')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = [json.loads(line) for line in evidence.read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['event'], 'skill_evidence')
        self.assertEqual(row['ref'], route['event_id'])
        self.assertEqual(row['stage'], 'applied')
        self.assertEqual(row['provenance'], 'self_reported')
        self.assertEqual(row['skill_path'], str(skill.resolve()))
        self.assertEqual(row['skill_sha256'], hashlib.sha256(skill.read_bytes()).hexdigest())
        self.assertNotIn('Synthetic private body.', evidence.read_text())
        self.assertEqual(log.read_bytes(), before)

    def test_shared_and_codex_copies_preserved_or_maintained(self):
        shared = self.home / '.agents/skills'
        codex = Path(self.env['CODEX_DIR']) / 'skills'
        for root in (shared, codex):
            path = root / 'cortex-log/SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_bytes((ROOT / 'skills/cortex-log/SKILL.md').read_bytes())
        self.assertEqual(self.install().returncode, 0)
        for root in (shared, codex):
            for name in ('cortex-log', 'cortex-learn', 'cortex-reroute'):
                path = root / name / 'SKILL.md'
                self.assertEqual(path.read_bytes(), (ROOT / 'skills' / name / 'SKILL.md').read_bytes())
        custom = shared / 'cortex-reroute/SKILL.md'
        custom.write_text('python3 ~/.Codex/bin/cortex correct # local customization\n')
        before = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('customized skill', result.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_shared_links_are_refused_without_touching_targets(self):
        external = self.root / 'external-skills'
        external.mkdir()
        shared = self.home / '.agents'
        shared.mkdir()
        (shared / 'skills').symlink_to(external)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(external.iterdir()), [])
        self.assertFalse(Path(self.env['CLAUDE_DIR']).exists())

    def test_shared_skill_and_stamp_links_refuse_even_matching_content(self):
        for index, relative in enumerate(('cortex-log', 'cortex-log/SKILL.md',
                                           'cortex-log/.cortex-installed.sha256')):
            for dangling in (False, True):
                with self.subTest(relative=relative, dangling=dangling):
                    case = self.root / f'shared-{index}-{dangling}'
                    case.mkdir()
                    self.env['HOME'] = str(case)
                    self.env['CLAUDE_DIR'] = str(case / '.claude')
                    self.env['CODEX_DIR'] = str(case / '.codex')
                    target = case / '.agents/skills' / relative
                    target.parent.mkdir(parents=True)
                    external = case / 'external'
                    if not dangling:
                        if relative == 'cortex-log':
                            external.mkdir()
                            shutil.copy2(ROOT / 'skills/cortex-log/SKILL.md', external / 'SKILL.md')
                        else:
                            external.write_bytes((ROOT / 'skills/cortex-log/SKILL.md').read_bytes())
                    target.symlink_to(external)
                    result = self.install()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('symlink', result.stderr)
                    self.assertTrue(target.is_symlink())
                    self.assertFalse((case / '.claude').exists())
                    if dangling:
                        self.assertFalse(external.exists())

    def test_doctor_checks_shared_duplicates_and_invalid_references(self):
        (self.home / '.agents').mkdir()
        Path(self.env['CODEX_DIR']).mkdir()
        self.assertEqual(self.install().returncode, 0)
        shared = self.home / '.agents/skills/cortex-log/SKILL.md'
        shared.write_text('python3 ~/.Codex/bin/cortex show\n')
        result = self.run_command(sys.executable, str(ROOT / 'bin/cortex'),
                                  'doctor', '--no-probe', '-v')
        self.assertIn('invalid CLI reference', result.stdout)
        self.assertIn(str(shared), result.stdout)
        self.assertIn('duplicate personal skill cortex-log', result.stdout)
        shared.unlink()
        shared.symlink_to(self.root / 'missing-skill')
        result = self.run_command(sys.executable, str(ROOT / 'bin/cortex'),
                                  'doctor', '--no-probe')
        self.assertIn('unreadable personal skill', result.stdout)

    def test_doctor_duplicate_severity_and_label_limits(self):
        (self.home / '.agents').mkdir()
        Path(self.env['CODEX_DIR']).mkdir()
        self.assertEqual(self.install().returncode, 0)
        self.env['CORTEX_REPO'] = str(ROOT)
        state = Path(self.env['CLAUDE_DIR'])
        (state / 'cortex-log.jsonl').write_text(json.dumps(
            {'system': 'Direct', 'task': 'fixture', 'tier': 'L2'}) + '\n')

        def doctor():
            return self.run_command(sys.executable, str(ROOT / 'bin/cortex'),
                                    'doctor', '--no-probe', '-v').stdout

        output = doctor()
        self.assertIn('✓ duplicate personal skill cortex-log (byte-identical)', output)
        self.assertNotIn('! duplicate personal skill', output)
        self.assertNotIn('system never used', output)
        self.assertNotIn('system used:', output)
        self.assertIn('no routes labelled system OMC; usage unknown, aliases/other hosts not measured', output)
        self.assertIn('routes labelled system Direct: 1 (usage unknown)', output)
        shared = self.home / '.agents/skills/cortex-log/SKILL.md'
        shared.write_text(shared.read_text() + '\nLocal customization.\n')
        output = doctor()
        self.assertIn('! duplicate personal skill cortex-log (divergent, undocumented content)', output)
        self.assertEqual(output.count(f'personal skill differs from repo source: {shared}'), 1)
        self.assertNotIn('skill cortex-log differs from repo source', output)
        (shared.parent / '.cortex-installed.sha256').write_text(
            hashlib.sha256(shared.read_bytes()).hexdigest() + '\n')
        output = doctor()
        self.assertIn('✓ duplicate personal skill cortex-log (divergent, installation hashes verified', output)
        self.assertNotIn('! duplicate personal skill cortex-log', output)
        # Installation hashes document installed bytes, not agreement with source.
        self.assertIn(f'personal skill differs from repo source: {shared}', output)

    def test_fresh_and_repeat_preserve_registry_and_log(self):
        codex = Path(self.env['CODEX_DIR'])
        codex.mkdir()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        state = Path(self.env['CLAUDE_DIR'])
        self.assertEqual((state / 'bin/cortex_jev.py').read_bytes(),
                         (ROOT / 'bin/cortex_jev.py').read_bytes())
        self.assertEqual((state / 'bin/cortex_skill_evidence.py').read_bytes(),
                         (ROOT / 'bin/cortex_skill_evidence.py').read_bytes())
        adviser = self.run_command(sys.executable, str(state / 'bin/cortex'),
                                   'advise', 'installation smoke check', '--mode', 'off', '--json')
        self.assertEqual(adviser.returncode, 0, adviser.stderr)
        self.assertEqual(json.loads(adviser.stdout)['status'], 'off')
        self.assertFalse((state / 'experiments').exists())
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
        targets = ('bin', 'bin/cortex', 'bin/cortex_jev.py', 'bin/cortex_skill_evidence.py', 'skills', 'skills/cortex-init',
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
                        if relative.endswith(('cortex', 'SKILL.md', '.md', '.new', '.jsonl', '.py')):
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

    def sync(self, apply=False, base=None):
        return self.run_command(sys.executable, '-B', str(ROOT / 'bin/sync-agents'),
                                '--src', str(self.src), '--dst', str(self.dst),
                                *(['--base', base] if base else []),
                                *(['--apply'] if apply else []))

    def snapshot(self, root):
        """Include directories and dangling links without following those links."""
        result = {}
        for path in [root, *root.rglob('*')]:
            name = str(path.relative_to(root))
            if path.is_symlink():
                result[name] = ('link', os.readlink(path))
            elif path.is_dir():
                result[name] = ('directory',)
            else:
                result[name] = ('file', path.read_bytes())
        return result

    def test_all_destination_links_preflight_before_any_mutation(self):
        self.write('update.md', 'original', 'upstream update')
        (self.src / 'z-team').mkdir()
        self.write('z-team/agent.md', 'original', 'new agent')
        self.commit()
        original = self.dst
        targets = ('update.md', 'z-team', 'z-team/agent.md', '.synced-from',
                   '.synced-bases.json')
        for index, relative in enumerate(targets):
            for dangling in (False, True):
                with self.subTest(relative=relative, dangling=dangling):
                    case = self.root / f'links-{index}-{dangling}'
                    case.mkdir()
                    self.dst = case / 'installed'
                    shutil.copytree(original, self.dst)
                    external = case / 'external'
                    if not dangling:
                        if relative == 'z-team':
                            external.mkdir()
                            (external / 'agent.md').write_text('external content')
                        else:
                            external.write_text('external content')
                    target = self.dst / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        target.unlink()
                    target.symlink_to(external)
                    before = self.snapshot(case)
                    for apply in (False, True):
                        result = self.sync(apply=apply)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertIn('unsafe destination', result.stderr)
                        self.assertEqual(self.snapshot(case), before)
        self.dst = original

    def test_destination_and_ancestor_links_are_rejected(self):
        self.write('update.md', 'original', 'upstream update')
        self.commit()
        original = self.dst
        link = self.root / 'linked'
        link.symlink_to(original)
        ancestor = self.root / 'ancestor'
        ancestor.symlink_to(self.root)
        for destination in (link, ancestor / 'installed',
                            link / '..' / 'installed'):
            with self.subTest(destination=destination):
                self.dst = destination
                before = self.snapshot(original)
                result = self.sync(apply=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('unsafe destination', result.stderr)
                self.assertEqual(self.snapshot(original), before)
        self.dst = original

    def test_wrong_destination_types_preflight_before_any_mutation(self):
        self.write('update.md', 'original', 'upstream update')
        (self.src / 'z-team').mkdir()
        self.write('z-team/agent.md', 'original', 'new agent')
        self.commit()
        original = self.dst
        for index, relative in enumerate(('z-team', 'z-team/agent.md',
                                           '.synced-from', '.synced-bases.json')):
            with self.subTest(relative=relative):
                self.dst = self.root / f'wrong-type-{index}'
                shutil.copytree(original, self.dst)
                target = self.dst / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.unlink()
                if relative == 'z-team':
                    target.write_text('not a directory')
                else:
                    target.mkdir()
                before = self.snapshot(self.dst)
                result = self.sync(apply=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('unsafe destination', result.stderr)
                self.assertEqual(self.snapshot(self.dst), before)
        self.dst = original

    def test_case_insensitive_metadata_collision_refuses_before_writes(self):
        self.write('update.md', 'original', 'upstream update')
        (self.src / '.SYNCED-FROM').mkdir()
        self.write('.SYNCED-FROM/agent.md', 'original', 'new agent')
        self.commit()
        before = self.snapshot(self.dst)
        result = self.sync(apply=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsafe destination', result.stderr)
        self.assertEqual(self.snapshot(self.dst), before)

    def test_dirty_source_uses_only_pinned_committed_blobs(self):
        self.write('merge.md', 'custom description', 'original body', local=True)
        self.write('merge.md', 'original', 'committed body')
        self.write('update.md', 'original', 'committed body')
        (self.src / 'team').mkdir()
        self.write('team/new.md', 'original', 'committed new body')
        head = self.commit()
        committed_update = (self.src / 'update.md').read_bytes()
        committed_new = (self.src / 'team/new.md').read_bytes()
        self.write('update.md', 'staged edit', 'staged body')
        self.write('staged-new.md', 'staged', 'uncommitted new body')
        self.git('add', '.')
        self.write('update.md', 'unstaged edit', 'unstaged body')
        self.write('merge.md', 'dirty description', 'dirty body')
        (self.src / 'team/new.md').unlink()
        self.write('untracked.md', 'untracked', 'untracked body')
        # A source working-tree link must not be read either.
        (self.src / 'conflict.md').unlink()
        (self.src / 'conflict.md').symlink_to(self.root / 'absent')
        before = self.snapshot(self.dst)
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(self.dst), before)
        result = self.sync(apply=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.dst / 'update.md').read_bytes(), committed_update)
        self.assertEqual((self.dst / 'team/new.md').read_bytes(), committed_new)
        self.assertIn('custom description', (self.dst / 'merge.md').read_text())
        self.assertIn('committed body', (self.dst / 'merge.md').read_text())
        self.assertFalse((self.dst / 'staged-new.md').exists())
        self.assertFalse((self.dst / 'untracked.md').exists())
        self.assertEqual((self.dst / '.synced-from').read_text(), head + '\n')
        installed = self.snapshot(self.dst)
        self.assertEqual(self.sync(apply=True).returncode, 0)
        self.assertEqual(self.snapshot(self.dst), installed)

    def test_committed_source_symlink_is_rejected_before_writes(self):
        self.write('update.md', 'original', 'upstream update')
        (self.src / 'z-link.md').symlink_to('update.md')
        self.commit()
        before = self.snapshot(self.dst)
        result = self.sync(apply=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not a regular committed agent', result.stderr)
        self.assertEqual(self.snapshot(self.dst), before)

    def test_new_agent_directories_cannot_collide_with_missing_stamps(self):
        (self.dst / '.synced-from').unlink()
        self.write('update.md', 'original', 'upstream update')
        for name in ('.synced-from', '.synced-bases.json'):
            with self.subTest(name=name):
                directory = self.src / name
                directory.mkdir()
                self.write(f'{name}/agent.md', 'original', 'new agent')
                self.commit()
                before = self.snapshot(self.dst)
                result = self.sync(apply=True, base=self.base)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('target collision', result.stderr)
                self.assertEqual(self.snapshot(self.dst), before)
                (directory / 'agent.md').unlink()
                directory.rmdir()

    def test_clean_updates_copy_exact_bytes_and_keep_local_only_files(self):
        data = b'---\r\nname: fixture\r\ndescription: original\r\n---\r\nnew body\r\n'
        (self.src / 'update.md').write_bytes(data)
        (self.src / 'team').mkdir()
        (self.src / 'team/new.md').write_bytes(data)
        head = self.commit()
        self.write('local-only.md', 'local', 'local body', local=True)
        local = (self.dst / 'local-only.md').read_bytes()
        result = self.sync(apply=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.dst / 'update.md').read_bytes(), data)
        self.assertEqual((self.dst / 'team/new.md').read_bytes(), data)
        self.assertEqual((self.dst / 'local-only.md').read_bytes(), local)
        self.assertEqual((self.dst / '.synced-from').read_text(), head + '\n')
        self.assertEqual(json.loads((self.dst / '.synced-bases.json').read_text()), {})

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

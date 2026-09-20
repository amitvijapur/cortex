"""Exercise pointer installation without touching real agent homes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.claude = self.base / 'claude'
        self.codex = self.base / 'codex'

    def run_install(self):
        return subprocess.run(
            ['bash', str(ROOT / 'scripts/install_frontend_library.sh')],
            env={**os.environ, 'CLAUDE_DIR': str(self.claude),
                 'CODEX_DIR': str(self.codex)},
            capture_output=True, text=True)

    def test_links_are_idempotent_and_cli_is_untouched(self):
        for home in (self.claude, self.codex):
            (home / 'bin').mkdir(parents=True)
            (home / 'bin/cortex').write_text('existing newer CLI')
        for _ in range(2):
            result = self.run_install()
            self.assertEqual(result.returncode, 0, result.stderr)
        for home in (self.claude, self.codex):
            self.assertEqual((home / 'cortex-frontend').resolve(), ROOT / 'frontend')
            skill = home / 'skills/cortex-frontend-design/SKILL.md'
            self.assertEqual(skill.resolve(), ROOT / 'skills/cortex-frontend-design/SKILL.md')
            self.assertTrue((skill.resolve().parent / '../../frontend/README.md').is_file())
            self.assertEqual((home / 'bin/cortex').read_text(), 'existing newer CLI')

    def test_absent_homes_stay_absent(self):
        self.assertEqual(self.run_install().returncode, 0)
        self.assertFalse(self.claude.exists())
        self.assertFalse(self.codex.exists())

    def test_conflict_is_detected_before_any_install(self):
        self.claude.mkdir()
        self.codex.mkdir()
        conflict = self.codex / 'cortex-frontend'
        conflict.write_text('user content')
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(conflict.read_text(), 'user content')
        self.assertFalse((self.claude / 'cortex-frontend').exists())

    def test_broken_link_is_preserved(self):
        self.claude.mkdir()
        conflict = self.claude / 'cortex-frontend'
        conflict.symlink_to(self.base / 'missing-checkout')
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(os.readlink(conflict), str(self.base / 'missing-checkout'))


if __name__ == '__main__':
    unittest.main()

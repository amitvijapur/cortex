#!/usr/bin/env python3
"""Proposal decision persistence checks in disposable directories."""
import importlib.machinery
import importlib.util
import argparse
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('cortex_proposals', str(Path(__file__).resolve().parents[1] / 'bin/cortex'))
spec = importlib.util.spec_from_loader(loader.name, loader)
cli = importlib.util.module_from_spec(spec)
loader.exec_module(cli)


class ProposalDecisions(unittest.TestCase):
    def test_next_learning_pass_suppresses_rejection_even_after_growth(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cli, 'PROPOSALS_DIR', Path(directory)):
            proposal = Path(directory) / 'candidate.md'
            proposal.write_text('---\nstatus: rejected\nclass: build\nsystem: Direct\npattern: edit\n---\n')
            rows = [{'class': 'build', 'system': 'Direct', 'pattern': 'edit',
                     'tier': 'L2', 'project': 'fixture', 'task': 'Fixture task'}] * 10
            for include_actioned in (False, True):
                args = argparse.Namespace(include_actioned=include_actioned,
                                          threshold=3, check=False, no_proposals=True)
                output = io.StringIO()
                with patch.object(cli, 'read_log', return_value=rows), contextlib.redirect_stdout(output):
                    cli.cmd_learn(args)
                self.assertIn('found 1 pattern' if include_actioned else 'no new patterns', output.getvalue())
            self.assertIn('status: rejected', proposal.read_text())

    def test_only_persisted_actioned_status_suppresses_original_tuple(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cli, 'PROPOSALS_DIR', Path(directory)):
            proposal = Path(directory) / 'candidate.md'
            for status in ('pending', 'rejected', 'approved', 'superseded'):
                with self.subTest(status=status):
                    proposal.write_text(
                        f'---\nstatus: {status}\nclass: build\nsystem: Direct\npattern: edit\n---\n'
                        '- [x] Rejected\n\nModified candidate: build -> Other > alternative\n')
                    expected = set() if status == 'pending' else {('build', 'Direct', 'edit')}
                    self.assertEqual(cli.actioned_tuples(), expected)

    def test_chat_or_checkbox_is_not_a_persisted_decision(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cli, 'PROPOSALS_DIR', Path(directory)):
            (Path(directory) / 'candidate.md').write_text(
                '---\nclass: build\nsystem: Direct\npattern: edit\n---\n'
                '- [x] Rejected\nUser said no.\n')
            self.assertEqual(cli.actioned_tuples(), set())


if __name__ == '__main__':
    unittest.main()

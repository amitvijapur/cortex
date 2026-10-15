"""Synthetic Claude evidence regressions, with no external state or processes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import derive_outcomes as D
import score_adherence as S


LOG = "python3 /fixture/bin/cortex log-line 'Direct > fix @ L2' 'fixture task'"
HINT = "python3 /fixture/bin/cortex hint 'fixture task' --class debug"


class ClaudeCommandEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(patch('subprocess.run', side_effect=AssertionError('unexpected process')))

    def session(self, command, *, result=True, error=False, code=0, content='ok'):
        rows = []
        for i, cmd in enumerate((command, LOG)):
            stamp = f'2026-10-01T10:0{i}:00Z'
            rows.append({'type': 'assistant', 'sessionId': 'fixture', 'uuid': f'call-{i}',
                'timestamp': stamp, 'message': {'content': [{'type': 'tool_use',
                    'id': f'tool-{i}', 'name': 'Bash', 'input': {'command': cmd}}]}})
            if result or i == 1:
                rows.append({'type': 'user', 'sessionId': 'fixture', 'uuid': f'result-{i}',
                    'timestamp': stamp, 'toolUseResult': {'exitCode': code if i == 0 else 0},
                    'message': {'content': [{'type': 'tool_result', 'tool_use_id': f'tool-{i}',
                        'is_error': error if i == 0 else False, 'content': content if i == 0 else 'ok'}]}})
        path = self.root / 'fixture.jsonl'
        path.write_text('\n'.join(map(json.dumps, rows)))
        return {'fixture': {'host': 'claude', 'events': list(D.read_transcript(path)), 'files': []}}

    def hint(self, sessions):
        index, times = D.build_anchor_index(sessions)
        row = {'task': 'fixture task', 'task_hash': D.task_hash('fixture task'),
               'ts': '2026-10-01T10:01:00Z', 'session_ref': 'fixture'}
        return S.hint_check(row, D.attribute(row, index, times, sessions), sessions, times)

    def test_echo_quoted_commands_and_shell_code_are_not_invocations(self):
        for cmd in (f'echo "{LOG}"', f"printf '%s' \"{LOG}\"", repr(LOG),
                    f"python3 -c {LOG!r}", f'false && {LOG}; true',
                    f'cat <<EOF\n{LOG}\nEOF', f'{LOG} --help', f'exit 0 && {LOG}',
                    f'exec true && {LOG}'):
            with self.subTest(cmd=cmd):
                self.assertEqual(D.anchor_tasks(cmd), [])
        for cmd in (f'echo "{HINT}"', repr(HINT), f'false && {HINT}; true'):
            with self.subTest(cmd=cmd):
                self.assertFalse(self.hint(self.session(cmd))['ran'])

    def test_success_is_required_for_both_anchors_and_hints(self):
        for options in ({'result': False}, {'error': True}, {'code': 1},
                        {'code': True}, {'content': 'Exit code: 2'}):
            with self.subTest(options=options):
                sessions = self.session(LOG, **options)
                index, _ = D.build_anchor_index(sessions)
                self.assertEqual(len(index[D.task_hash('fixture task')]), 1)
                check = self.hint(self.session(HINT, **options))
                self.assertFalse(check['ran'])
                self.assertFalse(check['earlier_in_session'])

    def test_actual_success_and_literal_quoted_task_are_preserved(self):
        self.assertEqual(D.anchor_tasks(LOG), ['fixture task'])
        self.assertEqual(D.anchor_tasks('cortex log --task="fixture task"'), ['fixture task'])
        self.assertEqual(D.anchor_tasks(f'{HINT} && {LOG}'), ['fixture task'])
        self.assertEqual(D.anchor_tasks('cortex log --task one --task two'), [])
        check = self.hint(self.session(HINT))
        self.assertTrue(check['ran'])
        self.assertTrue(check['could_inform'])
        self.assertEqual(check['query_matched'], 'exact')
        sessions = self.session(f'{HINT} && {LOG}')
        index, _ = D.build_anchor_index(sessions)
        self.assertEqual(len(index[D.task_hash('fixture task')]), 2)

    def test_outcome_mentions_and_failures_do_not_become_ceremony(self):
        for cmd, options, expected in (
                ('echo "cortex outcome shipped"', {}, False),
                ('cortex outcome shipped', {'code': 1}, False),
                ('cortex outcome shipped', {}, True)):
            with self.subTest(cmd=cmd, options=options):
                sessions = self.session(cmd, **options)
                attribution = {'method': 'anchor-command', 'session': 'fixture',
                               'start': D.parse_ts('2026-10-01T09:59:00Z'),
                               'end': D.parse_ts('2026-10-01T10:00:30Z')}
                findings = D.signal_label_provenance({'outcome': 'shipped'}, sessions, attribution)
                self.assertEqual(bool(findings), expected)

    def test_late_completion_cannot_inform_route(self):
        sessions = self.session(HINT)
        sessions['fixture']['events'][0].completed_at = D.parse_ts('2026-10-01T10:02:00Z')
        self.assertFalse(self.hint(sessions)['ran'])

    def test_parallel_hint_with_shared_timestamp_cannot_inform_route(self):
        stamp = '2026-10-01T10:01:00Z'
        for completed in (stamp, '2026-10-01T10:02:00Z'):
            with self.subTest(completed=completed):
                rows = [{'type': 'assistant', 'sessionId': 'fixture', 'uuid': 'parallel',
                    'timestamp': stamp, 'message': {'content': [
                        {'type': 'tool_use', 'id': ident, 'name': 'Bash',
                         'input': {'command': cmd}} for ident, cmd in (('hint', HINT), ('log', LOG))]}}]
                for ident, end in (('log', stamp), ('hint', completed)):
                    rows.append({'type': 'user', 'sessionId': 'fixture', 'uuid': ident,
                        'timestamp': end, 'toolUseResult': {'exitCode': 0},
                        'message': {'content': [{'type': 'tool_result', 'tool_use_id': ident,
                            'is_error': False, 'content': 'ok'}]}})
                path = self.root / 'parallel.jsonl'
                path.write_text('\n'.join(map(json.dumps, rows)))
                sessions = {'fixture': {'host': 'claude', 'events': list(D.read_transcript(path))}}
                check = self.hint(sessions)
                self.assertFalse(check['ran'])
                self.assertFalse(check['could_inform'])
                self.assertFalse(check['earlier_in_session'])

    def test_same_shell_hint_ran_but_cannot_inform_its_declaration(self):
        for completed in ('2026-10-01T10:01:00Z', '2026-10-01T10:02:00Z'):
            with self.subTest(completed=completed):
                sessions = self.session(f'{HINT} && {LOG}')
                event = sessions['fixture']['events'][0]
                event.ts = D.parse_ts('2026-10-01T10:01:00Z')
                event.completed_at = D.parse_ts(completed)
                sessions['fixture']['events'] = [event]
                check = self.hint(sessions)
                self.assertTrue(check['ran'])
                self.assertFalse(check['could_inform'])
                self.assertEqual(check['query_matched'], 'exact')

    def test_hint_completing_at_declaration_is_not_earlier_evidence(self):
        sessions = self.session(HINT)
        sessions['fixture']['events'][0].completed_at = D.parse_ts('2026-10-01T10:01:00Z')
        check = self.hint(sessions)
        self.assertFalse(check['ran'])
        self.assertFalse(check['could_inform'])

    def test_parallel_chain_declaring_another_route_does_not_count(self):
        sessions = self.session(f"{HINT} && cortex log --task other")
        event = sessions['fixture']['events'][0]
        event.ts = D.parse_ts('2026-10-01T10:01:00Z')
        event.completed_at = D.parse_ts('2026-10-01T10:02:00Z')
        check = self.hint(sessions)
        self.assertFalse(check['ran'])
        self.assertFalse(check['could_inform'])

    def test_outcome_checks_parse_the_verb_not_quoted_arguments(self):
        attribution = {'method': 'anchor-command', 'session': 'fixture',
                       'start': D.parse_ts('2026-10-01T09:59:30Z'),
                       'end': D.parse_ts('2026-10-01T10:01:00Z')}
        for verdict in ('shipped', 'partial', 'abandoned', 'corrected'):
            for batched in (False, True):
                for actual in (False, True):
                    with self.subTest(verdict=verdict, batched=batched, actual=actual):
                        cmd = (f'cortex outcome {verdict}' if actual else
                               f'cortex hint "document cortex outcome {verdict}" --class research')
                        if batched:
                            cmd += f' && {LOG}'
                        sessions = self.session(cmd)
                        findings = D.signal_label_provenance({'outcome': verdict}, sessions, attribution)
                        self.assertEqual(bool(findings), actual)
                        self.assertEqual(S.outcome_command_lag(sessions, attribution),
                                         0.5 if actual else None)
                        provenance, _ = S.outcome_provenance({'outcome': verdict}, sessions, attribution)
                        self.assertEqual(provenance, 'ceremony' if actual else 'observation')
                        if actual:
                            self.assertEqual(findings[0]['signal'], 'outcome_batched_with_next_route'
                                             if batched else 'outcome_stamped_at_declaration')
                            self.assertIn(f'cortex outcome {verdict}', findings[0]['evidence'])

    def test_full_transcript_orphan_revert_is_still_reported(self):
        sessions = self.session('git revert deadbeef')
        _, times = D.build_anchor_index(sessions)
        findings = D.orphan_evidence(sessions, times, [])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['signal'], 'work_reverted')
        self.assertEqual(findings[0]['confidence'], 'high')

    def test_unattributed_outcomes_are_unknown_not_absent(self):
        for attribution in ({'method': 'none'}, {'method': 'session_ref'}, {'method': 'ambiguous'}):
            self.assertEqual(S.outcome_provenance({'outcome': 'shipped'}, {}, attribution)[0], 'unknown')
        records, _, _, _ = S.build([{'outcome': 'shipped'}], {}, {}, {})
        self.assertEqual(records[0]['outcome_provenance'], 'unknown')
        self.assertIsNone(records[0]['hint'])
        self.assertEqual(S.outcome_provenance({}, {}, {})[0], 'none')
        self.assertEqual(S.outcome_provenance({'outcome': 'shipped', 'outcome_backfilled': True}, {}, {})[0], 'backfilled')


if __name__ == '__main__':
    unittest.main()

"""Offline Codex ownership and report regressions. No private fixture contents."""
import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import codex_transcripts as C
import derive_outcomes as D
import score_adherence as S

BASE = 1790683200000
TASK = 'Repair fixture cache'
SID = 'thread-a'


def meta(sid=SID, created=BASE, **extra):
    return {'type': 'session_meta', 'payload': {'id': sid,
        'timestamp': C.timestamp(created).isoformat(), 'source': 'vscode', **extra}}


def command(cmd, ident='call-a', owner=SID, at=BASE + 10000, **extra):
    item = {'type': 'CommandExecution', 'id': ident,
            'command': ['/bin/zsh', '-lc', cmd], 'cwd': '/fixture',
            'status': 'completed', 'exit_code': 0, **extra}
    return {'type': 'event_msg', 'payload': {'type': 'item_completed',
        'thread_id': owner, 'turn_id': 'turn-a', 'item': item,
        'started_at_ms': at, 'completed_at_ms': at + 50}}


def route(**extra):
    return {'event': 'route', 'event_id': 'route-a', 'host': 'codex',
        'session_ref': SID, 'task': TASK, 'task_hash': D.task_hash(TASK),
        'ts': C.timestamp(BASE + 10020).isoformat(), 'class': 'build',
        'system': 'Direct', 'pattern': 'fix', 'tier': 'L2', **extra}


LOG = f"python3 /fixture/bin/cortex log --task '{TASK}' --class build --system Direct --pattern fix --tier L2"


class CodexAttribution(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.codex = self.root / 'sessions'
        self.codex.mkdir()

    def write(self, rows, name='rollout.jsonl'):
        path = self.codex / name
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return path

    def load(self):
        return D.load_evidence_sessions(self.root / 'claude', self.codex)

    def attr(self, sessions, row=None):
        index, times = D.build_anchor_index(sessions)
        return D.attribute(row or route(), index, times, sessions)

    def test_exact_owner_joins_and_keeps_outcome_unknown(self):
        self.write([meta(), command(LOG)])
        sessions, diagnostics = self.load()
        attr = self.attr(sessions)
        self.assertEqual(attr['session'], 'codex:' + SID)
        self.assertEqual(attr['evidence_host'], 'codex')
        self.assertEqual(diagnostics['codex']['accepted_commands'], 1)
        index, times = D.build_anchor_index(sessions)
        record = D.derive(route(), sessions, index, times, [route()], False)
        self.assertEqual(record['derived_state'], 'unknown')
        self.assertEqual(record['signals'], [])
        self.assertIsNone(record['effort'])

    def test_foreign_fork_history_and_rethreaded_old_history_excluded(self):
        self.write([meta('child', created=BASE + 20000),
            command(LOG), command(LOG, 'rethreaded', owner='child')])
        sessions, diag = self.load()
        self.assertEqual(D.build_anchor_index(sessions)[0], {})
        self.assertEqual(diag['codex']['foreign_owner_items'], 1)
        self.assertEqual(diag['codex']['unowned_or_precreation_commands'], 1)
        self.write([meta('child', created=BASE + 20000, forked_from_id=SID),
            command(LOG, owner='child', at=BASE + 30000)], 'child-new.jsonl')
        sessions, _ = self.load()
        self.assertEqual(sessions, {})

    def test_subagent_and_guardian_not_human_sessions(self):
        for source in ({'subagent': {'other': 'guardian'}}, {'subagent': {'thread_spawn': {'parent_thread_id': 'p'}}}):
            self.write([meta(source=source), command(LOG)])
            sessions, _ = self.load()
            self.assertEqual(sessions, {})
        self.write([meta(parent_thread_id='parent'), command(LOG)])
        self.assertEqual(self.load()[0], {})

    def test_neither_response_items_nor_compaction_are_execution_evidence(self):
        self.write([meta(), {'type': 'response_item', 'payload': {'type': 'function_call',
            'name': 'exec_command', 'arguments': json.dumps({'cmd': LOG})}},
            {'type': 'compacted', 'payload': {'replacement_history': [command(LOG)]}}])
        self.assertEqual(D.build_anchor_index(self.load()[0])[0], {})

    def test_echo_code_and_compound_commands_not_anchors(self):
        self.assertIsNotNone(C.cortex_command(['/bin/zsh', '-lc',
            "cortex log-line 'Direct > fix @ L2' 'Fixture task'"]))
        for cmd in ('echo "cortex log --task fake"', LOG + '; echo ok',
                    'python3 -c "print(\'cortex log --task fake\')"',
                    "printf '%s' 'cortex log --task fake'", LOG + '\ntrue',
                    LOG + ' || true', '$(echo cortex) log --task fake'):
            with self.subTest(cmd=cmd):
                self.assertIsNone(C.cortex_command(['/bin/zsh', '-lc', cmd]))

    def test_failed_or_missing_timing_is_unknown(self):
        cases = [command(LOG, status='failed', exit_code=1), command(LOG, exit_code=True),
                 command(LOG, status='inProgress')]
        untimed = command(LOG)
        untimed['payload'].pop('started_at_ms')
        cases.append(untimed)
        self.write([meta(), *cases])
        self.assertEqual(D.build_anchor_index(self.load()[0])[0], {})

    def test_help_only_commands_not_evidence(self):
        for cmd in (LOG+' --help', LOG+' -h', LOG+' --he', LOG+' --h',
                    'cortex hint fixture --hel'):
            self.assertIsNone(C.cortex_command(['/bin/zsh', '-lc', cmd]))

    def test_repeated_tasks_and_shell_expansions_cannot_change_identity(self):
        for cmd in ('cortex log --task first --task second',
                    'cortex log --task=first --task second',
                    'cortex log --task first --ta second',
                    'cortex log --task first --ta=second'):
            self.assertIsNone(C.command_task(cmd, 'log'))
        self.assertIsNone(C.command_task("cortex log-line --tier-reason reason 'Direct > fix @ L2' actual", 'log-line'))
        for text in ('actual#suffix', 'actual*', 'actual?', '{first,second}', '[ab]'):
            self.assertIsNone(C.cortex_command(['/bin/zsh', '-lc', 'cortex log --task '+text]))

    def test_overlapping_hint_finishes_after_route_start_is_unknown(self):
        log = command(LOG)
        log['payload']['completed_at_ms'] = BASE + 20000
        self.write([meta(), command('cortex hint fixture', ident='hint', at=BASE+15000), log])
        sessions, _ = self.load()
        index, times = D.build_anchor_index(sessions)
        attr = self.attr(sessions)
        self.assertIsNone(S.codex_command_evidence(attr, sessions, times)['hint_observed'])

    def test_quoted_cortex_prose_never_becomes_nested_anchor_or_hint(self):
        self.write([meta(), command('cortex hint "cortex log --task fake"'),
            command("cortex log --task 'cortex hint fake'", ident='nested')])
        sessions, _ = self.load()
        index, _ = D.build_anchor_index(sessions)
        self.assertNotIn(D.task_hash('fake'), index)
        self.assertIn(D.task_hash('cortex hint fake'), index)
        self.assertIsNone(C.command_task("cortex log --task 'cortex hint fake'", 'hint'))

    def test_duplicate_copies_deduplicate_and_conflicts_remove_evidence(self):
        rows = [meta(), command(LOG)]
        self.write(rows)
        self.write(rows, 'copy.jsonl')
        sessions, _ = self.load()
        self.assertEqual(len(sessions['codex:' + SID]['events']), 1)
        changed = copy.deepcopy(rows)
        changed[1]['payload']['item']['cwd'] = '/other'
        self.write(changed, 'conflict.jsonl')
        self.assertEqual(D.build_anchor_index(self.load()[0])[0], {})

    def test_conflicting_failed_duplicate_invalidates_success(self):
        self.write([meta(), command(LOG)])
        self.write([meta(), command(LOG, status='failed', exit_code=1)], 'failed-copy.jsonl')
        self.assertEqual(D.build_anchor_index(self.load()[0])[0], {})

    def test_conflicting_item_type_invalidates_success(self):
        changed = command(LOG)
        changed['payload']['item']['type'] = 'AgentMessage'
        self.write([meta(), command(LOG), changed])
        self.assertEqual(D.build_anchor_index(self.load()[0])[0], {})

    def test_metadata_conflicts_and_malformed_tail(self):
        path = self.write([meta(), command(LOG)])
        with path.open('a') as stream:
            stream.write('{truncated')
        self.assertEqual(self.attr(self.load()[0])['method'], 'anchor-command')
        self.write([meta(created=BASE-1000), command(LOG)], 'conflict.jsonl')
        self.assertEqual(self.load()[0], {})

    def test_exact_host_session_required_no_legacy_ppid_guess(self):
        self.write([meta(), command(LOG)])
        sessions, _ = self.load()
        for overrides in ({'host': 'claude'}, {'session_ref': 'other'},
                          {'session_ref': 'ppid_123'}, {'session_ref': None}):
            self.assertEqual(self.attr(sessions, route(**overrides))['method'], 'none')
        self.assertEqual(self.attr(sessions, route(host='unknown'))['method'], 'anchor-command')

    def test_host_collisions_are_disjoint_or_ambiguous_not_overwritten(self):
        self.write([meta(), command(LOG)])
        sessions, _ = self.load()
        event = D.Event(C.timestamp(BASE+10050), 'tool_use', SID, 'claude-event', '/fixture',
                        tool='Bash', cmd=LOG, completed_at=C.timestamp(BASE+10050))
        sessions[SID] = {'host': 'claude', 'events': [event], 'files': []}
        self.assertEqual(self.attr(sessions)['session'], 'codex:' + SID)
        self.assertEqual(self.attr(sessions, route(host='claude'))['session'], SID)
        self.assertEqual(self.attr(sessions, route(host='unknown'))['method'], 'ambiguous')

    def test_hint_positive_only_excluded_from_adherence_and_session_band(self):
        self.write([meta(), command(f"cortex hint '{TASK}'", ident='hint', at=BASE+5000), command(LOG)])
        sessions, _ = self.load()
        index, times = D.build_anchor_index(sessions)
        records, session_records, metrics, _ = S.build([route()], sessions, index, times)
        self.assertIsNone(records[0]['hint'])
        self.assertTrue(records[0]['codex_command_evidence']['hint_observed'])
        self.assertIsNotNone(session_records[0]['excluded'])
        self.assertEqual(S.ghost_declarations(sessions, index, []), [])
        self.assertIsNone(next(m['value'] for m in metrics if m['id']=='hint_before_route'))
        self.assertIsNone(next(m['value'] for m in metrics if m['id']=='outcome_is_observation'))

    def test_reports_opt_in_same_coverage_no_evidence_mutation(self):
        transcript = self.write([meta(), command(LOG)])
        log = self.root / 'log.jsonl'
        log.write_text(json.dumps(route())+'\n')
        original = (transcript.read_bytes(), log.read_bytes())
        headers=[]
        for module in (D, S):
            out=self.root/(module.__name__+'.jsonl')
            args=['--log',str(log),'--projects',str(self.root/'missing'),
                  '--codex-sessions',str(self.codex),'--out',str(out)]
            if module is D:args.append('--no-git')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(args),0)
            headers.append(json.loads(out.read_text().splitlines()[0])['evidence_coverage'])
            before=out.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(args+['--dry-run']),0)
            self.assertEqual(out.read_bytes(),before)
        self.assertEqual(headers[0],headers[1])
        self.assertEqual(headers[0]['by_host_period'][0]['anchor_attributed'],1)
        self.assertEqual((transcript.read_bytes(),log.read_bytes()),original)
        sessions, diag=D.load_evidence_sessions(self.root/'missing')
        self.assertEqual(sessions,{})
        self.assertEqual(diag['codex']['status'],'not_requested')


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Isolated regression tests; never read or write the real catalogue."""
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from validate_frontend_library import ValidationError, load_catalogue, validate
from build_frontend_library import build, render_references, render_site


def resource(**changes):
    record = dict(id='example-tool', title='Example tool', kind='resource',
                  category='Unrestricted category', url='https://example.com/tool',
                  purpose='A useful tool', tags=['design'], status='reference',
                  added='2026-09-13', last_checked=None, notes='', used_in=[])
    record.update(changes)
    return record


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.nodes = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


class ValidationTests(unittest.TestCase):
    def test_valid_resource_and_book_and_free_category(self):
        book = resource(id='example-book', kind='book', last_checked='2024-02-29')
        del book['url']
        self.assertEqual(validate([resource(), book]), [resource(), book])

    def test_bad_shapes_and_fields(self):
        for records in ({}, None, 'data', [None], [3], [[]]):
            with self.subTest(records=records), self.assertRaises(ValidationError):
                validate(records)
        for field in resource():
            record = resource()
            del record[field]
            with self.subTest(missing=field), self.assertRaises(ValidationError):
                validate([record])
        with self.assertRaises(ValidationError):
            validate([resource(unexpected='value')])

    def test_types_and_enums(self):
        invalid = {'id': ['UPPER', 'with space', '../escape', 7],
                   'title': [False, [], ' '], 'kind': ['link', 1],
                   'category': ['', {}], 'purpose': [None], 'notes': [False],
                   'tags': ['string', [7], ['']], 'used_in': [None, [{}]],
                   'status': ['new', []], 'url': [None, 12]}
        for key, values in invalid.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                    validate([resource(**{key: value})])
        with self.assertRaises(ValidationError):
            validate([resource(kind='book')])

    def test_dates(self):
        for field in ('added', 'last_checked'):
            for value in ('2026-02-30', '2025-02-29', '2026-9-13', '20260913',
                          '2026-09-13T12:00:00Z', '0000-01-01', 12, True):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    validate([resource(**{field: value})])
        with self.assertRaises(ValidationError):
            validate([resource(added=None)])

    def test_duplicates(self):
        with self.assertRaisesRegex(ValidationError, 'duplicate id'):
            validate([resource(), resource(url='https://other.example.com')])
        for url in ('HTTPS://EXAMPLE.COM:443/tool/', 'https://example.com/tool#section',
                    'https://example.com/%74ool', 'https://example.com./tool'):
            with self.subTest(url=url), self.assertRaisesRegex(ValidationError, 'duplicate normalized URL'):
                validate([resource(), resource(id='second', url=url)])

    def test_unsafe_urls(self):
        for url in ('javascript:alert(1)', 'data:text/html,hello', 'file:///tmp/a',
                    '//example.com', 'https://user:secret@example.com',
                    'https://@example.com', 'https://localhost/test',
                    'http://127.0.0.1', 'http://10.0.0.1', 'http://[::1]',
                    'https://host.internal', 'https://example.com:bad',
                    'https://example.com/\nfoo', 'https://example.com/%0Afoo',
                    'https://example.com\\@evil.com', 'https://[bad'):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                validate([resource(url=url)])

    def test_private_paths_in_all_public_text(self):
        for value in ('/Users/amit/private', 'Saved at /tmp/private', '~/private',
                      'C:\\Users\\amit', '\\\\server\\private', 'file:///secret',
                      '%2FUsers%2Famit', 'path="/home/amit"'):
            for field in ('title', 'purpose', 'notes', 'category', 'tags', 'used_in'):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    validate([resource(**{field: [value] if field in ('tags', 'used_in') else value})])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'frontend/resources.json'
        self.source.parent.mkdir()
        self.write([resource()])

    def write(self, records):
        self.source.write_text(json.dumps(records), encoding='utf-8')

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def cli(self, script, *args):
        return subprocess.run([sys.executable, '-B', str(SCRIPTS / script),
                               '--root', str(self.root), *args], text=True, capture_output=True)

    def test_build_and_check_cli(self):
        self.assertEqual(self.cli('validate_frontend_library.py').returncode, 0)
        self.assertEqual(self.cli('build_frontend_library.py').returncode, 0)
        before = self.snapshot()
        result = self.cli('build_frontend_library.py', '--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertIn('frontend/site/index.html', before)
        self.assertIn('frontend/REFERENCES.md', before)

    def test_missing_and_modified_drift_are_read_only(self):
        before = self.snapshot()
        self.assertNotEqual(self.cli('build_frontend_library.py', '--check').returncode, 0)
        self.assertEqual(before, self.snapshot())
        build(self.root)
        for relative in ('frontend/site/index.html', 'frontend/REFERENCES.md'):
            with self.subTest(relative=relative):
                path = self.root / relative
                path.write_text('manual edit', encoding='utf-8')
                before = self.snapshot()
                result = self.cli('build_frontend_library.py', '--check')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(relative, result.stderr)
                self.assertEqual(before, self.snapshot())
                build(self.root)

    def test_invalid_data_never_writes_outputs(self):
        for existing in (False, True):
            if existing:
                self.write([resource()])
                build(self.root)
            self.write([resource(), resource(id='second', url='javascript:alert(1)')])
            before = self.snapshot()
            for args in ((), ('--check',)):
                result = self.cli('build_frontend_library.py', *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Build failed:', result.stderr)
                self.assertEqual(before, self.snapshot())

    def test_bad_json_and_duplicate_keys(self):
        for raw in ('[', '[{"id":"first","id":"second"}]'):
            self.source.write_text(raw, encoding='utf-8')
            before = self.snapshot()
            with self.assertRaises(ValidationError):
                load_catalogue(self.root)
            self.assertNotEqual(self.cli('validate_frontend_library.py').returncode, 0)
            self.assertNotEqual(self.cli('build_frontend_library.py').returncode, 0)
            self.assertEqual(before, self.snapshot())

    def test_determinism_independent_of_input_order(self):
        records = [resource(), resource(id='second', title='Another tool', url='https://other.example.com')]
        self.write(records)
        build(self.root)
        first = {key: value for key, value in self.snapshot().items() if key != 'frontend/resources.json'}
        self.write(list(reversed(records)))
        build(self.root)
        second = {key: value for key, value in self.snapshot().items() if key != 'frontend/resources.json'}
        self.assertEqual(first, second)

    def test_safety_escaping_and_no_js_content(self):
        payload = '<img src=x onerror=alert(1)> & "quoted"'
        record = resource(title=payload, purpose=payload, notes=payload,
                          category=payload, tags=[payload], used_in=[payload],
                          url='https://example.com/?q="<tag>&x=1')
        validate([record])
        page = render_site([record])
        parsed = Document(page)
        self.assertFalse(any(tag == 'img' for tag, _ in parsed.nodes))
        self.assertEqual(sum(tag == 'script' for tag, _ in parsed.nodes), 1)
        self.assertIn('&lt;img', page)
        self.assertIn('href="https://example.com/?q=&quot;&lt;tag&gt;&amp;x=1"', page)
        entries = [attrs for _, attrs in parsed.nodes if attrs.get('class') == 'entry']
        self.assertEqual(len(entries), 1)
        self.assertNotIn('hidden', entries[0])
        self.assertIn('aria-live="polite"', page)
        self.assertIn('No matching entries', page)
        self.assertIn('summary:focus-visible', page)
        self.assertTrue(any(tag == 'a' and attrs.get('href') == '#entries' for tag, attrs in parsed.nodes))
        self.assertTrue(any(attrs.get('id') == 'entries' and attrs.get('tabindex') == '-1' for _, attrs in parsed.nodes))
        for filename in ('PLAYBOOK.md', 'PROMPT-PACK.md', 'CHECKLISTS.md', 'SKILL-MAP.md'):
            self.assertIn(f'href="../guidance/{filename}"', page)
        self.assertIn('Original guide · 5 Sep</a>', page)
        for identifier in ('search', 'category', 'kind', 'status'):
            self.assertTrue(any(tag == 'label' and attrs.get('for') == identifier for tag, attrs in parsed.nodes))
        self.assertNotIn('fetch(', page)
        self.assertFalse(any(tag in ('link', 'iframe') or tag == 'script' and 'src' in attrs
                             for tag, attrs in parsed.nodes))
        references = render_references([record])
        self.assertNotIn('<img', references)
        self.assertIn('%22%3Ctag%3E', references)

    def test_empty_catalogue(self):
        self.write([])
        self.assertEqual(build(self.root), 0)
        self.assertIn('0 of 0 entries', (self.root / 'frontend/site/index.html').read_text())


if __name__ == '__main__':
    unittest.main()

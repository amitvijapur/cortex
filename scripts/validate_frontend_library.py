#!/usr/bin/env python3
"""Validate the public frontend catalogue using only the Python standard library."""
import argparse
from datetime import date
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {'id', 'title', 'kind', 'category', 'url', 'purpose', 'tags', 'status',
          'added', 'last_checked', 'notes', 'used_in'}
REQUIRED = FIELDS - {'url'}
STATUSES = ('reference', 'tested', 'watch', 'archived')


class ValidationError(ValueError):
    """Catalogue cannot safely be published."""


def public_text(value, label):
    if not isinstance(value, str):
        raise ValidationError(f'{label}: expected a string')
    decoded = unquote(value)
    if any(ord(c) < 32 and c not in '\n\t' for c in decoded):
        raise ValidationError(f'{label}: control characters are not allowed')
    # Public prose may contain web URLs, but never local filesystem locations.
    if re.search(r'(?i)(file:|(?:^|[\s"\x27(<=>])(?:/|~[/\\]|[a-z]:[/\\]|\\\\))', decoded):
        raise ValidationError(f'{label}: absolute or private paths are not public data')
    return value


def normalized_url(value):
    public_text(value, 'url')
    if re.search(r'\s|\\', value) or re.search(r'%0[0-9a-f]|%1[0-9a-f]|%7f', value, re.I):
        raise ValidationError('url: whitespace, controls and backslashes are not allowed')
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {'https', 'http'} or not parts.hostname:
            raise ValueError('expected an absolute HTTP(S) URL')
        if parts.username is not None or parts.password is not None:
            raise ValueError('credentials are forbidden')
        host = parts.hostname.lower().rstrip('.')
        if '%' in host or not re.fullmatch(r'[a-z0-9.:-]+', host):
            raise ValueError('invalid public host')
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '.' not in host and ':' not in host:
            raise ValueError('private hosts are forbidden')
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError('private addresses are forbidden')
        port = parts.port
        scheme = parts.scheme.lower()
        authority = f'[{host}]' if ':' in host else host
        if port is not None and port != (443 if scheme == 'https' else 80):
            authority += f':{port}'
        # Fragments do not identify a separate resource; trailing slash is cosmetic.
        path = re.sub(r'%([0-9a-fA-F]{2})', lambda m: chr(int(m[1], 16))
                      if chr(int(m[1], 16)) in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
                      else '%' + m[1].upper(), parts.path).rstrip('/')
        return urlunsplit((scheme, authority, path, parts.query, ''))
    except ValueError as exc:
        raise ValidationError(f'url: {exc}') from exc


def validate(records):
    if not isinstance(records, list):
        raise ValidationError('catalogue: expected an array')
    ids, urls = set(), set()
    for i, record in enumerate(records):
        label = f'entry {i + 1}'
        if not isinstance(record, dict):
            raise ValidationError(f'{label}: expected an object')
        missing, extra = REQUIRED - record.keys(), record.keys() - FIELDS
        if missing or extra:
            raise ValidationError(f'{label}: missing fields {sorted(missing)}; unknown fields {sorted(extra)}')
        for field in ('id', 'title', 'kind', 'category', 'purpose', 'status', 'added', 'notes'):
            public_text(record[field], f'{label}.{field}')
            if field != 'notes' and not record[field].strip():
                raise ValidationError(f'{label}.{field}: must not be empty')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', record['id']):
            raise ValidationError(f'{label}.id: expected a lowercase slug')
        if record['id'] in ids:
            raise ValidationError(f'{label}: duplicate id {record["id"]}')
        ids.add(record['id'])
        if record['kind'] not in ('resource', 'book') or record['status'] not in STATUSES:
            raise ValidationError(f'{label}: invalid kind or status')
        for field in ('tags', 'used_in'):
            if not isinstance(record[field], list):
                raise ValidationError(f'{label}.{field}: expected a list')
            for item in record[field]:
                if not public_text(item, f'{label}.{field}').strip():
                    raise ValidationError(f'{label}.{field}: empty strings are forbidden')
        for field in ('added', 'last_checked'):
            value = record[field]
            if field == 'last_checked' and value is None:
                continue
            if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValidationError(f'{label}.{field}: expected ISO date YYYY-MM-DD')
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValidationError(f'{label}.{field}: invalid date') from exc
        if record['kind'] == 'book':
            if 'url' in record:
                raise ValidationError(f'{label}: books must omit url')
        else:
            if 'url' not in record:
                raise ValidationError(f'{label}: resource requires url')
            url = normalized_url(record['url'])
            if url in urls:
                raise ValidationError(f'{label}: duplicate normalized URL {url}')
            urls.add(url)
    return records


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f'duplicate JSON field: {key}')
        result[key] = value
    return result


def load_catalogue(root=ROOT):
    try:
        text = (Path(root) / 'frontend/resources.json').read_text(encoding='utf-8')
        return validate(json.loads(text, object_pairs_hook=unique_object))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='repository root')
    args = parser.parse_args(argv)
    try:
        records = load_catalogue(args.root)
    except ValidationError as exc:
        print(f'Invalid catalogue: {exc}', file=sys.stderr)
        return 1
    print(f'Valid catalogue: {len(records)} entries')
    return 0


if __name__ == '__main__':
    sys.exit(main())

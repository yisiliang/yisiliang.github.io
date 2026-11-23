#!/usr/bin/env python3
"""Build the static site in docs/roots/.

Word lists and Chinese word glosses come from ECDICT (MIT).
Roots, affixes, breakdowns and etymology notes come from the vendored
anki-word-roots tables (CC BY-SA 4.0). Chinese beside a root or affix is a
translation of that table's English gloss, stored in tools/roots/zh/.

Wordiyo's database is not an input. See vendor/SOURCE.txt.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VENDOR = HERE / 'vendor' / 'anki-word-roots'
ZH = HERE / 'zh'
OUT = ROOT / 'docs' / 'roots'
ECDICT_COMMIT = '39cfb9672c0906b63569e0453c2e6abfb9ab182a'
ANKI_COMMIT = 'd5f7bd1ab23a29832e4b7ee8de558177229b5e2e'
EXAM = ('cet4', 'cet6', 'ielts', 'toefl', 'gre', 'zk')
EXAM_SET = set(EXAM)
LIST_META = {
    'cet4': ('CET-4', '大学英语四级'),
    'cet6': ('CET-6', '大学英语六级'),
    'ielts': ('IELTS', '雅思'),
    'toefl': ('TOEFL', '托福'),
    'gre': ('GRE', 'GRE'),
    'zk': ('中考', '初中学业水平'),
}
POS_RE = re.compile(
    r'^(n|vt|vi|v|adj|adv|prep|conj|pron|num|int|aux|art|a)\.\s*', re.I)
SHORT_LABEL_RE = re.compile(r'\[[^\[\]\n]{1,8}\]')
HAN_RE = re.compile(r'[\u4e00-\u9fff]')
TAG_RE = re.compile(r'<[^>]+>')
POS_LABEL = {
    'n': '名', 'v': '动', 'vt': '动', 'vi': '动', 'a': '形', 'adj': '形',
    'adv': '副', 'prep': '介', 'conj': '连', 'pron': '代', 'num': '数',
    'int': '叹', 'aux': '助', 'art': '冠',
}


def load_tsv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        key, value = line.split('\t', 1)
        if key in data:
            raise SystemExit(f'duplicate key {key!r} in {path.name}')
        if not value.strip():
            raise SystemExit(f'empty translation for {key!r}')
        data[key] = value
    return data


def gloss_zh(english: str, meanings: dict[str, str], glosses: dict[str, str]) -> str:
    if english in glosses:
        return glosses[english]
    if english in meanings:
        return meanings[english]
    raise KeyError(english)


def clean_translation(text: str) -> tuple[str, list[str]]:
    """Keep up to four Chinese senses copied from an ECDICT translation field."""
    senses: list[str] = []
    network: list[str] = []
    poses: list[str] = []
    text = (text or '').replace('\\n', '\n').replace('\\r', '')
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        from_web = line.startswith('[网络]')
        match = POS_RE.match(line)
        if match:
            label = POS_LABEL.get(match.group(1).lower())
            if label and label not in poses:
                poses.append(label)
            line = line[match.end():]
        line = SHORT_LABEL_RE.sub('', line).strip()
        if line.startswith('[') and HAN_RE.search(line):
            line = line[1:]
        if line.endswith(']') and line.count('[') < line.count(']'):
            line = line[:-1]
        line = line.strip(' ,，;；[]')
        if not line or not HAN_RE.search(line):
            continue
        parts = [part.strip() for part in re.split(r'[,，;；、]', line) if part.strip()]
        (network if from_web else senses).extend(parts)
    chosen: list[str] = []
    for part in senses or network:
        if part not in chosen:
            chosen.append(part)
        if len(chosen) == 4:
            break
    return '；'.join(chosen), poses


def norm_ipa(value: str) -> str:
    if not value:
        return ''
    value = value.split(',')[0].split(';')[0].strip()
    return value.replace('ә', 'ə')


def parse_marked(field: str) -> list[tuple[str, int, int]]:
    found = []
    for part in re.split(r';\s*', (field or '').strip()):
        part = part.strip()
        if not part:
            continue
        start_b = part.find('[')
        end_b = part.find(']')
        if start_b < 0 or end_b < start_b:
            raise SystemExit(f'bracket missing in {part!r}')
        surface = part[:start_b] + part[start_b + 1:end_b] + part[end_b + 1:]
        found.append((surface, start_b, end_b - 1))
    return found


def parse_decode(parts: str) -> list[dict]:
    segments = []
    for part in parts.split(' + '):
        surface, rest = part.split('=', 1)
        if ':' in rest:
            morph_id, gloss = rest.split(':', 1)
        else:
            morph_id, gloss = rest, ''
        segments.append({'s': surface, 'id': morph_id, 'gloss': gloss})
    return segments


def ensure_ecdict() -> Path:
    candidates = []
    if os.environ.get('ECDICT_CSV'):
        candidates.append(Path(os.environ['ECDICT_CSV']))
    candidates.append(Path('/tmp/vocab-src/ecdict.csv'))
    candidates.append(HERE / '.cache' / 'ecdict.csv')
    for path in candidates:
        if path.is_file() and path.stat().st_size > 1_000_000:
            return path
    cache = HERE / '.cache' / 'ecdict.csv'
    cache.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://raw.githubusercontent.com/skywind3000/ECDICT/{ECDICT_COMMIT}/ecdict.csv'
    print('downloading', url)
    urllib.request.urlretrieve(url, cache)
    return cache


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def lookup_record(word: str, records: dict, alias: dict) -> dict | None:
    key = word.lower()
    direct = records.get(key)
    if direct and direct['zh']:
        return direct
    lemma = alias.get(key)
    if lemma:
        via = records.get(lemma)
        if via and via['zh']:
            return via
    return direct or (records.get(lemma) if lemma else None)


def build() -> None:
    meanings = load_tsv(ZH / 'meanings.tsv')
    glosses = load_tsv(ZH / 'glosses.tsv')
    literals = load_tsv(ZH / 'literals.tsv')
    story_zh = load_tsv(ZH / 'stories.tsv')
    morph_rows = read_csv(VENDOR / 'morphemes.csv')
    decode_rows = read_csv(VENDOR / 'decode.csv')
    story_rows = read_csv(VENDOR / 'stories.csv')
    if len(morph_rows) != 700:
        raise SystemExit(f'expected 700 morphemes, got {len(morph_rows)}')

    morphs = {}
    for index, row in enumerate(morph_rows):
        if row['meaning'] not in meanings:
            raise SystemExit(f'missing Chinese for meaning {row["meaning"]!r}')
        morphs[row['id']] = {
            'id': row['id'],
            'kind': row['kind'],
            'forms': row['forms'],
            'en': row['meaning'],
            'zh': meanings[row['meaning']],
            'lang': row['language'],
            'origin': row['origin'],
            'core': row['core'] == 'y',
            'med': row['medical'],
            'order': index,
            'source': row['source'],
        }

    stories = {}
    for row in story_rows:
        if row['id'] not in story_zh:
            raise SystemExit(f'missing story translation {row["id"]}')
        if row['id'] not in morphs:
            raise SystemExit(f'story for unknown morpheme {row["id"]}')
        stories[row['id']] = {
            'zh': story_zh[row['id']],
            'en': TAG_RE.sub('', row['story']),
            'source': row['source'],
        }

    # surface -> spans collected from example highlights
    hits: dict[str, dict] = {}

    def add_hit(surface: str, start: int, end: int, morph_id: str, bucket: str) -> None:
        key = surface.lower()
        slot = hits.get(key)
        if slot is None:
            slot = {'surface': surface, 'spans': [], 'order': []}
            hits[key] = slot
        slot['order'].append((bucket, morphs[morph_id]['order'], morph_id))
        slot['spans'].append((start, end, morph_id, surface[start:end]))

    for row in morph_rows:
        for bucket, field in (('front', row['front']), ('more', row['more'])):
            for surface, start, end in parse_marked(field):
                add_hit(surface, start, end, row['id'], bucket)

    decode_by_word = {}
    for row in decode_rows:
        if row['word'] not in literals:
            raise SystemExit(f'missing literal translation {row["word"]}')
        segments = parse_decode(row['parts'])
        built = ''.join(segment['s'] for segment in segments)
        if built.lower() != row['word'].lower():
            raise SystemExit(f'decode spelling mismatch {row["word"]} != {built}')
        for segment in segments:
            if segment['id'] and segment['id'] not in morphs:
                raise SystemExit(f'unknown morpheme {segment["id"]} in {row["word"]}')
            if segment['gloss']:
                gloss_zh(segment['gloss'], meanings, glosses)
        decode_by_word[row['word'].lower()] = {
            'surface': row['word'],
            'segments': segments,
            'literal_en': row['literal'],
            'literal_zh': literals[row['word']],
            'medical': row['medical'] == 'y',
        }
        key = row['word'].lower()
        if key not in hits:
            hits[key] = {'surface': row['word'], 'spans': [], 'order': []}
        for segment in segments:
            if segment['id']:
                hits[key]['order'].append(('decode', morphs[segment['id']]['order'], segment['id']))

    targets = set(hits)
    records: dict[str, dict] = {}
    alias: dict[str, str] = {}
    ecdict_path = ensure_ecdict()
    print('ECDICT', ecdict_path, ecdict_path.stat().st_size)

    def keep(row: dict) -> dict:
        chinese, poses = clean_translation(row.get('translation') or '')
        tags = [tag for tag in (row.get('tag') or '').split() if tag in EXAM_SET]
        frq_raw = row.get('frq') or ''
        return {
            'zh': chinese,
            'pos': poses,
            'tags': tags,
            'ipa': norm_ipa(row.get('phonetic') or ''),
            'frq': int(frq_raw) if frq_raw.isdigit() else 0,
        }

    with ecdict_path.open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            word = (row.get('word') or '').strip().lower()
            if not word:
                continue
            tags = [tag for tag in (row.get('tag') or '').split() if tag in EXAM_SET]
            linked = False
            for item in (row.get('exchange') or '').split('/'):
                if ':' not in item:
                    continue
                _kind, form = item.split(':', 1)
                form = form.strip().lower()
                if form in targets and form != word:
                    alias.setdefault(form, word)
                    linked = True
            if word not in targets and not tags and not linked:
                continue
            rec = keep(row)
            current = records.get(word)
            if current is None or (rec['zh'] and not current['zh']):
                records[word] = rec
            elif rec['zh'] and current['zh']:
                for tag in rec['tags']:
                    if tag not in current['tags']:
                        current['tags'].append(tag)
                if not current['ipa'] and rec['ipa']:
                    current['ipa'] = rec['ipa']
                if not current['pos'] and rec['pos']:
                    current['pos'] = rec['pos']
                if rec['frq'] and (not current['frq'] or rec['frq'] < current['frq']):
                    current['frq'] = rec['frq']

    def segments_for(key: str) -> tuple[list[dict], bool]:
        decoded = decode_by_word.get(key)
        if decoded:
            parts = []
            for segment in decoded['segments']:
                morph = morphs.get(segment['id'])
                english = segment['gloss'] or (morph['en'] if morph else '')
                if segment['gloss'] and segment['gloss'] in glosses:
                    chinese = glosses[segment['gloss']]
                elif morph:
                    # The morpheme's own Chinese stays with that entry. A short
                    # gloss such as "back" or "draw" can be another entry's
                    # whole meaning, so it is not looked up globally.
                    chinese = morph['zh']
                elif english:
                    chinese = gloss_zh(english, meanings, glosses)
                else:
                    chinese = ''
                parts.append({
                    's': segment['s'],
                    't': morph['kind'] if morph else 'other',
                    'id': segment['id'] or '',
                    'en': english,
                    'zh': chinese,
                })
            return parts, False
        slot = hits[key]
        surface = slot['surface']
        spans = []
        for start, end, morph_id, marked in slot['spans']:
            if surface[start:end].lower() != marked.lower():
                continue
            spans.append((start, end, morph_id))
        spans.sort()
        placed = []
        last = -1
        overlap = False
        for start, end, morph_id in spans:
            if start < last:
                overlap = True
                continue
            if any(start < prev_end and prev_start < end for prev_start, prev_end, _mid in placed):
                overlap = True
                continue
            placed.append((start, end, morph_id))
            last = end
        if overlap and not placed:
            return [], True
        parts = []
        cursor = 0
        partial = overlap
        for start, end, morph_id in placed:
            if start > cursor:
                parts.append({'s': surface[cursor:start], 't': 'other', 'id': '', 'en': '', 'zh': ''})
                partial = True
            morph = morphs[morph_id]
            parts.append({
                's': surface[start:end], 't': morph['kind'], 'id': morph_id,
                'en': morph['en'], 'zh': morph['zh'],
            })
            cursor = end
        if cursor < len(surface):
            parts.append({'s': surface[cursor:], 't': 'other', 'id': '', 'en': '', 'zh': ''})
            partial = True
        return parts, partial

    words: dict[str, dict] = {}
    members: dict[str, list[str]] = defaultdict(list)
    member_rank: dict[tuple[str, str], tuple] = {}

    def touch(morph_id: str, key: str, bucket: str, order: int) -> None:
        rank = (bucket != 'front', bucket != 'more', order)
        prev = member_rank.get((morph_id, key))
        if prev is None or rank < prev:
            member_rank[(morph_id, key)] = rank
        if key not in members[morph_id]:
            members[morph_id].append(key)

    for key, slot in hits.items():
        # Source order: front examples, then more, then decode-only.
        rank = min((item[0] != 'front', item[0] != 'more', item[1]) for item in slot['order'])
        rec = lookup_record(slot['surface'], records, alias) or {}
        parts, partial = segments_for(key)
        decoded = decode_by_word.get(key)
        known = []
        seen = set()
        for bucket, order, morph_id in sorted(slot['order'], key=lambda item: (item[1], item[0])):
            touch(morph_id, key, bucket, order)
            if morph_id in seen:
                continue
            seen.add(morph_id)
            morph = morphs[morph_id]
            known.append({'id': morph_id, 't': morph['kind'], 'zh': morph['zh'], 'en': morph['en'], 'forms': morph['forms']})
        words[key] = {
            'w': decoded['surface'] if decoded else slot['surface'],
            'ipa': rec.get('ipa') or '',
            'zh': rec.get('zh') or '',
            'pos': rec.get('pos') or [],
            'tags': rec.get('tags') or [],
            'parts': parts,
            'partial': partial,
            'literalEn': decoded['literal_en'] if decoded else '',
            'literalZh': decoded['literal_zh'] if decoded else '',
            'known': known,
            'rank': rank,
        }

    for morph_id, keys in members.items():
        keys.sort(key=lambda key: member_rank[(morph_id, key)] + (words[key]['w'].lower(),))

    data_dir = OUT / 'data'
    if data_dir.exists():
        shutil.rmtree(data_dir)
    (data_dir / 'm').mkdir(parents=True)
    (data_dir / 'lists').mkdir()

    catalog = []
    for morph in morphs.values():
        keys = members.get(morph['id'], [])
        detail = {
            'id': morph['id'],
            'kind': morph['kind'],
            'forms': morph['forms'],
            'en': morph['en'],
            'zh': morph['zh'],
            'lang': morph['lang'],
            'origin': morph['origin'],
            'core': morph['core'],
            'med': morph['med'],
            'story': stories.get(morph['id']),
            'words': [{k: v for k, v in words[key].items() if k != 'rank'} for key in keys],
        }
        (data_dir / 'm' / f'{morph["id"]}.json').write_text(
            json.dumps(detail, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        catalog.append({
            'id': morph['id'],
            'kind': morph['kind'],
            'forms': morph['forms'],
            'en': morph['en'],
            'zh': morph['zh'],
            'lang': morph['lang'],
            'origin': morph['origin'],
            'core': morph['core'],
            'med': morph['med'],
            'n': len(keys),
            'story': morph['id'] in stories,
            'order': morph['order'],
        })

    index = []
    missing = []
    with_zh = 0
    for key in sorted(words):
        word = words[key]
        if word['zh']:
            with_zh += 1
        else:
            missing.append(word['w'])
        index.append({
            'w': word['w'],
            'z': word['zh'],
            'm': [item['id'] for item in word['known']],
        })

    linked_ids = {word['w'].lower(): [item['id'] for item in word['known']] for word in words.values()}
    list_stats = {}
    for tag in EXAM:
        rows = []
        for word, rec in records.items():
            if tag not in rec['tags']:
                continue
            item = {
                'w': word,
                'z': rec['zh'],
                'p': rec['ipa'],
                'g': '/'.join(rec['pos']),
                't': rec['tags'],
            }
            if word in linked_ids:
                item['m'] = linked_ids[word]
            rows.append((rec['frq'] or 10**9, word, item))
        rows.sort()
        items = [item for _frq, _word, item in rows]
        covered = sum(1 for item in items if item['z'])
        linked = sum(1 for item in items if item.get('m'))
        code, label = LIST_META[tag]
        payload = {
            'tag': tag, 'code': code, 'label': label,
            'count': len(items), 'withZh': covered, 'linked': linked,
            'words': items,
        }
        (data_dir / 'lists' / f'{tag}.json').write_text(
            json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        list_stats[tag] = {'count': len(items), 'withZh': covered, 'linked': linked, 'code': code, 'label': label}

    kind_count = defaultdict(int)
    lang_count = defaultdict(int)
    for morph in morphs.values():
        kind_count[morph['kind']] += 1
        lang_count[morph['lang']] += 1
    stats = {
        'morphemes': len(morphs),
        'roots': kind_count['root'],
        'prefixes': kind_count['prefix'],
        'suffixes': kind_count['suffix'],
        'latin': lang_count['Latin'],
        'greek': lang_count['Greek'],
        'latinAndGreek': lang_count['Latin and Greek'],
        'core': sum(1 for morph in morphs.values() if morph['core']),
        'medical': sum(1 for morph in morphs.values() if morph['med'] == 'y'),
        'stories': len(stories),
        'decodeWords': len(decode_by_word),
        'memberWords': len(words),
        'memberWithZh': with_zh,
        'memberWithoutZh': len(missing),
        'missing': missing,
        'lists': list_stats,
        'ankiCommit': ANKI_COMMIT,
        'ecdictCommit': ECDICT_COMMIT,
    }
    catalog_payload = {'stats': stats, 'morphemes': catalog}
    (data_dir / 'catalog.json').write_text(
        json.dumps(catalog_payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (data_dir / 'words-index.json').write_text(
        json.dumps(index, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (OUT / 'coverage.json').write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps({k: v for k, v in stats.items() if k != 'missing'}, ensure_ascii=False, indent=2))
    print('missing sample', missing[:30])
    for sample in ('conduct', 'biology', 'incredible', 'return', 'photograph'):
        word = words.get(sample)
        if not word:
            print(sample, 'ABSENT')
            continue
        print(sample, word['zh'], [(p['s'], p['t'], p['zh']) for p in word['parts']], 'partial', word['partial'])


if __name__ == '__main__':
    build()

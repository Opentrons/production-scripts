"""Local storage, immutable read snapshots and traceable temporary-action evidence."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .normalization import (
    SECOND_PATTERN, canonical_product, clean, duration_values, normalize_action,
    normalize_seconds, normalized_description, positive_verification,
)


BUSINESS_FIELDS = (
    'date', 'station', 'defect_code', 'product', 'serial_number', 'defect_description',
    'containment_action', 'exchange_component', 'exchange_verification', 'problem_type',
    'cause_analysis', 'long_term_action_qe', 'responsible_department', 'completion_date',
    'engineering_analysis_needed', 'informed_engineer', 'root_cause',
    'long_term_action_engineering', 'verified_by', 'remark',
)
SCHEMA_VERSION = '4'
_CACHE_LOCK = RLock()
_SNAPSHOTS: dict[str, dict[str, Any]] = {}
_DATA_PATHS: dict[str, Path] = {}


def valid_case(case: dict[str, str]) -> bool:
    return any(clean(case.get(field)) for field in BUSINESS_FIELDS)


def valid_action(action: str) -> bool:
    return bool(clean(action)) and clean(action).casefold() not in {'na', 'n/a', '/'}


_ACTION_VERB = re.compile(
    r'复测|重测|重新测试|老化|更换|替换|换新|(?<![交转变切])换|调整|调节|'
    r'调(?=电磁铁|[XYZ]轴|角度|间距|宽度)|重装|复装|重新安装|重新组装|'
    r'校准|校正|重新烧录|烧录|重新烧|重烧|烧(?=\s*录|\s*固件)|清洁|清理|检查|排查|'
    r'紧固|拧紧|润滑|维修|返修|复位|重启|开关机|断电|升级|更新|重新连接|重新插拔|'
    r'插拔|插排线|插线|接线|转工装|拆机|拆(?=\s*\d)|'
    r'(?<![a-z])(?:retest(?:ing)?|re-?test|replac(?:e|ed|ing)|adjust(?:ed|ing)?|'
    r'reinstall(?:ed|ing)?|calibrat(?:e|ed|ing)|flash(?:ed|ing)?|clean(?:ed|ing)?|'
    r'check(?:ed|ing)?|inspect(?:ed|ing)?|tighten(?:ed|ing)?|lubricat(?:e|ed|ing)|'
    r'repair(?:ed|ing)?|reset|restart(?:ed|ing)?|reboot(?:ed|ing)?|updat(?:e|ed|ing)|'
    r'upgrad(?:e|ed|ing)|reconnect(?:ed|ing)?)(?![a-z])', re.IGNORECASE,
)
_FAILED_ACTION = re.compile(
    r'不通过|未通过|失败|无效|未解决|没解决|仍(?:然|有|旧)?|依旧|还是|复发|'
    r'待分析|见工程分析|未处理|(?<![a-z])(?:ng|fail(?:ed|ure)?|not\s+ok)(?![a-z])', re.IGNORECASE,
)


def recommendation_action(action: str) -> bool:
    """Keep executable measures, excluding causes and failed/pending outcomes.

    This is deliberately separate from ``valid_action``: the source-field
    coverage statistic still counts every filled historical measure field.
    Only a clear operation after the last recorded failure can be recommended.
    The original text is never rewritten by this classification.
    """
    value = clean(action)
    if not valid_action(value):
        return False
    failures = list(_FAILED_ACTION.finditer(value))
    last_failure = failures[-1].end() if failures else -1
    for operation in _ACTION_VERB.finditer(value):
        if operation.start() < last_failure:
            continue
        prefix = value[max(0, operation.start() - 10):operation.start()]
        if re.search(r'(?:待|等待|未|没有|无需|不必|不用|禁止|不能)\s*$', prefix):
            continue
        if re.match(r'\s*(?:前|之前)', value[operation.end():]):
            continue
        if operation.group(0) in {'检查', '排查'} and re.match(r'\s*(?:到|发现|结果|显示)', value[operation.end():]):
            continue
        return True
    return False


def only_retest(action: str) -> bool:
    """Treat bare retest spellings as one attempted step, retaining repairs."""
    value = clean(action)
    if not re.search(r'复测|重测|重新测试|(?<![a-z])(?:retest(?:ing)?|re-?test)(?![a-z])', value, re.IGNORECASE):
        return False
    return not re.search(
        r'老化|更换|替换|换|调整|重装|复装|重新安装|重新组装|拆|安装|装配|校准|校正|'
        r'烧录|升级|更新|清洁|清理|检查|排查|润滑|紧固|返修|维修|复位|重启|断电|'
        r'reset|restart|replace|adjust|repair|install|calibrat|flash|clean|check|inspect|update|upgrade',
        value, re.IGNORECASE,
    )


def _key(database_path: Path) -> str:
    return str(Path(database_path).resolve())


def _file_signature(database_path: Path) -> tuple[tuple[int, int, int] | None, ...]:
    values = []
    for filename in (str(database_path), f'{database_path}-wal'):
        try:
            info = Path(filename).stat()
            values.append((info.st_ino, info.st_size, info.st_mtime_ns))
        except FileNotFoundError:
            values.append(None)
    return tuple(values)


def invalidate_cache(database_path: Path) -> None:
    with _CACHE_LOCK:
        _SNAPSHOTS.pop(_key(database_path), None)


def backup_database(database_path: Path, reason: str = 'manual') -> Path:
    """Use SQLite's online backup so committed WAL data is included as well."""
    database_path = Path(database_path)
    backup_dir = database_path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    safe_reason = ''.join(char for char in reason if char.isalnum() or char in '-_') or 'manual'
    destination = backup_dir / f'{database_path.stem}-{safe_reason}-{stamp}.sqlite3'
    pending = destination.with_suffix('.sqlite3.pending')
    pending.touch(exist_ok=False)
    try:
        with sqlite3.connect(database_path, timeout=30) as source, sqlite3.connect(pending) as target:
            source.backup(target)
        # Publish only completed backups, without overwriting any existing one.
        os.link(pending, destination)
    finally:
        pending.unlink(missing_ok=True)
    return destination


def _schema_ready(connection: sqlite3.Connection) -> bool:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'defect_cases', 'knowledge_meta', 'temporary_action_profiles', 'temporary_action_evidence',
            'defect_feedback', 'knowledge_changes'}.issubset(tables):
        return False
    row = connection.execute("SELECT value FROM knowledge_meta WHERE key='storage_schema_version'").fetchone()
    columns = {row[1] for row in connection.execute('PRAGMA table_info(temporary_action_evidence)')}
    case_columns = {row[1] for row in connection.execute('PRAGMA table_info(defect_cases)')}
    feedback_columns = {row[1] for row in connection.execute('PRAGMA table_info(defect_feedback)')}
    return bool(row and row[0] == SCHEMA_VERSION
                and {'normalized_action', 'operation', 'components', 'versions', 'positions'}.issubset(columns)
                and {'id', 'payload', 'is_active'}.issubset(case_columns)
                and {'repair_session_id', 'actual_serial_number'}.issubset(feedback_columns))


def _data_digest(stored: list[tuple[int, dict[str, str]]]) -> str:
    return hashlib.sha256(json.dumps(stored, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _evidence_digest(data_digest: str) -> str:
    return hashlib.sha256(f'temporary-actions-v{SCHEMA_VERSION}\0{data_digest}'.encode()).hexdigest()


def _prepare(connection: sqlite3.Connection, data_path: Path) -> None:
    # Original payloads/IDs remain authoritative. Feedback is never replaced.
    if not connection.in_transaction:
        connection.execute('BEGIN IMMEDIATE')
    connection.execute('CREATE TABLE IF NOT EXISTS defect_cases (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1)')
    if 'is_active' not in {row[1] for row in connection.execute('PRAGMA table_info(defect_cases)')}:
        connection.execute('ALTER TABLE defect_cases ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1')
    connection.execute('CREATE TABLE IF NOT EXISTS knowledge_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    if connection.execute("SELECT value FROM knowledge_meta WHERE key='imported'").fetchone() is None:
        if connection.execute('SELECT COUNT(*) FROM defect_cases').fetchone()[0] == 0 and data_path.is_file():
            with data_path.open(encoding='utf-8-sig', newline='') as source:
                records = [{k: clean(v) for k, v in row.items()} for row in csv.DictReader(source)]
            connection.executemany('INSERT INTO defect_cases(payload) VALUES (?)', [(json.dumps(row, ensure_ascii=False),) for row in records])
        connection.execute("INSERT INTO knowledge_meta VALUES ('imported', '1')")
    connection.execute('''CREATE TABLE IF NOT EXISTS temporary_action_profiles (
        id TEXT PRIMARY KEY, product TEXT NOT NULL, station TEXT NOT NULL,
        defect_code TEXT NOT NULL, symptom_normalized TEXT NOT NULL,
        record_count INTEGER NOT NULL, missing_action_count INTEGER NOT NULL)''')
    connection.execute('''CREATE TABLE IF NOT EXISTS temporary_action_evidence (
        profile_id TEXT NOT NULL, case_id INTEGER NOT NULL PRIMARY KEY, action TEXT NOT NULL,
        FOREIGN KEY(profile_id) REFERENCES temporary_action_profiles(id),
        FOREIGN KEY(case_id) REFERENCES defect_cases(id))''')
    evidence_columns = {row[1] for row in connection.execute('PRAGMA table_info(temporary_action_evidence)')}
    for column in ('normalized_action', 'operation', 'components', 'versions', 'positions'):
        if column not in evidence_columns:
            connection.execute(f"ALTER TABLE temporary_action_evidence ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    connection.execute('''CREATE TABLE IF NOT EXISTS defect_feedback (
        id TEXT PRIMARY KEY, case_id INTEGER NOT NULL, query TEXT NOT NULL,
        action TEXT NOT NULL, outcome TEXT NOT NULL, recurrence TEXT NOT NULL,
        note TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT NOT NULL,
        FOREIGN KEY(case_id) REFERENCES defect_cases(id))''')
    feedback_columns = {row[1] for row in connection.execute('PRAGMA table_info(defect_feedback)')}
    for column in ('repair_session_id', 'actual_serial_number'):
        if column not in feedback_columns:
            connection.execute(f"ALTER TABLE defect_feedback ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    connection.execute('CREATE INDEX IF NOT EXISTS idx_defect_feedback_case ON defect_feedback(case_id, created_at)')
    connection.execute('CREATE INDEX IF NOT EXISTS idx_defect_feedback_session ON defect_feedback(repair_session_id, created_by, created_at)')
    connection.execute('''CREATE TABLE IF NOT EXISTS knowledge_changes (
        id INTEGER PRIMARY KEY, event TEXT NOT NULL, created_at TEXT NOT NULL,
        details TEXT NOT NULL)''')
    stored = [(row_id, json.loads(payload)) for row_id, payload in connection.execute('SELECT id, payload FROM defect_cases ORDER BY id')]
    data_digest = _data_digest(stored)
    signature = _evidence_digest(data_digest)
    previous = connection.execute("SELECT value FROM knowledge_meta WHERE key='temporary_actions_digest'").fetchone()
    if previous is None or previous[0] != signature:
        grouped: dict[tuple[str, ...], list[tuple[int, dict[str, str]]]] = defaultdict(list)
        connection.execute('DELETE FROM temporary_action_evidence')
        connection.execute('DELETE FROM temporary_action_profiles')
        for case_id, case in stored:
            active = valid_case(case)
            connection.execute('UPDATE defect_cases SET is_active=? WHERE id=?', (int(active), case_id))
            if active:
                key = (canonical_product(case.get('product', '')), clean(case.get('station')), clean(case.get('defect_code')), normalized_description(case.get('defect_description', '')))
                grouped[key].append((case_id, case))
        for key, members in grouped.items():
            profile_id = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()
            missing = sum(not valid_action(case.get('containment_action', '')) for _, case in members)
            connection.execute('INSERT INTO temporary_action_profiles VALUES (?,?,?,?,?,?,?)', (profile_id, *key, len(members), missing))
            for case_id, case in members:
                if not valid_action(case.get('containment_action', '')):
                    continue
                action = clean(case['containment_action'])
                normalized = normalize_action(action, case.get('serial_number', ''))
                connection.execute('''INSERT INTO temporary_action_evidence
                    (profile_id,case_id,action,normalized_action,operation,components,versions,positions)
                    VALUES (?,?,?,?,?,?,?,?)''', (profile_id, case_id, action,
                    normalized['normalized_action'], normalized['operation'],
                    json.dumps(normalized['components'], ensure_ascii=False),
                    json.dumps(normalized['versions'], ensure_ascii=False),
                    json.dumps(normalized['positions'], ensure_ascii=False)))
        connection.execute("INSERT OR REPLACE INTO knowledge_meta VALUES ('temporary_actions_digest', ?)", (signature,))
    previous_version = connection.execute("SELECT value FROM knowledge_meta WHERE key='data_version'").fetchone()
    if previous_version is None or previous_version[0] != data_digest:
        connection.execute("INSERT OR REPLACE INTO knowledge_meta VALUES ('data_version', ?)", (data_digest,))
        connection.execute("INSERT OR REPLACE INTO knowledge_meta VALUES ('last_updated', ?)", (datetime.now(timezone.utc).isoformat(),))
    schema_version = connection.execute("SELECT value FROM knowledge_meta WHERE key='storage_schema_version'").fetchone()
    if schema_version is None or schema_version[0] != SCHEMA_VERSION:
        connection.execute("INSERT OR REPLACE INTO knowledge_meta VALUES ('storage_schema_version', ?)", (SCHEMA_VERSION,))


def _read_snapshot(connection: sqlite3.Connection, stored: list[tuple[int, dict[str, str]]] | None = None) -> dict[str, Any]:
    cases = []
    active_ids = {row[0] for row in connection.execute('SELECT id FROM defect_cases WHERE is_active=1')}
    if stored is None:
        stored = [(case_id, json.loads(payload)) for case_id, payload in connection.execute('SELECT id,payload FROM defect_cases ORDER BY id')]
    for case_id, payload in stored:
        if case_id not in active_ids:
            continue
        case = dict(payload)
        product = canonical_product(case.get('product', ''))
        if product != case.get('product', ''):
            case['original_product'] = case.get('product', '')
        case['product'] = product
        case['local_id'] = str(case_id)
        case['source_url'] = f'/api/defect-search/source/{case_id}'
        cases.append(case)
    evidence = {}
    for row in connection.execute('SELECT case_id,action,normalized_action,operation,components,versions,positions FROM temporary_action_evidence'):
        evidence[row[0]] = {'original_action': row[1], 'normalized_action': row[2], 'operation': row[3],
                            'components': json.loads(row[4] or '[]'), 'versions': json.loads(row[5] or '[]'), 'positions': json.loads(row[6] or '[]')}
    return {
        'cases': tuple(cases), 'evidence': evidence,
        'statistics': {'action_profiles': connection.execute('SELECT COUNT(*) FROM temporary_action_profiles').fetchone()[0],
                       'action_cases': len(evidence)},
    }


def _finish_snapshot(connection: sqlite3.Connection, database_path: Path, current: dict[str, Any], version_before: int) -> bool:
    connection.commit()
    signature = _file_signature(database_path)
    version_after = connection.execute('PRAGMA data_version').fetchone()[0]
    current['signature'] = signature
    # A concurrent process must not make an older consistent snapshot appear
    # current merely by changing the DB between our commit and file stat.
    return version_before == version_after and _file_signature(database_path) == signature


def _snapshot(database_path: Path, data_path: Path | None = None) -> dict[str, Any]:
    database_path = Path(database_path)
    key = _key(database_path)
    with _CACHE_LOCK:
        if data_path is not None:
            _DATA_PATHS[key] = Path(data_path)
        source_path = _DATA_PATHS.get(key, database_path.parent / 'seed.csv')
        signature = _file_signature(database_path)
        previous = _SNAPSHOTS.get(key)
        if previous is not None and previous['signature'] == signature:
            return previous
        database_path.parent.mkdir(parents=True, exist_ok=True)
        schema_ready = False
        # A feedback write changes the file signature, but not case evidence.
        # Confirm that in one read transaction and avoid acquiring a write lock.
        if database_path.exists() and database_path.stat().st_size:
            with sqlite3.connect(database_path, timeout=30) as connection:
                version_before = connection.execute('PRAGMA data_version').fetchone()[0]
                connection.execute('BEGIN')
                schema_ready = _schema_ready(connection)
                if schema_ready:
                    stored = [(case_id, json.loads(payload)) for case_id, payload in connection.execute('SELECT id,payload FROM defect_cases ORDER BY id')]
                    meta = dict(connection.execute('SELECT key,value FROM knowledge_meta'))
                    digest = _data_digest(stored)
                    if meta.get('data_version') == digest and meta.get('temporary_actions_digest') == _evidence_digest(digest):
                        current = _read_snapshot(connection, stored)
                        if _finish_snapshot(connection, database_path, current, version_before):
                            _SNAPSHOTS[key] = current
                        return current
        if not schema_ready:
            backup_database(database_path, 'before-schema-v' + SCHEMA_VERSION)
        with sqlite3.connect(database_path, timeout=30) as connection:
            version_before = connection.execute('PRAGMA data_version').fetchone()[0]
            _prepare(connection, source_path)
            # Derivation and reading use the same transaction, so external case
            # updates cannot pair a new description with old action evidence.
            current = _read_snapshot(connection)
            if _finish_snapshot(connection, database_path, current, version_before):
                _SNAPSHOTS[key] = current
        return current


def ensure_database(database_path: Path, data_path: Path) -> None:
    _snapshot(database_path, data_path)


def load_cases(database_path: Path, data_path: Path) -> tuple[dict[str, str], ...]:
    # A caller may annotate scores; copies prevent cross-request state leaks.
    return copy.deepcopy(_snapshot(database_path, data_path)['cases'])


def statistics(database_path: Path, cases: tuple[dict[str, str], ...] | list[dict[str, str]] | None = None) -> dict[str, int]:
    if cases is not None:
        # A request may continue working from an older valid snapshot while a
        # CSV import commits. Its summary must describe that same snapshot.
        profiles = {(canonical_product(case.get('product', '')), clean(case.get('station')),
                     clean(case.get('defect_code')), normalized_description(case.get('defect_description', '')))
                    for case in cases}
        return {'action_profiles': len(profiles),
                'action_cases': sum(valid_action(case.get('containment_action', '')) for case in cases)}
    return dict(_snapshot(database_path)['statistics'])


def _date_key(value: str) -> tuple[int, ...]:
    import re
    values = [int(part) for part in re.findall(r'\d+', value)[:6]]
    return tuple(values + [0] * (6 - len(values)))


def recommend(database_path: Path, cases: list[dict[str, str]], *, retest_first: bool = False,
              exclude_action: str = '', exclude_retest: bool = False) -> list[dict[str, Any]]:
    if not cases:
        return []
    # Cases are already a local DB snapshot. Re-reading newer evidence here
    # could mix versions if another request imports a CSV during this search.
    evidence = {}
    for case in cases:
        action = clean(case.get('containment_action', ''))
        if recommendation_action(action):
            evidence[int(case['local_id'])] = {'original_action': action,
                                             **normalize_action(action, case.get('serial_number', ''))}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for case in cases:
        grouped[canonical_product(case.get('product', ''))].append(case)
    excluded = normalize_action(exclude_action)['normalized_action'].casefold() if exclude_action else ''
    recommendations = []
    for product, members in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        actions: dict[str, list[dict[str, str]]] = defaultdict(list)
        for case in members:
            item = evidence.get(int(case['local_id']))
            if (item and item['normalized_action'].casefold() != excluded
                    and not (exclude_retest and only_retest(item['normalized_action']))):
                actions[item['normalized_action'].casefold()].append(case)
        action_items = []
        for _, sources in actions.items():
            representative = evidence[int(sources[0]['local_id'])]
            action = representative['normalized_action']
            verified = sum(positive_verification(case.get('exchange_verification', '')) for case in sources)
            latest = max(sources, key=lambda case: _date_key(case.get('date', ''))).get('date', '')
            action_items.append({
                'action': action, 'normalized_action': action,
                'operation': representative['operation'], 'components': list(representative['components']),
                'versions': list(representative['versions']), 'positions': list(representative['positions']),
                'original_variants': sorted({evidence[int(case['local_id'])]['original_action'] for case in sources}),
                'count': len(sources), 'share': len(sources) / len(members),
                'verified_cases': verified,
                'evidence_level': 'verified' if verified else ('multiple' if len(sources) > 1 else 'single'),
                'latest_date': latest,
                'sources': [{
                    'local_id': case['local_id'], 'source': case.get('source', ''),
                    'source_row': case.get('source_row', ''), 'source_url': f"/api/defect-search/source/{case['local_id']}",
                    'defect_description': case.get('defect_description', ''),
                    'verification': case.get('exchange_verification', ''),
                    'original_action': evidence[int(case['local_id'])]['original_action'],
                } for case in sorted(sources, key=lambda case: (_date_key(case.get('date', '')), int(case['local_id'])), reverse=True)[:3]],
            })
        action_items.sort(key=lambda item: (not (retest_first and item['action'] == '复测'), -item['count'], item['action']))
        recommendations.append({
            'product': product, 'matched_cases': len(members),
            'missing_action_cases': sum(int(case['local_id']) not in evidence for case in members),
            'non_action_cases': sum(valid_action(case.get('containment_action', ''))
                                    and int(case['local_id']) not in evidence for case in members),
            'stations': sorted({case.get('station', '') for case in members if case.get('station')}),
            'defect_codes': sorted({case.get('defect_code', '') for case in members if case.get('defect_code')}),
            'actions': action_items[:3],
        })
    return recommendations

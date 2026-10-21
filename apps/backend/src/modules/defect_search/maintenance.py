"""Previewed, transactional CSV updates and recoverable local maintenance."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import repository


CSV_COLUMNS = (
    'source', 'source_url', 'source_sheet', 'source_row', 'symptom_category',
    'symptom_normalized', 'problem_type_normalized', 'knowledge_status',
    'duplicate_candidate', 'duplicate_group_id', 'record_no', *repository.BUSINESS_FIELDS,
)
REQUIRED_COLUMNS = ('source', 'source_sheet', 'source_row', 'product', 'defect_description', 'containment_action')


def backup_database(database_path: Path, reason: str = 'manual') -> Path:
    return repository.backup_database(database_path, reason)


def _parse(csv_content: str) -> tuple[list[dict[str, str]], list[str], list[str]]:
    errors: list[str] = []
    rows: list[dict[str, str]] = []
    if len(csv_content.encode('utf-8')) > 20 * 1024 * 1024:
        return [], [], ['CSV 超过 20 MB，请分批导入。']
    reader = csv.DictReader(io.StringIO(csv_content.lstrip('\ufeff')), strict=True)
    try:
        columns = [repository.clean(column) for column in (reader.fieldnames or [])]
        if not columns:
            return [], [], ['CSV 缺少表头。']
        if len(set(columns)) != len(columns):
            errors.append('CSV 表头有重复列。')
        unknown = sorted(set(columns) - set(CSV_COLUMNS))
        missing = sorted(set(REQUIRED_COLUMNS) - set(columns))
        if unknown:
            errors.append('不支持的列：' + '、'.join(unknown))
        if missing:
            errors.append('缺少必要列：' + '、'.join(missing))
        # DictReader uses original headers, so assign the cleaned known headers.
        reader.fieldnames = columns
        identities: set[tuple[str, str, str]] = set()
        for line, raw in enumerate(reader, 2):
            if None in raw:
                errors.append(f'第 {line} 行列数多于表头。')
                continue
            if any(value is None for value in raw.values()):
                errors.append(f'第 {line} 行列数少于表头。')
                continue
            row = {key: repository.clean(value) for key, value in raw.items() if key in CSV_COLUMNS and key != 'source_url'}
            if not any(row.values()):
                continue
            if not row.get('source') or not row.get('source_sheet'):
                errors.append(f'第 {line} 行的 source 和 source_sheet 不能为空。')
            row_number = row.get('source_row', '')
            if not row_number.isascii() or not row_number.isdigit() or int(row_number or '0') < 1:
                errors.append(f'第 {line} 行的 source_row 必须为正整数。')
            else:
                row['source_row'] = str(int(row_number))
            identity = _identity(row)
            if identity in identities:
                errors.append(f'第 {line} 行来源键重复：{identity[0]} / {identity[1]} / {identity[2]}。')
            identities.add(identity)
            rows.append(row)
            if len(rows) > 50000:
                errors.append('单次最多导入 50000 行。')
                break
        if not rows:
            errors.append('CSV 没有数据行。')
        return rows, columns, errors
    except (csv.Error, UnicodeError) as exc:
        return rows, [], [f'CSV 格式无效：{exc}']


def _identity(row: dict[str, str]) -> tuple[str, str, str]:
    number = repository.clean(row.get('source_row'))
    if number.isascii() and number.isdigit():
        number = str(int(number))
    return (repository.clean(row.get('source')), repository.clean(row.get('source_sheet')), number)


def _stored(database_path: Path, data_path: Path, connection: sqlite3.Connection | None = None) -> list[tuple[int, dict[str, str]]]:
    if connection is not None:
        return [(case_id, json.loads(payload)) for case_id, payload in connection.execute('SELECT id,payload FROM defect_cases ORDER BY id')]
    if database_path.exists() and database_path.stat().st_size:
        with sqlite3.connect(database_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=30) as source:
            if source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='defect_cases'").fetchone():
                return _stored(database_path, data_path, source)
    # Previewing a never-initialized installation is still read-only. Account
    # for an optional deployment seed; new installations can start empty.
    if not Path(data_path).is_file():
        return []
    with Path(data_path).open(encoding='utf-8-sig', newline='') as source_file:
        return [(index, {key: repository.clean(value) for key, value in row.items()})
                for index, row in enumerate(csv.DictReader(source_file), 1)]


def _comparable(payload: dict[str, str]) -> dict[str, str]:
    return {key: repository.clean(value) for key, value in payload.items() if key != 'source_url'}


def _plan(database_path: Path, data_path: Path, csv_content: str, connection: sqlite3.Connection | None = None) -> tuple[dict[str, Any], list[tuple[int | None, dict[str, str]]]]:
    rows, columns, errors = _parse(csv_content)
    stored = _stored(database_path, data_path, connection)
    data_digest = hashlib.sha256(json.dumps(stored, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    token = hashlib.sha256(('defect-import-v1\0' + data_digest + '\0' + csv_content).encode()).hexdigest()
    by_source: dict[tuple[str, str, str], tuple[int, dict[str, str]]] = {}
    for case_id, payload in stored:
        identity = _identity(payload)
        if identity in by_source:
            errors.append(f'本地来源键不唯一，需先整理：{identity[0]} / {identity[1]} / {identity[2]}。')
        by_source[identity] = (case_id, payload)
    inserted = updated = unchanged = 0
    changes: list[tuple[int | None, dict[str, str]]] = []
    for row in rows:
        existing = by_source.get(_identity(row))
        if existing is None:
            inserted += 1
            changes.append((None, row))
        else:
            case_id, payload = existing
            merged = {**payload, **row}
            if _comparable(merged) == _comparable(payload):
                unchanged += 1
            else:
                updated += 1
                changes.append((case_id, merged))
    return ({'preview_token': token, 'rows': len(rows), 'inserted': inserted,
             'updated': updated, 'unchanged': unchanged, 'errors': errors, 'columns': columns}, changes)


def preview_import(database_path: Path, data_path: Path, csv_content: str) -> dict[str, Any]:
    """Inspect only: no migrations, database writes or backup side effects."""
    return _plan(Path(database_path), Path(data_path), csv_content)[0]


def import_csv(database_path: Path, data_path: Path, csv_content: str, preview_token: str) -> dict[str, Any]:
    database_path, data_path = Path(database_path), Path(data_path)
    with repository._CACHE_LOCK:
        preflight, _ = _plan(database_path, data_path, csv_content)
        if preflight['errors']:
            raise ValueError('；'.join(preflight['errors']))
        if not preview_token or preview_token != preflight['preview_token']:
            raise ValueError('预览已失效或文件内容已改变，请重新预览后导入。')
        repository.ensure_database(database_path, data_path)
        with sqlite3.connect(database_path, timeout=30) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('BEGIN IMMEDIATE')
            result, changes = _plan(database_path, data_path, csv_content, connection)
            if result['errors']:
                raise ValueError('；'.join(result['errors']))
            if not preview_token or preview_token != result['preview_token']:
                raise ValueError('预览已失效或文件内容已改变，请重新预览后导入。')
            backup = backup_database(database_path, 'before-csv-import')
            for case_id, payload in changes:
                if case_id is None:
                    cursor = connection.execute('INSERT INTO defect_cases(payload) VALUES (?)', ('{}',))
                    case_id = cursor.lastrowid
                local_payload = {**payload, 'source_url': f'/api/defect-search/source/{case_id}'}
                connection.execute('UPDATE defect_cases SET payload=? WHERE id=?', (json.dumps(local_payload, ensure_ascii=False), case_id))
            # Derived tables and original rows commit atomically; existing IDs
            # are updated in place and feedback foreign keys remain intact.
            repository._prepare(connection, data_path)
            timestamp = datetime.now(timezone.utc).isoformat()
            connection.execute("INSERT OR REPLACE INTO knowledge_meta VALUES ('last_import', ?)", (timestamp,))
            connection.execute('INSERT INTO knowledge_changes(event,created_at,details) VALUES (?,?,?)',
                               ('csv_import', timestamp, json.dumps({key: result[key] for key in ('rows', 'inserted', 'updated', 'unchanged')} | {'backup': backup.name}, ensure_ascii=False)))
        repository.invalidate_cache(database_path)
        repository.ensure_database(database_path, data_path)
        status = get_maintenance_status(database_path)
        return {**result, 'backup': backup.name, 'data_version': status['data_version'], 'last_updated': status['last_updated']}


def get_maintenance_status(database_path: Path) -> dict[str, Any]:
    database_path = Path(database_path)
    backup_dir = database_path.parent / 'backups'
    backups = sorted(backup_dir.glob(database_path.stem + '-*.sqlite3'), key=lambda item: item.stat().st_mtime_ns, reverse=True) if backup_dir.exists() else []
    result: dict[str, Any] = {
        'data_version': '', 'last_updated': '', 'last_import': '',
        'backup_count': len(backups), 'last_backup': backups[0].name if backups else '',
        'last_backup_at': datetime.fromtimestamp(backups[0].stat().st_mtime, timezone.utc).isoformat() if backups else '',
        'rows': 0, 'active_rows': 0, 'action_profiles': 0, 'action_cases': 0,
        'feedback_count': 0, 'changes': [],
    }
    if not database_path.exists():
        return result
    with sqlite3.connect(database_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=30) as connection:
        connection.execute('BEGIN')
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'knowledge_meta' in tables:
            meta = dict(connection.execute('SELECT key,value FROM knowledge_meta'))
            result.update({key: meta.get(key, '') for key in ('data_version', 'last_updated', 'last_import')})
        if 'defect_cases' in tables:
            result['rows'] = connection.execute('SELECT COUNT(*) FROM defect_cases').fetchone()[0]
            columns = {row[1] for row in connection.execute('PRAGMA table_info(defect_cases)')}
            result['active_rows'] = connection.execute('SELECT COUNT(*) FROM defect_cases WHERE is_active=1').fetchone()[0] if 'is_active' in columns else result['rows']
        for table, key in (('temporary_action_profiles', 'action_profiles'), ('temporary_action_evidence', 'action_cases'), ('defect_feedback', 'feedback_count')):
            if table in tables:
                result[key] = connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        if 'knowledge_changes' in tables:
            result['changes'] = [{'event': event, 'created_at': timestamp, 'details': json.loads(details)}
                                 for event, timestamp, details in connection.execute('SELECT event,created_at,details FROM knowledge_changes ORDER BY id DESC LIMIT 20')]
    return result

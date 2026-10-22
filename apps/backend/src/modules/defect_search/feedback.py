"""Local repair observations, kept separate from imported historical evidence."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import repository


class CaseNotFoundError(LookupError):
    """The selected record is not an active local case."""


class RepairSessionNotFoundError(LookupError):
    """The repair session is absent or belongs to another signed-in user."""


def _case_from_row(row: sqlite3.Row) -> dict[str, str]:
    try:
        payload = json.loads(row['payload'])
        if not isinstance(payload, dict):
            raise ValueError('Invalid case payload')
    except (ValueError, TypeError) as exc:
        raise sqlite3.DatabaseError('Invalid local case record') from exc
    return {**payload, 'local_id': str(row['id']),
            'source_url': f"/api/defect-search/source/{row['id']}"}


def _active_case(connection: sqlite3.Connection, case_id: int) -> dict[str, str]:
    row = connection.execute(
        'SELECT id, payload FROM defect_cases WHERE id=? AND is_active=1', (case_id,),
    ).fetchone()
    if row is None:
        raise CaseNotFoundError('未找到有效的本地缺陷案例')
    return _case_from_row(row)


def _repair_session(
    connection: sqlite3.Connection, repair_session_id: str, *, case_id: int,
    created_by: str, actual_serial_number: str | None = None,
) -> dict[str, Any]:
    rows = list(connection.execute(
        '''SELECT DISTINCT case_id, created_by, actual_serial_number
           FROM defect_feedback WHERE repair_session_id=?''', (repair_session_id,),
    ))
    # Do not reveal another user's session or use a browser-supplied identity.
    if not rows or not created_by or any(row['created_by'] != created_by for row in rows):
        raise RepairSessionNotFoundError('未找到本次处理记录，请新建本次处理')
    if any(row['case_id'] != case_id for row in rows):
        raise ValueError('本次处理已绑定另一条参考案例，请新建本次处理')
    if len(rows) != 1:
        raise ValueError('本次处理信息不一致，请新建本次处理')
    session = dict(rows[0])
    if actual_serial_number is not None and session['actual_serial_number'] != actual_serial_number:
        raise ValueError('本次处理的实际设备 SN 不能变更，请为另一台设备新建处理')
    return session


def list_feedback(
    database_path: Path, data_path: Path, case_id: int, *, repair_session_id: str = '',
    created_by: str = '',
) -> list[dict[str, Any]]:
    repair_session_id = repair_session_id.strip()
    if not created_by:
        raise ValueError('请登录后查看本次处理结果')
    if len(repair_session_id) > 128:
        raise ValueError('本次处理标识过长')
    repository.ensure_database(database_path, data_path)
    with sqlite3.connect(database_path, timeout=10) as connection:
        connection.row_factory = sqlite3.Row
        _active_case(connection, case_id)
        if repair_session_id:
            _repair_session(connection, repair_session_id, case_id=case_id, created_by=created_by)
            return [dict(row) for row in connection.execute(
                '''SELECT * FROM defect_feedback
                   WHERE repair_session_id=? AND case_id=? AND created_by=?
                   ORDER BY created_at DESC, id DESC LIMIT 100''',
                (repair_session_id, case_id, created_by),
            )]
        return [dict(row) for row in connection.execute(
            'SELECT * FROM defect_feedback WHERE case_id=? AND created_by=? ORDER BY created_at DESC, id DESC LIMIT 100',
            (case_id, created_by),
        )]


def _result_guidance(observation: dict[str, Any]) -> dict[str, Any]:
    """Acknowledge an optional observation and direct new symptoms to search."""
    outcome = observation['outcome']
    if outcome == 'passed' and observation['recurrence'] == 'yes':
        return {
            'kind': 'engineering_review', 'action': '保留本次通过和再次复发的记录，提交工程分析。',
            'reason': '请补充复发条件、当前现象及已采取措施和结果，重新检索处理建议，或由工程根据实际问题分析。',
            'sources': [],
        }
    if outcome == 'passed':
        return {
            'kind': 'resolved', 'action': '记录本次复测通过，并按工站要求完成后续检查。',
            'reason': '已保存本次处理结果。后续如出现新的异常，可补充实际描述重新检索，或交由工程分析。',
            'sources': [],
        }
    if outcome == 'pending':
        return {
            'kind': 'pending', 'action': '完成当前措施后的复测，再记录通过或失败。',
            'reason': '已保存本次措施。需要继续咨询时，请补充最新现象和测试结果重新检索，或交由工程分析。', 'sources': [],
        }
    return {
        'kind': 'engineering_review', 'action': '补充实际现象重新检索，或交由工程分析。',
        'reason': '已保存本次未通过的结果。请在缺陷描述中补充当前表现、报错、已采取措施及结果，助手将依据最新描述提供历史参考建议。',
        'sources': [],
    }


def save_feedback(
    database_path: Path, data_path: Path, *, case_id: int, query: str, action: str,
    outcome: str, recurrence: str, note: str, created_by: str,
    repair_session_id: str = '', actual_serial_number: str = '',
) -> dict[str, Any]:
    query, action, note = query.strip(), action.strip(), note.strip()
    repair_session_id, actual_serial_number = repair_session_id.strip(), actual_serial_number.strip()
    if not action or len(action) > 2000 or len(query) > 500 or len(note) > 4000:
        raise ValueError('请填写有效的处理措施，并检查内容长度')
    if len(repair_session_id) > 128 or len(actual_serial_number) > 128:
        raise ValueError('本次处理标识或实际设备 SN 过长')
    if not created_by:
        raise ValueError('请登录后记录本次处理结果')
    if outcome not in {'passed', 'failed', 'pending'} or recurrence not in {'unknown', 'yes', 'no'}:
        raise ValueError('处理结果或复发状态无效')
    repository.ensure_database(database_path, data_path)
    observation = {
        'id': str(uuid4()), 'case_id': case_id, 'query': query, 'action': action,
        'outcome': outcome, 'recurrence': recurrence, 'note': note,
        'created_at': datetime.now(timezone.utc).isoformat(), 'created_by': created_by,
        'repair_session_id': repair_session_id or str(uuid4()),
        'actual_serial_number': actual_serial_number,
    }
    with sqlite3.connect(database_path, timeout=10) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('BEGIN IMMEDIATE')
        _active_case(connection, case_id)
        if repair_session_id:
            _repair_session(
                connection, repair_session_id, case_id=case_id, created_by=created_by,
                actual_serial_number=actual_serial_number,
            )
        connection.execute(
            '''INSERT INTO defect_feedback
               (id, case_id, query, action, outcome, recurrence, note, created_at, created_by,
                repair_session_id, actual_serial_number) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            tuple(observation.values()),
        )
        result_guidance = _result_guidance(observation)
    repository.invalidate_cache(database_path)
    # Keep the response key for clients that already consume it. It now
    # contains result guidance, rather than a prescribed repair sequence.
    return {'feedback': observation, 'next_step': result_guidance}

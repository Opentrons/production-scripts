"""Read captured QC evidence without importing robot code or regrading results.

Every proposed investigation refers to an original JSON path.  Input strings are
untrusted report contents, never commands or instructions to the analyzer.
"""

import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..reference import reference_event_volume, reference_failure_context, reference_snapshot


RULES_VERSION = "1.2"
MAX_FAILED_ROWS = 30
MAX_FAILURE_DETAILS = 30
MAX_TEST_STATUSES = 40
MAX_HANDLED_EXCEPTIONS = 40
MAX_THRESHOLDS = 60
MAX_EVENTS = 10
MAX_FINDING_REFS = 12


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _action_view(value: Any) -> dict:
    """Exclude the copied readings from an action; readings have their own refs."""
    value = _mapping(value)
    return {
        key: value[key]
        for key in (
            "id",
            "action",
            "error",
            "status",
            "observed_at",
            "arguments",
            "context",
        )
        if key in value
    }


def _reference_failure_volume(failure: dict, blocked_volumes: dict) -> str:
    """Associate only this action's physical mount and reference tip volume."""
    context = reference_failure_context(failure)
    volume = str(context.volume) if context.volume is not None else ""
    if context.mount != "LEFT" and volume in blocked_volumes and (context.mount == "RIGHT" or context.in_reference):
        return volume
    return ""


def _compact(value: Any, depth: int = 0) -> Any:
    """Bound payload size; truncation is visible, full inputs stay in snapshots."""
    if depth >= 7:
        return "[内容过深；请核对原文件]"
    if isinstance(value, str):
        return value if len(value) <= 1400 else value[:1400] + "[内容截断]"
    if isinstance(value, list):
        result = [_compact(item, depth + 1) for item in value[:40]]
        if len(value) > 40:
            result.append({"omitted_items": len(value) - 40})
        return result
    if isinstance(value, dict):
        result = {
            str(key): _compact(item, depth + 1)
            for key, item in list(value.items())[:50]
        }
        if len(value) > 50:
            result["_omitted_keys"] = len(value) - 50
        return result
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _safe_file(directory: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).name != name or name in ("", ".", ".."):
        raise ValueError("invalid_report_name: 只允许快照目录内的文件名")
    path = directory / name
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError("invalid_report_path: 不读取目录外文件或符号链接")
    return path


def _encoder_summary(directory: Path, name: str) -> dict:
    """Summarize only the same-stem attachment, without assumed units/limits."""
    path = _safe_file(directory, name)
    if not path.is_file():
        return {"status": "not_available", "filename": name}
    if path.stat().st_size > 2 * 1024 * 1024:
        return {"status": "too_large", "filename": name, "limit_bytes": 2097152}
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            headers = next(reader, [])
            if not headers or len(headers) > 64:
                return {"status": "invalid_header", "filename": name}
            columns: dict[int, list[float]] = {}
            counts: Counter = Counter()
            total = 0
            truncated = False
            for row in reader:
                if total >= 2000:
                    truncated = True
                    break
                total += 1
                if len(row) != len(headers):
                    counts["malformed_rows"] += 1
                    continue
                for index, cell in enumerate(row):
                    try:
                        numeric = float(cell)
                    except ValueError:
                        continue
                    if math.isfinite(numeric):
                        columns.setdefault(index, []).append(numeric)
            return {
                "status": "summarized",
                "filename": name,
                "rows_examined": total,
                "truncated": truncated,
                "malformed_rows": counts["malformed_rows"],
                "columns": [
                    {
                        "column_index": index,
                        "header": header[:200],
                        "numeric_samples": len(columns.get(index, [])),
                        "minimum": min(columns[index]) if index in columns else None,
                        "maximum": max(columns[index]) if index in columns else None,
                    }
                    for index, header in enumerate(headers)
                ],
                "interpretation": "仅为原列数值摘要；单位依原表头，不据此重新判定合格或故障。",
            }
    except (OSError, UnicodeError, csv.Error) as error:
        return {"status": "unreadable", "filename": name, "error": str(error)[:300]}


# Stable, reviewable investigation rules. No component is diagnosed by a keyword.
_RULES = {
    "software_interface": (
        "调用接口与传入参数不兼容，尚不能仅凭此确定哪个部署文件版本错误。",
        ["核对异常中的函数名和参数名；比对协议、helpers 与机器人软件部署版本及哈希。"],
        "由维护人员统一调用方与函数接口版本；无需据此更换扫码枪或移液器。",
        "版本一致后重跑原失败步骤，再完成原配置下的完整 QC。",
    ),
    "sensor_support": (
        "所请求的传感器状态不存在；具体是型号调用不适配还是状态/软件异常待核实。",
        ["核对失败安装位的实际型号、通道数与请求 PRIMARY/SECONDARY。", "检查匹配软件版本的传感器支持能力；状态缺失不能证明传感器损坏。"],
        "先排除配置及接口支持问题；支持该传感器仍复现时交工程人员核对通讯与硬件。",
        "修正确认的问题后复测原传感器调用和其所属测试，再完成完整 QC。",
    ),
    "overpressure": (
        "压力保护在记录的动作中触发；触发瞬间压力及具体硬件原因尚未确认。",
        [
            "先查看最内层失败动作、安装位和上下文：若为 calibration.home，核对当时探针安装确认及回零状态。",
            "记录当时吸头、探针、夹具和气路状态，核对原柱塞运动；最近读数仅供背景参考。",
        ],
        "按现场证据排除安装/耗材/夹具条件；异常仍在同一安装位时交工程人员检查气路与运动。保留压力保护。",
        "确认并处理原因后，按原参数复测失败阶段和关联压力项目，再完整 QC。",
    ),
    "identity": (
        "报告身份与实际左侧被测设备身份不一致。",
        ["核对设备读取序列号、扫码内容、标签及装配记录，确认本报告归属。"],
        "在归属确认前暂停针对某台移液器的返修结论，先纠正报告/设备关联。",
        "身份一致后重跑元数据验证和该设备完整 QC。",
    ),
    "barcode": (
        "设备编号校验未通过。",
        ["逐字核对扫码内容、设备读取编号与装配记录。"],
        "纠正已确认的录入或身份关联问题，不据此判断机械故障。",
        "编号一致后验证元数据并运行完整 QC。",
    ),
    "right_reference": (
        "右侧参考流程未完成；对应规格待测侧试验存在前置阻断，原始判定仍保留。",
        [
            "按该规格核对右侧 P1000S 身份、A12 吸头、参考校准、液面、基线稳定性和实际失败动作。",
            "记录吸头规格及失败原因；不可将未执行的左侧试验归因为左侧传感器损坏。",
            "参考流程归属不等于 RIGHT 本体故障；保留最内层动作的实际 mount、软件异常及原始异常链。",
        ],
        "处理已确认的右侧参考条件或配置问题；机械/气路问题交工程核实。",
        "先重新完成同规格右侧点水，再执行左侧全部试次，沿用原准确度及重复性判据。",
    ),
    "plunger_travel_setup": (
        "参考点水所需柱塞行程条件未满足，尚不足以确定零件故障。",
        ["核对点水前柱塞位置、可用行程、预充气参数及实际运动记录。"],
        "由工程确认行程配置与现场条件，不自行增加下降距离或取消保护。",
        "条件满足后按原批准参数重跑参考点水及对应规格 liquid probe。",
    ),
    "diagnostic_pressure": (
        "诊断压力项目原判定未通过，不能等同于压力夹具泄漏测试。",
        ["分空气、封堵和吸液阶段对照压力、通道及该次范围。", "检查诊断吸头安装与堵孔状态，记录换用已确认正常耗材后异常是否仍在原通道。"],
        "先排除耗材和封堵条件；同通道持续异常时交工程检查气路/传感器，不直接指定换件。",
        "按该次原范围复测诊断各压力阶段及关联压力项目。",
    ),
    "pressure_fixture": (
        "压力夹具项目原判定未通过，需区分范围、稳定性及压差。",
        ["按通道、阶段和时间核对原范围与聚合判据，未分级原始点不得单独判失败。", "先检查吸头、夹具、接头密封；记录异常是否随耗材或夹具变动转移。"],
        "定位耗材/夹具影响后再考虑本体气路，内部处理交工程确认。",
        "按原配置复测对应压力事件及整组夹具测试，不更改阈值。",
    ),
    "temperature": (
        "温度项目原判定未通过。",
        ["核对现场温度、稳定时间及日志读数，与已确认正常的外部温度计对照。"],
        "先稳定测试环境；偏差仍固定于设备时由工程核对传感器。",
        "按本次记录的温度范围复测，并复测受环境影响的项目。",
    ),
    "humidity": (
        "湿度项目原判定未通过。",
        ["核对现场湿度、稳定时间及日志读数，与已确认正常的外部湿度计对照。"],
        "先确认环境条件；持续测量偏差交工程核对传感器。",
        "环境稳定后按原湿度范围复测及相关 QC。",
    ),
    "capacitance": (
        "电容或探针校准项目原判定未通过。",
        ["核对探针型号、操作员安装确认、校准结构和空气/探针/方块读数。"],
        "先确认探针与结构条件；重复异常交工程检查相关连接与感测路径。",
        "按原阈值复测电容各阶段及校准重复性。",
    ),
    "encoder_motion": (
        "编码器/运动位置项目原判定未通过。",
        ["核对方向、运动前后电机及编码器位置、偏差与是否堵转，关联同报告 encoder 附件。"],
        "先确认测试位置和运动条件；同位置重复异常交工程检查运动阻力与位置反馈。",
        "按原位置差阈值复测编码器和相关电流速度项目。",
    ),
    "current_speed": (
        "电流速度测试原判定未通过。",
        ["核对型号、电流档、方向、速度与该档是否属于必须通过范围，不将所有低电流堵转视作故障。"],
        "按对应运行配置确认阻力/驱动线索；原始数据不足时补齐该报告，不直接判定电机损坏。",
        "按同版电流速度配置复测，前置通过后补做被阻断的装配 QC。",
    ),
    "plunger_position": (
        "柱塞位置确认未通过。",
        ["核对 BLOW-OUT / DROP-TIP 所处阶段、操作员确认与实际位置记录。"],
        "由工程核对定位与装配状态，暂无 SOP 时不指定内部调整量。",
        "复测原柱塞位置项目和关联取退头动作。",
    ),
    "tip_sensor": (
        "吸头传感器或取退头项目原判定未通过。",
        ["检查实际取头/退头完成情况、吸头安装一致性和传感器触发位置。"],
        "先排除耗材或安装问题；持续触发异常交工程核对传感器与机构。",
        "按原位置标准复测取头和退头传感器项目。",
    ),
    "liquid_leak": (
        "漏液项目原判定未通过。",
        ["核对吸头规格、体积、等待时间和操作员观察，记录异常通道。", "换用已确认正常耗材复核密封，观察异常是否仍在同通道。"],
        "先排除耗材密封影响；异常固定于本体时交工程检查对应气路。",
        "按原体积和等待时长复测漏液及相关压力项目。",
    ),
    "liquid_probe": (
        "液面探测项目原判定未通过，需区分未找到液面、准确度与重复性。",
        ["核对同规格右侧参考高度、左右校准偏移、各次有效读数与吸头状态。", "保留缺失/无效试次，不能用剩余样本计算通过结论。"],
        "先确认参考和耗材条件；有效条件下仍异常再由工程核对左侧探测路径。",
        "重新参考点水并完成同规格左侧全部试次，以该次原算法和阈值判定。",
    ),
    "unclassified": (
        "记录显示失败，但当前证据不足以确定原因类别。",
        ["结合原始异常、最后动作、实际型号与现场记录补齐证据。"],
        "交品质/工程复核，暂不指定故障零件或维修工序。",
        "原因确认后复测原失败步骤及完整 QC。",
    ),
}


def _category(text: str, mode: str = "") -> str:
    text = text.lower()
    rules = [
        ("software_interface", ("unexpected keyword argument",)),
        ("sensor_support", ("requested status for sensor", "secondary not found")),
        (
            "overpressure",
            ("pipetteoverpressure", "exceeded operational limits", "压力超限"),
        ),
        ("barcode", ("test_device_id", "barcode_mismatch")),
        (
            "plunger_travel_setup",
            ("insufficient plunger travel", "insufficient remaining plunger", "柱塞行程不足"),
        ),
        (
            "right_reference",
            (
                "right a12 surface calibration failed",
                "右侧 a12 液面校准失败",
                "dut trials not run",
                "dut trials for this tip volume not run",
                "本规格左侧测量未执行",
            ),
        ),
        (
            "diagnostic_pressure",
            (
                "pressure-open-air",
                "pressure-sealed",
                "pressure-compressed",
                "diagnostic-pressure",
                "空气中气压",
                "封堵吸头气压",
                "吸液后气压",
            ),
        ),
        (
            "pressure_fixture",
            (
                "fixture",
                "pressure-pre",
                "pressure-insert",
                "pressure-holding",
                "pressure-dispensed",
                "pressure-post",
                "夹具",
            ),
        ),
        ("temperature", ("celsius-", "environment_temperature", "温度超出范围")),
        ("humidity", ("humidity-", "environment_humidity", "湿度超出范围")),
        (
            "capacitance",
            ("capacitive", "capacitance", "calibrationstructurenotfound", "电容"),
        ),
        ("current_speed", ("current_speed", "current-speed", "电流速度")),
        ("encoder_motion", ("encoder", "stall", "编码器")),
        (
            "tip_sensor",
            (
                "tip-sensor",
                "tip_pickup",
                "tip_drop",
                "tip-presence",
                "verify_tip_presence",
                "failedtipstatecheck",
                "吸头传感器",
            ),
        ),
        ("liquid_leak", ("droplets", "liquid_leak", "漏液")),
        (
            "liquid_probe",
            ("liquid-probe", "liquid_probe", "liquid_surface", "liquidnotfound", "液面"),
        ),
        ("plunger_position", ("plunger", "柱塞")),
    ]
    for category, tokens in rules:
        if any(token in text for token in tokens):
            return category
    # A run mode is not evidence of the cause of an otherwise unknown failure.
    return "unclassified"


def prepare_evidence(snapshot_dir: Path, report_name: str, config: dict) -> dict:
    """Build compact, cited context from a schema-1 protocol failure bundle.

    Only a trusted configuration may select a protocol source for SHA matching.
    No report-provided path is followed. Unknown schemas are explicitly rejected.
    """
    snapshot_dir = Path(snapshot_dir)
    path = _safe_file(snapshot_dir, report_name)
    if path.suffix.lower() != ".json":
        raise ValueError("unsupported_schema: 首版自动分析需要 schema_version=1 的 JSON 证据包")
    max_bytes = int(config.get("max_report_bytes", 20 * 1024 * 1024))
    if path.stat().st_size > max_bytes:
        raise ValueError("report_too_large: 证据包超过配置大小上限")
    try:
        data = path.read_bytes()
        bundle = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid_json: 报告未完整写入或不是有效 JSON") from error
    if (
        not isinstance(bundle, dict)
        or type(bundle.get("schema_version")) is not int
        or bundle.get("schema_version") != 1
    ):
        raise ValueError(
            "unsupported_schema: 仅支持协议失败证据包 schema_version=1；旧 App JSON 不等同于此格式"
        )
    if not isinstance(bundle.get("report_rows"), list) or not isinstance(
        bundle.get("trace"), dict
    ):
        raise ValueError("invalid_schema: schema 1 需要 report_rows 列表和 trace 对象")
    rows = bundle["report_rows"]
    trace = bundle["trace"]
    catalog: dict[str, Any] = {}
    limitations = [
        "暂无维修 SOP：只给出检查、处理方向与复测要求；内部维修交工程确认。",
        "保留报告原始判定；unknown、not_recorded、跳过和未执行均不等于 PASS。",
        "最近传感器读数不是压力保护触发瞬间数值；缺失触发值不能推测。",
        "摘要限长，截断内容及完整时间线可在原始快照复核。",
    ]

    def cite(ref: str, value: Any) -> str:
        catalog.setdefault(ref, _compact(value))
        return ref

    def item(ref: str, value: Any) -> dict:
        cite(ref, value)
        return {"evidence_ref": ref, "value": _compact(value)}

    findings: dict[str, dict] = {}
    finding_refs: dict[str, set[str]] = {}

    def finding(category: str, ref: str, value: Any) -> None:
        observed, checks, direction, retest = _RULES[category]
        entry = findings.setdefault(
            category,
            {
                "category": category,
                "status": "confirmed_configuration_issue"
                if category == "software_interface"
                else "insufficient_evidence"
                if category == "unclassified"
                else "needs_confirmation",
                "evidence_refs": [],
                "observed": observed,
                "checks": checks,
                "direction": direction,
                "retest": retest,
                "omitted_evidence_refs": 0,
            },
        )
        seen_refs = finding_refs.setdefault(category, set())
        if ref in seen_refs:
            return
        seen_refs.add(ref)
        if len(entry["evidence_refs"]) < MAX_FINDING_REFS:
            entry["evidence_refs"].append(cite(ref, value))
        else:
            entry["omitted_evidence_refs"] += 1

    mode = str(bundle.get("mode", "unknown"))
    identity = _mapping(trace.get("identity"))
    identity_result = item("trace.identity", identity)
    metadata = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        values = _list(row.get("data"))
        if (
            row.get("section") == "META_DATA"
            and values
            and row.get("tag") in ("test_device_id", "test_run_id", "test_time_utc")
        ):
            metadata[row["tag"]] = item(f"report_rows[{index}]", row)
    report_serial = _list(
        _mapping(_mapping(metadata.get("test_device_id")).get("value")).get("data")
    )
    report_serial = report_serial[0] if report_serial else None
    left = _mapping(_mapping(identity.get("actual_pipettes")).get("LEFT"))
    identity_conflict = bool(
        report_serial and left.get("serial") and report_serial != left["serial"]
    )
    if identity_conflict:
        finding("identity", "trace.identity.actual_pipettes.LEFT", left)
        finding(
            "identity",
            metadata["test_device_id"]["evidence_ref"],
            metadata["test_device_id"]["value"],
        )
        limitations.append("报告 SN 与实际 LEFT 序列号冲突；确认归属前不能将返修方案关联到特定设备。")
    if not report_serial and not left.get("serial"):
        limitations.append("报告和实际 LEFT 均缺序列号，不能以目录名替代已验证的设备身份。")

    protocol_hash = _mapping(identity.get("protocol")).get("sha256")
    source_path = config.get("protocol_source_path")
    source_comparison = {"status": "unavailable", "recorded_sha256": protocol_hash}
    if source_path:
        trusted_source = Path(source_path)
        if trusted_source.is_file():
            local_hash = hashlib.sha256(trusted_source.read_bytes()).hexdigest()
            source_comparison.update(
                local_sha256=local_hash,
                status="match"
                if protocol_hash == local_hash
                else "mismatch"
                if protocol_hash
                else "recorded_hash_missing",
            )
    if source_comparison["status"] != "match":
        limitations.append("未取得与运行哈希匹配的协议源码；只引用该次报告阈值，不用最新源码重新判定历史结果。")

    snapshot = reference_snapshot(bundle)
    blocked_volumes: dict[str, str] = {}
    events = _list(trace.get("events"))
    for index in range(len(events) - 1, -1, -1):
        volume = reference_event_volume(events[index])
        if volume is not None:
            ref = f"trace.events[{index}]"
            blocked_volumes.setdefault(str(volume), ref)
            finding("right_reference", ref, events[index])
    if snapshot:
        finding("right_reference", "stage", bundle.get("stage"))
        blocked_volumes.setdefault(str(snapshot.volume), snapshot.event_ref or "stage")
        if snapshot.handled is None:
            limitations.append("该记录属于右侧参考快照，但缺少与当前异常相符的明确 handled 事件；不能据此认定异常已被协议捕获。")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        tag = str(row.get("tag", ""))
        if re.fullmatch(r"liquid-probe-\d+-reference-error", tag) and any(
            v not in (None, "") for v in _list(row.get("data"))
        ):
            volume = tag.split("-")[2]
            blocked_volumes[volume] = f"report_rows[{index}]"
            finding("right_reference", f"report_rows[{index}]", row)
        elif row.get("result") == "FAIL" and any(
            token in _text(row).lower()
            for token in ("dut trials not run", "dut trials for this tip volume not run", "本规格左侧测量未执行")
        ):
            match = re.search(r"liquid-probe-(\d+)", tag)
            if match:
                blocked_volumes.setdefault(match.group(1), f"report_rows[{index}]")
            finding("right_reference", f"report_rows[{index}]", row)
    details = _list(bundle.get("failure_details"))
    reference_details: set[str] = set()
    for index, detail in enumerate(details):
        label = re.search(r"RIGHT\s+P1000S\s*/\s*(\d+)\s*uL\s*/\s*A12", str(detail), re.IGNORECASE)
        if label or "[QC_REFERENCE_ERROR]" in str(detail):
            reference_details.add(str(detail).strip())
        if any(token in str(detail).lower() for token in ("dut trials not run", "dut trials for this tip volume not run", "本规格左侧测量未执行")):
            ref = f"failure_details[{index}]"
            finding("right_reference", ref, detail)
            if label:
                blocked_volumes.setdefault(label.group(1), ref)

    def classify_exception(ref: str, value: Any, belongs_to_reference: bool) -> None:
        category = _category(_text(value), mode)
        if belongs_to_reference:
            finding("right_reference", ref, value)
            # Keep actionable software/protection facts alongside the workflow.
            if category in {"unclassified", "tip_sensor", "liquid_probe", "right_reference"}:
                return
        finding(category, ref, value)

    last_failure = _mapping(trace.get("last_failure"))
    runtime = _mapping(bundle.get("runtime_error"))
    execution_error = any(
        _mapping(state).get("status") in {"execution_error", "exception"}
        for state in _mapping(trace.get("tests")).values()
    )
    handled_checkpoint = bool(snapshot and snapshot.handled is True and not runtime and not execution_error)
    handled_exceptions = []
    if handled_checkpoint:
        limitations.append("这是协议已捕获的右侧参考异常快照，不是协议中止；测试执行状态保留归档时的记录。")
        if last_failure:
            ref = "trace.last_failure"
            handled_exceptions.append({"interpretation": "右侧参考流程已捕获的异常，不是协议中止起因", **item(ref, _action_view(last_failure))})
            classify_exception(ref, _action_view(last_failure), bool(_reference_failure_volume(last_failure, blocked_volumes)))
    primary = (
        item("trace.last_failure", _action_view(last_failure))
        if last_failure and not handled_checkpoint
        else item("runtime_error", runtime)
        if runtime
        else None
    )
    if primary:
        belongs_to_reference = bool(_reference_failure_volume(last_failure, blocked_volumes)) if last_failure else bool(
            snapshot and snapshot.event and runtime.get("message")
            and str(runtime["message"]) in str(snapshot.event.get("error", ""))
        )
        classify_exception(
            primary["evidence_ref"],
            primary["value"],
            belongs_to_reference,
        )
    if runtime and not last_failure:
        limitations.append("缺少最内层失败动作，顶层异常可能含清理影响；需结合原始异常链核对起因。")
    secondary = []
    if (
        runtime
        and last_failure
        and str(runtime.get("message", "")) not in str(last_failure.get("error", ""))
    ):
        secondary.append(
            {
                "kind": "outer_runtime_error_compare_with_primary",
                **item("runtime_error", runtime),
            }
        )
    for key in (
        "cleanup_error",
        "cleanup_traceback",
        "trace_error",
        "report_extraction_error",
    ):
        if bundle.get(key):
            secondary.append({"kind": key, **item(key, bundle[key])})
    for index, error in enumerate(_list(trace.get("logging_errors"))[:10]):
        secondary.append(
            {"kind": "logging_error", **item(f"trace.logging_errors[{index}]", error)}
        )
    for index, artifact in enumerate(_list(bundle.get("artifacts"))[:12]):
        artifact = _mapping(artifact)
        if artifact.get("upload_status") not in (None, "uploaded", "success"):
            secondary.append(
                {"kind": "artifact_upload", **item(f"artifacts[{index}]", artifact)}
            )
            if artifact.get("upload_status") == "pending_self_upload":
                limitations.append("JSON 的 pending_self_upload 是上传自身前写入的状态，不证明该文件上传失败。")

    failed_rows, thresholds, blocked = [], [], []
    counts: Counter = Counter()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            counts["malformed_rows"] += 1
            continue
        ref = f"report_rows[{index}]"
        counts["result_" + str(row.get("result", "unknown"))] += 1
        if row.get("record_status") == "not_recorded":
            counts["not_recorded"] += 1
        if row.get("section") in ("TEST-THRESHOLDS", "PRESSURE-CONFIGURATIONS"):
            counts["threshold_rows"] += 1
            if len(thresholds) < MAX_THRESHOLDS:
                thresholds.append(item(ref, row))
        if row.get("result") != "FAIL":
            continue
        counts["failed_rows"] += 1
        match = re.search(r"liquid-probe-(\d+)", str(row.get("tag", "")))
        is_blocked = match is not None and match.group(1) in blocked_volumes
        not_executed_cap = "capacitive-square" in str(row.get("tag", "")) and any(
            token in _text(row.get("failure_reasons", [])).lower()
            for token in ("检查未执行", "not run", "not performed")
        )
        if is_blocked:
            blocked.append(
                {
                    "evidence_ref": ref,
                    "tip_volume_ul": int(match.group(1)),
                    "status": "not_run_due_to_right_reference_failure",
                    "blocked_by": blocked_volumes[match.group(1)],
                    "original_result": "FAIL",
                }
            )
        if len(failed_rows) < MAX_FAILED_ROWS:
            failed_rows.append(
                {
                    **item(ref, row),
                    "interpretation": "前置右侧参考失败，不能据此判定左侧硬件故障"
                    if is_blocked
                    else "校准失败导致本检查未执行；数值为占位记录，不是实测零电容"
                    if not_executed_cap
                    else "原报告明确 FAIL，原因需核对",
                }
            )
        if not_executed_cap:
            blocked.append(
                {
                    "evidence_ref": ref,
                    "status": "not_run_due_to_calibration_failure",
                    "original_result": "FAIL",
                    "numeric_values_are_placeholders": True,
                }
            )
        if row.get("section") != "RESULTS_OVERVIEW":
            finding(
                "right_reference" if is_blocked else _category(_text(row), mode),
                ref,
                row,
            )

    # Summary entries can contain independent failures absent from report_rows.
    # Scan every entry while bounding the cited context, as for failed rows.
    detail_context = []
    for index, detail in enumerate(details):
        ref = f"failure_details[{index}]"
        if len(detail_context) < MAX_FAILURE_DETAILS:
            detail_context.append(item(ref, detail))
        detail_text = str(detail).strip()
        if not detail_text:
            continue
        runtime_text = re.sub(r"^\[QC_RUNTIME_ERROR\]\s*", "", detail_text)
        belongs_to_reference = detail_text in reference_details or bool(
            runtime_text and runtime_text != detail_text
            and any(runtime_text in known for known in reference_details)
        )
        classify_exception(ref, detail, belongs_to_reference)

    tests = []
    test_states = _mapping(trace.get("tests"))
    handled_total = len(handled_exceptions)
    failure_statuses = {"failed", "execution_error", "exception"}
    for name, state in test_states.items():
        state = _mapping(state)
        handled = _mapping(state.get("last_handled_exception"))
        if len(tests) < MAX_TEST_STATUSES:
            tests.append(
                {
                    "name": name,
                    **item(
                        f"trace.tests.{name}",
                        {
                            key: value
                            for key, value in state.items()
                            if key != "last_handled_exception"
                        },
                    ),
                }
            )
        if state.get("status") in failure_statuses and state.get("error"):
            error = state["error"]
            belongs_to_reference = bool(_reference_failure_volume(state, blocked_volumes))
            # Test-level errors can wrap the already captured leaf exception.
            # Match its actual error; a LIQUID-PROBE test name alone proves no side.
            state_context = reference_failure_context(state)
            if not state_context.mount and state_context.volume is None:
                for failure in (last_failure, handled):
                    original = str(failure.get("error", "")).strip()
                    if original and original in str(error):
                        belongs_to_reference = bool(_reference_failure_volume(failure, blocked_volumes))
                        break
            classify_exception(f"trace.tests.{name}.error", error, belongs_to_reference)
        if handled:
            ref = f"trace.tests.{name}.last_handled_exception"
            handled_total += 1
            if len(handled_exceptions) < MAX_HANDLED_EXCEPTIONS:
                handled_exceptions.append(
                    {
                        "interpretation": "测试已捕获的异常，不是协议中止起因",
                        **item(ref, _action_view(handled)),
                    }
                )
            # Passed tests can deliberately handle a tip-state/stall exception.
            if state.get("status") in failure_statuses:
                classify_exception(
                    ref,
                    _action_view(handled),
                    bool(name == "LIQUID-PROBE" and _reference_failure_volume(handled, blocked_volumes)),
                )
    if not findings:
        finding("unclassified", "stage", bundle.get("stage"))
        limitations.append("未找到明确 FAIL 或异常，不能由文件名推断具体故障。")
    if not tests:
        limitations.append("缺少 trace.tests，行缺失不能区分跳过、阻断或未开始。")
    if len(details) > MAX_FAILURE_DETAILS or len(test_states) > MAX_TEST_STATUSES or handled_total > MAX_HANDLED_EXCEPTIONS:
        limitations.append("失败摘要或测试状态已限长；所有条目均已检查分类，省略数量见 coverage，完整内容请核对原始快照。")
    recent_events = [
        item(f"trace.events[{index}]", events[index])
        for index in range(max(0, len(events) - MAX_EVENTS), len(events))
    ]
    readings = (
        _mapping(last_failure.get("latest_readings"))
        if last_failure
        else _mapping(trace.get("latest_readings"))
    )
    readings_prefix = (
        "trace.last_failure.latest_readings"
        if last_failure
        else "trace.latest_readings"
    )
    recent_readings = [
        {
            "interpretation": "last_observed_not_trigger_value",
            **item(f"{readings_prefix}.{name}", value),
        }
        for name, value in list(readings.items())[-12:]
    ]
    trigger = item(
        "trace.trigger_pressure", trace.get("trigger_pressure", {"status": "unknown"})
    )
    if not thresholds:
        limitations.append("未记录阈值配置，无法复核数值边界或聚合判据；需取得运行时规则。")
    if (
        counts["failed_rows"] > MAX_FAILED_ROWS
        or counts["threshold_rows"] > MAX_THRESHOLDS
    ):
        limitations.append("报告行摘要已截断；所有原判定仍保留在快照，必须复核省略项目。")

    if any(item.get("numeric_values_are_placeholders") for item in blocked):
        limitations.append("校准方块检查明确未执行时，记录的 0 是占位值，不能解释为传感器实测零电容。")
    relevant_categories = set(findings)
    threshold_tokens = {
        "temperature": ("temperature",),
        "humidity": ("humidity",),
        "capacitance": ("capacitive", "probe-deck"),
        "diagnostic_pressure": ("pressure-",),
        "right_reference": ("liquid-probe",),
        "liquid_probe": ("liquid-probe",),
        "encoder_motion": ("encoder",),
        "current_speed": ("current", "speed", "encoder"),
    }
    applicable_thresholds = [
        entry
        for entry in thresholds
        if (
            entry["value"].get("section") == "PRESSURE-CONFIGURATIONS"
            and "pressure_fixture" in relevant_categories
        )
        or any(
            token in str(entry["value"].get("tag", ""))
            for category in relevant_categories
            for token in threshold_tokens.get(category, ())
        )
    ]

    def failure_order(entry: dict) -> tuple:
        is_primary = bool(primary and primary["evidence_ref"] in entry["evidence_refs"])
        times = [
            catalog[ref].get("elapsed_seconds")
            for ref in entry["evidence_refs"]
            if isinstance(catalog.get(ref), dict)
        ]
        numeric_times = [
            value
            for value in times
            if isinstance(value, (int, float)) and math.isfinite(value)
        ]
        return (
            0 if is_primary else 1,
            min(numeric_times) if numeric_times else float("inf"),
        )

    ordered_findings = sorted(findings.values(), key=failure_order)
    for index, entry in enumerate(ordered_findings, start=1):
        entry["id"] = f"F{index}"
        entry["threshold_evidence_refs"] = [
            row["evidence_ref"]
            for row in applicable_thresholds
            if (
                row["value"].get("section") == "PRESSURE-CONFIGURATIONS"
                and entry["category"] == "pressure_fixture"
            )
            or any(
                token in str(row["value"].get("tag", ""))
                for token in threshold_tokens.get(entry["category"], ())
            )
        ]

    encoder = _encoder_summary(snapshot_dir, path.stem + ".encoder.csv")
    if encoder["status"] == "summarized":
        cite("encoder_summary", encoder)
    return {
        "schema_version": 1,
        "rules_version": RULES_VERSION,
        "source_report": report_name,
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "report_identity": {
            "run_id": bundle.get("run_id"),
            "report_run_id": bundle.get("report_run_id"),
            "mode": mode,
            "failure_created_at_utc": bundle.get("created_at_utc"),
            "metadata": metadata,
            "report_serial": report_serial,
            "actual_left_serial": left.get("serial"),
            "identity_conflict": identity_conflict,
        },
        "identity": identity_result,
        "protocol_source_comparison": source_comparison,
        "parameters": item("parameters", bundle.get("parameters", {})),
        "labware": item("trace.labware", trace.get("labware", {})),
        "stage": item("stage", bundle.get("stage")),
        "test_statuses": tests,
        "handled_exceptions": handled_exceptions,
        "primary_failure": primary,
        "failed_rows": failed_rows,
        "failure_details": detail_context,
        "thresholds": thresholds,
        "applicable_thresholds": applicable_thresholds,
        "recent_readings": recent_readings,
        "trigger_pressure": trigger,
        "recent_events": recent_events,
        "secondary_errors": secondary,
        "blocked_tests": blocked[:MAX_FAILED_ROWS],
        "deterministic_findings": ordered_findings,
        "limitations": list(dict.fromkeys(limitations)),
        "coverage": {
            "report_rows_total": len(rows),
            **dict(counts),
            "failed_rows": counts["failed_rows"],
            "threshold_rows": counts["threshold_rows"],
            "failed_rows_in_context": len(failed_rows),
            "failure_details_total": len(details),
            "failure_details_in_context": len(detail_context),
            "failure_details_omitted": max(0, len(details) - len(detail_context)),
            "test_statuses_total": len(test_states),
            "test_statuses_in_context": len(tests),
            "test_statuses_omitted": max(0, len(test_states) - len(tests)),
            "handled_exceptions_total": handled_total,
            "handled_exceptions_omitted": max(0, handled_total - len(handled_exceptions)),
            "threshold_rows_in_context": len(thresholds),
            "events_total": len(events),
            "events_in_context": len(recent_events),
            "blocked_rows_total": len(blocked),
            "finding_refs_omitted": sum(
                f["omitted_evidence_refs"] for f in findings.values()
            ),
        },
        "encoder_summary": encoder,
        "evidence_catalog": catalog,
    }

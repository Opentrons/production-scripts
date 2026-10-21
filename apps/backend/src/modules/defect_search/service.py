from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
import threading
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from . import guidance, normalization, repository


DATA_DIR = Path(os.getenv("PRODUCTION_PLATFORM_DATA_DIR", Path(__file__).parents[3] / "data"))
INDEX_DIR = DATA_DIR / "defect-search"
DATA_PATH = Path(os.getenv("PRODUCTION_PLATFORM_DEFECT_SEED_PATH", INDEX_DIR / "seed.csv"))
DATABASE_PATH = DATA_DIR / "defect-search" / "knowledge.sqlite3"
_database_lock = threading.Lock()
MODEL_CACHE_DIR = INDEX_DIR / "model-cache"
VECTOR_CACHE_PATH = INDEX_DIR / "embeddings.npz"
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
MIN_VECTOR_SCORE = 0.42
logger = logging.getLogger(__name__)
SEARCH_FIELDS = ("defect_description", "symptom_normalized", "symptom_category")
GENERIC_CATEGORIES = {"", "其他", "其他/待归类", "待归类", "未分类"}
ACTION_WORDS = re.compile(r"^(?:复测|重测|更换|换件|换主板|重装|重新安装|调整|维修|清洁|清理|润滑|重新烧录|烧录|重启)|^老化后复测$")
CHANNEL_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*(?:ch|通道)(?![a-z])|(?:ch|通道)\s*(\d{1,2})(?!\d)", re.I)
VECTOR_FIELDS = (
    "product", "defect_code", "station", "symptom_category", "symptom_normalized",
    "defect_description",
)
SEARCH_SYNONYMS = {
    "机子": ("机器", "设备", "整机", "机台"), "机器": ("机子", "设备", "整机", "机台"),
    "设备": ("机子", "机器", "整机", "机台"), "整机": ("机子", "机器", "设备", "机台"),
    "机台": ("机子", "机器", "设备", "整机"), "噪音": ("异响", "噪声"),
    "噪声": ("异响", "噪音"), "异响": ("噪音", "噪声"),
    "漏水": ("漏液", "leak"), "漏液": ("漏水", "leak"), "leak": ("漏液", "漏水"),
}
_index_lock = threading.Lock()
_model: Any = None
_case_vectors: np.ndarray | None = None
_case_vector_hash: str | None = None


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _compact(value: Any) -> str:
    return re.sub(r"[\s\W_]+", "", repository.normalize_seconds(_clean(value)), flags=re.UNICODE)


def _query_variants(value: str) -> list[str]:
    compact = _compact(value)
    variants = {compact} if compact else set()
    for term, synonyms in SEARCH_SYNONYMS.items():
        if term in compact:
            variants.update(compact.replace(term, synonym) for synonym in synonyms)
    return list(variants)


def _partial_similarity(query: str, value: str) -> float:
    if not query or not value:
        return 0.0
    if query in value:
        return 1.0
    if len(query) < 3:
        return 0.0
    # Align around the longest common block, rather than comparing every
    # sliding window in every field of the entire database.
    block = SequenceMatcher(None, query, value, autojunk=False).find_longest_match()
    if not block.size:
        return 0.0
    best = 0.0
    anchor = block.b - block.a
    for start in range(max(0, anchor - 1), min(len(value), anchor + 2)):
        for size in (len(query) - 1, len(query), len(query) + 1):
            best = max(best, SequenceMatcher(None, query, value[start:start + size], autojunk=False).ratio())
    return best


def _minimum_similarity(query: str) -> float:
    if len(query) <= 2:
        return 1.0
    return 0.50 if len(query) <= 4 else 0.42


def _date_key(value: str) -> datetime:
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?", value)
    if not match:
        return datetime.min
    try:
        return datetime(*(int(part or 0) for part in match.groups()))
    except ValueError:
        return datetime.min


def _load_cases() -> tuple[dict[str, str], ...]:
    with _database_lock:
        return repository.load_cases(DATABASE_PATH, DATA_PATH)


def get_local_case(record_id: int) -> dict[str, str] | None:
    return next((case for case in _load_cases() if case["local_id"] == str(record_id)), None)


def get_options() -> dict[str, list[str]]:
    cases = _load_cases()
    return {
        "product": sorted({normalization.canonical_product(case.get("product", "")) for case in cases if case.get("product")}, key=str.casefold),
        **{key: sorted({case.get(key, "") for case in cases if case.get(key)}, key=str.casefold)
           for key in ("station", "defect_code")},
    }


def get_summary(cases: tuple[dict[str, str], ...] | None = None) -> dict[str, int]:
    if cases is None:
        cases = _load_cases()
    return {
        "total_cases": len(cases),
        "capacity_cases": sum(case.get("symptom_category") == "容量测试失败" for case in cases),
        "capacity_retest_cases": sum(case.get("symptom_category") == "容量测试失败" and case.get("containment_action") == "复测" for case in cases),
        "root_cause_cases": sum(bool(case.get("root_cause")) for case in cases),
        **repository.statistics(DATABASE_PATH, cases),
    }


def _vector_document(case: dict[str, str]) -> str:
    return "\n".join(f"{field}: {case[field]}" for field in VECTOR_FIELDS if case.get(field))


def _normalized(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def _ensure_vector_index(cases: tuple[dict[str, str], ...]) -> tuple[Any, np.ndarray]:
    global _model, _case_vectors, _case_vector_hash
    documents = [_vector_document(case) for case in cases]
    digest = hashlib.sha256((MODEL_NAME + "\0symptoms-v2\0" + "\0".join(documents)).encode("utf-8")).hexdigest()
    with _index_lock:
        if _case_vectors is not None and _case_vector_hash == digest and _model is not None:
            return _model, _case_vectors
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        if _model is None:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(MODEL_CACHE_DIR), local_files_only=True)
        if VECTOR_CACHE_PATH.exists():
            try:
                with np.load(VECTOR_CACHE_PATH, allow_pickle=False) as cache:
                    if str(cache["dataset_hash"].item()) == digest and cache["vectors"].shape[0] == len(documents):
                        _case_vectors = cache["vectors"].astype(np.float32, copy=False)
                        _case_vector_hash = digest
                        return _model, _case_vectors
            except (OSError, ValueError, KeyError):
                pass
        vectors = _normalized(np.vstack(list(_model.embed(documents, batch_size=32))).astype(np.float32))
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=INDEX_DIR, suffix=".npz", delete=False) as temporary_file:
                temporary_path = Path(temporary_file.name)
                np.savez_compressed(temporary_file, dataset_hash=np.asarray(digest), vectors=vectors)
            os.replace(temporary_path, VECTOR_CACHE_PATH)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
        _case_vectors = vectors
        _case_vector_hash = digest
        return _model, vectors


def _lexical_similarity(query_text: str, query_tokens: list[str], variants: list[str], case: dict[str, str]) -> tuple[float, bool]:
    searchable = [_symptom_text(case.get(field, "")) for field in SEARCH_FIELDS if case.get(field)]
    terms = query_tokens or [query_text]
    scores = [max((_partial_similarity(_symptom_text(term), value) for value in searchable), default=0.0)
              for term in terms if term]
    if not scores:
        return 0.0, False
    # Every symptom term contributes. A single word such as "复测" in an
    # unrelated containment action can no longer make the defect an exact hit.
    coverage = sum(score >= 0.65 for score in scores) / len(scores)
    score = (sum(scores) / len(scores)) * coverage
    exact = all(term_score == 1.0 for term_score in scores)
    return score, exact


def _query_terms(query: str) -> list[str]:
    return normalization.symptom_terms(query)


def _extract_failed_action(query: str) -> tuple[str, str]:
    """Recognize an explicit failed retest without filtering out its history."""
    pattern = re.compile(
        r"(?:已(?:经)?|尝试)?(?:复测|重测|重新测试|(?<![a-z])re-?test)(?:过)?(?:后)?[\s,，;；:：]*"
        r"(?:(?:仍(?:然)?|还是|依旧)\s*)?(?:无效|未通过|不通过|没通过|无改善|失败|(?:fail(?:ed|ure)?|ng)(?![a-z]))",
        re.IGNORECASE,
    )
    if not pattern.search(query):
        return query, ""
    return pattern.sub(" ", query).strip(), "复测"


def _split_action_query(query: str, action: str) -> tuple[str, str]:
    tokens = re.split(r"[\s,，;；]+", query.strip())
    def is_action(token: str) -> bool:
        # “重启失败/老化测试失败” are observed symptoms, rather than actions.
        return bool(ACTION_WORDS.match(token) and not re.search(
            r"失败|不成功|无效|未通过|不通过|没通过|无改善|仍|复发|后.*(?:漏液|漏水|异响|黑屏|不亮)|fail|(?<![a-z])ng(?![a-z])", token, re.I))
    actions: list[str] = []
    symptoms: list[str] = []
    in_action = False
    for token in tokens:
        if not token:
            continue
        if is_action(token):
            in_action = True
            actions.append(token)
        elif re.search(r"漏液|漏水|异响|黑屏|不亮|失败|复发|fail|(?<![a-z])ng(?![a-z])", token, re.I):
            in_action = False
            symptoms.append(token)
        elif in_action:
            # Preserve separated parameters: “更换 913-00041 / 调整 电磁铁”.
            actions.append(token)
        else:
            symptoms.append(token)
    if len(tokens) == 1 and not actions:
        # Common unspaced shop-floor wording: 漏液复测 / 漏液更换913-00041.
        match = re.fullmatch(r"(.*?(?:漏液|漏水|异响|黑屏|不亮|失败|fail|ng))\s*(复测|重测|更换.*|调整.*)", query, re.I)
        if match:
            symptoms, actions = [match[1]], [match[2]]
    return " ".join(symptoms).strip(), " ".join(filter(None, [action.strip(), *actions]))


def _extract_serials(query: str, cases: tuple[dict[str, str], ...]) -> tuple[str, set[str]]:
    remaining = query
    serials: set[str] = set()
    prefix = re.compile(r"(?:\bs\s*/?\s*n|序列号)\s*[:：]?\s*([a-z\d][a-z\d-]{5,})", re.I)
    for match in prefix.finditer(query):
        serials.add(_compact(match[1]))
    remaining = prefix.sub(" ", remaining)
    for serial in {case.get("serial_number", "") for case in cases}:
        if len(serial) < 7 or not re.search(r"[a-z]", serial, re.I) or not re.search(r"\d", serial):
            continue
        pattern = re.compile(r"(?<![a-z\d])" + re.escape(serial) + r"(?![a-z\d])", re.I)
        if pattern.search(remaining):
            serials.add(_compact(serial))
            remaining = pattern.sub(" ", remaining)
    return remaining.strip(), serials


def _action_matches(action: str, case: dict[str, str]) -> bool:
    if not action:
        return True
    raw = " ".join((case.get("containment_action", ""), case.get("exchange_component", "")))
    value = _compact(raw).replace("重测", "复测")
    for term in re.split(r"[\s,，;；]+", action):
        if not term:
            continue
        if re.fullmatch(r"\d{3}-\d{5}", term):
            if not re.search(r"(?<!\d)" + re.escape(term) + r"(?!\d)", raw):
                return False
        elif _compact(term).replace("重测", "复测") not in value:
            return False
    return True


def _channels(value: str) -> set[str]:
    return {str(int(match[1] or match[2])) for match in CHANNEL_PATTERN.finditer(value)}


def _extract_query_labels(query: str, cases: tuple[dict[str, str], ...]) -> tuple[str, dict[str, set[str]]]:
    """Treat model names and defect codes in the input as actual constraints."""
    remaining = query
    inferred: dict[str, set[str]] = {"product": set(), "defect_code": set(), "station": set()}
    for field in inferred:
        labels = sorted({normalization.canonical_product(case.get(field, "")) if field == "product" else case.get(field, "")
                         for case in cases if case.get(field)}, key=len, reverse=True)
        for label in labels:
            # ASCII boundaries allow Chinese immediately beside a model name,
            # while preventing Gripper from matching inside Gripper-MINI.
            label_pattern = normalization.product_pattern(label) if field == "product" else re.escape(label)
            if field == "station":
                # A test name within a symptom (容量测试失败/协议测试过程中
                # 黑屏) is not an explicit station filter. Those faults may
                # also have been reported at a different diagnostic station.
                pattern = re.compile(r"(?<!\w)" + label_pattern + r"(?!\w)", re.IGNORECASE)
                def extract_station(match: re.Match[str]) -> str:
                    following = remaining[match.end():]
                    if re.match(r"[\s_-]*(?:失败|异常|故障|报错|不通过|未通过|过程中|后|时|fail(?:ed|ure)?\b|ng\b)", following, re.I):
                        return match[0]
                    inferred[field].add(_compact(label))
                    return " "
                remaining = pattern.sub(extract_station, remaining)
                continue
            pattern = re.compile(r"(?<![a-z\d-])" + label_pattern + r"(?![a-z\d-])", re.IGNORECASE)
            if pattern.search(remaining):
                inferred[field].add(_compact(label))
                remaining = pattern.sub(" ", remaining)
        if field == "product":
            # A family abbreviation constrains the family and leaves variant
            # selection to the user; it never silently selects G3 over MINI.
            families = {label.split("-")[0] for label in labels if "-" in label}
            for family in sorted(families, key=len, reverse=True):
                if family in labels:
                    continue
                pattern = re.compile(r"(?<![a-z\d-])" + re.escape(family) + r"(?![a-z\d-])", re.I)
                if pattern.search(remaining):
                    inferred[field].update(_compact(label) for label in labels if label.startswith(family + "-"))
                    remaining = pattern.sub(" ", remaining)
    return remaining.strip(), inferred


def _capacity_query(query_text: str) -> bool:
    query_text = normalization.normalize_symptom(CHANNEL_PATTERN.sub("", query_text))
    return query_text in {
        "容量", "容量测试", "容量失败", "容量测试ng", "容量测试失败", "容量测试fail", "容量ng",
        "capacitytest", "capacitytestng", "capacitytestfail", "capacitytestfailure", "capacityfailure",
        "capacitytest失败", "capacity失败",
    }


def _capacity_case(case: dict[str, str]) -> bool:
    return (case.get("symptom_category") == "容量测试失败"
            or _compact(case.get("defect_code", "")) == _compact("P+PC004"))


def _symptom_text(value: str) -> str:
    return normalization.normalize_symptom(value)


def _symptom_exact(query: str, case: dict[str, str]) -> bool:
    # Measures, cause notes and replacement parts are intentionally excluded:
    # mentioning a symptom in an action is not evidence of that defect.
    description = case.get("defect_description", "")
    durations = repository.duration_values(query)
    if durations and not durations.issubset(repository.duration_values(description)):
        return False
    if _channels(query) and not _channels(query).issubset(_channels(description)):
        return False
    query_text = _symptom_text(query)
    if _capacity_query(query_text):
        return _capacity_case(case)
    # Temporal clauses and multiple numeric parameters retain their order;
    # unordered tokens must not reverse a stage or swap speed/current values.
    if normalization.ordered_symptom(query) and query_text not in _symptom_text(description):
        return False
    # Other words may change order. Numbers and channels are checked
    # separately, so 60 seconds never matches 160 seconds by substring.
    residual = CHANNEL_PATTERN.sub("", repository.SECOND_PATTERN.sub("", query))
    description = CHANNEL_PATTERN.sub("", repository.SECOND_PATTERN.sub("", description))
    if not _compact(residual):
        return bool(durations or _channels(query))
    return all(term in _symptom_text(description) for term in _query_terms(residual))


def _generic_query(query_text: str) -> bool:
    return (len(query_text) < 2 or bool(re.fullmatch(
                r"(?:[+-]?\d+(?:\.\d+)?(?:秒|℃|度|c|mm|ma|v|ch|通道)?|"
                r"(?:ch|通道)\d+|[a-h](?:1[0-2]|[1-9])|[xyz]轴)+", query_text, re.I))
            or query_text in {
                "机子", "机器", "设备", "整机", "机台", "ng", "fail", "failure", "失败", "异常", "报错", "问题", "故障", "测试",
                "老化", "老化测试",
                "移液器", "夹爪", "电机", "主板", "传感器", "风扇", "吸嘴", "针管", "电磁铁", "电路板", "吸头", "密封圈",
                "pipette", "motor", "mainboard", "sensor", "fan", "nozzle", "electromagnet",
            })


def _similar_evidence(ranked: list[tuple[float, float, datetime, dict[str, str]]]) -> list[dict[str, str]]:
    # Only the closest strong semantic neighbours support an action summary.
    # Their vectors contain symptoms, never action/cause text.
    strongest = max((similarity for _, similarity, _, _ in ranked), default=0.0)
    if strongest < 0.70:
        return []
    close = [case for _, similarity, _, case in ranked if similarity >= max(0.70, strongest - 0.06)]
    if not close:
        return []
    anchor = max(ranked, key=lambda item: item[1])[3]
    category = anchor.get("symptom_category", "")
    if not category or category in {"其他", "其他/待归类", "待归类", "未分类"}:
        return [case for case in close if _symptom_text(case.get("defect_description", "")) == _symptom_text(anchor.get("defect_description", ""))]
    return [case for case in close if case.get("symptom_category") == category
            and case.get("defect_code", "") == anchor.get("defect_code", "")]


def _scope_action_evidence(query: str, basis: str, cases: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep a named failure separate from related or compound failures.

    Resolve each model independently: an unclassified result for one model
    must not discard the clear history of another. Duration searches retain
    their established numeric scope (including recorded channel variants).
    """
    groups: dict[str, list[dict[str, str]]] = {}
    for case in cases:
        groups.setdefault(normalization.canonical_product(case.get("product", "")), []).append(case)
    selected = []
    duration_query = bool(repository.duration_values(query))
    for members in groups.values():
        complete = [case for case in members if basis == "exact" and query
                    and normalization.complete_symptom(query, case.get("defect_description", ""))]
        mixed_unknown = (any(case.get("symptom_category", "") in GENERIC_CATEGORIES for case in members)
                         and len({_symptom_text(case.get("defect_description", "")) for case in members}) > 1)
        if complete and (not duration_query or mixed_unknown):
            selected.extend(complete)
        elif not mixed_unknown:
            selected.extend(members)
    return selected


def _scenario_advice(cases: list[dict[str, str]], attempted_action: str) -> list[dict[str, Any]]:
    """Offer distinct, sourced scenarios when one shared action is unsupported."""
    groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for case in cases:
        key = (normalization.canonical_product(case.get("product", "")), case.get("station", ""),
               case.get("defect_code", ""), _symptom_text(case.get("defect_description", "")))
        groups.setdefault(key, []).append(case)
    options: list[dict[str, Any]] = []
    ordered = sorted(groups.values(), key=lambda members: (
        len(members), max(_date_key(case.get("date", "")) for case in members)), reverse=True)
    for members in ordered:
        recommendations = repository.recommend(
            DATABASE_PATH, members, exclude_action=attempted_action, exclude_retest=bool(attempted_action),
        )
        if not recommendations or not recommendations[0]["actions"]:
            continue
        group = recommendations[0]
        actions = group["actions"]
        for action in actions:
            if action["count"] != actions[0]["count"]:
                break
            options.append({
                "product": group["product"], "description": members[0].get("defect_description", ""),
                "action": action["action"], "count": action["count"], "matched_cases": group["matched_cases"],
                "stations": group["stations"], "defect_codes": group["defect_codes"], "sources": action["sources"],
            })
            if len(options) == 6:
                return options
    return options


def _missing_advice_conditions(query: str, cases: list[dict[str, str]]) -> list[str]:
    """Expose omitted source qualifiers without changing retrieval or scores."""
    descriptions = list(dict.fromkeys(
        _clean(case.get("defect_description", "")) for case in cases
        if case.get("defect_description")
        and not normalization.complete_symptom(query, case["defect_description"])
    ))
    if not descriptions:
        return []
    patterns = (
        ("通道", re.compile(
            r"(?<!\d)\d{1,2}\s*(?:[-~～至到]\s*\d{1,2}\s*)?(?:个\s*)?(?:ch|通道)(?![a-z])|"
            r"(?<![a-z\d])(?:ch|通道)\s*\d{1,2}(?:\s*[-~～至到]\s*\d{1,2})?(?!\d)", re.I)),
        ("位置", re.compile(
            r"(?<![a-z])[a-h]\s*(?:1[0-2]|[1-9])(?!\d)|[xyz]\s*轴|"
            r"左(?:侧|边)|右(?:侧|边)|前端|后端|上端|下端|顶部|底部", re.I)),
        ("故障阶段", re.compile(
            r"[\w″”\"℃.\-]{1,24}?(?:过程中|之前|之后|前|后|时)|"
            r"(?<![a-z])(?:before|after|during|while)\s+[^,，;；。]{1,40}", re.I)),
    )

    def summarize(values: list[str]) -> str:
        return " / ".join(values[:3]) + (f" 等（共 {len(values)} 种）" if len(values) > 3 else "")

    missing: list[str] = []
    for label, pattern in patterns:
        values: list[str] = []
        for description in descriptions:
            for match in pattern.finditer(description):
                detail = match[0]
                if (label == "通道" and normalization.symptom_conditions_match(detail, query)):
                    continue
                if label != "通道" and _symptom_text(detail) in _symptom_text(query):
                    continue
                if detail not in values:
                    values.append(detail)
        if values:
            missing.append(f"需确认{label}：来源案例为 {summarize(values)}")
    # A remaining qualifier can be an additional fault, component or an
    # uncommon stage not covered by the labels above. Preserve its full text.
    missing.append("需确认完整现象与来源案例一致：" + summarize(descriptions))
    return missing


def search_cases(*, query: str = "", product: str = "", station: str = "", defect_code: str = "",
                 action: str = "", page: int = 1, page_size: int = 20) -> dict[str, Any]:
    cases = _load_cases()
    remaining, serials = _extract_serials(query, cases)
    remaining, inferred = _extract_query_labels(remaining, cases)
    remaining, attempted_action = _extract_failed_action(remaining)
    parts = re.findall(r"(?<!\d)\d{3}-\d{5}(?!\d)", remaining)
    if parts:
        remaining = re.sub(r"(?<!\d)\d{3}-\d{5}(?!\d)", " ", remaining)
    symptom_query, action_filter = _split_action_query(remaining, action)
    action_filter = " ".join(filter(None, [action_filter, *parts]))
    query_text = _symptom_text(symptom_query)
    query_tokens = _query_terms(symptom_query)
    variants = _query_variants(symptom_query)
    durations = repository.duration_values(symptom_query)
    channels = _channels(symptom_query)
    identifier_query = bool(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]{7,}", symptom_query)
                            and len(re.findall(r"\d", symptom_query)) >= 6 and not durations and not channels)
    filters = {"product": _compact(normalization.canonical_product(product)),
               "station": _compact(station), "defect_code": _compact(defect_code)}

    def field_value(case: dict[str, str], field: str) -> str:
        value = case.get(field, "")
        return _compact(normalization.canonical_product(value) if field == "product" else value)

    candidates = [(index, case) for index, case in enumerate(cases)
                  if not any(value and field_value(case, field) != value for field, value in filters.items())
                  and not any(values and field_value(case, field) not in values for field, values in inferred.items())
                  and (not durations or durations.issubset(repository.duration_values(case.get("defect_description", ""))))
                  and (not channels or channels.issubset(_channels(case.get("defect_description", ""))))
                  and (identifier_query or normalization.symptom_conditions_match(symptom_query, case.get("defect_description", "")))
                  and (not serials or _compact(case.get("serial_number", "")) in serials)
                  and _action_matches(action_filter, case)]
    search_mode = "browse"
    recommendation_basis = "none"
    evidence_cases: list[dict[str, str]] = []
    # Displayed score is the same fused score that determines result order.
    ranked: list[tuple[float, float, datetime, dict[str, str]]] = []
    reasons: dict[str, str] = {}
    if identifier_query:
        for _, case in candidates:
            serial = _compact(case.get("serial_number", ""))
            serial_match = bool(serial and query_text in serial)
            if not serial_match:
                continue
            score = 1.0 if query_text == serial else 0.95
            ranked.append((score, score, _date_key(case.get("date", "")), case))
            reasons[case["local_id"]] = "serial_exact" if serial_match and score == 1.0 else "keyword"
        search_mode = "exact"
    elif query_text:
        exact_cases = [case for _, case in candidates if _symptom_exact(symptom_query, case)]
        if exact_cases:
            ranked = [(1.0, 1.0, _date_key(case.get("date", "")), case) for case in exact_cases]
            reasons.update({case["local_id"]: "duration_exact" if durations else "symptom_exact" for case in exact_cases})
            search_mode = "exact"
            if not _generic_query(query_text):
                evidence_cases = exact_cases
                recommendation_basis = "exact"
        elif not candidates:
            search_mode = "exact"
        else:
            try:
                model, vectors = _ensure_vector_index(cases)
                expanded_query = symptom_query
                for term, synonyms in SEARCH_SYNONYMS.items():
                    if term in symptom_query:
                        expanded_query += " " + " ".join(synonyms)
                query_vector = _normalized(np.asarray(list(model.embed([QUERY_INSTRUCTION + expanded_query]))[0], dtype=np.float32).reshape(1, -1))[0]
                indices = np.fromiter((index for index, _ in candidates), dtype=np.int64)
                semantic_scores = vectors[indices] @ query_vector
                for (_, case), semantic_score in zip(candidates, semantic_scores):
                    lexical_score, _ = _lexical_similarity(query_text, query_tokens, variants, case)
                    # Multiple requested symptoms must all have lexical support;
                    # a strong vector for just one term is insufficient.
                    if len(query_tokens) > 1 and any(
                        max((_partial_similarity(term, _symptom_text(case.get(field, ""))) for field in SEARCH_FIELDS), default=0.0) < 0.50
                        for term in query_tokens
                    ):
                        continue
                    if semantic_score < MIN_VECTOR_SCORE and lexical_score < _minimum_similarity(query_text):
                        continue
                    similarity = max(0.0, min(1.0, float(semantic_score)))
                    relevance = min(0.99, 0.82 * similarity + 0.18 * lexical_score)
                    ranked.append((relevance, similarity, _date_key(case.get("date", "")), case))
                    reasons[case["local_id"]] = "semantic" if semantic_score >= MIN_VECTOR_SCORE else "fuzzy"
                search_mode = "semantic"
                if not _generic_query(query_text):
                    evidence_cases = _similar_evidence(ranked)
                    if evidence_cases:
                        recommendation_basis = "similar"
            except Exception:
                logger.warning("Local semantic defect search unavailable; using lexical matching", exc_info=True)
                ranked = []
                reasons = {}
                for _, case in candidates:
                    lexical_score, _ = _lexical_similarity(query_text, query_tokens, variants, case)
                    if len(query_tokens) > 1 and any(
                        max((_partial_similarity(term, _symptom_text(case.get(field, ""))) for field in SEARCH_FIELDS), default=0.0) < 0.50
                        for term in query_tokens
                    ):
                        continue
                    if lexical_score < _minimum_similarity(query_text):
                        continue
                    ranked.append((min(0.99, lexical_score), lexical_score, _date_key(case.get("date", "")), case))
                    reasons[case["local_id"]] = "fuzzy"
                search_mode = "fuzzy_fallback"
    else:
        ranked = [(1.0, 1.0, _date_key(case.get("date", "")), case) for _, case in candidates]
        reasons.update({case["local_id"]: "serial_exact" if serials else "keyword" if action_filter else "browse" for _, case in candidates})
        capacity_code = (filters["defect_code"] == _compact("P+PC004")
                         or _compact("P+PC004") in inferred["defect_code"])
        if capacity_code or ((filters["station"] or inferred["station"])
                             and (filters["defect_code"] or inferred["defect_code"])):
            categories = {case.get("symptom_category", "") for _, case in candidates}
            if len(categories) == 1 and not categories.intersection(GENERIC_CATEGORIES):
                evidence_cases = [case for _, case in candidates]
                recommendation_basis = "filtered"

    ranked.sort(key=lambda item: (item[0],
                                 normalization.complete_symptom(symptom_query, item[3].get("defect_description", ""))
                                 if query_text and search_mode == "exact" else False,
                                 item[2]), reverse=True)
    total = len(ranked)
    start = (page - 1) * page_size
    selected = []
    for relevance, _, _, case in ranked[start:start + page_size]:
        selected_case = dict(case)
        selected_case["match_score"] = str(round(relevance * 100))
        selected_case["match_reason"] = reasons.get(case["local_id"], "browse")
        selected.append(selected_case)

    # Only an explicit capacity symptom/code or exact capacity evidence can
    # activate the user's retest rule. A station label alone cannot do so.
    capacity_code = (filters["defect_code"] == _compact("P+PC004")
                     or _compact("P+PC004") in inferred["defect_code"])
    is_capacity_failure = bool(not identifier_query and (
        _capacity_query(symptom_query)
        or (recommendation_basis in {"exact", "filtered"} and evidence_cases
            and all(_capacity_case(case) for case in evidence_cases))
        or (not query_text and capacity_code)))
    reference_cases = evidence_cases
    if evidence_cases and not is_capacity_failure:
        evidence_cases = _scope_action_evidence(symptom_query, recommendation_basis, evidence_cases)
        if not evidence_cases:
            recommendation_basis = "none"
    recommendations = repository.recommend(
        DATABASE_PATH, evidence_cases, retest_first=is_capacity_failure and not attempted_action,
        exclude_action=attempted_action, exclude_retest=bool(attempted_action),
    )
    action_counts: dict[str, int] = {}
    for group in recommendations:
        for entry in group["actions"]:
            action_counts[entry["action"]] = action_counts.get(entry["action"], 0) + entry["count"]
    actions = [{"action": value, "count": count} for value, count in sorted(action_counts.items(), key=lambda item: item[1], reverse=True)[:5]]
    matched_products = {normalization.canonical_product(case.get("product", ""))
                        for _, _, _, case in ranked if case.get("product")}
    known_product = normalization.canonical_product(product)
    if not known_product and len(matched_products) == 1:
        known_product = next(iter(matched_products))
    first_step = guidance.first_step(
        requested=bool(_clean(query) or product or station or defect_code or action),
        has_symptom=bool(query_text) and not identifier_query,
        generic_symptom=_generic_query(query_text) if query_text and not identifier_query else False,
        needs_detail=query_text in {"漏液", "异响", "黑屏", "不亮", "黄灯", "报警", "运行失败"},
        capacity_failure=is_capacity_failure, basis=recommendation_basis,
        recommendations=recommendations, total=total, product=known_product, products=sorted(matched_products),
        attempted_action=attempted_action,
    )
    if first_step is not None and first_step["kind"] in {"historical", "reference"}:
        selected_action = first_step["action"].casefold()
        action_cases = [case for case in evidence_cases
                        if normalization.normalized_action(
                            case.get("containment_action", ""), case.get("serial_number", "")
                        ).casefold() == selected_action]
        missing_conditions = _missing_advice_conditions(symptom_query, action_cases)
        if missing_conditions:
            first_step["kind"] = "reference"
            if first_step["reason"] == "history":
                first_step["reason"] = "broad_symptom"
            first_step["conditions"].extend(missing_conditions)
    if first_step is not None and not recommendations and reference_cases and not _generic_query(query_text):
        first_step["alternatives"] = _scenario_advice(reference_cases, attempted_action)
        if first_step["alternatives"]:
            first_step["next_step"] = {
                "kind": "engineering_review", "action": "选择与本次现象一致的场景，查看该场景的处理建议。",
                "count": 0, "sources": [],
                "note": "以下措施分别来自不同故障场景；可按本次实际型号、工站和现象选择场景，也可补充描述重新检索或提交工程分析。",
            }
    constrained_products = sorted({normalization.canonical_product(case.get("product", "")) for case in cases
                                  if case.get("product") and (filters["product"] or inferred["product"])
                                  and (not filters["product"] or field_value(case, "product") == filters["product"])
                                  and (not inferred["product"] or field_value(case, "product") in inferred["product"])})
    constrained_stations = sorted({case.get("station", "") for case in cases if case.get("station")
                                  and (filters["station"] or inferred["station"])
                                  and (not filters["station"] or field_value(case, "station") == filters["station"])
                                  and (not inferred["station"] or field_value(case, "station") in inferred["station"])})
    return {
        "total": total, "page": page, "page_size": page_size, "cases": selected,
        "suggested_actions": actions, "summary": get_summary(cases), "is_capacity_failure": is_capacity_failure,
        "search_mode": search_mode, "recommendation_basis": recommendation_basis,
        "recommendations": recommendations, "first_step": first_step,
        "applied_constraints": {"products": constrained_products, "stations": constrained_stations,
                                "attempted_action": attempted_action, "duration_seconds": sorted(durations),
                                "channels": sorted(channels, key=int), "action": action_filter,
                                "serials": sorted(serials)},
    }

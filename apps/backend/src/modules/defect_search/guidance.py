"""Choose an evidence-backed first step for each submitted defect search."""
from __future__ import annotations

import re
from typing import Any

from . import repository
from .normalization import normalized_action


def _action_key(value: str) -> str:
    return re.sub(r"\s+", "", normalized_action(value)).casefold().rstrip("。.!！;；、,，")


def _contains_retest(value: str) -> bool:
    return bool(re.search(r"复测|重测|重新测试|\bre-?test(?:ing)?\b", value, re.IGNORECASE))


def _only_retest(value: str) -> bool:
    return repository.only_retest(value)


def _actions(group: dict[str, Any], attempted_action: str) -> list[dict[str, Any]]:
    attempted = _action_key(attempted_action)
    retest_failed = _contains_retest(attempted_action)
    return sorted(
        [action for action in group.get("actions", [])
         if action.get("action")
         and (not attempted or _action_key(action["action"]) != attempted)
         and not (retest_failed and _only_retest(action["action"]))],
        key=lambda action: (-action["count"], action["action"]),
    )


def _option(group: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    return {
        "product": group["product"], "action": action["action"], "count": action["count"],
        "matched_cases": group["matched_cases"], "stations": group.get("stations", []),
        "defect_codes": group.get("defect_codes", []), "sources": action.get("sources", []),
    }


def _top_options(group: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_option(group, action) for action in actions
            if actions and action["count"] == actions[0]["count"]]


def _conditions(group: dict[str, Any]) -> list[str]:
    conditions = [f"产品型号：{group['product']}"] if group.get("product") else []
    if group.get("stations"):
        conditions.append("测试工站：" + " / ".join(group["stations"]))
    if group.get("defect_codes"):
        conditions.append("缺陷代码：" + " / ".join(group["defect_codes"]))
    conditions.append("缺陷现象、故障阶段及位置与来源案例一致")
    return conditions


def _engineering_step(note: str = "") -> dict[str, Any]:
    return {
        "kind": "engineering_review",
        "action": "根据当前实际现象、报错、已采用措施及结果补充描述，重新检索建议；也可提交工程分析。",
        "count": 0, "sources": [],
        "note": note or "后续处理需依据新的实际问题判断，历史措施不构成固定维修顺序。",
    }


def first_step(
    *,
    requested: bool,
    has_symptom: bool,
    generic_symptom: bool,
    needs_detail: bool,
    capacity_failure: bool,
    basis: str,
    recommendations: list[dict[str, Any]],
    total: int,
    product: str = "",
    products: list[str] | None = None,
    attempted_action: str = "",
) -> dict[str, Any] | None:
    if not requested:
        return None

    matched_products = list(dict.fromkeys(products if products is not None else
                                         [group["product"] for group in recommendations if group["product"]]))
    result: dict[str, Any] = {
        "kind": "confirm_symptom", "basis": basis, "product": product,
        "action": "", "count": 0, "matched_cases": total, "sources": [],
        "evidence_level": "none", "verified_cases": 0, "latest_date": "",
        "reason": "mixed_symptoms", "stations": [], "defect_codes": [], "products": matched_products,
        "attempted_action": attempted_action, "conditions": [], "alternatives": [], "options": [],
        "next_step": None,
    }
    grouped_actions = [(group, _actions(group, attempted_action)) for group in recommendations]
    result["alternatives"] = [option for group, actions in grouped_actions
                              for option in _top_options(group, actions)]
    if len(recommendations) == 1 and len(matched_products) <= 1:
        result["product"] = recommendations[0]["product"]
        result["matched_cases"] = recommendations[0]["matched_cases"]
        result["stations"] = recommendations[0]["stations"]
        result["defect_codes"] = recommendations[0]["defect_codes"]
        result["conditions"] = _conditions(recommendations[0])

    # Retest is an explicit operating rule supplied by the user. Missing
    # history does not invalidate the rule or count as evidence of a retest.
    if capacity_failure and not _contains_retest(attempted_action):
        retests = [action for _, actions in grouped_actions for action in actions
                   if _only_retest(action["action"])]
        result.update(
            kind="retest", basis="policy", reason="policy", evidence_level="policy", action="复测",
            count=sum(action["count"] for action in retests),
            matched_cases=sum(group["matched_cases"] for group in recommendations),
            sources=[source for action in retests for source in action["sources"]][:3],
            verified_cases=sum(action.get("verified_cases", 0) for action in retests),
            latest_date=max((action.get("latest_date", "") for action in retests), default=""),
        )
        result["next_step"] = _engineering_step(
            "复测未通过时，可补充本次型号、工站、具体报错及复测结果重新检索，或由工程分析新的问题。"
        )
        return result

    if (not has_symptom and basis == "none") or generic_symptom:
        result["kind"] = "clarify_symptom"
        result["reason"] = "broad_symptom" if generic_symptom else "missing_symptom"
        return result
    if total == 0:
        result["kind"] = "no_history"
        result["reason"] = "no_history"
        result["next_step"] = _engineering_step("本地暂无对应案例；可补充本次型号、工站、报错及现象重新检索，或提交工程分析。")
        return result
    # Evidence scoping can omit a model with mixed or missing history. That
    # must never silently select a different model from the search results.
    if len(matched_products) > 1:
        result["kind"] = "select_product"
        result["reason"] = "multiple_products"
        result["next_step"] = _engineering_step("不同型号的结构和历史措施不同，请先选择当前产品型号，再参考该型号的处理建议。")
        return result
    if not recommendations:
        result["reason"] = "similar_only" if basis == "similar" else "mixed_symptoms"
        result["next_step"] = _engineering_step("匹配结果尚不足以支持具体维修动作；可补充本次报错、工站或故障阶段重新检索，或提交工程分析。")
        return result
    if len(recommendations) > 1 or not recommendations[0]["product"]:
        result["kind"] = "select_product"
        result["reason"] = "multiple_products"
        result["next_step"] = _engineering_step("请先选择当前产品型号，再参考该型号的历史处理措施。")
        return result

    group = recommendations[0]
    actions = grouped_actions[0][1]
    if not actions:
        result["kind"] = "no_action"
        result["reason"] = "missing_action"
        result["next_step"] = _engineering_step(
            "当前已知措施未解决，可补充处理后的实际现象重新检索，或提交工程分析。" if attempted_action
            else "相似案例没有可执行的临时措施；可补充现象和测试信息重新检索，或提交工程分析。"
        )
        return result
    # Show a concrete historical reference when its applicability still needs
    # confirmation. Conditions remain explicit so it cannot imply a confirmed
    # diagnosis or unconditional replacement instruction.
    reason = ""
    if basis != "exact":
        reason = "similar_only" if basis == "similar" else "broad_symptom"
    elif needs_detail:
        reason = "broad_symptom"
    elif len(group["stations"]) > 1:
        reason = "multiple_stations"
    elif len(group["defect_codes"]) > 1:
        reason = "multiple_codes"
    options = _top_options(group, actions)
    if len(options) > 1:
        result["kind"] = "compare_actions"
        result["reason"] = reason or "action_tie"
        result["options"] = options
        result["next_step"] = _engineering_step("多项历史措施的采用次数并列；可补充现象、零件版本和位置，重新检索适用建议，或提交工程分析。")
        return result

    most_common = actions[0]
    result.update(
        kind="reference" if reason else "historical", reason=reason or "history", action=most_common["action"],
        count=most_common["count"], sources=most_common["sources"],
        evidence_level=most_common.get("evidence_level", "single"),
        verified_cases=most_common.get("verified_cases", 0),
        latest_date=most_common.get("latest_date", ""),
    )
    result["next_step"] = _engineering_step()
    return result

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from llm.models import SopTextChunkRequest, SopTextMaterial


MATERIAL_PART_NUMBER_PATTERN = re.compile(r"(?<!\d)\d{3,4}-\d{5}(?!\d)")
MATERIAL_NAME_ACTION_PATTERN = re.compile(
    r"(?:需要|确保|确认|检查|使用|安装|组装|固定|锁紧|拧紧|放入|取出|替换|更换|完成)"
    r"|\b(?:need|ensure|check|use|install|assemble|fasten|tighten|place|remove|replace)\b",
    re.IGNORECASE,
)


def normalize_material_name(value: Any) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    name = re.sub(r"^(?:物料名称|物料名|名称)\s*[:：]\s*", "", name)
    name = MATERIAL_PART_NUMBER_PATTERN.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip(" \t\r\n:：,，;；。|/\\-–—")


def material_name_score(value: Any) -> int:
    """Prefer concise noun phrases over full SOP instruction sentences."""
    name = normalize_material_name(value)
    if not name:
        return -1000
    score = 100
    if len(name) <= 48:
        score += 20
    elif len(name) > 100:
        score -= 40
    if MATERIAL_NAME_ACTION_PATTERN.search(name):
        score -= 80
    if re.search(r"[。！？；;\n]", name):
        score -= 30
    if len(name.split()) > 10:
        score -= 25
    return score


def choose_material_name(current: Any, candidate: Any) -> str:
    current_name = normalize_material_name(current)
    candidate_name = normalize_material_name(candidate)
    if not current_name:
        return candidate_name
    if not candidate_name:
        return current_name
    candidate_score = material_name_score(candidate_name)
    current_score = material_name_score(current_name)
    if candidate_score > current_score:
        return candidate_name
    if (
        candidate_score == current_score
        and len(candidate_name) > len(current_name)
        and current_name.casefold() in candidate_name.casefold()
    ):
        return candidate_name
    return current_name


class LLMConfigurationError(RuntimeError):
    pass


class LLMService:
    """Stateless OpenAI-compatible chat client; no conversation is retained."""

    def __init__(self) -> None:
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
        self.sop_chunk_chars = max(4000, int(os.getenv("LLM_SOP_CHUNK_CHARS", "30000")))

    def extract_sop_materials(self, request: SopTextChunkRequest) -> list[SopTextMaterial]:
        if not self.api_key:
            raise LLMConfigurationError("未配置 LLM_API_KEY（或 DEEPSEEK_API_KEY/OPENAI_API_KEY）")
        system = (
            "你是制造业 SOP 物料识别器。输入内容已经筛选为包含物料料号的 SOP 原始文本行；只分析这些行中明确出现的物料。\n"
            "返回严格 JSON，不要 Markdown：{\"materials\":[{\"part_number\":\"料号\",\"name\":\"料号名\",\"quantity\":数量或null,\"unit\":\"单位或null\",\"confidence\":0到1}]}。\n"
            "part_number 必须是文本中明确出现的料号；不要臆测。数量是该物料在上下文中的用量。\n"
            "name 必须是料号附近所指向的最短、最具体的物料实体名，通常紧邻料号前后。去掉操作动作、状态描述、数量、序号和整句说明。\n"
            "不要把“安装、固定、拧紧、确保、检查、使用、完成”等动作文字放进 name；无法确定实体名时返回空字符串，不要复制整句。\n"
            "示例：“所有螺丝拧紧,需要确保柱塞块 415-00635”应返回 name=“柱塞块”，part_number=“415-00635”。\n"
            "示例：“使用 415-00635 柱塞块进行安装”也应返回 name=“柱塞块”。\n"
            "重点识别数量写法：* 10、*10、x10、X22、× 4、Qty: 3、数量 5，以及表格中料号后面的数字。"
            "特别注意“卡簧 4×467-00004”表示料号 467-00004、数量 4；数字和 ×/x 在料号前，不是料号的一部分。"
        )
        payload = {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": request.text}]}
        try:
            response = httpx.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json=payload, timeout=self.timeout)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = self._parse_json(content)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise RuntimeError(f"LLM 物料识别失败：{exc}") from exc
        materials = []
        for item in data.get("materials", []) if isinstance(data, dict) else []:
            if not isinstance(item, dict) or not str(item.get("part_number", "")).strip():
                continue
            materials.append(SopTextMaterial(part_number=str(item["part_number"]).strip(), name=normalize_material_name(item.get("name")), quantity=item.get("quantity"), unit=item.get("unit"), confidence=item.get("confidence", 0), page_number=request.page_number, source=request.source))
        return materials

    def extract_sop_pages(self, pages: list[tuple[int, str]]) -> list[SopTextMaterial]:
        """Analyze all extracted pages in context-sized chunks and merge by part number."""
        chunks: list[str] = []
        current = ""
        for page_number, text in pages:
            block = f"\n\n===== SOP 第 {page_number} 页 =====\n{text}"
            if current and len(current) + len(block) > self.sop_chunk_chars:
                chunks.append(current)
                current = ""
            current += block
        if current:
            chunks.append(current)
        merged: dict[str, SopTextMaterial] = {}
        for index, chunk in enumerate(chunks):
            items = self.extract_sop_materials(SopTextChunkRequest(text=chunk, source=f"sop-chunk-{index + 1}"))
            for item in items:
                key = item.part_number.strip().upper()
                existing = merged.get(key)
                if existing is None:
                    merged[key] = item
                else:
                    existing.quantity = (existing.quantity or 0) + (item.quantity or 0) if item.quantity is not None else existing.quantity
                    existing.name = choose_material_name(existing.name, item.name)
                    existing.confidence = min(existing.confidence, item.confidence)
        return list(merged.values())

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = content.strip().lstrip("\ufeff")
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)

        candidates = [cleaned]
        extracted = LLMService._extract_json_object(cleaned)
        if extracted and extracted != cleaned:
            candidates.append(extracted)

        last_error: json.JSONDecodeError | None = None
        for candidate in candidates:
            for variant in (candidate, LLMService._repair_common_json_errors(candidate)):
                try:
                    parsed = json.loads(variant)
                except json.JSONDecodeError as exc:
                    last_error = exc
                    continue
                if isinstance(parsed, dict):
                    return parsed
                raise ValueError("LLM 返回的 JSON 顶层不是对象")

        recovered_materials = LLMService._recover_complete_materials(cleaned)
        if recovered_materials:
            return {"materials": recovered_materials}

        if last_error is not None:
            start = max(0, last_error.pos - 80)
            end = min(len(cleaned), last_error.pos + 80)
            context = cleaned[start:end].replace("\n", "\\n")
            raise ValueError(
                f"{last_error.msg}（第 {last_error.lineno} 行第 {last_error.colno} 列，附近内容：{context}）"
            ) from last_error
        raise ValueError("LLM 未返回可解析的 JSON")

    @staticmethod
    def _extract_json_object(content: str) -> str | None:
        """Extract the first balanced JSON object when a provider adds prose around it."""
        start = content.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(content)):
            char = content[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[start:index + 1]
        return None

    @staticmethod
    def _repair_common_json_errors(content: str) -> str:
        """Repair harmless JSON formatting mistakes seen in occasional LLM responses."""
        repaired: list[str] = []
        in_string = False
        escaped = False
        index = 0
        while index < len(content):
            char = content[index]
            if in_string:
                repaired.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                repaired.append(char)
                index += 1
                continue

            if char == ",":
                next_index = index + 1
                while next_index < len(content) and content[next_index].isspace():
                    next_index += 1
                if next_index < len(content) and content[next_index] in "}]":
                    index += 1
                    continue

            if char == ":":
                next_index = index + 1
                while next_index < len(content) and content[next_index].isspace():
                    next_index += 1
                if next_index < len(content) and content[next_index] in ",}]":
                    repaired.append(": null")
                    index += 1
                    continue

            repaired.append(char)
            index += 1

        return "".join(repaired)

    @staticmethod
    def _recover_complete_materials(content: str) -> list[dict[str, Any]]:
        """Keep complete material objects when a long JSON response is cut off at the end."""
        match = re.search(r'"materials"\s*:\s*\[', content)
        if not match:
            return []

        materials: list[dict[str, Any]] = []
        object_start: int | None = None
        object_depth = 0
        in_string = False
        escaped = False
        for index in range(match.end(), len(content)):
            char = content[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                if object_depth == 0:
                    object_start = index
                object_depth += 1
                continue
            if char != "}" or object_depth == 0:
                continue

            object_depth -= 1
            if object_depth != 0 or object_start is None:
                continue
            item_text = content[object_start:index + 1]
            try:
                item = json.loads(LLMService._repair_common_json_errors(item_text))
            except json.JSONDecodeError:
                object_start = None
                continue
            if isinstance(item, dict) and str(item.get("part_number", "")).strip():
                materials.append(item)
            object_start = None

        return materials


llm_service = LLMService()

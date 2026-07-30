from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from llm.models import SopSemanticDecision, SopSemanticMaterial, SopTextChunkRequest, SopTextMaterial


MATERIAL_PART_NUMBER_PATTERN = re.compile(
    r"(?<!\d)(?:\d{3}-0\d{5}(?![xX×*])|\d{3,4}-\d{5})"
    r"(?:(?!\d)|(?=\d{1,3}[xX×*]\d{3,4}-))"
)
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
        self.semantic_max_workers = max(1, min(4, int(os.getenv("LLM_SEMANTIC_MAX_WORKERS", "3"))))

    def extract_sop_materials(self, request: SopTextChunkRequest) -> list[SopTextMaterial]:
        if not self.api_key:
            raise LLMConfigurationError("未配置 LLM_API_KEY（或 DEEPSEEK_API_KEY/OPENAI_API_KEY）")
        system = (
            "你是制造业 SOP 物料识别器。输入内容已经筛选为包含物料料号的 SOP 原始文本行；只分析这些行中明确出现的物料。\n"
            "返回严格 JSON，不要 Markdown：{\"materials\":[{\"part_number\":\"料号\",\"name\":\"料号名\",\"quantity\":数量或null,\"unit\":\"单位或null\",\"confidence\":0到1}]}。\n"
            "part_number 必须是文本中明确出现的料号；不要臆测。数量是该物料在上下文中的用量。\n"
            "SOP 经常在同一页先写中文、再写对应的英文翻译。相同料号同时出现在中英文描述时，只按英文描述计算数量，中文仅用于辅助理解名称，绝对不要把中英文数量相加。"
            "只有该页没有对应英文描述时，才使用中文描述计算数量。\n"
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
        chunks = self._build_page_chunks(pages)
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

    def extract_sop_semantic_references(self, pages: list[tuple[int, str]]) -> list[SopTextMaterial]:
        """Estimate final quantities using all instruction evidence for each part.

        Every part number is kept within one LLM request, so the model can judge
        installation, later tightening/checking, and repeated references across
        the entire SOP instead of making isolated page-level decisions.
        """

        evidence_groups = self._build_part_evidence_groups(
            pages,
            max_chars=min(max(self.sop_chunk_chars, 8000), 12000),
        )
        expected_part_numbers = {
            part_number
            for _, part_numbers in evidence_groups
            for part_number in part_numbers
        }
        merged: dict[str, SopSemanticMaterial] = {}
        with ThreadPoolExecutor(
            max_workers=min(self.semantic_max_workers, max(1, len(evidence_groups)))
        ) as executor:
            futures = {
                executor.submit(
                    self._extract_sop_semantic_chunk,
                    evidence,
                    index + 1,
                    part_numbers,
                ): part_numbers
                for index, (evidence, part_numbers) in enumerate(evidence_groups)
            }
            for future in as_completed(futures):
                part_numbers = futures[future]
                items = future.result()
                for item in items:
                    key = item.part_number.strip().upper()
                    if key in part_numbers:
                        merged[key] = item

        materials: list[SopTextMaterial] = []
        for part_number in sorted(expected_part_numbers):
            item = merged.get(part_number)
            if item is None:
                quantity = 1.0
                name = ""
                confidence = 0.0
                explanation = "大模型未返回完整语义判断，保留本地统计结果"
                decisions: list[SopSemanticDecision] = []
            else:
                added_quantity = float(item.added_quantity)
                reference_quantity = float(item.reference_quantity)
                accumulated_decisions = [decision for decision in item.decisions if decision.accumulate]
                decision_quantity = sum(
                    float(decision.quantity_delta) for decision in accumulated_decisions
                )
                model_quantity = (
                    float(item.final_quantity)
                    if item.final_quantity is not None
                    else added_quantity if added_quantity > 0 else max(reference_quantity, 1.0)
                )
                quantity = model_quantity
                name = item.name
                confidence = item.confidence
                explanation = item.reason
                if accumulated_decisions and abs(decision_quantity - model_quantity) > 1e-6:
                    explanation = (
                        f"{explanation}；模型总数为 {model_quantity:g}，"
                        f"事件增量明细合计为 {decision_quantity:g}，"
                        "两者不一致时采用整篇上下文语义总数"
                    ).strip("；")
                decisions = item.decisions
            materials.append(
                SopTextMaterial(
                    part_number=part_number,
                    name=name,
                    quantity=quantity,
                    confidence=confidence,
                    source="sop-semantic",
                    quantity_explanation=explanation,
                    quantity_decisions=decisions,
                )
            )
        return materials

    def _extract_sop_semantic_chunk(
        self,
        text: str,
        chunk_number: int,
        expected_part_numbers: list[str] | None = None,
    ) -> list[SopSemanticMaterial]:
        if not self.api_key:
            raise LLMConfigurationError("未配置 LLM_API_KEY（或 DEEPSEEK_API_KEY/OPENAI_API_KEY）")
        expected_part_numbers = expected_part_numbers or sorted(
            set(MATERIAL_PART_NUMBER_PATTERN.findall(text))
        )
        system = (
            "你是制造业 SOP 正文装配事件分析器。禁止使用或推测 BOM 表，只能依据提供的操作正文证据判断最终装入产品的物料数量。\n"
            "输入按“目标料号”分段，每段包含该料号在整份 SOP 中的全部出现证据及相邻上下文。必须跨页综合判断同一实体的首次安装、后续锁紧、检查和重复引用。\n"
            "返回严格 JSON，不要 Markdown："
            '{"materials":[{"part_number":"料号","name":"最短物料名","added_quantity":新增装入数量,'
            '"reference_quantity":仅作为已有对象被引用的不同实体数量,"final_quantity":最终不同实体总数量,'
            '"confidence":0到1,"reason":"不超过120字的最终数量汇总说明，禁止重复推理",'
            '"decisions":[{"event_id":"E1","page_numbers":[页码],"action":"动作",'
            '"target":"安装目标","location":"位置","quantity_delta":本事件计入数量,"accumulate":true或false,'
            '"duplicate_of":"重复事件ID或null","reason":"是否累加原因","evidence":"简短原文证据"}]}]}。\n'
            "必须为用户列出的每个料号返回且只返回一条记录，不得遗漏或增加料号。\n"
            "每段只计算标题中的目标料号；证据行里的其他料号只是动作和装配目标上下文，除非它们也有自己的目标料号分段。\n"
            "added_quantity 只统计这个正文块中新装入、放入、插入、粘贴、包装或消耗的物料。作为安装目标、底座、已有组件、定位对象的料号不增加。\n"
            "锁紧、拧紧、检查、确认、清洁、测试、接线、测量、校准、移动或再次描述已有物料，不属于新装，不能重复增加。\n"
            "同一步骤的中文和英文是翻译关系，只计算一次；优先按英文理解，中文用于补充。图片标注和正文重复也只计算一次。\n"
            "同一料号在后续步骤如果明确安装到新的左/右、前/后或另一个独立位置，属于新的装配事件，需要继续增加。\n"
            "必须理解上下文倍率：2×料号且 repeat 96 times 表示新增 192；192pcs O-ring 料号表示新增 192；O-ring X96 表示新增 96。\n"
            "reference_quantity 用于正文块内只被反复引用但未新装的实体；同一个装配基体出现很多次通常填 1，不能按出现次数填写。"
            "但如果正文明确对 96 个吸嘴、96 个轴或其他 96 个不同实体重复操作，并给出了这些实体的料号，则该装配目标的 reference_quantity 应为 96，而不是 1。"
            "如果该料号已有 added_quantity，普通的后续引用不要再放入 reference_quantity。\n"
            "final_quantity 是你综合全部证据后判断的最终不同实体数量，不是出现次数，也不是 added_quantity 与 reference_quantity 的机械相加。"
            "如果后续 reference 明确指向前面已安装的同一实体，不能重复计入 final_quantity。\n"
            "decisions 必须覆盖每一个有意义的装配事件和被排除的重复事件，并清楚说明是否累加。"
            "accumulate=true 时 quantity_delta 表示该事件对最终数量的增量；accumulate=false 时 quantity_delta 必须为0。"
            "所有 accumulate=true 的 quantity_delta 合计必须等于 final_quantity。\n"
            "判断事件是否相同时必须同时比较动作、安装目标、位置、步骤顺序和上下文，不能仅凭料号相同去重。"
            "例如先把A安装到B，后来再取一个A安装到C，应是两个事件并累加2；如果正文明确把前面同一个A从B移动到C，则第二次是移动同一实体，不新增。\n"
            "同一事件的中文、英文、图片标注应分别在 decisions 中说明重复关系，或者合并为一个事件并在 reason 中说明已去除双语重复。\n"
            "步骤序号、页码、扭力、尺寸不是物料数量。不要为了接近任何外部结果而修改数量。\n"
            "例：Attach 4×415-00643 to plunger block 415-00845 with 4×438-00147："
            "415-00643 added=4，438-00147 added=4，415-00845 reference=1。\n"
            "例：Install 2×438-00147 后又 Tighten 2×438-00147：只在安装事件新增 2，锁紧事件新增 0。"
        )
        user = (
            f"证据组 {chunk_number} 必须返回的目标料号：{', '.join(expected_part_numbers)}\n\n"
            f"各目标料号的全文证据：\n{text}"
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = self._parse_json(content)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise RuntimeError(f"LLM SOP 语义数量识别失败：{exc}") from exc

        materials: list[SopSemanticMaterial] = []
        for raw_item in data.get("materials", []) if isinstance(data, dict) else []:
            if not isinstance(raw_item, dict):
                continue
            part_number = str(raw_item.get("part_number") or "").strip().upper()
            if part_number not in expected_part_numbers:
                continue
            try:
                materials.append(
                    SopSemanticMaterial(
                        part_number=part_number,
                        name=normalize_material_name(raw_item.get("name")),
                        added_quantity=raw_item.get("added_quantity") or 0,
                        reference_quantity=raw_item.get("reference_quantity") or 0,
                        final_quantity=raw_item.get("final_quantity"),
                        confidence=raw_item.get("confidence") or 0,
                        reason=str(raw_item.get("reason") or "").strip(),
                        decisions=[
                            SopSemanticDecision.model_validate(decision)
                            for decision in raw_item.get("decisions", [])
                            if isinstance(decision, dict)
                        ],
                    )
                )
            except ValueError:
                continue
        return materials

    def _build_part_evidence_groups(
        self,
        pages: list[tuple[int, str]],
        max_chars: int,
    ) -> list[tuple[str, list[str]]]:
        evidence_by_part: dict[str, list[tuple[int, str]]] = {}
        for page_number, text in pages:
            part_numbers = list(dict.fromkeys(MATERIAL_PART_NUMBER_PATTERN.findall(text)))
            for part_number in part_numbers:
                evidence_by_part.setdefault(part_number.upper(), []).append((page_number, text.strip()))

        groups: list[tuple[str, list[str]]] = []
        current_blocks: list[str] = []
        current_part_numbers: list[str] = []
        current_length = 0
        for part_number, evidence_pages in evidence_by_part.items():
            page_blocks = [
                f"\n----- 第 {page_number} 页完整正文 -----\n{page_text}"
                for page_number, page_text in evidence_pages
            ]
            block = f"\n===== 目标料号 {part_number} 的全部整页上下文 =====\n" + "".join(page_blocks)
            if current_blocks and current_length + len(block) > max_chars:
                groups.append(("".join(current_blocks), current_part_numbers))
                current_blocks = []
                current_part_numbers = []
                current_length = 0
            current_blocks.append(block)
            current_part_numbers.append(part_number)
            current_length += len(block)
        if current_blocks:
            groups.append(("".join(current_blocks), current_part_numbers))
        return groups

    def _build_page_chunks(
        self,
        pages: list[tuple[int, str]],
        max_chars: int | None = None,
    ) -> list[str]:
        chunks: list[str] = []
        current = ""
        chunk_chars = max_chars or self.sop_chunk_chars
        for page_number, text in pages:
            block = f"\n\n===== SOP 第 {page_number} 页 =====\n{text}"
            if current and len(current) + len(block) > chunk_chars:
                chunks.append(current)
                current = ""
            current += block
        if current:
            chunks.append(current)
        return chunks

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

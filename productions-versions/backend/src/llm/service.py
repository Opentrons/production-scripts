from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from llm.models import SopTextChunkRequest, SopTextMaterial


class LLMConfigurationError(RuntimeError):
    pass


class LLMService:
    """Stateless OpenAI-compatible chat client; no conversation is retained."""

    def __init__(self) -> None:
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))

    def extract_sop_materials(self, request: SopTextChunkRequest) -> list[SopTextMaterial]:
        if not self.api_key:
            raise LLMConfigurationError("未配置 LLM_API_KEY（或 DEEPSEEK_API_KEY/OPENAI_API_KEY）")
        system = (
            "你是制造业 SOP 物料识别器。只从输入文本中提取物料。\n"
            "返回严格 JSON，不要 Markdown：{\"materials\":[{\"part_number\":\"料号\",\"name\":\"料号名\",\"quantity\":数量或null,\"unit\":\"单位或null\",\"confidence\":0到1}]}。\n"
            "part_number 必须是文本中明确出现的料号；不要臆测。数量是该物料在上下文中的用量。\n"
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
            materials.append(SopTextMaterial(part_number=str(item["part_number"]).strip(), name=str(item.get("name", "")).strip(), quantity=item.get("quantity"), unit=item.get("unit"), confidence=item.get("confidence", 0), page_number=request.page_number, source=request.source))
        return materials

    def extract_sop_pages(self, pages: list[tuple[int, str]]) -> list[SopTextMaterial]:
        """Analyze all extracted pages in context-sized chunks and merge by part number."""
        chunks: list[str] = []
        current = ""
        for page_number, text in pages:
            block = f"\n\n===== SOP 第 {page_number} 页 =====\n{text}"
            if current and len(current) + len(block) > 110000:
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
                    if len(item.name) > len(existing.name):
                        existing.name = item.name
                    existing.confidence = min(existing.confidence, item.confidence)
        return list(merged.values())

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        return json.loads(cleaned)


llm_service = LLMService()

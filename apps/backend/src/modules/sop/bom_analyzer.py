from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Literal

from modules.sop.models import SopBomMaterial, SopBomSection, SopPartOccurrence, SopPartReference


SopPageCategory = Literal["instruction", "material_list", "tool_list"]
ReferenceLanguage = Literal["zh", "en", "other"]

MATERIAL_LIST_MARKERS = (
    "物料清单",
    "材料清单",
    "零件清单",
    "辅料清单",
    "material list",
    "matrail list",
    "parts list",
    "bill of materials",
)
TOOL_LIST_MARKERS = (
    "工具清单",
    "工具列表",
    "所需工具",
    "工装清单",
    "治具清单",
    "tool list",
    "tools list",
    "required tools",
    "fixture list",
)
INSTRUCTION_MARKERS = (
    "操作步骤",
    "组装步骤",
    "安装步骤",
    "操作说明",
    "作业步骤",
    "assembly procedure",
    "work instruction",
    "installation procedure",
)
ACTION_PATTERN = re.compile(
    r"(?:组装|安装|固定|锁紧|检查|确认|放入|取出|assemble|install|fasten|tighten|check|place|remove)",
    re.IGNORECASE,
)
PART_NUMBER_PATTERN = re.compile(
    r"(?<!\d)(?P<part_number>(?:\d{3}-0\d{5}(?![xX×*])|\d{3,4}-\d{5}))"
    r"(?:(?!\d)|(?=\d{1,3}[xX×*]\d{3,4}-))"
)
PREFIX_QUANTITY_PATTERN = re.compile(r"(?P<quantity>\d+)\s*[xX×*]\s*$")
CONCATENATED_PREFIX_QUANTITY_PATTERN = re.compile(
    r"\d{3,4}-\d{5}(?P<quantity>\d{1,3})\s*[xX×*]\s*$"
)
QUANTITY_PATTERN = re.compile(r"^\s+(?P<quantity>\d+(?:\.\d+)?)\b(?P<note>.*)$")
LEADING_SEQUENCE_PATTERN = re.compile(r"^\s*(?P<sequence>\d{1,3})\s+(?P<name>.+)$")
TRAILING_SEQUENCE_PATTERN = re.compile(r"(?P<name>.*?[A-Za-z,)])(?P<sequence>\d{1,3})$")
UNIT_PATTERN = re.compile(r"^\s*(?P<unit>PCS?|EA|SET|ML|L|G|KG)\b", re.IGNORECASE)
REFERENCE_NAME_ACTION_PATTERN = re.compile(
    r"(?:需要|确保|确认|检查|使用|安装|组装|固定|锁紧|拧紧|放入|取出|替换|更换|完成)",
    re.IGNORECASE,
)
REFERENCE_NAME_PREFIX_PATTERN = re.compile(
    r"^(?:(?:所有)?[^,，。；;]{0,30}?(?:拧紧|锁紧|固定|安装|完成)\s*)?"
    r"(?:需要)?(?:确保|确认|检查|使用|安装|组装|放入|取出|替换|更换|将|把)?\s*",
    re.IGNORECASE,
)
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")


@dataclass
class _LanguageQuantity:
    occurrences: int = 0
    explicit_quantity: int | None = None


@dataclass
class _PagePartQuantity:
    languages: dict[ReferenceLanguage, _LanguageQuantity] = field(default_factory=dict)

    def add(self, language: ReferenceLanguage, explicit_quantity: int | None) -> None:
        quantity = self.languages.setdefault(language, _LanguageQuantity())
        quantity.occurrences += 1
        if explicit_quantity is not None:
            quantity.explicit_quantity = max(quantity.explicit_quantity or 0, explicit_quantity)

    def resolve(self) -> int:
        # SOPs commonly repeat a Chinese instruction as an English translation.
        # Prefer the English quantity when present, then fall back to Chinese or
        # language-neutral lines so bilingual text is not counted twice.
        for language in ("en", "zh", "other"):
            quantity = self.languages.get(language)
            if quantity is not None and quantity.occurrences:
                return quantity.explicit_quantity or quantity.occurrences
        return 0


def is_bom_page(text: str) -> bool:
    return _contains_marker(text, MATERIAL_LIST_MARKERS)


def classify_sop_page(text: str, previous_category: SopPageCategory = "instruction") -> SopPageCategory:
    if _contains_marker(text, MATERIAL_LIST_MARKERS):
        return "material_list"
    if _contains_marker(text, TOOL_LIST_MARKERS):
        return "tool_list"
    if _contains_marker(text, INSTRUCTION_MARKERS) or _action_line_count(text) >= 2:
        return "instruction"
    if previous_category == "material_list" and _looks_like_continued_table(text, require_part_numbers=True):
        return "material_list"
    if previous_category == "tool_list" and _looks_like_continued_table(text, require_part_numbers=False):
        return "tool_list"
    return "instruction"


def _contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    normalized = re.sub(r"\s+", " ", text.casefold())
    return any(marker in normalized for marker in markers)


def _action_line_count(text: str) -> int:
    return sum(bool(ACTION_PATTERN.search(line)) for line in text.splitlines() if line.strip())


def _looks_like_continued_table(text: str, require_part_numbers: bool) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    header_text = " ".join(lines[:8]).casefold()
    has_table_header = (
        ("序号" in header_text or "no." in header_text or "item" in header_text)
        and ("名称" in header_text or "name" in header_text or "description" in header_text)
        and ("数量" in header_text or "qty" in header_text or "quantity" in header_text)
    )
    part_number_lines = sum(bool(PART_NUMBER_PATTERN.search(line)) for line in lines)
    if require_part_numbers:
        return has_table_header or part_number_lines >= 3 and part_number_lines / len(lines) >= 0.5
    short_rows = sum(len(line) <= 100 for line in lines)
    return has_table_header or short_rows >= 4 and short_rows / len(lines) >= 0.7


def analyze_bom_pages(layout_pages: list[tuple[int, str]]) -> tuple[list[SopBomSection], list[SopBomMaterial]]:
    sections: list[SopBomSection] = []
    for page_number, text in layout_pages:
        section = _parse_bom_page(page_number, text)
        if section.materials:
            sections.append(section)
    return sections, _aggregate_materials(sections)


def analyze_part_references(
    pages: list[tuple[int, str]],
    bom_materials: list[SopBomMaterial],
) -> list[SopPartReference]:
    """Aggregate part-number references from non-BOM pages.

    BOM material names take precedence over names inferred from surrounding
    document text. Raw occurrences retain every Chinese and English match for
    traceability. Quantity prefers English matches per page and falls back to
    Chinese only when no English match exists, avoiding translation double-counting.
    """

    bom_names = {
        material.part_number: material.name.strip()
        for material in bom_materials
        if material.name.strip()
    }
    references: OrderedDict[str, SopPartReference] = OrderedDict()
    page_quantities: dict[str, dict[int, _PagePartQuantity]] = {}
    for page_number, text in pages:
        for source_line in text.splitlines():
            matches = list(PART_NUMBER_PATTERN.finditer(source_line))
            if not matches:
                continue
            cleaned_line = source_line.strip()
            for part_match in matches:
                part_number = part_match.group("part_number")
                inferred_name = _infer_reference_name(source_line, part_match)
                reference = references.get(part_number)
                if reference is None:
                    reference = SopPartReference(
                        part_number=part_number,
                        name=bom_names.get(part_number, inferred_name),
                    )
                    references[part_number] = reference
                elif part_number in bom_names:
                    reference.name = bom_names[part_number]
                elif not reference.name and inferred_name:
                    reference.name = inferred_name

                reference.occurrences += 1
                quantity_prefix = source_line[:part_match.start()]
                quantity_match = (
                    CONCATENATED_PREFIX_QUANTITY_PATTERN.search(quantity_prefix)
                    or PREFIX_QUANTITY_PATTERN.search(quantity_prefix)
                )
                explicit_quantity = int(quantity_match.group("quantity")) if quantity_match else None
                quantities_for_part = page_quantities.setdefault(part_number, {})
                page_quantity = quantities_for_part.setdefault(page_number, _PagePartQuantity())
                page_quantity.add(_reference_line_language(source_line), explicit_quantity)
                reference.quantity = sum(quantity.resolve() for quantity in quantities_for_part.values())
                if page_number not in reference.pages:
                    reference.pages.append(page_number)
                reference.source_lines.append(cleaned_line)
                reference.occurrence_details.append(
                    SopPartOccurrence(page_number=page_number, evidence=cleaned_line)
                )
    return list(references.values())


def has_bilingual_reference_lines(source_lines: list[str]) -> bool:
    languages = {_reference_line_language(line) for line in source_lines}
    return "zh" in languages and "en" in languages


def _reference_line_language(source_line: str) -> ReferenceLanguage:
    if CJK_PATTERN.search(source_line):
        return "zh"
    if LATIN_PATTERN.search(source_line):
        return "en"
    return "other"


def extract_material_lines(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Return only pages and source lines that contain a material part number."""

    material_pages: list[tuple[int, str]] = []
    for page_number, text in pages:
        matching_lines = [
            source_line.strip()
            for source_line in text.splitlines()
            if PART_NUMBER_PATTERN.search(source_line)
        ]
        if matching_lines:
            material_pages.append((page_number, "\n".join(matching_lines)))
    return material_pages


def _parse_bom_page(page_number: int, text: str) -> SopBomSection:
    section_name = _section_name(text, page_number)
    materials: list[SopBomMaterial] = []
    for source_line in text.splitlines():
        material = _parse_material_line(source_line, section_name, page_number)
        if material is not None:
            materials.append(material)
    return SopBomSection(name=section_name, page_number=page_number, materials=materials)


def _parse_material_line(
    source_line: str,
    section_name: str,
    page_number: int,
) -> SopBomMaterial | None:
    line = source_line.rstrip()
    part_match = PART_NUMBER_PATTERN.search(line)
    if part_match is None:
        return None

    name_text = line[:part_match.start()].strip()
    remainder = line[part_match.end():]
    quantity_match = QUANTITY_PATTERN.match(remainder)
    quantity = float(quantity_match.group("quantity")) if quantity_match else None
    note = quantity_match.group("note").strip() if quantity_match else remainder.strip()
    unit_match = UNIT_PATTERN.match(note)
    unit = unit_match.group("unit").upper() if unit_match else None

    name_text = re.sub(r"^NO\s+", "", name_text, flags=re.IGNORECASE)
    leading_sequence = LEADING_SEQUENCE_PATTERN.match(name_text)
    had_leading_sequence = leading_sequence is not None
    if leading_sequence:
        name_text = leading_sequence.group("name").strip()
    elif not _ends_with_product_number(name_text):
        trailing_sequence = TRAILING_SEQUENCE_PATTERN.fullmatch(name_text)
        if trailing_sequence:
            name_text = trailing_sequence.group("name").strip()

    if not name_text or _looks_like_document_header(name_text):
        return None

    confidence = 1.0
    if quantity is None:
        confidence -= 0.25
    if not had_leading_sequence and not source_line.lstrip().upper().startswith("NO"):
        confidence -= 0.05
    return SopBomMaterial(
        part_number=part_match.group("part_number"),
        name=name_text,
        quantity=quantity,
        quantity_complete=quantity is not None,
        unit=unit,
        sections=[section_name],
        pages=[page_number],
        occurrences=1,
        confidence=max(0, confidence),
        source_lines=[source_line.strip()],
    )


def _section_name(text: str, page_number: int) -> str:
    station_match = re.search(r"适用工位\s+(.+?物料清单)\s+本页版次号", text)
    if station_match:
        return station_match.group(1).strip()
    for line in text.splitlines():
        if "物料清单" in line:
            cleaned = line.strip()
            cleaned = re.sub(r"^适用工位\s*", "", cleaned)
            cleaned = re.sub(r"\s*本页版次号.*$", "", cleaned)
            return cleaned
    return f"BOM 第 {page_number} 页"


def _aggregate_materials(sections: list[SopBomSection]) -> list[SopBomMaterial]:
    aggregated: OrderedDict[str, SopBomMaterial] = OrderedDict()
    for section in sections:
        for material in section.materials:
            current = aggregated.get(material.part_number)
            if current is None:
                aggregated[material.part_number] = material.model_copy(deep=True)
                continue

            if material.quantity is None:
                current.quantity_complete = False
            elif current.quantity is None:
                current.quantity = material.quantity
                current.quantity_complete = False
            else:
                current.quantity += material.quantity
            current.occurrences += 1
            current.confidence = min(current.confidence, material.confidence)
            current.sections = list(dict.fromkeys([*current.sections, *material.sections]))
            current.pages = list(dict.fromkeys([*current.pages, *material.pages]))
            current.source_lines.extend(material.source_lines)
            if len(material.name) > len(current.name):
                current.name = material.name
            if current.unit is None:
                current.unit = material.unit
    return list(aggregated.values())


def _ends_with_product_number(value: str) -> bool:
    return bool(re.search(r"\b(?:OT|M)\d+$", value, flags=re.IGNORECASE))


def _looks_like_document_header(value: str) -> bool:
    normalized = value.lower()
    return any(marker in normalized for marker in ("sop no", "page no", "otsz-sop"))


def _infer_reference_name(source_line: str, part_match: re.Match[str]) -> str:
    before = source_line[:part_match.start()].strip()
    after = source_line[part_match.end():].strip()
    if REFERENCE_NAME_ACTION_PATTERN.search(before):
        before_segments = [item for item in re.split(r"[,，。；;]", before) if item.strip()]
        candidates = [*reversed(before_segments), after, before]
    else:
        candidates = [before, after]
    for candidate in candidates:
        cleaned = re.sub(
            r"(?i)\b(?:part\s*(?:number|no\.?|#)|p/?n|item\s*(?:number|no\.?))\b",
            " ",
            candidate,
        )
        cleaned = re.sub(r"(?:物料)?料号|图号|零件号|编号", " ", cleaned)
        cleaned = REFERENCE_NAME_PREFIX_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"^[\s:：,，;；|/\\\-–—]+|[\s:：,，;；|/\\\-–—]+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned and not _looks_like_document_header(cleaned):
            return cleaned[:200]
    return ""

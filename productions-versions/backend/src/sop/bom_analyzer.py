from __future__ import annotations

import re
from collections import OrderedDict

from sop.models import SopBomMaterial, SopBomSection, SopPartReference


BOM_PAGE_MARKERS = (
    "物料清单",
    "material list",
    "matrail list",
)
PART_NUMBER_PATTERN = re.compile(r"(?<!\d)(?P<part_number>\d{3,4}-\d{5})(?!\d)")
QUANTITY_PATTERN = re.compile(r"^\s+(?P<quantity>\d+(?:\.\d+)?)\b(?P<note>.*)$")
LEADING_SEQUENCE_PATTERN = re.compile(r"^\s*(?P<sequence>\d{1,3})\s+(?P<name>.+)$")
TRAILING_SEQUENCE_PATTERN = re.compile(r"(?P<name>.*?[A-Za-z,)])(?P<sequence>\d{1,3})$")
UNIT_PATTERN = re.compile(r"^\s*(?P<unit>PCS?|EA|SET|ML|L|G|KG)\b", re.IGNORECASE)


def is_bom_page(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in BOM_PAGE_MARKERS)


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
    document text. Every pattern occurrence counts once, including repeated
    occurrences on the same page or source line.
    """

    bom_names = {
        material.part_number: material.name.strip()
        for material in bom_materials
        if material.name.strip()
    }
    references: OrderedDict[str, SopPartReference] = OrderedDict()
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
                reference.quantity = reference.occurrences
                if page_number not in reference.pages:
                    reference.pages.append(page_number)
                reference.source_lines.append(cleaned_line)
    return list(references.values())


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
    candidates = [before, after]
    for candidate in candidates:
        cleaned = re.sub(
            r"(?i)\b(?:part\s*(?:number|no\.?|#)|p/?n|item\s*(?:number|no\.?))\b",
            " ",
            candidate,
        )
        cleaned = re.sub(r"(?:物料)?料号|图号|零件号|编号", " ", cleaned)
        cleaned = re.sub(r"^[\s:：,，;；|/\\\-–—]+|[\s:：,，;；|/\\\-–—]+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned and not _looks_like_document_header(cleaned):
            return cleaned[:200]
    return ""

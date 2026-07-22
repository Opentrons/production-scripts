from sop.bom_analyzer import (
    analyze_bom_pages,
    analyze_part_references,
    extract_material_lines,
    is_bom_page,
)


SAMPLE_LAYOUT_PAGE = """
适用工位                     底板组装物料清单                     本页版次号 B0
Station                  Deck Assembly material list             Version
序号                     物料名称                                  图号       数量
 NO             DECK BRACE, VERTICAL, OT3                       415-00390      2
  1             DECK BRACE, HORIZONTAL, OT3                     415-00391      3
SCREW, SHOULDER, 5MM OD, 18MM LENGTH, HEX23                     438-00210      4
"""


def test_detects_and_parses_bom_material_table() -> None:
    assert is_bom_page(SAMPLE_LAYOUT_PAGE)

    sections, materials = analyze_bom_pages([(5, SAMPLE_LAYOUT_PAGE)])

    assert len(sections) == 1
    assert sections[0].name == "底板组装物料清单"
    assert len(sections[0].materials) == 3
    assert sections[0].materials[0].part_number == "415-00390"
    assert sections[0].materials[0].quantity == 2
    assert sections[0].materials[2].name.endswith("HEX")


def test_aggregates_same_part_across_bom_sections() -> None:
    second_page = """
适用工位                     最终组装物料清单                     本页版次号 B0
Station                  Final Assembly material list            Version
  1             DECK BRACE, VERTICAL, OT3                       415-00390      4
"""

    sections, materials = analyze_bom_pages([(5, SAMPLE_LAYOUT_PAGE), (10, second_page)])

    material = next(item for item in materials if item.part_number == "415-00390")
    assert material.quantity == 6
    assert material.occurrences == 2
    assert material.pages == [5, 10]
    assert material.sections == ["底板组装物料清单", "最终组装物料清单"]


def test_aggregates_part_references_and_uses_bom_material_name() -> None:
    _, bom_materials = analyze_bom_pages([(5, SAMPLE_LAYOUT_PAGE)])
    pages = [
        (1, "安装 415-00390，并确认 415-00390 已锁紧。"),
        (3, "替换件 438-00210 安装完成。\n备用零件 Part No: 999-12345 TEST BRACKET"),
    ]

    references = analyze_part_references(pages, bom_materials)

    brace = next(item for item in references if item.part_number == "415-00390")
    assert brace.name == "DECK BRACE, VERTICAL, OT3"
    assert brace.occurrences == 2
    assert brace.quantity == 2
    assert brace.pages == [1]

    unknown = next(item for item in references if item.part_number == "999-12345")
    assert unknown.name == "备用零件"
    assert unknown.occurrences == 1
    assert unknown.pages == [3]


def test_part_number_pattern_does_not_match_inside_longer_numbers() -> None:
    references = analyze_part_references([(1, "无效 1415-003900；有效 415-00390")], [])

    assert [item.part_number for item in references] == ["415-00390"]


def test_extract_material_lines_omits_other_pages_and_lines() -> None:
    pages = [
        (1, "准备工具\n安装 415-00390，并锁紧。\n检查外观"),
        (2, "本页没有任何物料"),
        (3, "使用 438-00210 完成装配。\n无效编号 1415-003900"),
    ]

    assert extract_material_lines(pages) == [
        (1, "安装 415-00390，并锁紧。"),
        (3, "使用 438-00210 完成装配。"),
    ]

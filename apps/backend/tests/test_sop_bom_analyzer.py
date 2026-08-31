from modules.sop.bom_analyzer import (
    analyze_bom_pages,
    analyze_part_references,
    classify_sop_page,
    extract_material_lines,
    is_bom_page,
)
from modules.sop.models import SopPdfPage


SAMPLE_LAYOUT_PAGE = """
适用工位                     底板组装物料清单                     本页版次号 B0
Station                  Deck Assembly material list             Version
序号                     物料名称                                  图号       数量
 NO             DECK BRACE, VERTICAL, OT3                       415-00390      2
  1             DECK BRACE, HORIZONTAL, OT3                     415-00391      3
SCREW, SHOULDER, 5MM OD, 18MM LENGTH, HEX23                     438-00210      4
"""


def test_pdf_page_accepts_content_category() -> None:
    page = SopPdfPage(page_number=2, text="工具清单", text_length=4, category="tool_list")

    assert page.category == "tool_list"


def test_detects_and_parses_bom_material_table() -> None:
    assert is_bom_page(SAMPLE_LAYOUT_PAGE)

    sections, materials = analyze_bom_pages([(5, SAMPLE_LAYOUT_PAGE)])

    assert len(sections) == 1
    assert sections[0].name == "底板组装物料清单"
    assert len(sections[0].materials) == 3
    assert sections[0].materials[0].part_number == "415-00390"
    assert sections[0].materials[0].quantity == 2
    assert sections[0].materials[2].name.endswith("HEX")


def test_classifies_material_and_tool_lists_anywhere_in_document() -> None:
    assert classify_sop_page("第 20 页\n材料清单\n序号 名称 料号 数量") == "material_list"
    assert classify_sop_page("第 35 页\n工具清单\n序号 工具名称 数量") == "tool_list"
    assert classify_sop_page("组装步骤\n安装 415-00390 并检查") == "instruction"


def test_continued_material_table_inherits_category_until_instructions_resume() -> None:
    continuation = """序号 名称 料号 数量
1 BRACKET 415-00390 2
2 SCREW 438-00210 4
3 COVER 415-00391 1
"""
    assert classify_sop_page(continuation, "material_list") == "material_list"
    assert classify_sop_page("操作步骤\n安装 415-00390\n检查 438-00210", "material_list") == "instruction"


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
    assert [(item.page_number, item.evidence) for item in brace.occurrence_details] == [
        (1, "安装 415-00390，并确认 415-00390 已锁紧。"),
        (1, "安装 415-00390，并确认 415-00390 已锁紧。"),
    ]

    unknown = next(item for item in references if item.part_number == "999-12345")
    assert unknown.name == "备用零件"
    assert unknown.occurrences == 1
    assert unknown.pages == [3]
    assert unknown.occurrence_details[0].evidence == "备用零件 Part No: 999-12345 TEST BRACKET"


def test_part_number_pattern_does_not_match_inside_longer_numbers() -> None:
    references = analyze_part_references([(1, "无效 1415-003900；有效 415-00390")], [])

    assert [item.part_number for item in references] == ["415-00390"]


def test_part_number_pattern_keeps_cleanup_candidates_for_workflow_audit() -> None:
    references = analyze_part_references(
        [(1, "安装 415-000656，并检查 920-000131。")],
        [],
    )

    assert [item.part_number for item in references] == ["415-000656", "920-000131"]


def test_concatenated_layout_quantities_do_not_create_false_cleanup_part_number() -> None:
    references = analyze_part_references(
        [(63, "4×438-001474×415-00650")],
        [],
    )

    assert [item.part_number for item in references] == ["438-00147", "415-00650"]
    assert [item.quantity for item in references] == [4, 4]


def test_concatenated_layout_quantity_does_not_create_four_digit_part_number() -> None:
    references = analyze_part_references(
        [(7, "415-00734*2415-00733")],
        [],
    )

    assert [item.part_number for item in references] == ["415-00734", "415-00733"]
    assert [item.quantity for item in references] == [2, 1]
    assert all(item.part_number != "2415-00733" for item in references)


def test_real_four_digit_part_after_quantity_marker_is_preserved() -> None:
    references = analyze_part_references(
        [(7, "2*2415-00733")],
        [],
    )

    assert [item.part_number for item in references] == ["2415-00733"]
    assert [item.quantity for item in references] == [2]


def test_spaced_suffix_quantity_is_not_summed_as_explicit_quantity() -> None:
    """``料号*N`` reminders are common on instruction pages; do not treat them
    as explicit per-page quantities or multi-page totals explode.
    """

    references = analyze_part_references(
        [(7, "415-00734*2 415-00733")],
        [],
    )

    assert [item.part_number for item in references] == ["415-00734", "415-00733"]
    assert [item.quantity for item in references] == [1, 1]


def test_prefix_quantity_still_wins_over_glued_trailing_digit() -> None:
    references = analyze_part_references(
        [(7, "4×415-00734*2415-00733")],
        [],
    )

    assert [item.part_number for item in references] == ["415-00734", "415-00733"]
    assert [item.quantity for item in references] == [4, 1]


def test_quantity_before_part_number_is_used_without_double_counting_translation() -> None:
    references = analyze_part_references(
        [
            (
                61,
                "1 卡簧 4×467-00004 固定螺丝\n"
                "1 E-clip 4x467-00004 fasten screw",
            )
        ],
        [],
    )

    retaining_ring = next(item for item in references if item.part_number == "467-00004")
    assert retaining_ring.occurrences == 2
    assert retaining_ring.quantity == 4
    assert retaining_ring.pages == [61]


def test_bilingual_reference_quantity_uses_english_occurrences_only() -> None:
    references = analyze_part_references(
        [
            (
                61,
                "安装卡簧 467-00004\n"
                "检查卡簧 467-00004\n"
                "Install E-clip 467-00004",
            )
        ],
        [],
    )

    retaining_ring = references[0]
    assert retaining_ring.occurrences == 3
    assert retaining_ring.quantity == 1


def test_reference_quantity_falls_back_to_chinese_when_english_is_absent() -> None:
    references = analyze_part_references(
        [(61, "安装卡簧 467-00004\n检查卡簧 467-00004")],
        [],
    )

    assert references[0].occurrences == 2
    assert references[0].quantity == 2


def test_reference_name_uses_nearest_material_noun_phrase() -> None:
    references = analyze_part_references(
        [(1, "所有螺丝拧紧,需要确保柱塞块 415-00635")],
        [],
    )

    assert len(references) == 1
    assert references[0].part_number == "415-00635"
    assert references[0].name == "柱塞块"


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

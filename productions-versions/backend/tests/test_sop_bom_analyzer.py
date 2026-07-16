from sop.bom_analyzer import analyze_bom_pages, is_bom_page


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

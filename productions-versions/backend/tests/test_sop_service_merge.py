from sop.models import SopPartReference, SopQuantityDecision
from sop.service import _merge_part_references, _merge_semantic_part_references


def test_llm_references_enrich_local_results_without_dropping_local_part_numbers() -> None:
    local = [
        SopPartReference(
            part_number="467-00004",
            name="卡簧 4×",
            occurrences=2,
            quantity=4,
            pages=[61],
            source_lines=["卡簧 4×467-00004"],
        )
    ]
    ai = [
        SopPartReference(
            part_number="446-00042",
            name="卡簧/E-clip",
            occurrences=1,
            quantity=4,
        )
    ]

    merged = _merge_part_references(local, ai)

    assert {item.part_number for item in merged} == {"467-00004", "446-00042"}
    retaining_ring = next(item for item in merged if item.part_number == "467-00004")
    assert retaining_ring.quantity == 4
    assert retaining_ring.pages == [61]


def test_llm_quantity_enriches_matching_local_reference() -> None:
    local = [SopPartReference(part_number="467-00004", name="卡簧", occurrences=2, quantity=2, pages=[61])]
    ai = [SopPartReference(part_number="467-00004", name="卡簧/Retaining ring", occurrences=1, quantity=4)]

    merged = _merge_part_references(local, ai)

    assert len(merged) == 1
    assert merged[0].quantity == 4
    assert merged[0].pages == [61]
    assert merged[0].name == "卡簧/Retaining ring"


def test_llm_does_not_reinflate_bilingual_reference_quantity() -> None:
    local = [
        SopPartReference(
            part_number="467-00004",
            name="卡簧",
            occurrences=2,
            quantity=1,
            pages=[61],
            source_lines=["安装卡簧 467-00004", "Install E-clip 467-00004"],
        )
    ]
    ai = [
        SopPartReference(
            part_number="467-00004",
            name="E-clip",
            occurrences=2,
            quantity=2,
        )
    ]

    merged = _merge_part_references(local, ai)

    assert merged[0].quantity == 1


def test_semantic_quantity_replaces_occurrence_based_local_quantity() -> None:
    local = [
        SopPartReference(
            part_number="415-00845",
            name="柱塞块",
            occurrences=25,
            quantity=25,
            pages=[12, 14],
            source_lines=["Attach rail to plunger block 415-00845"],
        )
    ]
    semantic = [
        SopPartReference(
            part_number="415-00845",
            name="Plunger block",
            occurrences=1,
            quantity=1,
            quantity_explanation="同一柱塞块被重复引用，只计一个实体",
            quantity_decisions=[
                SopQuantityDecision(
                    event_id="E1",
                    page_numbers=[12, 14],
                    action="作为装配目标",
                    quantity_delta=1,
                    accumulate=True,
                    reason="首次建立装配基体",
                )
            ],
        )
    ]

    merged = _merge_semantic_part_references(local, semantic)

    assert merged[0].quantity == 1
    assert merged[0].occurrences == 25
    assert merged[0].pages == [12, 14]
    assert merged[0].quantity_explanation == "同一柱塞块被重复引用，只计一个实体"
    assert merged[0].quantity_decisions[0].event_id == "E1"


def test_llm_short_material_name_replaces_instruction_sentence() -> None:
    local = [
        SopPartReference(
            part_number="415-00635",
            name="所有螺丝拧紧,需要确保柱塞块",
            occurrences=1,
            quantity=1,
            pages=[12],
        )
    ]
    ai = [SopPartReference(part_number="415-00635", name="柱塞块", occurrences=1, quantity=1)]

    merged = _merge_part_references(local, ai)

    assert merged[0].name == "柱塞块"

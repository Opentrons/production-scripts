from sop.models import SopPartReference
from sop.service import _merge_part_references


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

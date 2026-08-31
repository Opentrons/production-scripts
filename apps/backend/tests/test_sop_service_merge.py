from modules.agent.llm.models import SopSemanticDecision, SopTextMaterial
from modules.sop.models import SopPartReference, SopQuantityDecision
from modules.sop.service import (
    _apply_semantic_to_references,
    _enrich_reference_name_occurrences,
    _merge_part_references,
    _merge_semantic_part_references,
)


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


def test_confirmed_material_name_adds_name_only_occurrence_evidence() -> None:
    references = [
        SopPartReference(
            part_number="242-00052",
            name="扎带/zip-tie",
            occurrences=1,
            quantity=1,
            pages=[14],
            source_lines=["Install 1×242-00052 around the harness"],
        )
    ]

    material_names = _enrich_reference_name_occurrences(
        references,
        [
            (14, "Install 1×242-00052 around the harness"),
            (15, "Check the zip-tie position and trim the tail"),
        ],
    )

    assert material_names == {"242-00052": "扎带/zip-tie"}
    assert references[0].occurrences == 2
    assert references[0].pages == [14, 15]
    assert references[0].occurrence_details[-1].page_number == 15
    assert references[0].occurrence_details[-1].evidence == "Check the zip-tie position and trim the tail"


def test_name_occurrence_is_not_added_when_alias_belongs_to_another_material() -> None:
    references = [
        SopPartReference(
            part_number="435-00017",
            name="O-ring",
            occurrences=1,
            quantity=1,
            pages=[14],
            source_lines=["Install 435-00017"],
        )
    ]

    _enrich_reference_name_occurrences(
        references,
        [(15, "Install the O-ring into the plunger")],
        known_material_names={
            "435-00017": "O-ring",
            "435-00025": "O-ring",
        },
    )

    assert references[0].occurrences == 1
    assert references[0].pages == [14]


def test_apply_semantic_to_references_runs_without_page_material_hits(monkeypatch) -> None:
    def fake_semantic(pages, excluded_part_numbers=None, **kwargs):
        assert pages == [(1, "Install 2×415-00390")]
        return [
            SopTextMaterial(
                part_number="415-00390",
                name="bracket",
                quantity=2,
                confidence=0.9,
                quantity_explanation="安装 2 个支架",
                quantity_decisions=[
                    SopSemanticDecision(
                        event_id="E1",
                        page_numbers=[1],
                        action="安装",
                        target="框架",
                        location="",
                        quantity_delta=2,
                        accumulate=True,
                        duplicate_of=None,
                        reason="新增安装",
                        evidence="Install 2×415-00390",
                    )
                ],
            )
        ]

    monkeypatch.setattr("modules.sop.service.llm_service.api_key", "test-key")
    monkeypatch.setattr(
        "modules.sop.service.llm_service.extract_sop_semantic_references",
        fake_semantic,
    )

    local = [SopPartReference(part_number="415-00390", occurrences=5, quantity=5, pages=[1])]
    merged, applied = _apply_semantic_to_references(local, [(1, "Install 2×415-00390")], set())

    assert applied is True
    assert merged[0].quantity == 2
    assert merged[0].quantity_explanation == "安装 2 个支架"
    assert merged[0].quantity_decisions[0].quantity_delta == 2


def test_apply_semantic_to_references_skips_excluded_part_numbers(monkeypatch) -> None:
    monkeypatch.setattr("modules.sop.service.llm_service.api_key", "test-key")
    monkeypatch.setattr(
        "modules.sop.service.llm_service.extract_sop_semantic_references",
        lambda pages, excluded_part_numbers=None, **kwargs: [
            SopTextMaterial(
                part_number="242-00050",
                name="zip tie",
                quantity=2,
                confidence=0.9,
                quantity_explanation="忽略项不应进入结果",
                quantity_decisions=[],
            )
        ],
    )

    local = [SopPartReference(part_number="242-00050", occurrences=2, quantity=2, pages=[1])]
    merged, applied = _apply_semantic_to_references(
        local,
        [(1, "Stick zip tie 242-00050")],
        {"242-00050"},
    )

    assert applied is False
    assert merged == local

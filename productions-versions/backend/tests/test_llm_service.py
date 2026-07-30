from llm.models import SopTextChunkRequest
from llm.service import LLMService, choose_material_name


def test_parse_json_accepts_markdown_and_provider_prose() -> None:
    parsed = LLMService._parse_json('模型结果如下：\n```json\n{"materials": []}\n```')

    assert parsed == {"materials": []}


def test_parse_json_repairs_trailing_commas_and_empty_values() -> None:
    parsed = LLMService._parse_json(
        '{"materials":[{"part_number":"467-00004","name":"卡簧",'
        '"quantity": , "unit":"个", "confidence":0.9,},]}'
    )

    assert parsed["materials"][0]["part_number"] == "467-00004"
    assert parsed["materials"][0]["quantity"] is None


def test_parse_json_reports_context_for_unrecoverable_response() -> None:
    try:
        LLMService._parse_json('{"materials":[{"part_number":]}')
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected malformed JSON to raise ValueError")

    assert "附近内容" in message


def test_parse_json_recovers_complete_materials_from_truncated_response() -> None:
    parsed = LLMService._parse_json(
        '{"materials":['
        '{"part_number":"467-00004","name":"卡簧","quantity":4},'
        '{"part_number":"415-00888","name":"未完成'
    )

    assert parsed == {
        "materials": [
            {"part_number": "467-00004", "name": "卡簧", "quantity": 4}
        ]
    }


def test_choose_material_name_prefers_entity_over_instruction_sentence() -> None:
    assert choose_material_name("所有螺丝拧紧,需要确保柱塞块", "柱塞块") == "柱塞块"


def test_extract_material_prompt_requires_nearest_entity_name(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"materials":[{"part_number":"415-00635","name":"柱塞块","quantity":null,"unit":null,"confidence":0.95}]}'
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("llm.service.httpx.post", fake_post)
    service = LLMService()
    service.api_key = "test-key"

    materials = service.extract_sop_materials(
        SopTextChunkRequest(text="所有螺丝拧紧,需要确保柱塞块 415-00635")
    )

    payload = captured["json"]
    system_prompt = payload["messages"][0]["content"]  # type: ignore[index]
    assert "最短、最具体的物料实体名" in system_prompt
    assert "柱塞块 415-00635" in system_prompt
    assert "只按英文描述计算数量" in system_prompt
    assert "绝对不要把中英文数量相加" in system_prompt
    assert materials[0].name == "柱塞块"


def test_semantic_reference_prompt_classifies_added_and_reference_quantities(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"materials":['
                                '{"part_number":"415-00643","name":"支架","added_quantity":4,'
                                '"reference_quantity":0,"final_quantity":1,"confidence":0.98,"reason":"安装到柱塞块",'
                                '"decisions":[{"event_id":"E1","page_numbers":[1],"action":"安装",'
                                '"target":"415-00845","location":"","quantity_delta":4,"accumulate":true,'
                                '"duplicate_of":null,"reason":"新的安装目标","evidence":"Attach 4×415-00643"}]},'
                                '{"part_number":"415-00845","name":"柱塞块","added_quantity":0,'
                                '"reference_quantity":1,"final_quantity":1,"confidence":0.97,"reason":"装配目标"}'
                                "]}"
                            )
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("llm.service.httpx.post", fake_post)
    service = LLMService()
    service.api_key = "test-key"

    materials = service.extract_sop_semantic_references(
        [(1, "Attach 4×415-00643 to plunger block 415-00845")]
    )

    payload = captured["json"]
    system_prompt = payload["messages"][0]["content"]  # type: ignore[index]
    assert "锁紧、拧紧、检查" in system_prompt
    assert "repeat 96 times" in system_prompt
    assert "reference_quantity 应为 96" in system_prompt
    assert "跨页综合判断" in system_prompt
    assert "所有 accumulate=true" in system_prompt
    assert {item.part_number: item.quantity for item in materials} == {
        "415-00643": 1,
        "415-00845": 1,
    }
    bracket = next(item for item in materials if item.part_number == "415-00643")
    assert bracket.quantity_explanation.startswith("安装到柱塞块")
    assert "两者不一致时采用整篇上下文语义总数" in bracket.quantity_explanation
    assert bracket.quantity_decisions[0].quantity_delta == 4
    assert bracket.quantity_decisions[0].accumulate is True


def test_semantic_evidence_groups_keep_all_occurrences_of_a_part_together() -> None:
    service = LLMService()

    groups = service._build_part_evidence_groups(
        [
            (1, "Preparation notes\nInstall 2×438-00147 into 415-00845\nTorque 90N.cm"),
            (20, "Tighten 2×438-00147 on 415-00845"),
        ],
        max_chars=10000,
    )

    evidence = next(text for text, parts in groups if "438-00147" in parts)
    assert "第 1 页" in evidence
    assert "第 20 页" in evidence
    assert "Preparation notes" in evidence
    assert "Torque 90N.cm" in evidence


def test_semantic_evidence_groups_include_cleanup_candidate_part_numbers() -> None:
    service = LLMService()

    groups = service._build_part_evidence_groups(
        [(1, "Install 415-000656 and inspect 920-000131")],
        max_chars=10000,
    )

    part_numbers = {part_number for _, parts in groups for part_number in parts}
    assert part_numbers == {"415-000656", "920-000131"}


def test_semantic_evidence_groups_split_concatenated_layout_quantity_and_part() -> None:
    service = LLMService()

    groups = service._build_part_evidence_groups(
        [(63, "4×438-001474×415-00650")],
        max_chars=10000,
    )

    part_numbers = {part_number for _, parts in groups for part_number in parts}
    assert part_numbers == {"438-00147", "415-00650"}
    assert "438-001474" not in part_numbers

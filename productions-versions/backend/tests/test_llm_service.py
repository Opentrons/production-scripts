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
    assert materials[0].name == "柱塞块"

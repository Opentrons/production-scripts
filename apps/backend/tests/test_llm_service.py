import asyncio

from modules.agent.llm.models import SopTextChunkRequest
from modules.agent.llm.service import (
    LLMService,
    choose_material_name,
    resolve_material_part_number,
)


def test_openai_environment_variables_configure_service(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.bridgefloods.com")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("PRODUCTION_PLATFORM_LLM_API_KEY", "legacy-key")
    monkeypatch.setenv("PRODUCTION_PLATFORM_LLM_BASE_URL", "https://legacy.example/v1")
    monkeypatch.setenv("PRODUCTION_PLATFORM_LLM_MODEL", "legacy-model")

    service = LLMService()

    assert service.api_key == "openai-key"
    assert service.base_url == "https://api.bridgefloods.com/v1"
    assert service.model == "gpt-5.6-sol"


def test_resolve_material_part_number_repairs_pdf_quantity_concatenation() -> None:
    assert resolve_material_part_number(
        "2415-00733",
        "415-00734*2415-00733",
    ) == "415-00733"


def test_resolve_material_part_number_preserves_real_four_digit_part() -> None:
    assert resolve_material_part_number("2415-00733", "2*2415-00733") == "2415-00733"


def test_parse_json_accepts_markdown_and_provider_prose() -> None:
    parsed = LLMService._parse_json('模型结果如下：\n```json\n{"materials": []}\n```')

    assert parsed == {"materials": []}


def test_stream_chat_parses_openai_compatible_sse(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"生产"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"助手"}}]}'
            yield "data: [DONE]"

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, method, url, **kwargs):
            captured.update(method=method, url=url, **kwargs)
            return FakeResponse()

    monkeypatch.setattr("modules.agent.llm.service.httpx.AsyncClient", FakeClient)
    service = LLMService()
    service.api_key = "test-key"

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in service.stream_chat(
                [{"role": "user", "content": "测试"}],
                system_prompt="系统提示",
            )
        ]

    assert asyncio.run(collect()) == ["生产", "助手"]
    assert captured["method"] == "POST"
    assert captured["url"] == f"{service.base_url}/chat/completions"
    assert captured["json"] == {
        "model": service.model,
        "temperature": 0.2,
        "stream": True,
        "messages": [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "测试"},
        ],
    }


def test_stream_chat_ignores_usage_only_sse_frame(monkeypatch) -> None:
    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"OK"}}]}'
            yield 'data: {"choices":[],"usage":{"total_tokens":1}}'
            yield "data: [DONE]"

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("modules.agent.llm.service.httpx.AsyncClient", FakeClient)
    service = LLMService()
    service.api_key = "test-key"

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in service.stream_chat(
                [{"role": "user", "content": "测试"}],
                system_prompt="系统提示",
            )
        ]

    assert asyncio.run(collect()) == ["OK"]


def test_stream_tool_round_reassembles_fragmented_tool_calls(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_","function":{"name":"query_","arguments":"{\\"page\\":"}}]}}]}'
            yield 'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"1","function":{"name":"products","arguments":"1}"}}]}}]}'
            yield "data: [DONE]"

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, method, url, **kwargs):
            captured.update(method=method, url=url, **kwargs)
            return FakeResponse()

    monkeypatch.setattr("modules.agent.llm.service.httpx.AsyncClient", FakeClient)
    service = LLMService()
    service.api_key = "test-key"
    tools = [{"type": "function", "function": {"name": "query_products", "parameters": {"type": "object"}}}]

    async def collect():
        return [event async for event in service.stream_tool_round(
            [{"role": "user", "content": "查询"}],
            system_prompt="系统提示",
            tools=tools,
        )]

    events = asyncio.run(collect())

    assert events == [
        {
            "type": "round_done",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "query_products", "arguments": '{"page":1}'},
                    }
                ],
            },
        }
    ]
    assert captured["json"]["tools"] == tools  # type: ignore[index]
    assert captured["json"]["tool_choice"] == "auto"  # type: ignore[index]


def test_stream_tool_round_ignores_usage_only_sse_frame(monkeypatch) -> None:
    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"完成"}}]}'
            yield 'data: {"choices":[],"usage":{"total_tokens":1}}'
            yield "data: [DONE]"

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("modules.agent.llm.service.httpx.AsyncClient", FakeClient)
    service = LLMService()
    service.api_key = "test-key"

    async def collect() -> list[dict]:
        return [
            event
            async for event in service.stream_tool_round(
                [{"role": "user", "content": "测试"}],
                system_prompt="系统提示",
                tools=[],
            )
        ]

    assert asyncio.run(collect()) == [
        {"type": "chunk", "content": "完成"},
        {"type": "round_done", "message": {"role": "assistant", "content": "完成"}},
    ]


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

    monkeypatch.setattr(
        "modules.agent.llm.service.httpx.post",
        fake_post,
    )
    service = LLMService()
    service.api_key = "test-key"

    materials = service.extract_sop_materials(
        SopTextChunkRequest(text="所有螺丝拧紧,需要确保柱塞块 415-00635")
    )

    payload = captured["json"]
    system_prompt = payload["messages"][0]["content"]  # type: ignore[index]
    assert payload["max_tokens"] == service.sop_max_tokens  # type: ignore[index]
    assert "最短、最具体的物料实体名" in system_prompt
    assert "柱塞块 415-00635" in system_prompt
    assert "只按英文描述计算数量" in system_prompt
    assert "绝对不要把中英文数量相加" in system_prompt
    assert materials[0].name == "柱塞块"


def test_extract_materials_keeps_multipliers_out_of_part_numbers(monkeypatch) -> None:
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
                                '{"part_number":"438-006012","name":"螺丝","quantity":2},'
                                '{"part_number":"2*415-00390","name":"支架","quantity":2},'
                                '{"part_number":"999-99999","name":"不存在","quantity":1}'
                                "]}"
                            )
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("modules.agent.llm.service.httpx.post", fake_post)
    service = LLMService()
    service.api_key = "test-key"

    materials = service.extract_sop_materials(
        SopTextChunkRequest(text="Install 438-00601 *2 and 2*415-00390")
    )

    assert [(item.part_number, item.quantity) for item in materials] == [
        ("438-00601", 2),
        ("415-00390", 2),
    ]


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

    monkeypatch.setattr(
        "modules.agent.llm.service.httpx.post",
        fake_post,
    )
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
    assert "即使某页只出现物料名称" not in system_prompt
    assert {item.part_number: item.quantity for item in materials} == {
        "415-00643": 1,
        "415-00845": 1,
    }
    bracket = next(item for item in materials if item.part_number == "415-00643")
    assert bracket.quantity_explanation.startswith("安装到柱塞块")
    assert "两者不一致时采用整篇上下文语义总数" in bracket.quantity_explanation
    assert bracket.quantity_decisions[0].quantity_delta == 4
    assert bracket.quantity_decisions[0].accumulate is True


def test_semantic_evidence_groups_skip_excluded_part_numbers() -> None:
    service = LLMService()

    groups = service._build_part_evidence_groups(
        [
            (1, "Install 2×438-00147 into 415-00845"),
            (2, "Stick zip tie 242-00050 around harness"),
        ],
        max_chars=10000,
        excluded_part_numbers={"242-00050"},
    )

    part_numbers = {part_number for _, parts in groups for part_number in parts}
    assert part_numbers == {"438-00147", "415-00845"}
    assert "242-00050" not in part_numbers


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


def test_semantic_evidence_groups_include_confirmed_material_name_pages() -> None:
    service = LLMService()

    groups = service._build_part_evidence_groups(
        [
            (14, "Install 1×242-00052 around the harness"),
            (15, "Check the zip-tie position and trim the tail"),
            (16, "Inspect unrelated cable routing"),
        ],
        max_chars=10000,
        material_names={"242-00052": "扎带/zip-tie"},
    )

    evidence = next(text for text, parts in groups if "242-00052" in parts)
    assert "已确认物料名称：扎带/zip-tie" in evidence
    assert "第 14 页" in evidence
    assert "第 15 页" in evidence
    assert "第 16 页" not in evidence


def test_semantic_evidence_groups_limit_name_expansion_to_target_parts() -> None:
    service = LLMService()

    groups = service._build_part_evidence_groups(
        [
            (14, "Install 1×242-00052 around the harness"),
            (15, "Use one zip-tie to secure the harness"),
            (20, "Install 1×242-00059 around the cable"),
            (21, "Check the magnetic ring position"),
        ],
        max_chars=10000,
        material_names={
            "242-00052": "扎带/zip-tie",
            "242-00059": "磁环/magnetic ring",
        },
        target_part_numbers={"242-00052"},
    )

    assert {part_number for _, parts in groups for part_number in parts} == {"242-00052"}
    evidence = groups[0][0]
    assert "第 15 页" in evidence
    assert "第 20 页" not in evidence
    assert "第 21 页" not in evidence


def test_semantic_evidence_groups_ignore_shared_generic_material_names() -> None:
    service = LLMService()

    groups = service._build_part_evidence_groups(
        [
            (1, "Install 2×438-00147"),
            (2, "Install 4×438-00213"),
            (3, "Tighten all screws"),
        ],
        max_chars=10000,
        material_names={"438-00147": "螺丝/screw", "438-00213": "螺丝/screw"},
    )

    evidence_by_part = {
        part_number: evidence
        for evidence, part_numbers in groups
        for part_number in part_numbers
    }
    assert "第 3 页" not in evidence_by_part["438-00147"]
    assert "第 3 页" not in evidence_by_part["438-00213"]


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

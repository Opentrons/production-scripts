from __future__ import annotations

from typing import Any

from modules.agent.tools import google_sheets, knowledge, opentrons, platform
from modules.agent.tools.runtime import AgentTool, ToolExecutionResult, execute_handler


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


def _string(description: str, *, enum: list[str] | None = None, default: str | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "description": description}
    if enum:
        schema["enum"] = enum
    if default is not None:
        schema["default"] = default
    return schema


def _integer(description: str, default: int, minimum: int = 1, maximum: int = 2000) -> dict[str, Any]:
    return {"type": "integer", "description": description, "default": default, "minimum": minimum, "maximum": maximum}


def _boolean(description: str, default: bool = False) -> dict[str, Any]:
    return {"type": "boolean", "description": description, "default": default}


def build_tools() -> list[AgentTool]:
    pagination = {
        "page": _integer("页码", 1),
        "page_size": _integer("每页数量", 20, maximum=100),
    }
    record_filters = {
        "status": _string("状态筛选，空字符串表示不限", default=""),
        "model": _string("产品型号筛选，空字符串表示不限", default=""),
        "barcode": _string("条码或 SN 模糊筛选", default=""),
        "start_date": _string("开始日期 YYYY-MM-DD", default=""),
        "end_date": _string("结束日期 YYYY-MM-DD", default=""),
    }
    confirm = _boolean("用户已明确确认本次外部写操作。未确认必须传 false", False)
    return [
        AgentTool("get_current_time", "获取当前北京时间和日期。", _object({}), platform.current_time, "utility"),
        AgentTool("get_platform_overview", "获取全平台概览，包括运行模式、上传统计、产品数、设备、版本、监控房间、消息和工作流。适合先判断平台整体状态。", _object({}), platform.platform_overview),
        AgentTool("query_upload_records", "查询 CSV 上传记录及每次上传的解析、Google Drive、Unit Tracker、Slack 状态和错误。", _object({**record_filters, **pagination}), platform.query_upload_records),
        AgentTool("analyze_upload_records", "统计上传完成数、成功数、失败数、运行数、成功率、产品良率和测试耗时。", _object(record_filters), platform.analyze_upload_records),
        AgentTool("query_products", "查询产品管理中的条码、型号、OEM、测试过程和产品状态。", _object({"barcode": _string("条码模糊查询", default=""), "model": _string("型号", default=""), "test_type": _string("测试类型", default=""), "status": _string("产品状态", default=""), **pagination}), platform.query_products),
        AgentTool("query_unit_tracker", "查询 Unit Tracker。mongodb 来源是上传 CSV 解析行；google_drive 来源直接读取总表，且必须指定产品和测试类型。", _object({"source": _string("数据来源", enum=["mongodb", "google_drive"], default="mongodb"), "product": _string("产品，如 P2HH、P50M、Robot", default=""), "test_type": _string("测试类型，如 Assembly QC、Gravimetric", default=""), "barcode": _string("条码筛选", default=""), **pagination, "refresh": _boolean("Google Drive 模式是否跳过缓存", False)}), platform.query_unit_tracker),
        AgentTool("list_data_links", "列出各产品测试的 Google 模板、Unit Tracker 和原始数据文件夹链接。", _object({}), platform.list_data_links),
        AgentTool("list_test_data_collections", "列出测试数据库中可查询的 pipette 数据集合。", _object({}), platform.list_test_data_collections),
        AgentTool("query_test_data", "查询标准测试数据库，支持跨集合或指定集合按产品、类型、结果、条码和日期筛选。", _object({"collection": _string("集合名；__all__ 表示全部", default="__all__"), "model": _string("产品型号", default=""), "production_type": _string("产品类型", default=""), "total_result": _string("测试总结果", default=""), "barcode": _string("条码", default=""), "start_date": _string("开始日期 YYYY-MM-DD", default=""), "end_date": _string("结束日期 YYYY-MM-DD", default=""), **pagination}), platform.query_test_data),
        AgentTool("query_devices", "读取设备扫描缓存，或按 IP 获取 Flex 的真实健康、SN、仪器和服务信息。", _object({"ip": _string("设备 IPv4；空字符串返回全部缓存设备", default=""), "include_detail": _boolean("提供 IP 时是否实时读取设备详情", False)}), platform.query_devices),
        AgentTool("query_version_history", "查询 Robot/Instrument 固件版本历史，或按 IP 实时读取 Robot 和子系统版本。", _object({"ip": _string("设备 IPv4；为空查询历史", default=""), **pagination}), platform.query_version_history),
        AgentTool("query_protocol_monitor", "查询 Protocol 监控房间和设备；指定 room_id 可刷新空闲、离线、运行状态及脚本名。", _object({"room_id": _string("房间 ID", default=""), "refresh_status": _boolean("是否实时刷新房间设备状态", False)}), platform.query_protocol_monitor),
        AgentTool("query_workflows", "查询 BOM/SOP 工作流、配置和最近运行结果。", _object({"workflow_id": _string("工作流 ID；为空返回全部", default=""), "include_runs": _boolean("是否包含运行记录", True), "limit": _integer("运行记录数量", 20, maximum=100)}), platform.query_workflows),
        AgentTool("query_test_cases", "查询测试管理中的产品测试用例和可视化流程节点。", _object({"product_id": _string("产品 ID", default=""), "test_type": _string("测试类型", default=""), "include_archived": _boolean("是否包含已归档用例", False)}), platform.query_test_cases),
        AgentTool("search_sop_catalog", "读取并搜索 Google SOP 总表中的项目、工序、发布日期、状态和 PDF 链接。", _object({"query": _string("项目、工序或状态关键词", default=""), "refresh": _boolean("是否跳过缓存重新读取 Google Sheet", False), "limit": _integer("最大返回行数", 30, maximum=100)}), platform.search_sop_catalog),
        AgentTool("query_platform_messages", "查询平台上传消息和未读异常消息。", _object({"limit": _integer("返回数量", 30, maximum=50), "unread_only": _boolean("仅返回未读消息", False)}), platform.query_messages),
        AgentTool("query_platform_database", "对允许的平台数据集执行安全只读 JSON 查询。支持字段选择、排序和过滤，不允许任意数据库或危险操作符。", _object({"dataset": _string("数据集", enum=["upload_records", "messages", "product_management", "unit_tracker", "version_history", "protocol_rooms", "robot_scan_cache", "test_cases", "test_data"]), "collection_name": _string("dataset=test_data 时指定集合", default=""), "filters": {"type": "object", "description": "Mongo 风格只读过滤条件", "default": {}}, "fields": {"type": "array", "items": {"type": "string"}, "description": "仅返回这些字段", "default": []}, "sort_by": _string("排序字段", default=""), "sort_direction": _string("排序方向", enum=["asc", "desc"], default="desc"), "limit": _integer("最大记录数", 50, maximum=200)}, ["dataset"]), platform.query_platform_database),
        AgentTool("aggregate_platform_database", "对允许的平台数据集做分组计数、求和、平均值、最小值或最大值，用于业务数据分析。", _object({"dataset": _string("数据集", enum=["upload_records", "messages", "product_management", "unit_tracker", "version_history", "protocol_rooms", "robot_scan_cache", "test_cases", "test_data"]), "collection_name": _string("dataset=test_data 时指定集合", default=""), "filters": {"type": "object", "description": "过滤条件", "default": {}}, "group_by": _string("分组字段；为空汇总全部", default=""), "value_field": _string("数值字段；count 时可为空", default=""), "operation": _string("聚合操作", enum=["count", "sum", "average", "min", "max"], default="count"), "limit": _integer("最多分析记录数", 2000, maximum=2000)}, ["dataset"]), platform.aggregate_platform_database),
        AgentTool("get_spreadsheet_info", "读取 Google 表格标题、时区、所有工作表名称、gid 和网格大小。", _object({"spreadsheet_id": _string("Google Sheet ID 或 URL")}, ["spreadsheet_id"]), google_sheets.get_spreadsheet_info, "google_sheets"),
        AgentTool("read_sheet_range", "读取 Google Sheet 指定 A1 区域，可按行或列返回。", _object({"spreadsheet_id": _string("Google Sheet ID 或 URL"), "range_name": _string("A1 区域，例如 'Sheet1'!A1:F100"), "major_dimension": _string("返回维度", enum=["ROWS", "COLUMNS"], default="ROWS"), "max_rows": _integer("最大返回行或列数", 300, maximum=1000)}, ["spreadsheet_id", "range_name"]), google_sheets.read_sheet_range, "google_sheets"),
        AgentTool("create_spreadsheet", "新建 Google 表格，可指定首个工作表名和 Drive 文件夹。属于外部写操作。", _object({"title": _string("表格标题"), "sheet_title": _string("首个工作表名称", default="Sheet1"), "folder_id": _string("可选 Drive 文件夹 ID", default=""), "confirm": confirm}, ["title"]), google_sheets.create_spreadsheet, "google_sheets", True),
        AgentTool("add_sheet", "在现有 Google 表格中新增工作表。属于外部写操作。", _object({"spreadsheet_id": _string("Google Sheet ID 或 URL"), "title": _string("新工作表名称"), "confirm": confirm}, ["spreadsheet_id", "title"]), google_sheets.add_sheet, "google_sheets", True),
        AgentTool("update_sheet_range", "覆盖 Google Sheet 指定区域的值。属于外部写操作，必须提供二维 values。", _object({"spreadsheet_id": _string("Google Sheet ID 或 URL"), "range_name": _string("A1 区域"), "values": {"type": "array", "items": {"type": "array", "items": {}}, "description": "二维单元格值"}, "value_input_option": _string("写入解析模式", enum=["RAW", "USER_ENTERED"], default="USER_ENTERED"), "confirm": confirm}, ["spreadsheet_id", "range_name", "values"]), google_sheets.update_sheet_range, "google_sheets", True),
        AgentTool("append_sheet_rows", "向 Google Sheet 区域末尾追加新行。属于外部写操作。", _object({"spreadsheet_id": _string("Google Sheet ID 或 URL"), "range_name": _string("目标工作表或区域"), "values": {"type": "array", "items": {"type": "array", "items": {}}, "description": "要追加的二维行"}, "value_input_option": _string("写入解析模式", enum=["RAW", "USER_ENTERED"], default="USER_ENTERED"), "confirm": confirm}, ["spreadsheet_id", "range_name", "values"]), google_sheets.append_sheet_rows, "google_sheets", True),
        AgentTool("clear_sheet_range", "清空 Google Sheet 指定区域。属于破坏性外部写操作。", _object({"spreadsheet_id": _string("Google Sheet ID 或 URL"), "range_name": _string("要清空的 A1 区域"), "confirm": confirm}, ["spreadsheet_id", "range_name"]), google_sheets.clear_sheet_range, "google_sheets", True),
        AgentTool("copy_sheet", "把一个工作表复制到另一个 Google 表格。属于外部写操作。", _object({"source_spreadsheet_id": _string("源表格 ID 或 URL"), "sheet_id": _integer("源工作表 gid", 0, minimum=0, maximum=2147483647), "destination_spreadsheet_id": _string("目标表格 ID 或 URL"), "confirm": confirm}, ["source_spreadsheet_id", "sheet_id", "destination_spreadsheet_id"]), google_sheets.copy_sheet, "google_sheets", True),
        AgentTool("get_opentrons_knowledge_status", "检查 Opentrons 官方文档目录和服务器本地源码是否可用，并返回源码目录与 Git revision。", _object({}), opentrons.get_opentrons_knowledge_status, "opentrons"),
        AgentTool("search_opentrons_official_docs", "检索 Opentrons 官网产品、Python Protocol API、Robot HTTP API、Flex 手册和 Labware Library 文档入口。找到文档后使用 read_opentrons_official_doc 读取原文。", _object({"query": _string("产品名、API 类、方法、endpoint 或问题关键词"), "limit": _integer("最大结果数", 8, maximum=20)}, ["query"]), opentrons.search_opentrons_official_docs, "opentrons"),
        AgentTool("read_opentrons_official_doc", "读取指定 Opentrons 官方网页的正文。优先传 search_opentrons_official_docs 返回的 document_id；大型页面应传 query 直接抽取 endpoint、方法或产品关键词附近的段落；url 仅允许 Opentrons 官方 HTTPS 域名。", _object({"document_id": _string("官方文档目录 ID", default=""), "url": _string("Opentrons 官方 HTTPS URL", default=""), "query": _string("可选正文关键词，例如 POST /runs 或 transfer", default=""), "max_chars": _integer("最大正文字数", 16000, minimum=1000, maximum=30000)}), opentrons.read_opentrons_official_doc, "opentrons"),
        AgentTool("search_opentrons_source", "只读检索服务器的 Opentrons monorepo，返回 Git revision、源码相对路径、行号和命中片段。Protocol 脚本或 HTTP API 技术问题应优先检索对应 scope。", _object({"query": _string("类、函数、路由、endpoint、错误文本或代码关键词"), "scope": _string("检索范围", enum=["all", "protocol_api", "http_api", "products", "docs", "tests"], default="all"), "path": _string("可选仓库内相对目录/文件，留空按 scope 检索", default=""), "root": _string("可选工具状态返回的源码根目录，留空自动选择", default=""), "limit": _integer("最大命中行数", 20, maximum=50)}, ["query"]), opentrons.search_opentrons_source, "opentrons"),
        AgentTool("read_opentrons_source", "按相对路径和行号只读 Opentrons 源码或仓库内文档。必须先通过源码检索取得路径，不允许读取仓库之外或生成目录中的文件。", _object({"path": _string("Opentrons 仓库内相对文件路径"), "root": _string("可选源码根目录，留空自动选择", default=""), "start_line": _integer("起始行", 1, maximum=1000000), "end_line": _integer("结束行；单次最多读取 400 行", 200, maximum=1000000)}, ["path"]), opentrons.read_opentrons_source, "opentrons"),
        AgentTool("search_knowledge", "按关键词检索生产平台知识库。回答平台规则、排障经验、SOP 或业务约定前优先调用。", _object({"query": _string("知识检索关键词"), "category": _string("可选分类", default=""), "limit": _integer("最大结果数", 8, maximum=50)}, ["query"]), knowledge.search_knowledge, "knowledge"),
        AgentTool("list_knowledge", "列出知识库文档和分类。", _object({"category": _string("分类；空字符串表示全部", default=""), "limit": _integer("最大结果数", 30, maximum=200)}), knowledge.list_knowledge, "knowledge"),
        AgentTool("save_knowledge", "新增或更新一条可复用的生产知识。仅当用户明确要求记录知识时使用。", _object({"title": _string("知识标题"), "content": _string("准确、完整的知识正文"), "category": _string("分类", default="general"), "tags": {"type": "array", "items": {"type": "string"}, "default": []}, "source": _string("知识来源", default="agent"), "document_id": _string("更新已有文档时提供 ID", default=""), "confirm": confirm}, ["title", "content"]), knowledge.save_knowledge, "knowledge", True),
        AgentTool("delete_knowledge", "删除非内置知识文档。属于破坏性操作。", _object({"document_id": _string("知识文档 ID"), "confirm": confirm}, ["document_id"]), knowledge.delete_knowledge, "knowledge", True),
    ]


class ToolRegistry:
    def __init__(self, tools: list[AgentTool] | None = None) -> None:
        selected = tools if tools is not None else build_tools()
        self._tools = {tool.name: tool for tool in selected}
        if len(self._tools) != len(selected):
            raise ValueError("工具名称不能重复")

    @property
    def count(self) -> int:
        return len(self._tools)

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema for tool in self._tools.values()]

    def describe(self) -> list[dict[str, Any]]:
        return [
            {"name": tool.name, "description": tool.description, "category": tool.category, "mutating": tool.mutating}
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        tool = self._tools.get(str(name or ""))
        if tool is None:
            return ToolExecutionResult(tool=str(name or "unknown"), ok=False, error="未知工具")
        if not isinstance(arguments, dict):
            return ToolExecutionResult(tool=tool.name, ok=False, error="工具参数必须是 JSON 对象")
        return await execute_handler(tool, arguments)


tool_registry = ToolRegistry()

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import core.config as setting
from core.database import mongodb
from modules.agent.knowledge.models import KnowledgeDocument, KnowledgeDocumentInput


_TOKEN_PATTERN = re.compile(r"[a-z0-9_.-]+|[\u3400-\u4dbf\u4e00-\u9fff]+", re.IGNORECASE)

PLATFORM_KNOWLEDGE = (
    {
        "id": "platform-data-upload",
        "title": "生产数据上传与上传记录",
        "category": "platform",
        "tags": ["数据上传", "CSV", "Google Drive", "Slack", "上传记录"],
        "content": "数据上传模块负责解析生产 CSV、识别产品和测试类型、写入标准数据库、更新 Google Unit Tracker，并记录 Google Drive 与 Slack 的执行状态。排查失败时应查询上传记录的 status、error、file_desc、result 和 request_started_at。",
    },
    {
        "id": "platform-unit-tracker",
        "title": "Unit Tracker 双数据源",
        "category": "platform",
        "tags": ["Unit Tracker", "MongoDB", "Google Sheet"],
        "content": "Unit Tracker 支持 MongoDB CSV 标准行和 Google Drive 总表两种模式。MongoDB 模式来自上传 CSV 的解析结果；Google Drive 模式直接读取配置的数据总表，不依赖数据库，并按产品和测试类型转换为标准列。",
    },
    {
        "id": "platform-device-management",
        "title": "设备管理与机器人状态",
        "category": "platform",
        "tags": ["设备管理", "Robot", "Flex", "子系统", "Protocol"],
        "content": "设备管理通过局域网扫描 Flex，展示健康状态、API Level、Robot SN、仪器信息和子系统版本。设备详情支持 HTTP API、SSH、Protocol、日志、文件和版本查询。只读诊断优先使用缓存扫描结果，再按明确 IP 查询设备详情。",
    },
    {
        "id": "platform-protocol-monitor",
        "title": "Protocol 监控平台",
        "category": "platform",
        "tags": ["Protocol", "监控", "房间", "运行状态"],
        "content": "Protocol 监控平台按房间维护设备，状态包括空闲、离线和运行。运行状态通过 Robot Server runs 接口判断，并解析具体 Protocol 脚本名称。",
    },
    {
        "id": "platform-sop-bom",
        "title": "SOP 与 BOM 版本核对",
        "category": "platform",
        "tags": ["SOP", "BOM", "Duro", "工作流", "版本核对"],
        "content": "BOM 版本模块从 Google SOP 总表读取项目文件，解析 PDF 中料号和数量，并与 Duro BOM 核对。工作流报告包含缺失、冗余、数量差异、数量未知和忽略项。",
    },
    {
        "id": "platform-test-data",
        "title": "测试数据库与数据分析",
        "category": "platform",
        "tags": ["测试数据", "MongoDB", "质量分析", "良率"],
        "content": "测试数据位于 ProductionsData 数据库的 pipette_* 集合。平台可按产品、类型、结果、条码和日期查询。上传记录统计提供完成数、成功数、失败数、运行数、成功率、各产品统计和测试耗时。",
    },
    {
        "id": "platform-version-management",
        "title": "设备版本查询与历史",
        "category": "platform",
        "tags": ["版本", "固件", "Revision", "Robot SN", "查询历史"],
        "content": "版本查询读取 Robot、gantry_x、gantry_y、head、rear_panel 或 instrument 的固件与 Revision，并记录条码、测试过程、测试版本和查询时间。历史记录按产品条码聚合多个 test_name。",
    },
    {
        "id": "platform-test-management",
        "title": "测试用例管理",
        "category": "platform",
        "tags": ["测试管理", "测试用例", "流程节点"],
        "content": "测试管理按产品和测试类型维护可视化测试用例。用例由开始、命令、等待输入和结束等节点及连线组成，可查询树形目录和具体流程。",
    },
    {
        "id": "opentrons-knowledge-routing",
        "title": "Opentrons 技术知识取证规则",
        "category": "opentrons",
        "tags": ["Opentrons", "官网", "源码", "Protocol API", "HTTP API", "知识库"],
        "content": "回答 Opentrons 产品、Protocol API、HTTP API、脚本或源码问题时，先调用 Opentrons 专用工具取证。公开产品和 API 用法以 docs.opentrons.com、opentrons.com 与 Labware Library 为依据；实际部署行为以服务器本地 Opentrons monorepo 的 Git revision 和目标 Robot 的 /openapi.json 为准。答案应给出官方 URL，或源码相对路径、行号和 revision。",
    },
    {
        "id": "opentrons-protocol-api",
        "title": "Python Protocol API 与脚本编写",
        "category": "opentrons",
        "tags": ["Python", "Protocol API", "ProtocolContext", "apiLevel", "Flex", "OT-2", "脚本"],
        "content": "Python Protocol API 用于编写 Flex 或 OT-2 的机器人 Protocol。Protocol 通常声明 metadata/requirements，并实现 run(protocol: protocol_api.ProtocolContext)。编写前必须确认 robotType、目标 Robot 支持的 apiLevel、pipette、tip rack、labware load name、deck 位置、体积和操作步骤。具体方法、参数和版本兼容性应检索官方 Python API 文档，并读取本地 docs/python-api/docs 或 api/src/opentrons/protocol_api 对应实现。官方入口：https://docs.opentrons.com/python-api/",
    },
    {
        "id": "opentrons-http-api",
        "title": "Robot Server HTTP API",
        "category": "opentrons",
        "tags": ["HTTP API", "Robot Server", "OpenAPI", "curl", "runs", "protocols", "commands"],
        "content": "Robot Server HTTP API 是网络接口，与 Python Protocol API 不同。官网 OpenAPI 参考为 https://docs.opentrons.com/http/api_reference.html；目标 Robot 可通过 /openapi.json 获取其实际接口定义。服务器本地实现位于 robot-server/robot_server，路由汇总位于 robot-server/robot_server/router.py。回答 endpoint、header、body 或响应结构时必须检索并读取当前源码或目标机器 OpenAPI，避免用其他软件版本的接口行为代替当前部署。",
    },
    {
        "id": "opentrons-source-map",
        "title": "Opentrons Monorepo 源码导航",
        "category": "opentrons",
        "tags": ["monorepo", "源码", "robot-server", "protocol_api", "protocol_engine", "shared-data", "ot3"],
        "content": "Opentrons monorepo 中，api/src/opentrons/protocol_api 是公开 Python Protocol API 实现；api/src/opentrons/protocol_engine 是 Protocol 分析和执行引擎；robot-server/robot_server 是 Robot HTTP API 服务；docs/python-api/docs 是 Python API 官网文档源码；docs/flex/docs 是 Flex 手册源码；shared-data 保存 labware 等跨项目定义。源码中 ot3/OT-3 通常是 Flex 的内部型号标识。生产助手自动识别 ~/projects/opentrons、~/projects/opentorns 和 /opentrons，也可由 PRODUCTION_PLATFORM_OPENTRONS_SOURCE_ROOTS 指定。",
    },
    {
        "id": "opentrons-product-resources",
        "title": "Opentrons 产品与官方资源",
        "category": "opentrons",
        "tags": ["产品", "Flex", "OT-2", "pipette", "gripper", "module", "Labware Library"],
        "content": "Opentrons 产品问题应从官网当前产品目录与对应手册取证。机器人目录：https://opentrons.com/products/categories/robots；Flex 产品页：https://opentrons.com/products/opentrons-flex-robot；Flex 手册：https://docs.opentrons.com/flex/；Labware Library：https://labware.opentrons.com/。产品配置和兼容性可能随版本变化，回答时不要仅依赖这条摘要，应读取官方页面正文。",
    },
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(value: Any) -> set[str]:
    text = str(value or "").casefold()
    tokens: set[str] = set()
    for match in _TOKEN_PATTERN.findall(text):
        token = match.strip()
        if not token:
            continue
        tokens.add(token)
        if re.fullmatch(r"[\u3400-\u4dbf\u4e00-\u9fff]+", token) and len(token) > 2:
            tokens.update(token[index : index + 2] for index in range(len(token) - 1))
    return tokens


class KnowledgeService:
    def __init__(self) -> None:
        self._seed_lock = threading.RLock()
        self._seeded = False

    @property
    def storage(self) -> str:
        return "sqlite" if setting.use_sqlite_persistence() else "mongodb"

    def _collection(self):
        if setting.use_sqlite_persistence():
            from core.sqlite_store import get_platform_store

            return get_platform_store()[setting.AGENT_KNOWLEDGE_COLLECTION]
        if mongodb.client is None and not mongodb.connect():
            raise RuntimeError("知识库数据库连接失败")
        collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.AGENT_KNOWLEDGE_COLLECTION]
        collection.create_index("category")
        collection.create_index("updated_at")
        return collection

    def ensure_seeded(self) -> None:
        with self._seed_lock:
            if self._seeded:
                return
            collection = self._collection()
            now = _now()
            for seed in PLATFORM_KNOWLEDGE:
                collection.update_one(
                    {"_id": seed["id"]},
                    {
                        "$set": {
                            **seed,
                            "source": "builtin",
                            "metadata": {"managed": True},
                            "updated_at": now,
                        },
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
            self._seeded = True

    def count(self) -> int:
        self.ensure_seeded()
        return self._collection().count_documents({})

    @staticmethod
    def _serialize(document: dict[str, Any]) -> dict[str, Any]:
        payload = dict(document)
        payload["id"] = str(payload.pop("_id", payload.get("id") or ""))
        payload.setdefault("title", "")
        payload.setdefault("content", "")
        payload.setdefault("category", "general")
        payload.setdefault("tags", [])
        payload.setdefault("source", "manual")
        payload.setdefault("metadata", {})
        payload.setdefault("created_at", payload.get("updated_at") or _now())
        payload.setdefault("updated_at", payload["created_at"])
        return payload

    def list_documents(self, *, category: str | None = None, limit: int = 50) -> dict[str, Any]:
        self.ensure_seeded()
        documents = [self._serialize(item) for item in self._collection().find({})]
        normalized_category = str(category or "").strip().casefold()
        if normalized_category:
            documents = [
                item for item in documents
                if str(item.get("category") or "").casefold() == normalized_category
            ]
        documents.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        limited = documents[: max(1, min(int(limit), 200))]
        return {"documents": limited, "total": len(documents), "storage": self.storage}

    def search(self, query: str, *, category: str | None = None, limit: int = 8) -> dict[str, Any]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return self.list_documents(category=category, limit=limit)
        query_tokens = _tokens(normalized_query)
        documents = self.list_documents(category=category, limit=500)["documents"]
        scored: list[tuple[int, dict[str, Any]]] = []
        query_folded = normalized_query.casefold()
        for document in documents:
            title = str(document.get("title") or "")
            content = str(document.get("content") or "")
            tags = " ".join(str(item) for item in document.get("tags") or [])
            title_tokens = _tokens(title)
            tag_tokens = _tokens(tags)
            content_tokens = _tokens(content)
            score = 8 * len(query_tokens & title_tokens)
            score += 5 * len(query_tokens & tag_tokens)
            score += 2 * len(query_tokens & content_tokens)
            if query_folded in title.casefold():
                score += 20
            if query_folded in content.casefold():
                score += 8
            if score > 0:
                result = dict(document)
                result["score"] = score
                scored.append((score, result))
        scored.sort(key=lambda item: (item[0], str(item[1].get("updated_at") or "")), reverse=True)
        results = [item for _, item in scored[: max(1, min(int(limit), 50))]]
        return {"documents": results, "total": len(scored), "storage": self.storage, "query": normalized_query}

    def upsert(self, payload: KnowledgeDocumentInput, *, document_id: str | None = None) -> KnowledgeDocument:
        self.ensure_seeded()
        doc_id = str(document_id or f"knowledge_{uuid4().hex[:16]}").strip()
        now = _now()
        document = {
            "title": payload.title.strip(),
            "content": payload.content.strip(),
            "category": payload.category.strip() or "general",
            "tags": list(dict.fromkeys(str(tag).strip() for tag in payload.tags if str(tag).strip())),
            "source": payload.source.strip() or "manual",
            "metadata": payload.metadata,
            "updated_at": now,
        }
        self._collection().update_one(
            {"_id": doc_id},
            {"$set": document, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        stored = self._collection().find_one({"_id": doc_id}) or {"_id": doc_id, **document, "created_at": now}
        return KnowledgeDocument.model_validate(self._serialize(stored))

    def delete(self, document_id: str) -> bool:
        self.ensure_seeded()
        normalized_id = str(document_id or "").strip()
        if not normalized_id:
            raise ValueError("知识文档 ID 不能为空")
        document = self._collection().find_one({"_id": normalized_id})
        if document and (document.get("metadata") or {}).get("managed"):
            raise ValueError("内置平台知识不能删除")
        return self._collection().delete_one({"_id": normalized_id}).deleted_count > 0


knowledge_service = KnowledgeService()

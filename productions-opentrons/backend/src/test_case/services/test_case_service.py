from __future__ import annotations

from collections import defaultdict
from typing import Any

from test_case.models.domain import (
    NodePosition,
    TestCase,
    TestCaseCreate,
    TestCaseEdge,
    TestCaseInputOption,
    TestCaseListResponse,
    TestCaseNode,
    TestCaseTreeCase,
    TestCaseTreeGroup,
    TestCaseTreeProduct,
    TestCaseTreeResponse,
    TestCaseUpdate,
    TestProduct,
    TestProductCreate,
    TestType,
    TestTypeCreate,
)
from test_case.repositories import TestCaseRepository, test_case_repository


class TestCaseValidationError(ValueError):
    pass


def dump_model(model: Any, *, exclude_unset: bool = False) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=exclude_unset)
    return model.dict(exclude_unset=exclude_unset)


def copy_model(model: Any, *, update: dict[str, Any]):
    if hasattr(model, "model_copy"):
        return model.model_copy(update=update)
    return model.copy(update=update)


def model_fields(model_class: Any) -> list[str]:
    fields = getattr(model_class, "model_fields", None)
    if fields is None:
        fields = getattr(model_class, "__fields__")
    return list(fields)


class TestCaseService:
    def __init__(self, repository: TestCaseRepository) -> None:
        self.repository = repository

    def list_cases(
        self,
        *,
        product_id: str | None = None,
        test_type: str | None = None,
        include_archived: bool = False,
    ) -> TestCaseListResponse:
        cases = self.repository.list_cases(
            product_id=product_id,
            test_type=test_type,
            include_archived=include_archived,
        )
        return TestCaseListResponse(cases=cases, total=len(cases))

    def get_tree(self) -> TestCaseTreeResponse:
        products: dict[str, dict[str, object]] = {}
        grouped_cases: dict[str, dict[str, list[TestCase]]] = defaultdict(lambda: defaultdict(list))
        catalog_types: dict[str, set[str]] = defaultdict(set)

        for product in self.repository.list_products():
            products[product.product_id] = {
                "product_id": product.product_id,
                "product_name": product.product_name,
            }
            for test_type in self.repository.list_types(product.product_id):
                catalog_types[product.product_id].add(test_type.test_type)

        for item in self.repository.list_cases():
            products[item.product_id] = {
                "product_id": item.product_id,
                "product_name": item.product_name,
            }
            catalog_types[item.product_id].add(item.test_type)
            grouped_cases[item.product_id][item.test_type].append(item)

        tree_products: list[TestCaseTreeProduct] = []
        for product_id in sorted(products):
            product = products[product_id]
            groups: list[TestCaseTreeGroup] = []
            total = 0
            for test_type in sorted(catalog_types[product_id]):
                cases = grouped_cases[product_id][test_type]
                case_nodes = [
                    TestCaseTreeCase(
                        id=item.id,
                        name=item.name,
                        status=item.status,
                        test_type=item.test_type,
                        updated_at=item.updated_at,
                    )
                    for item in cases
                ]
                total += len(case_nodes)
                groups.append(TestCaseTreeGroup(test_type=test_type, total=len(case_nodes), cases=case_nodes))
            tree_products.append(
                TestCaseTreeProduct(
                    product_id=str(product["product_id"]),
                    product_name=str(product["product_name"]),
                    total=total,
                    groups=groups,
                )
            )

        return TestCaseTreeResponse(products=tree_products, total=sum(item.total for item in tree_products))

    def create_product(self, payload: TestProductCreate) -> TestProduct:
        if not payload.product_id.strip():
            raise TestCaseValidationError("产品 ID 不能为空")
        if not payload.product_name.strip():
            raise TestCaseValidationError("产品名称不能为空")
        return self.repository.create_product(payload)

    def create_type(self, product_id: str, payload: TestTypeCreate) -> TestType | None:
        if not payload.test_type.strip():
            raise TestCaseValidationError("测试类型不能为空")
        return self.repository.create_type(product_id, payload)

    def get_case(self, case_id: str) -> TestCase | None:
        return self.repository.get_case(case_id)

    def create_case(self, payload: TestCaseCreate) -> TestCase:
        normalized = self._with_default_flow(payload)
        self._validate_flow(normalized.nodes, normalized.edges)
        return self.repository.create_case(normalized)

    def update_case(self, case_id: str, payload: TestCaseUpdate) -> TestCase | None:
        current = self.repository.get_case(case_id)
        if current is None:
            return None

        merged_data = dump_model(current)
        merged_data.update(dump_model(payload, exclude_unset=True))
        candidate = TestCaseCreate(**{key: merged_data[key] for key in model_fields(TestCaseCreate)})
        self._validate_flow(candidate.nodes, candidate.edges)
        return self.repository.update_case(case_id, payload)

    def archive_case(self, case_id: str) -> TestCase | None:
        return self.repository.archive_case(case_id)

    def _with_default_flow(self, payload: TestCaseCreate) -> TestCaseCreate:
        if payload.nodes:
            return payload

        start_node = TestCaseNode(
            id="start",
            name="开始测试",
            kind="start",
            position=NodePosition(x=80, y=160),
        )
        expect_node = TestCaseNode(
            id="expect_1",
            name="等待设备输出",
            kind="expect",
            expect="input your name:",
            input_kind="text",
            position=NodePosition(x=330, y=160),
        )
        end_node = TestCaseNode(
            id="end",
            name="结束测试",
            kind="end",
            position=NodePosition(x=590, y=160),
        )
        expect_node.input_options = [
            TestCaseInputOption(label="输入字符串", value=""),
        ]
        return copy_model(
            payload,
            update={
                "nodes": [start_node, expect_node, end_node],
                "edges": [
                    TestCaseEdge(id="edge_start_expect_1", source=start_node.id, target=expect_node.id),
                    TestCaseEdge(id="edge_expect_1_end", source=expect_node.id, target=end_node.id),
                ],
            },
        )

    def _validate_flow(self, nodes: list[TestCaseNode], edges: list[TestCaseEdge]) -> None:
        start_nodes = [item for item in nodes if item.kind == "start"]
        end_nodes = [item for item in nodes if item.kind == "end"]
        if len(start_nodes) != 1:
            raise TestCaseValidationError("测试用例需要且只能有一个开始节点")
        if len(end_nodes) != 1:
            raise TestCaseValidationError("测试用例需要且只能有一个结束节点")

        node_ids = {item.id for item in nodes}
        for edge in edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise TestCaseValidationError("节点连线包含不存在的节点")


test_case_service = TestCaseService(test_case_repository)

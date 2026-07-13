from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database.mongodb import mongodb
from test_case.config import (
    TEST_CASE_CATALOG_COLLECTION_NAME,
    TEST_CASE_COLLECTION_NAME,
    TEST_CASE_DB_NAME,
)
from test_case.models.domain import (
    TestCase,
    TestCaseCreate,
    TestCaseUpdate,
    TestProduct,
    TestProductCreate,
    TestType,
    TestTypeCreate,
)


def dump_model(model: Any, *, exclude_unset: bool = False) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=exclude_unset)
    return model.dict(exclude_unset=exclude_unset)


def doc_datetime(value: Any) -> datetime:
    return value if isinstance(value, datetime) else datetime.now(timezone.utc)


class TestCaseRepository:
    """Repository boundary for the test_cases collection."""

    def __init__(self) -> None:
        self._indexes_ready = False

    def _database(self):
        if mongodb.client is None and not mongodb.connect():
            raise RuntimeError("Test case database connection failed")

        return mongodb.get_database(TEST_CASE_DB_NAME)

    def _collection(self):
        collection = self._database()[TEST_CASE_COLLECTION_NAME]
        if not self._indexes_ready:
            collection.create_index("id", unique=True)
            collection.create_index([("product_id", 1), ("test_type", 1), ("updated_at", -1)])
            collection.create_index("status")
            self._catalog_collection().create_index("product_id", unique=True)
            self._catalog_collection().create_index("types.test_type")
            self._indexes_ready = True
        return collection

    def _catalog_collection(self):
        return self._database()[TEST_CASE_CATALOG_COLLECTION_NAME]

    def _from_doc(self, doc: dict[str, Any] | None) -> TestCase | None:
        if doc is None:
            return None
        doc.pop("_id", None)
        return TestCase(**doc)

    def _product_from_doc(self, doc: dict[str, Any] | None) -> TestProduct | None:
        if doc is None:
            return None
        doc.pop("_id", None)
        return TestProduct(
            product_id=doc["product_id"],
            product_name=doc["product_name"],
            created_at=doc_datetime(doc.get("created_at")),
            updated_at=doc_datetime(doc.get("updated_at")),
        )

    def list_products(self) -> list[TestProduct]:
        cursor = self._catalog_collection().find({}, {"_id": 0}).sort("product_name", 1)
        products: list[TestProduct] = []
        for item in cursor:
            products.append(
                TestProduct(
                    product_id=item["product_id"],
                    product_name=item["product_name"],
                    created_at=doc_datetime(item.get("created_at")),
                    updated_at=doc_datetime(item.get("updated_at")),
                )
            )
        return products

    def get_product(self, product_id: str) -> TestProduct | None:
        return self._product_from_doc(self._catalog_collection().find_one({"product_id": product_id}, {"_id": 0}))

    def create_product(self, payload: TestProductCreate) -> TestProduct:
        now = datetime.now(timezone.utc)
        existing = self.get_product(payload.product_id)
        if existing is None:
            self._catalog_collection().insert_one(
                {
                    "product_id": payload.product_id,
                    "product_name": payload.product_name,
                    "types": [],
                    "created_at": now,
                    "updated_at": now,
                }
            )
        else:
            self._catalog_collection().update_one(
                {"product_id": payload.product_id},
                {"$set": {"product_name": payload.product_name, "updated_at": now}},
            )
        product = self.get_product(payload.product_id)
        if product is None:
            raise RuntimeError("Product catalog write failed")
        return product

    def list_types(self, product_id: str) -> list[TestType]:
        product = self._catalog_collection().find_one({"product_id": product_id}, {"_id": 0, "types": 1})
        if product is None:
            return []
        types = product.get("types") or []
        return [
            TestType(
                product_id=product_id,
                test_type=item["test_type"],
                created_at=doc_datetime(item.get("created_at")),
                updated_at=doc_datetime(item.get("updated_at")),
            )
            for item in sorted(types, key=lambda value: value.get("test_type", ""))
        ]

    def create_type(self, product_id: str, payload: TestTypeCreate) -> TestType | None:
        product = self.get_product(product_id)
        if product is None:
            return None

        now = datetime.now(timezone.utc)
        existing = self._catalog_collection().find_one(
            {"product_id": product_id, "types.test_type": payload.test_type},
            {"_id": 0},
        )
        if existing is None:
            self._catalog_collection().update_one(
                {"product_id": product_id},
                {
                    "$push": {
                        "types": {
                            "test_type": payload.test_type,
                            "created_at": now,
                            "updated_at": now,
                        }
                    },
                    "$set": {"updated_at": now},
                },
            )
        return TestType(product_id=product_id, test_type=payload.test_type, created_at=now, updated_at=now)

    def list_cases(
        self,
        *,
        product_id: str | None = None,
        test_type: str | None = None,
        include_archived: bool = False,
    ) -> list[TestCase]:
        query: dict[str, Any] = {}
        if not include_archived:
            query["status"] = {"$ne": "archived"}
        if product_id:
            query["product_id"] = product_id
        if test_type:
            query["test_type"] = test_type

        cursor = self._collection().find(query, {"_id": 0}).sort("updated_at", -1)
        return [TestCase(**item) for item in cursor]

    def get_case(self, case_id: str) -> TestCase | None:
        return self._from_doc(self._collection().find_one({"id": case_id}, {"_id": 0}))

    def create_case(self, payload: TestCaseCreate) -> TestCase:
        self.create_product(TestProductCreate(product_id=payload.product_id, product_name=payload.product_name))
        self.create_type(payload.product_id, TestTypeCreate(test_type=payload.test_type))
        test_case = TestCase(**dump_model(payload))
        self._collection().insert_one(dump_model(test_case))
        return test_case

    def update_case(self, case_id: str, payload: TestCaseUpdate) -> TestCase | None:
        current = self.get_case(case_id)
        if current is None:
            return None

        update_data = dump_model(payload, exclude_unset=True)
        update_data["revision"] = current.revision + 1
        update_data["updated_at"] = datetime.now(timezone.utc)
        self._collection().update_one({"id": case_id}, {"$set": update_data})
        return self.get_case(case_id)

    def archive_case(self, case_id: str) -> TestCase | None:
        current = self.get_case(case_id)
        if current is None:
            return None
        self._collection().update_one(
            {"id": case_id},
            {
                "$set": {
                    "status": "archived",
                    "revision": current.revision + 1,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return self.get_case(case_id)


test_case_repository = TestCaseRepository()

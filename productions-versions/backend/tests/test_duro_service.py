import sqlite3

from duro.models import DuroProduct, DuroProductSearchRequest, DuroProductSearchResponse
from duro.service import DuroService


class FakeDuroClient:
    def __init__(self) -> None:
        self.call_count = 0
        self.base_url = "https://mfg.duro.app"

    def search_products(self, payload: DuroProductSearchRequest) -> DuroProductSearchResponse:
        self.call_count += 1
        return DuroProductSearchResponse(
            count=1,
            products=[DuroProduct.model_validate({"_id": "id", "name": "Robot"})],
            request=payload,
        )

    def get_product(self, product_id: str):
        self.call_count += 1
        return {
            "_id": product_id,
            "name": "OT-3",
            "cpn": "8100000001",
            "revision": "A1",
            "status": "PRODUCTION",
            "children": [
                {
                    "_id": "bom-line-1",
                    "quantity": 4,
                    "itemNumber": 10,
                    "refDes": ["M1", "M2", "M3", "M4"],
                    "component": {
                        "_id": "component-1",
                        "name": "Motor",
                        "cpn": "2200000001",
                        "revision": "B",
                        "status": "PRODUCTION",
                        "children": [{"_id": "child-hint"}],
                    },
                }
            ],
        }

    def get_component(self, component_id: str):
        self.call_count += 1
        return {
            "_id": component_id,
            "name": "Motor",
            "children": [
                {
                    "_id": "bom-line-2",
                    "quantity": "2",
                    "component": {
                        "_id": "component-2",
                        "name": "Bearing",
                        "cpn": "2200000002",
                        "children": [],
                    },
                }
            ],
        }


def test_product_search_uses_cache() -> None:
    client = FakeDuroClient()
    service = DuroService(client, cache_seconds=300)  # type: ignore[arg-type]
    payload = DuroProductSearchRequest()

    first = service.search_products(payload)
    second = service.search_products(payload)

    assert first.cached is False
    assert second.cached is True
    assert client.call_count == 1


def test_product_page_cache_survives_service_restart(tmp_path) -> None:
    cache_path = tmp_path / "duro-cache.sqlite3"
    first_client = FakeDuroClient()
    first_service = DuroService(
        first_client, cache_seconds=300, cache_path=cache_path  # type: ignore[arg-type]
    )
    first_service.list_products()

    second_client = FakeDuroClient()
    second_service = DuroService(
        second_client, cache_seconds=300, cache_path=cache_path  # type: ignore[arg-type]
    )
    response = second_service.list_products()

    assert response.cached is True
    assert response.products[0].name == "Robot"
    assert second_client.call_count == 0


def test_persistent_cache_is_not_expired_by_legacy_timestamp(tmp_path) -> None:
    cache_path = tmp_path / "duro-cache.sqlite3"
    first_client = FakeDuroClient()
    first_service = DuroService(first_client, cache_seconds=300, cache_path=cache_path)  # type: ignore[arg-type]
    first_service.list_products()
    with sqlite3.connect(cache_path) as connection:
        connection.execute("UPDATE duro_cache SET expires_at = 0")

    second_client = FakeDuroClient()
    second_service = DuroService(second_client, cache_seconds=300, cache_path=cache_path)  # type: ignore[arg-type]
    cached = second_service.list_products()

    assert cached.cached is True
    assert second_client.call_count == 0


def test_refresh_replaces_persistent_product_cache(tmp_path) -> None:
    cache_path = tmp_path / "duro-cache.sqlite3"
    client = FakeDuroClient()
    service = DuroService(
        client, cache_seconds=300, cache_path=cache_path  # type: ignore[arg-type]
    )

    service.list_products()
    refreshed = service.list_products(refresh=True)

    assert refreshed.cached is False
    assert client.call_count == 2


def test_product_bom_maps_relationship_fields_and_uses_cache() -> None:
    client = FakeDuroClient()
    service = DuroService(client, cache_seconds=300)  # type: ignore[arg-type]

    first = service.get_product_bom("product-id")
    second = service.get_product_bom("product-id")

    assert first.root.id == "product-id"
    assert first.root.name == "OT-3"
    assert first.direct_child_count == 1
    assert first.root.children[0].id == "component-1"
    assert first.root.children[0].quantity == 4
    assert first.root.children[0].item_number == 10
    assert first.root.children[0].reference_designators == ["M1", "M2", "M3", "M4"]
    assert first.root.children[0].has_children is True
    assert second.cached is True
    assert client.call_count == 1


def test_component_children_are_loaded_one_level_at_a_time() -> None:
    client = FakeDuroClient()
    service = DuroService(client, cache_seconds=300)  # type: ignore[arg-type]

    response = service.get_component_children("component-1")

    assert response.count == 1
    assert response.children[0].id == "component-2"
    assert response.children[0].quantity == "2"
    assert response.children[0].has_children is False

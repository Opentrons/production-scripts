import sqlite3

from modules.duro.models import (
    DuroProduct,
    DuroProductSearchRequest,
    DuroProductSearchResponse,
    DuroVersionComponent,
    DuroVersionGroup,
)
from modules.duro.service import DuroService


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


class AppUrlOnlyDuroClient(FakeDuroClient):
    def __init__(self) -> None:
        super().__init__()
        del self.base_url
        self.app_url = "https://mfg.duro.app"


class VersionDuroClient(FakeDuroClient):
    def search_products(self, payload: DuroProductSearchRequest) -> DuroProductSearchResponse:
        self.call_count += 1
        return DuroProductSearchResponse(
            count=1,
            products=[
                DuroProduct.model_validate(
                    {"_id": "product-id", "name": "OT3", "cpn": "999-00191", "revision": "D1.3"}
                )
            ],
            request=payload,
        )

    def get_product(self, product_id: str):
        self.call_count += 1
        return {
            "_id": product_id,
            "name": "OT3",
            "cpn": "999-00191",
            "revision": "D1.3",
            "children": [
                {
                    "quantity": 1,
                    "component": {
                        "_id": "version-parent",
                        "name": "FLEX ROBOT SOFTWARE FIRMWARE TOUCHPOINTS",
                        "cpn": "991-00147",
                    },
                }
            ],
        }

    def get_component(self, component_id: str):
        self.call_count += 1
        if component_id == "version-parent":
            return {
                "_id": component_id,
                "name": "FLEX ROBOT SOFTWARE FIRMWARE TOUCHPOINTS",
                "cpn": "991-00147",
                "revision": "A7.8",
                "description": "Software and firmware touchpoints",
                "children": [
                    {
                        "quantity": 1,
                        "component": {
                            "_id": "child-component",
                            "name": "FLEX ROBOT - Z STAGE TEST",
                            "cpn": "710-00047",
                            "revision": "A1.4",
                            "category": "Firmware",
                            "description": (
                                "App: v8.8.0\n"
                                "Firmware: V67\n"
                                "Tag: abcdef1234567"
                            ),
                            "specs": [{"key": "Owner", "value": "Test"}],
                            "children": [
                                {
                                    "quantity": 2,
                                    "component": {
                                        "_id": "nested-component",
                                        "name": "Nested test script",
                                        "cpn": "710-00048",
                                        "description": "App: v1.2.3",
                                        "children": [],
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        return {"_id": component_id, "name": "Unknown", "children": []}


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
    assert first.root.child_count == 1
    assert first.root.children[0].child_count == 1
    assert first.material_total_count == 1
    assert first.root.children[0].quantity == 4
    assert first.root.children[0].item_number == 10
    assert first.root.children[0].reference_designators == ["M1", "M2", "M3", "M4"]
    assert first.root.children[0].has_children is True
    assert first.source_url == "https://mfg.duro.app/product/view/product-id"
    assert second.cached is True
    assert client.call_count == 2


def test_product_bom_source_url_does_not_require_legacy_base_url() -> None:
    client = AppUrlOnlyDuroClient()
    service = DuroService(client, cache_seconds=300)  # type: ignore[arg-type]

    response = service.get_product_bom("product-id")

    assert response.source_url == "https://mfg.duro.app/product/view/product-id"


def test_component_children_are_loaded_one_level_at_a_time() -> None:
    client = FakeDuroClient()
    service = DuroService(client, cache_seconds=300)  # type: ignore[arg-type]

    response = service.get_component_children("component-1")

    assert response.count == 1
    assert response.children[0].id == "component-2"
    assert response.children[0].child_count == 0
    assert response.children[0].quantity == "2"
    assert response.children[0].has_children is False


def test_version_catalog_finds_software_parents_and_extracts_child_details(monkeypatch) -> None:
    client = VersionDuroClient()
    service = DuroService(client, cache_seconds=300)  # type: ignore[arg-type]
    monkeypatch.setattr(
        service,
        "_resolve_github_commit_id",
        lambda ref: f"resolved-{ref}" if ref == "abcdef1234567" else None,
    )

    response = service.get_version_catalog(refresh=True)

    assert response.products_scanned == 1
    assert response.matched_products == 1
    assert response.parent_menu_count == 1
    assert response.child_component_count == 2
    group = response.groups[0]
    assert group.product_cpn == "999-00191"
    assert group.parent_cpn == "991-00147"
    child = group.children[0]
    assert child.cpn == "710-00047"
    assert child.app_version == "v8.8.0"
    assert child.firmware_version == "v67"
    assert child.test_commit_hash == "abcdef1234567"
    assert child.test_commit_id == "resolved-abcdef1234567"
    assert child.test_tag is None
    assert group.children[1].app_version == "v1.2.3"


def test_version_details_only_extract_app_and_fw_labels() -> None:
    assert DuroService._extract_version("App: v8.8.0", "app") == "v8.8.0"
    assert DuroService._extract_version("FW：V67", "firmware") == "v67"
    assert DuroService._extract_version("Firmware: 67", "firmware") == "v67"
    assert DuroService._extract_version("FW: controller-v52", "firmware") == "v52"
    assert DuroService._extract_version("Firmware: controller/V52", "firmware") == "v52"
    assert DuroService._extract_version("Desktop App: v8.8.0", "app") == "v8.8.0"
    assert DuroService._extract_version("Robot Firmware: V67", "firmware") == "v67"
    assert DuroService._extract_version("API (App) Version: v8.8.0", "app") == "v8.8.0"
    assert DuroService._extract_version("API/App Version = 8.8.0", "app") == "v8.8.0"
    assert DuroService._extract_version("FW Version: controller/v67", "firmware") == "v67"
    assert DuroService._extract_version("Firmware Version = 67", "firmware") == "v67"
    assert DuroService._extract_version("No version here", "app") == ""


def test_version_details_extract_commit_hash_from_tag_scripts_and_protocol() -> None:
    assert DuroService._extract_commit_hash("Tag: abcdef1234567") == "abcdef1234567"
    assert DuroService._extract_commit_hash("Hardware Testing Tag: mp.robot.qc.2026.9.1") == "mp.robot.qc.2026.9.1"
    assert DuroService._extract_commit_hash("Release Branch: release-9.2") == "release-9.2"
    assert DuroService._extract_commit_hash("Hardware Testing Branch: hardware-testing/main") == "hardware-testing/main"
    assert DuroService._extract_commit_hash("Testing Commit Hash: abcdef1234567890") == "abcdef1234567890"
    assert DuroService._extract_commit_hash("Git SHA = abcdef1234567890") == "abcdef1234567890"
    assert DuroService._extract_commit_hash("Testing Commit Hash: `SERIAL`mp.gripper.diagnostics-24.08.05-1") == "mp.gripper.diagnostics-24.08.05-1"
    assert DuroService._extract_commit_hash("Testing Commit Hash:\nSERIAL\nmp.gripper.diagnostics-24.08.05-1") == "mp.gripper.diagnostics-24.08.05-1"
    assert DuroService._extract_commit_hash("Scripts: mp.pipette.qc.2026.6.9") == "mp.pipette.qc.2026.6.9"
    assert (
        DuroService._extract_commit_hash(
            "Scripts: mp.pipette.qc.2026.6.9\n"
            "https://github.com/Opentrons/opentrons/tree/mp.pipette.qc.2026.6.9"
        )
        == "mp.pipette.qc.2026.6.9"
    )
    assert (
        DuroService._extract_commit_hash(
            "Scripts:\nhttps://github.com/Opentrons/opentrons/tree/mp.pipette.qc.2026.6.9"
        )
        == "mp.pipette.qc.2026.6.9"
    )
    assert (
        DuroService._extract_commit_hash(
            "Scripts: https://github.com/Opentrons/opentrons/tree/abcdef1234567"
        )
        == "abcdef1234567"
    )
    assert (
        DuroService._extract_commit_hash(
            "Script: https://github.com/Opentrons/opentrons/tree/main/hardware-testing/foo"
        )
        == "main/hardware-testing/foo"
    )
    assert (
        DuroService._extract_commit_hash(
            "Protocol: https://github.com/Opentrons/opentrons/blob/main/protocols/flex_z_stage.py"
        )
        == "flex_z_stage.py"
    )
    assert DuroService._extract_commit_hash("Protocol: path/to/stage_test.py") == "stage_test.py"
    # Branch/Tag are higher-priority than generic script links; once a priority
    # level is found, extraction stops.
    assert (
        DuroService._extract_commit_hash(
            "Tag: tagged-ref\nBranch: branch-ref\nScripts: https://example.com/tree/from-scripts"
        )
        == "branch-ref"
    )
    assert (
        DuroService._extract_commit_hash(
            "Tag: tagged-ref\nScripts: https://example.com/tree/from-scripts\nProtocol: a/b.py"
        )
        == "tagged-ref"
    )
    assert DuroService._extract_commit_hash("No commit here") is None


def test_commits_page_url_and_resolvable_refs() -> None:
    assert (
        DuroService.commits_page_url("mp.pipette.qc.2026.6.9")
        == "https://github.com/Opentrons/opentrons/commits/mp.pipette.qc.2026.6.9/"
    )
    assert DuroService._is_resolvable_commit_ref("mp.pipette.qc.2026.6.9") is True
    assert DuroService._is_resolvable_commit_ref("flex_z_stage.py") is False
    assert DuroService._is_resolvable_commit_ref("hardware-testing/main") is True


def test_enrich_commit_ids_resolves_unique_refs(monkeypatch) -> None:
    client = FakeDuroClient()
    service = DuroService(client, cache_seconds=300)  # type: ignore[arg-type]
    calls: list[str] = []

    def fake_resolve(ref: str) -> str | None:
        calls.append(ref)
        return f"sha-{ref}"

    monkeypatch.setattr(service, "_resolve_github_commit_id", fake_resolve)
    groups = [
        DuroVersionGroup(
            product_id="p1",
            parent_id="parent",
            children=[
                DuroVersionComponent(
                    id="c1",
                    name="one",
                    test_commit_hash="mp.pipette.qc.2026.6.9",
                    source_text="",
                ),
                DuroVersionComponent(
                    id="c2",
                    name="two",
                    test_commit_hash="mp.pipette.qc.2026.6.9",
                    source_text="",
                ),
                DuroVersionComponent(
                    id="c3",
                    name="protocol",
                    test_commit_hash="stage_test.py",
                    source_text="",
                ),
            ],
        )
    ]

    service._enrich_commit_ids(groups)

    assert calls == ["mp.pipette.qc.2026.6.9"]
    assert groups[0].children[0].test_commit_id == "sha-mp.pipette.qc.2026.6.9"
    assert groups[0].children[1].test_commit_id == "sha-mp.pipette.qc.2026.6.9"
    assert groups[0].children[2].test_commit_id is None


def test_version_parent_requires_both_software_and_firmware_keywords() -> None:
    assert DuroService._is_version_parent({"name": "Software touchpoints"}) is False
    assert DuroService._is_version_parent({"name": "Firmware touchpoints"}) is False
    assert DuroService._is_version_parent({"name": "Software / Firmware touchpoints"}) is True

from modules.supplies.models import SupplementaryMaterialCreate, SupplementaryMaterialUpdate
from modules.supplies.repository import (
    DuplicateSupplementaryMaterialError,
    SupplementaryMaterialRepository,
)
from modules.supplies.seed import INITIAL_SUPPLEMENTARY_MATERIALS


def test_initial_supplies_are_seeded_once_and_support_crud(tmp_path) -> None:
    database_path = tmp_path / "supplementary-materials.sqlite3"
    repository = SupplementaryMaterialRepository(database_path, seed_initial=True)

    seeded = repository.list()
    assert len(seeded) == len(INITIAL_SUPPLEMENTARY_MATERIALS)
    assert seeded[0].material_number == "242-00049"

    created = repository.create(
        SupplementaryMaterialCreate(
            material_number="999-00001",
            english_name="Test Supply",
            chinese_name="测试辅料",
            eid="E1",
        )
    )
    assert repository.list("测试辅料")[0].id == created.id

    try:
        repository.create(SupplementaryMaterialCreate(material_number="999-00001"))
    except DuplicateSupplementaryMaterialError:
        pass
    else:
        raise AssertionError("expected duplicate material number to fail")

    updated = repository.update(
        created.id,
        SupplementaryMaterialUpdate(chinese_name="更新后的辅料", eid="E2"),
    )
    assert updated is not None
    assert updated.chinese_name == "更新后的辅料"
    assert updated.eid == "E2"

    assert repository.delete(created.id) is True
    assert repository.get(created.id) is None


def test_seed_marker_prevents_deleted_seed_from_returning(tmp_path) -> None:
    database_path = tmp_path / "supplementary-materials.sqlite3"
    repository = SupplementaryMaterialRepository(database_path, seed_initial=True)
    first_item = repository.list()[0]
    assert repository.delete(first_item.id) is True

    reopened = SupplementaryMaterialRepository(database_path, seed_initial=True)

    assert len(reopened.list()) == len(INITIAL_SUPPLEMENTARY_MATERIALS) - 1
    assert all(item.id != first_item.id for item in reopened.list())

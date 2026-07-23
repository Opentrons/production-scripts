from upload_handler.uploaders.common import UploadCommonMixin
import pytest


def test_normalize_csv_columns_expands_a_to_ap() -> None:
    columns = UploadCommonMixin.normalize_csv_columns(["A-AP"])

    assert len(columns) == 42
    assert columns[0] == "A"
    assert columns[-1] == "AP"


def test_prepare_csv_batch_updates_uses_expanded_range_width() -> None:
    csv_data = [[["value"]]]

    values, ranges = UploadCommonMixin.prepare_csv_batch_updates(csv_data, ["A-AP"])

    assert len(values[0][0]) == 42
    assert ranges == ["!A1:AP1"]


def test_prepare_csv_batch_updates_rejects_nonempty_columns_outside_range() -> None:
    csv_data = [[["a", "b", "must-not-be-dropped"]]]

    with pytest.raises(ValueError, match="data beyond configured range A-B"):
        UploadCommonMixin.prepare_csv_batch_updates(csv_data, ["A-B"])


def test_prepare_csv_batch_updates_allows_empty_trailing_columns() -> None:
    csv_data = [[["a", "b", "", ""]]]

    values, ranges = UploadCommonMixin.prepare_csv_batch_updates(csv_data, ["A-B"])

    assert values == [[['a', 'b']]]
    assert ranges == ["!A1:B1"]

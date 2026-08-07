from pathlib import Path

import pytest
import yaml

from modules.uploads.handler.drivers.csv_driver import CsvDriver
from modules.uploads.handler.uploaders.common import UploadCommonMixin


UPLOAD_CONFIG_DIR = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "modules"
    / "uploads"
    / "handler"
    / "configs"
)


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


def test_prepare_csv_batch_updates_truncates_columns_outside_range() -> None:
    csv_data = [[["a", "b", "not-uploaded"]]]

    values, ranges = UploadCommonMixin.prepare_csv_batch_updates(csv_data, ["A-B"])

    assert values == [[["a", "b"]]]
    assert ranges == ["!A1:B1"]


def test_prepare_csv_batch_updates_allows_empty_trailing_columns() -> None:
    csv_data = [[["a", "b", "", ""]]]

    values, ranges = UploadCommonMixin.prepare_csv_batch_updates(csv_data, ["A-B"])

    assert values == [[['a', 'b']]]
    assert ranges == ["!A1:B1"]


def test_csv_driver_reads_only_configured_column_count(tmp_path: Path) -> None:
    csv_path = tmp_path / "report.csv"
    csv_path.write_text("a,b,c,d,e,f\n1,2,3,4,5,6\n", encoding="utf-8")

    rows = CsvDriver().read_csv_rows(str(csv_path), max_columns=4)

    assert rows == [
        [["a", "b", "c", "d"]],
        [["1", "2", "3", "4"]],
    ]


@pytest.mark.parametrize("config_name", ["upload_debug.yaml", "upload_production.yaml"])
def test_gravimetric_upload_uses_configured_a_to_d_columns(config_name: str) -> None:
    config = yaml.safe_load((UPLOAD_CONFIG_DIR / config_name).read_text(encoding="utf-8"))

    for upload_key in ("1ch_update_volume", "8ch_update_volume"):
        configured_range = config[upload_key][0]["Range"]
        columns = UploadCommonMixin.normalize_csv_columns(configured_range)

        csv_data = [[["a", "b", "c", "d", "not-uploaded"]]]
        values, ranges = UploadCommonMixin.prepare_csv_batch_updates(
            csv_data, configured_range
        )

        assert columns == ["A", "B", "C", "D"]
        assert values == [[["a", "b", "c", "d"]]]
        assert ranges == ["!A1:D1"]

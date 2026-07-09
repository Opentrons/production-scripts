from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, TypedDict


# ---------------------------------------------------------------------------
# 上传方法返回值 Schema（内部层）
# 所有产品 upload 方法（update_*）统一返回 UploadResult.to_dict()。
# ---------------------------------------------------------------------------


class UploadResultFields(TypedDict, total=False):
    """上传方法内部返回字段定义。

    各测试类型只会填充与其相关的字段，未涉及的字段不出现在返回值中。
    """

    # --- 公共标识 ---
    sn: str
    """设备序列号。"""

    model: str
    """产品型号，如 P50S、P1000M、P1KH。"""

    type: str
    """OEM 厂商类型，如 Opentrons、Ultima、Millipore。"""

    # --- 链接 ---
    csv_link: str
    """测试数据 Google Spreadsheet 链接。"""

    unit_tracker: str
    """Unit Tracker 汇总表链接；粘贴失败或未执行时为 "N/A"。"""

    unit_tracker_status: str
    """Unit Tracker 上传状态说明。"""

    missing_tests: list[str]
    """组合测试中尚未完成的测试字段。"""

    raw_data: str
    """原始数据 zip 所在 Drive 文件夹链接；无 zip 或未上传时为 "N/A"。"""

    raw_data_name: str
    """原始数据上传到 Drive 后创建的文件夹名。"""

    database_saved: bool
    """上传结果是否已成功写入 MongoDB。"""

    error: str
    """上传流程失败原因。"""

    # --- 数据写入状态（bool）非公共字段，可填也可不填写---
    gravimetric: bool
    """1/8 通道 Gravimetric：CSV 是否成功写入 Spreadsheet。"""

    assembly_qc: bool
    """1/8 通道 Assembly QC：CSV 是否成功写入 Spreadsheet。"""

    current_speed: bool
    """1/8 通道 Current/Speed：CSV 是否成功写入 Spreadsheet。"""

    ninety_six_assembly_qc: bool
    """96 通道 Assembly QC：CSV 是否成功写入 Spreadsheet。"""

    z_stage_test: bool

    xy_calibration: bool

    gantry_stress_test: bool

    leveling_test: bool


    # --- 测试结果（Pass / Fail 字符串）---
    total_result: str

    """本次上传 workflow 的总测试结果；为空时跳过 Unit Tracker 粘贴步骤。"""


# 各测试类型的专用 Schema（继承公共字段，便于类型标注与文档）

class GravimetricUploadResult(UploadResultFields, total=False):
    """1/8 通道 Gravimetric 上传返回值。

    方法: SpreadsheetUploader.upload
    必填: sn, model, type, total_result, csv_link, unit_tracker
    """

    total_result: str


class AssemblyQcUploadResult(UploadResultFields, total=False):
    """1/8 通道 Robot Gripper Assembly QC 上传返回值。

    方法: SpreadsheetUploader.upload
    必填: sn, model, type, assembly_qc, total_result, csv_link
    可选: unit_tracker, raw_data
    """

    assembly_qc: bool
    total_result: str


class CurrentSpeedUploadResult(UploadResultFields, total=False):
    """1/8 通道 Current/Speed 上传返回值。

    方法: SpreadsheetUploader.upload
    必填: sn, model, type, current_speed, total_result, csv_link
    可选: unit_tracker, raw_data
    """

    current_speed: bool
    total_result: str


class AssemblyQc96ChUploadResult(UploadResultFields, total=False):
    """96 通道 Assembly QC 上传返回值。

    方法: SpreadsheetUploader.upload
    必填: sn, model, type, ninety_six_assembly_qc, total_result, csv_link
    可选: unit_tracker, raw_data
    """

    ninety_six_assembly_qc: bool
    total_result: str

class ZStageQcRobotUploadResult(UploadResultFields, total=False):
    """Z Stage QC 上传返回值。

    方法: SpreadsheetUploader.upload
    必填: sn, model, type, z_stage_test, total_result, csv_link
    可选: unit_tracker, raw_data
    """
    z_stage_test: bool
    total_result: str

class XYCalibrationRobotUploadResult(UploadResultFields, total=False):
    """XY Calibration 上传返回值。

    方法: SpreadsheetUploader.upload
    必填: sn, model, type, xy_calibration, total_result, csv_link
    可选: unit_tracker, raw_data
    """
    xy_calibration: bool
    total_result: str

class GantryStressRobotUploadResult(UploadResultFields, total=False):
    """Gantry Stress Test 上传返回值。

    方法: SpreadsheetUploader.upload
    必填: sn, model, type, gantry_stress_test, total_result, csv_link
    可选: unit_tracker, raw_data
    """
    gantry_stress_test: bool
    total_result: str

class LevelingRobotUploadResult(UploadResultFields, total=False):
    """Leveling Test 上传返回值。

    方法: SpreadsheetUploader.upload
    必填: sn, model, type, leveling_test, total_result, csv_link
    可选: unit_tracker, raw_data
    """
    leveling_test: bool
    total_result: str




# ---------------------------------------------------------------------------
# API 层返回 Schema（外部层）, 不需要更改，已经统一
# update_data_to_google_drive 对外统一返回此结构。
# ---------------------------------------------------------------------------


class UploadApiResponse(TypedDict, total=False):
    """上传 API 统一响应格式。"""

    finished: bool
    """是否上传成功。"""

    error: str | None
    """失败原因；成功时为 None。"""

    production_name: str
    """产品展示名，如 "Opentrons P1000S"。"""

    test_type: str
    """测试类型展示名，如 "Assembly QC"。"""

    test_result: str
    """主测试结果（Pass / Fail）。"""

    sn: str
    """设备序列号。"""

    csv_link: str
    """测试数据 Spreadsheet 链接。"""

    unit_tracker: str
    """Unit Tracker 链接。"""

    unit_tracker_status: str
    """Unit Tracker 上传状态说明。"""

    missing_tests: list[str]
    """组合测试中尚未完成的测试字段。"""

    raw_data: str
    """原始数据 zip 所在 Drive 文件夹链接。"""

    raw_data_name: str
    """原始数据上传到 Drive 后创建的文件夹名。"""


# ---------------------------------------------------------------------------
# 构建器
# ---------------------------------------------------------------------------


@dataclass
class UploadResult:
    """上传结果构建器，统一各 upload 方法的输出格式。

    用法::

        result = UploadResult.base(sn=device_sn, model=model, production_type=kind)
        result.set_csv_link(sheetlink)
        result.set_test_result(
            upload_flag_field="assembly_qc",
            upload_ok=True,
            result="Pass",
        )
        return result.to_dict()
    """

    sn: str = ""
    model: str = ""
    type: str = ""
    csv_link: str = ""
    unit_tracker: str = "N/A"
    unit_tracker_status: str = ""
    missing_tests: list[str] | None = None
    raw_data: str = "N/A"
    raw_data_name: str = ""
    database_saved: bool | None = None
    error: str | None = None
    # Known upload status fields are explicit; new upload status fields use extra_fields.
    gravimetric: bool | None = None
    assembly_qc: bool | None = None
    current_speed: bool | None = None
    ninety_six_assembly_qc: bool | None = None
    z_stage_test: bool | None = None
    xy_calibration: bool | None = None
    gantry_stress_test: bool | None = None
    leveling_test: bool | None = None
    total_result: str | None = None
    extra_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def base(cls, *, sn: str, model: str, production_type: str) -> UploadResult:
        """创建包含公共标识字段的结果对象。"""
        return cls(sn=sn, model=model, type=production_type)

    def set_csv_link(self, link: str) -> UploadResult:
        self.csv_link = link
        return self

    def set_unit_tracker(self, link: str) -> UploadResult:
        self.unit_tracker = link
        return self

    def set_unit_tracker_status(self, status: str, missing_tests: list[str] | None = None) -> UploadResult:
        self.unit_tracker_status = status
        self.missing_tests = missing_tests
        return self

    def set_raw_data(self, link: str, name: str = "") -> UploadResult:
        self.raw_data = link
        self.raw_data_name = name
        return self

    def set_database_saved(self, saved: bool) -> UploadResult:
        self.database_saved = saved
        return self

    def set_error(self, error: str) -> UploadResult:
        self.error = error
        return self

    def set_test_result(
        self,
        *,
        upload_flag_field: str,
        upload_ok: bool,
        result: str = "",
        total_result: str = "",
    ) -> UploadResult:
        """Set upload status and the unified total result."""
        if upload_flag_field:
            self.extra_fields[upload_flag_field] = upload_ok
            if hasattr(self, upload_flag_field):
                setattr(self, upload_flag_field, upload_ok)

        final_result = total_result or result
        if final_result:
            self.total_result = final_result

        return self

    def set_gravimetric(self, *, result: str = "", upload_ok: bool = True) -> UploadResult:
        return self.set_test_result(
            upload_flag_field="gravimetric",
            upload_ok=upload_ok,
            result=result,
        )

    def set_assembly_qc(
        self,
        *,
        upload_ok: bool,
        result: str = "",
        total_result: str = "",
    ) -> UploadResult:
        return self.set_test_result(
            upload_flag_field="assembly_qc",
            upload_ok=upload_ok,
            result=result,
            total_result=total_result,
        )

    def set_current_speed(
        self,
        *,
        upload_ok: bool,
        result: str = "",
        total_result: str = "",
    ) -> UploadResult:
        return self.set_test_result(
            upload_flag_field="current_speed",
            upload_ok=upload_ok,
            result=result,
            total_result=total_result,
        )

    def set_96ch_assembly_qc(
        self,
        *,
        upload_ok: bool,
        result: str = "",
        total_result: str = "",
    ) -> UploadResult:
        return self.set_test_result(
            upload_flag_field="ninety_six_assembly_qc",
            upload_ok=upload_ok,
            result=result,
            total_result=total_result,
        )

    def set_z_stage_test(
        self,
        *,
        upload_ok: bool,
        result: str = "",
        total_result: str = "",
    ) -> UploadResult:
        return self.set_test_result(
            upload_flag_field="z_stage_test",
            upload_ok=upload_ok,
            result=result,
            total_result=total_result,
        )

    def set_xy_calibration(
        self,
        *,
        upload_ok: bool,
        result: str = "",
        total_result: str = "",
    ) -> UploadResult:
        return self.set_test_result(
            upload_flag_field="xy_calibration",
            upload_ok=upload_ok,
            result=result,
            total_result=total_result,
        )

    def set_gantry_stress_test(
        self,
        *,
        upload_ok: bool,
        result: str = "",
        total_result: str = "",
    ) -> UploadResult:
        return self.set_test_result(
            upload_flag_field="gantry_stress_test",
            upload_ok=upload_ok,
            result=result,
            total_result=total_result,
        )

    def set_leveling_test(
        self,
        *,
        upload_ok: bool,
        result: str = "",
        total_result: str = "",
    ) -> UploadResult:
        return self.set_test_result(
            upload_flag_field="leveling_test",
            upload_ok=upload_ok,
            result=result,
            total_result=total_result,
        )   

    def primary_test_result(self) -> str:
        """返回用于 API test_result 字段的主测试结果。"""
        return self.total_result or ""

    def to_dict(self) -> dict[str, Any]:
        """转为 upload 方法返回值 dict，省略 None 及未设置的空字符串字段。"""
        data = asdict(self)
        extra_fields = data.pop("extra_fields", {}) or {}
        data.update(extra_fields)

        optional_strings = {
            "csv_link",
            "unit_tracker_status",
            "raw_data_name",
            "total_result",
        }
        return {
            key: value
            for key, value in data.items()
            if value is not None
            and not ((key in optional_strings or key.endswith("_result")) and value == "")
        }

    def to_db_dict(self) -> dict[str, Any]:
        """转为写入 MongoDB 的 dict（与 to_dict 相同，语义上表示持久化用途）。"""
        return self.to_dict()


def build_api_response(
    *,
    finished: bool,
    error: str | None = None,
    production_name: str = "",
    test_type: str = "",
    test_result: str = "",
    sn: str = "",
    csv_link: str = "",
    unit_tracker: str = "",
    unit_tracker_status: str = "",
    missing_tests: list[str] | None = None,
    raw_data: str = "",
    raw_data_name: str = "",
) -> UploadApiResponse:
    """构建 API 层统一响应。"""
    response: UploadApiResponse = {"finished": finished, "error": error}
    if production_name:
        response["production_name"] = production_name
    if test_type:
        response["test_type"] = test_type
    if test_result:
        response["test_result"] = test_result
    if sn:
        response["sn"] = sn
    if csv_link:
        response["csv_link"] = csv_link
    if unit_tracker:
        response["unit_tracker"] = unit_tracker
    if unit_tracker_status:
        response["unit_tracker_status"] = unit_tracker_status
    if missing_tests:
        response["missing_tests"] = missing_tests
    if raw_data:
        response["raw_data"] = raw_data
    if raw_data_name:
        response["raw_data_name"] = raw_data_name
    return response


def format_production_name(production_type: str, model: str) -> str:
    """生成 API 展示用的产品名。"""
    return f"{production_type} {model}".strip()

from datetime import datetime

from core.logging import get_logger
logger = get_logger(__name__)


class UploadCommonMixin:
    """Shared helpers for product-specific upload workflows."""

    # ------------------------------------------------------------------
    # File description / config helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_oem_type(file_desc: dict) -> str:
        kind = file_desc.get("kind_oem_type")
        if not kind or kind == "NA":
            return "Opentrons"
        return kind

    @staticmethod
    def is_ultima_oem(kind_oem_type: str) -> bool:
        return "Ultima" in kind_oem_type

    @staticmethod
    def build_tracker_sheet_name(kind_oem_type: str, model: str) -> str:
        return f"{kind_oem_type} {model}"

    @staticmethod
    def resolve_tracker_sheet_name(paste_cfg: dict, default_sheet_name: str) -> str:
        configured_sheet_name = str(paste_cfg.get("unit_tracker_tab") or "").strip()
        if configured_sheet_name:
            return configured_sheet_name
        return default_sheet_name

    @staticmethod
    def pick_config_value(cfg: dict, key: str, ultima_key: str, is_ultima: bool):
        return cfg[ultima_key] if is_ultima else cfg[key]

    def resolve_template_id(self, template_cfg: dict, file_desc: dict) -> str:
        """Resolve template id by OEM name, falling back to default."""
        oem_key = self.normalize_oem_type(file_desc).strip().lower()
        if oem_key in template_cfg and template_cfg[oem_key]:
            return template_cfg[oem_key]
        if "default" in template_cfg and template_cfg["default"]:
            return template_cfg["default"]

        raise KeyError(f"Template id config not found: keys={list(template_cfg.keys())}")

    def resolve_result_cell(self, yaml_cfg: dict, file_desc: dict, key: str = "result_cell") -> str:
        """Resolve a configured result cell. Dict values can be keyed by OEM name."""
        cell_cfg = yaml_cfg[key]
        if not isinstance(cell_cfg, dict):
            return cell_cfg

        oem_key = self.normalize_oem_type(file_desc).strip().lower()
        if oem_key in cell_cfg and cell_cfg[oem_key]:
            return cell_cfg[oem_key]
        if "default" in cell_cfg and cell_cfg["default"]:
            return cell_cfg["default"]

        raise KeyError(f"Result cell config not found: key={key}, oem={oem_key}")

    def resolve_optional_result_cell(self, yaml_cfg: dict, file_desc: dict, key: str = "total_result_cell") -> str | None:
        if key not in yaml_cfg or yaml_cfg[key] in (None, ""):
            return None
        return self.resolve_result_cell(yaml_cfg, file_desc, key=key)

    @staticmethod
    def build_sheet_link(spreadsheet_id: str) -> str:
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit#gid=0"

    def build_tracking_sheet_link(self, spreadsheet_id: str, sheet_name: str) -> str:
        gid_map = self.gdrive.get_sheet_gid_map(spreadsheet_id)
        gid = gid_map[sheet_name]
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit?gid={gid}#gid={gid}"

    # ------------------------------------------------------------------
    # Spreadsheet lifecycle
    # ------------------------------------------------------------------

    def get_or_copy_spreadsheet(
        self,
        csv_link,
        template_id: str,
        new_filename: str,
    ) -> tuple[str | None, str | None]:
        """Return (spreadsheet_id, sheet_link). Reuse existing sheet when csv_link is valid."""
        if csv_link is None or csv_link == "http:xx":
            copy_file = self.gdrive.copy_file(template_id, new_filename)
            if not copy_file:
                return None, None
            spreadsheet_id = copy_file[1]
        else:
            from modules.uploads.handler.drivers.google_drive import GoogleDriveDriver

            spreadsheet_id = GoogleDriveDriver.parse_drive_file_id(csv_link)
            if not spreadsheet_id:
                logger.warning("Invalid reusable csv_link, fallback to new spreadsheet: %s", csv_link)
                copy_file = self.gdrive.copy_file(template_id, new_filename)
                if not copy_file:
                    return None, None
                spreadsheet_id = copy_file[1]
        return spreadsheet_id, self.build_sheet_link(spreadsheet_id)

    def copy_new_spreadsheet(self, template_id: str, new_filename: str) -> tuple[str | None, str | None]:
        """Always copy a fresh template. Return (spreadsheet_id, sheet_link)."""
        copy_file = self.gdrive.copy_file(template_id, new_filename)
        if not copy_file:
            return None, None
        spreadsheet_id = copy_file[1]
        return spreadsheet_id, self.build_sheet_link(spreadsheet_id)

    # ------------------------------------------------------------------
    # CSV → spreadsheet batch write
    # ------------------------------------------------------------------

    @staticmethod
    def _column_to_number(column: str) -> int:
        value = 0
        for char in column.strip().upper():
            if not "A" <= char <= "Z":
                raise ValueError(f"Invalid spreadsheet column: {column}")
            value = value * 26 + ord(char) - ord("A") + 1
        return value

    @staticmethod
    def _number_to_column(number: int) -> str:
        if number < 1:
            raise ValueError(f"Invalid spreadsheet column number: {number}")
        column = ""
        while number:
            number, remainder = divmod(number - 1, 26)
            column = chr(ord("A") + remainder) + column
        return column

    @classmethod
    def normalize_csv_columns(cls, configured_range: list[str]) -> list[str]:
        """Expand compact column entries such as ``A-AP`` into column names."""
        columns: list[str] = []
        for entry in configured_range:
            value = str(entry).strip().upper()
            if "-" not in value:
                cls._column_to_number(value)
                columns.append(value)
                continue

            start, end = (part.strip() for part in value.split("-", 1))
            start_number = cls._column_to_number(start)
            end_number = cls._column_to_number(end)
            if start_number > end_number:
                raise ValueError(f"Invalid spreadsheet column range: {entry}")
            columns.extend(
                cls._number_to_column(number)
                for number in range(start_number, end_number + 1)
            )
        return columns

    @classmethod
    def prepare_csv_batch_updates(cls, csv_data: list, configured_range: list[str]) -> tuple[list, list]:
        """Fit rows to the configured width and split them into 1000-row batches.

        Columns after the configured range are intentionally ignored because the
        destination sheet schema is authoritative for uploads.
        """
        columns = cls.normalize_csv_columns(configured_range)
        datalen = len(columns)
        if datalen == 0:
            raise ValueError("CSV upload range must include at least one column")
        alldatalist = []
        allrangelist = []
        starrange = 1
        setdatalen = len(csv_data)
        setdata = []
        range_col = columns[-1]

        for i, row in enumerate(csv_data):
            cells = row[0]
            cell_count = len(cells)
            if cell_count < datalen:
                cells.extend([""] * (datalen - cell_count))
            elif cell_count > datalen:
                cells = cells[:datalen]
                row[0] = cells

            setdata.append(row[0])
            rangel = f"!A{starrange}:{range_col}{i + 1}"

            if (i + 1) % 1000 == 0:
                alldatalist.append(setdata)
                allrangelist.append(rangel)
                starrange = i + 2
                setdata = []
            elif i + 1 == setdatalen:
                alldatalist.append(setdata)
                allrangelist.append(rangel)

        return alldatalist, allrangelist

    def upload_csv_to_spreadsheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        filepath: str,
        ranglist: list,
    ) -> bool:
        """Read only configured CSV columns and write them to the spreadsheet."""
        configured_columns = self.normalize_csv_columns(ranglist)
        if not configured_columns:
            raise ValueError("CSV upload range must include at least one column")
        csv_data = self.csv_driver.read_csv_rows(
            path=filepath,
            max_columns=len(configured_columns),
        )
        alldatalist, allrangelist = self.prepare_csv_batch_updates(csv_data, ranglist)
        return self.gdrive.update_excel_sheet_page_batch(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            ranges=allrangelist,
            new_values=alldatalist,
        )

    # ------------------------------------------------------------------
    # Summary copy / paste helpers
    # ------------------------------------------------------------------

    def get_sheet_cell_value(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        cell_range: str,
        default: str = "",
    ) -> str:
        try:
            return self.gdrive.get_excel_sheet_page(
                spreadsheet_id, sheet_name, "ROWS", [cell_range]
            )[0][0][0]
        except (IndexError, TypeError, KeyError):
            return default

    def copy_summary_ranges(
        self,
        yaml_cfg: dict,
        updatefileid: str,
        copy_range_key: str = "copyRange",
        ultima_copy_range_key: str = "UltimacopyRange",
        is_ultima: bool = False,
    ) -> list:
        """Copy configured summary ranges from the working spreadsheet."""
        copydatalist = []
        for cop in yaml_cfg["ifcopydata"]:
            if not cop["off/on"]:
                continue
            sheet_name = cop["summary_source_sheet_name"]
            rangeval = self.pick_config_value(cop, copy_range_key, ultima_copy_range_key, is_ultima)
            copydata = self.gdrive.get_excel_sheet_page(updatefileid, sheet_name, "ROWS", rangeval)
            copydatalist.append(copydata)
        return copydatalist

    @staticmethod
    def find_last_row_by_length(values: list) -> int:
        return len(values) + 1

    def paste_row_to_tracker(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        paste_range: str,
        row_data: list,
        sheet_link: str | None = None,
        sheet_link_index: int = 0,
        sheet_link_mode: str = "insert",
        note_str: str = "",
        note_range: str | None = None,
    ) -> bool:
        """Paste summary rows into a tracker sheet.

        row_data is the batch payload (equivalent to pasedata[0] in legacy code).
        sheet_link_mode: "insert" prepends/shifts columns; "set" overwrites a column.
        """
        if sheet_link is not None:
            if sheet_link_mode == "insert":
                row_data[0].insert(sheet_link_index, sheet_link)
            else:
                row_data[0][sheet_link_index] = sheet_link

        ok = self.gdrive.update_excel_sheet_page_batch(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            ranges=paste_range,
            new_values=row_data,
        )
        if not ok:
            return False

        if note_range and note_str is not None:
            ok = self.gdrive.update_excel_sheet_page_batch(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                ranges=note_range,
                new_values=[[note_str]],
            )
        return ok

    @staticmethod
    def normalize_tracker_row(row: list) -> list[str]:
        normalized = [str(value).strip() for value in row]
        while normalized and normalized[-1] == "":
            normalized.pop()
        return normalized

    @staticmethod
    def quote_sheet_name(sheet_name: str) -> str:
        return "'" + sheet_name.replace("'", "''") + "'"

    def get_last_tracker_row_number(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        anchor_column: str,
    ) -> int | None:
        """Find the last tracker row using one column instead of loading the sheet."""
        column = anchor_column.strip().upper()
        self._column_to_number(column)
        quoted_sheet = self.quote_sheet_name(sheet_name)
        values = self.gdrive.get_excel_sheet(
            spreadsheetId=spreadsheet_id,
            range=f"{quoted_sheet}!{column}:{column}",
        )
        if not values:
            return None
        return len(values)

    def ensure_tracker_row_capacity(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        required_row: int,
    ) -> bool:
        """Append grid rows when the tracker is full before writing a new record."""
        sheet_info = self.gdrive.get_sheet_info(spreadsheet_id) or []
        target_sheet = next(
            (sheet for sheet in sheet_info if sheet.get("title") == sheet_name),
            None,
        )
        if target_sheet is None:
            logger.error(
                "Cannot expand tracker because the sheet was not found: "
                "spreadsheet=%s sheet=%s",
                spreadsheet_id,
                sheet_name,
            )
            return False

        row_count = int(target_sheet.get("grid_properties", {}).get("rowCount") or 0)
        if required_row <= row_count:
            return True

        try:
            self.gdrive.sheet_service_client.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [
                        {
                            "appendDimension": {
                                "sheetId": target_sheet["sheet_id"],
                                "dimension": "ROWS",
                                "length": required_row - row_count,
                            }
                        }
                    ]
                },
            ).execute()
        except Exception as exc:
            logger.error(
                "Expand tracker rows failed: spreadsheet=%s sheet=%s "
                "required_row=%s error=%s",
                spreadsheet_id,
                sheet_name,
                required_row,
                exc,
            )
            return False

        logger.info(
            "Expanded tracker rows: spreadsheet=%s sheet=%s old_rows=%s new_rows=%s",
            spreadsheet_id,
            sheet_name,
            row_count,
            required_row,
        )
        return True

    def get_last_tracker_row(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        start_column: str,
        end_column: str,
    ) -> tuple[int | None, list]:
        row_number = self.get_last_tracker_row_number(
            spreadsheet_id,
            sheet_name,
            start_column,
        )
        if row_number is None:
            return None, []

        start = start_column.strip().upper()
        end = end_column.strip().upper()
        self._column_to_number(end)
        quoted_sheet = self.quote_sheet_name(sheet_name)
        values = self.gdrive.get_excel_sheet(
            spreadsheetId=spreadsheet_id,
            range=f"{quoted_sheet}!{start}{row_number}:{end}{row_number}",
        )
        if not values:
            return None, []
        return row_number, values[0]

    def delete_last_tracker_row_if_matches(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        expected_row: list,
        start_column: str,
        end_column: str,
    ) -> bool:
        """Delete the current last tracker row only when it exactly matches expected data."""
        row_number, actual_row = self.get_last_tracker_row(
            spreadsheet_id,
            sheet_name,
            start_column,
            end_column,
        )
        if row_number is None or self.normalize_tracker_row(actual_row) != self.normalize_tracker_row(expected_row):
            logger.warning(
                "Skip tracker cleanup because the last row does not match: spreadsheet=%s sheet=%s",
                spreadsheet_id,
                sheet_name,
            )
            return False

        gid_map = self.gdrive.get_sheet_gid_map(spreadsheet_id) or {}
        sheet_id = gid_map.get(sheet_name)
        if sheet_id is None:
            logger.warning(
                "Skip tracker cleanup because the sheet gid was not found: spreadsheet=%s sheet=%s",
                spreadsheet_id,
                sheet_name,
            )
            return False

        try:
            self.gdrive.sheet_service_client.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [
                        {
                            "deleteDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": row_number - 1,
                                    "endIndex": row_number,
                                }
                            }
                        }
                    ]
                },
            ).execute()
        except Exception as exc:
            logger.error(
                "Delete tracker test row failed: spreadsheet=%s sheet=%s row=%s error=%s",
                spreadsheet_id,
                sheet_name,
                row_number,
                exc,
            )
            return False

        logger.info(
            "Deleted matching tracker test row: spreadsheet=%s sheet=%s row=%s",
            spreadsheet_id,
            sheet_name,
            row_number,
        )
        return True

    def resolve_paste_line_range(self, pase: dict, last_row_index: int, is_ultima: bool = False) -> tuple[str, str, str]:
        """Return (paste_range, star_col, end_col) for a configured paste target."""
        line_range = self.pick_config_value(
            pase, "pastelineRange", "UltimapastelineRange", is_ultima
        )
        star = line_range["star"]
        end = line_range["end"]
        paste_range = f"!{star}{last_row_index}:{end}{last_row_index}"
        return paste_range, star, end

    def resolve_paste_file_id(self, pase: dict, is_ultima: bool = False) -> str:
        return self.pick_config_value(pase, "pastefileid", "Ultimapastefileid", is_ultima)

    # ------------------------------------------------------------------
    # Post-upload: move file, upload raw zip, logging
    # ------------------------------------------------------------------

    def move_spreadsheet_to_month(
        self,
        yaml_cfg: dict,
        updatefileid: str,
        model_key: str | None = None,
    ) -> bool:
        month_id = self.resolve_month_folder_id(
            yaml_cfg["unit_tracker_sheet"],
            model_key=model_key,
        )
        result = self.gdrive.move_file_multi_level(updatefileid, month_id)
        return result["success"] not in (False, "False")

    def upload_raw_data(
        self,
        yaml_cfg: dict,
        device_sn: str,
        timestamp: str,
        zip_file,
        model_key: str | None = None,
    ) -> dict[str, str]:
        """Create a Drive folder and upload raw zip. Return folder URL and name."""
        folder_name = f"{device_sn}_{timestamp}"
        if zip_file is None:
            logger.warning("Raw data.zip is None")
            return {"url": "N/A", "name": ""}

        parent_id = self.resolve_month_folder_id(
            yaml_cfg["ifupdaterawdata"],
            model_key=model_key,
        )

        folder_id = self.gdrive.create_folders(folder_name, parent_id)
        if not folder_id:
            logger.error(f"Raw data folder create fail: {folder_name}")
            detail = getattr(self.gdrive, "last_error", None) or "Google Drive did not return a folder id"
            return {"url": "N/A", "name": "", "error": f"创建原始数据文件夹失败: {detail}"}

        upload_id = self.gdrive.upload_to_drive(zip_file, folder_id)
        if not upload_id:
            logger.error(f"Raw data.zip upload fail, check out the path: {zip_file}")
            detail = getattr(self.gdrive, "last_error", None) or "Google Drive did not return a file id"
            return {"url": "N/A", "name": "", "error": f"上传原始数据压缩包失败: {detail}"}
        logger.info("Upload zip file finished")
        return {
            "url": f"https://drive.google.com/drive/folders/{folder_id}",
            "name": folder_name,
        }

    @staticmethod
    def current_timestamp(fmt: str = "%Y%m%d%H%M%S") -> str:
        return datetime.now().strftime(fmt)

    def log_upload_links(self, sheetlink: str, tracking_sheet: str):
        print("Uploading successful")
        print(f"sheetlink: {sheetlink}")
        print(f"tracking_sheet: {tracking_sheet}")
        logger.info(f"sheetlink: {sheetlink}")
        logger.info(f"tracking_sheet: {tracking_sheet}")

    def resolve_month_folder_id(self, folder_cfg: dict, model_key: str | None = None) -> str:
        """Resolve Drive folder id by month only."""
        cfg = folder_cfg[model_key] if model_key else folder_cfg
        month = self.nowmonth

        if month in cfg:
            return cfg[month]

        raise KeyError(f"Month folder config not found: month={month}, model={model_key}")


class ProductUploaderBase(UploadCommonMixin):
    """Base class for product uploaders that operate on an UploadData context."""

    def __init__(self, context) -> None:
        self.context = context

    def report_progress(
        self,
        stage: str,
        message: str,
        checkpoint: dict | None = None,
    ) -> None:
        reporter = getattr(self.context, "report_upload_progress", None)
        if reporter:
            try:
                reporter(stage, message, checkpoint)
            except TypeError:
                reporter(stage, message)

    def get_upload_checkpoint(self) -> dict:
        return dict(getattr(self.context, "upload_checkpoint", {}) or {})

    def __getattr__(self, name):
        return getattr(self.context, name)

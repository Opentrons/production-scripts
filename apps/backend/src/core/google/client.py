from __future__ import annotations

import io
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar
from urllib.parse import parse_qs, urlparse

from google.auth.exceptions import TransportError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from core.google.proxy import (
    apply_oauth_proxy,
    build_auth_request,
    build_google_service,
)
from core.google.proxy_manager import google_proxy_manager
from core.config import (
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_INTERACTIVE_AUTH,
    GOOGLE_TOKEN_PATH,
)


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]
GOOGLE_WORKSPACE_MIME_PREFIX = "application/vnd.google-apps."
T = TypeVar("T")


class GoogleDriverError(RuntimeError):
    pass


class GoogleConfigurationError(GoogleDriverError):
    pass


@dataclass(frozen=True)
class GoogleSheetCell:
    value: str = ""
    hyperlink: str | None = None
    formula: str | None = None


@dataclass(frozen=True)
class GoogleSheetData:
    spreadsheet_id: str
    sheet_id: int
    title: str
    cells: list[list[GoogleSheetCell]] = field(default_factory=list)

    @property
    def values(self) -> list[list[str]]:
        return [[cell.value for cell in row] for row in self.cells]


@dataclass(frozen=True)
class GoogleDriveFile:
    id: str
    name: str
    mime_type: str
    size: int | None = None
    modified_time: str | None = None
    web_view_link: str | None = None


class GoogleDriver:
    def __init__(
        self,
        token_path: Path = GOOGLE_TOKEN_PATH,
        credentials_path: Path = GOOGLE_CREDENTIALS_PATH,
        allow_interactive_auth: bool = GOOGLE_INTERACTIVE_AUTH,
    ) -> None:
        self.token_path = Path(token_path)
        self.credentials_path = Path(credentials_path)
        self.allow_interactive_auth = allow_interactive_auth
        self._lock = threading.RLock()
        self._credentials: Credentials | None = None
        self._drive_service = None
        self._sheets_service = None
        self._proxy_url: str | None = None
        self._proxy_version = -1

    def get_sheet_metadata(self, spreadsheet_id: str) -> list[dict[str, Any]]:
        response = self._execute(
            lambda: self._sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields="sheets(properties(sheetId,title,index,sheetType,gridProperties))",
            )
        )
        return [dict(sheet.get("properties", {})) for sheet in response.get("sheets", [])]

    def read_sheet_by_gid(self, spreadsheet_id: str, sheet_gid: int) -> GoogleSheetData:
        metadata = self.get_sheet_metadata(spreadsheet_id)
        selected = next((item for item in metadata if int(item.get("sheetId", -1)) == int(sheet_gid)), None)
        if selected is None:
            raise GoogleDriverError(f"Google Sheet gid 不存在: {sheet_gid}")

        title = str(selected.get("title", ""))
        quoted_title = self._quote_sheet_title(title)
        values_response = self._execute(
            lambda: self._sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=quoted_title,
                majorDimension="ROWS",
            )
        )
        raw_values = values_response.get("values", [])
        if not raw_values:
            return GoogleSheetData(
                spreadsheet_id=spreadsheet_id,
                sheet_id=sheet_gid,
                title=title,
            )

        row_count = len(raw_values)
        column_count = max(len(row) for row in raw_values)
        grid_range = f"{quoted_title}!A1:{self.column_name(column_count)}{row_count}"
        grid_response = self._execute(
            lambda: self._sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                ranges=[grid_range],
                includeGridData=True,
                fields=(
                    "sheets(data(rowData(values(formattedValue,hyperlink,userEnteredValue))))"
                ),
            )
        )
        sheets = grid_response.get("sheets", [])
        row_data = sheets[0].get("data", [{}])[0].get("rowData", []) if sheets else []
        cells: list[list[GoogleSheetCell]] = []
        for row_index in range(row_count):
            value_row = raw_values[row_index]
            grid_cells = row_data[row_index].get("values", []) if row_index < len(row_data) else []
            cells.append(
                [
                    self._sheet_cell(value_row, grid_cells, column_index)
                    for column_index in range(column_count)
                ]
            )
        return GoogleSheetData(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_gid,
            title=title,
            cells=cells,
        )

    def get_file_metadata(self, file_id_or_url: str) -> GoogleDriveFile:
        file_id = self.parse_drive_file_id(file_id_or_url)
        if not file_id:
            raise GoogleDriverError("无法解析 Google Drive 文件 ID")
        response = self._execute(
            lambda: self._drive_service.files().get(
                fileId=file_id,
                fields="id,name,mimeType,size,modifiedTime,webViewLink",
                supportsAllDrives=True,
            )
        )
        size = response.get("size")
        return GoogleDriveFile(
            id=response["id"],
            name=response.get("name", file_id),
            mime_type=response.get("mimeType", "application/octet-stream"),
            size=int(size) if size is not None else None,
            modified_time=response.get("modifiedTime"),
            web_view_link=response.get("webViewLink"),
        )

    def download_file_bytes(
        self,
        file_id_or_url: str,
        export_mime_type: str = "application/pdf",
    ) -> tuple[GoogleDriveFile, bytes]:
        metadata = self.get_file_metadata(file_id_or_url)
        try:
            content = self._download_media(metadata, export_mime_type)
        except Exception as exc:
            if not self._should_retry(exc) or not google_proxy_manager.failover(self._proxy_url):
                raise GoogleDriverError(f"Google Drive 文件下载失败: {exc}") from exc
            self._ensure_services(force=True)
            try:
                content = self._download_media(metadata, export_mime_type)
            except Exception as retry_exc:
                raise GoogleDriverError(f"Google Drive 文件下载重试失败: {retry_exc}") from retry_exc
        return metadata, content

    def _download_media(self, metadata: GoogleDriveFile, export_mime_type: str) -> bytes:
        if metadata.mime_type.startswith(GOOGLE_WORKSPACE_MIME_PREFIX):
            request = self._drive_service.files().export_media(
                fileId=metadata.id,
                mimeType=export_mime_type,
            )
        else:
            request = self._drive_service.files().get_media(
                fileId=metadata.id,
                supportsAllDrives=True,
            )

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    def _ensure_services(self, force: bool = False) -> None:
        with self._lock:
            proxy_url, proxy_version = google_proxy_manager.current()
            if (
                not force
                and self._drive_service is not None
                and self._sheets_service is not None
                and proxy_version == self._proxy_version
            ):
                return
            self._proxy_url = proxy_url
            self._proxy_version = proxy_version
            self._credentials = self._load_credentials(self._proxy_url)
            self._drive_service = build_google_service(
                "drive",
                "v3",
                self._credentials,
                proxy_url=self._proxy_url,
            )
            self._sheets_service = build_google_service(
                "sheets",
                "v4",
                self._credentials,
                proxy_url=self._proxy_url,
            )

    def _load_credentials(self, proxy_url: str | None) -> Credentials:
        credentials: Credentials | None = None
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(self.token_path, GOOGLE_SCOPES)

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(build_auth_request(proxy_url))
            self._save_credentials(credentials)

        if credentials and credentials.valid:
            return credentials

        if not self.allow_interactive_auth:
            raise GoogleConfigurationError(
                f"Google token 不存在或无效: {self.token_path}. "
                "请复制 auth/token.json，或启用 PRODUCTION_PLATFORM_GOOGLE_INTERACTIVE_AUTH。"
            )
        if not self.credentials_path.exists():
            raise GoogleConfigurationError(f"Google OAuth credentials 不存在: {self.credentials_path}")

        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, GOOGLE_SCOPES)
        apply_oauth_proxy(flow, proxy_url)
        credentials = flow.run_local_server(port=0)
        self._save_credentials(credentials)
        return credentials

    def _save_credentials(self, credentials: Credentials) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(credentials.to_json(), encoding="utf-8")

    def _execute(self, request_factory: Callable[[], Any]) -> T:
        self._ensure_services()
        try:
            return request_factory().execute()
        except Exception as exc:
            if not self._should_retry(exc):
                raise GoogleDriverError(f"Google API 请求失败: {exc}") from exc
            fallback_proxy = google_proxy_manager.failover(self._proxy_url)
            if not fallback_proxy:
                raise GoogleDriverError(f"Google API 请求失败: {exc}") from exc
            self._ensure_services(force=True)
            try:
                return request_factory().execute()
            except Exception as retry_exc:
                raise GoogleDriverError(f"Google API 重试失败: {retry_exc}") from retry_exc

    def _should_retry(self, exc: Exception) -> bool:
        if isinstance(exc, HttpError):
            status = getattr(exc.resp, "status", 0)
            return status == 429 or status >= 500
        return isinstance(exc, (TransportError, OSError, TimeoutError))

    def _sheet_cell(
        self,
        raw_row: list[Any],
        grid_cells: list[dict[str, Any]],
        column_index: int,
    ) -> GoogleSheetCell:
        grid_cell = grid_cells[column_index] if column_index < len(grid_cells) else {}
        fallback = raw_row[column_index] if column_index < len(raw_row) else ""
        user_entered = grid_cell.get("userEnteredValue", {})
        return GoogleSheetCell(
            value=str(grid_cell.get("formattedValue", fallback) or ""),
            hyperlink=grid_cell.get("hyperlink"),
            formula=user_entered.get("formulaValue"),
        )

    @staticmethod
    def _quote_sheet_title(title: str) -> str:
        return f"'{title.replace(chr(39), chr(39) * 2)}'"

    @staticmethod
    def column_name(column_count: int) -> str:
        if column_count < 1:
            raise ValueError("column_count must be positive")
        name = ""
        value = column_count
        while value:
            value, remainder = divmod(value - 1, 26)
            name = chr(65 + remainder) + name
        return name

    @staticmethod
    def parse_drive_file_id(url_or_id: str) -> str | None:
        value = str(url_or_id or "").strip()
        if not value:
            return None
        if re.fullmatch(r"[A-Za-z0-9_-]{10,}", value):
            return value

        parsed = urlparse(value)
        path_match = re.search(r"/(?:d|folders)/([A-Za-z0-9_-]+)", parsed.path)
        if path_match:
            return path_match.group(1)
        query_id = parse_qs(parsed.query).get("id")
        if query_id:
            return query_id[0]
        return None

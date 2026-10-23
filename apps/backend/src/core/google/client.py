from __future__ import annotations

import io
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar
from urllib.parse import parse_qs, urlparse

from google.auth.exceptions import TransportError
from google.auth.credentials import Credentials as GoogleCredentials
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
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
    GOOGLE_SERVICE_ACCOUNT_PATH,
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
    document_title: str = ""

    @property
    def values(self) -> list[list[str]]:
        return [[cell.value for cell in row] for row in self.cells]


@dataclass(frozen=True)
class GoogleDriveFile:
    id: str
    name: str
    mime_type: str
    size: int | None = None
    created_time: str | None = None
    modified_time: str | None = None
    web_view_link: str | None = None
    description: str | None = None
    parent_path: str = ""
    resource_key: str | None = None
    shortcut_id: str | None = None
    target_mime_type: str | None = None
    target_resource_key: str | None = None


class GoogleDriver:
    def __init__(
        self,
        token_path: Path = GOOGLE_TOKEN_PATH,
        credentials_path: Path = GOOGLE_CREDENTIALS_PATH,
        service_account_path: Path | None = GOOGLE_SERVICE_ACCOUNT_PATH,
        allow_interactive_auth: bool = GOOGLE_INTERACTIVE_AUTH,
    ) -> None:
        self.token_path = Path(token_path)
        self.credentials_path = Path(credentials_path)
        self.service_account_path = (
            Path(service_account_path) if service_account_path is not None else None
        )
        self.allow_interactive_auth = allow_interactive_auth
        self._lock = threading.RLock()
        self._credentials: GoogleCredentials | None = None
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
                fields=(
                    "id,name,mimeType,size,createdTime,modifiedTime,webViewLink,description,resourceKey"
                ),
                supportsAllDrives=True,
            )
        )
        size = response.get("size")
        return GoogleDriveFile(
            id=response["id"],
            name=response.get("name", file_id),
            mime_type=response.get("mimeType", "application/octet-stream"),
            size=int(size) if size is not None else None,
            created_time=response.get("createdTime"),
            modified_time=response.get("modifiedTime"),
            web_view_link=response.get("webViewLink"),
            description=response.get("description"),
            resource_key=response.get("resourceKey"),
        )

    def read_spreadsheet_values(
        self,
        spreadsheet_id: str,
        range_name: str = "A1:CC200",
    ) -> list[list[str]]:
        """Read a bounded range from the first sheet in a spreadsheet."""
        response = self._execute(
            lambda: self._sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                majorDimension="ROWS",
                valueRenderOption="FORMATTED_VALUE",
            )
        )
        return [
            [str(value or "") for value in row]
            for row in response.get("values", [])
        ]

    def update_spreadsheet_values(
        self,
        spreadsheet_id: str,
        values_by_range: dict[str, str],
    ) -> None:
        """Write one value to each supplied A1 range in a single request."""

        if not values_by_range:
            return
        self._execute(
            lambda: self._sheets_service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "valueInputOption": "USER_ENTERED",
                    "data": [
                        {
                            "range": range_name,
                            "majorDimension": "ROWS",
                            "values": [[value]],
                        }
                        for range_name, value in values_by_range.items()
                    ],
                },
            )
        )

    def delete_spreadsheet_row(self, spreadsheet_id: str, sheet_gid: int, row: int) -> None:
        """Delete one 1-based row from a sheet."""
        self._execute(lambda: self._sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"deleteDimension": {"range": {
                "sheetId": sheet_gid, "dimension": "ROWS",
                "startIndex": row - 1, "endIndex": row,
            }}}]},
        ))

    def append_spreadsheet_row(self, spreadsheet_id: str, sheet_title: str, values: list[str]) -> int:
        response = self._execute(lambda: self._sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{self._quote_sheet_title(sheet_title)}!A:L",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [values]},
        ))
        updated_range = response.get("updates", {}).get("updatedRange", "")
        match = re.search(r"![A-Z]+(\d+)", updated_range)
        if not match:
            raise GoogleDriverError("写入 ECN 总表后无法确认新行号")
        return int(match.group(1))

    def write_spreadsheet_row(
        self,
        spreadsheet_id: str,
        sheet_title: str,
        row: int,
        values: list[str],
    ) -> int:
        """Write a complete row at a specific 1-based sheet row."""
        self._execute(lambda: self._sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{self._quote_sheet_title(sheet_title)}!A{row}:L{row}",
            valueInputOption="USER_ENTERED",
            body={"majorDimension": "ROWS", "values": [values]},
        ))
        return row

    def get_file_parent(self, file_id_or_url: str) -> str | None:
        file_id = self.parse_drive_file_id(file_id_or_url)
        if not file_id:
            return None
        response = self._execute(lambda: self._drive_service.files().get(
            fileId=file_id, fields="parents", supportsAllDrives=True,
        ))
        return next(iter(response.get("parents", [])), None)

    def trash_file(self, file_id_or_url: str) -> None:
        file_id = self.parse_drive_file_id(file_id_or_url)
        if not file_id:
            raise GoogleDriverError("无法解析要删除的 Google Drive 文件 ID")
        self._execute(lambda: self._drive_service.files().update(
            fileId=file_id, body={"trashed": True}, fields="id", supportsAllDrives=True,
        ))

    def rename_file(self, file_id_or_url: str, name: str) -> None:
        file_id = self.parse_drive_file_id(file_id_or_url)
        if not file_id:
            raise GoogleDriverError("无法解析要重命名的 Google Drive 文件 ID")
        self._execute(lambda: self._drive_service.files().update(
            fileId=file_id, body={"name": name}, fields="id", supportsAllDrives=True,
        ))

    def read_spreadsheet_preview(
        self,
        spreadsheet_id: str,
        range_name: str = "A1:CC200",
    ) -> GoogleSheetData:
        """Read display values and the first sheet gid in one API request."""
        response = self._execute(
            lambda: self._sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                ranges=[range_name],
                includeGridData=True,
                fields=(
                    "properties(title),sheets(properties(sheetId,title,index),"
                    "data(rowData(values(formattedValue))))"
                ),
            )
        )
        sheets = response.get("sheets", [])
        if not sheets:
            raise GoogleDriverError(f"Google Sheet 不包含工作表: {spreadsheet_id}")
        selected = min(
            sheets,
            key=lambda sheet: int(sheet.get("properties", {}).get("index", 0)),
        )
        properties = selected.get("properties", {})
        data = selected.get("data", [])
        row_data = data[0].get("rowData", []) if data else []
        cells = [
            [
                GoogleSheetCell(value=str(cell.get("formattedValue") or ""))
                for cell in row.get("values", [])
            ]
            for row in row_data
        ]
        return GoogleSheetData(
            spreadsheet_id=spreadsheet_id,
            sheet_id=int(properties.get("sheetId", 0)),
            title=str(properties.get("title") or ""),
            cells=cells,
            document_title=str(response.get("properties", {}).get("title") or ""),
        )

    def read_spreadsheet_previews(
        self,
        spreadsheet_id: str,
        range_name: str = "A1:CC200",
    ) -> list[GoogleSheetData]:
        """Read a bounded preview from every grid sheet in a spreadsheet."""
        metadata_response = self._execute(
            lambda: self._sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields=(
                    "properties(title),"
                    "sheets(properties(sheetId,title,index,sheetType))"
                ),
            )
        )
        sheet_properties = sorted(
            (
                dict(sheet.get("properties", {}))
                for sheet in metadata_response.get("sheets", [])
                if str(sheet.get("properties", {}).get("sheetType") or "GRID") == "GRID"
            ),
            key=lambda properties: int(properties.get("index", 0)),
        )
        if not sheet_properties:
            raise GoogleDriverError(f"Google Sheet 不包含工作表: {spreadsheet_id}")

        ranges = [
            f"{self._quote_sheet_title(str(properties.get('title') or ''))}!{range_name}"
            for properties in sheet_properties
        ]
        values_response = self._execute(
            lambda: self._sheets_service.spreadsheets().values().batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=ranges,
                majorDimension="ROWS",
                valueRenderOption="FORMATTED_VALUE",
            )
        )
        value_ranges = list(values_response.get("valueRanges", []))
        document_title = str(metadata_response.get("properties", {}).get("title") or "")
        previews: list[GoogleSheetData] = []
        for index, properties in enumerate(sheet_properties):
            raw_values = value_ranges[index].get("values", []) if index < len(value_ranges) else []
            cells = [
                [GoogleSheetCell(value=str(value or "")) for value in row]
                for row in raw_values
            ]
            previews.append(
                GoogleSheetData(
                    spreadsheet_id=spreadsheet_id,
                    sheet_id=int(properties.get("sheetId", 0)),
                    title=str(properties.get("title") or ""),
                    cells=cells,
                    document_title=document_title,
                )
            )
        return previews

    def list_files_in_folder(
        self,
        folder_id_or_url: str,
        *,
        year: int | None = None,
        recursive: bool = True,
    ) -> list[GoogleDriveFile]:
        """List non-folder files below a Drive folder.

        When ``year`` is provided, only files created during that year are
        returned. Folder traversal itself is never filtered by year.
        """
        root_id = self.parse_drive_file_id(folder_id_or_url)
        if not root_id:
            raise GoogleDriverError("无法解析 Google Drive 文件夹 ID")

        start = datetime(year, 1, 1, tzinfo=timezone.utc) if year is not None else None
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if year is not None else None
        pending: list[tuple[str, str]] = [(root_id, "")]
        visited: set[str] = set()
        file_ids: set[str] = set()
        files: list[GoogleDriveFile] = []

        while pending:
            folder_id, parent_path = pending.pop(0)
            if folder_id in visited:
                continue
            visited.add(folder_id)
            page_token: str | None = None
            while True:
                query = f"'{folder_id}' in parents and trashed = false"
                response = self._execute(
                    lambda query=query, page_token=page_token: self._drive_service.files().list(
                        q=query,
                        pageSize=1000,
                        pageToken=page_token,
                        orderBy="createdTime desc",
                        fields=(
                            "nextPageToken,files("
                            "id,name,mimeType,size,createdTime,modifiedTime,webViewLink,description,parents,resourceKey,"
                            "shortcutDetails(targetId,targetMimeType,targetResourceKey))"
                        ),
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                )
                for item in response.get("files", []):
                    mime_type = str(item.get("mimeType") or "application/octet-stream")
                    item_name = str(item.get("name") or item.get("id") or "")
                    item_path = f"{parent_path} / {item_name}" if parent_path else item_name
                    shortcut = item.get("shortcutDetails") or {}
                    target_id = str(shortcut.get("targetId") or item.get("id") or "")
                    target_mime_type = str(shortcut.get("targetMimeType") or "")
                    target_resource_key = str(shortcut.get("targetResourceKey") or "")
                    if mime_type == "application/vnd.google-apps.folder":
                        if recursive and item.get("id"):
                            pending.append((str(item["id"]), item_path))
                        continue
                    if (
                        mime_type == "application/vnd.google-apps.shortcut"
                        and target_mime_type == "application/vnd.google-apps.folder"
                    ):
                        if recursive and target_id:
                            pending.append((target_id, item_path))
                        continue
                    created_time = item.get("createdTime")
                    if year is not None:
                        if not created_time:
                            continue
                        try:
                            created_at = datetime.fromisoformat(str(created_time).replace("Z", "+00:00"))
                        except ValueError:
                            continue
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        if start is None or end is None or not (start <= created_at < end):
                            continue
                    item_id = target_id
                    if not item_id or item_id in file_ids:
                        continue
                    file_ids.add(item_id)
                    size = item.get("size")
                    files.append(
                        GoogleDriveFile(
                            id=item_id,
                            name=item_name,
                            mime_type=mime_type,
                            size=int(size) if size is not None else None,
                            created_time=str(created_time),
                            modified_time=item.get("modifiedTime"),
                            web_view_link=item.get("webViewLink"),
                            description=item.get("description"),
                            parent_path=parent_path,
                            resource_key=item.get("resourceKey"),
                            shortcut_id=str(item.get("id")) if mime_type == "application/vnd.google-apps.shortcut" else None,
                            target_mime_type=target_mime_type or None,
                            target_resource_key=target_resource_key or None,
                        )
                    )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        files.sort(key=lambda item: item.created_time or "", reverse=True)
        return files

    def find_folder(self, parent_id_or_url: str, name: str) -> GoogleDriveFile | None:
        """Find an immediate child folder by its exact name."""

        parent_id = self.parse_drive_file_id(parent_id_or_url)
        if not parent_id:
            raise GoogleDriverError("无法解析 Google Drive 父目录 ID")
        escaped_name = str(name or "").replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"'{parent_id}' in parents and trashed = false and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            f"name = '{escaped_name}'"
        )
        response = self._execute(
            lambda: self._drive_service.files().list(
                q=query,
                pageSize=2,
                fields="files(id,name,mimeType,createdTime,modifiedTime,webViewLink)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
        )
        items = response.get("files", [])
        if not items:
            return None
        item = items[0]
        return GoogleDriveFile(
            id=str(item["id"]),
            name=str(item.get("name") or name),
            mime_type=str(item.get("mimeType") or "application/vnd.google-apps.folder"),
            created_time=item.get("createdTime"),
            modified_time=item.get("modifiedTime"),
            web_view_link=item.get("webViewLink") or f"https://drive.google.com/drive/folders/{item['id']}",
        )

    def find_folder_by_prefix(
        self,
        parent_id_or_url: str,
        name_prefix: str,
    ) -> GoogleDriveFile | None:
        """Find an immediate child folder whose name starts with a prefix."""

        parent_id = self.parse_drive_file_id(parent_id_or_url)
        if not parent_id:
            raise GoogleDriverError("无法解析 Google Drive 父目录 ID")
        escaped_prefix = str(name_prefix or "").replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"'{parent_id}' in parents and trashed = false and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            f"name contains '{escaped_prefix}'"
        )
        response = self._execute(
            lambda: self._drive_service.files().list(
                q=query,
                pageSize=100,
                fields="files(id,name,mimeType,createdTime,modifiedTime,webViewLink)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
        )
        item = next(
            (
                candidate
                for candidate in response.get("files", [])
                if str(candidate.get("name") or "").startswith(name_prefix)
            ),
            None,
        )
        if item is None:
            return None
        folder_id = str(item["id"])
        return GoogleDriveFile(
            id=folder_id,
            name=str(item.get("name") or name_prefix),
            mime_type=str(item.get("mimeType") or "application/vnd.google-apps.folder"),
            created_time=item.get("createdTime"),
            modified_time=item.get("modifiedTime"),
            web_view_link=item.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder_id}",
        )

    def create_folder(self, parent_id_or_url: str, name: str) -> GoogleDriveFile:
        """Create a Drive folder below the supplied parent."""

        parent_id = self.parse_drive_file_id(parent_id_or_url)
        if not parent_id:
            raise GoogleDriverError("无法解析 Google Drive 父目录 ID")
        response = self._execute(
            lambda: self._drive_service.files().create(
                body={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                },
                fields="id,name,mimeType,createdTime,modifiedTime,webViewLink",
                supportsAllDrives=True,
            )
        )
        folder_id = str(response["id"])
        return GoogleDriveFile(
            id=folder_id,
            name=str(response.get("name") or name),
            mime_type=str(response.get("mimeType") or "application/vnd.google-apps.folder"),
            created_time=response.get("createdTime"),
            modified_time=response.get("modifiedTime"),
            web_view_link=response.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder_id}",
        )

    def copy_file(
        self,
        file_id_or_url: str,
        parent_id_or_url: str,
        name: str,
    ) -> GoogleDriveFile:
        """Copy a Drive file into a folder and return the new file metadata."""

        file_id = self.parse_drive_file_id(file_id_or_url)
        parent_id = self.parse_drive_file_id(parent_id_or_url)
        if not file_id:
            raise GoogleDriverError("无法解析 Google Drive 模板文件 ID")
        if not parent_id:
            raise GoogleDriverError("无法解析 Google Drive 目标目录 ID")
        response = self._execute(
            lambda: self._drive_service.files().copy(
                fileId=file_id,
                body={"name": name, "parents": [parent_id]},
                fields="id,name,mimeType,createdTime,modifiedTime,webViewLink",
                supportsAllDrives=True,
            )
        )
        copied_id = str(response["id"])
        return GoogleDriveFile(
            id=copied_id,
            name=str(response.get("name") or name),
            mime_type=str(response.get("mimeType") or "application/vnd.google-apps.spreadsheet"),
            created_time=response.get("createdTime"),
            modified_time=response.get("modifiedTime"),
            web_view_link=response.get("webViewLink") or f"https://docs.google.com/spreadsheets/d/{copied_id}/edit",
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

    def _load_credentials(self, proxy_url: str | None) -> GoogleCredentials:
        if self.service_account_path is not None and self.service_account_path.exists():
            return ServiceAccountCredentials.from_service_account_file(
                str(self.service_account_path),
                scopes=GOOGLE_SCOPES,
            )

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
                "Google API 凭据不存在或无效。请配置服务账号 "
                f"{self.service_account_path}，或 OAuth token {self.token_path}。"
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

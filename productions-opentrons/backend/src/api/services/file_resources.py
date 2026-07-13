from __future__ import annotations

from datetime import datetime
import mimetypes
from pathlib import Path
import re
import shutil
from typing import Any

import aiofiles
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import UploadFile
from pymongo.errors import DuplicateKeyError

import settings as setting
from api.services.logging import logger
from database.mongodb import mongodb


UPLOAD_CHUNK_SIZE = 1024 * 1024


class FileResourceValidationError(ValueError):
    pass


class FileResourceNotFoundError(LookupError):
    pass


def utc_now() -> datetime:
    return datetime.utcnow()


def normalize_required_text(value: Any, label: str, *, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise FileResourceValidationError(f"{label}不能为空")
    if len(text) > max_length:
        raise FileResourceValidationError(f"{label}不能超过 {max_length} 个字符")
    return text


def normalize_optional_text(value: Any, *, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise FileResourceValidationError(f"内容不能超过 {max_length} 个字符")
    return text


def parse_object_id(value: str, label: str) -> ObjectId:
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError) as exc:
        raise FileResourceValidationError(f"无效的{label}") from exc


def safe_filename(value: str | None) -> str:
    filename = Path(str(value or "")).name.replace("\x00", "").strip()
    if not filename:
        raise FileResourceValidationError("请选择文件")
    sanitized = re.sub(r"[^\w.()\-\u4e00-\u9fff ]+", "_", filename, flags=re.UNICODE).strip(" .")
    return sanitized[:180] or "resource-file"


def get_resource_collections():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("文件资源数据库连接失败")

    database = mongodb.get_database(setting.MESSAGE_COLLECTION)
    projects = database[setting.FILE_RESOURCE_PROJECTS_COLLECTION]
    versions = database[setting.FILE_RESOURCE_VERSIONS_COLLECTION]
    try:
        projects.create_index("name_key", unique=True)
        projects.create_index("updated_at")
        versions.create_index([("project_id", 1), ("version_key", 1)], unique=True)
        versions.create_index([("project_id", 1), ("created_at", -1)])
    except Exception as exc:
        logger.warning("File resource index creation skipped: %s", exc)
    return projects, versions


def serialize_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat() + ("Z" if value.tzinfo is None else "")
    return value


def serialize_version(document: dict[str, Any]) -> dict[str, Any]:
    version_id = str(document.get("_id") or "")
    return {
        "id": version_id,
        "project_id": str(document.get("project_id") or ""),
        "version": document.get("version") or "",
        "version_notes": document.get("version_notes") or "",
        "filename": document.get("filename") or "",
        "file_size": int(document.get("file_size") or 0),
        "content_type": document.get("content_type") or "application/octet-stream",
        "created_at": serialize_datetime(document.get("created_at")),
        "updated_at": serialize_datetime(document.get("updated_at")),
        "download_url": f"/api/file-resources/versions/{version_id}/download",
    }


def serialize_project(document: dict[str, Any], versions: list[dict[str, Any]]) -> dict[str, Any]:
    serialized_versions = [serialize_version(version) for version in versions]
    return {
        "id": str(document.get("_id") or ""),
        "name": document.get("name") or "",
        "description": document.get("description") or "",
        "created_at": serialize_datetime(document.get("created_at")),
        "updated_at": serialize_datetime(document.get("updated_at")),
        "version_count": len(serialized_versions),
        "versions": serialized_versions,
    }


def list_projects() -> dict[str, Any]:
    projects_collection, versions_collection = get_resource_collections()
    project_documents = list(projects_collection.find({}).sort("updated_at", -1))
    version_documents = list(versions_collection.find({}).sort("created_at", -1))
    versions_by_project: dict[str, list[dict[str, Any]]] = {}
    for version in version_documents:
        versions_by_project.setdefault(str(version.get("project_id") or ""), []).append(version)

    projects = [
        serialize_project(project, versions_by_project.get(str(project.get("_id") or ""), []))
        for project in project_documents
    ]
    return {"projects": projects, "total": len(projects)}


def get_project(project_id: ObjectId) -> dict[str, Any] | None:
    projects_collection, versions_collection = get_resource_collections()
    project = projects_collection.find_one({"_id": project_id})
    if project is None:
        return None
    versions = list(versions_collection.find({"project_id": project_id}).sort("created_at", -1))
    return serialize_project(project, versions)


def resolve_project(
    *,
    project_id: str | None,
    project_name: str,
    project_description: str,
) -> ObjectId:
    projects_collection, _ = get_resource_collections()
    description = normalize_optional_text(project_description, max_length=2000)
    now = utc_now()

    if project_id:
        object_id = parse_object_id(project_id, "项目")
        project = projects_collection.find_one({"_id": object_id})
        if project is None:
            raise FileResourceNotFoundError("项目不存在")
        updates: dict[str, Any] = {"updated_at": now}
        if description != str(project.get("description") or ""):
            updates["description"] = description
        projects_collection.update_one({"_id": object_id}, {"$set": updates})
        return object_id

    name = normalize_required_text(project_name, "项目名称", max_length=120)
    name_key = name.casefold()
    existing = projects_collection.find_one({"name_key": name_key})
    if existing is not None:
        projects_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": {"description": description, "updated_at": now}},
        )
        return existing["_id"]

    document = {
        "name": name,
        "name_key": name_key,
        "description": description,
        "created_at": now,
        "updated_at": now,
    }
    try:
        return projects_collection.insert_one(document).inserted_id
    except DuplicateKeyError:
        existing = projects_collection.find_one({"name_key": name_key})
        if existing is None:
            raise
        return existing["_id"]


async def create_version(
    *,
    project_id: str | None,
    project_name: str,
    project_description: str,
    version: str,
    version_notes: str,
    upload: UploadFile,
) -> dict[str, Any]:
    version_value = normalize_required_text(version, "版本号", max_length=80)
    notes = normalize_optional_text(version_notes, max_length=4000)
    filename = safe_filename(upload.filename)
    project_object_id = resolve_project(
        project_id=project_id,
        project_name=project_name,
        project_description=project_description,
    )
    projects_collection, versions_collection = get_resource_collections()
    version_key = version_value.casefold()
    if versions_collection.find_one({"project_id": project_object_id, "version_key": version_key}):
        raise FileResourceValidationError(f"版本 {version_value} 已存在")

    version_object_id = ObjectId()
    relative_path = Path(str(project_object_id)) / str(version_object_id) / filename
    storage_root = Path(setting.FILE_RESOURCE_DIR).resolve()
    target_path = (storage_root / relative_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    file_size = 0

    try:
        async with aiofiles.open(target_path, "wb") as output:
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                file_size += len(chunk)
                await output.write(chunk)

        now = utc_now()
        document = {
            "_id": version_object_id,
            "project_id": project_object_id,
            "version": version_value,
            "version_key": version_key,
            "version_notes": notes,
            "filename": filename,
            "relative_path": relative_path.as_posix(),
            "file_size": file_size,
            "content_type": upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "created_at": now,
            "updated_at": now,
        }
        versions_collection.insert_one(document)
        projects_collection.update_one({"_id": project_object_id}, {"$set": {"updated_at": now}})
        return serialize_version(document)
    except DuplicateKeyError as exc:
        target_path.unlink(missing_ok=True)
        raise FileResourceValidationError(f"版本 {version_value} 已存在") from exc
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def update_version(version_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    projects_collection, versions_collection = get_resource_collections()
    object_id = parse_object_id(version_id, "版本")
    document = versions_collection.find_one({"_id": object_id})
    if document is None:
        raise FileResourceNotFoundError("版本不存在")

    set_values: dict[str, Any] = {"updated_at": utc_now()}
    if "version" in updates:
        version_value = normalize_required_text(updates.get("version"), "版本号", max_length=80)
        set_values["version"] = version_value
        set_values["version_key"] = version_value.casefold()
    if "version_notes" in updates:
        set_values["version_notes"] = normalize_optional_text(updates.get("version_notes"), max_length=4000)
    if len(set_values) == 1:
        raise FileResourceValidationError("没有需要更新的版本信息")

    try:
        versions_collection.update_one({"_id": object_id}, {"$set": set_values})
    except DuplicateKeyError as exc:
        raise FileResourceValidationError(f"版本 {set_values.get('version')} 已存在") from exc
    projects_collection.update_one(
        {"_id": document.get("project_id")},
        {"$set": {"updated_at": set_values["updated_at"]}},
    )
    updated = versions_collection.find_one({"_id": object_id})
    return serialize_version(updated or document)


def resolve_download(version_id: str) -> tuple[Path, str, str]:
    _, versions_collection = get_resource_collections()
    object_id = parse_object_id(version_id, "版本")
    document = versions_collection.find_one({"_id": object_id})
    if document is None:
        raise FileResourceNotFoundError("版本不存在")

    storage_root = Path(setting.FILE_RESOURCE_DIR).resolve()
    file_path = (storage_root / str(document.get("relative_path") or "")).resolve()
    if not file_path.is_relative_to(storage_root) or not file_path.is_file():
        raise FileResourceNotFoundError("资源文件不存在")
    return (
        file_path,
        str(document.get("filename") or file_path.name),
        str(document.get("content_type") or "application/octet-stream"),
    )


def delete_version(version_id: str) -> dict[str, Any]:
    projects_collection, versions_collection = get_resource_collections()
    object_id = parse_object_id(version_id, "版本")
    document = versions_collection.find_one_and_delete({"_id": object_id})
    if document is None:
        raise FileResourceNotFoundError("版本不存在")

    storage_root = Path(setting.FILE_RESOURCE_DIR).resolve()
    version_dir = (storage_root / str(document.get("project_id")) / str(object_id)).resolve()
    if version_dir.is_relative_to(storage_root) and version_dir.exists():
        shutil.rmtree(version_dir)
    projects_collection.update_one(
        {"_id": document.get("project_id")},
        {"$set": {"updated_at": utc_now()}},
    )
    return {"success": True, "deleted_version_id": version_id}

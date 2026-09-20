from __future__ import annotations

import asyncio
import os
import re
from collections import OrderedDict
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query


router = APIRouter(prefix="/tools/pip-settings", tags=["pip-settings"])

REPOSITORY = "https://github.com/Opentrons/opentrons"
API_ROOT = "https://api.github.com/repos/Opentrons/opentrons"
RAW_ROOT = "https://raw.githubusercontent.com/Opentrons/opentrons"
PIPETTE_ROOT = "shared-data/pipette/definitions/2"
LIQUID_CLASS_ROOT = "shared-data/liquid-class/definitions/1"
PIPETTE_PATH = re.compile(
    r"^(general|geometry|liquid)/"
    r"(single_channel|eight_channel|eight_channel_em|ninety_six_channel)/"
    r"p\d+/(?:[^/]+/)?3_\d+\.json$"
)
LIQUID_CLASS_PATH = re.compile(r"^[^/]+/\d+\.json$")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")

CHANNEL_METADATA = {
    "single_channel": {"label": "1-Channel", "channels": 1, "prefix": "flex_1channel_"},
    "eight_channel": {"label": "8-Channel", "channels": 8, "prefix": "flex_8channel_"},
    "eight_channel_em": {"label": "8-Channel EM", "channels": 8, "prefix": None},
    "ninety_six_channel": {"label": "96-Channel", "channels": 96, "prefix": "flex_96channel_"},
}


class PipSettingsGithubError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _validate_branch_name(branch: str) -> str:
    normalized = branch.strip()
    if not normalized or len(normalized) > 240 or CONTROL_CHARACTERS.search(normalized):
        raise PipSettingsGithubError("Enter a valid GitHub branch name.", 400)
    return normalized


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("_"))
    except ValueError:
        return (0,)


def _as_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _as_number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _to_liquid_class(document: dict[str, Any]) -> dict[str, Any] | None:
    data = document["data"]
    liquid_class_name = _as_string(data.get("liquidClassName"))
    display_name = _as_string(data.get("displayName"))
    version = _as_number(data.get("version"))
    by_pipette = data.get("byPipette")
    if (
        not liquid_class_name
        or not display_name
        or version is None
        or not isinstance(by_pipette, list)
    ):
        return None
    return {
        "id": f"{liquid_class_name}/{version}",
        "liquidClassName": liquid_class_name,
        "displayName": display_name,
        "description": _as_string(data.get("description")) or "",
        "schemaVersion": _as_number(data.get("schemaVersion")) or 1,
        "version": version,
        "namespace": _as_string(data.get("namespace")) or "opentrons",
        "sourcePath": document["sourcePath"],
        "byPipette": by_pipette,
    }


def build_dataset(
    branch: str,
    commit: str,
    pipette_documents: list[dict[str, Any]],
    liquid_class_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    pipette_map: dict[str, dict[str, Any]] = {}

    for document in pipette_documents:
        relative_path = document["sourcePath"].removeprefix(f"{PIPETTE_ROOT}/")
        parts = relative_path.split("/")
        if len(parts) < 4:
            continue
        category, channel_type, model = parts[:3]
        metadata = CHANNEL_METADATA.get(channel_type)
        if metadata is None or category not in {"general", "geometry", "liquid"}:
            continue
        version = parts[-1].removesuffix(".json")
        profile = parts[3] if category == "liquid" and len(parts) > 4 else "default"
        pipette_id = f"{channel_type}/{model}"
        max_volume = int(model.removeprefix("p"))

        pipette = pipette_map.setdefault(
            pipette_id,
            {
                "id": pipette_id,
                "liquidClassModel": (
                    f"{metadata['prefix']}{max_volume}" if metadata["prefix"] else None
                ),
                "displayName": f"Flex {metadata['label']} {max_volume} µL",
                "displayCategory": "FLEX",
                "channelType": channel_type,
                "channelLabel": metadata["label"],
                "channels": metadata["channels"],
                "model": model,
                "maxVolume": max_volume,
                "revisions": {},
            },
        )
        revision = pipette["revisions"].setdefault(
            version,
            {"version": version, "liquid": {}},
        )
        if category == "liquid":
            revision["liquid"][profile] = document
        else:
            revision[category] = document

        if category == "general":
            pipette["displayName"] = (
                _as_string(document["data"].get("displayName"))
                or pipette["displayName"]
            )
            pipette["displayCategory"] = (
                _as_string(document["data"].get("displayCategory")) or pipette["displayCategory"]
            )
            pipette["channels"] = (
                _as_number(document["data"].get("channels"))
                or pipette["channels"]
            )

    pipettes: list[dict[str, Any]] = []
    for pipette in pipette_map.values():
        revisions = sorted(
            pipette.pop("revisions").values(),
            key=lambda item: _version_key(item["version"]),
        )
        if revisions:
            pipette["revisions"] = revisions
            pipettes.append(pipette)
    pipettes.sort(
        key=lambda item: (item["channels"], item["maxVolume"], item["displayName"])
    )

    liquid_classes = [
        definition
        for document in liquid_class_documents
        if (definition := _to_liquid_class(document)) is not None
    ]
    liquid_classes.sort(key=lambda item: (item["displayName"], item["version"]))
    if not pipettes:
        raise PipSettingsGithubError(
            f'Branch "{branch}" does not contain Gen3 pipette definitions.',
            404,
        )

    return {
        "source": {
            "repository": REPOSITORY,
            "branch": branch,
            "commit": commit,
            "pipetteDefinitions": f"{REPOSITORY}/tree/{commit}/{PIPETTE_ROOT}",
            "liquidClassDefinitions": f"{REPOSITORY}/tree/{commit}/{LIQUID_CLASS_ROOT}",
        },
        "stats": {
            "pipetteTypes": len(pipettes),
            "pipetteDefinitionFiles": len(pipette_documents),
            "liquidClassDefinitionFiles": len(liquid_classes),
        },
        "pipettes": pipettes,
        "liquidClasses": liquid_classes,
    }


class PipSettingsGithubService:
    def __init__(self) -> None:
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

    @staticmethod
    def _headers() -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Productions-PipSettings/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _request_json(self, client: httpx.AsyncClient, url: str) -> Any:
        response: httpx.Response | None = None
        for attempt in range(3):
            try:
                response = await client.get(url)
                break
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == 2:
                    raise PipSettingsGithubError(
                        "Unable to connect to GitHub. Check the network connection and try again."
                    ) from exc
                await asyncio.sleep(0.3 * (attempt + 1))
        if response is None:
            raise PipSettingsGithubError("Unable to connect to GitHub.")
        if response.status_code >= 400:
            message = ""
            try:
                message = str(response.json().get("message", ""))
            except (ValueError, AttributeError):
                pass
            if (
                response.status_code == 403
                and response.headers.get("x-ratelimit-remaining") == "0"
            ):
                raise PipSettingsGithubError(
                    "GitHub API rate limit reached. Please try again later.", 429
                )
            status_code = 404 if response.status_code == 404 else 502
            raise PipSettingsGithubError(
                message or f"GitHub request failed ({response.status_code}).",
                status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise PipSettingsGithubError("GitHub returned invalid JSON.") from exc

    async def search_branches(self, query: str) -> list[dict[str, str]]:
        normalized = query.strip()
        if len(normalized) > 240 or CONTROL_CHARACTERS.search(normalized):
            raise PipSettingsGithubError("Enter a valid GitHub branch prefix.", 400)
        async with httpx.AsyncClient(
            headers=self._headers(), timeout=30.0, follow_redirects=False
        ) as client:
            if normalized:
                encoded = quote(normalized, safe="")
                references = await self._request_json(
                    client, f"{API_ROOT}/git/matching-refs/heads/{encoded}"
                )
                branches = [
                    {
                        "name": reference["ref"].removeprefix("refs/heads/"),
                        "commit": reference["object"]["sha"],
                    }
                    for reference in references[:100]
                ]
            else:
                records = await self._request_json(
                    client, f"{API_ROOT}/branches?per_page=40&page=1"
                )
                branches = [
                    {"name": record["name"], "commit": record["commit"]["sha"]}
                    for record in records
                ]
        return sorted(
            branches,
            key=lambda item: (item["name"] != "edge", item["name"].casefold()),
        )

    async def _list_json_paths(
        self, client: httpx.AsyncClient, commit: str, root: str
    ) -> list[str]:
        treeish = quote(f"{commit}:{root}", safe="")
        result = await self._request_json(client, f"{API_ROOT}/git/trees/{treeish}?recursive=1")
        if result.get("truncated"):
            raise PipSettingsGithubError(
                f"GitHub returned an incomplete directory listing for {root}."
            )
        return [
            item["path"]
            for item in result.get("tree", [])
            if item.get("type") == "blob" and str(item.get("path", "")).endswith(".json")
        ]

    async def _fetch_documents(
        self,
        client: httpx.AsyncClient,
        commit: str,
        root: str,
        paths: list[str],
        concurrency: int,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch(path: str) -> dict[str, Any]:
            source_path = f"{root}/{path}"
            encoded_path = "/".join(quote(part, safe="") for part in source_path.split("/"))
            async with semaphore:
                data = await self._request_json(client, f"{RAW_ROOT}/{commit}/{encoded_path}")
            if not isinstance(data, dict):
                raise PipSettingsGithubError(f"GitHub returned invalid data for {source_path}.")
            return {"sourcePath": source_path, "data": data}

        return list(await asyncio.gather(*(fetch(path) for path in paths)))

    async def load_branch(self, branch: str) -> dict[str, Any]:
        normalized = _validate_branch_name(branch)
        async with httpx.AsyncClient(
            headers=self._headers(), timeout=30.0, follow_redirects=False
        ) as client:
            encoded_branch = quote(normalized, safe="")
            branch_info = await self._request_json(
                client, f"{API_ROOT}/branches/{encoded_branch}"
            )
            commit = branch_info["commit"]["sha"]
            cache_key = f"{normalized}:{commit}"
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                return self._cache[cache_key]

            pipette_paths, liquid_class_paths = await asyncio.gather(
                self._list_json_paths(client, commit, PIPETTE_ROOT),
                self._list_json_paths(client, commit, LIQUID_CLASS_ROOT),
            )
            valid_pipette_paths = [
                path for path in pipette_paths if PIPETTE_PATH.fullmatch(path)
            ]
            valid_liquid_paths = [
                path for path in liquid_class_paths if LIQUID_CLASS_PATH.fullmatch(path)
            ]
            pipette_documents, liquid_class_documents = await asyncio.gather(
                self._fetch_documents(client, commit, PIPETTE_ROOT, valid_pipette_paths, 5),
                self._fetch_documents(client, commit, LIQUID_CLASS_ROOT, valid_liquid_paths, 3),
            )

        dataset = build_dataset(
            normalized,
            commit,
            pipette_documents,
            liquid_class_documents,
        )
        self._cache[cache_key] = dataset
        self._cache.move_to_end(cache_key)
        while len(self._cache) > 3:
            self._cache.popitem(last=False)
        return dataset


github_service = PipSettingsGithubService()


def get_pip_settings_github_service() -> PipSettingsGithubService:
    return github_service


def _http_error(exc: PipSettingsGithubError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/branches")
async def search_pip_settings_branches(
    query: str = Query("", max_length=240),
    service: PipSettingsGithubService = Depends(get_pip_settings_github_service),
) -> dict[str, list[dict[str, str]]]:
    try:
        return {"branches": await service.search_branches(query)}
    except PipSettingsGithubError as exc:
        raise _http_error(exc) from exc


@router.get("/dataset")
async def load_pip_settings_dataset(
    branch: str = Query("edge", min_length=1, max_length=240),
    service: PipSettingsGithubService = Depends(get_pip_settings_github_service),
) -> dict[str, Any]:
    try:
        return await service.load_branch(branch)
    except PipSettingsGithubError as exc:
        raise _http_error(exc) from exc

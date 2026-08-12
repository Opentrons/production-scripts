from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx


SOURCE_ROOTS_ENV = "PRODUCTION_PLATFORM_OPENTRONS_SOURCE_ROOTS"
MAX_SOURCE_FILE_BYTES = 2 * 1024 * 1024
MAX_OFFICIAL_PAGE_BYTES = 5 * 1024 * 1024
MAX_READ_LINES = 400

_SOURCE_EXTENSIONS = {
    ".css",
    ".graphql",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".proto",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
_EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "site-packages",
}
_OFFICIAL_HOSTS = {
    "docs.opentrons.com",
    "labware.opentrons.com",
    "opentrons.com",
    "shop.opentrons.com",
    "support.opentrons.com",
    "www.opentrons.com",
}
_SEARCH_TOKEN_PATTERN = re.compile(r"[a-z0-9_./:@-]+|[\u3400-\u4dbf\u4e00-\u9fff]+", re.IGNORECASE)


OFFICIAL_DOCUMENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "protocol-api-overview",
        "title": "Python Protocol API",
        "url": "https://docs.opentrons.com/python-api/",
        "summary": "Protocol API 总览、协议结构和 Flex/OT-2 Python Protocol 入门。",
        "tags": ["Protocol API", "Python", "protocol", "Flex", "OT-2", "脚本"],
    },
    {
        "id": "protocol-api-tutorial",
        "title": "Protocol API Tutorial",
        "url": "https://docs.opentrons.com/python-api/tutorial/",
        "summary": "从 requirements、run() 到加载 labware、pipette 和执行移液的完整教程。",
        "tags": ["教程", "requirements", "apiLevel", "run", "load_labware", "load_instrument"],
    },
    {
        "id": "protocol-api-examples",
        "title": "Protocol Examples",
        "url": "https://docs.opentrons.com/python-api/examples/",
        "summary": "Flex 与 OT-2 可导入 Opentrons App 验证的 Python Protocol 示例。",
        "tags": ["示例", "protocol", "Flex", "OT-2", "编写脚本"],
    },
    {
        "id": "protocol-api-versioning",
        "title": "Protocol API Versioning",
        "url": "https://docs.opentrons.com/python-api/versioning/",
        "summary": "apiLevel、机器人兼容范围、行为变更和 Protocol API 版本选择。",
        "tags": ["apiLevel", "version", "版本", "兼容性", "requirements", "metadata"],
    },
    {
        "id": "protocol-api-context",
        "title": "ProtocolContext Reference",
        "url": "https://docs.opentrons.com/python-api/reference/protocols/",
        "summary": "ProtocolContext 的加载、运行控制、移动 labware 和机器人功能参考。",
        "tags": ["ProtocolContext", "load_labware", "load_module", "move_labware", "pause"],
    },
    {
        "id": "protocol-api-instruments",
        "title": "InstrumentContext Reference",
        "url": "https://docs.opentrons.com/python-api/reference/instruments/",
        "summary": "pipette 的 aspirate、dispense、transfer、distribute、consolidate 等命令参考。",
        "tags": ["InstrumentContext", "pipette", "aspirate", "dispense", "transfer", "移液"],
    },
    {
        "id": "protocol-api-labware",
        "title": "Labware Reference",
        "url": "https://docs.opentrons.com/python-api/reference/labware/",
        "summary": "Labware、Well、位置、偏移和自定义 labware 的 API 参考。",
        "tags": ["labware", "well", "deck", "slot", "offset", "耗材"],
    },
    {
        "id": "protocol-api-modules",
        "title": "Hardware Modules",
        "url": "https://docs.opentrons.com/python-api/modules/",
        "summary": "温控、热循环、加热振荡、磁力、Flex Stacker 等模块使用指南。",
        "tags": ["module", "模块", "heater-shaker", "thermocycler", "temperature", "stacker"],
    },
    {
        "id": "protocol-api-runtime-parameters",
        "title": "Runtime Parameters",
        "url": "https://docs.opentrons.com/python-api/runtime-parameters/",
        "summary": "在 Protocol 中定义和读取运行时参数。",
        "tags": ["runtime parameter", "params", "参数", "变量"],
    },
    {
        "id": "http-api-reference",
        "title": "Opentrons HTTP API Spec",
        "url": "https://docs.opentrons.com/http/api_reference.html",
        "summary": "Robot Server HTTP API 的 OpenAPI 参考，包括 health、protocols、runs 和 commands。",
        "tags": ["HTTP API", "Robot Server", "OpenAPI", "health", "runs", "protocols", "commands", "curl"],
    },
    {
        "id": "flex-user-manual",
        "title": "Opentrons Flex Documentation",
        "url": "https://docs.opentrons.com/flex/",
        "summary": "Flex 安装、仪器、模块、协议运行、维护、日志和开放源码手册。",
        "tags": ["Flex", "产品", "robot", "pipette", "gripper", "module", "维护"],
    },
    {
        "id": "flex-product",
        "title": "Opentrons Flex Robot",
        "url": "https://opentrons.com/products/opentrons-flex-robot",
        "summary": "Flex 产品功能、pipette、gripper、deck、模块和技术规格。",
        "tags": ["Flex", "产品", "规格", "pipette", "gripper", "deck"],
    },
    {
        "id": "robots-product-catalog",
        "title": "Opentrons Robots",
        "url": "https://opentrons.com/products/categories/robots",
        "summary": "Opentrons 当前机器人产品目录，包括 Flex 与 OT-2。",
        "tags": ["产品", "机器人", "Flex", "OT-2", "catalog"],
    },
    {
        "id": "flex-open-source",
        "title": "Flex Open-Source Software",
        "url": "https://docs.opentrons.com/flex/open-source/",
        "summary": "Opentrons monorepo 目录、Protocol API、Robot Server、shared-data 和固件仓库说明。",
        "tags": ["source", "源码", "monorepo", "robot-server", "shared-data", "firmware", "ot3"],
    },
    {
        "id": "labware-library",
        "title": "Opentrons Labware Library",
        "url": "https://labware.opentrons.com/",
        "summary": "Opentrons 官方 labware 定义、load name 和几何信息。",
        "tags": ["labware", "load name", "definition", "耗材", "几何"],
    },
)

_SCOPED_PATHS: dict[str, tuple[str, ...]] = {
    "all": (".",),
    "protocol_api": (
        "api/src/opentrons/protocol_api",
        "api/src/opentrons/protocol_engine",
        "api/tests/opentrons/protocol_api",
        "docs/python-api/docs",
    ),
    "http_api": ("robot-server/robot_server", "robot-server/tests"),
    "products": ("docs/flex/docs", "docs/ot-2/docs", "shared-data"),
    "docs": ("docs", "api/docs"),
    "tests": ("api/tests", "robot-server/tests"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _search_terms(query: str) -> list[str]:
    normalized = str(query or "").strip()
    if not normalized:
        raise ValueError("检索关键词不能为空")
    if len(normalized) > 200:
        raise ValueError("检索关键词不能超过 200 个字符")
    terms = [normalized]
    for token in _SEARCH_TOKEN_PATTERN.findall(normalized):
        token = token.strip()
        if len(token) >= 2 and token.casefold() not in {item.casefold() for item in terms}:
            terms.append(token)
    return terms[:12]


def _candidate_source_roots() -> list[Path]:
    configured = str(os.getenv(SOURCE_ROOTS_ENV, "") or "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.extend(Path(item.strip()).expanduser() for item in configured.split(os.pathsep) if item.strip())
    home = Path.home()
    candidates.extend(
        (
            home / "projects" / "opentrons",
            home / "projects" / "opentorns",
            Path("/opentrons"),
        )
    )
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        marker_paths = (resolved / "api", resolved / "robot-server", resolved / "docs")
        if not resolved.is_dir() or not any(marker.exists() for marker in marker_paths):
            continue
        normalized = str(resolved)
        if normalized not in seen:
            seen.add(normalized)
            roots.append(resolved)
    return roots


def _repo_revision(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unknown"


def _root_details(root: Path) -> dict[str, Any]:
    return {
        "path": str(root),
        "revision": _repo_revision(root),
        "has_protocol_api": (root / "api/src/opentrons/protocol_api").is_dir(),
        "has_http_api": (root / "robot-server/robot_server").is_dir(),
        "has_official_docs_source": (root / "docs").is_dir(),
    }


def get_opentrons_knowledge_status() -> dict[str, Any]:
    roots = _candidate_source_roots()
    return {
        "official_documents": len(OFFICIAL_DOCUMENTS),
        "source_roots": [_root_details(root) for root in roots],
        "source_available": bool(roots),
        "source_roots_environment": SOURCE_ROOTS_ENV,
        "checked_at": _utc_now(),
    }


def _catalog_score(document: dict[str, Any], terms: list[str]) -> int:
    title = str(document["title"]).casefold()
    summary = str(document["summary"]).casefold()
    tags = " ".join(str(item) for item in document["tags"]).casefold()
    score = 0
    for term in terms:
        folded = term.casefold()
        if folded in title:
            score += 12
        if folded in tags:
            score += 8
        if folded in summary:
            score += 4
    return score


def search_opentrons_official_docs(query: str, limit: int = 8) -> dict[str, Any]:
    terms = _search_terms(query)
    scored = [(_catalog_score(document, terms), document) for document in OFFICIAL_DOCUMENTS]
    matches = [dict(document, score=score) for score, document in sorted(scored, key=lambda item: item[0], reverse=True) if score > 0]
    maximum = max(1, min(int(limit), 20))
    return {
        "query": str(query).strip(),
        "documents": matches[:maximum],
        "total": len(matches),
        "source": "Opentrons official documentation catalog",
    }


def _official_url(document_id: str, url: str) -> tuple[str, str]:
    normalized_id = str(document_id or "").strip()
    normalized_url = str(url or "").strip()
    if normalized_id:
        document = next((item for item in OFFICIAL_DOCUMENTS if item["id"] == normalized_id), None)
        if document is None:
            raise ValueError("未知的官方文档 ID，请先调用 search_opentrons_official_docs")
        normalized_url = str(document["url"])
    if not normalized_url:
        raise ValueError("document_id 或 url 至少提供一个")
    parsed = urlparse(normalized_url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in _OFFICIAL_HOSTS or parsed.username or parsed.password:
        raise ValueError("只允许读取 Opentrons 官方 HTTPS 文档")
    if parsed.port not in (None, 443):
        raise ValueError("官方文档 URL 不允许使用自定义端口")
    return normalized_id, normalized_url


class _ReadableHTMLParser(HTMLParser):
    _BLOCK_TAGS = {
        "article",
        "blockquote",
        "br",
        "code",
        "dd",
        "div",
        "dl",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "main",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }
    _IGNORED_TAGS = {"script", "style", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
        if tag == "title":
            self._in_title = True
        if not self._ignored_depth and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
        if not self._ignored_depth and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        self.parts.append(text)

    def text(self) -> str:
        combined = " ".join(self.parts)
        combined = re.sub(r"[ \t\r\f\v]+", " ", combined)
        combined = re.sub(r" *\n *", "\n", combined)
        return re.sub(r"\n{3,}", "\n\n", combined).strip()


def _validate_final_official_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").casefold() not in _OFFICIAL_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("官方文档重定向到了不受信任的地址")


def _relevant_official_excerpt(content: str, query: str, maximum: int) -> tuple[str, int]:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return content[:maximum], 0
    terms = _search_terms(normalized_query)
    folded_terms = [term.casefold() for term in terms]
    lines = content.splitlines()
    scored_lines: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        folded_line = line.casefold()
        matching_count = sum(1 for term in folded_terms if term in folded_line)
        if not matching_count:
            continue
        score = 10 * matching_count
        if folded_terms[0] in folded_line:
            score += 100
        scored_lines.append((score, index))
    scored_lines.sort(key=lambda item: (-item[0], item[1]))
    segments: list[str] = []
    covered_lines: set[int] = set()
    length = 0
    for _, index in scored_lines:
        start = max(0, index - 4)
        end = min(len(lines), index + 10)
        if any(line_number in covered_lines for line_number in range(start, end)):
            continue
        segment = "\n".join(lines[start:end]).strip()
        if not segment:
            continue
        separator_length = 7 if segments else 0
        available = maximum - length - separator_length
        if available <= 0:
            break
        segments.append(segment[:available])
        covered_lines.update(range(start, end))
        length += min(len(segment), available) + separator_length
        if length >= maximum:
            break
    return ("\n\n...\n\n".join(segments) if segments else content[:maximum]), len(scored_lines)


def read_opentrons_official_doc(
    document_id: str = "",
    url: str = "",
    query: str = "",
    max_chars: int = 16000,
) -> dict[str, Any]:
    normalized_id, official_url = _official_url(document_id, url)
    maximum = max(1000, min(int(max_chars), 30000))
    headers = {"User-Agent": "ProductionPlatformKnowledge/1.0 (+Opentrons technical assistant)"}
    try:
        with httpx.Client(follow_redirects=True, timeout=15, headers=headers) as client:
            with client.stream("GET", official_url) as response:
                response.raise_for_status()
                _validate_final_official_url(str(response.url))
                content_type = str(response.headers.get("content-type") or "").casefold()
                if not any(item in content_type for item in ("html", "text", "json")):
                    raise ValueError(f"不支持的官方文档格式: {content_type or 'unknown'}")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_OFFICIAL_PAGE_BYTES:
                        raise ValueError("官方文档超过 5 MB，已停止读取")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                body = raw.decode(encoding, errors="replace")
                final_url = str(response.url)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"读取 Opentrons 官方文档失败: {exc}") from exc

    title = ""
    if "html" in content_type:
        parser = _ReadableHTMLParser()
        parser.feed(body)
        content = parser.text()
        title = parser.title
    else:
        content = body.strip()
    selected_content, match_count = _relevant_official_excerpt(content, query, maximum)
    return {
        "document_id": normalized_id,
        "title": title,
        "url": final_url,
        "query": str(query or "").strip(),
        "match_count": match_count,
        "content": selected_content,
        "truncated": len(selected_content) < len(content),
        "retrieved_at": _utc_now(),
        "source": "Opentrons official website",
    }


def _select_root(root: str = "") -> list[Path]:
    roots = _candidate_source_roots()
    if not roots:
        raise RuntimeError(
            "未找到 Opentrons 源码目录；请部署到 ~/projects/opentrons、~/projects/opentorns 或 /opentrons，"
            f"也可通过 {SOURCE_ROOTS_ENV} 配置绝对路径"
        )
    normalized = str(root or "").strip()
    if not normalized:
        return roots
    try:
        requested = Path(normalized).expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise ValueError("指定的源码根目录不存在") from exc
    if requested not in roots:
        raise ValueError("源码根目录不在允许列表中")
    return [requested]


def _safe_source_path(root: Path, relative_path: str, *, require_file: bool = False) -> Path:
    normalized = str(relative_path or ".").strip() or "."
    candidate_input = Path(normalized)
    if candidate_input.is_absolute() or ".." in candidate_input.parts:
        raise ValueError("源码路径必须是仓库内的相对路径")
    if any(part.startswith(".") and part != "." for part in candidate_input.parts):
        raise ValueError("不允许读取隐藏目录或隐藏文件")
    if any(part in _EXCLUDED_PARTS for part in candidate_input.parts):
        raise ValueError("该源码路径已被排除")
    try:
        candidate = (root / candidate_input).resolve(strict=True)
        candidate.relative_to(root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise ValueError("源码路径不存在或不在 Opentrons 仓库内") from exc
    if require_file and not candidate.is_file():
        raise ValueError("源码路径不是文件")
    return candidate


def _scope_targets(root: Path, scope: str, path: str) -> list[Path]:
    if path.strip():
        return [_safe_source_path(root, path)]
    normalized_scope = str(scope or "all").strip()
    relative_targets = _SCOPED_PATHS.get(normalized_scope)
    if relative_targets is None:
        raise ValueError(f"不支持的检索范围: {normalized_scope}")
    targets = []
    for relative_target in relative_targets:
        target = root if relative_target == "." else root / relative_target
        if target.exists():
            targets.append(target)
    return targets or [root]


def _is_allowed_source_file(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return (
        path.is_file()
        and path.suffix.casefold() in _SOURCE_EXTENSIONS
        and not any(part.startswith(".") or part in _EXCLUDED_PARTS for part in relative.parts)
    )


def _rg_candidate_files(root: Path, targets: list[Path], terms: list[str], maximum: int) -> list[Path]:
    rg = shutil.which("rg")
    if not rg:
        return []
    command = [rg, "--files-with-matches", "--fixed-strings", "--ignore-case", "--max-filesize", "2M"]
    for extension in sorted(_SOURCE_EXTENSIONS):
        command.extend(("--glob", f"*{extension}"))
    for excluded in sorted(_EXCLUDED_PARTS):
        command.extend(("--glob", f"!**/{excluded}/**"))
    for term in terms:
        command.extend(("-e", term))
    command.extend(str(target) for target in targets)
    candidates: list[Path] = []
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        assert process.stdout is not None
        for raw_path in process.stdout:
            candidate = Path(raw_path.strip())
            if not candidate.is_absolute():
                candidate = root / candidate
            try:
                candidate = candidate.resolve(strict=True)
            except (FileNotFoundError, OSError):
                continue
            if _is_allowed_source_file(candidate, root):
                candidates.append(candidate)
            if len(candidates) >= maximum:
                process.terminate()
                break
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
    except OSError:
        return []
    return candidates


def _walk_candidate_files(root: Path, targets: list[Path], terms: list[str], maximum: int) -> list[Path]:
    candidates: list[Path] = []
    folded_terms = [term.casefold() for term in terms]
    for target in targets:
        paths: Iterable[Path] = (target,) if target.is_file() else target.rglob("*")
        for path in paths:
            if not _is_allowed_source_file(path, root):
                continue
            try:
                if path.stat().st_size > MAX_SOURCE_FILE_BYTES:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace").casefold()
            except OSError:
                continue
            if any(term in content for term in folded_terms):
                candidates.append(path)
            if len(candidates) >= maximum:
                return candidates
    return candidates


def _candidate_files(root: Path, targets: list[Path], terms: list[str], maximum: int) -> list[Path]:
    exact_candidates = _rg_candidate_files(root, targets, terms[:1], maximum)
    expanded_candidates = _rg_candidate_files(root, targets, terms, maximum)
    if not exact_candidates and not expanded_candidates:
        exact_candidates = _walk_candidate_files(root, targets, terms[:1], maximum)
        expanded_candidates = _walk_candidate_files(root, targets, terms, maximum)
    candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in (*exact_candidates, *expanded_candidates):
        if candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)
        if len(candidates) >= maximum:
            break
    return candidates


def _matching_lines(path: Path, terms: list[str], limit: int) -> list[dict[str, Any]]:
    folded_terms = [term.casefold() for term in terms]
    full_query = folded_terms[0]
    matches: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as source_file:
            for line_number, line in enumerate(source_file, start=1):
                folded_line = line.casefold()
                matching_terms = [term for term, folded in zip(terms, folded_terms) if folded in folded_line]
                if not matching_terms:
                    continue
                excerpt = line.strip()
                matches.append(
                    {
                        "line": line_number,
                        "excerpt": excerpt[:500],
                        "matched_terms": matching_terms,
                        "_score": (100 if full_query in folded_line else 0) + 8 * len(matching_terms),
                    }
                )
    except OSError:
        return []
    matches.sort(key=lambda item: (-int(item["_score"]), int(item["line"])))
    return matches[:limit]


def search_opentrons_source(
    query: str,
    scope: str = "all",
    path: str = "",
    root: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    terms = _search_terms(query)
    maximum = max(1, min(int(limit), 50))
    results: list[dict[str, Any]] = []
    searched_roots: list[dict[str, Any]] = []
    for source_root in _select_root(root):
        targets = _scope_targets(source_root, scope, path)
        searched_roots.append(_root_details(source_root))
        candidate_limit = min(max(maximum * 50, 500), 1000)
        candidates = _candidate_files(source_root, targets, terms, candidate_limit)
        for candidate in candidates:
            per_file = _matching_lines(candidate, terms, 3)
            for match in per_file:
                relative_path = candidate.relative_to(source_root).as_posix()
                path_score = 12 if terms[0].casefold() in relative_path.casefold() else 0
                results.append(
                    {
                        "root": str(source_root),
                        "revision": searched_roots[-1]["revision"],
                        "path": relative_path,
                        "_score": int(match.pop("_score")) + path_score,
                        **match,
                    }
                )
    results.sort(key=lambda item: (-int(item["_score"]), str(item["path"]), int(item["line"])))
    selected_results = []
    for result in results[:maximum]:
        result.pop("_score", None)
        selected_results.append(result)
    return {
        "query": str(query).strip(),
        "scope": scope,
        "path": path,
        "matches": selected_results,
        "total_returned": len(selected_results),
        "source_roots": searched_roots,
    }


def read_opentrons_source(
    path: str,
    root: str = "",
    start_line: int = 1,
    end_line: int = 200,
) -> dict[str, Any]:
    start = max(1, int(start_line))
    end = max(start, int(end_line))
    if end - start + 1 > MAX_READ_LINES:
        end = start + MAX_READ_LINES - 1
    selected_root: Path | None = None
    selected_path: Path | None = None
    errors: list[Exception] = []
    for source_root in _select_root(root):
        try:
            candidate = _safe_source_path(source_root, path, require_file=True)
        except ValueError as exc:
            errors.append(exc)
            continue
        if not _is_allowed_source_file(candidate, source_root):
            raise ValueError("只允许读取 Opentrons 仓库内受支持的源码和文档文件")
        selected_root = source_root
        selected_path = candidate
        break
    if selected_root is None or selected_path is None:
        raise ValueError(str(errors[-1]) if errors else "未找到源码文件")
    if selected_path.stat().st_size > MAX_SOURCE_FILE_BYTES:
        raise ValueError("源码文件超过 2 MB，无法读取")
    try:
        lines = selected_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise RuntimeError(f"读取 Opentrons 源码失败: {exc}") from exc
    actual_end = min(end, len(lines))
    selected_lines = lines[start - 1 : actual_end]
    numbered_content = "\n".join(f"{line_number}: {line}" for line_number, line in enumerate(selected_lines, start=start))
    return {
        "root": str(selected_root),
        "revision": _repo_revision(selected_root),
        "path": selected_path.relative_to(selected_root).as_posix(),
        "start_line": start,
        "end_line": actual_end,
        "total_lines": len(lines),
        "content": numbered_content,
    }

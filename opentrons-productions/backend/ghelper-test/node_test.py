from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import requests
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_CONFIG_PATH = SCRIPT_DIR / "skill_config.json"
DEFAULT_YML_FILE = SCRIPT_DIR / "1779072081477.yml"
DEFAULT_TEST_URL = "https://www.googleapis.com/discovery/v1/apis/drive/v3/rest"
DEFAULT_CONNECT_TIMEOUT_SECONDS = int(os.getenv("GHELPER_CONNECT_TIMEOUT_SECONDS", "5"))
DEFAULT_NODE_TIMEOUT_SECONDS = int(os.getenv("GHELPER_NODE_TIMEOUT_SECONDS", "12"))
DEFAULT_SUBSCRIPTION_TIMEOUT_SECONDS = int(os.getenv("GHELPER_SUBSCRIPTION_TIMEOUT_SECONDS", "30"))
DEFAULT_MAX_THREADS = int(os.getenv("GHELPER_MONITOR_THREADS", "25"))


@dataclass(frozen=True)
class ProxyNode:
    name: str
    server: str
    port: int
    username: str
    password: str
    type: str
    tls: bool


@dataclass
class TestResult:
    name: str
    proxy_url: str
    latency: float | None = None
    status_code: int | None = None
    error: str | None = None
    success: bool = False


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json_config(config_path: Path = SKILL_CONFIG_PATH) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as config_file:
        data = json.load(config_file)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a JSON object: {config_path}")
    return data


def write_json_atomic(config_path: Path, data: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = config_path.with_name(f".{config_path.name}.tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_path, config_path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text if text.endswith("\n") else f"{text}\n", encoding="utf-8")
    os.replace(tmp_path, path)


def mask_proxy_url(proxy_url: str) -> str:
    try:
        parts = urlsplit(proxy_url)
        if not parts.netloc or "@" not in parts.netloc:
            return proxy_url
        host = parts.netloc.rsplit("@", 1)[1]
        return urlunsplit((parts.scheme, f"***@{host}", parts.path, parts.query, parts.fragment))
    except Exception:
        return "***"


def validate_subscription_yaml(text: str) -> dict[str, Any]:
    parsed = yaml.safe_load(text) or {}
    if not isinstance(parsed, dict):
        raise ValueError("subscription response is not a YAML object")
    proxies = parsed.get("proxies")
    if not isinstance(proxies, list) or not proxies:
        raise ValueError("subscription response does not contain proxy nodes")
    return parsed


def subscription_request_attempts(config: dict[str, Any]) -> list[tuple[str, dict[str, str] | None]]:
    attempts: list[tuple[str, dict[str, str] | None]] = [("direct", None)]
    proxy_url = str(config.get("proxy", "")).strip()
    if proxy_url:
        attempts.append(("current proxy", {"http": proxy_url, "https": proxy_url}))
    return attempts


def update_subscription_config(
    *,
    config_path: Path = SKILL_CONFIG_PATH,
    yml_file: Path = DEFAULT_YML_FILE,
    timeout: int = DEFAULT_SUBSCRIPTION_TIMEOUT_SECONDS,
) -> bool:
    config = read_json_config(config_path)
    subscription = config.get("ghelper_subscription") or {}
    if not isinstance(subscription, dict):
        print("ghelper_subscription is not configured")
        return False

    url = str(subscription.get("url", "")).strip()
    if not url:
        print("ghelper subscription URL is empty")
        return False

    username = str(subscription.get("username", "")).strip()
    password = str(subscription.get("password", "")).strip()
    auth = (username, password) if username and password else None
    headers = {"User-Agent": "data-handler-ghelper-monitor/1.0"}

    last_error: Exception | None = None
    for label, proxies in subscription_request_attempts(config):
        try:
            print(f"Fetching latest ghelper subscription via {label}...")
            response = requests.get(
                url,
                auth=auth,
                headers=headers,
                proxies=proxies,
                timeout=timeout,
            )
            response.raise_for_status()
            parsed = validate_subscription_yaml(response.text)
            write_text_atomic(yml_file, response.text)

            config["ghelper_subscription_last_updated_at"] = now_utc_iso()
            config["ghelper_subscription_node_count"] = len(parsed.get("proxies", []))
            config["ghelper_subscription_config_file"] = yml_file.name
            write_json_atomic(config_path, config)
            print(f"Updated ghelper subscription: {len(parsed.get('proxies', []))} nodes")
            return True
        except Exception as exc:
            last_error = exc
            print(f"Failed to update subscription via {label}: {exc}")

    if last_error:
        print(f"Using existing proxy list because subscription update failed: {last_error}")
    return False


def load_proxies_from_yml(file_path: Path) -> list[ProxyNode]:
    with file_path.open("r", encoding="utf-8") as yml_file:
        config = yaml.safe_load(yml_file) or {}

    if not isinstance(config, dict):
        raise ValueError(f"Proxy config must be a YAML object: {file_path}")

    proxies: list[ProxyNode] = []
    for proxy in config.get("proxies", []):
        if not isinstance(proxy, dict):
            continue
        proxy_type = str(proxy.get("type", "")).strip().lower()
        if proxy_type not in {"http", "socks5"}:
            continue
        try:
            proxies.append(
                ProxyNode(
                    name=str(proxy["name"]),
                    server=str(proxy["server"]),
                    port=int(proxy["port"]),
                    username=str(proxy.get("username", "")),
                    password=str(proxy.get("password", "")),
                    type=proxy_type,
                    tls=bool(proxy.get("tls", False)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return proxies


def build_proxy_url(node: ProxyNode) -> str:
    if node.type == "http":
        protocol = "https" if node.tls else "http"
    else:
        protocol = "socks5h" if node.tls else "socks5"

    credentials = ""
    if node.username and node.password:
        username = quote(node.username, safe="")
        password = quote(node.password, safe="")
        credentials = f"{username}:{password}@"
    return f"{protocol}://{credentials}{node.server}:{node.port}"


def test_latency(
    proxy_url: str,
    *,
    test_url: str = DEFAULT_TEST_URL,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    timeout: int = DEFAULT_NODE_TIMEOUT_SECONDS,
) -> tuple[float | None, int | None, str | None]:
    start = time.time()
    cmd = [
        "curl",
        "-x",
        proxy_url,
        "-L",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "--connect-timeout",
        str(connect_timeout),
        "--max-time",
        str(timeout),
        test_url,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
    except subprocess.TimeoutExpired:
        return None, None, "timeout"
    except FileNotFoundError:
        return None, None, "curl is not installed"
    except Exception as exc:
        return None, None, str(exc)

    elapsed = (time.time() - start) * 1000
    status_text = result.stdout.strip()[-3:]
    status_code = int(status_text) if status_text.isdigit() else None
    if result.returncode == 0 and status_code and 200 <= status_code < 400:
        return elapsed, status_code, None

    error = result.stderr.strip() or f"curl returned {result.returncode}"
    if status_code:
        error = f"{error}; http_status={status_code}" if error else f"http_status={status_code}"
    return None, status_code, error


def test_node(node: ProxyNode, *, test_url: str = DEFAULT_TEST_URL) -> TestResult:
    proxy_url = build_proxy_url(node)
    latency, status_code, error = test_latency(proxy_url, test_url=test_url)
    return TestResult(
        name=node.name,
        proxy_url=proxy_url,
        latency=latency,
        status_code=status_code,
        error=error,
        success=latency is not None,
    )


def run_tests(
    proxies: list[ProxyNode],
    *,
    max_threads: int = DEFAULT_MAX_THREADS,
    test_url: str = DEFAULT_TEST_URL,
) -> list[TestResult]:
    results: list[TestResult] = []
    workers = max(1, min(max_threads, len(proxies)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(test_node, node, test_url=test_url): node for node in proxies}
        for future in as_completed(future_map):
            node = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                result = TestResult(name=node.name, proxy_url=build_proxy_url(node), error=str(exc))
            results.append(result)
            status = "ok" if result.success else "fail"
            detail = f"{result.latency:.2f} ms" if result.success and result.latency else result.error
            print(f"[{status}] {result.name}: {detail}")
    return results


def print_results(results: list[TestResult]) -> None:
    print("\n" + "=" * 60)
    print(f"Tested {len(results)} proxy nodes")
    print("=" * 60)

    success_results = sorted((r for r in results if r.success), key=lambda item: item.latency or float("inf"))
    failed_results = [r for r in results if not r.success]

    if success_results:
        print("\nSuccessful nodes:")
        print(f"{'Rank':<6} {'Node':<28} {'Latency(ms)':<12} {'Status':<8}")
        print("-" * 60)
        for idx, result in enumerate(success_results, 1):
            latency = f"{result.latency:.2f}" if result.latency is not None else "N/A"
            status = str(result.status_code or "")
            print(f"{idx:<6} {result.name:<28} {latency:<12} {status:<8}")
        best = success_results[0]
        print(f"\nBest node: {best.name} - {best.latency:.2f} ms")

    if failed_results:
        print(f"\nFailed nodes: {len(failed_results)}")
        for result in failed_results[:20]:
            print(f"  {result.name}: {result.error}")
        if len(failed_results) > 20:
            print(f"  ... {len(failed_results) - 20} more failures")


def update_proxy_config(
    proxy_url: str,
    node_name: str,
    *,
    latency_ms: float | None = None,
    test_url: str = DEFAULT_TEST_URL,
    config_path: Path = SKILL_CONFIG_PATH,
) -> None:
    config = read_json_config(config_path)
    config["proxy"] = proxy_url
    config["proxy_node"] = node_name
    config["proxy_latency_ms"] = round(latency_ms, 2) if latency_ms is not None else None
    config["proxy_test_url"] = test_url
    config["proxy_updated_at"] = now_utc_iso()
    write_json_atomic(config_path, config)
    print(f"Updated proxy config: {node_name} ({mask_proxy_url(proxy_url)})")


def get_best_proxy_and_update_config(
    max_threads: int = DEFAULT_MAX_THREADS,
    *,
    update_subscription: bool = True,
    yml_file: Path = DEFAULT_YML_FILE,
    test_url: str = DEFAULT_TEST_URL,
) -> tuple[ProxyNode | None, str | None]:
    if update_subscription:
        update_subscription_config(yml_file=yml_file)

    proxies = load_proxies_from_yml(yml_file)
    if not proxies:
        print("No proxy nodes found")
        return None, None

    print(f"Loaded {len(proxies)} proxy nodes from {yml_file}")
    print(f"Testing Google API through proxies with {max_threads} workers...")
    results = run_tests(proxies, max_threads=max_threads, test_url=test_url)
    print_results(results)

    success_results = sorted((r for r in results if r.success), key=lambda item: item.latency or float("inf"))
    if not success_results:
        print("All proxy nodes failed")
        return None, None

    best_result = success_results[0]
    best_node = next((node for node in proxies if node.name == best_result.name), None)
    if best_node is None:
        return None, None

    update_proxy_config(
        best_result.proxy_url,
        best_node.name,
        latency_ms=best_result.latency,
        test_url=test_url,
    )
    return best_node, best_result.proxy_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh ghelper proxy config for Google API access.")
    parser.add_argument("--max-threads", type=int, default=DEFAULT_MAX_THREADS)
    parser.add_argument("--no-update-subscription", action="store_true")
    parser.add_argument("--yml-file", type=Path, default=DEFAULT_YML_FILE)
    parser.add_argument("--test-url", default=DEFAULT_TEST_URL)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    node, proxy = get_best_proxy_and_update_config(
        max_threads=args.max_threads,
        update_subscription=not args.no_update_subscription,
        yml_file=args.yml_file,
        test_url=args.test_url,
    )
    raise SystemExit(0 if node and proxy else 1)

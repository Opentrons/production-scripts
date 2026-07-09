from __future__ import annotations

import argparse
import errno
import posixpath
import shlex
import stat
import time
from pathlib import Path

import paramiko

from setting import PUSH_REMOTE_HOST


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_REMOTE_BACKEND = "/opt/data-handler/backend"
DEFAULT_REMOTE_HOST = PUSH_REMOTE_HOST
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = "root"
DEFAULT_KEY_FILE = ""
DEFAULT_CONNECT_TIMEOUT = 60
DEFAULT_CONNECT_RETRIES = 3
DEFAULT_CONNECT_RETRY_DELAY = 5

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "auth",
    "datas",
    "logs",
    "node_modules",
    "tests",
}
SKIP_FILES = {
    ".DS_Store",
}
SKIP_SUFFIXES = {
    ".log",
    ".pyc",
    ".pyo",
}
PRESERVE_REMOTE_NAMES = {
    ".venv",
}
REMOTE_SERVICE_NAME = "data-handler"
REMOTE_PROXY_MONITOR_TIMER = "data-handler-proxy-monitor.timer"
ROBOT_KEY_PATH = "/root/robot_key"
PROTECTED_REMOTE_PATHS = {
    "/",
    "/bin",
    "/boot",
    "/data",
    "/dev",
    "/etc",
    "/home",
    "/lib",
    "/lib64",
    "/opt",
    "/opt/data-handler",
    "/root",
    "/tmp",
    "/usr",
    "/var",
}


def validate_remote_backend_path(remote_backend: str) -> str:
    normalized = posixpath.normpath(remote_backend)
    if not normalized.startswith("/"):
        raise ValueError(f"Remote backend path must be absolute: {remote_backend}")
    if normalized in PROTECTED_REMOTE_PATHS:
        raise ValueError(f"Refusing to clear protected remote path: {normalized}")
    if posixpath.basename(normalized) != "backend":
        raise ValueError(f"Refusing to clear remote path that is not named backend: {normalized}")
    return normalized


def is_missing_path_error(exc: OSError) -> bool:
    return isinstance(exc, FileNotFoundError) or getattr(exc, "errno", None) == errno.ENOENT


def should_skip(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return True
    if path.name in SKIP_DIRS and path.is_dir():
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    if "tests/reports" in path.as_posix():
        return True
    return False


def connect_ssh_once(host: str, username: str, password: str, key_file: str | None, timeout: int):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if key_file:
        try:
            client.connect(host, username=username, key_filename=key_file, timeout=timeout)
            print("Connected using SSH key authentication")
            return client
        except Exception as exc:
            print(f"SSH key authentication failed: {exc}. Trying password authentication.")

    client.connect(host, username=username, password=password, timeout=timeout)
    print("Connected using password authentication")
    return client


def connect_ssh(
    host: str,
    username: str,
    password: str,
    key_file: str | None,
    timeout: int,
    retries: int,
    retry_delay: int,
):
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            print(f"Connecting to {host} via SSH, attempt {attempt}/{retries}...")
            return connect_ssh_once(host, username, password, key_file, timeout)
        except Exception as exc:
            last_exc = exc
            print(f"SSH connection attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                time.sleep(retry_delay)

    raise last_exc or ConnectionError(f"Failed to connect to {host}")


def ensure_remote_dir(sftp, remote_dir: str) -> None:
    parts = [part for part in remote_dir.split("/") if part]
    current = "/" if remote_dir.startswith("/") else "."
    for part in parts:
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except OSError as exc:
            if not is_missing_path_error(exc):
                raise
            sftp.mkdir(current)
            print(f"Created remote directory: {current}")


def remove_remote_path(sftp, remote_path: str, attr=None) -> tuple[int, int]:
    if attr is None:
        attr = sftp.stat(remote_path)

    if stat.S_ISDIR(attr.st_mode):
        removed_files = 0
        removed_dirs = 0
        for child_attr in sftp.listdir_attr(remote_path):
            child_path = posixpath.join(remote_path, child_attr.filename)
            child_files, child_dirs = remove_remote_path(sftp, child_path, child_attr)
            removed_files += child_files
            removed_dirs += child_dirs
        sftp.rmdir(remote_path)
        return removed_files, removed_dirs + 1

    sftp.remove(remote_path)
    return 1, 0


def clear_remote_dir(sftp, remote_backend: str) -> tuple[int, int]:
    remote_backend = validate_remote_backend_path(remote_backend)
    try:
        sftp.stat(remote_backend)
    except OSError as exc:
        if not is_missing_path_error(exc):
            raise
        ensure_remote_dir(sftp, remote_backend)
        return 0, 0

    removed_files = 0
    removed_dirs = 0
    preserved_items = 0
    print(f"Clearing remote backend directory: {remote_backend}")
    for attr in sftp.listdir_attr(remote_backend):
        if attr.filename in PRESERVE_REMOTE_NAMES:
            preserved_items += 1
            print(f"Preserving remote item: {attr.filename}")
            continue

        remote_path = posixpath.join(remote_backend, attr.filename)
        child_files, child_dirs = remove_remote_path(sftp, remote_path, attr)
        removed_files += child_files
        removed_dirs += child_dirs
    print(
        f"Cleared remote files: {removed_files}, "
        f"directories: {removed_dirs}, preserved: {preserved_items}"
    )
    return removed_files, removed_dirs


def upload_backend(sftp, local_backend: Path, remote_backend: str) -> tuple[int, int]:
    uploaded_files = 0
    skipped_items = 0

    ensure_remote_dir(sftp, remote_backend)
    for local_path in sorted(local_backend.rglob("*")):
        relative_path = local_path.relative_to(local_backend)
        if any(part in SKIP_DIRS for part in relative_path.parts):
            skipped_items += 1
            continue
        if should_skip(local_path):
            skipped_items += 1
            continue

        remote_path = posixpath.join(remote_backend, relative_path.as_posix())
        if local_path.is_dir():
            ensure_remote_dir(sftp, remote_path)
            continue

        ensure_remote_dir(sftp, posixpath.dirname(remote_path))
        print(f"Uploading: {relative_path}")
        sftp.put(str(local_path), remote_path)
        uploaded_files += 1

    return uploaded_files, skipped_items


def run_remote_command(client, command: str, *, timeout: int = 300) -> int:
    print(f"\n$ {command}")
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    channel = stdout.channel

    while not channel.exit_status_ready():
        if channel.recv_ready():
            print(channel.recv(4096).decode("utf-8", errors="replace"), end="")
        if channel.recv_stderr_ready():
            print(channel.recv_stderr(4096).decode("utf-8", errors="replace"), end="")
        time.sleep(0.1)

    while channel.recv_ready():
        print(channel.recv(4096).decode("utf-8", errors="replace"), end="")
    while channel.recv_stderr_ready():
        print(channel.recv_stderr(4096).decode("utf-8", errors="replace"), end="")

    exit_code = channel.recv_exit_status()
    print(f"exit code: {exit_code}")
    return exit_code


def build_remote_deploy_command(remote_backend: str) -> str:
    remote_backend_arg = shlex.quote(remote_backend)
    return (
        f"cd {remote_backend_arg} && "
        "chmod +x deploy.sh && "
        'if [ "$(id -u)" -eq 0 ]; then '
        "bash ./deploy.sh; "
        "else "
        "sudo -n bash ./deploy.sh; "
        "fi"
    )


def build_stop_services_command() -> str:
    return (
        f"systemctl stop {REMOTE_SERVICE_NAME} 2>/dev/null || true; "
        f"systemctl stop {REMOTE_PROXY_MONITOR_TIMER} 2>/dev/null || true; "
        "echo 'Stopped remote services before upload.'"
    )


def build_start_services_command() -> str:
    return (
        f"systemctl start {REMOTE_SERVICE_NAME} 2>/dev/null || true; "
        f"systemctl start {REMOTE_PROXY_MONITOR_TIMER} 2>/dev/null || true; "
        "echo 'Started remote services after upload.'"
    )


def build_fix_robot_key_command() -> str:
    key_path = shlex.quote(ROBOT_KEY_PATH)
    return (
        f"if [ -f {key_path} ]; then "
        f"chmod 600 {key_path}; "
        f"chown root:root {key_path}; "
        "echo 'robot_key permissions:'; "
        f"ls -la {key_path}; "
        "else "
        f"echo 'Warning: {ROBOT_KEY_PATH} not found; skipped permission fix.'; "
        "fi"
    )


def deploy_backend(
    *,
    host: str,
    username: str,
    password: str,
    key_file: str | None,
    local_backend: Path,
    remote_backend: str,
    timeout: int,
    connect_retries: int,
    connect_retry_delay: int,
    run_deploy: bool,
    clean_remote: bool,
) -> bool:
    if not local_backend.is_dir():
        raise FileNotFoundError(f"Local backend directory not found: {local_backend}")

    remote_backend = validate_remote_backend_path(remote_backend)
    started_at = time.time()
    print(f"Uploading backend from {local_backend} to {host}:{remote_backend}")
    client = connect_ssh(
        host,
        username,
        password,
        key_file,
        timeout,
        connect_retries,
        connect_retry_delay,
    )
    try:
        print("Stopping remote services before upload...")
        run_remote_command(client, build_stop_services_command(), timeout=120)

        sftp = client.open_sftp()
        try:
            if clean_remote:
                clear_remote_dir(sftp, remote_backend)
            uploaded_files, skipped_items = upload_backend(sftp, local_backend, remote_backend)
        finally:
            sftp.close()

        print(f"\nUploaded files: {uploaded_files}")
        print(f"Skipped items: {skipped_items}")

        ok = True
        if run_deploy:
            ok = run_remote_command(
                client,
                build_remote_deploy_command(remote_backend),
                timeout=1800,
            ) == 0 and ok
        else:
            print("Starting remote services after upload...")
            ok = run_remote_command(client, build_start_services_command(), timeout=120) == 0 and ok

        print("Fixing robot_key permissions...")
        ok = run_remote_command(client, build_fix_robot_key_command(), timeout=60) == 0 and ok

        elapsed = time.time() - started_at
        print(f"\nBackend update completed in {elapsed:.2f}s")
        return ok
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload backend code to the data-handler server.")
    parser.add_argument("--host", default=DEFAULT_REMOTE_HOST, help="Remote server IP or hostname.")
    parser.add_argument("--username", "-u", default=DEFAULT_USERNAME, help="SSH username.")
    parser.add_argument("--password", "-p", default=None, help="SSH password. Prompted when omitted.")
    parser.add_argument("--key-file", default=DEFAULT_KEY_FILE, help="SSH private key path. Use '' to disable.")
    parser.add_argument("--local-backend", default=str(BACKEND_DIR), help="Local backend directory.")
    parser.add_argument("--remote-backend", default=DEFAULT_REMOTE_BACKEND, help="Remote backend directory.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_CONNECT_TIMEOUT, help="SSH connection timeout in seconds.")
    parser.add_argument("--connect-retries", type=int, default=DEFAULT_CONNECT_RETRIES, help="SSH connection retries.")
    parser.add_argument(
        "--connect-retry-delay",
        type=int,
        default=DEFAULT_CONNECT_RETRY_DELAY,
        help="Seconds to wait between SSH connection retries.",
    )
    parser.add_argument("--no-clean-remote", action="store_true", help="Skip clearing remote backend before upload.")
    parser.add_argument("--no-deploy", action="store_true", help="Skip running remote deploy.sh after upload.")
    parser.add_argument("--no-uv-sync", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-restart", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password
    if password is None:
        entered = input(f"Enter password (default: {DEFAULT_PASSWORD}): ")
        password = entered or DEFAULT_PASSWORD

    key_file = str(Path(args.key_file).expanduser()) if args.key_file else None
    ok = deploy_backend(
        host=args.host,
        username=args.username,
        password=password,
        key_file=key_file,
        local_backend=Path(args.local_backend).expanduser().resolve(),
        remote_backend=args.remote_backend.rstrip("/"),
        timeout=args.timeout,
        connect_retries=args.connect_retries,
        connect_retry_delay=args.connect_retry_delay,
        run_deploy=not (args.no_deploy or args.no_uv_sync or args.no_restart),
        clean_remote=not args.no_clean_remote,
    )
    print(f"Upload result: {'success' if ok else 'failed'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

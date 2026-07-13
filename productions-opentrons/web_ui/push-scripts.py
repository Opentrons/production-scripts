from __future__ import annotations

import argparse
import errno
import posixpath
import shlex
import stat
import sys
import time
from pathlib import Path

import paramiko


WEB_UI_DIR = Path(__file__).resolve().parent
BACKEND_DIR = WEB_UI_DIR.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from setting import PUSH_REMOTE_HOST

DEFAULT_LOCAL_DIST = WEB_UI_DIR / "dist"
DEFAULT_REMOTE_WEB_UI = "/opt/data-handler/web_ui"
DEFAULT_REMOTE_HOST = PUSH_REMOTE_HOST
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = "root"
DEFAULT_KEY_FILE = ""
DEFAULT_CONNECT_TIMEOUT = 60
DEFAULT_CONNECT_RETRIES = 3
DEFAULT_CONNECT_RETRY_DELAY = 5

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


def validate_remote_web_ui_path(remote_web_ui: str) -> str:
    normalized = posixpath.normpath(remote_web_ui)
    if not normalized.startswith("/"):
        raise ValueError(f"Remote web_ui path must be absolute: {remote_web_ui}")
    if normalized in PROTECTED_REMOTE_PATHS:
        raise ValueError(f"Refusing to clear protected remote path: {normalized}")
    if posixpath.basename(normalized) != "web_ui":
        raise ValueError(f"Refusing to deploy to remote path that is not named web_ui: {normalized}")
    return normalized


def is_missing_path_error(exc: OSError) -> bool:
    return isinstance(exc, FileNotFoundError) or getattr(exc, "errno", None) == errno.ENOENT


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


def clear_remote_dir(sftp, remote_dir: str) -> tuple[int, int]:
    try:
        attr = sftp.stat(remote_dir)
    except OSError as exc:
        if not is_missing_path_error(exc):
            raise
        ensure_remote_dir(sftp, remote_dir)
        return 0, 0

    removed_files, removed_dirs = remove_remote_path(sftp, remote_dir, attr)
    ensure_remote_dir(sftp, remote_dir)
    return removed_files, removed_dirs


def upload_directory(sftp, local_dir: Path, remote_dir: str) -> int:
    uploaded_files = 0
    ensure_remote_dir(sftp, remote_dir)

    for local_path in sorted(local_dir.rglob("*")):
        relative_path = local_path.relative_to(local_dir)
        remote_path = posixpath.join(remote_dir, relative_path.as_posix())
        if local_path.is_dir():
            ensure_remote_dir(sftp, remote_path)
            continue

        ensure_remote_dir(sftp, posixpath.dirname(remote_path))
        print(f"Uploading dist: {relative_path}")
        sftp.put(str(local_path), remote_path)
        uploaded_files += 1

    return uploaded_files


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


def build_remote_deploy_command(remote_web_ui: str) -> str:
    remote_web_ui_arg = shlex.quote(remote_web_ui)
    return (
        f"cd {remote_web_ui_arg} && "
        "chmod +x deploy.sh && "
        'if [ "$(id -u)" -eq 0 ]; then '
        "bash ./deploy.sh; "
        "else "
        "sudo -n bash ./deploy.sh; "
        "fi"
    )


def deploy_web_ui(
    *,
    host: str,
    username: str,
    password: str,
    key_file: str | None,
    local_dist: Path,
    remote_web_ui: str,
    timeout: int,
    connect_retries: int,
    connect_retry_delay: int,
    clean_remote_dist: bool,
    run_deploy: bool,
) -> bool:
    if not local_dist.is_dir():
        raise FileNotFoundError(f"Local dist directory not found: {local_dist}")
    if not (local_dist / "index.html").is_file():
        raise FileNotFoundError(f"Local dist index.html not found: {local_dist / 'index.html'}")

    remote_web_ui = validate_remote_web_ui_path(remote_web_ui)
    remote_dist = posixpath.join(remote_web_ui, "dist")
    started_at = time.time()
    print(f"Uploading web_ui dist from {local_dist} to {host}:{remote_dist}")

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
        sftp = client.open_sftp()
        try:
            ensure_remote_dir(sftp, remote_web_ui)
            if clean_remote_dist:
                removed_files, removed_dirs = clear_remote_dir(sftp, remote_dist)
                print(f"Cleared remote dist files: {removed_files}, directories: {removed_dirs}")

            uploaded_files = upload_directory(sftp, local_dist, remote_dist)
            deploy_script = WEB_UI_DIR / "deploy.sh"
            if not deploy_script.is_file():
                raise FileNotFoundError(f"deploy.sh not found: {deploy_script}")
            remote_deploy_script = posixpath.join(remote_web_ui, "deploy.sh")
            print("Uploading deploy.sh")
            sftp.put(str(deploy_script), remote_deploy_script)
        finally:
            sftp.close()

        print(f"\nUploaded dist files: {uploaded_files}")
        ok = True
        if run_deploy:
            ok = run_remote_command(
                client,
                build_remote_deploy_command(remote_web_ui),
                timeout=600,
            ) == 0 and ok

        elapsed = time.time() - started_at
        print(f"\nweb_ui update completed in {elapsed:.2f}s")
        return ok
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload web_ui dist to the data-handler server.")
    parser.add_argument("--host", default=DEFAULT_REMOTE_HOST, help="Remote server IP or hostname.")
    parser.add_argument("--username", "-u", default=DEFAULT_USERNAME, help="SSH username.")
    parser.add_argument("--password", "-p", default=None, help="SSH password. Prompted when omitted.")
    parser.add_argument("--key-file", default=DEFAULT_KEY_FILE, help="SSH private key path. Use '' to disable.")
    parser.add_argument("--local-dist", default=str(DEFAULT_LOCAL_DIST), help="Local dist directory.")
    parser.add_argument("--remote-web-ui", default=DEFAULT_REMOTE_WEB_UI, help="Remote web_ui directory.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_CONNECT_TIMEOUT, help="SSH connection timeout in seconds.")
    parser.add_argument("--connect-retries", type=int, default=DEFAULT_CONNECT_RETRIES, help="SSH connection retries.")
    parser.add_argument(
        "--connect-retry-delay",
        type=int,
        default=DEFAULT_CONNECT_RETRY_DELAY,
        help="Seconds to wait between SSH connection retries.",
    )
    parser.add_argument("--no-clean-remote", action="store_true", help="Skip clearing remote dist before upload.")
    parser.add_argument("--no-deploy", action="store_true", help="Skip running remote deploy.sh after upload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password
    if password is None:
        entered = input(f"Enter password (default: {DEFAULT_PASSWORD}): ")
        password = entered or DEFAULT_PASSWORD

    key_file = str(Path(args.key_file).expanduser()) if args.key_file else None
    ok = deploy_web_ui(
        host=args.host,
        username=args.username,
        password=password,
        key_file=key_file,
        local_dist=Path(args.local_dist).expanduser().resolve(),
        remote_web_ui=args.remote_web_ui.rstrip("/"),
        timeout=args.timeout,
        connect_retries=args.connect_retries,
        connect_retry_delay=args.connect_retry_delay,
        clean_remote_dist=not args.no_clean_remote,
        run_deploy=not args.no_deploy,
    )
    print(f"Upload result: {'success' if ok else 'failed'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import getpass
import sqlite3

from core import config
from modules.auth.service import AuthService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Production Platform login user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default="")
    parser.add_argument("--role", choices=("admin", "operator", "viewer"), default="admin")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    service = AuthService(
        db_path=config.AUTH_DB_PATH,
        jwt_secret="unused-for-user-creation".ljust(32, "-"),
        issuer=config.AUTH_JWT_ISSUER,
        audience=config.AUTH_JWT_AUDIENCE,
        access_token_minutes=config.AUTH_ACCESS_TOKEN_MINUTES,
        refresh_token_hours=config.AUTH_REFRESH_TOKEN_HOURS,
    )
    try:
        user = service.create_user(
            username=args.username,
            password=password,
            display_name=args.display_name,
            role=args.role,
        )
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Created {user.role} user: {user.username} ({user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

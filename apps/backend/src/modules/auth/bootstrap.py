"""Idempotent initial administrator creation; never resets existing passwords."""

from sqlite3 import IntegrityError

from pymongo.errors import DuplicateKeyError

ADMIN_EMAILS = (
    "Jerome.li@opentrons.com",
    "Frank.zhang@opentrons.com",
    "zane.wang@opentrons.com",
    "andy.hu@opentrons.com",
    "kevin.jiang@opentrons.com",
)


def seed_administrators(store):
    from modules.auth.service import PASSWORD_HASH
    for email in ADMIN_EMAILS:
        existing = store.get_user_by_username(email)
        if existing:
            continue
        try:
            store.create_user(username=email, display_name=email.split('@')[0], role='admin',
                              password_hash=PASSWORD_HASH.hash(email.split('@')[0]))
        except (DuplicateKeyError, IntegrityError):
            pass  # Another worker initialized the same account.

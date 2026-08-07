from __future__ import annotations

import os

import core.config as setting


TEST_CASE_DB_NAME = os.getenv("PRODUCTION_PLATFORM_TEST_CASE_DB_NAME", setting.DATA_DB_NAME)
TEST_CASE_COLLECTION_NAME = os.getenv("PRODUCTION_PLATFORM_TEST_CASE_COLLECTION", "test_cases")
TEST_CASE_CATALOG_COLLECTION_NAME = os.getenv(
    "PRODUCTION_PLATFORM_TEST_CASE_CATALOG_COLLECTION",
    "test_case_catalog",
)

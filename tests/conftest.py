"""
pytest conftest — shared fixtures for all test modules.
"""
from __future__ import annotations

import pytest

from bot.utils.regex_engine import FilenameParser


@pytest.fixture
def parser() -> FilenameParser:
    return FilenameParser()

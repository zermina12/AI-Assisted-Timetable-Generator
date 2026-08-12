"""Small reusable helpers used across the project."""

from __future__ import annotations

import logging
import re
from typing import Iterable

from src import config


def get_logger(name: str) -> logging.Logger:
    """Return a project logger configured with the shared format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def normalize_teacher(name: str) -> str:
    """Normalize an instructor name for identity comparison.

    Collapses whitespace and normalises punctuation so that ``Mr. Kamran`` and
    ``Mr.  Kamran`` (as they inconsistently appear in the workbook) compare
    equal. An empty/whitespace name returns the canonical empty string.
    """
    if not name:
        return ""
    cleaned = re.sub(r"\s+", " ", str(name).strip())
    return cleaned


def normalize_section(section: str) -> str:
    """Normalize a section identifier (strip whitespace)."""
    if not section:
        return ""
    return re.sub(r"\s+", " ", str(section).strip())


def is_lab_title(title: str) -> bool:
    """Return True when a course title denotes a laboratory course."""
    low = title.lower()
    return any(token in low for token in config.LAB_TITLE_TOKENS)


def is_lab_room(room: str) -> bool:
    """Return True when a room name follows the lab-room naming convention."""
    low = room.lower()
    return any(low.startswith(prefix) for prefix in config.LAB_ROOM_PREFIXES)


def parse_period_string(text: str) -> str | None:
    """Parse and validate a period string such as ``08:30-10:00``.

    Returns the normalized string if valid, otherwise ``None``.
    """
    m = re.fullmatch(r"(\d{2}:\d{2})-(\d{2}:\d{2})", str(text).strip())
    if not m:
        return None
    start, end = m.group(1), m.group(2)
    if not (start < end):  # start must precede end lexicographically here
        return None
    return f"{start}-{end}"


def join_lines(items: Iterable[str], sep: str = "\n") -> str:
    return sep.join(str(i) for i in items)


def parse_credit_hours(value: object) -> int | None:
    """Convert the credit-hours cell value into the number of weekly sessions.

    - Numeric ``3``  -> 3 sessions
    - ``'NC'`` / non-numeric -> 1 session (a contact hour still occurs weekly)
    - Empty/None     -> ``None`` (data unavailable, caller decides)
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        n = int(text)
        return max(1, n)  # guard against 0-CH rows
    if text.upper() in {t.upper() for t in config.NON_NUMERIC_CREDIT_VALUES}:
        return 1
    return 1  # unparseable value defaults to 1 session and is flagged later

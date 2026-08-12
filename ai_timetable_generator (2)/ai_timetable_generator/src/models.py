"""Core data models for the timetable domain.

Every model is a lightweight dataclass with type hints. A ``Session`` is the
unit of scheduling: one required teaching occurrence (e.g. "Programming
Fundamentals, BCS-1A, session 1 of 3"). Sessions are what the CP-SAT model
assigns; courses are never assigned directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Course:
    """A course requirement row extracted from a program course sheet."""

    code: str
    title: str
    section: str              # e.g. "BCS-1A/3A" (combined) or "BCS-1A"
    instructor: str           # empty string when missing/TBA
    credit_hours: int         # number of lecture sessions per week (>=1)
    program: str              # e.g. "BS(CS)"
    category: str             # e.g. "CS (Core)"
    sheet: str                # source workbook sheet name
    is_lab: bool = False      # True when the title denotes a lab course
    is_merged: bool = False   # True when instructor cell says "(merged ...)"

    @property
    def sections(self) -> list[str]:
        """Individual section identities covered by this row.

        A combined-cell value such as ``BCS-1A/3A`` means the sections
        ``BCS-1A`` and ``BCS-3A`` attend together, so both are occupied.
        """
        parts = [p.strip() for p in self.section.split("/")]
        return [p for p in parts if p]

    @property
    def course_key(self) -> str:
        return f"{self.code}|{self.title}|{self.section}"


@dataclass(frozen=True)
class Session:
    """One required teaching occurrence.

    For a 3-credit-hour course the course row expands into three Session
    objects with session numbers 1, 2, 3. Each must be scheduled exactly once.
    """

    session_id: str           # unique id, e.g. "S-0042"
    course: Course
    session_number: int       # 1-based occurrence index within the course row
    is_lab: bool

    @property
    def sections(self) -> list[str]:
        return self.course.sections

    @property
    def teacher(self) -> str:
        return self.course.instructor


@dataclass(frozen=True)
class Assignment:
    """A concrete placement of one session."""

    session: Session
    day: str                  # one of VALID_DAYS
    period: int               # period index 0-based
    room: str

    @property
    def period_label(self) -> str:
        from src import config
        return config.PERIODS[self.period]


@dataclass
class ExistingEntry:
    """One non-empty cell parsed from the existing timetable grid."""

    day: str
    room: str
    period: int
    course_short: str         # short title as written in the grid
    sections: tuple[str, ...]
    teacher: str              # short teacher name (may be empty)


@dataclass
class TimetableData:
    """Aggregated, cleaned dataset ready for modeling.

    Holds everything the constraint model and validators need.
    """

    courses: list[Course] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)
    rooms: list[str] = field(default_factory=list)
    lab_rooms: list[str] = field(default_factory=list)
    existing_entries: list[ExistingEntry] = field(default_factory=list)
    # teacher -> set of session ids that the teacher must teach
    teacher_sessions: dict[str, set[str]] = field(default_factory=dict)
    # section -> set of session ids the section must attend
    section_sessions: dict[str, set[str]] = field(default_factory=dict)

    # ---- data-quality flags filled in during validation ----
    missing_teachers: list[Course] = field(default_factory=list)
    merged_courses: list[Course] = field(default_factory=list)
    unparseable_credit_hours: list[Course] = field(default_factory=list)

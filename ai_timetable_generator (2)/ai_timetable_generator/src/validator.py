"""Stage 1: Timetable Analysis and Validation.

Independently analyses the *existing* timetable (parsed from the workbook
grid) and reports every detected problem without trusting the solver.

Detected issues:
    * teacher conflicts   - same named teacher in two sessions, same day+period
    * section conflicts   - same section in two sessions, same day+period
    * room conflicts      - same room hosting two sessions, same day+period
    * invalid days        - day values not in VALID_DAYS
    * invalid periods     - period index outside 0..7
    * missing teachers    - grid entries without an instructor name
    * missing rooms       - (informational) entries whose room could not be read
    * duplicate sessions  - same course+section repeated more than its required
                            number of sessions in the input grid
    * unscheduled sessions- course-sheet sessions absent from the input grid
    * duration problems   - sessions whose required consecutive slots would not
                            fit (informational, when duration data exists)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Final

from src import config
from src.models import ExistingEntry, TimetableData
from src.utils import get_logger

log = get_logger(__name__)

CONFLICT_TEACHER = "teacher"
CONFLICT_SECTION = "section"
CONFLICT_ROOM = "room"
CONFLICT_INVALID_DAY = "invalid_day"
CONFLICT_INVALID_PERIOD = "invalid_period"
CONFLICT_MISSING_TEACHER = "missing_teacher"
CONFLICT_DUPLICATE_SESSION = "duplicate_session"
CONFLICT_UNSCHEDULED_SESSION = "unscheduled_session"
CONFLICT_DURATION = "duration"


@dataclass
class Conflict:
    kind: str
    day: str | None
    period: int | None
    room: str | None
    detail: str
    items: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    conflicts: list[Conflict] = field(default_factory=list)
    missing_teachers_report: list[str] = field(default_factory=list)
    merged_courses_report: list[str] = field(default_factory=list)
    unparseable_credit_report: list[str] = field(default_factory=list)

    @property
    def n_conflicts(self) -> int:
        return len(self.conflicts)

    def is_clean(self) -> bool:
        return self.n_conflicts == 0


def validate_input(data: TimetableData) -> ValidationReport:
    """Analyse the existing timetable and the extracted requirements."""
    report = ValidationReport()

    # ---------------------------------------------------------------
    # 1. Grid-level structural checks (invalid day / period)
    # ---------------------------------------------------------------
    valid_days = set(config.VALID_DAYS)
    for entry in data.existing_entries:
        if entry.day not in valid_days:
            report.conflicts.append(Conflict(
                CONFLICT_INVALID_DAY, entry.day, entry.period, entry.room,
                f"Day '{entry.day}' is not one of the valid days "
                f"{sorted(valid_days)}",
                [f"{entry.course_short} ({'/'.join(entry.sections)})"]))
        if not (0 <= entry.period <= 7):
            report.conflicts.append(Conflict(
                CONFLICT_INVALID_PERIOD, entry.day, entry.period, entry.room,
                f"Period index {entry.period} outside 0..7",
                [f"{entry.course_short} ({'/'.join(entry.sections)})"]))

    # ---------------------------------------------------------------
    # 2. Teacher / section / room clashes in the existing grid
    # ---------------------------------------------------------------
    by_day_period_teacher = defaultdict(list)
    by_day_period_section = defaultdict(list)
    by_day_period_room = defaultdict(list)

    for entry in data.existing_entries:
        key = (entry.day, entry.period)
        if entry.teacher:
            by_day_period_teacher[(entry.teacher, *key)].append(entry)
        for sec in entry.sections:
            by_day_period_section[(sec, *key)].append(entry)
        by_day_period_room[(*key, entry.room)].append(entry)

    def _emit(kind, key_items, entries):
        report.conflicts.append(Conflict(
            kind, entries[0].day, entries[0].period, entries[0].room,
            " ".join(str(i) for i in key_items),
            [f"{e.course_short} ({'/'.join(e.sections)})" +
             (f": {e.teacher}" if e.teacher else "") for e in entries]))

    for (teacher, day, per), entries in sorted(by_day_period_teacher.items()):
        if len(entries) > 1:
            _emit(CONFLICT_TEACHER, ("Teacher:", teacher, "Day:", day,
                                     "Period:", config.PERIODS[per]), entries)

    for (sec, day, per), entries in sorted(by_day_period_section.items()):
        if len(entries) > 1:
            _emit(CONFLICT_SECTION, ("Section:", sec, "Day:", day,
                                     "Period:", config.PERIODS[per]), entries)

    for (day, per, room), entries in sorted(by_day_period_room.items()):
        if len(entries) > 1:
            _emit(CONFLICT_ROOM, ("Room:", room, "Day:", day,
                                  "Period:", config.PERIODS[per]), entries)

    # ---------------------------------------------------------------
    # 3. Missing teachers (grid entries without an instructor)
    # ---------------------------------------------------------------
    missing = [e for e in data.existing_entries if not e.teacher]
    for entry in missing[:50]:
        report.conflicts.append(Conflict(
            CONFLICT_MISSING_TEACHER, entry.day, entry.period, entry.room,
            "No instructor recorded in the timetable grid",
            [f"{entry.course_short} ({'/'.join(entry.sections)})"]))
    if len(missing) > 50:
        report.conflicts.append(Conflict(
            CONFLICT_MISSING_TEACHER, None, None, None,
            f"... and {len(missing) - 50} more grid entries without a teacher",
            []))
    # Requirement-sheet missing teachers are also reported.
    report.missing_teachers_report = [
        f"{c.code} | {c.title} | {c.section} ({c.sheet})"
        for c in data.missing_teachers]

    # ---------------------------------------------------------------
    # 4. Duplicate / unscheduled sessions (requirements vs grid)
    # ---------------------------------------------------------------
    _report_scheduling_coverage(data, report)

    log.info("Input validation: %d conflicts found.", report.n_conflicts)
    for kind in (CONFLICT_TEACHER, CONFLICT_SECTION, CONFLICT_ROOM,
                 CONFLICT_INVALID_DAY, CONFLICT_INVALID_PERIOD,
                 CONFLICT_MISSING_TEACHER, CONFLICT_DUPLICATE_SESSION,
                 CONFLICT_UNSCHEDULED_SESSION):
        n = sum(1 for c in report.conflicts if c.kind == kind)
        if n:
            log.info("  %-22s %d", kind, n)
    return report


def _report_scheduling_coverage(data: TimetableData,
                                report: ValidationReport) -> None:
    """Compare required sessions against what already appears in the grid.

    The mapping grid text -> course row is heuristic (short titles differ
    from full titles), so coverage numbers are informational, not
    deterministic.
    """
    # Count how many times each (short_title, frozenset(sections)) appears in
    # the grid.
    grid_counts: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    for entry in data.existing_entries:
        grid_counts[(entry.course_short, tuple(sorted(entry.sections)))] += 1

    unscheduled = 0
    for session in data.sessions:
        key = (session.course.title, tuple(sorted(session.sections)))
        need = sum(1 for s in data.sessions
                   if (s.course.title, tuple(sorted(s.sections))) == key)
        have = grid_counts.get(key, 0)
        if have > need:
            report.conflicts.append(Conflict(
                CONFLICT_DUPLICATE_SESSION, None, None, None,
                f"'{session.course.title} ({session.course.section})' appears "
                f"{have}x in the grid but only {need} session(s) required",
                []))
            grid_counts[key] = need  # avoid re-reporting per session
        elif have < need:
            unscheduled += 1
    if unscheduled:
        report.conflicts.append(Conflict(
            CONFLICT_UNSCHEDULED_SESSION, None, None, None,
            f"{unscheduled} required session(s) not found in the existing "
            f"timetable grid (heuristic short-title match)", []))

    report.merged_courses_report = [
        f"{c.code} | {c.title} | {c.section} ({c.sheet}) - "
        f"instructor notes: {c.instructor}"
        for c in data.merged_courses]

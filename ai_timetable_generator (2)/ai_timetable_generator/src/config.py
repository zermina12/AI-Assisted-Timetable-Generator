"""Central configuration for the AI-Assisted Timetable Generator.

All tunable parameters, workbook conventions, and constants live here so that
the rest of the codebase stays free of magic numbers and ad-hoc paths.
"""

from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "outputs"
INPUT_WORKBOOK: Final[Path] = DATA_DIR / "FSC_F26_TT_v1.0.2_06082026.xlsx"

OUTPUT_TIMETABLE_XLSX: Final[Path] = OUTPUT_DIR / "generated_timetable.xlsx"
OUTPUT_TIMETABLE_CSV: Final[Path] = OUTPUT_DIR / "generated_timetable.csv"
OUTPUT_CONFLICT_REPORT: Final[Path] = OUTPUT_DIR / "conflict_report.csv"
OUTPUT_VALIDATION_REPORT: Final[Path] = OUTPUT_DIR / "validation_report.txt"

# ---------------------------------------------------------------------------
# Workbook sheet conventions
# ---------------------------------------------------------------------------

# Course (requirement) sheets: one per program. Row 2 holds the column headers.
COURSE_SHEETS: Final[list[str]] = ["CS", "SE", "DS", "AI", "CY", "CI"]

# Timetable grid sheets. "Combined TT" is the master grid; the department grids
# (CS TT, ...) are subsets of it and are NOT double-counted.
GRID_SHEET: Final[str] = "Combined TT"

# Columns in course sheets (1-indexed)
COL_CODE: Final[int] = 1
COL_TITLE: Final[int] = 2
COL_SECTION: Final[int] = 3
COL_INSTRUCTOR: Final[int] = 4
COL_CREDIT_HOURS: Final[int] = 5
COL_PROGRAM: Final[int] = 6
COL_CATEGORY: Final[int] = 7

# ---------------------------------------------------------------------------
# Timetable grid layout (verified against the workbook)
# ---------------------------------------------------------------------------

# Row indices of the grid header rows inside a timetable sheet.
GRID_PERIOD_HEADER_ROW: Final[int] = 3  # "Periods" + period strings
GRID_DAYS_HEADER_ROW: Final[int] = 4    # "Days" | "Room" | sub-slot numbers

# Starting columns of the 8 periods (verified: 6,15,24,33,42,51,60,69).
PERIOD_START_COLUMNS: Final[list[int]] = [6, 15, 24, 33, 42, 51, 60, 69]

# Column indices for the meta columns in a grid sheet.
GRID_DAY_COL: Final[int] = 1
GRID_ROOM_COL: Final[int] = 2
GRID_FIRST_CONTENT_COL: Final[int] = 3

# ---------------------------------------------------------------------------
# Time model
# ---------------------------------------------------------------------------

# Human-readable period strings exactly as they appear in the workbook,
# in period index order (index 0 == first period).
PERIODS: Final[list[str]] = [
    "08:30-10:00",
    "10:00-11:30",
    "11:30-13:00",
    "13:00-14:30",
    "14:30-16:00",
    "16:00-17:30",
    "17:30-19:00",
    "19:00-20:30",
]

# Days actually present in the workbook (Mon-Sat). NOT assumed to be Mon-Fri.
VALID_DAYS: Final[list[str]] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Periods available to the solver.
#
# The workbook header lists EIGHT periods (08:30-20:30), but the existing
# timetable uses ZERO classes in the eighth period (19:00-20:30). Period 7 is
# therefore intentionally EXCLUDED: scheduling into an unused evening slot
# would be a pure quality loss, and excluding it keeps the search space
# small enough for the solver to prove OPTIMALITY (see the two-phase note in
# README.md). If the institution ever starts using 19:00-20:30, append 7 to
# this list -- and expect the solver to report FEASIBLE rather than OPTIMAL
# within the default time limit unless the limit is raised.
# Changing this list is the single knob for restricting hours (e.g. to
# [0, 1, 2, 3, 4] for a 08:30-16:00 day) -- just remember to keep
# MAX_CLASSES_PER_SLOT <= number of rooms.
ACTIVE_PERIODS: Final[list[int]] = [0, 1, 2, 3, 4, 5, 6]

# ---------------------------------------------------------------------------
# Session / credit-hour model (documented assumption)
# ---------------------------------------------------------------------------

# How the number of required weekly sessions is derived from course data:
#   lecture sessions per week = credit hours (3 CH -> 3 sessions, 2 CH -> 2,
#   1 CH -> 1)
#   lab rows                        = 1 session each
# This matches the FAST-NUCES convention where each credit hour corresponds to
# one 90-minute contact hour per week, and matches the occurrence counts of
# already-scheduled courses in the existing timetable grid.
LAB_TITLE_TOKENS: Final[list[str]] = ["lab"]

# Marker text found in the Instructor column when a course is merged with
# another program (e.g. "(merged with DS)"). Merged courses are NOT scheduled
# independently; they are covered by the other program's rows and flagged.
MERGED_INSTRUCTOR_TOKEN: Final[str] = "merged"

# Values in the credit-hours column that are not numeric. They still produce
# exactly one session per week, same as a 1-CH course.
NON_NUMERIC_CREDIT_VALUES: Final[set[str]] = {"NC"}

# ---------------------------------------------------------------------------
# Room typing (inferred from room naming conventions in the workbook)
# ---------------------------------------------------------------------------

# Lab rooms: rooms whose name begins with one of these prefixes (case-insensitive).
LAB_ROOM_PREFIXES: Final[list[str]] = ["lab-", "eng lab", "c-lab"]

# ---------------------------------------------------------------------------
# Solver tuning
# ---------------------------------------------------------------------------

# Maximum solver wall time in seconds. With all eight workbook periods
# excluded/available as configured by ACTIVE_PERIODS (period 7 intentionally
# excluded -- the real timetable uses it zero times), 60 s is enough for the
# solver to prove OPTIMALITY. Raise only if ACTIVE_PERIODS is widened.
SOLVER_TIME_LIMIT_SECONDS: Final[int] = 120

# Number of parallel workers for CP-SAT (0 = auto, uses all cores).
SOLVER_NUM_WORKERS: Final[int] = 0

# Whether to enable solver statistics logging.
SOLVER_LOG_SEARCH_PROGRESS: Final[bool] = True

# ---------------------------------------------------------------------------
# Optimization weights (soft-constraint penalties)
# ---------------------------------------------------------------------------

# Penalty for scheduling a session in a late period (index >= this value).
LATE_PERIOD_INDEX: Final[int] = 5  # 16:00-17:30 and later are "late"
PENALTY_LATE_PERIOD: Final[int] = 1

# Penalty for moving a session away from a valid pre-existing assignment.
PENALTY_CHANGED_ASSIGNMENT: Final[int] = 5

# Penalty for a day-level gap in a section's schedule (two consecutive
# scheduled periods with an idle period between them). Kept small so it never
# beats the change penalty.
PENALTY_SECTION_GAP: Final[int] = 1

# Penalty for a day-level gap in a teacher's schedule.
PENALTY_TEACHER_GAP: Final[int] = 1

# Maximum number of classes allowed in any single (day, period) slot. Must be
# <= the number of rooms so that the Phase-B room assignment can never fail.
MAX_CLASSES_PER_SLOT: Final[int] = 51

# Lab room restriction mode:
#   "hard" = lab courses may only be placed in lab rooms (hard constraint)
#   "soft" = prefer lab rooms for lab courses via penalty (default, defensible
#            because the workbook does not explicitly state room capacities)
LAB_ROOM_RESTRICTION_MODE: Final[str] = "soft"

# Penalty when a lab course is placed outside a lab room (soft mode only).
PENALTY_LAB_NOT_IN_LAB_ROOM: Final[int] = 2

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"

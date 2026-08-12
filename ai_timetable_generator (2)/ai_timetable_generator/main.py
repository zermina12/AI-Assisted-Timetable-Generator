"""AI-Assisted Timetable Generator - main entry point.

Workflow:
    Excel input
        -> data inspection & loading
        -> preprocessing (normalization, session expansion)
        -> Stage 1: existing-timetable validation & conflict report
        -> session creation
        -> CP-SAT model build (hard constraints + soft objectives)
        -> solver run
        -> Stage 2: independent post-solution validation
        -> export (xlsx, csv, conflict report, validation report)
"""

from __future__ import annotations

import logging
import sys

from src import config

# Exit codes: 0 success, 1 validation failure (timetable exists but fails
# checks), 2 infeasible (no timetable could be produced), 3 environment /
# input error (missing workbook, bad data), 4 unexpected runtime/export
# failure.
EXIT_INPUT_ERROR = 3
EXIT_RUNTIME_ERROR = 4
from src.data_loader import load_timetable_data
from src.exporter import export_all
from src.postvalidator import validate_solution
from src.solver import TimetableSolver
from src.validator import validate_input
from src.utils import get_logger


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT,
                        force=True)
    log = get_logger("main")

    log.info("=== AI-Assisted Timetable Generator ===")
    log.info("Input workbook: %s", config.INPUT_WORKBOOK)

    # ------------------------------------------------------------------
    # 1. Data inspection, loading & preprocessing
    # ------------------------------------------------------------------
    try:
        data = load_timetable_data()
    except FileNotFoundError as exc:
        log.error("Input workbook not found: %s\n"
                  "Place the workbook at %s and re-run.",
                  exc.filename, config.INPUT_WORKBOOK)
        return EXIT_INPUT_ERROR
    except (ValueError, KeyError) as exc:
        # Structural problems in the workbook (missing sheets, unexpected
        # header layout, unparseable values) surface as ValueError/KeyError
        # from the loader.
        log.error("Failed to load data from the workbook: %s", exc)
        return EXIT_INPUT_ERROR
    except OSError as exc:
        log.error("Could not read the workbook: %s", exc)
        return EXIT_INPUT_ERROR

    # ------------------------------------------------------------------
    # 2. Stage 1: analyse & validate the EXISTING timetable
    # ------------------------------------------------------------------
    log.info("--- Stage 1: input analysis & validation ---")
    input_report = validate_input(data)
    log.info("Input conflicts: %d. Missing teachers (course sheet): %d. "
             "Merged courses (not scheduled independently): %d.",
             input_report.n_conflicts,
             len(input_report.missing_teachers_report),
             len(input_report.merged_courses_report))

    # ------------------------------------------------------------------
    # 3. Stage 2: build model, solve, validate
    # ------------------------------------------------------------------
    log.info("--- Stage 2: CP-SAT generation / repair ---")
    log.info("Sessions to schedule: %d | Days: %d | Periods: %d | Rooms: %d",
             len(data.sessions), len(config.VALID_DAYS),
             len(config.ACTIVE_PERIODS), len(data.rooms))

    try:
        solver = TimetableSolver(data)
        result = solver.solve()
    except Exception:  # pragma: no cover - defensive
        log.exception("Unexpected runtime error during model build or solve")
        return EXIT_RUNTIME_ERROR
    log.info(result.message)

    if not result.is_valid:
        log.error("No timetable could be produced. "
                  "Review the infeasibility diagnostics above.")
        # Still export the conflict report so the failure is documented.
        from src.postvalidator import PostValidationReport
        export_all(data, result, input_report, PostValidationReport())
        return 2

    log.info("--- Independent post-solution validation ---")
    post_report = validate_solution(data, result.assignments)
    log.info(post_report.to_text())

    # ------------------------------------------------------------------
    # 4. Export outputs
    # ------------------------------------------------------------------
    log.info("--- Exporting outputs ---")
    try:
        export_all(data, result, input_report, post_report)
    except OSError as exc:
        log.error("Export failed: could not write outputs: %s", exc)
        return EXIT_RUNTIME_ERROR
    except Exception:  # pragma: no cover - defensive
        log.exception("Unexpected failure while exporting outputs")
        return EXIT_RUNTIME_ERROR

    log.info("=== Done. Outputs in %s ===", config.OUTPUT_DIR)
    return 0 if post_report.passed else 1


if __name__ == "__main__":
    sys.exit(main())

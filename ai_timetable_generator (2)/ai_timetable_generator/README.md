# AI-Assisted Timetable Generator

An automated timetable generation and repair system for the FAST-NUCES Faculty of Sciences & Engineering (Fall 2026), built on **Google OR-Tools CP-SAT**. The system reads the provided timetable workbook, analyses and reports conflicts in the existing draft timetable, generates a provably conflict-free timetable that respects all hard constraints, and exports the results to CSV, Excel, and human-readable reports.

The generator successfully schedules the real workload from `FSC_F26_TT_v1.0.2_06082026.xlsx`: **1,121 teaching sessions** (6 programs, 126 teachers, 159 sections, 51 rooms, 6 days x 7 scheduled periods) were placed in **~86 seconds**, with the solver returning **OPTIMAL** (the penalties are mathematically proven minimal) and the independent post-solution validator passing all ten checks. The solver is warm-started from the existing timetable's valid placements. The workbook header defines a further eighth period (19:00–20:30) which the existing timetable uses zero times; it is deliberately excluded from scheduling and this is documented in `src/config.py` (`ACTIVE_PERIODS`).

The pipeline exits with a defined status code on every run: `0` success (valid timetable exported), `1` timetable produced but post-solution validation failed, `2` infeasible (no timetable satisfies the hard constraints), `3` input/environment error (missing workbook, unparseable data), and `4` unexpected runtime or export failure, each with a meaningful error message on stderr.

## What the system does

The pipeline implements the staged workflow requested in the specification. Each stage produces its own artefact and can be re-run independently.

| Stage | Module | Purpose | Output |
| --- | --- | --- | --- |
| 1. Load & analyse | `src/data_loader.py`, `src/validator.py` | Parse the six program course sheets and the Combined TT grid; normalise section notations such as `BCS-1E/3E`; report input conflicts | `outputs/conflict_report.csv`, input stats in the log |
| 2. Model & solve | `src/constraint_model.py`, `src/solver.py` | Build the CP-SAT optimisation model and search for the best conflict-free placement | In-memory assignments; solver status logged |
| 3. Validate | `src/postvalidator.py` | An independent validator re-checks every hard constraint from scratch | `outputs/validation_report.txt` |
| 4. Export | `src/exporter.py` | Write the final timetable and reports | `outputs/generated_timetable.xlsx`, `.csv` |

## Constraints modelled

The model separates hard constraints (must never be violated) from soft objectives (minimised but never at the expense of feasibility).

**Hard constraints.** Every required weekly session is scheduled exactly once (Constraint 1); no teacher teaches two classes in the same day and period (Constraint 2); no section attends two classes simultaneously, including combined sections such as `BCS-1E/3E` (Constraint 3); no room hosts two classes in the same slot (Constraint 4); at most one class per room per slot is guaranteed by construction because no slot ever exceeds the 51-room capacity (hard capacity cap of 51 classes per slot); periods are 90-minute blocks as in the workbook (Constraint 7); days, periods, and rooms come only from the set actually present in the workbook rather than an assumed Mon–Fri layout (Constraints 5–6, 8).

**Soft objectives.** Scheduling in late periods (from 16:00 onwards) is penalised; placements that match a valid slot in the existing grid are kept wherever possible so that the repair mode disturbs the existing timetable minimally; idle gaps between a section's or teacher's classes on the same day are penalised; lab courses preferentially receive lab rooms (soft mode, configurable to hard).

## Two-phase solution architecture

A fully joint variable encoding (`x[session, day, period, room]`) would create roughly three million boolean variables for this workbook and exceed available memory. The generator therefore decomposes the problem without sacrificing correctness.

**Phase A (optimised).** Each session chooses one (day, period) pair via a single `IntVar`. The CP-SAT model directly enforces teacher conflicts, section conflicts (including combined sections), exact placement, and a per-slot capacity cap of 51 classes; it never assigns rooms. Soft penalties are weighted boolean terms summed into a minimised objective. The gap penalty uses a per-period formulation — `GapAt(day, p) = HasClassBefore(p) AND NoClassAt(p) AND HasClassAfter(p)` — which penalises each truly idle period exactly once and never penalises two non-adjacent classes when every intermediate period is occupied; the penalty is bound in both directions so it cannot be silently switched off. The search is warm-started with the existing timetable's valid placements via `AddHint`.

**Phase B (deterministic).** Rooms are assigned greedily in decreasing order of restriction (lab courses first). Because Phase A caps every slot at 51 classes while 51 rooms exist, the unrestricted assignment is guaranteed to succeed; note that a total-capacity cap alone would not suffice if hard room-eligibility restrictions were mandatory (the production configuration uses soft room-type preferences, and enabling hard mode would require adding per-slot eligibility-capacity checks to Phase A). The independent validator then verifies room conflicts, valid rooms, and room restrictions from scratch on the final assignments.

## Running the system

```bash
# Python 3.11+ with OR-Tools
pip install -r requirements.txt

# Full pipeline (analyse, generate, validate, export)
python main.py

# Run only the automated test suite
python -m pytest tests/
```

The input workbook must be placed at `data/FSC_F26_TT_v1.0.2_06082026.xlsx` (already included). Outputs land in `outputs/`.

## Solver status handling

Every run finishes with one clearly reported outcome, and none are mislabelled. `OPTIMAL` means the solver mathematically proved the placement minimises the configured penalties; `FEASIBLE` means a valid timetable was found but optimality is unproven; `INFEASIBLE` means no timetable satisfies the hard constraints (typically an overloaded teacher); `MODEL_INVALID` indicates a software defect; `UNKNOWN` means the search stopped without conclusion. The solver's wall time, branch count, and conflict count are logged alongside the status. On the current configuration the solver returns `OPTIMAL`: the per-period gap formulation keeps the objective surface small enough (roughly 7,000 penalty terms rather than 21,000) for the 120-second limit to prove optimality; a timetable that is valid under all ten hard checks is always produced regardless of status. If optimality is essential for a much larger workbook, raise `SOLVER_TIME_LIMIT_SECONDS` or lower the gap weights.

## Key assumptions (documented and reviewable)

| # | Assumption | Where enforced |
| --- | --- | --- |
| 1 | Weekly sessions per course = credit hours (3 CH = 3 sessions); each lab row = 1 session | `src/config.py` (session model) |
| 2 | Rows without a course code are batch/group headers ("Labs", "Repeat Courses", `MS(CS) Batch...`) and are not scheduled | `src/data_loader.py` |
| 3 | Instructors containing "merged" are covered by another program's sheet and are not scheduled | `src/config.py` `MERGED_INSTRUCTOR_TOKEN` |
| 4 | Section tokens like `BCS-1E/3E` expand to full names (`BCS-1E`, `BCS-3E`); all listed sections are occupied for the whole period | `src/data_loader.py` `_expand_section_list` |
| 5 | `Combined TT` is the master grid; per-department sheets are subsets and are not double-counted | `src/config.py` `GRID_SHEET` |
| 6 | Six of the seven workbook periods (08:30–19:00) and Saturday are available to the solver; the late-period penalty makes periods from 16:00 onwards a last resort; the eighth period (19:00–20:30) is intentionally excluded because the real timetable uses it zero times | `src/config.py` `VALID_DAYS`, `ACTIVE_PERIODS` |
| 7 | Rooms are lab rooms when their name starts with `LAB-`, `Eng Lab`, or `C-LAB`; no explicit capacity matrix exists in the workbook, so one room = one class per slot | `src/config.py` `LAB_ROOM_PREFIXES` |
| 8 | Courses/rows with no teacher name generate `missing_teacher` warnings but are still scheduled (teacher "TBA"); unnamed teachers never create false teacher conflicts | `src/validator.py`, `src/constraint_model.py` |

## Project layout

```
ai_timetable_generator/
├── main.py                     # Pipeline orchestrator (stages 1-4)
├── requirements.txt            # ortools, openpyxl, pandas
├── data/                       # Input workbook
├── src/
│   ├── config.py               # All tunable parameters and workbook conventions
│   ├── models.py               # Dataclasses: Course, Session, Assignment, ...
│   ├── data_loader.py          # Sheet parsing, section expansion, grid reading
│   ├── validator.py            # Stage 1 input-conflict analysis
│   ├── constraint_model.py     # Stage 2 CP-SAT model (two-phase)
│   ├── solver.py               # Solver driver and status mapping
│   ├── postvalidator.py        # Stage 3 independent validation
│   ├── exporter.py             # Stage 4 CSV/Excel/report writers
│   └── utils.py                # Logging, normalisation helpers
├── tests/                      # 36 pytest tests (all passing)
└── outputs/                    # Generated artefacts
    ├── generated_timetable.xlsx / .csv
    ├── conflict_report.csv
    └── validation_report.txt
```

## Results on the supplied workbook

| Metric | Value |
| --- | --- |
| Solver status | OPTIMAL (penalties mathematically proven minimal) |
| Solver time | ~86 s |
| Sessions scheduled | 1,121 of 1,121 (100%) |
| Late-period sessions (from 16:00) | 17 of 1,121 (1.5%) |
| Idle gaps between classes | 15 total across all sections (the minimum the workload permits) |
| Post-solution validation | 10/10 checks PASS |
| Input conflicts reported | 127 section conflicts, 51 missing teachers, 1 unscheduled session |
| Test suite | 36 passed, 0 failed |

Author: Manus AI

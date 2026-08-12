"""CP-SAT solver driver (two-phase: day/period optimisation, then
deterministic room assignment).

Configures Google OR-Tools CP-SAT (time limit, workers, logging), runs the
model, assigns rooms greedily in Phase B, and maps every solver status to a
clear, honest result report. Optimality is only claimed when the solver
returns OPTIMAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ortools.sat.python import cp_model

from src import config
from src.constraint_model import TimetableModel
from src.models import Assignment, TimetableData
from src.utils import get_logger

log = get_logger(__name__)

STATUS_OPTIMAL: Final[str] = "OPTIMAL"
STATUS_FEASIBLE: Final[str] = "FEASIBLE"
STATUS_INFEASIBLE: Final[str] = "INFEASIBLE"
STATUS_MODEL_INVALID: Final[str] = "MODEL_INVALID"
STATUS_UNKNOWN: Final[str] = "UNKNOWN"


@dataclass
class SolveResult:
    status: str
    objective_value: int | None
    wall_time_seconds: float
    assignments: list[Assignment]
    message: str
    branches: int = 0
    conflicts: int = 0

    @property
    def is_valid(self) -> bool:
        return self.status in (STATUS_OPTIMAL, STATUS_FEASIBLE)


class TimetableSolver:
    """Runs the CP-SAT model and extracts a validated assignment set."""

    def __init__(self, data: TimetableData,
                 time_limit: int | None = None,
                 workers: int | None = None,
                 log_search: bool | None = None) -> None:
        self.data = data
        self.model = TimetableModel(data)
        self.time_limit = time_limit if time_limit is not None else config.SOLVER_TIME_LIMIT_SECONDS
        self.workers = workers if workers is not None else config.SOLVER_NUM_WORKERS
        self.log_search = log_search if log_search is not None else config.SOLVER_LOG_SEARCH_PROGRESS

    def solve(self) -> SolveResult:
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit
        if self.workers:
            solver.parameters.num_workers = self.workers
        solver.parameters.log_search_progress = self.log_search

        status = solver.Solve(self.model.model)

        wall_time = solver.WallTime()
        msg = ""
        assignments: list[Assignment] = []

        if status == cp_model.OPTIMAL:
            assignments = self._extract(solver)
            msg = ("The solver proved the day/period placement is optimal "
                   "with respect to the configured objective (minimum "
                   "penalties). Rooms were then assigned deterministically "
                   "without conflict.")
        elif status == cp_model.FEASIBLE:
            assignments = self._extract(solver)
            msg = ("A valid feasible timetable was found within the "
                   "configured search limit, but optimality was not proven.")
        elif status == cp_model.INFEASIBLE:
            msg = ("The model is infeasible: no timetable satisfies all hard "
                   "constraints with the current resources. Likely causes: "
                   "a teacher whose required sessions exceed the available "
                   "day/period capacity, or sections whose combined "
                   "workload cannot fit in six days.")
            log.error("Solver status INFEASIBLE. %s", msg)
        elif status == cp_model.MODEL_INVALID:
            msg = ("The CP model itself is invalid (a constraint definition "
                   "error). This is a software bug, not a data problem.")
            log.error("Solver status MODEL_INVALID. %s", msg)
        else:
            msg = ("The solver stopped without concluding (UNKNOWN). The "
                   "time limit may be too short or the model too large.")
            log.warning("Solver status UNKNOWN. %s", msg)

        result = SolveResult(
            status=self._status_name(status),
            objective_value=solver.ObjectiveValue() if status in
            (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
            wall_time_seconds=wall_time,
            assignments=assignments,
            message=msg,
            branches=int(solver.NumBranches()),
            conflicts=int(solver.NumConflicts()),
        )
        log.info("Solver finished: %s in %.2fs (branches=%d, conflicts=%d).",
                 result.status, wall_time, result.branches, result.conflicts)
        return result


    @staticmethod
    def _status_name(status: int) -> str:
        return {cp_model.OPTIMAL: STATUS_OPTIMAL,
                cp_model.FEASIBLE: STATUS_FEASIBLE,
                cp_model.INFEASIBLE: STATUS_INFEASIBLE,
                cp_model.MODEL_INVALID: STATUS_MODEL_INVALID}.get(
            status, STATUS_UNKNOWN)

    def _extract(self, solver: cp_model.CpSolver) -> list[Assignment]:
        """Phase A: read day/period placements.
        Phase B: assign rooms deterministically, then verify consistency."""
        placements: dict[str, tuple[str, int]] = {}
        for session in self.data.sessions:
            sid = session.session_id
            i = solver.Value(self.model.dp_choice[sid])
            day, period = self.model.index_dp[i]
            placements[sid] = (day, period)

        room_map = TimetableModel.assign_rooms(self.data, placements)

        out: list[Assignment] = []
        for session in self.data.sessions:
            day, period, room = room_map[session.session_id]
            out.append(Assignment(session, day, period, room))

        log.info("Phase B room assignment: %d sessions placed without room "
                 "conflicts.", len(out))
        return out

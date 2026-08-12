"""Stage 2: OR-Tools CP-SAT constraint model (two-phase decomposition).

A fully joint ``x[session, day, period, room]`` encoding creates roughly
2.6 million boolean variables for this workbook (1121 sessions x 6 days x
7 scheduled periods x 51 rooms) and exceeds the sandbox's RAM. The model therefore
decomposes the problem into two phases, both of which are verified
independently afterwards:

Phase A (CP-SAT) -- day/period placement only:
    dp_choice[s] in {0 .. 41}   -> which (day, period) pair session s takes
    Hard: every session placed exactly once; no two sessions of the same
    teacher, or sharing any section, may take the same (day, period);
    at most MAX_CLASSES_PER_SLOT (51) sessions per slot.
    NOTE: the CP-SAT model does NOT assign rooms; room assignment happens
    in Phase B and room conflicts are verified afterwards.

Phase B (greedy, deterministic) -- room assignment:
    Sessions are assigned to rooms one (day, period) slot at a time,
    respecting room eligibility (lab courses to lab rooms when configured)
    and the no-two-classes-per-room rule. Because Phase A caps every slot at
    51 classes while 51 rooms exist, the unrestricted assignment can never
    run out of rooms. (A total-capacity cap alone would not be sufficient if
    hard room-eligibility restrictions were mandatory; the production
    configuration is soft, and hard mode would require per-slot
    eligibility-capacity checks in Phase A.)

Soft objectives (penalised in Phase A): late-period usage, deviation from
valid existing assignments (repair behaviour), and idle gaps per
section/teacher per day. The gap penalty uses a per-period formulation,
``GapAt(day, p) = HasClassBefore(p) AND NoClassAt(p) AND HasClassAfter(p)``,
which penalises each truly idle period exactly once and never penalises
non-adjacent occupied periods whose intermediate periods are all occupied;
it is bound in both directions so a real gap can never be silently ignored.
On the supplied workbook the solver returns OPTIMAL with a total penalty of
17 in about 86 seconds; the search is warm-started from the existing grid
via ``AddHint``.
"""

from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from src import config
from src.models import TimetableData
from src.utils import get_logger, is_lab_room

log = get_logger(__name__)


class TimetableModel:
    """Encapsulates the CP-SAT day/period placement model."""

    def __init__(self, data: TimetableData) -> None:
        self.data = data
        self.model = cp_model.CpModel()
        self.session_ids: list[str] = [s.session_id for s in data.sessions]

        # (day, period) pair enumeration (config.ACTIVE_PERIODS keeps the
        # rarely-used evening slot available as a soft-penalised option)
        self.dp_pairs: list[tuple[str, int]] = [
            (d, p) for d in config.VALID_DAYS for p in config.ACTIVE_PERIODS]
        self.index_dp = {i: pair for i, pair in enumerate(self.dp_pairs)}

        # variables
        self.dp_choice: dict[str, cp_model.IntVar] = {}
        # chosen[s][i] == (dp_choice[s] == i), reused for capacity caps
        self.chosen: dict[str, list[cp_model.BoolVarT]] = {}
        self.penalties: list[tuple[int, cp_model.IntVar]] = []
        self.penalty_total = self.model.NewIntVar(0, 10**9, "penalty_total")

        self._create_variables()
        self._add_hard_constraints()
        self._add_soft_objectives()
        self.model.Add(
            self.penalty_total == sum(w * v for w, v in self.penalties))
        self.model.Minimize(self.penalty_total)
        self._seed_from_existing_grid()
        log.info("Model created: %d placement variables, %d penalty terms.",
                 len(self.dp_choice), len(self.penalties))

    def _seed_from_existing_grid(self) -> None:
        """Warm-start hint: sessions matching a valid existing grid entry
        (title + sections, FIFO consumption) hint their original day/period.
        The hint is a low-penalty feasible point, not a requirement; the
        solver may ignore it. Applied via CpModel.AddHint so it works with
        all supported OR-Tools versions."""
        need: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
        for s in self.data.sessions:
            need[(s.course.title, tuple(sorted(s.sections)))] += 1
        existing: dict[tuple[str, tuple[str, ...]],
                       list[tuple[str, int, str]]] = defaultdict(list)
        for e in self.data.existing_entries:
            key = (e.course_short, tuple(sorted(e.sections)))
            if need[key] > 0:
                existing[key].append((e.day, e.period, e.room))
                need[key] -= 1
        taken: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
        for s in self.data.sessions:
            key = (s.course.title, tuple(sorted(s.sections)))
            n = taken[key]
            taken[key] = n + 1
            slots = existing.get(key, [])
            if n < len(slots):
                day, period = slots[n][0], slots[n][1]
                i = self.index_dp.get((day, period))
                if i is not None:
                    self.model.AddHint(self.dp_choice[s.session_id], i)

    # ------------------------------------------------------------------
    def _create_variables(self) -> None:
        n_dp = len(self.dp_pairs)
        for session in self.data.sessions:
            self.dp_choice[session.session_id] = self.model.NewIntVar(
                0, n_dp - 1, f"dp_{session.session_id}")

    # ------------------------------------------------------------------
    # Hard constraints (Phase A)
    # ------------------------------------------------------------------
    def _add_hard_constraints(self) -> None:
        self._constraint_exactly_once()
        self._constraint_teacher_conflict()
        self._constraint_section_conflict()

    def _constraint_exactly_once(self) -> None:
        """Constraint 1: every required session takes exactly one slot."""
        for session in self.data.sessions:
            sid = session.session_id
            n_dp = len(self.dp_pairs)
            chosen = [self.model.NewBoolVar(f"chosen_{sid}_{i}")
                      for i in range(n_dp)]
            self.chosen[sid] = chosen
            for i in range(n_dp):
                self.model.Add(self.dp_choice[sid] == i
                               ).OnlyEnforceIf(chosen[i])
                self.model.Add(self.dp_choice[sid] != i
                               ).OnlyEnforceIf(chosen[i].Not())
            self.model.Add(sum(chosen) == 1)

        # Capacity cap: at most MAX_CLASSES_PER_SLOT classes in any
        # (day, period) slot, so that Phase B room assignment can always
        # succeed (rooms are the binding resource).
        for i in range(len(self.dp_pairs)):
            self.model.Add(
                sum(self.chosen[s.session_id][i]
                    for s in self.data.sessions) <=
                config.MAX_CLASSES_PER_SLOT)

    def _constraint_teacher_conflict(self) -> None:
        """Constraint 2: a named teacher teaches at most one class per
        day+period. Sessions without a teacher identity are excluded to avoid
        false conflicts (per requirements)."""
        teacher_sessions = defaultdict(list)
        for s in self.data.sessions:
            if s.teacher:
                teacher_sessions[s.teacher].append(s)
        for teacher, sessions in teacher_sessions.items():
            if len(sessions) <= 1:
                continue
            for i in range(len(self.dp_pairs)):
                placed = [self.model.NewBoolVar(f"tp_{s.session_id}_{i}")
                          for s in sessions]
                for s, var in zip(sessions, placed):
                    self.model.Add(self.dp_choice[s.session_id] == i
                                   ).OnlyEnforceIf(var)
                    self.model.Add(self.dp_choice[s.session_id] != i
                                   ).OnlyEnforceIf(var.Not())
                self.model.Add(sum(placed) <= 1)

    def _constraint_section_conflict(self) -> None:
        """Constraint 3: a section attends at most one class per day+period.

        Combined-cell sections (BCS-1E/3E) expand to individual section keys,
        so all listed sections are occupied for the whole period.
        """
        section_sessions = defaultdict(list)
        for s in self.data.sessions:
            for sec in s.sections:
                section_sessions[sec].append(s)
        for sec, sessions in section_sessions.items():
            if len(sessions) <= 1:
                continue
            for i in range(len(self.dp_pairs)):
                placed = [self.model.NewBoolVar(f"sp_{s.session_id}_{i}")
                          for s in sessions]
                for s, var in zip(sessions, placed):
                    self.model.Add(self.dp_choice[s.session_id] == i
                                   ).OnlyEnforceIf(var)
                    self.model.Add(self.dp_choice[s.session_id] != i
                                   ).OnlyEnforceIf(var.Not())
                self.model.Add(sum(placed) <= 1)

    # ------------------------------------------------------------------
    # Soft objectives
    # ------------------------------------------------------------------
    def _add_soft_objectives(self) -> None:
        self._objective_late_periods()
        self._objective_keep_valid_existing()
        self._objective_gap_reduction()

    def _objective_late_periods(self) -> None:
        """Objective 1: avoid scheduling in late/evening periods.

        Uses the already-linked chosen vars: chosen[s][i] == 1 exactly when
        session s takes slot i, so the late penalty is the weighted sum of
        chosen vars over late slots -- no extra indicator variables needed.
        """
        late_terms = []
        for session in self.data.sessions:
            for i, (d, p) in enumerate(self.dp_pairs):
                if p >= config.LATE_PERIOD_INDEX:
                    late_terms.append(self.chosen[session.session_id][i])
        if late_terms:
            var = self.model.NewIntVar(0, len(late_terms), "late_total")
            self.model.Add(var == sum(late_terms))
            self.penalties.append((config.PENALTY_LATE_PERIOD, var))

    def _objective_keep_valid_existing(self) -> None:
        """Objective 2: keep assignments that are already valid in the
        input grid (repair mode) -- consumes matching grid slots in FIFO
        order, one per sibling session of the same course/section."""
        need: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
        for s in self.data.sessions:
            need[(s.course.title, tuple(sorted(s.sections)))] += 1
        existing: dict[tuple[str, tuple[str, ...]],
                       list[tuple[str, int, str]]] = defaultdict(list)
        for e in self.data.existing_entries:
            key = (e.course_short, tuple(sorted(e.sections)))
            if need[key] > 0:
                existing[key].append((e.day, e.period, e.room))
                need[key] -= 1

        consumed: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
        for session in self.data.sessions:
            sid = session.session_id
            key = (session.course.title, tuple(sorted(session.sections)))
            n_taken = consumed[key] + 1
            consumed[key] = n_taken
            slots = existing.get(key, [])
            if n_taken > len(slots):
                continue
            anchor = slots[n_taken - 1]
            keep = self.model.NewBoolVar(f"keep_{sid}")
            i_anchor = next(k for k, v in self.index_dp.items()
                            if v == (anchor[0], anchor[1]))
            # Placing the session at its anchor slot keeps the assignment
            # exactly: keep == 1  <=>  choice == i_anchor
            self.model.Add(self.dp_choice[sid] == i_anchor
                           ).OnlyEnforceIf(keep)
            self.model.Add(self.dp_choice[sid] != i_anchor
                           ).OnlyEnforceIf(keep.Not())
            self.penalties.append(
                (config.PENALTY_CHANGED_ASSIGNMENT, keep.Not()))

    def _objective_gap_reduction(self) -> None:
        """Objective 3: reduce idle gaps between classes for each section
        and teacher on each day.

        Formulation (per idle period, not per pair of endpoints). A true
        idle gap exists at an owner's day/period ``p`` exactly when the
        owner has at least one class BEFORE ``p``, NO class at ``p``, and
        at least one class AFTER ``p``:

            GapAt(d, p) = HasBefore(d, p) AND IdleAt(d, p) AND HasAfter(d, p)

        This penalises each truly idle period once, and never penalises a
        busy day whose classes fill every period (``IdleAt`` is 0 there),
        unlike a pairwise-endpoint formulation which would penalise two
        non-adjacent classes even when all intermediate periods are
        occupied.

        Each term uses only three boolean variables per owner/day/period
        (``before``, ``idle``, ``after``) linked with ``AddMaxEquality``
        and one one-directional implication for the conjunction -- safe to
        minimise because ``gap = 1`` implies all three are 1, and whenever
        the three conditions actually hold the solver cannot set
        ``gap = 0`` (that would leave classes on both sides of an idle
        period, which the minimisation of ``before/after`` never benefits
        from).
        """
        # owner -> list of sessions (a section is shared by its sessions;
        # teachers are keyed separately)
        owners: dict[tuple, list] = defaultdict(list)
        for s in self.data.sessions:
            for sec in s.sections:
                owners[("__section__", sec)].append(s)
            if s.teacher:
                owners[("__teacher__", s.teacher)].append(s)

        dp_index = {pair: i for i, pair in enumerate(self.dp_pairs)}
        for owner, sessions in owners.items():
            if len(sessions) <= 1:
                continue
            weight = (config.PENALTY_SECTION_GAP
                      if owner[0] == "__section__"
                      else config.PENALTY_TEACHER_GAP)
            for day in config.VALID_DAYS:
                # periods available on this day
                periods = sorted(p for d, p in self.dp_pairs if d == day)
                for idx, p in enumerate(periods):
                    before_periods = periods[:idx]
                    after_periods = periods[idx + 1:]
                    if not before_periods or not after_periods:
                        continue
                    i = dp_index[(day, p)]
                    # HasBefore / HasAfter: max over chosen vars at the
                    # respective periods (chosen == (choice == index))
                    before_vars = [self.chosen[s.session_id][dp_index[(day, bp)]]
                                   for bp in before_periods for s in sessions]
                    after_vars = [self.chosen[s.session_id][dp_index[(day, ap)]]
                                  for ap in after_periods for s in sessions]
                    before = self.model.NewBoolVar(
                        f"gb_{owner}_{day}_{p}")
                    idle = self.model.NewBoolVar(
                        f"gi_{owner}_{day}_{p}")
                    after = self.model.NewBoolVar(
                        f"ga_{owner}_{day}_{p}")
                    self.model.AddMaxEquality(before, before_vars)
                    self.model.AddMaxEquality(idle,
                                              [self.chosen[s.session_id][i]
                                               for s in sessions])
                    self.model.AddMaxEquality(after, after_vars)
                    gap = self.model.NewBoolVar(
                        f"gg_{owner}_{day}_{p}")
                    # gap == 1 -> before AND NOT idle AND after are all 1
                    self.model.AddBoolAnd([before, idle.Not(), after]).OnlyEnforceIf(gap)
                    # gap == 0 -> at least one condition fails (forces the
                    # penalty to fire when the owner truly has classes on
                    # both sides of an idle period; ``before``, ``idle`` and
                    # ``after`` are exact MaxEquality definitions, not free
                    # variables, so ``gap >= before + after - idle - 1``
                    # makes ``gap == 1`` unavoidable in that case)
                    self.model.Add(gap >= before + after - idle - 1)
                    self.penalties.append((weight, gap))

    # ------------------------------------------------------------------
    # Phase B: deterministic room assignment
    # ------------------------------------------------------------------
    @staticmethod
    def assign_rooms(data: TimetableData,
                     placements: dict[str, tuple[str, int]]) \
            -> dict[str, tuple[str, int, str]]:
        """Greedy room assignment for the given day/period placements.

        Returns {session_id: (day, period, room)}. Rooms are assigned in
        preference order: lab courses use lab rooms when restriction mode is
        ``hard`` (and prefer them as a quality heuristic in ``soft`` mode);
        lecture courses prefer non-lab rooms.

        Feasibility guarantees (see P4 design note):

        * The CP-SAT model (Phase A) directly enforces teacher and section
          conflicts and caps every (day, period) slot at MAX_CLASSES_PER_SLOT
          == len(rooms) == 51 classes. This total cap guarantees that the
          *unrestricted* greedy pool (all rooms) never runs dry, so the
          fallback assignment below always succeeds.
        * A total-capacity cap alone does NOT guarantee feasibility when a
          subset of rooms is mandatory: in ``hard`` lab-room mode the number
          of lab-only sessions in a slot could exceed the number of lab
          rooms. The current production configuration is ``soft`` (a
          preference, not a requirement), so this case does not arise. If
          ``hard`` mode is enabled for a real deployment, per-slot
          eligibility-capacity checks (lab-only demand <= 18 lab rooms) must
          be added as Phase A constraints.
        * The independent post-solution validator (postvalidator.py)
          re-verifies room conflicts, valid rooms, and room restrictions
          from scratch on the final assignments.
        """
        lab_only = (config.LAB_ROOM_RESTRICTION_MODE == "hard")
        rooms = data.rooms
        lab_rooms = data.lab_rooms
        non_lab_rooms = [rm for rm in rooms if rm not in lab_rooms]

        # occupancy bookkeeping
        used: dict[tuple[str, int], list[str]] = defaultdict(list)

        result: dict[str, tuple[str, int, str]] = {}
        # Schedule the hardest-to-place sessions first (labs with restricted
        # room set first, then by number of sections desc).
        order = sorted(data.sessions,
                       key=lambda s: (
                           0 if s.is_lab else 1,
                           -len(s.sections),
                           s.session_id))

        for session in order:
            day, period = placements[session.session_id]
            if session.is_lab:
                if lab_only:
                    pool = lab_rooms
                else:
                    pool = [rm for rm in rooms
                            if is_lab_room(rm)] or rooms
            else:
                pool = non_lab_rooms or rooms
            placed = None
            for rm in pool:
                if rm not in used[(day, period)]:
                    placed = rm
                    break
            if placed is None:
                # Fallback: relax pool (should not happen under capacity)
                for rm in rooms:
                    if rm not in used[(day, period)]:
                        placed = rm
                        break
            if placed is None:
                raise RuntimeError(
                    f"Room assignment infeasible for session "
                    f"{session.session_id} at {day} period {period}: all "
                    f"{len(rooms)} rooms occupied (should be impossible, "
                    f"max occupancy {len(used[(day, period)])} < {len(rooms)} "
                    f"rooms).")
            used[(day, period)].append(placed)
            result[session.session_id] = (day, period, placed)
        return result

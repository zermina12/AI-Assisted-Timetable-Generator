"""Tests for the CP-SAT constraint model and solution extraction."""

from collections import defaultdict

import pytest
from ortools.sat.python import cp_model

from src import config
from src.constraint_model import TimetableModel
from src.models import Course, Session, TimetableData
from src.solver import STATUS_FEASIBLE, STATUS_OPTIMAL, TimetableSolver
from src.postvalidator import validate_solution


def _course(**kw):
    defaults = dict(code="T1", title="Test", section="T-1A",
                    instructor="Tch A", credit_hours=2, program="BS(T)",
                    category="Core", sheet="CS")
    defaults.update(kw)
    return Course(**defaults)


def _make_data(courses):
    data = TimetableData()
    data.rooms = ["L1", "L2", "R1", "R2"]
    data.lab_rooms = ["L1", "L2"]
    sid = 0
    for c in courses:
        data.courses.append(c)
        n = 1 if c.is_lab else c.credit_hours
        for k in range(1, n + 1):
            sid += 1
            s = Session(f"S-{sid:04d}", c, k, c.is_lab)
            data.sessions.append(s)
            if c.instructor:
                data.teacher_sessions.setdefault(c.instructor, set()).add(s.session_id)
            for sec in s.sections:
                data.section_sessions.setdefault(sec, set()).add(s.session_id)
    return data


def _solve(data, time_limit=30, lab_mode="soft"):
    import src.config as cfg
    old = cfg.LAB_ROOM_RESTRICTION_MODE
    cfg.LAB_ROOM_RESTRICTION_MODE = lab_mode
    try:
        solver = TimetableSolver(data, time_limit=time_limit,
                                 log_search=False)
        result = solver.solve()
        return result
    finally:
        cfg.LAB_ROOM_RESTRICTION_MODE = old


class TestModelConstruction:
    def test_exactly_one_assignment_per_session(self):
        data = _make_data([_course(credit_hours=3)])
        model = TimetableModel(data)
        s = data.sessions[0]
        # A placement variable exists for every session
        assert s.session_id in model.dp_choice
        assert len(model.dp_pairs) == len(config.VALID_DAYS) * len(
            config.ACTIVE_PERIODS)

    def test_pair_domains_valid(self):
        data = _make_data([_course(), _course(title="Lab", section="T-1B",
                                              credit_hours=1, is_lab=True)])
        model = TimetableModel(data)
        for d, p in model.dp_pairs:
            assert d in config.VALID_DAYS
            assert p in config.ACTIVE_PERIODS


class TestSolverCorrectness:
    def test_single_course_solves_and_passes_validation(self):
        data = _make_data([_course(credit_hours=3)])
        result = _solve(data)
        assert result.is_valid
        report = validate_solution(data, result.assignments)
        assert report.passed, report.to_text()

    def test_multiple_teachers_no_conflict(self):
        data = _make_data([
            _course(code="T1", section="T-1A", instructor="Tch A",
                    credit_hours=3),
            _course(code="T2", section="T-1B", instructor="Tch B",
                    credit_hours=3),
        ])
        result = _solve(data)
        assert result.is_valid
        report = validate_solution(data, result.assignments)
        assert report.passed, report.to_text()

    def test_same_teacher_two_sections_scheduled_different_times(self):
        data = _make_data([
            _course(code="T1", section="T-1A", instructor="Same T",
                    credit_hours=2),
            _course(code="T2", section="T-2A", instructor="Same T",
                    credit_hours=2),
        ])
        result = _solve(data)
        assert result.is_valid
        report = validate_solution(data, result.assignments)
        assert report.passed, report.to_text()
        by = defaultdict(list)
        for a in result.assignments:
            by[(a.session.teacher, a.day, a.period)].append(a)
        for lst in by.values():
            assert len(lst) == 1

    def test_same_section_two_courses_no_conflict(self):
        data = _make_data([
            _course(code="T1", section="T-1A", instructor="Tch A",
                    credit_hours=2),
            _course(code="T2", section="T-1A", instructor="Tch B",
                    credit_hours=2),
        ])
        result = _solve(data)
        assert result.is_valid
        report = validate_solution(data, result.assignments)
        assert report.passed, report.to_text()

    def test_lab_soft_mode_prefers_lab_rooms(self):
        data = _make_data([_course(title="Comp Lab", section="T-1A",
                                   credit_hours=1, is_lab=True)])
        result = _solve(data)
        assert result.is_valid
        # With the change penalty absent (no existing assignments) and lab
        # penalty active, the lab should land in a lab room.
        assert all(a.room in data.lab_rooms for a in result.assignments)

    def test_real_data_solves(self):
        from src.data_loader import load_timetable_data
        data = load_timetable_data()
        result = _solve(data, time_limit=config.SOLVER_TIME_LIMIT_SECONDS)
        assert result.is_valid, result.message
        report = validate_solution(data, result.assignments)
        assert report.passed, report.to_text()

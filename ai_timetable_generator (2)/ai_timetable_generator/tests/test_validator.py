"""Tests for the input-validation stage and the independent validator."""

from collections import defaultdict

import pytest

from src import config
from src.models import (
    Assignment,
    Course,
    ExistingEntry,
    Session,
    TimetableData,
)
from src.postvalidator import validate_solution
from src.validator import (
    CONFLICT_ROOM,
    CONFLICT_SECTION,
    CONFLICT_TEACHER,
    validate_input,
)


@pytest.fixture(scope="module")
def data():
    from src.data_loader import load_timetable_data
    return load_timetable_data()


def _course(**kw):
    defaults = dict(code="CS1002", title="PF", section="BCS-1A",
                    instructor="Dr. A", credit_hours=3, program="BS(CS)",
                    category="CS (Core)", sheet="CS")
    defaults.update(kw)
    return Course(**defaults)


def _sessions_for(course, n=None, lab=False):
    n = n if n is not None else (1 if lab else course.credit_hours)
    out = []
    for k in range(1, n + 1):
        out.append(Session(f"S-{k}", course, k, lab))
    return out


def _make_data(courses_sessions, entries):
    data = TimetableData()
    data.rooms = ["R1", "R2", "R3"]
    for course, sessions in courses_sessions.items():
        data.courses.append(course)
        data.sessions.extend(sessions)
    for e in entries:
        data.existing_entries.append(e)
    for s in data.sessions:
        if s.teacher:
            data.teacher_sessions.setdefault(s.teacher, set()).add(s.session_id)
        for sec in s.sections:
            data.section_sessions.setdefault(sec, set()).add(s.session_id)
    return data


class TestInputValidation:
    def test_real_data_has_conflicts(self, data):
        report = validate_input(data)
        kinds = {c.kind for c in report.conflicts}
        # The real workbook grid is known to contain section and room clashes
        assert CONFLICT_SECTION in kinds or CONFLICT_ROOM in kinds

    def test_teacher_conflict_detected(self):
        c = _course(instructor="Dr. A")
        sessions = _sessions_for(c)
        entries = [
            ExistingEntry("Mon", "R1", 0, "PF", ("BCS-1A",), "Dr. A"),
            ExistingEntry("Mon", "R2", 0, "DS", ("BCS-1A",), "Dr. A"),
        ]
        report = validate_input(_make_data({c: sessions}, entries))
        assert any(x.kind == CONFLICT_TEACHER for x in report.conflicts)

    def test_missing_teacher_no_false_conflict(self):
        """Two entries without teachers must NOT create a teacher conflict."""
        c = _course(instructor="")
        sessions = _sessions_for(c)
        entries = [
            ExistingEntry("Mon", "R1", 0, "PF", ("BCS-1A",), ""),
            ExistingEntry("Mon", "R2", 0, "DS", ("BCS-1B",), ""),
        ]
        report = validate_input(_make_data({c: sessions}, entries))
        assert not any(x.kind == CONFLICT_TEACHER for x in report.conflicts)

    def test_combined_section_conflict_detected(self):
        c1 = _course(title="Calc", section="BCS-1E/3E", instructor="Dr. X")
        c2 = _course(title="Alg", section="BCS-3E", instructor="Dr. Y")
        e1 = [ExistingEntry("Mon", "R1", 0, "Calc", ("BCS-1E", "BCS-3E"), "Dr. X")]
        e2 = [ExistingEntry("Mon", "R2", 0, "Alg", ("BCS-3E",), "Dr. Y")]
        data = _make_data({c1: _sessions_for(c1), c2: _sessions_for(c2)},
                          e1 + e2)
        report = validate_input(data)
        assert any(x.kind == CONFLICT_SECTION for x in report.conflicts)

    def test_room_conflict_detected(self):
        c1 = _course(title="PF", instructor="Dr. A")
        c2 = _course(title="DS", instructor="Dr. B")
        entries = [
            ExistingEntry("Mon", "R1", 0, "PF", ("BCS-1A",), "Dr. A"),
            ExistingEntry("Mon", "R1", 0, "DS", ("BCS-1B",), "Dr. B"),
        ]
        report = validate_input(_make_data({c1: _sessions_for(c1),
                                            c2: _sessions_for(c2)}, entries))
        assert any(x.kind == CONFLICT_ROOM for x in report.conflicts)

    def test_invalid_day_detected(self):
        c = _course()
        entries = [ExistingEntry("Sunday", "R1", 0, "PF", ("BCS-1A",), "Dr. A")]
        report = validate_input(_make_data({c: _sessions_for(c)}, entries))
        assert any(x.kind == "invalid_day" for x in report.conflicts)


class TestPostValidation:
    def _conflict_free_solution(self, data):
        """Build an obviously valid synthetic solution for the real data."""
        rooms = data.rooms
        assignments = []
        used = defaultdict(list)  # (teacher|section, day, per)
        day_i = 0
        per_i = 0
        for session in data.sessions:
            placed = False
            for d in config.VALID_DAYS:
                for p in config.ACTIVE_PERIODS:
                    for rm in rooms:
                        key_t = (session.teacher, d, p) if session.teacher else None
                        key_s = [(s, d, p) for s in session.sections]
                        key_r = (d, p, rm)
                        ok = (not key_t or key_t not in used)
                        ok = ok and all(ks not in used for ks in key_s)
                        ok = ok and key_r not in used
                        if ok:
                            assignments.append(
                                Assignment(session, d, p, rm))
                            if key_t:
                                used[key_t] = [1]
                            for ks in key_s:
                                used[ks] = [1]
                            used[key_r] = [1]
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break
            assert placed, f"could not place {session.session_id}"
        return assignments

    def test_synthetic_conflict_free_solution_passes(self, data):
        sol = self._conflict_free_solution(data)
        report = validate_solution(data, sol)
        assert report.passed, report.to_text()

    def test_teacher_conflict_caught(self, data):
        a = data.sessions[0]
        b = data.sessions[1]
        bad = [Assignment(a, "Mon", 0, data.rooms[0]),
               Assignment(b, "Mon", 0, data.rooms[1])]
        report = validate_solution(data, bad)
        if a.teacher and a.teacher == b.teacher:
            assert not report.checks.get("no_teacher_conflict", True)

    def test_section_conflict_caught(self, data):
        a = data.sessions[0]
        b = [s for s in data.sessions
             if s.session_id != a.session_id
             and set(s.sections) & set(a.sections)]
        if b:
            bad = [Assignment(a, "Mon", 0, data.rooms[0]),
                   Assignment(b[0], "Mon", 0, data.rooms[1])]
            report = validate_solution(data, bad)
            assert not report.checks.get("no_section_conflict", True)

    def test_room_conflict_caught(self, data):
        a, b = data.sessions[0], data.sessions[1]
        bad = [Assignment(a, "Mon", 0, data.rooms[0]),
               Assignment(b, "Mon", 0, data.rooms[0])]
        report = validate_solution(data, bad)
        assert not report.checks.get("no_room_conflict", True)

    def test_missing_session_caught(self, data):
        only_one = [Assignment(data.sessions[0], "Mon", 0, data.rooms[0])]
        report = validate_solution(data, only_one)
        assert not report.checks.get("every_session_scheduled", True)

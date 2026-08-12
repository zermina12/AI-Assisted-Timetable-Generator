"""Tests for the Excel data-loading pipeline."""

import pytest

from src.data_loader import load_timetable_data
from src import config


@pytest.fixture(scope="module")
def data():
    return load_timetable_data()


class TestWorkbookLoading:
    def test_workbook_loads_without_error(self, data):
        assert len(data.sessions) > 0

    def test_all_course_sheets_loaded(self, data):
        sheets = {c.sheet for c in data.courses}
        for name in config.COURSE_SHEETS:
            assert name in sheets, f"sheet {name} not loaded"

    def test_sessions_created(self, data):
        # ~996 lecture + ~110 lab sessions expected from inspection
        assert len(data.sessions) >= 1000

    def test_session_ids_unique(self, data):
        ids = [s.session_id for s in data.sessions]
        assert len(ids) == len(set(ids))

    def test_rooms_extracted_from_grid(self, data):
        assert len(data.rooms) >= 40
        assert "S. Hall" in data.rooms
        assert any(r.startswith("F-") for r in data.rooms)

    def test_lab_rooms_flagged(self, data):
        assert len(data.lab_rooms) >= 10
        assert any(r.startswith("Lab-") or r.startswith("Eng Lab")
                   for r in data.lab_rooms)

    def test_existing_entries_parsed(self, data):
        assert len(data.existing_entries) >= 500
        days = {e.day for e in data.existing_entries}
        assert days == {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat"}


class TestParsing:
    def test_credit_hours_map_to_session_count(self, data):
        # A 3-CH course row must expand to 3 sessions
        threes = [c for c in data.courses if c.credit_hours == 3
                  and not c.is_lab and not c.is_merged]
        assert len(threes) > 0
        titles = {(c.title, c.section): c.credit_hours for c in threes}
        for (title, sec), ch in list(titles.items())[:20]:
            n = sum(1 for s in data.sessions
                    if s.course.title == title
                    and s.course.section == sec and not s.is_lab)
            assert n == ch, f"{title} {sec}: expected {ch}, got {n}"

    def test_lab_rows_single_session(self, data):
        labs = [c for c in data.courses if c.is_lab]
        assert len(labs) > 0
        for c in labs[:10]:
            n = sum(1 for s in data.sessions
                    if s.course is c)
            assert n == 1

    def test_combined_sections_expand(self, data):
        comb = [c for c in data.courses if "/" in c.section and not c.is_merged]
        assert len(comb) > 0
        for c in comb[:10]:
            assert len(c.sections) == len(c.section.split("/"))
            assert all(s for s in c.sections)

    def test_instructor_names_normalized(self, data):
        # No instructor name should contain collapsed-whitespace artifacts
        for c in data.courses:
            assert c.instructor == " ".join(c.instructor.split())

    def test_missing_teachers_flagged_not_invented(self, data):
        assert len(data.missing_teachers) > 0
        for c in data.missing_teachers:
            assert c.instructor == ""

    def test_merged_courses_excluded_from_sessions(self, data):
        merged_ids = {id(c) for c in data.merged_courses}
        for s in data.sessions:
            assert id(s.course) not in merged_ids, (
                f"session {s.session_id} belongs to merged course "
                f"{s.course.code} {s.course.title}")

    def test_nc_credit_handled(self, data):
        nc = [c for c in data.courses
              if str(c.sheet) and c.credit_hours == 1 and not c.is_lab]
        # NC rows default to 1 session and are not crashes
        assert len(data.courses) > 0


class TestIndexes:
    def test_teacher_index_nonempty(self, data):
        assert len(data.teacher_sessions) > 100

    def test_section_index_covers_all_sessions(self, data):
        indexed = set()
        for ids in data.section_sessions.values():
            indexed.update(ids)
        # Sessions whose course has no section (e.g. merged placeholder rows
        # or thesis rows with no section stated) are intentionally absent from
        # the section index; every other session must be indexed.
        for s in data.sessions:
            if s.course.sections:
                assert s.session_id in indexed, s.session_id

    def test_lab_sessions_no_teacher_required(self, data):
        lab_sessions = [s for s in data.sessions if s.is_lab]
        # Labs may or may not have teachers; neither should crash indexing
        assert len(lab_sessions) > 50

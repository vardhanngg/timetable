import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import solver


def build_shared_teacher_case():
    teachers = {
        0: {"Name": "Shared Teacher", "available": True},
        1000: {"Name": "f1", "available": True},
        1001: {"Name": "f2", "available": True},
    }
    class_teacher_periods = {
        0: {0: 2},
        1: {0: 2},
    }
    subject_map = {
        0: {0: [{"name": "Mathematics", "hours": 2, "type": "theory"}]},
        1: {0: [{"name": "Mathematics", "hours": 2, "type": "theory"}]},
    }
    bundle = [{
        "name": "shared-maths",
        "type": "merged",
        "periodsPerWeek": 2,
        "members": [
            {"classIdx": 0, "subject": "Mathematics", "teacherId": "0"},
            {"classIdx": 1, "subject": "Mathematics", "teacherId": "0"},
        ],
    }]
    return teachers, class_teacher_periods, subject_map, bundle


class SyncGroupSolverTests(unittest.TestCase):
    def test_shared_teacher_syncs_classes_in_cp_sat(self):
        teachers, credits, subjects, bundles = build_shared_teacher_case()
        timetable = solver.generate_timetable_ortools(
            2, 2, 2, teachers, credits, {}, subjects,
            time_limit_seconds=10, elective_bundles=bundles
        )
        self.assertIsNotNone(timetable)
        shared_slots = [
            slot for slot in range(4)
            if timetable[slot][0] == "Mathematics"
            and timetable[slot][1] == "Mathematics"
        ]
        self.assertEqual(len(shared_slots), 2)
        for slot in range(4):
            self.assertEqual(
                timetable[slot][0] == "Mathematics",
                timetable[slot][1] == "Mathematics",
            )

    def test_single_class_electives_lock_all_subteachers(self):
        teachers = {
            0: {"Name": "English", "available": True},
            1: {"Name": "French", "available": True},
            2: {"Name": "Telugu", "available": True},
            1000: {"Name": "f1", "available": True},
            1001: {"Name": "f2", "available": True},
        }
        credits = {
            0: {0: 2},
            1: {1: 2, 2: 2},
        }
        subjects = {
            0: {0: [{"name": "Language", "hours": 2, "type": "theory"}]},
            1: {
                1: [{"name": "French", "hours": 2, "type": "theory"}],
                2: [{"name": "Telugu", "hours": 2, "type": "theory"}],
            },
        }
        bundles = [{
            "name": "Language|Class1",
            "type": "split",
            "periodsPerWeek": 2,
            "members": [
                {"classIdx": 0, "subject": "Language", "teacherId": "0"},
                {"classIdx": 0, "subject": "Language", "teacherId": "1"},
                {"classIdx": 0, "subject": "Language", "teacherId": "2"},
            ],
        }]
        timetable = solver.generate_timetable_ortools(
            2, 2, 3, teachers, credits, {}, subjects,
            time_limit_seconds=10, elective_bundles=bundles
        )
        self.assertIsNotNone(timetable)
        language_slots = [
            slot for slot in range(6) if timetable[slot][0] == "Language"
        ]
        self.assertEqual(len(language_slots), 2)
        for slot in language_slots:
            self.assertNotEqual(timetable[slot][1], "French")
            self.assertNotEqual(timetable[slot][1], "Telugu")

    def test_unavailable_elective_teacher_blocks_split_slot(self):
        teachers = {
            0: {"Name": "English", "available": True},
            1: {"Name": "French", "available": True},
            2: {"Name": "Telugu", "available": True},
        }
        credits = {0: {0: 1}, 1: {1: 1, 2: 1}}
        subjects = {
            0: {0: [{"name": "Language", "hours": 1, "type": "theory"}]},
            1: {
                1: [{"name": "French", "hours": 1, "type": "theory"}],
                2: [{"name": "Telugu", "hours": 1, "type": "theory"}],
            },
        }
        bundles = [{
            "name": "Language|Class1",
            "type": "split",
            "periodsPerWeek": 1,
            "members": [
                {"classIdx": 0, "subject": "Language", "teacherId": "0"},
                {"classIdx": 0, "subject": "Language", "teacherId": "1"},
                {"classIdx": 0, "subject": "Language", "teacherId": "2"},
            ],
        }]
        timetable = solver.generate_timetable_ortools(
            2, 1, 2, teachers, credits, {}, subjects,
            time_limit_seconds=10,
            teacher_unavailability={"1": [0]},
            elective_bundles=bundles,
        )
        self.assertIsNotNone(timetable)
        self.assertNotEqual(timetable[0][0], "Language")


if __name__ == "__main__":
    unittest.main()

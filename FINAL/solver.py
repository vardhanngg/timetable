import random
import copy
import csv

# ==================================================
# MAIN ENTRY POINT (NEW — REQUIRED)
# ==================================================
def generate_timetable(
    No_of_classes,
    No_of_days_in_week,
    No_of_periods,
    teacher_list,
    class_teacher_periods,
    lab_teacher_periods,
    subject_map,
    fixed_periods=None
):
    random.seed(10)

    # ---------------- BASIC CONFIG ----------------
    total_periods = No_of_days_in_week * No_of_periods

    # ---------------- TIMETABLE MATRIX ----------------
    Timetable = []
    arr = [0] * No_of_classes
    for _ in range(total_periods):
        Timetable.append(arr.copy())

    # ---------------- FIXED PERIODS ----------------
    fixed_periods_count = 0
    if fixed_periods:
        for slot, value in fixed_periods.items():
            for cls in range(No_of_classes):
                Timetable[slot][cls] = value
            fixed_periods_count += 1

    # ---------------- TEACHER STATE ----------------
    main_teacher_list = [
        copy.deepcopy(teacher_list)
        for _ in range(total_periods)
    ]

    No_of_teachers = len(teacher_list)

    # ---------------- LAB HELPERS ----------------
    labs = {}
    for cls, labs_info in lab_teacher_periods.items():
        for _, (_, _, lab_no) in labs_info.items():
            labs.setdefault(lab_no, [])

    lab_used_by_class_per_day = {
        class_idx: {}
        for class_idx in range(No_of_classes)
    }

    # ------------------------------------------------
    # RESET LAB DAY USAGE
    # ------------------------------------------------
    def reset_lab_day_usage():
        for cls in lab_used_by_class_per_day:
            lab_used_by_class_per_day[cls].clear()

    # ------------------------------------------------
    # ASSIGN LAB PERIODS RANDOMLY (UNCHANGED LOGIC)
    # ------------------------------------------------
    def assign_lab_periods_randomly():
        for class_idx, teacher_periods in lab_teacher_periods.items():
            for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():

                available_slots = [
                    i for i in range(total_periods)
                    if Timetable[i][class_idx] == 0
                    and main_teacher_list[i][teacher_id]["available"]
                ]
                random.shuffle(available_slots)

                sessions_assigned = 0
                for slot in available_slots:
                    if slot + consecutive_periods > total_periods:
                        continue

                    can_assign = True
                    for i in range(consecutive_periods):
                        day = (slot + i) // No_of_periods
                        if (
                            Timetable[slot + i][class_idx] != 0 or
                            not main_teacher_list[slot + i][teacher_id]["available"] or
                            (slot // No_of_periods) != ((slot + i) // No_of_periods) or
                            (slot + i) in labs[lab_number] or
                            lab_number in lab_used_by_class_per_day[class_idx].get(day, set())
                        ):
                            can_assign = False
                            break

                    if can_assign:
                        for i in range(consecutive_periods):
                            subject_name = subject_map.get((class_idx, teacher_id), "Lab")
                            Timetable[slot + i][class_idx] = f"{subject_name} (Lab {lab_number})"
                            main_teacher_list[slot + i][teacher_id]["available"] = False
                            class_to_teacher[class_idx][teacher_id] -= 1
                            labs[lab_number].append(slot + i)

                            day = (slot + i) // No_of_periods
                            lab_used_by_class_per_day.setdefault(class_idx, {}).setdefault(day, set()).add(lab_number)

                            sessions_assigned += 1

                    if sessions_assigned == total_sessions:
                        break

    # ------------------------------------------------
    # CLASS → TEACHER CREDIT MATRIX (UNCHANGED LOGIC)
    # ------------------------------------------------
    FREE_TEACHERS = [
        t_id for t_id, info in teacher_list.items()
        if info["Name"].startswith("f")
    ]

    class_to_teacher = []

    for class_idx in range(No_of_classes):
        teacher_part = [0] * No_of_teachers

        assigned_theory = 0
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            teacher_part[t_idx] = periods
            assigned_theory += periods

        assigned_labs = 0
        if class_idx in lab_teacher_periods:
            for t_id, info in lab_teacher_periods[class_idx].items():
                teacher_part[t_id] += info[0]
                assigned_labs += info[0]

        free_count = total_periods - assigned_theory - assigned_labs - fixed_periods_count
        if free_count < 0:
            free_count = 0

        free_teacher_index = FREE_TEACHERS[class_idx % len(FREE_TEACHERS)]
        teacher_part[free_teacher_index] = free_count

        priority_list = list(range(No_of_teachers))
        row = teacher_part.copy()
        row.append(priority_list)
        class_to_teacher.append(row)

    # ------------------------------------------------
    # MRV SLOT SELECTION (UNCHANGED)
    # ------------------------------------------------
    def find_empty():
        best_cell = (-1, -1)
        min_teachers = float("inf")

        rows = list(range(len(Timetable)))
        random.shuffle(rows)

        for x in rows:
            for y in range(No_of_classes):
                if Timetable[x][y] != 0:
                    continue

                count = 0
                for i in range(No_of_teachers):
                    if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                        count += 1

                if count == 0:
                    return x, y

                if count < min_teachers:
                    min_teachers = count
                    best_cell = (x, y)

        return best_cell

    # ------------------------------------------------
    # BACKTRACKING SOLVER (UNCHANGED)
    # ------------------------------------------------
    def solve():
        x, y = find_empty()
        if x == -1:
            return True

        priority = class_to_teacher[y][-1][:]
        random.shuffle(priority)

        for i in priority:
            if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                class_to_teacher[y][i] -= 1
                main_teacher_list[x][i]["available"] = False

                Timetable[x][y] = subject_map.get((y, i), teacher_list[i]["Name"])

                if solve():
                    return True

                Timetable[x][y] = 0
                class_to_teacher[y][i] += 1
                main_teacher_list[x][i]["available"] = True

        return False

    # ------------------------------------------------
    # EXECUTION PIPELINE
    # ------------------------------------------------
    reset_lab_day_usage()
    assign_lab_periods_randomly()

    if solve():
        return Timetable

    return None
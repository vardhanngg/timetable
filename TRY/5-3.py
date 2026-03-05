import random
import copy
import csv
import logging
import os

# 1. LOGGING CONFIGURATION
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solver_debug.log')
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

# 2. YOUR ORIGINAL SOLVER CODE (UNMODIFIED)
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
    # ---------------- BASIC CONFIG ----------------
    total_periods = No_of_days_in_week * No_of_periods

    # ---------------- TIMETABLE MATRIX ----------------
    Timetable = []
    arr = [0] * No_of_classes
    for _ in range(total_periods):
        Timetable.append(arr.copy())

    # ---------------- TEACHER STATE ----------------
    main_teacher_list = [
        copy.deepcopy(teacher_list)
        for _ in range(total_periods)
    ]

    # ---------------- 1 & 4. COORDINATE MAPPING & PRE-FILLING ----------------
    teacher_fixed_workload = {c: {t: 0 for t in teacher_list} for c in range(No_of_classes)}
    class_fixed_total = [0] * No_of_classes

    if fixed_periods:
        for cls_idx_str, slots in fixed_periods.items():
            try:
                cls_idx = int(cls_idx_str)
            except ValueError:
                continue
            
            for slot_str, info in slots.items():
                if not info.get('label') or info.get('label').strip() == "":
                    continue
                
                try:
                    d, p = map(int, slot_str.split('-'))
                    flat_slot = d * No_of_periods + p
                except (ValueError, IndexError):
                    continue

                Timetable[flat_slot][cls_idx] = info['label']
                class_fixed_total[cls_idx] += 1
                
                t_id_raw = info.get('teacher_id', "None")
                if t_id_raw is not None and str(t_id_raw).isdigit():
                    t_id = int(t_id_raw)
                    if t_id in main_teacher_list[flat_slot]:
                        main_teacher_list[flat_slot][t_id]["available"] = False
                        teacher_fixed_workload[cls_idx][t_id] += 1

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

    def reset_lab_day_usage():
        for cls in lab_used_by_class_per_day:
            lab_used_by_class_per_day[cls].clear()

    # ---------------- LAB ASSIGNMENT ----------------
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

    # ---------------- 3. CREDIT MATRIX ----------------
    FREE_TEACHERS = [
        t_id for t_id, info in teacher_list.items()
        if info["Name"].startswith("f")
    ]

    class_to_teacher = []
    for class_idx in range(No_of_classes):
        teacher_part = [0] * No_of_teachers
        assigned_workload = 0
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            fixed_already = teacher_fixed_workload[class_idx].get(t_idx, 0)
            net_needed = max(0, periods - fixed_already)
            teacher_part[t_idx] = net_needed
            assigned_workload += net_needed

        assigned_labs = 0
        if class_idx in lab_teacher_periods:
            for t_id, info in lab_teacher_periods[class_idx].items():
                teacher_part[t_id] += info[0]
                assigned_labs += info[0]

        free_count = total_periods - assigned_workload - assigned_labs - class_fixed_total[class_idx]
        if free_count < 0:
            free_count = 0

        free_teacher_index = FREE_TEACHERS[class_idx % len(FREE_TEACHERS)]
        teacher_part[free_teacher_index] = free_count

        priority_list = list(range(No_of_teachers))
        row = teacher_part.copy()
        row.append(priority_list)
        class_to_teacher.append(row)

    # ---------------- MRV & BACKTRACKING ----------------
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

    def solve():
        x, y = find_empty()
        if x == -1:
            logging.info("Solution found! All slots filled.")
            return True
        priority = class_to_teacher[y][-1][:]
        random.shuffle(priority)
        for i in priority:
            if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                t_name = teacher_list[i]["Name"]
                logging.debug(f"Slot({x}) Class({y}): Trying Teacher {t_name}") 
                class_to_teacher[y][i] -= 1
                main_teacher_list[x][i]["available"] = False
                Timetable[x][y] = subject_map.get((y, i), teacher_list[i]["Name"])
                if solve():
                    return True
                logging.warning(f"Slot({x}) Class({y}): Backtracking from {t_name}")
                Timetable[x][y] = 0
                class_to_teacher[y][i] += 1
                main_teacher_list[x][i]["available"] = True
        return False

    reset_lab_day_usage()
    assign_lab_periods_randomly()

    if solve():
        return Timetable
    return None

# 3. FEEDING LOGIC (Using your JSON data)
if __name__ == "__main__":
    raw_data = {
        "No_of_classes": 5, "days": 6, "periods": 6,
        "teacher_list": {
            "0": {"Name": "S1", "available": True}, "1": {"Name": "S2", "available": True},
            "2": {"Name": "S3", "available": True}, "3": {"Name": "S4", "available": True},
            "4": {"Name": "S5", "available": True}, "5": {"Name": "S6", "available": True},
            "6": {"Name": "S7", "available": True}, "7": {"Name": "S8", "available": True},
            "8": {"Name": "S9", "available": True}, "9": {"Name": "S10", "available": True},
            "10": {"Name": "S11", "available": True}, "11": {"Name": "S12", "available": True},
            "12": {"Name": "f1", "available": True}, "13": {"Name": "f2", "available": True},
            "14": {"Name": "f3", "available": True}, "15": {"Name": "f4", "available": True},
            "16": {"Name": "f5", "available": True}
        },
        "class_theory_workload": {
            "0": {"5": 3, "6": 3, "1": 4, "4": 4, "2": 2, "7": 2, "8": 3},
            "1": {"5": 3, "8": 6, "3": 4, "4": 4, "6": 2},
            "2": {"3": 4, "9": 7, "4": 5, "2": 5, "6": 2},
            "3": {"11": 4, "3": 4, "10": 4, "9": 2, "0": 4, "7": 2},
            "4": {"4": 5, "2": 5, "1": 5, "0": 5, "7": 2}
        },
        "lab_periods": {
            "0": {"1": [6, 2, 1], "2": [2, 2, 1]},
            "1": {"9": [4, 2, 1]},
            "2": {"10": [6, 2, 2]}
        },
        "subject_map": {}, 
        "fixed_periods": {"0": {}}
    }

    # Transform string keys to integers as required by your solver
    t_list = {int(k): v for k, v in raw_data["teacher_list"].items()}
    c_theory = {int(cls): {int(t): p for t, p in t_dict.items()} for cls, t_dict in raw_data["class_theory_workload"].items()}
    c_labs = {int(cls): {int(t): tuple(vals) for t, vals in t_dict.items()} for cls, t_dict in raw_data["lab_periods"].items()}
    
    # Auto-fill subject map from teacher names since it was empty
    s_map = {(c, t): t_list[t]["Name"] for c in range(raw_data["No_of_classes"]) for t in range(len(t_list))}

    # RUN
    result = generate_timetable(
        raw_data["No_of_classes"], raw_data["days"], raw_data["periods"],
        t_list, c_theory, c_labs, s_map, raw_data["fixed_periods"]
    )

    # 4. LOG RESULT TO FILE
    if result:
        res_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timetable_result.txt')
        with open(res_file, 'w') as f:
            for c_idx in range(raw_data["No_of_classes"]):
                f.write(f"\n--- CLASS {c_idx} ---\n")
                for d in range(raw_data["days"]):
                    day_row = [str(result[d * 6 + p][c_idx]) for p in range(6)]
                    f.write(f"Day {d+1}: {' | '.join(day_row)}\n")
        print(f"Success! Check results in: {res_file}")
    else:
        print("No solution found. Check solver_debug.log")
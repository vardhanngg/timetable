import random
import copy
import csv

def generate_timetable(
    No_of_classes,
    No_of_days_in_week,
    No_of_periods,
    teacher_list,
    class_teacher_periods,
    lab_teacher_periods,
    subject_map,
    fixed_periods=None  # Added this parameter
):
    random.seed(10)

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
    # Track workload already covered by fixed slots to subtract later
    teacher_fixed_workload = {c: {t: 0 for t in teacher_list} for c in range(No_of_classes)}
    class_fixed_total = [0] * No_of_classes

    if fixed_periods:
        # fixed_periods: { "ClassIdx": { "Day-Period": {"label": "Lunch", "teacher_id": "0"} } }
        for cls_idx_str, slots in fixed_periods.items():
            try:
                cls_idx = int(cls_idx_str)
            except ValueError:
                continue # Skip if class index is invalid
            
            for slot_str, info in slots.items():
                # Only process if there is a Label (e.g., "Lunch", "Library")
                if not info.get('label') or info.get('label').strip() == "":
                    continue
                
                try:
                    d, p = map(int, slot_str.split('-'))
                    flat_slot = d * No_of_periods + p
                except (ValueError, IndexError):
                    continue

                # 1. Pre-fill the Timetable matrix for this specific class
                Timetable[flat_slot][cls_idx] = info['label']
                class_fixed_total[cls_idx] += 1
                
                # 2. Handle Teacher Blocking
                t_id_raw = info.get('teacher_id', "None")
                
                # We check if it's a digit to avoid crashes from "None" or empty strings
                if t_id_raw is not None and str(t_id_raw).isdigit():
                    t_id = int(t_id_raw)
                    
                    # Safety check: Ensure the teacher exists in our list
                    if t_id in main_teacher_list[flat_slot]:
                        # Block teacher for EVERYONE else at this time slot
                        main_teacher_list[flat_slot][t_id]["available"] = False
                        
                        # Track that this teacher has already "worked" this hour 
                        # so the solver doesn't give them extra theory later
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

    # ---------------- LAB ASSIGNMENT (UNCHANGED) ----------------
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

    # ---------------- 3. CREDIT MATRIX (DYNAMIC FREE CALC) ----------------
    FREE_TEACHERS = [
        t_id for t_id, info in teacher_list.items()
        if info["Name"].startswith("f")
    ]

    class_to_teacher = []
    for class_idx in range(No_of_classes):
        teacher_part = [0] * No_of_teachers
        assigned_workload = 0
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            # SUBTRACT: Required - Fixed
            fixed_already = teacher_fixed_workload[class_idx].get(t_idx, 0)
            net_needed = max(0, periods - fixed_already)
            teacher_part[t_idx] = net_needed
            assigned_workload += net_needed

        assigned_labs = 0
        if class_idx in lab_teacher_periods:
            for t_id, info in lab_teacher_periods[class_idx].items():
                teacher_part[t_id] += info[0]
                assigned_labs += info[0]

        # CHANGE 3: Logic: Total - (Net Theory) - Labs - (Total Fixed Slots for this class)
        free_count = total_periods - assigned_workload - assigned_labs - class_fixed_total[class_idx]
        if free_count < 0:
            free_count = 0

        free_teacher_index = FREE_TEACHERS[class_idx % len(FREE_TEACHERS)]
        teacher_part[free_teacher_index] = free_count

        priority_list = list(range(No_of_teachers))
        row = teacher_part.copy()
        row.append(priority_list)
        class_to_teacher.append(row)

    # ---------------- MRV & BACKTRACKING (UNCHANGED) ----------------
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

    reset_lab_day_usage()
    assign_lab_periods_randomly()

    if solve():
        return Timetable

    return None
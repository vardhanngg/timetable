import random
import copy
import csv
import logging
import os

# Configure logging to overwrite the file each time you run the solver
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solver_debug.log')
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

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
    
    # FIX: Determine size based on the highest ID present to avoid IndexError.
    # If a filler teacher has ID 1001, we need a list of size 1002.
    max_t_id = max(teacher_list.keys()) if teacher_list else 0
    No_of_teachers = max_t_id + 1

    # ---------------- TIMETABLE MATRIX ----------------
    Timetable = [[0 for _ in range(No_of_classes)] for _ in range(total_periods)]

    # ---------------- TEACHER STATE ----------------
    main_teacher_list = [
        copy.deepcopy(teacher_list)
        for _ in range(total_periods)
    ]

    # ---------------- 1 & 4. COORDINATE MAPPING & PRE-FILLING ----------------
    # Use a dictionary or a large list for teacher_fixed_workload to handle high IDs
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
                    # Handle flat slot index from app.py or d-p format
                    if '-' in slot_str:
                        d, p = map(int, slot_str.split('-'))
                        flat_slot = d * No_of_periods + p
                    else:
                        flat_slot = int(slot_str)
                except (ValueError, IndexError):
                    continue

                if flat_slot < total_periods and cls_idx < No_of_classes:
                    Timetable[flat_slot][cls_idx] = info['label']
                    class_fixed_total[cls_idx] += 1
                    
                    t_id_raw = info.get('teacher_id')
                    if t_id_raw is not None and str(t_id_raw).isdigit():
                        t_id = int(t_id_raw)
                        if t_id in main_teacher_list[flat_slot]:
                            main_teacher_list[flat_slot][t_id]["available"] = False
                            teacher_fixed_workload[cls_idx][t_id] = teacher_fixed_workload[cls_idx].get(t_id, 0) + 1

    # ---------------- CREDIT MATRIX (WORKLOAD MAPPING) ----------------
    class_to_teacher = []
    for class_idx in range(No_of_classes):
        # Initialize with the expanded size to accommodate high IDs
        teacher_part = [0] * No_of_teachers
        active_teacher_ids = list(teacher_list.keys())
        
        # 1. Theory Workload
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            fixed_already = teacher_fixed_workload[class_idx].get(t_idx, 0)
            teacher_part[t_idx] = max(0, periods - fixed_already)

        # 2. Lab Workload
        if class_idx in lab_teacher_periods:
            for t_id, info in lab_teacher_periods[class_idx].items():
                # Add lab hours to the theory tracking for simple solving
                teacher_part[t_id] += info[0]

        # Use the actual IDs for the priority list instead of range(No_of_teachers)
        # to avoid iterating over 1000 empty slots during solving
        row = teacher_part.copy()
        row.append(active_teacher_ids) 
        class_to_teacher.append(row)

    # ---------------- LAB HELPERS ----------------
    labs = {}
    lab_used_by_class_per_day = {idx: {} for idx in range(No_of_classes)}

    def assign_lab_periods_randomly():
        for class_idx, teacher_periods in lab_teacher_periods.items():
            for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():
                labs.setdefault(lab_number, [])
                available_slots = [
                    i for i in range(total_periods)
                    if Timetable[i][class_idx] == 0
                    and main_teacher_list[i][teacher_id]["available"]
                ]
                random.shuffle(available_slots)
                sessions_assigned = 0
                for slot in available_slots:
                    if slot + consecutive_periods > total_periods: continue
                    can_assign = True
                    for i in range(consecutive_periods):
                        day = (slot + i) // No_of_periods
                        if (Timetable[slot + i][class_idx] != 0 or
                            not main_teacher_list[slot + i][teacher_id]["available"] or
                            (slot // No_of_periods) != day or
                            (slot + i) in labs[lab_number] or
                            lab_number in lab_used_by_class_per_day[class_idx].get(day, set())):
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
                            lab_used_by_class_per_day[class_idx].setdefault(day, set()).add(lab_number)
                        sessions_assigned += 1
                    if sessions_assigned == total_sessions: break

    # ---------------- SOLVER CORE ----------------
    def find_empty():
        best_cell = (-1, -1)
        min_teachers = float("inf")
        rows = list(range(total_periods))
        random.shuffle(rows)
        for x in rows:
            for y in range(No_of_classes):
                if Timetable[x][y] == 0:
                    count = 0
                    active_ids = class_to_teacher[y][-1]
                    for i in active_ids:
                        if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                            count += 1
                    if count == 0: return x, y
                    if count < min_teachers:
                        min_teachers = count
                        best_cell = (x, y)
        return best_cell

    def solve():
        x, y = find_empty()
        if x == -1: return True
        
        priority = class_to_teacher[y][-1][:]
        random.shuffle(priority)
        for i in priority:
            if class_to_teacher[y][i] > 0 and main_teacher_list[x][i]["available"]:
                t_name = teacher_list[i]["Name"]
                class_to_teacher[y][i] -= 1
                main_teacher_list[x][i]["available"] = False
                Timetable[x][y] = subject_map.get((y, i), t_name)
                
                if solve(): return True
                
                Timetable[x][y] = 0
                class_to_teacher[y][i] += 1
                main_teacher_list[x][i]["available"] = True
        return False

    assign_lab_periods_randomly()
    if solve():
        return Timetable
    return None
import random
import copy
import csv
import logging
import os
import sys

sys.setrecursionlimit(50000)

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
    # ── BASIC CONFIG ──────────────────────────────────────────────────────────
    total_periods = No_of_days_in_week * No_of_periods

    max_t_id     = max(teacher_list.keys()) if teacher_list else 0
    No_of_teachers = max_t_id + 1

    # ── TIMETABLE MATRIX ──────────────────────────────────────────────────────
    Timetable = [[0 for _ in range(No_of_classes)] for _ in range(total_periods)]

    # ── TEACHER AVAILABILITY (per-slot copy) ──────────────────────────────────
    main_teacher_list = [copy.deepcopy(teacher_list) for _ in range(total_periods)]

    # ── PRE-FILL FIXED SLOTS ──────────────────────────────────────────────────
    # adapter.py already deducted hours from subject_map / class_teacher_periods.
    # Here we ONLY stamp the timetable and mark teachers unavailable.
    # We do NOT reduce hours again — that would cause double-deduction.
    if fixed_periods:
        for cls_idx_str, slots in fixed_periods.items():
            try:
                cls_idx = int(cls_idx_str)
            except ValueError:
                continue

            for slot_str, info in slots.items():
                label    = (info.get('label') or '').strip()
                t_id_raw = info.get('teacher_id', '')
                is_free  = info.get('is_free', False) or str(t_id_raw) == '__free__'
                is_event = info.get('is_event', False) or str(t_id_raw) == '__event__'

                # Skip un-set slots
                if not label or str(t_id_raw) == '__none__':
                    continue

                # Parse flat slot index
                try:
                    if '-' in slot_str:
                        d, p = map(int, slot_str.split('-'))
                        flat_slot = d * No_of_periods + p
                    else:
                        flat_slot = int(slot_str)
                except Exception:
                    logging.warning(f"Bad slot key '{slot_str}' — skipping")
                    continue

                if flat_slot < 0 or flat_slot >= total_periods:
                    logging.warning(f"Slot {flat_slot} out of range — skipping")
                    continue

                # Stamp timetable
                Timetable[flat_slot][cls_idx] = label
                logging.debug(f"Pre-filled Class {cls_idx} slot {flat_slot} = '{label}'")

                # Mark teacher unavailable
                if is_event:
                    pass  # No teacher linked — nobody's availability changes
                elif is_free:
                    f_id = 1000 + cls_idx
                    if f_id in main_teacher_list[flat_slot]:
                        main_teacher_list[flat_slot][f_id]["available"] = False
                elif str(t_id_raw).lstrip('-').isdigit():
                    t_id = int(t_id_raw)
                    if t_id in main_teacher_list[flat_slot]:
                        if not main_teacher_list[flat_slot][t_id]["available"]:
                            logging.error(
                                f"COLLISION: Teacher {t_id} already busy at slot {flat_slot} "
                                f"(Class {cls_idx})"
                            )
                            return None
                        main_teacher_list[flat_slot][t_id]["available"] = False

    # ── CREDIT MATRIX (remaining workload after fixed deductions) ────────────
    class_to_teacher = []
    for class_idx in range(No_of_classes):
        credits = {}
        active_teacher_ids = list(teacher_list.keys())
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            credits[t_idx] = max(0, periods)
        if class_idx in lab_teacher_periods:
            for t_id, info in lab_teacher_periods[class_idx].items():
                credits[t_id] = credits.get(t_id, 0) + info[0]
        credits['__ids__'] = active_teacher_ids
        class_to_teacher.append(credits)

    # ── LAB HELPERS ───────────────────────────────────────────────────────────
    labs = {}
    lab_used_by_class_per_day = {idx: {} for idx in range(No_of_classes)}

    def assign_lab_periods_randomly():
        for class_idx, teacher_periods in lab_teacher_periods.items():
            for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():
                labs.setdefault(lab_number, [])
                available_slots = [
                    i for i in range(total_periods)
                    if Timetable[i][class_idx] == 0
                    and teacher_id in main_teacher_list[i]
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
                        if (Timetable[slot + i][class_idx] != 0 or
                                not main_teacher_list[slot + i][teacher_id]["available"] or
                                (slot // No_of_periods) != day or
                                (slot + i) in labs[lab_number] or
                                lab_number in lab_used_by_class_per_day[class_idx].get(day, set())):
                            can_assign = False
                            break
                    if can_assign:
                        subject_name = "Lab"
                        if class_idx in subject_map and teacher_id in subject_map[class_idx]:
                            for sub in subject_map[class_idx][teacher_id]:
                                if sub["type"] == "lab":
                                    subject_name = sub["name"]
                                    break
                        for i in range(consecutive_periods):
                            Timetable[slot + i][class_idx] = f"{subject_name} (Lab {lab_number})"
                            main_teacher_list[slot + i][teacher_id]["available"] = False
                            if teacher_id in class_to_teacher[class_idx]:
                                class_to_teacher[class_idx][teacher_id] -= 1
                            labs[lab_number].append(slot + i)
                            day = (slot + i) // No_of_periods
                            lab_used_by_class_per_day[class_idx].setdefault(day, set()).add(lab_number)
                        sessions_assigned += consecutive_periods
                    if sessions_assigned >= total_sessions:
                        break

    # ── SOLVER CORE ───────────────────────────────────────────────────────────
    def find_empty():
        # MRV heuristic: return the empty cell with fewest available teachers.
        # Cells with 0 options are returned immediately to force a fast backtrack.
        best_cell = (-1, -1)
        min_count = float("inf")
        rows = list(range(total_periods))
        random.shuffle(rows)
        for x in rows:
            for y in range(No_of_classes):
                if Timetable[x][y] == 0:
                    count = 0
                    active_ids = class_to_teacher[y]['__ids__']
                    for i in active_ids:
                        if class_to_teacher[y].get(i, 0) > 0 and main_teacher_list[x][i]["available"]:
                            count += 1
                    if count < min_count:
                        min_count = count
                        best_cell = (x, y)
                        if count == 0:
                            return best_cell  # can't do better, backtrack immediately
        return best_cell

    def subject_already_on_day(class_idx, slot, subject_name):
        """Return True if subject_name already appears on the same day for class_idx."""
        day = slot // No_of_periods
        day_start = day * No_of_periods
        day_end   = day_start + No_of_periods
        for s in range(day_start, day_end):
            if Timetable[s][class_idx] == subject_name:
                return True
        return False

    def solve(depth=0):
        x, y = find_empty()
        if x == -1:
            return True

        if depth % 50 == 0:
            logging.debug(f"Solving Slot {x}, Class {y}. Depth: {depth}")

        priority = class_to_teacher[y]['__ids__'][:]
        random.shuffle(priority)

        for i in priority:
            if class_to_teacher[y].get(i, 0) > 0 and main_teacher_list[x][i]["available"]:
                t_name = teacher_list[i]["Name"]

                assigned_name = t_name
                sub_ptr = None
                if y in subject_map and i in subject_map[y]:
                    for sub in subject_map[y][i]:
                        if sub["type"] == "theory" and sub["hours"] > 0:
                            assigned_name = sub["name"]
                            sub_ptr = sub
                            break

                if assigned_name != "Free" and subject_already_on_day(y, x, assigned_name):
                    continue

                class_to_teacher[y][i] -= 1
                main_teacher_list[x][i]["available"] = False
                if sub_ptr:
                    sub_ptr["hours"] -= 1
                Timetable[x][y] = assigned_name

                if solve(depth + 1):
                    return True

                logging.warning(f"Backtracking Slot {x}, Class {y}, Teacher {t_name}")
                Timetable[x][y] = 0
                class_to_teacher[y][i] += 1
                main_teacher_list[x][i]["available"] = True
                if sub_ptr:
                    sub_ptr["hours"] += 1

        return False

    assign_lab_periods_randomly()
    if solve():
        return Timetable
    return None


def generate_timetable_with_retry(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, max_attempts=10
):
    """Retry wrapper — solver is randomized, so a different shuffle may succeed."""
    import copy as _copy
    for attempt in range(1, max_attempts + 1):
        logging.info(f"Solver attempt {attempt}/{max_attempts}")
        # Deep copy inputs so each attempt starts fresh
        result = generate_timetable(
            No_of_classes, No_of_days_in_week, No_of_periods,
            _copy.deepcopy(teacher_list),
            _copy.deepcopy(class_teacher_periods),
            _copy.deepcopy(lab_teacher_periods),
            _copy.deepcopy(subject_map),
            fixed_periods
        )
        if result is not None:
            logging.info(f"Solved on attempt {attempt}")
            return result
        logging.warning(f"Attempt {attempt} failed, retrying...")
    logging.error("All attempts exhausted — unsolvable with current constraints")
    return None
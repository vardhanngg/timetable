import random
import copy
import logging
import os
import json

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solver_debug.log')
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
    logging.info("OR-Tools loaded successfully")
except ImportError:
    ORTOOLS_AVAILABLE = False
    logging.warning("OR-Tools not installed. Falling back to backtracking solver.")


# ═══════════════════════════════════════════════════════════════════════════════
#  OR-TOOLS CP-SAT SOLVER
# ═══════════════════════════════════════════════════════════════════════════════

def generate_timetable_ortools(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, teacher_unavailability=None,
    time_limit_seconds=60, elective_bundles=None
):
    total_slots = No_of_days_in_week * No_of_periods
    model = cp_model.CpModel()

    # ── STEP 1: Pre-fill fixed slots ─────────────────────────────────────────
    Timetable = [[0] * No_of_classes for _ in range(total_slots)]
    fixed_set = set()
    teacher_busy = {tid: set() for tid in teacher_list}

    # ── Inject teacher unavailability into teacher_busy ─────────────────────
    if teacher_unavailability:
        for tid_str, slots in teacher_unavailability.items():
            try:
                tid = int(tid_str)
            except ValueError:
                continue
            if tid not in teacher_busy:
                teacher_busy[tid] = set()
            for slot_str in slots:
                try:
                    if '-' in str(slot_str):
                        d, p = map(int, str(slot_str).split('-'))
                        flat = d * No_of_periods + p
                    else:
                        flat = int(slot_str)
                    if 0 <= flat < total_slots:
                        teacher_busy[tid].add(flat)
                except Exception:
                    continue

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

                if not label or str(t_id_raw) == '__none__':
                    continue
                try:
                    if '-' in slot_str:
                        d, p = map(int, slot_str.split('-'))
                        flat_slot = d * No_of_periods + p
                    else:
                        flat_slot = int(slot_str)
                except Exception:
                    continue
                if flat_slot < 0 or flat_slot >= total_slots:
                    continue

                Timetable[flat_slot][cls_idx] = label
                fixed_set.add((flat_slot, cls_idx))

                if not is_event and not is_free and str(t_id_raw).lstrip('-').isdigit():
                    t_id = int(t_id_raw)
                    if t_id in teacher_busy:
                        if flat_slot in teacher_busy[t_id]:
                            logging.error(f"Fixed slot collision: Teacher {t_id} slot {flat_slot}")
                            return None
                        teacher_busy[t_id].add(flat_slot)
                elif is_free:
                    f_id = 1000 + cls_idx
                    teacher_busy.setdefault(f_id, set()).add(flat_slot)

    # ── STEP 2: Place labs greedily (consecutive blocks) ─────────────────────
    labs = {}
    lab_used_by_class_per_day = {idx: {} for idx in range(No_of_classes)}
    lab_shortfalls = []  # collects any lab that didn't get its full hours placed

    for class_idx, teacher_periods in lab_teacher_periods.items():
        for teacher_id, (total_hours, consecutive_periods, lab_number) in teacher_periods.items():
            # total_hours is the total lab hours for the semester/week.
            # Each block uses consecutive_periods slots, so number of blocks to place:
            consecutive_periods_i = max(1, int(consecutive_periods))
            num_blocks = max(1, int(total_hours) // consecutive_periods_i)
            if int(total_hours) % consecutive_periods_i != 0:
                logging.warning(
                    f"Class {class_idx}, teacher {teacher_id}, lab {lab_number}: "
                    f"{total_hours}h does not divide evenly into {consecutive_periods_i}-period blocks — "
                    f"only {num_blocks * consecutive_periods_i}h will be schedulable, "
                    f"{total_hours - num_blocks * consecutive_periods_i}h will be lost. Check the extracted hours."
                )
            labs.setdefault(lab_number, [])
            available_slots = [
                s for s in range(total_slots)
                if Timetable[s][class_idx] == 0
                and s not in teacher_busy.get(teacher_id, set())
            ]
            random.shuffle(available_slots)
            sessions_assigned = 0
            for slot in available_slots:
                if slot + consecutive_periods_i > total_slots:
                    continue
                can_assign = True
                for i in range(consecutive_periods_i):
                    day = (slot + i) // No_of_periods
                    if (Timetable[slot + i][class_idx] != 0 or
                            (slot + i) in teacher_busy.get(teacher_id, set()) or
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
                    for i in range(consecutive_periods_i):
                        s = slot + i
                        Timetable[s][class_idx] = f"{subject_name} (Lab {lab_number})"
                        fixed_set.add((s, class_idx))
                        teacher_busy.setdefault(teacher_id, set()).add(s)
                        labs[lab_number].append(s)
                        day = s // No_of_periods
                        lab_used_by_class_per_day[class_idx].setdefault(day, set()).add(lab_number)
                    sessions_assigned += 1  # one block = one session
                if sessions_assigned >= num_blocks:
                    break

            # This used to fail silently: if there weren't enough conflict-free
            # slots to place every block, the loop just stopped and the caller
            # got back a "successful" timetable with fewer lab hours than
            # requested. Surface it loudly instead.
            if sessions_assigned < num_blocks:
                subject_name = "Lab"
                if class_idx in subject_map and teacher_id in subject_map[class_idx]:
                    for sub in subject_map[class_idx][teacher_id]:
                        if sub["type"] == "lab":
                            subject_name = sub["name"]
                            break
                missing_hours = (num_blocks - sessions_assigned) * consecutive_periods_i
                msg = (f"Class {class_idx} — '{subject_name}' (Lab {lab_number}, teacher {teacher_id}): "
                       f"only placed {sessions_assigned}/{num_blocks} block(s), "
                       f"{missing_hours}h missing from the timetable.")
                logging.error(f"LAB SHORTFALL: {msg}")
                lab_shortfalls.append({
                    "class_idx": class_idx, "teacher_id": teacher_id, "lab_number": lab_number,
                    "subject": subject_name, "blocks_requested": num_blocks,
                    "blocks_placed": sessions_assigned, "hours_missing": missing_hours
                })

    if lab_shortfalls:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab_scheduling_warnings.json"), "w") as f:
                json.dump(lab_shortfalls, f, indent=2)
        except Exception as e:
            logging.error(f"Could not write lab_scheduling_warnings.json: {e}")

    # ── STEP 3: Build subject entries per class ───────────────────────────────
    # class_entries[cidx] = list of {teacher_id, name, type, hours}
    class_entries = {}
    for cidx in range(No_of_classes):
        class_entries[cidx] = []
        if cidx in subject_map:
            for tid, subs in subject_map[cidx].items():
                for sub in subs:
                    if sub["type"] == "theory" and sub["hours"] > 0:
                        class_entries[cidx].append({
                            "teacher_id": tid,
                            "name": sub["name"],
                            "hours": sub["hours"]
                        })

    bundle_slot_indicators_by_name = {}  # bname -> {slot: BoolVar} for sync-scoped teacher constraints

    # ── STEP 4: Create boolean decision variables ─────────────────────────────
    # assign_vars[cidx][slot] = list of (entry_idx, BoolVar)
    assign_vars = {}
    for cidx in range(No_of_classes):
        assign_vars[cidx] = {}
        for slot in range(total_slots):
            if (slot, cidx) in fixed_set:
                continue
            slot_vars = []
            for eidx, entry in enumerate(class_entries[cidx]):
                v = model.NewBoolVar(f"c{cidx}_s{slot}_e{eidx}")
                slot_vars.append((eidx, v))
            assign_vars[cidx][slot] = slot_vars
            # Exactly one subject per empty slot
            if slot_vars:
                model.AddExactlyOne([v for _, v in slot_vars])

    # ── STEP 5: Hour budget — each subject assigned exactly its hours ─────────
    for cidx in range(No_of_classes):
        for eidx, entry in enumerate(class_entries[cidx]):
            vars_for_entry = [
                v for slot, slot_vars in assign_vars[cidx].items()
                for ei, v in slot_vars if ei == eidx
            ]
            if vars_for_entry:
                model.Add(sum(vars_for_entry) == entry["hours"])

    # ── STEP 6: Teacher conflict — one class per teacher per slot ─────────────
    # Exception: sync groups (both "merged" AND "split") may have the same teacher
    # serving multiple classes at the same sync slot — e.g. S7 teaches Awareness
    # to Class 2 and Class 3 simultaneously (different rooms, same time).
    # We collect those teachers and exempt them from AddAtMostOne ONLY for
    # the slots that the sync group's indicator variables actually choose.
    # Since we don't know those slots yet (solver picks them), we defer:
    # instead we add a softer constraint: for synced teacher-slot pairs,
    # allow AT MOST len(members_with_that_teacher) vars to be 1.
    #
    # Implementation: build a map of (tid → max_simultaneous_classes) from
    # sync groups, then use AddAtMost(max) instead of AddAtMostOne.
    teacher_sync_max = {}   # tid → max simultaneous classes allowed (default 1)
    if elective_bundles:
        for bundle in elective_bundles:
            members = bundle.get("members", [])
            # Count how many members share each teacher
            tid_count = {}
            for m in members:
                tid_str = str(m.get("teacherId") or "")
                if tid_str and tid_str.lstrip("-").isdigit():
                    tid_count[int(tid_str)] = tid_count.get(int(tid_str), 0) + 1
            for tid, cnt in tid_count.items():
                if cnt > 1:
                    teacher_sync_max[tid] = max(teacher_sync_max.get(tid, 1), cnt)

    slot_teacher_vars = {}
    for cidx in range(No_of_classes):
        for slot, slot_vars in assign_vars[cidx].items():
            for eidx, v in slot_vars:
                tid = class_entries[cidx][eidx]["teacher_id"]
                slot_teacher_vars.setdefault((slot, tid), []).append(v)

    # Block vars for teachers already busy at a slot (from fixed/labs)
    for tid, busy_slots in teacher_busy.items():
        for slot in busy_slots:
            for v in slot_teacher_vars.get((slot, tid), []):
                model.Add(v == 0)

    # At most N classes per teacher per slot (N=1 normally, N>1 for sync-group shared teachers)
    # For sync-group shared teachers we allow N simultaneous classes, but ONLY when the
    # sync-group bundle indicator is active. Outside sync slots they must stay at 1.
    # Build a map: (slot, tid) -> [bundle_indicator_var] for sync-linked teachers
    sync_teacher_slot_bv = {}  # (slot, tid) -> list of bundle BoolVars active at that slot
    if elective_bundles:
        for bundle in elective_bundles:
            bname = bundle.get("name", "")
            bv_map = bundle_slot_indicators_by_name.get(bname, {})
            members = bundle.get("members", [])
            tid_count = {}
            for m in members:
                tid_str = str(m.get("teacherId") or "")
                if tid_str and tid_str.lstrip("-").isdigit():
                    tid = int(tid_str)
                    tid_count[tid] = tid_count.get(tid, 0) + 1
            shared_tids = {tid for tid, cnt in tid_count.items() if cnt > 1}
            for slot, bv in bv_map.items():
                for tid in shared_tids:
                    sync_teacher_slot_bv.setdefault((slot, tid), []).append(bv)

    for (slot, tid), var_list in slot_teacher_vars.items():
        max_allowed = teacher_sync_max.get(tid, 1)
        if len(var_list) <= 1:
            continue
        if max_allowed == 1:
            model.AddAtMostOne(var_list)
        else:
            # Shared teacher: allow N simultaneous ONLY when a sync indicator is active
            bvs = sync_teacher_slot_bv.get((slot, tid), [])
            if bvs:
                # When any sync indicator is active at this slot, allow up to max_allowed
                # When no sync indicator is active, enforce AtMostOne
                sync_active = model.NewBoolVar(f"sync_active_s{slot}_t{tid}")
                model.AddMaxEquality(sync_active, bvs)
                # If sync NOT active -> at most 1
                model.Add(sum(var_list) <= 1).OnlyEnforceIf(sync_active.Not())
                # If sync active -> at most max_allowed
                model.Add(sum(var_list) <= max_allowed).OnlyEnforceIf(sync_active)
            else:
                model.Add(sum(var_list) <= max_allowed)

    # ── STEP 7: No repeat subject on same day ─────────────────────────────────
    for cidx in range(No_of_classes):
        for eidx, entry in enumerate(class_entries[cidx]):
            if entry["name"] == "Free":
                continue
            for day in range(No_of_days_in_week):
                day_vars = [
                    v for p in range(No_of_periods)
                    for slot in [day * No_of_periods + p]
                    if slot in assign_vars[cidx]
                    for ei, v in assign_vars[cidx][slot] if ei == eidx
                ]
                if day_vars:
                    model.Add(sum(day_vars) <= 1)

    # ── STEP 7b: Sync Group constraints ──────────────────────────────────────
    # For each sync group, all member subjects must be placed at the SAME K slots.
    # Works for both:
    #   split  — different subjects/teachers firing simultaneously
    #   merged — same subject shared across classes (same teacher in multiple classes)
    if elective_bundles:
        for bundle in elective_bundles:
            bname    = bundle.get("name", "bundle")
            btype    = bundle.get("type", "split")
            k        = int(bundle.get("periodsPerWeek", bundle.get("periods_per_week", 1)))
            members  = bundle.get("members", [])
            # Fall back to assignments dict if members not provided (backward compat)
            if not members:
                for ci_raw, subj in bundle.get("assignments", {}).items():
                    members.append({"classIdx": int(ci_raw), "subject": subj, "teacherId": None})
            if not members or k < 1:
                continue

            involved_cidxs = list({int(m["classIdx"]) for m in members if int(m.get("classIdx", 999)) < No_of_classes})

            # For single-class splits (e.g. "II Language" with subs a+b in one class):
            # The block subject is already in class_entries as "II Language" (3h),
            # carrying only ONE teacher_id (the "primary" sub-option's teacher — see
            # app.py /update-data). The OTHER sub-teachers never appear as a teacher_id
            # on any class_entries row, so without an explicit constraint here the
            # solver has literally no way to know they're busy whenever the block is
            # scheduled — they could get assigned to teach a different class at the
            # exact same slot. We fix that below by forcing every other class's use of
            # those sub-teacher ids to zero whenever this class's block var is 1.
            # For multi-class splits: full cross-class sync constraint is applied below.
            if len(involved_cidxs) < 2:
                cidx = involved_cidxs[0] if involved_cidxs else -1
                block_name = (members[0].get('subject') or '').strip()
                if cidx < 0 or cidx >= No_of_classes or not block_name:
                    logging.warning(f"Sync group '{bname}': single-class split — could not resolve class/block, sub-teachers NOT locked")
                    continue

                eidx_for_block = None
                for eidx, entry in enumerate(class_entries[cidx]):
                    if entry["name"].lower().strip() == block_name.lower().strip():
                        eidx_for_block = eidx
                        break
                if eidx_for_block is None:
                    logging.warning(f"Sync group '{bname}': block '{block_name}' not found in class {cidx} entries — sub-teachers NOT locked")
                    continue

                primary_tid = class_entries[cidx][eidx_for_block]["teacher_id"]
                sub_tids = {
                    int(m['teacherId']) for m in members
                    if str(m.get('teacherId') or '').lstrip('-').isdigit()
                    and int(m['teacherId']) != primary_tid
                }

                locked_pairs = 0
                for slot, slot_vars in assign_vars[cidx].items():
                    block_vars = [v for ei, v in slot_vars if ei == eidx_for_block]
                    if not block_vars:
                        continue
                    block_v = block_vars[0]
                    for tid in sub_tids:
                        other_vars = slot_teacher_vars.get((slot, tid), [])
                        if other_vars:
                            model.Add(sum(other_vars) == 0).OnlyEnforceIf(block_v)
                            locked_pairs += 1

                logging.info(f"Sync group '{bname}': single-class split — locked {len(sub_tids)} sub-teacher(s) "
                             f"to block '{block_name}' in class {cidx} ({locked_pairs} slot constraints added)")
                continue

            # Slot indicators: True iff this slot is one of K shared bundle slots
            bundle_slot_indicators = {}
            for slot in range(total_slots):
                if any((slot, ci) in fixed_set for ci in involved_cidxs):
                    continue
                bv = model.NewBoolVar(f"sg_{bname}_slot{slot}".replace(" ", "_"))
                bundle_slot_indicators[slot] = bv

            if not bundle_slot_indicators:
                logging.warning(f"Sync group '{bname}': no free slots available")
                continue

            # Store by name so teacher-conflict step can scope relaxation to sync slots
            bundle_slot_indicators_by_name[bname] = bundle_slot_indicators

            model.Add(sum(bundle_slot_indicators.values()) == k)

            for m in members:
                cidx         = int(m.get("classIdx", -1))
                subj_name    = (m.get("subject") or "").strip()
                if cidx < 0 or cidx >= No_of_classes or not subj_name:
                    continue

                eidx_for_subj = None
                for eidx, entry in enumerate(class_entries[cidx]):
                    if entry["name"].lower().strip() == subj_name.lower().strip():
                        eidx_for_subj = eidx
                        break
                if eidx_for_subj is None:
                    logging.error(
                        f"Sync group '{bname}': subject '{subj_name}' not found in class {cidx}. "
                        f"Available subjects: {[e['name'] for e in class_entries[cidx]]}. "
                        f"Check that class indices in the sync group match the actual classes that have this subject."
                    )
                    # Return None so the caller gets a clear failure rather than a corrupted timetable
                    return None

                for slot, bv in bundle_slot_indicators.items():
                    if slot not in assign_vars[cidx]:
                        model.Add(bv == 0)
                        continue
                    elec_vars = [v for ei, v in assign_vars[cidx][slot] if ei == eidx_for_subj]
                    if not elec_vars:
                        model.Add(bv == 0)
                        continue
                    elec_v = elec_vars[0]
                    model.AddImplication(bv, elec_v)
                    model.AddImplication(elec_v, bv)

            logging.info(f"Sync group '{bname}' ({btype}): {k} shared slots, {len(members)} members constrained")

    # ── STEP 8: Solve ─────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers  = 8
    solver.parameters.log_search_progress = False

    logging.info(f"CP-SAT solving: {No_of_classes} classes, {total_slots} slots, {time_limit_seconds}s limit")
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logging.error(f"CP-SAT failed: {solver.StatusName(status)}")
        return None

    logging.info(f"CP-SAT done: {solver.StatusName(status)} in {solver.WallTime():.2f}s")

    # ── STEP 9: Extract into Timetable matrix ─────────────────────────────────
    # Build a map: (cidx, subject_name_lower) -> bundle_display_name
    # so that sync-group sub-subjects show the block name (e.g. "2nd Language")
    subj_to_block = {}
    if elective_bundles:
        for bundle in elective_bundles:
            bname   = bundle.get('name', '')
            for m in bundle.get('members', []):
                cidx_m = int(m.get('classIdx', -1))
                subj_m = (m.get('subject') or '').lower().strip()
                if cidx_m >= 0 and subj_m and bname:
                    subj_to_block[(cidx_m, subj_m)] = bname

    for cidx in range(No_of_classes):
        for slot, slot_vars in assign_vars[cidx].items():
            for eidx, v in slot_vars:
                if solver.Value(v) == 1:
                    raw_name = class_entries[cidx][eidx]['name']
                    # Use block display name if this subject belongs to a split group
                    display = subj_to_block.get((cidx, raw_name.lower().strip()), raw_name)
                    Timetable[slot][cidx] = display
                    break

    return Timetable


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTRACKING SOLVER (fallback)
# ═══════════════════════════════════════════════════════════════════════════════

import sys
sys.setrecursionlimit(50000)

def generate_timetable_backtrack(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, teacher_unavailability=None,
    elective_bundles=None
):
    import time as _time
    _start_time = _time.time()
    _TIME_LIMIT  = 45  # seconds per attempt before giving up and retrying
    total_periods = No_of_days_in_week * No_of_periods
    Timetable = [[0] * No_of_classes for _ in range(total_periods)]
    main_teacher_list = [copy.deepcopy(teacher_list) for _ in range(total_periods)]

    # ── Inject teacher unavailability — mark teacher as busy at those slots ──
    if teacher_unavailability:
        for tid_str, slots in teacher_unavailability.items():
            try:
                tid = int(tid_str)
            except ValueError:
                continue
            for slot_str in slots:
                try:
                    if '-' in str(slot_str):
                        d, p = map(int, str(slot_str).split('-'))
                        flat = d * No_of_periods + p
                    else:
                        flat = int(slot_str)
                    if 0 <= flat < total_periods and tid in main_teacher_list[flat]:
                        main_teacher_list[flat][tid]['available'] = False
                except Exception:
                    continue

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
                if not label or str(t_id_raw) == '__none__':
                    continue
                try:
                    if '-' in slot_str:
                        d, p = map(int, slot_str.split('-'))
                        flat_slot = d * No_of_periods + p
                    else:
                        flat_slot = int(slot_str)
                except Exception:
                    continue
                if flat_slot < 0 or flat_slot >= total_periods:
                    continue
                Timetable[flat_slot][cls_idx] = label
                if is_event:
                    pass
                elif is_free:
                    f_id = 1000 + cls_idx
                    if f_id in main_teacher_list[flat_slot]:
                        main_teacher_list[flat_slot][f_id]["available"] = False
                elif str(t_id_raw).lstrip('-').isdigit():
                    t_id = int(t_id_raw)
                    if t_id in main_teacher_list[flat_slot]:
                        if not main_teacher_list[flat_slot][t_id]["available"]:
                            return None
                        main_teacher_list[flat_slot][t_id]["available"] = False

    class_to_teacher = []
    for class_idx in range(No_of_classes):
        credits = {}
        active_teacher_ids = list(teacher_list.keys())
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            # Set phantom Free teacher credits to 0 initially — Free is pre-placed
            # before solve() runs, so backtracker must not try to assign Free.
            if isinstance(t_idx, int) and t_idx >= 1000:
                credits[t_idx] = 0
            else:
                credits[t_idx] = max(0, periods)
        # NOTE: lab hours are NOT added to credits here — labs are pre-placed
        # by assign_lab_periods_randomly(). Adding them here would cause the
        # backtracker to try assigning extra theory slots for lab teachers.
        # Exclude phantom Free teacher IDs (>=1000) from backtracking active list.
        # Free periods are pre-placed before solve() runs; including them in __ids__
        # causes useless branching in the backtracker.
        non_free_ids = [tid for tid in active_teacher_ids
                        if not (isinstance(tid, int) and tid >= 1000)]
        credits['__ids__'] = non_free_ids
        class_to_teacher.append(credits)

    labs = {}
    lab_used_by_class_per_day = {idx: {} for idx in range(No_of_classes)}
    lab_shortfalls = []  # collects any lab that didn't get its full hours placed

    def assign_lab_periods_randomly():
        for class_idx, teacher_periods in lab_teacher_periods.items():
            for teacher_id, (total_hours, consecutive_periods, lab_number) in teacher_periods.items():
                # total_hours = total lab hours; num_blocks = how many consecutive blocks to place
                consecutive_periods_i = max(1, int(consecutive_periods))
                num_blocks = max(1, int(total_hours) // consecutive_periods_i)
                if int(total_hours) % consecutive_periods_i != 0:
                    logging.warning(
                        f"Class {class_idx}, teacher {teacher_id}, lab {lab_number}: "
                        f"{total_hours}h does not divide evenly into {consecutive_periods_i}-period blocks — "
                        f"only {num_blocks * consecutive_periods_i}h will be schedulable, "
                        f"{total_hours - num_blocks * consecutive_periods_i}h will be lost. Check the extracted hours."
                    )
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
                    if slot + consecutive_periods_i > total_periods:
                        continue
                    can_assign = True
                    for i in range(consecutive_periods_i):
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
                        for i in range(consecutive_periods_i):
                            Timetable[slot + i][class_idx] = f"{subject_name} (Lab {lab_number})"
                            main_teacher_list[slot + i][teacher_id]["available"] = False
                            if teacher_id in class_to_teacher[class_idx]:
                                class_to_teacher[class_idx][teacher_id] -= 1
                            labs[lab_number].append(slot + i)
                            day = (slot + i) // No_of_periods
                            lab_used_by_class_per_day[class_idx].setdefault(day, set()).add(lab_number)
                        sessions_assigned += 1  # one block = one session
                    if sessions_assigned >= num_blocks:
                        break

                # Silent-failure fix: this used to just stop and hand back a
                # "successful" timetable with fewer lab hours than requested.
                if sessions_assigned < num_blocks:
                    subject_name = "Lab"
                    if class_idx in subject_map and teacher_id in subject_map[class_idx]:
                        for sub in subject_map[class_idx][teacher_id]:
                            if sub["type"] == "lab":
                                subject_name = sub["name"]
                                break
                    missing_hours = (num_blocks - sessions_assigned) * consecutive_periods_i
                    msg = (f"Class {class_idx} — '{subject_name}' (Lab {lab_number}, teacher {teacher_id}): "
                           f"only placed {sessions_assigned}/{num_blocks} block(s), "
                           f"{missing_hours}h missing from the timetable.")
                    logging.error(f"LAB SHORTFALL: {msg}")
                    lab_shortfalls.append({
                        "class_idx": class_idx, "teacher_id": teacher_id, "lab_number": lab_number,
                        "subject": subject_name, "blocks_requested": num_blocks,
                        "blocks_placed": sessions_assigned, "hours_missing": missing_hours
                    })

        if lab_shortfalls:
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab_scheduling_warnings.json"), "w") as f:
                    json.dump(lab_shortfalls, f, indent=2)
            except Exception as e:
                logging.error(f"Could not write lab_scheduling_warnings.json: {e}")

    # Build subject → block display name map for backtracker
    subj_to_block_bt = {}
    # Maps (class_idx, primary_teacher_id) -> (block_name, {sub_teacher_ids}) so that
    # whenever the backtracker assigns the primary teacher to a single-class split
    # block, it also locks the co-teaching sub-teacher(s) at that same slot. Without
    # this, sub-teachers are invisible to the solver's conflict tracking (they never
    # own a class_entries/subject_map row of their own for the block) and can be
    # double-booked onto a different class at the exact same period.
    block_sub_teachers = {}
    if elective_bundles:
        for bundle in elective_bundles:
            bname = bundle.get('name', '')
            for m in bundle.get('members', []):
                cidx_m = int(m.get('classIdx', -1))
                subj_m = (m.get('subject') or '').lower().strip()
                if cidx_m >= 0 and subj_m and bname:
                    subj_to_block_bt[(cidx_m, subj_m)] = bname

    def find_empty():
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
                            return best_cell
        return best_cell

    def subject_already_on_day(class_idx, slot, subject_name):
        day = slot // No_of_periods
        for s in range(day * No_of_periods, day * No_of_periods + No_of_periods):
            if Timetable[s][class_idx] == subject_name:
                return True
        return False

    def solve(depth=0):
        x, y = find_empty()
        if x == -1:
            return True
        # Quick check: if no teacher has remaining hours AND availability for this
        # cell, this branch is a dead end — backtrack immediately.
        active_ids = class_to_teacher[y]['__ids__']
        if not any(
            class_to_teacher[y].get(i, 0) > 0 and main_teacher_list[x][i]["available"]
            for i in active_ids
        ):
            return False
        # Time limit check — abandon this attempt if taking too long
        if _time.time() - _start_time > _TIME_LIMIT:
            logging.warning(f"Backtrack attempt timed out after {_TIME_LIMIT}s at depth {depth}")
            return False
        priority = active_ids[:]
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

                # If this teacher is the "primary" for a single-class split block
                # and this is in fact that block being assigned, lock the
                # co-teaching sub-teacher(s) at this same slot too, so the search
                # can never place them into another class at the same period.
                locked_subs = []
                block_entry = block_sub_teachers.get((y, i))
                if block_entry is not None and block_entry[0] == assigned_name.lower().strip():
                    for sub_tid in block_entry[1]:
                        if sub_tid in main_teacher_list[x] and main_teacher_list[x][sub_tid]["available"]:
                            main_teacher_list[x][sub_tid]["available"] = False
                            locked_subs.append(sub_tid)

                class_to_teacher[y][i] -= 1
                main_teacher_list[x][i]["available"] = False
                if sub_ptr:
                    sub_ptr["hours"] -= 1
                # Use split-block display name if applicable
                display_name = subj_to_block_bt.get((y, assigned_name.lower().strip()), assigned_name)
                Timetable[x][y] = display_name
                if solve(depth + 1):
                    return True
                Timetable[x][y] = 0
                class_to_teacher[y][i] += 1
                main_teacher_list[x][i]["available"] = True
                if sub_ptr:
                    sub_ptr["hours"] += 1
                for sub_tid in locked_subs:
                    main_teacher_list[x][sub_tid]["available"] = True
        return False

    # ── Step 1: Place labs first (consecutive constraint needs max free space) ──
    assign_lab_periods_randomly()

    # ── Step 2: Pre-place sync groups BEFORE Free ────────────────────────────
    # Sync groups need specific slots for multiple classes simultaneously.
    # Must run before Free fills remaining slots randomly.
    # ── Pre-place sync groups ─────────────────────────────────────────────────
    # All members of a sync group must share the SAME K slot indices.
    # We pick K free slots where every member's teacher is available, stamp
    # the subject names, mark teachers busy, and deduct subject_map hours.
    if elective_bundles:
        for bundle in elective_bundles:
            bname   = bundle.get("name", "bundle")
            btype   = bundle.get("type", "split")
            k       = int(bundle.get("periodsPerWeek", bundle.get("periods_per_week", 1)))
            members = bundle.get("members", [])
            # Backward compat: build members from assignments dict if needed
            if not members:
                for ci_raw, subj in bundle.get("assignments", {}).items():
                    members.append({"classIdx": int(ci_raw), "subject": subj, "teacherId": None})
            if not members or k < 1:
                continue

            # Resolve teacher ids for each member from subject_map
            resolved = []
            for m in members:
                cidx      = int(m.get("classIdx", -1))
                subj_name = (m.get("subject") or "").strip()
                tid_hint  = m.get("teacherId")
                if cidx < 0 or cidx >= No_of_classes or not subj_name:
                    continue
                # Find teacher id in subject_map
                tid = None
                if cidx in subject_map:
                    for t_id, subs in subject_map[cidx].items():
                        for sub in subs:
                            if sub["name"].lower().strip() == subj_name.lower().strip() and sub["type"] == "theory":
                                tid = t_id
                                break
                        if tid is not None:
                            break
                resolved.append({"cidx": cidx, "subj": subj_name, "tid": tid})

            if not resolved:
                logging.error(
                    f"Sync group '{bname}': no subjects could be resolved. "
                    f"Requested members: {[(m.get('classIdx'), m.get('subject')) for m in members]}. "
                    f"This usually means the classIdx values don't match the classes that have these subjects."
                )
                return None

            # Skip sync groups that only involve a single class — no cross-class
            # sync needed; the subjects are already constrained by individual hours.
            unique_class_indices = {r["cidx"] for r in resolved}
            if len(unique_class_indices) < 2:
                # Single-class split — the block subject occupies one row in the
                # timetable, owned by a single "primary" teacher_id. Register the
                # OTHER sub-teacher(s) so solve() locks them at whatever slot the
                # primary teacher ends up assigned to (see block_sub_teachers use
                # inside solve()).
                cidx = next(iter(unique_class_indices), -1)
                block_name = (members[0].get('subject') or '').strip()
                primary_tid = None
                if cidx in subject_map and block_name:
                    for t_id, subs in subject_map[cidx].items():
                        if any(s["name"].lower().strip() == block_name.lower().strip() and s["type"] == "theory" for s in subs):
                            primary_tid = t_id
                            break
                if primary_tid is None:
                    logging.warning(f"Sync group '{bname}': single-class split — could not resolve primary teacher for "
                                     f"'{block_name}' in class {cidx}; sub-teachers NOT locked.")
                    continue
                sub_tids = {
                    int(m['teacherId']) for m in members
                    if str(m.get('teacherId') or '').lstrip('-').isdigit()
                    and int(m['teacherId']) != primary_tid
                }
                if sub_tids:
                    block_sub_teachers[(cidx, primary_tid)] = (block_name.lower().strip(), sub_tids)
                    logging.info(f"Sync group '{bname}': single-class split — will lock {len(sub_tids)} sub-teacher(s) "
                                 f"whenever '{block_name}' is assigned in class {cidx}.")
                else:
                    logging.info(f"Sync group '{bname}': single-class split — no distinct sub-teachers to lock.")
                continue

            # Build teacher_sync_max: how many simultaneous classes each teacher
            # may serve within this sync group (applies to both split and merged)
            teacher_sync_max_local = {}
            for r in resolved:
                tid = r["tid"]
                if tid is not None:
                    teacher_sync_max_local[tid] = teacher_sync_max_local.get(tid, 0) + 1

            def slot_ok_for_all(slot):
                # Track how many times we've "used" a shared teacher at this slot
                teacher_usage = {}
                for r in resolved:
                    if Timetable[slot][r["cidx"]] != 0:
                        return False
                    tid = r["tid"]
                    if tid is not None:
                        max_allowed = teacher_sync_max_local.get(tid, 1)
                        usage = teacher_usage.get(tid, 0)
                        if usage >= max_allowed:
                            # Teacher would be serving more classes than allowed at this slot
                            return False
                        # Check availability (marked by previous sync/lab placements)
                        if not main_teacher_list[slot].get(tid, {}).get("available", True):
                            return False
                        # Check teacher still has remaining credit for this class
                        if class_to_teacher[r["cidx"]].get(tid, 0) <= 0:
                            return False
                        teacher_usage[tid] = usage + 1
                return True

            candidates = [s for s in range(total_periods) if slot_ok_for_all(s)]
            random.shuffle(candidates)

            # Prefer one slot per day (no-repeat-same-day)
            chosen    = []
            used_days = set()
            for slot in candidates:
                day = slot // No_of_periods
                if day not in used_days:
                    chosen.append(slot); used_days.add(day)
                if len(chosen) == k:
                    break
            if len(chosen) < k:
                chosen = candidates[:k]

            if len(chosen) < k:
                logging.warning(f"Sync group '{bname}': only found {len(chosen)}/{k} slots — skipping")
                continue

            for slot in chosen:
                tids_marked_busy = set()
                for r in resolved:
                    # Show block name (e.g. "II Language") instead of sub-subject name
                    display = subj_to_block_bt.get((r["cidx"], r["subj"].lower().strip()), r["subj"])
                    Timetable[slot][r["cidx"]] = display
                    tid = r["tid"]
                    # Only mark teacher busy once per slot (shared teacher serves all at same time)
                    if tid is not None and tid not in tids_marked_busy:
                        if tid in main_teacher_list[slot]:
                            main_teacher_list[slot][tid]["available"] = False
                        tids_marked_busy.add(tid)
                    if tid is not None and tid in class_to_teacher[r["cidx"]]:
                        class_to_teacher[r["cidx"]][tid] = max(0, class_to_teacher[r["cidx"]][tid] - 1)
                    if r["cidx"] in subject_map and tid is not None and tid in subject_map[r["cidx"]]:
                        for sub in subject_map[r["cidx"]][tid]:
                            if sub["name"].lower().strip() == r["subj"].lower().strip() and sub["hours"] > 0:
                                sub["hours"] -= 1
                                break

            logging.info(f"Sync group '{bname}' ({btype}): placed at slots {chosen}")

    # ── Step 3: Pre-place Free periods AFTER labs and sync groups ─────────────
    # Scatter Free slots across remaining empty cells before backtracking.
    # Running AFTER labs ensures consecutive lab blocks aren't blocked by Free.
    for class_idx in range(No_of_classes):
        if class_idx not in subject_map:
            continue
        for t_id, subs in subject_map[class_idx].items():
            if not (isinstance(t_id, int) and t_id >= 1000):
                continue  # only phantom Free teachers
            for sub in subs:
                if sub.get("name") != "Free":
                    continue
                free_hours = int(sub.get("hours", 0))
                if free_hours <= 0:
                    continue
                empty_slots = [s for s in range(total_periods) if Timetable[s][class_idx] == 0]
                random.shuffle(empty_slots)
                placed = 0
                for slot in empty_slots:
                    if placed >= free_hours:
                        break
                    Timetable[slot][class_idx] = "Free"
                    if t_id in main_teacher_list[slot]:
                        main_teacher_list[slot][t_id]["available"] = False
                    placed += 1
                sub["hours"] = 0  # mark as placed in subject_map
                logging.info(f"Pre-placed {placed} Free slots for class {class_idx} (teacher {t_id})")

    # ── Step 4: Backtrack-solve remaining theory slots ────────────────────────
    # Feasibility pre-check: classes with almost all Free slots don't need backtracking
    # They've already been solved by Free pre-placement above.
    remaining_empty = sum(
        1 for s in range(total_periods)
        for c in range(No_of_classes)
        if Timetable[s][c] == 0
    )
    if remaining_empty == 0:
        logging.info("All slots pre-filled (labs + free) — no backtracking needed!")
        return Timetable

    logging.info(f"Backtracking {remaining_empty} remaining empty cells")
    if solve():
        return Timetable
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def generate_timetable(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, teacher_unavailability=None,
    elective_bundles=None
):
    if ORTOOLS_AVAILABLE:
        return generate_timetable_ortools(
            No_of_classes, No_of_days_in_week, No_of_periods,
            teacher_list, class_teacher_periods, lab_teacher_periods,
            subject_map, fixed_periods, teacher_unavailability,
            elective_bundles=elective_bundles
        )
    return generate_timetable_backtrack(
        No_of_classes, No_of_days_in_week, No_of_periods,
        teacher_list, class_teacher_periods, lab_teacher_periods,
        subject_map, fixed_periods, teacher_unavailability,
        elective_bundles=elective_bundles
    )


def generate_timetable_with_retry(
    No_of_classes, No_of_days_in_week, No_of_periods,
    teacher_list, class_teacher_periods, lab_teacher_periods,
    subject_map, fixed_periods=None, teacher_unavailability=None,
    max_attempts=3, elective_bundles=None
):
    if ORTOOLS_AVAILABLE:
        # Scale time limit by problem size:
        # Small (≤8 classes): 60s, Medium (≤16): 120s, Large (>16): 180s
        total_slots = No_of_classes * No_of_days_in_week * No_of_periods
        if No_of_classes <= 8:
            time_limit = 60
        elif No_of_classes <= 16:
            time_limit = 120
        else:
            time_limit = 180
        logging.info(f"OR-Tools: {No_of_classes} classes × {No_of_days_in_week*No_of_periods} slots = {total_slots} cells → time limit {time_limit}s")
        return generate_timetable_ortools(
            No_of_classes, No_of_days_in_week, No_of_periods,
            copy.deepcopy(teacher_list),
            copy.deepcopy(class_teacher_periods),
            copy.deepcopy(lab_teacher_periods),
            copy.deepcopy(subject_map),
            fixed_periods, teacher_unavailability,
            time_limit_seconds=time_limit,
            elective_bundles=elective_bundles
        )
    for attempt in range(1, max_attempts + 1):
        logging.info(f"Backtrack attempt {attempt}/{max_attempts}")
        result = generate_timetable_backtrack(
            No_of_classes, No_of_days_in_week, No_of_periods,
            copy.deepcopy(teacher_list),
            copy.deepcopy(class_teacher_periods),
            copy.deepcopy(lab_teacher_periods),
            copy.deepcopy(subject_map),
            fixed_periods, teacher_unavailability,
            elective_bundles=elective_bundles
        )
        if result is not None:
            logging.info(f"Solved on attempt {attempt}")
            return result
        logging.warning(f"Attempt {attempt} failed")
    logging.error("All attempts exhausted")
    return None
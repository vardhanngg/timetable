def build_solver_inputs_from_classes(CONFIG, days, periods):
    class_names = list(CONFIG["classes"].keys())
    No_of_classes = len(class_names)
    total_slots_per_class = days * periods # e.g., 6 * 6 = 36

    teacher_ids = {}
    teacher_list = {}
    next_tid = 0

    class_teacher_periods = {}
    lab_teacher_periods = {}
    subject_map = {}
    
    # 1. Map Real Teachers from UI
    for cidx, cname in enumerate(class_names):
        class_teacher_periods[cidx] = {}
        total_assigned_hours = 0
        
        # Changed to 0 as requested - filler will take ALL remaining slots
        fixed_count = 0 

        for item in CONFIG["classes"][cname]:
            tname = item["teacher"]
            hours = int(item["hours"])
            total_assigned_hours += hours

            if tname not in teacher_ids:
                teacher_ids[tname] = next_tid
                teacher_list[next_tid] = {"Name": tname, "available": True}
                next_tid += 1

            tid = teacher_ids[tname]
            class_teacher_periods[cidx][tid] = hours
            subject_map[(cidx, tid)] = item["subject"]

            if item["type"] == "lab":
                lab_teacher_periods.setdefault(cidx, {})
                lab_teacher_periods[cidx][tid] = [
                    hours,
                    int(item["continuous"]),
                    int(item["lab_no"])
                ]
        
        # 2. Add the UNIQUE 'f' Filler Teacher for THIS class
        f_name = f"f{cidx + 1}"
        teacher_list[next_tid] = {"Name": f_name, "available": True}
        
        # Calculate remaining credits: (Total Slots - Theory - Labs)
        free_credits = total_slots_per_class - total_assigned_hours - fixed_count
        
        # Safety check: ensure we don't pass negative credits to the solver
        if free_credits > 0:
            class_teacher_periods[cidx][next_tid] = free_credits
            subject_map[(cidx, next_tid)] = "Free"
        elif free_credits < 0:
            # This means the user assigned more hours than the week allows
            print(f"Warning: Class {cname} is over-scheduled by {abs(free_credits)} hours!")
            
        next_tid += 1

    return (
        No_of_classes,
        teacher_list,
        class_teacher_periods,
        lab_teacher_periods,
        subject_map
    )
def build_final_inputs(CONFIG, days, periods, fixed_slots_data):
    # 1. Get base inputs (Theory/Lab requirements)
    No_of_classes, teacher_list, class_teacher_periods, lab_teacher_periods, subject_map = build_solver_inputs_from_classes(CONFIG, days, periods)

    # fixed_slots_data is likely: {"0": {"0-1": {"label": "Lunch", "teacher_id": "None"}}, "1": {...}}
    
    # 2. Process Fixed Slots Class-by-Class
    for cls_idx_str, slots in fixed_slots_data.items():
        cls_idx = int(cls_idx_str)
        
        fixed_count_for_this_class = 0
        
        for slot_id, info in slots.items():
            label = info.get('label', '').strip()
            if not label:
                continue
                
            fixed_count_for_this_class += 1
            t_id_raw = info.get('teacher_id')

            # If a specific teacher is assigned to this fixed slot
            if t_id_raw is not None and str(t_id_raw).isdigit():
                t_id = int(t_id_raw)
                
                # Subtract 1 from their theory load requirements for this class
                # so the solver doesn't assign them again
                if t_id in class_teacher_periods[cls_idx]:
                    if class_teacher_periods[cls_idx][t_id] > 0:
                        class_teacher_periods[cls_idx][t_id] -= 1

        # 3. Recalculate 'f' Fillers (Free Periods) for THIS class
        # We need to find the specific filler teacher ID for this class (e.g., "f1")
        filler_tid = None
        for t_id, t_info in teacher_list.items():
            if t_info['Name'] == f"f{cls_idx + 1}":
                filler_tid = t_id
                break
        
        if filler_tid is not None:
            # Total Capacity (e.g. 36)
            total_slots = days * periods
            
            # Sum of remaining Theory + Labs
            theory_sum = sum(val for tid, val in class_teacher_periods[cls_idx].items() if tid != filler_tid)
            lab_sum = sum(val[0] for val in lab_teacher_periods.get(cls_idx, {}).values())
            
            # Filler = Total - (Remaining Theory) - (Labs) - (Fixed Slots like Lunch)
            new_free_credits = total_slots - theory_sum - lab_sum - fixed_count_for_this_class
            class_teacher_periods[cls_idx][filler_tid] = max(0, new_free_credits)

    return No_of_classes, teacher_list, class_teacher_periods, lab_teacher_periods, subject_map
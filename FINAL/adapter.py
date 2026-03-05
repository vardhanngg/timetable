def build_solver_inputs_from_classes(CONFIG, days, periods):
    class_names = list(CONFIG["classes"].keys())
    No_of_classes = len(class_names)
    total_slots_per_class = days * periods 

    teacher_list = {} 
    class_teacher_periods = {}
    lab_teacher_periods = {}
    subject_map = {}
    
    for cidx, cname in enumerate(class_names):
        class_teacher_periods[cidx] = {}
        total_assigned_hours = 0

        for item in CONFIG["classes"][cname]:
            # TRUST the numeric ID from the UI/App.py
            tid = int(item.get("teacher_id", 99)) 
            tname = item.get("teacher", "Unknown")
            hours = int(item.get("hours", 0))
            
            total_assigned_hours += hours

            if tid not in teacher_list:
                teacher_list[tid] = {"Name": tname, "available": True}

            subject_map[(cidx, tid)] = item.get("subject", "Subject")

            if str(item.get("type")).lower() == "lab":
                lab_teacher_periods.setdefault(cidx, {})
                lab_teacher_periods[cidx][tid] = [
                    hours,
                    int(item.get("continuous", 2)),
                    int(item.get("lab_no", 1))
                ]
                if tid not in class_teacher_periods[cidx]:
                    class_teacher_periods[cidx][tid] = 0
            else:
                class_teacher_periods[cidx][tid] = class_teacher_periods[cidx].get(tid, 0) + hours
        
        # Filler Logic: High ID range to avoid clashing
        f_id = 1000 + cidx 
        teacher_list[f_id] = {"Name": f"f{cidx + 1}", "available": True}
        
        free_credits = total_slots_per_class - total_assigned_hours
        class_teacher_periods[cidx][f_id] = max(0, free_credits)
        subject_map[(cidx, f_id)] = "Free"

    return No_of_classes, teacher_list, class_teacher_periods, lab_teacher_periods, subject_map


def build_final_inputs(CONFIG, days, periods, fixed_slots_data):
    # Call the core builder
    No_of_classes, teacher_list, class_teacher_periods, lab_teacher_periods, subject_map = build_solver_inputs_from_classes(CONFIG, days, periods)

    for cls_idx_str, slots in fixed_slots_data.items():
        cls_idx = int(cls_idx_str)
        fixed_count_for_this_class = 0
        
        for slot_id, info in slots.items():
            if not info.get('label', '').strip(): continue
                
            fixed_count_for_this_class += 1
            t_id_raw = info.get('teacher_id')

            if t_id_raw and str(t_id_raw).isdigit():
                t_id = int(t_id_raw)
                # Subtract one hour from the workload because it is now "fixed"
                if t_id in class_teacher_periods[cls_idx] and class_teacher_periods[cls_idx][t_id] > 0:
                    class_teacher_periods[cls_idx][t_id] -= 1

        # Re-adjust the "Free" (filler) teacher to keep the total slots correct
        filler_tid = 1000 + cls_idx
        if filler_tid in class_teacher_periods[cls_idx]:
            total_slots = days * periods
            theory_sum = sum(val for tid, val in class_teacher_periods[cls_idx].items() if tid != filler_tid)
            lab_sum = sum(val[0] for val in lab_teacher_periods.get(cls_idx, {}).values())
            
            new_free = total_slots - theory_sum - lab_sum - fixed_count_for_this_class
            class_teacher_periods[cls_idx][filler_tid] = max(0, new_free)

    return No_of_classes, teacher_list, class_teacher_periods, lab_teacher_periods, subject_map
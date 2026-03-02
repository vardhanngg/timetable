def build_solver_inputs_from_classes(CONFIG):
    class_names = list(CONFIG["classes"].keys())
    No_of_classes = len(class_names)

    teacher_ids = {}
    teacher_list = {}
    next_tid = 0

    class_teacher_periods = {}
    lab_teacher_periods = {}
    subject_map = {}

    for cidx, cname in enumerate(class_names):
        class_teacher_periods[cidx] = {}

        for item in CONFIG["classes"][cname]:
            tname = item["teacher"]

            if tname not in teacher_ids:
                teacher_ids[tname] = next_tid
                teacher_list[next_tid] = {
                    "Name": tname,
                    "available": True
                }
                next_tid += 1

            tid = teacher_ids[tname]

            class_teacher_periods[cidx][tid] = item["hours"]
            subject_map[(cidx, tid)] = item["subject"]

            if item["type"] == "lab":
                lab_teacher_periods.setdefault(cidx, {})
                lab_teacher_periods[cidx][tid] = [
                    item["hours"],
                    item["continuous"],
                    item["lab_no"]
                ]

    return (
        No_of_classes,
        teacher_list,
        class_teacher_periods,
        lab_teacher_periods,
        subject_map
    )
import random
import copy
# Used for shuffling teacher priority order randomly
import sys
random.seed(1)

log_file = open("timetable_debug.log", "w", encoding="utf-8")
sys.stdout = log_file


# ---------------- BASIC CONFIG ----------------

No_of_classes = 8
# Number of classes (columns in timetable)

No_of_teachers = 0
# Placeholder; actual value set after teacher_list creation

No_of_days_in_week = 6
# Working days per week

No_of_periods = 6
# Periods per day

total_periods = No_of_days_in_week * No_of_periods
# Total weekly periods per class (36)


# ---------------- TIMETABLE MATRIX ----------------

Timetable = []
# 2D matrix: rows = periods (36), columns = classes (8)

arr = []
# Temporary row template

for i in range(No_of_classes):
    arr.append(0)
# Create one row with 8 empty slots

for j in range(total_periods):
    Timetable.append(arr.copy())
# Create 36 such rows (empty timetable)

#for i in range(len(Timetable[0])):
 #   Timetable[18][i] = "foyer"


# ---------------- BLOCK DEFINITIONS ----------------
def row_is_globally_free(r):
    return all(Timetable[r][c] == 0 for c in range(No_of_classes))


BLOCKS = []

for day in range(No_of_days_in_week):
    base = day * No_of_periods

    # 1-period blocks
    for p in range(No_of_periods):
        r = base + p
        if row_is_globally_free(r):
            BLOCKS.append({
                "periods": [r],
                "length": 1
            })

    # 2-period blocks (labs)
    for p in range(0, No_of_periods - 1, 2):
        r1 = base + p
        r2 = base + p + 1
        if row_is_globally_free(r1) and row_is_globally_free(r2):
            BLOCKS.append({
                "periods": [r1, r2],
                "length": 2
            })
def block_is_free(block, cls, Timetable):
    for r in block["periods"]:
        if Timetable[r][cls] != 0:
            return False
    return True

# ---------------- TEACHER DEFINITIONS ----------------



teacher_list = {
    0:  {"Name": "Aditi",  "available": True},
    1:  {"Name": "Sanjay", "available": True},
    2:  {"Name": "Kavita", "available": True},
    3:  {"Name": "Anil",   "available": True},
    4:  {"Name": "Pooja",  "available": True},
    5:  {"Name": "Manoj",  "available": True},
    6:  {"Name": "Priya",  "available": True},
    7:  {"Name": "Rohit",  "available": True},
    8:  {"Name": "Rahul",  "available": True},
    9:  {"Name": "Rajesh", "available": True},
    10: {"Name": "Ritu",   "available": True},
    11: {"Name": "Nisha",  "available": True},
    12: {"Name": "Meera",  "available": True},
    13: {"Name": "Sameer", "available": True},
    14: {"Name": "Sneha",  "available": True},
    15: {"Name": "Vikram", "available": True},
    16: {"Name": "Richa",  "available": True},

    # Free periods treated as teachers
    17: {"Name": "f1", "available": True},
    18: {"Name": "f2", "available": True},
    19: {"Name": "f3", "available": True},
    20: {"Name": "f4", "available": True},
    21: {"Name": "f5", "available": True},
    22: {"Name": "f6", "available": True},
    23: {"Name": "f7", "available": True},
    24: {"Name": "f8", "available": True}

}
'''
main_teacher_list={}
for day in range(No_of_days_in_week):
    main_teacher_list[day] = {}
    for period in range(No_of_periods):
        main_teacher_list[day][period] = copy.deepcopy(teacher_list)
'''
main_teacher_list = [
    copy.deepcopy(teacher_list)
    for _ in range(total_periods)
]

No_of_teachers = len(teacher_list)
# Total teachers including free placeholders


# ---------------- REQUIRED PERIODS PER CLASS ----------------
'''
class_teacher_periods = {
    0: {0:5, 1:5, 2:5, 3:5, 4:4, 5:4},
    1: {0:5, 1:5, 2:5, 3:5, 4:4, 5:4},
    2: {6:5, 7:4, 15:5, 3:5, 8:5, 9:5},
    3: {6:4, 7:4, 10:5, 3:5, 8:5, 4:5},
    4: {6:4, 1:5, 2:5, 11:5, 14:5, 8:5},
    5: {6:4, 1:5, 2:5, 10:5, 14:5, 8:3, 9:3},
    6: {6:4, 7:4, 15:5, 11:5, 14:5, 8:3, 9:3},
    7: {16:4, 7:4, 15:5, 13:5, 14:5, 8:3, 9:3}
}'''
class_teacher_periods = {
    0: {0:5, 1:5, 2:5, 3:5, 4:4, 5:4},
    1: {0:5, 1:5, 2:5, 3:5, 4:4, 5:4},
    2: {6:5, 7:4, 15:5, 3:5, 8:5, 9:5},
    3: {  10:5, 3:5, 8:5, 4:5},
    4: { 1:5, 2:5, 11:5, 14:5, 8:5},
    5: {6:4, 1:5, 2:5, 10:5, 14:5, 8:3, 9:3},
    6: { 15:5, 11:5, 14:5, 8:3, 9:3},
    7: {16:4,  15:5, 13:5, 14:5, 8:3, 9:3}
}
LAB_SUBJECTS = {
    6: "Physics Lab",
    7: "Chemistry Lab"
}
LAB_TEACHERS = set(LAB_SUBJECTS.keys())
FREE_TEACHERS_SET = set(range(17, 25))
# Dict format: class → teacher → weekly periods


    # ---------------- CLASS → TEACHER MATRIX ----------------
class_to_teacher = [] 
# Each row: [remaining_periods_per_teacher..., priority_list]
FREE_TEACHERS = list(range(17, 25))
# One free-teacher per class (f1 for class 0, f2 for class 1, ...)

for class_idx in range(No_of_classes):

    teacher_part = [0] * No_of_teachers
    # Remaining periods for each teacher for this class

    assigned = 0
    # Count assigned real teacher periods

    for t_idx, periods in class_teacher_periods[class_idx].items():
        teacher_part[t_idx] = periods
        assigned += periods
    # Fill real teacher requirements

    free_count = total_periods - assigned
    # Remaining periods are free periods

    free_teacher_index = FREE_TEACHERS[class_idx]
    teacher_part[free_teacher_index] = free_count
    # Assign ALL free periods to ONE free-teacher (diagonal / identity style)


    priority_list = list(range(No_of_teachers))  # base order ONLY

    row = teacher_part.copy()
    row.append(priority_list)

    class_to_teacher.append(row)


# ---------------- HELPER FUNCTIONS ----------------
'''
def printmat(Timetable):
    for i in range(len(Timetable)):
        print(f"Row {i}: {Timetable[i]}")

def printmat(Timetable):
    for cls in range(No_of_classes):
        print(f"\n========== Class {cls} ==========")

        for day in range(No_of_days_in_week):
            start = day * No_of_periods
            end = start + No_of_periods

            day_periods = []
            for p in range(start, end):
                day_periods.append(Timetable[p][cls])

            print(f"Day {day + 1}: {day_periods}")
'''


def print_timetable_classwise(Timetable):
    # Day names (we will slice based on No_of_days_in_week)
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    days = all_days[:No_of_days_in_week]

    # Period header
    period_header = "        "  # spacing for day label
    for p in range(1, No_of_periods + 1):
        period_header += f"P{p:^6}"
    
    for cls in range(No_of_classes):
        print(f"\n========== Class {cls} ==========")
        print(period_header)

        for day_index, day_name in enumerate(days):
            start = day_index * No_of_periods
            end = start + No_of_periods

            print(f"{day_name:<9}", end="")

            for row in range(start, end):
                teacher = Timetable[row][cls]
                print(f"{teacher:^7}", end="")

            print() 

def find_empty_block(Timetable, class_to_teacher, Tl):
    best = (-1, -1)
    min_domain = float("inf")

    for b_idx, block in enumerate(BLOCKS):
        for cls in range(No_of_classes):

            if not block_is_free(block, cls, Timetable):
                continue

            legal = 0

            for t in range(No_of_teachers):

                # 🚫 Skip lab/theory restriction for FREE teachers
                ''' if t not in FREE_TEACHERS_SET:
                    # Lab teachers → only 2-period blocks
                    if t in LAB_TEACHERS and block["length"] != 2:
                        continue

                    # Theory teachers → only 1-period blocks
                    if t not in LAB_TEACHERS and block["length"] != 1:
                        continue'''

                if class_to_teacher[cls][t] < block["length"]:
                    continue

                if not all(Tl[p][t]["available"] for p in block["periods"]):
                    continue

                legal += 1

            if legal == 0:
                return b_idx, cls

            if legal < min_domain:
                min_domain = legal
                best = (b_idx, cls)

    return best
def place_block(block, cls, t, Timetable, class_to_teacher, Tl):
    for r in block["periods"]:
        Timetable[r][cls] = teacher_list[t]["Name"]
        Tl[r][t]["available"] = False
    class_to_teacher[cls][t] -= block["length"]


def unplace_block(block, cls, t, Timetable, class_to_teacher, Tl):
    for r in block["periods"]:
        Timetable[r][cls] = 0
        Tl[r][t]["available"] = True
    class_to_teacher[cls][t] += block["length"]

def shuffle_days(Timetable):
    days = []
    for d in range(No_of_days_in_week):
        start = d * No_of_periods
        end = start + No_of_periods
        days.append(Timetable[start:end])

    random.shuffle(days)
    Timetable[:] = [row for day in days for row in day]
'''def reset_available(Tl):
    # Reset teacher availability at new period
    for i in Tl:
        Tl[i]["available"] = True
'''



# ---------------- BACKTRACKING SOLVER ----------------

#prev_x = [-1]
# Tracks last period row to reset availability

def solve(Timetable, class_to_teacher, Tl):
    BLOCKS.sort(key=lambda b: -b["length"])
    b_idx, cls = find_empty_block(Timetable, class_to_teacher, Tl)

    # All blocks filled
    if b_idx == -1:
        return True

    block = BLOCKS[b_idx]

    teachers = list(range(No_of_teachers))
    random.shuffle(teachers)

    for t in teachers:

        # 🚫 Apply lab/theory restriction ONLY to real teachers
        if t not in FREE_TEACHERS_SET:

            # Lab teachers → only 2-period blocks
            if t in LAB_TEACHERS and block["length"] != 2:
                continue

            # Theory teachers → only 1-period blocks
            if t not in LAB_TEACHERS and block["length"] != 1:
                continue

        # Enough remaining load?
        if class_to_teacher[cls][t] < block["length"]:
            continue

        # Teacher free for all periods in block?
        if not all(Tl[p][t]["available"] for p in block["periods"]):
            continue

        # Place
        place_block(block, cls, t, Timetable, class_to_teacher, Tl)

        # Recurse
        if solve(Timetable, class_to_teacher, Tl):
            return True

        # Backtrack
        unplace_block(block, cls, t, Timetable, class_to_teacher, Tl)

    return False



if solve(Timetable, class_to_teacher, main_teacher_list):
    #shuffle_days(Timetable)
    print_timetable_classwise(Timetable)
else:
    print("No Solution!")
#printmat(Timetable)

log_file.close()

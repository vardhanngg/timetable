import random
import copy
import sys

#for puttong result in a file 
log_file = open("output.log", "w", encoding="utf-8")
sys.stdout = log_file


# ---------------- BASIC CONFIG ----------------

No_of_classes = 8              # Total number of classes
No_of_days_in_week = 6         # Working days (Mon–Sat)
No_of_periods = 6              # Periods per day

# Total periods per week per class (6 × 6 = 36)
total_periods = No_of_days_in_week * No_of_periods


# ---------------- TIMETABLE MATRIX ----------------

Timetable = []                 #2D matrix: rows = time slots (36), columns = classes
arr = []

# Create one empty row (one slot for each class)
for i in range(No_of_classes):
    arr.append(0)

# Create 36 rows (one for each period in week)
for j in range(total_periods):
    Timetable.append(arr.copy())

# Pre-assign fixed slots (same for all classes)
# These are locked and solver will not change them
for i in range(len(Timetable[0])):
    Timetable[18][i] = "foyer"   # Thursday Period 1
    Timetable[30][i] = "iic"     # Saturday Period 1
    Timetable[31][i] = "iic"     # Saturday Period 2


#----------------------------------------------------

                        #teachers list
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
    #free periods
    17: {"Name": "f1", "available": True},
    18: {"Name": "f2", "available": True},
    19: {"Name": "f3", "available": True},
    20: {"Name": "f4", "available": True},
    21: {"Name": "f5", "available": True},
    22: {"Name": "f6", "available": True},
    23: {"Name": "f7", "available": True},
    24: {"Name": "f8", "available": True}
}

# Create availability table for each time slot
# main_teacher_list[x] → availability of all teachers in period x
main_teacher_list = [
    copy.deepcopy(teacher_list)
    for _ in range(total_periods)
]

No_of_teachers = len(teacher_list)  # Total teachers including free placeholders


# ---------------- REQUIRED PERIODS PER CLASS ----------------

# Format:
# class_index → {teacher_index: weekly_required_periods}
class_teacher_periods = {
    0: {0:5, 1:3, 2:5, 3:5, 4:4, 5:4},
    1: {0:5, 1:2, 2:5, 3:5, 4:4, 5:4},
    2: {6:5, 7:5, 15:5, 3:5, 8:5, 9:5},
    3: {6:5, 7:5, 10:5, 3:2, 8:5, 4:5},
    4: {6:5, 1:5, 2:5, 11:5, 14:5, 8:5},
    5: {6:5, 1:2, 2:5, 10:2, 14:5, 8:3, 9:3},
    6: {6:5, 7:5, 15:5, 11:5, 14:5, 8:3, 9:3},
    7: {16:5, 7:5, 15:5, 13:5, 14:5, 8:3, 9:3}
}
lab_teacher_periods={
    #class:[teacher number,how many lab periods in that week,how many continuous,lab_number]
    0: {12:[4,3,2,1]}, #so there will be total of 3 into 2 = 6 periods per week for class 0
    1: {12:[4,2,2,1]}, 
    5: {10:[1,3,2,2]}, 
}
total_lab_periods = sum(
    block_info[1] * block_info[2] 
    for class_periods in lab_teacher_periods.values() 
    for block_info in class_periods.values()
)
print("Total lab periods:", total_lab_periods)
# -------------------------------

class_to_teacher = []
FREE_TEACHERS = list(range(17, 25))  #f1 to f8

for class_idx in range(No_of_classes):

    # Remaining periods for each teacher (initially 0)
    teacher_part = [0] * No_of_teachers
    assigned = 0

    # Fill required real-teacher periods
    for t_idx, periods in class_teacher_periods[class_idx].items():
        teacher_part[t_idx] = periods
        assigned += periods

    # Remaining periods become free periods
    free_count = total_periods - assigned 
    free_teacher_index = FREE_TEACHERS[class_idx]
    teacher_part[free_teacher_index] = free_count

    # Priority list controls teacher trial order
    priority_list = list(range(No_of_teachers))

    row = teacher_part.copy()
    row.append(priority_list)

    class_to_teacher.append(row)
# this is class to teacher format 
#meaninf teacher 2 has 1 periods for that class 
#[0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]],
# ---------------- PRINT FUNCTION ----------------

def print_timetable_classwise(Timetable):
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    days = all_days[:No_of_days_in_week]

    # Print header row
    period_header = "        "
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

print(class_to_teacher)
print()
print(main_teacher_list)
# ---------------- MRV SLOT SELECTION ----------------

def find_empty(Timetable, class_to_teacher, Tl):
    """
    Uses MRV (Minimum Remaining Values) heuristic.
    Chooses the empty slot with the fewest legal teachers.
    """

    best_cell = (-1, -1)
    class_with_min_avl_teachers = float("inf") 

    for x in range(len(Timetable)):      # iterate over periods
        for y in range(len(Timetable[0])):  # iterate over classes

            if Timetable[x][y] == 0 or Timetable[x][y] == "":  # if that period is free

                teacher_count = 0   #to count how many teachers can teach that class at that period

                for i in range(No_of_teachers):   #find how many teachers are available to teeach that class at that period
                    if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:
                        #if credits remaining          #if not busy with other class
                        teacher_count += 1


                if teacher_count == 0:  # if no teacher is available... wither busy with that class or all credits over
                    return x, y

                # Select slot with smallest domain
                if (
                    teacher_count < class_with_min_avl_teachers or
                    (teacher_count == class_with_min_avl_teachers and random.random() < 0.5)
                ):
                    class_with_min_avl_teachers = teacher_count
                    best_cell = (x, y)

    return best_cell


# ---------------- BACKTRACKING SOLVER ----------------

def solve(Timetable, class_to_teacher, Tl):
    x, y = find_empty(Timetable, class_to_teacher, Tl)

    # If no empty slot remains → solution found
    if x == -1:
        return True

    # Copy priority list and shuffle for randomness
    priority_list = class_to_teacher[y][-1].copy()   
    random.shuffle(priority_list)

    for i in priority_list:

        # Check if teacher i can be assigned
        if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:

            # Assign teacher
            class_to_teacher[y][i] -= 1
            Tl[x][i]["available"] = False
            Timetable[x][y] = Tl[x][i]["Name"]

            # Recursive call
            if solve(Timetable, class_to_teacher, Tl):
                return True

            # Backtrack (undo assignment)
            Timetable[x][y] = 0
            class_to_teacher[y][i] += 1
            Tl[x][i]["available"] = True

    return False



if solve(Timetable, class_to_teacher, main_teacher_list):
    print_timetable_classwise(Timetable)
else:
    print("No Solution!")
print(class_to_teacher)
log_file.close()
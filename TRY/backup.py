import random
import copy
# Used for shuffling teacher priority order randomly
#import sys

#log_file = open("timetable_debug.log", "w", encoding="utf-8")
#sys.stdout = log_file


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

class_teacher_periods = {
    0: {0:5, 1:5, 2:5, 3:5, 4:4, 5:4},
    1: {0:5, 1:5, 2:5, 3:5, 4:4, 5:4},
    2: {6:5, 7:5, 15:5, 3:5, 8:5, 9:5},
    3: {6:5, 7:5, 10:5, 3:5, 8:5, 4:5},
    4: {6:5, 1:5, 2:5, 11:5, 14:5, 8:5},
    5: {6:5, 1:5, 2:5, 10:5, 14:5, 8:3, 9:3},
    6: {6:5, 7:5, 15:5, 11:5, 14:5, 8:3, 9:3},
    7: {16:5, 7:5, 15:5, 13:5, 14:5, 8:3, 9:3}
}
# Dict format: class → teacher → weekly periods


    # ---------------- CLASS → TEACHER MATRIX ----------------
class_to_teacher = [] 
# Each row: [remaining_periods_per_teacher..., [priority_list, pointer]]

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

    pseudo_random_order = [list(range(No_of_teachers)), 0]
    pseudo_random_order[1] = 0 

    #print(f"Before shuffle: {pseudo_random_order}")
    random.shuffle(pseudo_random_order[0])
    #print(f"After shuffle: {pseudo_random_order}")

    row = teacher_part.copy()  # Create a copy of teacher_part to avoid modifications
    row.append(pseudo_random_order)  # Append the shuffled teacher order with 0 at the end

    class_to_teacher.append(row)  # Append the final row to the class_to_teacher list




# ---------------- HELPER FUNCTIONS ----------------
def printmat(Timetable):
    for i in range(len(Timetable)):
        print(f"Row {i}: {Timetable[i]}")

def find_empty(x):
    # Find first empty timetable slot
    for i in range(len(x)):
        for j in range(len(x[0])):
            if x[i][j] == 0 or x[i][j] == "":
                print(f"returning {i},{j}")
                return i, j

    return -1, -1


def reset_available(Tl):
    # Reset teacher availability at new period
    for i in Tl:
        Tl[i]["available"] = True


def find_teacher(class_to_teacher, x,y, Tl):
    # Try all teachers for class y using priority list

    priority_list, ptr = class_to_teacher[y][-1]
    #print(priority_list)

    while ptr < len(priority_list):
        i = priority_list[ptr]      #picking a teacher inedx randomly
        class_to_teacher[y][-1][1] += 1 #increasing the ptr by +1

        if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:
            class_to_teacher[y][i] -= 1
            Tl[x][i]["available"] = False
            print(f"returning {i}")
            return i

        ptr = class_to_teacher[y][-1][1]

    return -1


# ---------------- BACKTRACKING SOLVER ----------------

prev_x = [-1]
# Tracks last period row to reset availability

def solve(Timetable, class_to_teacher, Tl):

    x, y = find_empty(Timetable)
    print(f"x is {x}, y is {y}")

    if x == -1:   # All slots filled successfully
        return True
    '''
    
    if x != prev_x[0]:
        reset_available(Tl)
        for c in range(No_of_classes):
            class_to_teacher[c][-1][1] = 0
        prev_x[0] = x
    # New period → reset availability & pointers
    
   
    #if x != prev_x[0]:
    #    reset_available(Tl[x])              # ONLY this period
        #for c in range(No_of_classes):
            #class_to_teacher[c][-1][1] = 0
     #   prev_x[0] = x
       
    
    if x != prev_x[0]:
        reset_available(Tl[x])              # ONLY this period
        for c in range(No_of_classes):
          class_to_teacher[c][-1][1] = 0  # reset priority pointer for all classes
        prev_x[0] = x

    #printmat(Tl)
    #printmat(Timetable)

    #e = find_teacher(class_to_teacher, x, y, Tl)
    #print(f'e is {e}')

    #if e == -1:
        #return False

    '''
    #ptr=Tl[]
    #Timetable[x][y] = Tl[x][t]["Name"]
    print(f"in time table of {x}{y}, placed {Tl[x][e]["Name"]}")

    if solve(Timetable, class_to_teacher, Tl):
        return True

    # Backtrack
    Timetable[x][y] = 0
    class_to_teacher[y][e] += 1
    Tl[x][e]["available"] = True
    class_to_teacher[y][-1][1] = 0   #resetpointer

    return False






#if solve(Timetable, class_to_teacher, main_teacher_list):
    print("Solution Found!")
#else:
    print("No Solution!")

printmat(teacher_list)
#log_file.close()

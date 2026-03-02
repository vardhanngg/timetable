import random
import copy
import sys
random.seed(10)

#for puttong result in a file 
log_file = open("output.log", "w", encoding="utf-8")
sys.stdout = log_file

#-------------this is for exporting to csv
import csv

def export_timetable_to_csv(Timetable):
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    days = all_days[:No_of_days_in_week]

    for cls in range(No_of_classes):
        filename = f"class_{cls}_timetable.csv"

        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            # Header row
            header = ["Day/Period"] + [f"P{p}" for p in range(1, No_of_periods + 1)]
            writer.writerow(header)

            for day_index, day_name in enumerate(days):
                start = day_index * No_of_periods
                end = start + No_of_periods

                row = [day_name]

                for period in range(start, end):
                    value = Timetable[period][cls]

                    if value in [info["Name"] for info in teacher_list.values() if info["Name"].startswith("f")]:
                        value = "Free"

                    row.append(value)

                writer.writerow(row)

        print(f"Exported: {filename}")

#for all together

def export_all_classes_one_file(Timetable):
    

    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    days = all_days[:No_of_days_in_week]

    with open("full_timetable.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        for cls in range(No_of_classes):
            writer.writerow([f"Class {cls}"])
            header = ["Day/Period"] + [f"P{p}" for p in range(1, No_of_periods + 1)]
            writer.writerow(header)

            for day_index, day_name in enumerate(days):
                start = day_index * No_of_periods
                end = start + No_of_periods

                row = [day_name]
                #for period in range(start, end):
                #   row.append(Timetable[period][cls])
                for period in range(start, end):
                    value = Timetable[period][cls]

                    # Clean free teachers
                    if value in [info["Name"] for info in teacher_list.values() if info["Name"].startswith("f")]:
                        value = "Free"

                row.append(value)
                writer.writerow(row)

            writer.writerow([])  # blank line between classes

    print("Exported: full_timetable.csv")
# ---------------- BASIC CONFIG ----------------

No_of_classes = 5  #9           # Total number of classes
No_of_days_in_week = 6         # Working days (Mon–Sat)
No_of_periods = 6              # Periods per day

# Total periods per week per class (6 × 6 = 36)
total_periods = No_of_days_in_week * No_of_periods


# ---------------- TIMETABLE MATRIX ----------------

Timetable = []                 #2D matrix: rows = time slots (36), columns = classes
arr = [] #tmp

# Creating one empty row with classes=no of classes
for i in range(No_of_classes):
    arr.append(0)

#Creating 36 rows (one for each period in week)
for j in range(total_periods):
    Timetable.append(arr.copy())

#fixed periods
for i in range(len(Timetable[0])):
    Timetable[18][i] = "foyer"   
    Timetable[30][i] = "iic"    
    Timetable[31][i] = "iic"   

fixed_periods_count=3

#----------------------------------------------------

'''                        #teachers list
teacher_list = {
    0:  {"Name": "Akshath",  "available": True},
    1:  {"Name": "pavan", "available": True},
    2:  {"Name": "rajesh", "available": True},
    3:  {"Name": "vardhan",   "available": True},
    4:  {"Name": "sathwik",  "available": True},
    5:  {"Name": "badhri",  "available": True},
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
    24: {"Name": "f8", "available": True},
    #25: {"Name": "f9", "available": True}
}
'''
teacher_list = {
    0: {"Name": "S1", "available": True},
    1: {"Name": "S2", "available": True},
    2: {"Name": "S3", "available": True},
    3: {"Name": "S4", "available": True},
    4: {"Name": "S5", "available": True},
    5: {"Name": "S6", "available": True},
    6: {"Name": "S7", "available": True},
    7: {"Name": "S8", "available": True},
    8: {"Name": "S9", "available": True},
    9: {"Name": "S10", "available": True},
    10: {"Name": "S11", "available": True},
    11: {"Name": "S12", "available": True},

    # Free periods
    12: {"Name": "f1", "available": True},
    13: {"Name": "f2", "available": True},
    14: {"Name": "f3", "available": True},
    15: {"Name": "f4", "available": True},
    16: {"Name": "f5", "available": True}
}

main_teacher_list = [
    copy.deepcopy(teacher_list)
    for _ in range(total_periods)   # repeated 36 times.... so for each teacher ther is one teachers list
]                                   #lots of memory used
#print("main teachers list is ",main_teacher_list)
#sys.stdout.flush()
No_of_teachers = len(teacher_list)  #total teachers including free teachers.


# ---------------- REQUIRED PERIODS PER CLASS ----------------


# class_index → {teacher_index: weekly_required_periods}
'''
class_teacher_periods = {

    # I Year
    0: {
        #teacher 5 has 3 subs to take
        5: 3,   # General English (S6)
        6: 3,   # II Language (S7)
        1: 4,   # Problem Solving with Computers (S2)
        4: 4,   # Calculus (S5)
        2: 2,   # Software Lab Python – theory part (S3)
        7: 2,   # Awareness (S8)
        8: 3,   # Multidisciplinary Course (S9)
    },

    # II Year
    1: {
        5: 3,   # General English (S6)
        8: 6,   # Computer Organization (S9) # Multidisciplinary Course (S9)
        3: 4,   # Discrete Mathematics (S4)
        4: 4,   # Statistics for Data Science (S5)
        6: 2,   # Awareness (S7)
    },

    # III Year
    2: {
        3: 4,   # Operating Systems (S4)
        9: 4,   # Computer Networks (S10)
        4: 5,   # Optimization for ML (S5)
        2: 5,   # Data Mining & ML (S3)
        6: 2,   # Awareness (S7)
    },

    # IV Year
    3: {
        11: 4,  # Linux System Programming (S12)
        3: 4,   # Elective II (S4)
        10: 4,  # Elective III (S11)
        9: 2,   # Research Methodology (S10)
        0: 4,   # Cloud Computing (S1)
        7: 2,   # Awareness (S8)
    },

    # V Year
    4: {
        4: 5,   # Stochastic Processes (S5)
        2: 5,   # Deep Learning (S3)
        1: 5,   # NLP (S2)
        0: 5,   # Cloud Computing (S1)
        7: 2,   # Awareness (S8)
    },
}

lab_teacher_periods={
#class:{teacher number:[how many labs in that week,how many continuous,lab_number]
    1: {1:[2,2,1]}, 
    5: {5:[3,2,2]}, 
    2: {2:[2,1,1]}
}

lab_teacher_periods = {

    # I Year
    0: {
        #for the class 0 , teacher 1 has 6 labs and continuously 2 in lab no. 1
        1: [6, 2, 1],   
        2: [2, 2, 1],
    },

    # II Year
    1: {
        9: [4, 2, 1],   # Data Visualization Lab (S10)
    },

    # III Year
    2: {
        10: [6, 2, 2],  # Java Lab (S11)
    },
}'''
class_teacher_periods = {
    0: {5: 3, 6: 3, 1: 4, 4: 4, 2: 2, 7: 2, 8: 3}, # I Year 
    
    1: {5: 3, 8: 6, 3: 4, 4: 4, 6: 2},             # II Year 
    
    2: {
        3: 4,   # S4 (OS) 
        9: 7,   # S10 (Networks 4 + Skill Enhancement 3) <-- UPDATED 
        4: 5,   # S5 (ML Optimization) 
        2: 5,   # S3 (Data Mining) 
        6: 2    # S7 (Awareness) 
    },
    
    3: {11: 4, 3: 4, 10: 4, 9: 2, 0: 4, 7: 2},    # IV Year 
    
    4: {4: 5, 2: 5, 1: 5, 0: 5, 7: 2},            # V Year [cite: 2, 3]
}

lab_teacher_periods = {
    0: {1: [6, 2, 1], 2: [2, 2, 1]},              # C Lab (6), Python Lab (2) 
    1: {9: [4, 2, 1]},                            # Data Vis Lab (4) 
    2: {10: [6, 2, 2]},                           # Java Lab (6) 
}
labs={
    1:[],
    2:[]
}

lab_used_by_class_per_day = {
    class_idx: {}   # day → set of lab_numbers
    for class_idx in range(No_of_classes)
}
# (class_index, teacher_index) → Subject Name
subject_map = {
    # I Year (Class 0)
    (0, 1): "Problem Solving with Computers",
    (0, 2): "Software Lab in Python - I",
    (0, 3): "Software Lab in C - Part I",
    (0, 4): "Calculus",
    (0, 5): "General English",
    (0, 6): "II Language",
    (0, 7): "Awareness",
    (0, 8): "Multidisciplinary Course",

    # II Year (Class 1)
    (1, 3): "Discrete Mathematics for Computer Science",
    (1, 4): "Statistics for Data Science",
    (1, 5): "General English",
    (1, 6): "Awareness",
    (1, 8): "Computer Organization and design",
    (1, 9): "Multidisciplinary Course",
    (1, 10): "Software Lab in Data Visualization",

    # III Year (Class 2)
    (2, 2): "Datamining and Machine Learning",
    (2, 3): "Operating Systems",
    (2, 4): "Optimization for Machine Learning",
    (2, 6): "Awareness",
    (2, 9): "Computer Networks",
    (2, 10): "Skill Enhancement Course",
    (2, 11): "Software Lab in Java",

    # IV Year (Class 3)
    (3, 0): "Cloud Computing",
    (3, 3): "Elective - II",
    (3, 7): "Awareness",
    (3, 9): "Research Methodology",
    (3, 10): "Elective - III",
    (3, 11): "Linux System Programming",

    # V Year (Class 4)
    (4, 0): "Cloud Computing",
    (4, 1): "Natural Language Processing",
    (4, 2): "Deep Learning",
    (4, 4): "Stochastic Processes",
    (4, 7): "Awareness Course",
}

def reset_lab_day_usage():
    for cls in lab_used_by_class_per_day:
        lab_used_by_class_per_day[cls].clear()

def assign_lab_periods_randomly():
    """
    Randomly assign lab periods for each class as per the lab_teacher_periods configuration.
    It ensures the teacher is marked as unavailable for the assigned lab slots.
    """
    for class_idx, teacher_periods in lab_teacher_periods.items():  #we are taking the class into idx and the its values 10: [3, 2, 2], into teacher_periods
        for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():
            # Find all available periods for the lab in the timetable (free periods)
            available_slots = [
                i for i in range(total_periods) if Timetable[i][class_idx] == 0 
                and main_teacher_list[i][teacher_id]["available"]
                #and labs.get(lab_number, False)  #if the lab is not availableavailable
            ]
            random.shuffle(available_slots)  #shuffling available slots
            
            sessions_assigned = 0
            for slot in available_slots:
                # Ensure the slot + consecutive periods don't exceed total periods
                if slot + consecutive_periods > total_periods:
                    continue  # Skip this slot if it cannot accommodate the full consecutive periods

                # Check if we can assign consecutive periods
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
                        break #also need to plan such that they don tcome on same day

#also same lab cant be assigned at same time to 2 diff classes
                if can_assign:
                    for i in range(consecutive_periods):
                        #Timetable[slot + i][class_idx] = teacher_list[teacher_id]["Name"] + f"(lab {lab_number})"
                        subject_name = subject_map.get((class_idx, teacher_id), "Lab")
                        Timetable[slot + i][class_idx] = f"{subject_name} (Lab {lab_number})"
                        main_teacher_list[slot + i][teacher_id]["available"] = False
                        class_to_teacher[class_idx][teacher_id] -= 1
                        labs[lab_number].append(slot + i)

                        day = (slot + i) // No_of_periods
                        if day not in lab_used_by_class_per_day[class_idx]:
                            lab_used_by_class_per_day[class_idx][day] = set()
                        lab_used_by_class_per_day[class_idx][day].add(lab_number)

                        sessions_assigned += 1

                    print(f"Assigned lab session {sessions_assigned} for class {class_idx} with teacher {teacher_id} at periods {slot} to {slot + consecutive_periods - 1}")
                if sessions_assigned == total_sessions:
                    break
        #labs[lab_number] = True  # Mark the lab as available again after assigning all sessions for that teacher

total_lab_periods = sum(
    block_info[0]# * block_info[1] 
    for class_periods in lab_teacher_periods.values() 
    for block_info in class_periods.values()
)
print("Total lab periods:", total_lab_periods)
# -------------------------------


FREE_TEACHERS = [t_id for t_id, info in teacher_list.items() if info["Name"].startswith("f")]
class_to_teacher = []

for class_idx in range(No_of_classes):
    teacher_part = [0] * No_of_teachers
    
    # 1. Assign Theory Periods
    assigned_theory = 0
    for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
        teacher_part[t_idx] = periods
        assigned_theory += periods

    # 2. Assign Lab Periods (Total number of periods spent in lab)
    assigned_labs = 0
    if class_idx in lab_teacher_periods:
        for t_id, info in lab_teacher_periods[class_idx].items():
            # info[0] is the total number of periods (e.g., 6)
            teacher_part[t_id] += info[0] 
            assigned_labs += info[0]

    # 3. Calculate Free Periods
    # Total periods (36) - Theory - Labs - Fixed (3)
    free_count = total_periods - assigned_theory - assigned_labs - fixed_periods_count
    print(f"free count for class {class_idx} is {free_count}")
    # Safety check: if free_count is negative, the schedule is impossible
    if free_count < 0:
        print(f"Warning: Class {class_idx} is over-scheduled by {abs(free_count)} periods!")
        free_count = 0

    free_teacher_index = FREE_TEACHERS[class_idx % len(FREE_TEACHERS)]
    teacher_part[free_teacher_index] = free_count

    # Priority list for the solver
    priority_list = list(range(No_of_teachers))
    row = teacher_part.copy()
    row.append(priority_list)
    class_to_teacher.append(row)



# clamp negative credits to zero (IMPORTANT)
for cls in range(No_of_classes):
    for t in range(No_of_teachers):
        if class_to_teacher[cls][t] < 0:
            class_to_teacher[cls][t] = 0
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

                # display cleanup
                if teacher in [info["Name"] for info in teacher_list.values() if info["Name"].startswith("f")]:
                    teacher = "free"

                print(f"{teacher:^7}", end="")

            print()
#print(main_teacher_list)
# ---------------- MRV SLOT SELECTION ----------------
def reset_labs():
    for x in range(total_periods):
        for y in range(No_of_classes):
            if isinstance(Timetable[x][y], str) and "(Lab" in Timetable[x][y]:
                Timetable[x][y] = 0

    # Reset teacher availability only for lab teachers
    for x in range(total_periods):
        for class_idx, teachers in lab_teacher_periods.items():
            for teacher_id in teachers:
                main_teacher_list[x][teacher_id]["available"] = True

def find_empty(Timetable, class_to_teacher, Tl):
    """
    Uses MRV (Minimum Remaining Values) heuristic.
    Chooses the empty slot with the fewest legal teachers.
    """

    best_cell = (-1, -1)
    class_with_min_avl_teachers = float("inf") 

    rows = list(range(len(Timetable)))
    random.shuffle(rows)

    for x in rows:     # iterate over periods
        for y in range(len(Timetable[0])):  # iterate over classes

            if Timetable[x][y] != 0:
                continue

            teacher_count = 0   #to count how many teachers can teach that class at that period

            for i in range(No_of_teachers):   #find how many teachers are available to teeach that class at that period
                if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:
                    #if credits remaining          #if not busy with other class
                    teacher_count += 1


            if teacher_count == 0:  # if no teacher is available... wither busy with that class or all credits over
                #continue
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
        if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:
            class_to_teacher[y][i] -= 1
            Tl[x][i]["available"] = False
            #Timetable[x][y] = Tl[x][i]["Name"]
            if (y, i) in subject_map:
                Timetable[x][y] = subject_map[(y, i)]
            else:
                Timetable[x][y] = Tl[x][i]["Name"]   # fallback (free periods etc.)
            if solve(Timetable, class_to_teacher, Tl):
                return True

            Timetable[x][y] = 0
            class_to_teacher[y][i] += 1
            Tl[x][i]["available"] = True
    return False

def re_randomize_lab_periods():
    # Randomly re-assign lab periods and try solving again
    for i in range(3):  # Try reshuffling up to 3 times
        print(f"Attempt {i+1} with new lab assignments:")
        reset_labs()
        assign_lab_periods_randomly()  # Re-randomize lab periods
        if solve(Timetable, class_to_teacher, main_teacher_list):
            print("Solution found!")
            print_timetable_classwise(Timetable)
            return True
    print("No solution found after reshuffling.")
    return False
def reset_everything():
    global Timetable, main_teacher_list, class_to_teacher

    # Reset timetable
    Timetable = []
    arr = [0] * No_of_classes
    for _ in range(total_periods):
        Timetable.append(arr.copy())

    # Reset fixed periods
    for i in range(len(Timetable[0])):
        Timetable[18][i] = "foyer"
        Timetable[30][i] = "iic"
        Timetable[31][i] = "iic"

    # Reset teachers
    main_teacher_list = [
        copy.deepcopy(teacher_list)
        for _ in range(total_periods)
    ]

    # Reset credits
    # (Rebuild class_to_teacher again using your original logic)
        # Rebuild class_to_teacher
    global class_to_teacher
    class_to_teacher = []

    FREE_TEACHERS = [t_id for t_id, info in teacher_list.items() if info["Name"].startswith("f")]

    for class_idx in range(No_of_classes):
        teacher_part = [0] * No_of_teachers

        assigned_theory = 0
        for t_idx, periods in class_teacher_periods.get(class_idx, {}).items():
            teacher_part[t_idx] = periods
            assigned_theory += periods

        assigned_labs = 0
        if class_idx in lab_teacher_periods:
            for t_id, info in lab_teacher_periods[class_idx].items():
                teacher_part[t_id] += info[0]
                assigned_labs += info[0]

        free_count = total_periods - assigned_theory - assigned_labs - fixed_periods_count
        if free_count < 0:
            free_count = 0

        free_teacher_index = FREE_TEACHERS[class_idx % len(FREE_TEACHERS)]
        teacher_part[free_teacher_index] = free_count

        priority_list = list(range(No_of_teachers))
        row = teacher_part.copy()
        row.append(priority_list)
        class_to_teacher.append(row)
def generate_timetable():
    global Timetable, main_teacher_list, class_to_teacher
    reset_everything()
    reset_lab_day_usage()
    assign_lab_periods_randomly()
    random.seed(10)

    if solve(Timetable, class_to_teacher, main_teacher_list):
        print_timetable_classwise(Timetable)
        export_all_classes_one_file(Timetable)
        log_file.close()
        return True
    else:
        print("No Solution!")
        log_file.close()
        return False
    


def show_class_timetable():
    cls = int(class_selector.get())

    display.delete("1.0", tk.END)

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    for day_index, day_name in enumerate(days):
        start = day_index * No_of_periods
        end = start + No_of_periods

        display.insert(tk.END, f"\n{day_name}\n")
        display.insert(tk.END, "-" * 60 + "\n")

        for period in range(start, end):
            subject = Timetable[period][cls]
            display.insert(tk.END, f"P{(period % 6)+1}: {subject}\n")

def generate_action():
    success = generate_timetable()
    if success:
        messagebox.showinfo("Success", "Timetable Generated!")
    else:
        messagebox.showerror("Error", "No Solution Found")

def export_action():
    export_all_classes_one_file(Timetable)
    messagebox.showinfo("Exported", "Exported to full_timetable.csv")



from flask import Flask, render_template_string, request, redirect

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>College Timetable Generator</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        table { border-collapse: collapse; margin-bottom: 30px; }
        th, td { border: 1px solid black; padding: 6px 10px; text-align: center; }
        th { background-color: #f2f2f2; }
        button { padding: 8px 15px; margin: 5px; }
    </style>
</head>
<body>

<h2>College Timetable Generator</h2>

<form method="post" action="/generate">
    <button type="submit">Generate Timetable</button>
</form>

<form method="post" action="/export">
    <button type="submit">Export to CSV</button>
</form>

<form method="get" action="/">
    <label>Select Class:</label>
    <select name="cls">
        {% for c in classes %}
        <option value="{{c}}" {% if c == selected %}selected{% endif %}>Class {{c}}</option>
        {% endfor %}
    </select>
    <button type="submit">Show Timetable</button>
</form>

{% if timetable %}
<h3>Class {{selected}} Timetable</h3>
<table>
<tr>
<th>Day</th>
{% for p in periods %}
<th>P{{p}}</th>
{% endfor %}
</tr>

{% for row in timetable %}
<tr>
{% for cell in row %}
<td>{{cell}}</td>
{% endfor %}
</tr>
{% endfor %}
</table>
{% endif %}

</body>
</html>
"""

def get_class_timetable(cls):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    result = []

    for day_index, day_name in enumerate(days[:No_of_days_in_week]):
        start = day_index * No_of_periods
        end = start + No_of_periods

        row = [day_name]
        for period in range(start, end):
            value = Timetable[period][cls]
            row.append(value)

        result.append(row)

    return result

@app.route("/", methods=["GET"])
def home():
    cls = int(request.args.get("cls", 0))
    timetable = get_class_timetable(cls)
    return render_template_string(
        HTML_TEMPLATE,
        classes=range(No_of_classes),
        selected=cls,
        timetable=timetable,
        periods=range(1, No_of_periods + 1)
    )

@app.route("/generate", methods=["POST"])
def generate():
    reset_everything()
    reset_lab_day_usage()
    assign_lab_periods_randomly()
    solve(Timetable, class_to_teacher, main_teacher_list)
    return redirect("/")

@app.route("/export", methods=["POST"])
def export():
    export_all_classes_one_file(Timetable)
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
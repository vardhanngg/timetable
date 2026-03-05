import random 
import copy 
import sys 

random.seed() 
#for puttong result in a file  
log_file = open("output.log", "w", encoding="utf-8") 
sys.stdout = log_file   

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
'''
#fixed periods 
for i in range(len(Timetable[0])):     
    Timetable[18][i] = "foyer"        
    Timetable[30][i] = "iic"         
    Timetable[31][i] = "iic"     
fixed_periods_count=3  
'''
fixed_periods_count=0
#----------------------------------------------------  
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
]                                   

No_of_teachers = len(teacher_list)  #total teachers including free teachers.   

# ---------------- REQUIRED PERIODS PER CLASS ----------------   
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
    4: {4: 5, 2: 5, 1: 5, 0: 5, 7: 2},            # V Year 
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

def reset_lab_day_usage():     
    for cls in lab_used_by_class_per_day:         
        lab_used_by_class_per_day[cls].clear()  

def assign_lab_periods_randomly():     
    """     
    Randomly assign lab periods for each class as per the lab_teacher_periods configuration.     
    It ensures the teacher is marked as unavailable for the assigned lab slots.     
    """     
    for class_idx, teacher_periods in lab_teacher_periods.items():  
        for teacher_id, (total_sessions, consecutive_periods, lab_number) in teacher_periods.items():             
            available_slots = [                 
                i for i in range(total_periods) if Timetable[i][class_idx] == 0                  
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
                    if (                         
                        Timetable[slot + i][class_idx] != 0 or                         
                        not main_teacher_list[slot + i][teacher_id]["available"] or                         
                        (slot // No_of_periods) != ((slot + i) // No_of_periods) or                         
                        (slot + i) in labs[lab_number] or                         
                        lab_number in lab_used_by_class_per_day[class_idx].get(day, set())                     
                    ):                         
                        can_assign = False                         
                        break 
                
                if can_assign:                     
                    for i in range(consecutive_periods):                         
                        Timetable[slot + i][class_idx] = teacher_list[teacher_id]["Name"] + f"(lab {lab_number})"                         
                        main_teacher_list[slot + i][teacher_id]["available"] = False                         
                        class_to_teacher[class_idx][teacher_id] -= 1                         
                        labs[lab_number].append(slot + i)                          
                        
                        day = (slot + i) // No_of_periods                         
                        if day not in lab_used_by_class_per_day[class_idx]:                             
                            lab_used_by_class_per_day[class_idx][day] = set()                         
                        lab_used_by_class_per_day[class_idx][day].add(lab_number)                          
                        
                        sessions_assigned += 1                      
                    print(f"Assigned lab session for class {class_idx} with teacher {teacher_id}")                 
                if sessions_assigned == total_sessions:                     
                    break         

total_lab_periods = sum(     
    block_info[0]      
    for class_periods in lab_teacher_periods.values()      
    for block_info in class_periods.values() 
) 
print("Total lab periods:", total_lab_periods) 

# -------------------------------   
FREE_TEACHERS = [t_id for t_id, info in teacher_list.items() if info["Name"].startswith("f")] 
class_to_teacher = []  

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
    print(f"free count for class {class_idx} is {free_count}")     
    if free_count < 0:         
        print(f"Warning: Class {class_idx} is over-scheduled!")         
        free_count = 0      

    free_teacher_index = FREE_TEACHERS[class_idx % len(FREE_TEACHERS)]     
    teacher_part[free_teacher_index] = free_count      
    
    priority_list = list(range(No_of_teachers))     
    row = teacher_part.copy()     
    row.append(priority_list)     
    class_to_teacher.append(row)    

for cls in range(No_of_classes):     
    for t in range(No_of_teachers):         
        if class_to_teacher[cls][t] < 0:             
            class_to_teacher[cls][t] = 0 

# ---------------- PRINT FUNCTION ----------------  
def print_timetable_classwise(Timetable):     
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]     
    days = all_days[:No_of_days_in_week]      
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
                if teacher in [info["Name"] for info in teacher_list.values() if info["Name"].startswith("f")]:                     
                    teacher = "free"                  
                print(f"{str(teacher):^7}", end="")              
            print() 

# ---------------- MRV SLOT SELECTION ---------------- 
def reset_labs():     
    for x in range(total_periods):         
        for y in range(No_of_classes):             
            if isinstance(Timetable[x][y], str) and "(lab" in Timetable[x][y]:                 
                Timetable[x][y] = 0     
    for x in range(total_periods):         
        for class_idx, teachers in lab_teacher_periods.items():             
            for teacher_id in teachers:                 
                main_teacher_list[x][teacher_id]["available"] = True   

def find_empty(Timetable, class_to_teacher, Tl):     
    best_cell = (-1, -1)     
    class_with_min_avl_teachers = float("inf")       
    rows = list(range(len(Timetable)))     
    random.shuffle(rows)      

    for x in rows:         
        for y in range(len(Timetable[0])):              
            if Timetable[x][y] != 0:                 
                continue              
            teacher_count = 0              
            for i in range(No_of_teachers):                 
                if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:                     
                    teacher_count += 1               
            if teacher_count == 0:                 
                return x, y              
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
    if x == -1:         
        return True      

    priority_list = class_to_teacher[y][-1].copy()     
    random.shuffle(priority_list)     
    for i in priority_list:         
        if class_to_teacher[y][i] > 0 and Tl[x][i]["available"]:             
            class_to_teacher[y][i] -= 1             
            Tl[x][i]["available"] = False             
            Timetable[x][y] = Tl[x][i]["Name"]              
            if solve(Timetable, class_to_teacher, Tl):                 
                return True              
            Timetable[x][y] = 0             
            class_to_teacher[y][i] += 1             
            Tl[x][i]["available"] = True     
    return False  

reset_lab_day_usage() 
assign_lab_periods_randomly() 

if solve(Timetable, class_to_teacher, main_teacher_list):     
    print_timetable_classwise(Timetable) 
else:     
    print("No Solution!") 
log_file.close()
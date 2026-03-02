import random
No_of_classes=7
No_of_teachers=10
No_of_days_in_week=6
No_of_periods=6
Timetable=[]
br=[]
crr=0
arr=[]




#making the timetable box with default input 0
for i in range(No_of_classes):
        crr=0
        arr.append(crr)
for j in range(No_of_days_in_week*No_of_periods):
     Timetable.append(arr.copy())

#print(Timetable)

#below - making the class to teacher
pseudo_random_order=[[],0]
max_index=No_of_teachers
pseudo_random_order[0]=list(range(max_index))
random.shuffle(pseudo_random_order[0])
print(pseudo_random_order)
crr=0
arr=[]
class_to_teacher=[] # classes X teachers
'''
for i in range(No_of_teachers):
       crr=3
       arr.append(crr)
       random.shuffle(pseudo_random_order[0])
       #arr.append(pseudo_random_order.copy())
       arr.append([pseudo_random_order[0][:], pseudo_random_order[1]]) #gpt

for j in range(No_of_classes):
       class_to_teacher.append(arr.copy())
'''
for i in range(No_of_teachers):
       crr=3
       arr.append(crr)
for j in range(No_of_classes):
       #class_to_teacher.append(arr.copy())
        row = arr.copy()
        pseudo_random_order=[list(range(No_of_teachers)),0]
        random.shuffle(pseudo_random_order[0])
        row.append(pseudo_random_order)
        class_to_teacher.append(row)

#print(class_to_teacher)

teacher_list = {
    0:  {"Name": "t1",  "no_of_hours": 4, "available": False},
    1:  {"Name": "t2",  "no_of_hours": 4, "available": True},
    2:  {"Name": "t3",  "no_of_hours": 4, "available": True},
    3:  {"Name": "t4",  "no_of_hours": 4, "available": True},
    4:  {"Name": "t5",  "no_of_hours": 4, "available": True},
    5:  {"Name": "t6",  "no_of_hours": 4, "available": True},
    6:  {"Name": "t7",  "no_of_hours": 4, "available": True},
    7:  {"Name": "t8",  "no_of_hours": 4, "available": True},
    8:  {"Name": "t9",  "no_of_hours": 4, "available": True},
    9:  {"Name": "t10", "no_of_hours": 4, "available": True},
}

def same_teacher_today(Timetable, x, y, teacher):
    day_start = (x // No_of_periods) * No_of_periods
    for i in range(day_start, x):
        if Timetable[i][y] == teacher:
            return True
    return False


#print(teacher_lis)
def available_resetter(Tl,i,j):   #np=no. of periods in a week ==no of in a week * no. of periods in a day, i is which period 
    if(j==0):
        for t in Tl:
               Tl[t]["available"] = True
             #Tl["available"]=True                                         #we are in out of (np*no of days in a week)
                                           #i is which period we are in 
                                            #trying to reset every next period
                                
def find_empty(Timetable,Tl):
    empty=[]
    for i in range (len(Timetable)):
       # print(f"i now in {i}")
        for j in range (len(Timetable[0])):
           # available_resetter(Tl,i,j)     #1. removed 
            #print(f"j now in {j}")
            #print(x[i][j])
            if Timetable[i][j] == 0  or  Timetable[i][j] == "":
                #print(f"tried {i} and {j}")
                empty.append((i,j))
    if not empty:
        
        return -1,-1
    return random.choice(empty) 

def reset_available(x):
     for i in range(len(x)):
        x[i]["available"]=True

     
def find_teacher(Timetable, class_to_teacher, x, y, Tl):
    order, index = class_to_teacher[y][-1]

    while index < len(order):
        i = order[index]
        class_to_teacher[y][-1][1] += 1  # advance pointer

        if (
    class_to_teacher[y][i] > 0
    and Tl[i]["available"]
    and not same_teacher_today(Timetable, x, y, Tl[i]["Name"])
):

            class_to_teacher[y][i] -= 1
            Tl[i]["available"] = False
            return i

        index = class_to_teacher[y][-1][1]

    return -1
 

'''
for i in range(No_of_classes):
        crr=0
        arr.append(crr)
for j in range(No_of_days_in_week*No_of_periods):
     Timetable.append(arr)'''

def print_timetable(x):
     for i in range(len(x)):
          print(f'printing row {i}-{x[i]}')

def solve(Timetable, class_to_teacher, Tl):
    x, y = find_empty(Timetable, Tl)
    if x == -1:
        return True

    if y == 0:
        reset_available(Tl)
        for c in range(No_of_classes):
            random.shuffle(class_to_teacher[c][-1][0])

    #  RESET teacher-try pointer for THIS SLOT
    class_to_teacher[y][-1][1] = 0

    while True:
        e = find_teacher(Timetable, class_to_teacher, x, y, Tl)
        print(f'e i {e}')

        if e == -1:
            break

        Timetable[x][y] = Tl[e]["Name"]

        if solve(Timetable, class_to_teacher, Tl):
            return True

        # BACKTRACK
        Timetable[x][y] = 0
        class_to_teacher[y][e] += 1
        Tl[e]["available"] = True

    # ONLY now allow free
    Timetable[x][y] = "free"
    if solve(Timetable, class_to_teacher, Tl):
        return True

    Timetable[x][y] = 0
    return False

     
#print_timetable(Timetable)
solve(Timetable,class_to_teacher,teacher_list)
#print(solve==0)
print_timetable(Timetable)
print_timetable(class_to_teacher)
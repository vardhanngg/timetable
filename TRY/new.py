'''class timetable:
    def __init__(self):
        self.name = ""
       '''
No_of_classes=7
No_of_teachers=10
No_of_days_in_week=6
No_of_periods=6
Timetable=[]
br=[]
crr=0
arr=[]
for i in range(No_of_classes):
        crr=i
        arr.append(crr)
for j in range(No_of_days_in_week*No_of_periods):
     Timetable.append(arr)
print(Timetable)
crr=0
arr=[]
C_T=[]
for i in range(No_of_teachers):
       crr=3
       arr.append(crr)
for j in range(No_of_classes):
       C_T.append(arr)

print(C_T)

teacher_list={0:"a",1:"b",2:"c",}
print(teacher_list)
def find_empty(x):
    for i in range (len(x)):
       # print(f"i now in {i}")
        for j in range (len(x[0])):
        #    print(f"j now in {j}")
            print(x[i][j])
            if x[i][j] == 0  or  x[i][j] == "":
                print(f"tried {i} and {j}")
                return i, j
    return -1,-1
def find_teacher(x,y):
    for i in range (len(x[0])):
          if x[y][i]==0:
               return i
    return -1
x=""
y=""
print(" ")
while(True):
    x,y=find_empty(Timetable)
    if x==-1:
         break
    e=find_teacher(C_T,y)
    break
    #if e==-1: #need to implement
         #use free cases

def solve(){
    x,y=find_empty(Timetable)
    if x==-1:
        return 1
    e=find_teacher(C_T,y)
    #if e==-1: #need to implement
         #use free cases

     
}
import random
import copy
import sys
import csv
import os
from flask import Flask, render_template_string, request, redirect

random.seed(10)

# --- BASIC CONFIG ---
No_of_classes = 5
No_of_days_in_week = 6
No_of_periods = 6
total_periods = No_of_days_in_week * No_of_periods

# --- HARDCODED INPUTS FROM YOUR DATA ---
# (Using unique IDs for "No Faculty" to prevent solver collisions)
teacher_list = {
    0: {"Name": "S1", "available": True},
    1: {"Name": "S2", "available": True},
    2: {"Name": "S3", "available": True},
    3: {"Name": "S4", "available": True},
    4: {"Name": "S5", "available": True},
    5: {"Name": "S6", "available": True},
    6: {"Name": "S7", "available": True},
    7: {"Name": "S8", "available": True},
    8: {"Name": "S99 (Guest 1)", "available": True}, # No Faculty placeholder
    9: {"Name": "S100 (Guest 2)", "available": True}, # No Faculty placeholder
    10: {"Name": "f1", "available": True}, # Filler for Class 0
    11: {"Name": "f2", "available": True}, # Filler for Class 1
    12: {"Name": "f3", "available": True}, # Filler for Class 2
    13: {"Name": "f4", "available": True}, # Filler for Class 3
    14: {"Name": "f5", "available": True}  # Filler for Class 4
}

# Updated based on your table
class_teacher_periods = {
    0: {5: 3, 6: 3, 1: 4, 4: 4, 7: 2, 8: 3},         # Class 1
    1: {5: 3, 8: 2, 3: 4, 4: 4, 6: 2},               # Class 2
    2: {3: 4, 9: 3, 4: 5, 2: 5, 6: 2},               # Class 3
    3: {8: 2, 3: 4, 0: 4, 7: 2},                     # Class 4
    4: {4: 5, 2: 5, 1: 5, 0: 5, 7: 2}                # Class 5
}

# Updated based on your images (Total, Block, Room)
lab_teacher_periods = {
    0: {1: [6, 2, 1], 2: [2, 2, 1]},  # C Lab (6 hrs), Python Lab (2 hrs)
    1: {9: [4, 2, 2]},                # Data Vis (4 hrs)
    2: {8: [6, 2, 3]}                 # Java Lab (6 hrs)
}

subject_map = {
    (0, 5): "General English", (0, 6): "II Language", (0, 1): "Problem Solving (C)",
    (0, 4): "Calculus", (0, 7): "Awareness", (0, 8): "Multidisciplinary",
    (1, 5): "General English", (1, 8): "Multidisciplinary", (1, 3): "Discrete Math",
    (1, 4): "Statistics", (1, 6): "Awareness",
    (2, 3): "OS", (2, 9): "Skill Enhancement", (2, 4): "Optimization ML",
    (2, 2): "Datamining ML", (2, 6): "Awareness",
    (3, 8): "Research Methodology", (3, 3): "Elective II", (3, 0): "Cloud Computing", (3, 7): "Awareness",
    (4, 4): "Stochastic Processes", (4, 2): "Deep Learning", (4, 1): "NLP", (4, 0): "Cloud Computing", (4, 7): "Awareness"
}

# --- SOLVER CORE ---
Timetable = []
main_teacher_list = []
class_to_teacher = []
labs = {1: [], 2: [], 3: []}

def reset_everything():
    global Timetable, main_teacher_list, class_to_teacher, labs
    Timetable = [[0 for _ in range(No_of_classes)] for _ in range(total_periods)]
    main_teacher_list = [copy.deepcopy(teacher_list) for _ in range(total_periods)]
    labs = {1: [], 2: [], 3: []}
    
    class_to_teacher = []
    for cls_idx in range(No_of_classes):
        credits = [0] * len(teacher_list)
        # Add Theory
        for t_id, hrs in class_teacher_periods.get(cls_idx, {}).items():
            credits[t_id] = hrs
        # Add Labs
        for t_id, lab_info in lab_teacher_periods.get(cls_idx, {}).items():
            credits[t_id] = lab_info[0]
        
        # Calculate Free Periods (No fixed periods as requested)
        used = sum(credits)
        free_hrs = max(0, total_periods - used)
        filler_id = 10 + cls_idx
        credits[filler_id] = free_hrs
        
        credits.append(list(range(len(teacher_list))))
        class_to_teacher.append(credits)

def assign_lab_periods_randomly():
    for cls_idx, t_labs in lab_teacher_periods.items():
        for t_id, (total, block, room_no) in t_labs.items():
            assigned = 0
            # Try to place blocks
            attempts = 0
            while assigned < total and attempts < 100:
                attempts += 1
                slot = random.randint(0, total_periods - block)
                
                # Boundary check: Lab cannot span across two days
                if (slot // No_of_periods) != ((slot + block - 1) // No_of_periods):
                    continue
                
                can_place = True
                for i in range(block):
                    if (Timetable[slot+i][cls_idx] != 0 or 
                        not main_teacher_list[slot+i][t_id]["available"] or
                        (slot+i) in labs[room_no]):
                        can_place = False
                        break
                
                if can_place:
                    subj = subject_map.get((cls_idx, t_id), "Lab")
                    for i in range(block):
                        Timetable[slot+i][cls_idx] = f"{subj} (L{room_no})"
                        main_teacher_list[slot+i][t_id]["available"] = False
                        class_to_teacher[cls_idx][t_id] -= 1
                        labs[room_no].append(slot+i)
                    assigned += block

def solve(T, C2T, TL):
    # Find Empty with MRV
    min_val = float('inf')
    best_cell = None
    
    for r in range(total_periods):
        for c in range(No_of_classes):
            if T[r][c] == 0:
                count = sum(1 for i in range(len(teacher_list)) if C2T[c][i] > 0 and TL[r][i]["available"])
                if count < min_val:
                    min_val = count
                    best_cell = (r, c)
    
    if not best_cell: return True
    r, c = best_cell
    
    choices = C2T[c][-1].copy()
    random.shuffle(choices)
    for t_id in choices:
        if C2T[c][t_id] > 0 and TL[r][t_id]["available"]:
            C2T[c][t_id] -= 1
            TL[r][t_id]["available"] = False
            T[r][c] = subject_map.get((c, t_id), teacher_list[t_id]["Name"])
            
            if solve(T, C2T, TL): return True
            
            T[r][c] = 0
            TL[r][t_id]["available"] = True
            C2T[c][t_id] += 1
    return False

# --- FLASK APP ---
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    cls = int(request.args.get("cls", 0))
    days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    display_table = []
    
    if Timetable:
        for d_idx, d_name in enumerate(days_names):
            row = [d_name]
            for p in range(No_of_periods):
                val = Timetable[d_idx * No_of_periods + p][cls]
                if isinstance(val, str) and (val.startswith('f1') or val.startswith('f2') or val.startswith('f3') or val.startswith('f4') or val.startswith('f5')):
                    val = "Free"
                row.append(val)
            display_table.append(row)

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Hardcoded Solver</title><style>
        body { font-family: sans-serif; padding: 20px; background: #f4f4f9; }
        table { border-collapse: collapse; width: 100%; background: white; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: center; }
        th { background-color: #007bff; color: white; }
        .btn { padding: 10px 20px; background: #28a745; color: white; border: none; cursor: pointer; border-radius: 4px; }
    </style></head>
    <body>
        <h2>College Timetable Generator (Clean Solve)</h2>
        <form method="POST" action="/generate" style="display:inline;"><button class="btn">Generate New</button></form>
        <form method="GET" action="/" style="display:inline; margin-left:20px;">
            <select name="cls" onchange="this.form.submit()">
                {% for i in range(5) %}<option value="{{i}}" {% if i == selected %}selected{% endif %}>Class {{i+1}}</option>{% endfor %}
            </select>
        </form>
        {% if table %}
        <table>
            <tr><th>Day</th>{% for p in range(1,7) %}<th>P{{p}}</th>{% endfor %}</tr>
            {% for row in table %}<tr>{% for cell in row %}<td>{{cell}}</td>{% endfor %}</tr>{% endfor %}
        </table>
        {% endif %}
    </body></html>
    """, table=display_table, selected=cls)

@app.route("/generate", methods=["POST"])
def generate():
    reset_everything()
    assign_lab_periods_randomly()
    solve(Timetable, class_to_teacher, main_teacher_list)
    return redirect("/")

if __name__ == "__main__":
    reset_everything() # Initialize on startup
    app.run(host="0.0.0.0", port=5000, debug=True)
from flask import Flask, render_template, request, redirect
from config import CONFIG
from utils import setup_progress

from solver import generate_timetable
from adapter import (build_solver_inputs_from_classes)

app = Flask(__name__)

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------
@app.route("/")
def home():
    return redirect("/setup/basic")

# --------------------------------------------------
# BASIC INFORMATION
# --------------------------------------------------
@app.route("/setup/classes", methods=["GET", "POST"])
def setup_classes():
    if request.method == "POST":
        class_name = request.form["class"]
        entry_type = request.form["type"]  # theory / lab

        entry = {
            "subject": request.form["subject"],
            "hours": int(request.form["hours"]),
            "teacher": request.form["teacher"],
            "type": entry_type
        }

        if entry_type == "lab":
            entry["continuous"] = int(request.form["continuous"])
            entry["lab_no"] = int(request.form["lab_no"])

        CONFIG["classes"].setdefault(class_name, []).append(entry)

    return render_template(
        "classes.html",
        classes=CONFIG["classes"],
        labs=CONFIG["labs"]
    )

@app.route("/setup/basic", methods=["GET", "POST"])
def setup_basic():
    if request.method == "POST":
        CONFIG["basic_info"] = {
            "institute_name": request.form["institute"],
            "academic_year": request.form["year"],
            "working_days": int(request.form["days"])
        }
        return redirect("/setup/bell")
    return render_template("basic.html")

# --------------------------------------------------
# BELL SCHEDULE
# --------------------------------------------------
@app.route("/setup/bell", methods=["GET", "POST"])
def setup_bell():
    if request.method == "POST":
        CONFIG["bell_schedule"] = {
            "periods_per_day": int(request.form["periods"])
        }
        return redirect("/setup/faculty")
    return render_template("bell.html")

# --------------------------------------------------
# FACULTY
# --------------------------------------------------
@app.route("/setup/faculty", methods=["GET", "POST"])
def setup_faculty():
    if request.method == "POST":
        fid = len(CONFIG["faculty"])
        CONFIG["faculty"][fid] = {
            "name": request.form["name"],
            "max_load": int(request.form["max_load"])
        }
    return render_template("faculty.html", faculty=CONFIG["faculty"])

# --------------------------------------------------
# GRADES & DIVISIONS
# --------------------------------------------------
@app.route("/setup/grades", methods=["GET", "POST"])
def setup_grades():
    if request.method == "POST":
        grade = request.form["grade"]
        division = request.form["division"]
        CONFIG["grades"].setdefault(grade, []).append(division)
    return render_template("grades.html", grades=CONFIG["grades"])

# --------------------------------------------------
# SUBJECTS
# --------------------------------------------------
@app.route("/setup/subjects", methods=["GET", "POST"])
def setup_subjects():
    if request.method == "POST":
        sid = len(CONFIG["subjects"])
        CONFIG["subjects"][sid] = {
            "name": request.form["name"],
            "type": request.form["type"]
        }
    return render_template("subjects.html", subjects=CONFIG["subjects"])

# --------------------------------------------------
#labs
@app.route("/setup/labs", methods=["GET", "POST"])
def setup_labs():
    if request.method == "POST":
        lab_no = int(request.form["lab_no"])
        lab_name = request.form["lab_name"]
        CONFIG["labs"][lab_no] = lab_name

    return render_template("labs.html", labs=CONFIG["labs"])

# LESSONS
# --------------------------------------------------
@app.route("/setup/lessons", methods=["GET", "POST"])
def setup_lessons():
    if request.method == "POST":
        CONFIG["lessons"].append({
            "grade": request.form["grade"],
            "division": request.form["division"],
            "subject": request.form["subject"],
            "faculty": request.form["faculty"],
            "periods": int(request.form["periods"]),
            "consecutive": int(request.form.get("consecutive", 1))
        })
    return render_template(
        "lessons.html",
        lessons=CONFIG["lessons"],
        grades=CONFIG["grades"],
        subjects=CONFIG["subjects"],
        faculty=CONFIG["faculty"]
    )

# --------------------------------------------------
# GENERATE TIMETABLE
# --------------------------------------------------
from adapter import build_solver_inputs_from_classes
@app.route("/generate")
def generate():
    # ---------- basic checks ----------
    if not CONFIG["basic_info"] or not CONFIG["bell_schedule"]:
        return "<h3>Please complete basic info and bell schedule</h3>"

    if not CONFIG["classes"]:
        return "<h3>Please add at least one class</h3>"

    # ---------- BASIC VALIDATION (PASTE HERE) ----------
    total_slots = (
        CONFIG["basic_info"]["working_days"]
        * CONFIG["bell_schedule"]["periods_per_day"]
    )

    for cls, items in CONFIG["classes"].items():
        total_hours = sum(i["hours"] for i in items)
        if total_hours > total_slots:
            return f"<h3>{cls} exceeds available periods</h3>"

    # ---------- build solver inputs ----------
    (
        No_of_classes,
        teacher_list,
        class_teacher_periods,
        lab_teacher_periods,
        subject_map
    ) = build_solver_inputs_from_classes(CONFIG)

    No_of_days_in_week = CONFIG["basic_info"]["working_days"]
    No_of_periods = CONFIG["bell_schedule"]["periods_per_day"]

    # ---------- call solver ----------
    timetable = generate_timetable(
        No_of_classes,
        No_of_days_in_week,
        No_of_periods,
        teacher_list,
        class_teacher_periods,
        lab_teacher_periods,
        subject_map,
        fixed_periods=None
    )

    if not timetable:
        return "<h3>No solution found ❌</h3>"

    CONFIG["timetable"] = timetable
    return redirect("/view")
# --------------------------------------------------
#view
@app.route("/view")
def view():
    timetable = CONFIG.get("timetable")
    if not timetable:
        return "<h3>No timetable generated yet</h3>"

    class_names = list(CONFIG["classes"].keys())
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    return render_template(
        "view.html",
        timetable=timetable,
        class_names=class_names,
        days=days,
        periods=range(1, CONFIG["bell_schedule"]["periods_per_day"] + 1)
    )
#export


@app.route("/export")
def export():
    timetable = CONFIG.get("timetable")
    if not timetable:
        return "<h3>No timetable to export</h3>"

    class_names = list(CONFIG["classes"].keys())
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    periods_per_day = CONFIG["bell_schedule"]["periods_per_day"]

    with open("timetable.csv", "w", newline="") as f:
        writer = csv.writer(f)

        for cidx, cname in enumerate(class_names):
            writer.writerow([cname])
            writer.writerow(["Day"] + [f"P{p}" for p in range(1, periods_per_day + 1)])

            for d in range(CONFIG["basic_info"]["working_days"]):
                row = [days[d]]
                for p in range(periods_per_day):
                    row.append(timetable[d * periods_per_day + p][cidx])
                writer.writerow(row)

            writer.writerow([])

    return "<h3>Exported timetable.csv successfully ✅</h3>"
# RUN
# --------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
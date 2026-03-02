import os
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename

# Import your custom modules
from config import CONFIG
from utils import setup_progress
from solver import generate_timetable
from process_pdf import extract_to_solver_format  # Your Groq logic

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'

# --------------------------------------------------
# PDF UPLOAD & EXTRACTION
# --------------------------------------------------
@app.route("/upload-pdf", methods=["GET", "POST"])
def upload_pdf():
    if request.method == "POST":
        if 'file' not in request.files:
            return "No file part"
        file = request.files['file']
        if file.filename == '':
            return "No selected file"

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            try:
                # 1. Use Groq/Llama 3.3 to extract data from PDF
                # Make sure your TOGETHER_API_KEY or GROQ_API_KEY is set in environment
                api_key = os.environ.get("GROQ_API_KEY")
                raw_data = extract_to_solver_format(file_path, api_key)

                # 2. Map AI output to your global CONFIG
                # This bypasses manual entry in /setup/faculty etc.
                CONFIG["classes"] = raw_data.get("classes", {})
                CONFIG["faculty"] = raw_data.get("teacher_list", {})
                CONFIG["basic_info"]["working_days"] = raw_data.get("working_days", 5)
                CONFIG["bell_schedule"]["periods_per_day"] = raw_data.get("periods_per_day", 8)
                
                # Store raw data for adapter use
                CONFIG["raw_extraction"] = raw_data

                return redirect(url_for('generate'))
            except Exception as e:
                return f"❌ Extraction failed: {str(e)}"

    return render_template("upload.html")

# --------------------------------------------------
# GENERATE TIMETABLE (Updated for AI input)
# --------------------------------------------------
@app.route("/generate")
def generate():
    # If we have AI extraction, use it. Otherwise, use manual adapter logic.
    if "raw_extraction" in CONFIG:
        data = CONFIG["raw_extraction"]
        
        # Format the subject_map keys from "0,1" string to (0, 1) tuple
        formatted_subject_map = {
            tuple(map(int, k.split(','))): v 
            for k, v in data['subject_map'].items()
        }

        timetable = generate_timetable(
            No_of_classes=data['No_of_classes'],
            No_of_days_in_week=CONFIG["basic_info"]["working_days"],
            No_of_periods=CONFIG["bell_schedule"]["periods_per_day"],
            teacher_list={int(k): v for k, v in data['teacher_list'].items()},
            class_teacher_periods={int(k): {int(tk): tv for tk, tv in v.items()} for k, v in data['class_teacher_periods'].items()},
            lab_teacher_periods={int(k): {int(tk): tv for tk, tv in v.items()} for k, v in data['lab_teacher_periods'].items()},
            subject_map=formatted_subject_map
        )
    else:
        # Fallback to manual entry adapter
        from adapter import build_solver_inputs_from_classes
        # ... (your existing build_solver_inputs_from_classes logic) ...

    if not timetable:
        return "<h3>No solution found ❌</h3>"

    CONFIG["timetable"] = timetable
    return redirect("/view")

# ... (rest of your /view and /export routes) ...

if __name__ == "__main__":
    app.run(debug=True)
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
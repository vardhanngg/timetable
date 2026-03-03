import os
import json
import csv
from flask import Flask, render_template, request, redirect, url_for, jsonify

# Custom modules
from config import CONFIG
from solver import generate_timetable
from adapter import build_solver_inputs_from_classes
from extractor import get_solver_data_from_pdf 

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath('uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route("/")
def home():
    return render_template("upload.html")

@app.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return "No file selected", 400

    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], "uploaded_schedule.pdf")
    file.save(pdf_path)
    
    try:
        raw_data = get_solver_data_from_pdf(pdf_path) 
        with open("last_extraction.json", "w") as f:
            json.dump(raw_data, f)
        
        CONFIG["raw_extraction"] = raw_data
        return redirect(url_for('generate'))
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"AI Extraction Failed: {str(e)}", 500

@app.route("/generate")
def generate():
    data = CONFIG.get("raw_extraction")
    if not data and os.path.exists("last_extraction.json"):
        with open("last_extraction.json", "r") as f:
            data = json.load(f)
    
    if not data:
        return "<h3>No data found. Please upload a PDF first.</h3>"

    try:
        display_data = []
        teacher_map = data.get('teacher_list', {})

        # Process Theory
        for class_id, teachers in data.get('class_teacher_periods', {}).items():
            for t_id, info in teachers.items():
                subj = info.get('subject', 'Theory') if isinstance(info, dict) else "Theory"
                p_val = info.get('periods', 0) if isinstance(info, dict) else info

                display_data.append({
                    "class": f"Class {class_id}",
                    "subject": subj,
                    "teacher": teacher_map.get(str(t_id), {}).get('Name', f"S{t_id}"),
                    "type": "Theory",
                    "periods": p_val
                })

        # Process Labs
        for class_id, labs in data.get('lab_teacher_periods', {}).items():
            for t_id, info in labs.items():
                subj = info.get('subject', 'Lab') if isinstance(info, dict) else "Lab"
                p_raw = info.get('periods', [0]) if isinstance(info, dict) else [info]
                p_count = p_raw[0] if (isinstance(p_raw, list) and len(p_raw) > 0) else 0

                display_data.append({
                    "class": f"Class {class_id}",
                    "subject": subj,
                    "teacher": teacher_map.get(str(t_id), {}).get('Name', f"S{t_id}"),
                    "type": "Lab",
                    "periods": p_count
                })

        return render_template("view_simple.html", rows=display_data)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"<h3>Data Processing Error: {str(e)}</h3>"


# CLEANED: Only one version of success_summary using dynamic metadata
@app.route("/success-summary")
def success_summary():
    if not os.path.exists("generated_timetable.json") or not os.path.exists("generated_metadata.json"):
        return redirect(url_for('home'))
        
    with open("generated_timetable.json", "r") as f:
        timetable = json.load(f)
    with open("generated_metadata.json", "r") as f:
        meta = json.load(f)
    with open("final_schedule.json", "r") as f:
        final_data = json.load(f)
    
    # Get unique class names from the final data verified by the user
    class_names = list(dict.fromkeys([row['class'] for row in final_data]))
    
    return render_template("success.html", 
                           timetable=timetable, 
                           num_classes=meta['num_classes'],
                           class_names=class_names,
                           num_days=meta['days'], 
                           periods_per_day=meta['periods'])





# --- KEEP THIS VERSION (REPLACES THE TWO OLD ONES) ---
@app.route("/update-data", methods=["POST"])
def update_data():
    try:
        incoming_payload = request.get_json()
        web_data = incoming_payload.get('table_data', [])
        config = incoming_payload.get('config', {})
        
        # Create a mapping of teacher names to unique IDs
        all_teachers = sorted(list(set(row['teacher'] for row in web_data)))
        t_name_to_id = {name: i for i, name in enumerate(all_teachers)}

        organized_classes = {}
        for row in web_data:
            c_name = row['class'].replace("Class ", "").strip()
            if c_name not in organized_classes: 
                organized_classes[c_name] = []
            
            organized_classes[c_name].append({
                "teacher": row.get('teacher', 'Unknown'),
                "teacher_id": t_name_to_id.get(row.get('teacher'), 99), # Numeric ID!
                "subject": row.get('subject', 'General'),
                "hours": int(row.get('periods', 0)),
                "type": row.get('type', 'theory').lower(),
                "continuous": int(row.get('continuous', 1)),
                "lab_no": int(row.get('lab_no', 0))
            })

        session_data = {
            "organized": organized_classes,
            "days": int(config.get('days', 6)),
            "periods": int(config.get('periods', 6))
        }
        with open("temp_web_data.json", "w") as f:
            json.dump(session_data, f)

        return jsonify({"status": "success", "redirect": url_for('setup_fixed')})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# .................
@app.route("/setup-fixed")
def setup_fixed():
    if not os.path.exists("temp_web_data.json"):
        return redirect(url_for('home'))
        
    with open("temp_web_data.json", "r") as f:
        stored = json.load(f)
    
    return render_template("fixed_setup.html", 
                           days=stored['days'], 
                           periods=stored['periods'], 
                           class_data=stored['organized'])

@app.route("/run-final-solver", methods=["POST"])
def run_final_solver():
    try:
        fixed_data = request.get_json().get('fixed_slots', {})
        
        if not os.path.exists("temp_web_data.json"):
            return jsonify({"status": "error", "message": "Session expired. Please restart."}), 400

        with open("temp_web_data.json", "r") as f:
            stored = json.load(f)

        from adapter import build_final_inputs 
        
        (No_of_classes, t_list, c_theory, l_periods, subj_map) = build_final_inputs(
            {"classes": stored['organized']}, 
            stored['days'], 
            stored['periods'], 
            fixed_data
        )

        final_timetable = generate_timetable(
            No_of_classes, stored['days'], stored['periods'], t_list, 
            c_theory, l_periods, subj_map, 
            fixed_periods=fixed_data
        )

        if final_timetable:
            # 1. Save metadata for the success page
            with open("generated_metadata.json", "w") as f:
                json.dump({
                    "days": stored['days'], 
                    "periods": stored['periods'], 
                    "num_classes": No_of_classes
                }, f)
            
            # 2. Save the actual timetable
            with open("generated_timetable.json", "w") as f:
                json.dump(final_timetable, f)

            # 3. Create the 'final_schedule.json' that success_summary expects
            # We reconstruct it from the 'organized' data
            flat_rows = []
            for c_name, teachers in stored['organized'].items():
                for t in teachers:
                    flat_rows.append({"class": f"Class {c_name}", "teacher": t['teacher']})
            
            with open("final_schedule.json", "w") as f:
                json.dump(flat_rows, f)

            return jsonify({"status": "success", "redirect": url_for('success_summary')})
        
        return jsonify({"status": "error", "message": "Solver failed. Likely a teacher collision."})
    except Exception as e:
        import traceback
        print(traceback.format_exc()) # Check your terminal to see the real error!
        return jsonify({"status": "error", "message": str(e)}), 500



        
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
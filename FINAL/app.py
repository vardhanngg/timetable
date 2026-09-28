import os
import logging
import json
import csv
import uuid
import time
import re
import traceback
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import io
from flask import send_file
from xml.sax.saxutils import escape
# Custom modules
from solver import generate_timetable, generate_timetable_with_retry
from adapter import build_solver_inputs_from_classes
from extractor import get_solver_data_from_pdf 
import xml.etree.ElementTree as ET

# ============================================================================
# FONT REGISTRATION FOR RENDER COMPATIBILITY
# ============================================================================
# When deployed to Render, the container is minimal and doesn't have system
# fonts installed by default. This function attempts to register TrueType fonts
# that will be installed by the Dockerfile, so ReportLab can use them.
# ============================================================================

def register_fonts():
    """
    Register TrueType fonts that are available in Render's container.
    ReportLab defaults to PostScript fonts which don't exist in minimal containers.
    This function is called on app startup.
    """
    try:
        from reportlab.pdfbase import pdfmetrics, ttfonts
        
        font_paths = [
            ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'DejaVu'),
            ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'DejaVu-Bold'),
            ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 'LiberationSans'),
            ('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 'LiberationSans-Bold'),
        ]
        
        for font_path, font_name in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(ttfonts.TTFont(font_name, font_path))
                    print(f"✓ Registered font: {font_name}")
                except Exception as e:
                    print(f"⚠ Could not register {font_name}: {e}")
            else:
                pass  # Font file not installed yet, OK for local development
    except ImportError:
        pass  # reportlab will be imported in routes, no need to fail here
    except Exception as e:
        print(f"⚠ Error registering fonts: {e}")

# Register fonts on startup
register_fonts()

# ============================================================================
# FLASK APP SETUP
# ============================================================================

def parse_xml_timetable(xml_path):
    """Parse XML timetable file into the PDF extraction format"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        config = {}
        class_teacher_periods = {}  # class_id → list of {teacher_id, periods, subject, type}
        lab_teacher_periods = {}     # class_id → list of {teacher_id, periods, subject, type}
        teacher_list = {}
        
        # Parse config
        config_elem = root.find('config')
        if config_elem is not None:
            config["days"], config["periods"] = _validate_week_config(
                config_elem.findtext("days", 5),
                config_elem.findtext("periods", 6),
            )
        
        # Parse classes and assign teacher IDs
        teacher_id_counter = 0
        teacher_name_to_id = {}
        
        for class_elem in root.findall('classes/class'):
            class_name = class_elem.get('name', 'Unknown')
            class_teacher_periods[class_name] = []
            lab_teacher_periods[class_name] = []
            
            for subject_elem in class_elem.findall('subject'):
                name = subject_elem.findtext('name', 'Unknown')
                teacher_name = subject_elem.findtext('teacher', 'Unknown')
                hours = int(subject_elem.findtext('hours', 1))
                subject_type = subject_elem.findtext('type', 'theory')
                
                # Assign unique teacher ID
                if teacher_name not in teacher_name_to_id:
                    teacher_id_counter += 1
                    teacher_id = teacher_id_counter
                    teacher_name_to_id[teacher_name] = teacher_id
                    teacher_list[str(teacher_id)] = {"Name": teacher_name}
                else:
                    teacher_id = teacher_name_to_id[teacher_name]
                
                # Build subject entry in the expected format
                subject_data = {
                    "teacher_id": teacher_id,
                    "periods": hours,  # for theory, periods = hours
                    "subject": name,
                    "type": subject_type
                }
                
                # For labs, extract the periods_per_block
                if subject_type == "lab":
                    periods_per_block = int(subject_elem.findtext('periods', 2))
                    subject_data["periods"] = [hours, periods_per_block, 1]  # [total_hours, consecutive_periods, lab_number]
                    lab_teacher_periods[class_name].append(subject_data)
                else:
                    class_teacher_periods[class_name].append(subject_data)
        
        return {
            "organized": {k: v for k, v in zip(
                [cls.get('name') for cls in root.findall('classes/class')],
                [[] for _ in root.findall('classes/class')]
            )},
            "class_teacher_periods": class_teacher_periods,
            "lab_teacher_periods": lab_teacher_periods,
            "teacher_list": teacher_list,
            "config": config,
            "source": "xml"
        }
    except Exception as e:
        raise ValueError(f"Error parsing XML: {str(e)}")
    
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath('uploads')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ── Per-user session isolation ───────────────────────────────────────────────
# Previously every stage of the pipeline (uploaded data, generated timetable,
# metadata, etc.) was read/written to fixed filenames in the working directory
# — e.g. open("temp_web_data.json"). That means every visitor shared the exact
# same files: two people using the app at once would silently overwrite each
# other's data, and a server restart wiped everyone's in-progress work. Fixed
# below by giving each browser a private, cookie-identified subdirectory and
# routing all of that file I/O through it via spath(...).
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or uuid.uuid4().hex
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV", "").lower() == "production",
)
if not os.environ.get("FLASK_SECRET_KEY"):
    print("⚠️  FLASK_SECRET_KEY not set — using a random key generated for this run. "
          "Sessions won't survive a server restart. Set FLASK_SECRET_KEY in the "
          "environment for persistent sessions.")

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)


_SID_RE = re.compile(r"^[0-9a-f]{32}$")

def _sid():
    """Get/create a validated UUID-hex session id from the signed Flask session."""
    raw = session.get("sid")
    if not isinstance(raw, str) or not _SID_RE.fullmatch(raw):
        raw = uuid.uuid4().hex
        session["sid"] = raw
        session.permanent = True
    return raw


def spath(filename):
    """Resolve an internal filename to this browser's private session directory."""
    d = os.path.join(SESSIONS_DIR, _sid())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, filename)


def _validate_week_config(days, periods):
    try:
        days, periods = int(days), int(periods)
    except (TypeError, ValueError):
        raise ValueError("Days and periods must be integers.")
    if not (1 <= days <= 7):
        raise ValueError("Working days must be between 1 and 7.")
    if not (1 <= periods <= 24):
        raise ValueError("Periods per day must be between 1 and 24.")
    return days, periods


def _safe_download_stem(value, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
    return (cleaned or fallback)[:100]


def _safe_sheet_title(value, fallback, used):
    base = re.sub(r'[\\/*?:\[\]]+', "_", str(value or "")).strip() or fallback
    base = base[:31]
    candidate = base
    n = 1
    while candidate in used:
        suffix = f" ({n})"
        candidate = f"{base[:31-len(suffix)]}{suffix}"
        n += 1
    used.add(candidate)
    return candidate


def _normalise_subject(value):
    s = str(value or "").strip()
    return re.sub(r"\s*\(lab[^)]*\)", "", s, flags=re.IGNORECASE).lower().strip()


def _resolve_class_index(class_keys, member):
    name = str(member.get("className", "") or "").replace("Class ", "").strip()
    if name and name in class_keys:
        return class_keys.index(name)
    try:
        return int(member.get("classIdx", -1))
    except (TypeError, ValueError):
        return -1


def _teachers_for_cell(cidx, cell_value, stored):
    """Return every teacher responsible for a rendered timetable cell."""
    if cell_value in (None, 0) or str(cell_value).strip().lower() in ("", "0", "free"):
        return set()
    norm = _normalise_subject(cell_value)
    teachers = set()
    organized = stored.get("organized", {}) if isinstance(stored, dict) else {}
    class_keys = list(organized.keys())
    if 0 <= cidx < len(class_keys):
        for row in organized.get(class_keys[cidx], []):
            if _normalise_subject(row.get("subject", "")) == norm:
                name = str(row.get("teacher", "")).strip()
                if name:
                    teachers.add(name)
    bundles = []
    if isinstance(stored, dict):
        bundles.extend(stored.get("auto_bundles", []) or [])
        bundles.extend(stored.get("sync_groups", []) or [])
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        display = bundle.get("display_name") or bundle.get("name") or ""
        if _normalise_subject(display) != norm:
            continue
        for member in bundle.get("members", []) or []:
            if _resolve_class_index(class_keys, member) == cidx:
                name = str(member.get("teacherName", "")).strip()
                if name:
                    teachers.add(name)
    return teachers


def _is_lab_cell(cidx, cell_value, stored):
    text = str(cell_value or "").strip().lower()
    if re.search(r"\(\s*lab\b", text):
        return True
    organized = stored.get("organized", {}) if isinstance(stored, dict) else {}
    class_keys = list(organized.keys())
    if 0 <= cidx < len(class_keys):
        norm = _normalise_subject(cell_value)
        return any(
            _normalise_subject(row.get("subject", "")) == norm
            and str(row.get("type", "theory")).lower().strip() == "lab"
            for row in organized.get(class_keys[cidx], [])
        )
    return False


def _fixed_entry_for_slot(meta, class_idx, slot_idx):
    fixed = meta.get("fixed_slots", {}) if isinstance(meta, dict) else {}
    entries = fixed.get(str(class_idx), {}) if isinstance(fixed, dict) else {}
    periods = int(meta.get("periods", 0) or 0) if isinstance(meta, dict) else 0
    for raw_slot, info in (entries or {}).items():
        try:
            flat = int(raw_slot)
        except (TypeError, ValueError):
            try:
                d, p = map(int, str(raw_slot).split("-", 1))
                flat = d * periods + p
            except Exception:
                continue
        if flat == slot_idx and isinstance(info, dict) and info.get("label") and info.get("teacher_id", "__none__") != "__none__":
            return info
    return None


# ── Clear stale session directories on startup ───────────────────────────────
# No request context exists at startup, so we can't resolve a per-user sid here.
# Instead, sweep away session directories left over from previous runs/older
# than a day, rather than blowing away a single shared set of global files
# (which used to nuke every current user's in-progress work on every restart).
_SESSION_MAX_AGE_SECONDS = 24 * 60 * 60
try:
    now = time.time()
    for _entry in os.listdir(SESSIONS_DIR):
        _entry_path = os.path.join(SESSIONS_DIR, _entry)
        try:
            if os.path.isdir(_entry_path) and (now - os.path.getmtime(_entry_path)) > _SESSION_MAX_AGE_SECONDS:
                import shutil
                shutil.rmtree(_entry_path, ignore_errors=True)
        except Exception:
            pass
except Exception:
    pass

# ── Check for OR-Tools on startup ────────────────────────────────────────────
try:
    from ortools.sat.python import cp_model as _cp_test
    print("✅ OR-Tools available — using CP-SAT solver (fast)")
except ImportError:
    print("⚠️  OR-Tools NOT installed. Falling back to slow backtracking solver.")
    print("   To fix: run  pip install ortools  and restart the app.")
    print("   Without OR-Tools, solving may take 3-5 minutes or fail on large inputs.")


# ============================================================================
# HEALTH CHECK ENDPOINT (NEW - for monitoring)
# ============================================================================

@app.route("/health")
def health():
    """
    Health check endpoint — returns 200 if app is running and responsive.
    Used by Render to verify deployment and auto-restart if needed.
    """
    try:
        return jsonify({"status": "ok", "service": "timetable-generator"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/")
def home():
    return render_template("upload.html")

@app.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return "No file selected", 400

    pdf_path = spath(f"upload_{uuid.uuid4().hex}.pdf")
    try:
        header = file.stream.read(1024)
        file.stream.seek(0)
        if b"%PDF-" not in header:
            return "The uploaded file is not a valid PDF.", 400
        file.save(pdf_path)
        raw_data = get_solver_data_from_pdf(pdf_path)
        if not isinstance(raw_data, dict) or not (
            raw_data.get("class_teacher_periods") or raw_data.get("lab_teacher_periods")
        ):
            return "AI extraction returned no timetable data.", 422
        with open(spath("last_extraction.json"), "w") as f:
            json.dump(raw_data, f)

        return redirect(url_for("generate"))
        
    except Exception as e:
        print(traceback.format_exc())
        return f"AI Extraction Failed: {escape(str(e))}", 500
    finally:
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        except OSError:
            pass

@app.route("/upload-xml", methods=["POST"])
def upload_xml():
    """Upload and parse XML timetable file"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
    
    if not file.filename.endswith('.xml'):
        return jsonify({"status": "error", "message": "File must be XML"}), 400
    
    try:
        xml_path = spath(f"upload_{uuid.uuid4().hex}.xml")
        file.save(xml_path)
        data = parse_xml_timetable(xml_path)
        
        # Save as temp_web_data for /generate to use
        with open(spath("last_extraction.json"), "w") as f:
            json.dump(data, f)
        
        return jsonify({
            "status": "success",
            "message": "XML uploaded and parsed successfully",
            "redirect": url_for("generate")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        try:
            if os.path.exists(xml_path):
                os.remove(xml_path)
        except OSError:
            pass

    
@app.route("/generate")
def generate():
    # NOTE: this used to check a module-level CONFIG["raw_extraction"] dict
    # first. That dict is shared by every request in the process, so once ANY
    # user uploaded a PDF, every OTHER user hitting /generate would silently
    # receive that same cached extraction instead of their own — a serious
    # cross-user data leak on top of the file-sharing issue. Read straight
    # from this session's own file instead.
    data = None
    if os.path.exists(spath("last_extraction.json")):
        with open(spath("last_extraction.json"), "r") as f:
            data = json.load(f)
    
    if not data:
        return "<h3>No data found. Please upload a PDF first.</h3>"

    try:
        display_data = []
        teacher_map = data.get('teacher_list', {})

        # 1. Process Theory (Now a LIST, not a DICT)
        for class_id, teachers_list in data.get('class_teacher_periods', {}).items():
            # FIX: Loop through the list directly instead of using .items()
            for item in teachers_list:
                t_id = str(item.get('teacher_id'))
                subj = item.get('subject', 'Theory')
                p_val = item.get('periods', 0)

                display_data.append({
                    "class": f"Class {class_id}",
                    "subject": subj,
                    "teacher": (
    teacher_map.get(t_id, {}).get("Name")
    or teacher_map.get(t_id, {}).get("name")
    or f"S{t_id}"
),
                    "type": "Theory",
                    "periods": p_val,
                    "split_children_json": "[]"
                })

        # 2. Process Labs (Now a LIST, not a DICT)
        for class_id, labs_list in data.get('lab_teacher_periods', {}).items():
            # FIX: Loop through the list directly instead of using .items()
            for item in labs_list:
                t_id = str(item.get('teacher_id'))
                subj = item.get('subject', 'Lab')
                p_raw = item.get('periods', [0])
                p_count = p_raw[0] if isinstance(p_raw, list) else p_raw

                display_data.append({
                    "class": f"Class {class_id}",
                    "subject": subj,
                    "teacher": teacher_map.get(t_id, {}).get('Name', f"S{t_id}"),
                    "type": "Lab",
                    "periods": p_count,
                    "split_children_json": "[]"
                })

        # Extract days/periods from the PDF data if the extractor provided them
        extracted_days    = int(data.get('days', 6))
        extracted_periods = int(data.get('periods', 6))

        return render_template("view_simple.html", rows=display_data,
                               extracted_days=extracted_days,
                               extracted_periods=extracted_periods,
                               merge_groups_json="[]")

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"<h3>Data Processing Error: {str(e)}</h3>"


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER — resolve one cell value from the timetable
#  Timetable structure: timetable[slot_index][class_idx]
#  where slot_index = day * periods_per_day + period
# ─────────────────────────────────────────────────────────────────────────────
def _cell_text(timetable, class_idx, day, period, periods_per_day):
    slot_index = day * periods_per_day + period
    try:
        slot_row = timetable[slot_index]
        # slot_row is either a list [cls0_val, cls1_val, ...] or a dict
        if isinstance(slot_row, list):
            raw = slot_row[class_idx]
        elif isinstance(slot_row, dict):
            raw = slot_row.get(str(class_idx), slot_row.get(class_idx, ""))
        else:
            raw = slot_row
    except (IndexError, KeyError, TypeError):
        return "", "normal"

    if raw is None or raw == 0 or raw == "0":
        return "", "normal"

    text = str(raw).strip()
    lower = text.lower()

    if lower == "free":
        return "Free", "free"
    if "lab" in lower:
        return text, "lab"
    return text, "normal"


# ─────────────────────────────────────────────────────────────────────────────
#  EXCEL DOWNLOAD (FIXED for Render)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/download/excel")
def download_excel():
    """
    Generate and download timetable as Excel file.
    FIXED: Added error handling and logging for Render debugging.
    """
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        if not os.path.exists(spath("generated_timetable.json")) or \
           not os.path.exists(spath("generated_metadata.json")) or \
           not os.path.exists(spath("last_extraction.json")):
            return "No timetable found. Please generate one first.", 404

        with open(spath("generated_timetable.json"))  as f: timetable   = json.load(f)
        with open(spath("generated_metadata.json"))   as f: meta        = json.load(f)
        with open(spath("last_extraction.json"))        as f: stored      = json.load(f)

        days        = meta["days"]
        periods     = meta["periods"]
        num_classes = meta["num_classes"]

        organized_keys = list(stored.get("organized", {}).keys())
        all_class_names = [organized_keys[i] if i < len(organized_keys) else str(i+1) for i in range(num_classes)]

        # Support single-class export via ?class_idx=N
        single_idx = request.args.get("class_idx", None)
        if single_idx is not None:
            try:
                single_idx = int(single_idx)
                # Python allows negative indices (all_class_names[-1] silently
                # returns the LAST class instead of raising IndexError), so a
                # request like ?class_idx=-1 used to bypass the "export all
                # classes" fallback below and return the wrong class instead.
                if single_idx < 0:
                    raise IndexError("class_idx must be non-negative")
                class_names = [all_class_names[single_idx]]
                class_indices = [single_idx]
            except (ValueError, IndexError):
                class_names = all_class_names
                class_indices = list(range(num_classes))
        else:
            class_names   = all_class_names
            class_indices = list(range(num_classes))

        # Day labels: Mon–Sat for 6, Mon–Fri for 5, etc.
        _day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_labels = [_day_names[i] if i < len(_day_names) else f"Day {i+1}" for i in range(days)]

        # ── Style factories (new object per cell avoids openpyxl shared-style bugs) ─
        def hdr_fill():  return PatternFill("solid", fgColor="1F3864")
        def hdr_font():  return Font(color="FFFFFF", bold=True, size=11)
        def per_fill():  return PatternFill("solid", fgColor="D9E1F2")
        def per_font():  return Font(bold=True, size=10)
        def free_fill(): return PatternFill("solid", fgColor="FFF9C4")
        def lab_fill():  return PatternFill("solid", fgColor="E7F5FF")
        def norm_fill(): return PatternFill("solid", fgColor="FFFFFF")
        def mk_border(): return Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"),  bottom=Side(style="thin"))
        def mk_center(): return Alignment(horizontal="center", vertical="center", wrap_text=True)

        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        used_sheet_titles = set()

        for cls_idx, cls_name in zip(class_indices, class_names):
            ws = wb.create_sheet(title=_safe_sheet_title(f"Class {cls_name}", "Class", used_sheet_titles))

            # Header row: Day | P1 | P2 | P3 | ...
            ws.row_dimensions[1].height = 26
            ws.column_dimensions["A"].width = 14

            for col, label in enumerate(["Day"] + [f"P{p+1}" for p in range(periods)]):
                c = ws.cell(row=1, column=col+1, value=label)
                c.fill      = hdr_fill()
                c.font      = hdr_font()
                c.alignment = mk_center()
                c.border    = mk_border()

            for p in range(periods):
                ws.column_dimensions[get_column_letter(p + 2)].width = 24

            # Data rows — one row per day
            for d in range(days):
                row_num = d + 2
                ws.row_dimensions[row_num].height = 42

                # Day label cell
                dc = ws.cell(row=row_num, column=1, value=day_labels[d])
                dc.fill      = per_fill()
                dc.font      = per_font()
                dc.alignment = mk_center()
                dc.border    = mk_border()

                for p in range(periods):
                    text, kind = _cell_text(timetable, cls_idx, d, p, periods)

                    fill = {"free": free_fill(), "lab": lab_fill()}.get(kind, norm_fill())

                    pc = ws.cell(row=row_num, column=p+2, value=text)
                    pc.fill      = fill
                    pc.alignment = mk_center()
                    pc.border    = mk_border()
                    pc.font      = Font(size=9, bold=(kind == "lab"),
                                        italic=(kind == "free"),
                                        color="6C757D" if kind == "free" else "000000")

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)  # CRITICAL: Must seek to beginning before sending
        
        fname = f"timetable_class_{class_names[0]}.xlsx" if len(class_names) == 1 else "timetable.xlsx"
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=_safe_download_stem(fname, "timetable.xlsx")
        )
    
    except Exception as e:
        # Log the full error for Render debugging
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"EXCEL DOWNLOAD ERROR: {error_msg}")
        print(f"TRACEBACK:\n{error_trace}")
        return jsonify({
            "status": "error",
            "message": f"Excel generation failed: {error_msg}"
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
#  PDF DOWNLOAD (FIXED for Render)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/download/pdf")
def download_pdf():
    """
    Generate and download timetable as PDF file.
    FIXED: Better error handling, uses safe fonts, explicit font registration.
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        if not os.path.exists(spath("generated_timetable.json")) or \
           not os.path.exists(spath("generated_metadata.json")) or \
           not os.path.exists(spath("last_extraction.json")):
            return "No timetable found. Please generate one first.", 404

        with open(spath("generated_timetable.json"))  as f: timetable   = json.load(f)
        with open(spath("generated_metadata.json"))   as f: meta        = json.load(f)
        with open(spath("last_extraction.json"))        as f: stored      = json.load(f)

        days        = meta["days"]
        periods     = meta["periods"]
        num_classes = meta["num_classes"]

        organized_keys = list(stored.get("organized", {}).keys())
        class_names = []
        for i in range(num_classes):
            class_names.append(organized_keys[i] if i < len(organized_keys) else str(i + 1))

        # Day labels: Mon–Sat for 6, Mon–Fri for 5, etc.
        _day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_labels = [_day_names[i] if i < len(_day_names) else f"Day {i+1}" for i in range(days)]

        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            leftMargin=1.5*cm, rightMargin=1.5*cm,
            topMargin=1.5*cm,  bottomMargin=1.5*cm
        )

        styles  = getSampleStyleSheet()
        title_s = ParagraphStyle("ttl", parent=styles["Heading2"],
                                 alignment=TA_CENTER, spaceAfter=6)
        cell_s  = ParagraphStyle("cel", parent=styles["Normal"],
                                 fontSize=7, leading=9, alignment=TA_CENTER)
        free_s  = ParagraphStyle("fre", parent=styles["Normal"],
                                 fontSize=7, leading=9, alignment=TA_CENTER,
                                 textColor=colors.HexColor("#6C757D"))

        NAVY  = colors.HexColor("#1F3864")
        LBLUE = colors.HexColor("#D9E1F2")
        YFREE = colors.HexColor("#FFF9C4")
        BLAB  = colors.HexColor("#E7F5FF")
        WHITE = colors.white


        # Support single-class export via ?class_idx=N
        single_idx = request.args.get("class_idx", None)
        if single_idx is not None:
            try:
                single_idx = int(single_idx)
                # Negative indices (e.g. class_idx=-1) previously slipped through
                # here silently — Python indexing wraps around instead of raising,
                # so the "export all classes" fallback below never triggered and
                # the wrong (last) class was returned instead. Also, an
                # out-of-range *positive* index used to leave class_names (full
                # fallback list) and class_indices ([single_idx], one bad index)
                # mismatched in length instead of both falling back together.
                if single_idx < 0 or single_idx >= len(class_names):
                    raise IndexError("class_idx out of range")
                class_indices = [single_idx]
                class_names   = [class_names[single_idx]]
            except (ValueError, IndexError):
                class_names   = [organized_keys[i] if i < len(organized_keys) else str(i+1) for i in range(num_classes)]
                class_indices = list(range(num_classes))
        else:
            class_indices = list(range(num_classes))

        story = []
        for cls_idx, cls_name in zip(class_indices, class_names):
            story.append(Paragraph(escape(f"Class {cls_name} — Timetable"), title_s))

            # Build table rows: header + one row per day
            header = ["Day"] + [f"P{p+1}" for p in range(periods)]
            rows   = [header]

            # Track which (row, col) cells need colour overrides
            free_cells = []
            lab_cells  = []

            for d in range(days):
                row = [Paragraph(escape(day_labels[d]), cell_s)]
                for p in range(periods):
                    text, kind = _cell_text(timetable, cls_idx, d, p, periods)
                    style = free_s if kind == "free" else cell_s
                    row.append(Paragraph(escape(text), style))
                    if kind == "free":
                        free_cells.append((p+1, d+1))   # col, row
                    elif kind == "lab":
                        lab_cells.append((p+1, d+1))
                rows.append(row)

            col_w = (27 * cm) / (periods + 1)
            t = Table(rows, colWidths=[col_w] * (periods + 1), repeatRows=1)

            ts = TableStyle([
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0),  NAVY),
                ("TEXTCOLOR",  (0, 0), (-1, 0),  WHITE),
                # FIXED: Use safe font name that exists in all environments
                ("FONTNAME",   (0, 0), (-1, 0),  "Helvetica"),
                ("FONTSIZE",   (0, 0), (-1, 0),  9),
                # Day column
                ("BACKGROUND", (0, 1), (0, -1),  LBLUE),
                ("FONTNAME",   (0, 1), (0, -1),  "Helvetica"),
                # All cells
                ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
                ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE",   (1, 1), (-1, -1), 8),
                ("ROWHEIGHT",  (0, 1), (-1, -1), 28),
                ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ])

            # Apply per-cell colour overrides
            for (col_i, row_i) in free_cells:
                ts.add("BACKGROUND", (col_i, row_i), (col_i, row_i), YFREE)
            for (col_i, row_i) in lab_cells:
                ts.add("BACKGROUND", (col_i, row_i), (col_i, row_i), BLAB)

            t.setStyle(ts)
            story.append(t)
            story.append(Spacer(1, 0.8 * cm))

        doc.build(story)
        output.seek(0)  # CRITICAL: Must seek to beginning before sending
        
        fname = f"timetable_class_{class_names[0]}.pdf" if len(class_names) == 1 else "timetable.pdf"
        return send_file(
            output,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=fname
        )
    
    except Exception as e:
        # Log the full error for Render debugging
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"PDF DOWNLOAD ERROR: {error_msg}")
        print(f"TRACEBACK:\n{error_trace}")
        return jsonify({
            "status": "error",
            "message": f"PDF generation failed: {error_msg}"
        }), 500



# ─────────────────────────────────────────────────────────────────────────────
#  TEACHER TIMETABLE HELPER
# ─────────────────────────────────────────────────────────────────────────────
def _build_teacher_timetable(teacher_name, timetable, stored, days, periods, num_classes):
    """Return a days×periods grid for one teacher."""
    organized = stored.get("organized", {})
    class_keys = list(organized.keys())
    grid = [["" for _ in range(periods)] for _ in range(days)]
    for day in range(days):
        for p in range(periods):
            si = day * periods + p
            for cidx in range(num_classes):
                try:
                    cell = timetable[si][cidx]
                except (IndexError, KeyError, TypeError):
                    continue
                if not cell or str(cell).strip().lower() in ("", "free", "0"):
                    continue
                if teacher_name in _teachers_for_cell(cidx, cell, stored):
                    cname_label = class_keys[cidx] if cidx < len(class_keys) else str(cidx)
                    grid[day][p] = f"{cell}\n({cname_label})"
    return grid


@app.route("/download/teacher-pdf")
def download_teacher_pdf():
    """Download one teacher's timetable as PDF. ?teacher=<name>"""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        teacher_name = request.args.get("teacher", "").strip()
        if not teacher_name:
            return "No teacher specified (?teacher=Name)", 400

        for fn in ("generated_timetable.json", "generated_metadata.json", "last_extraction.json"):
            if not os.path.exists(spath(fn)):
                return "No timetable found. Please generate one first.", 404

        with open(spath("generated_timetable.json")) as f: timetable = json.load(f)
        with open(spath("generated_metadata.json"))  as f: meta      = json.load(f)
        with open(spath("last_extraction.json"))      as f: stored    = json.load(f)

        days = meta["days"]; periods = meta["periods"]; num_classes = meta["num_classes"]
        _day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        day_labels = [_day_names[i] if i < len(_day_names) else f"Day {i+1}" for i in range(days)]
        grid = _build_teacher_timetable(teacher_name, timetable, stored, days, periods, num_classes)

        styles  = getSampleStyleSheet()
        title_s = ParagraphStyle("ttl", parent=styles["Heading2"], alignment=TA_CENTER, spaceAfter=6)
        cell_s  = ParagraphStyle("cel", parent=styles["Normal"], fontSize=7, leading=9, alignment=TA_CENTER)
        free_s  = ParagraphStyle("fre", parent=styles["Normal"], fontSize=7, leading=9, alignment=TA_CENTER,
                                 textColor=colors.HexColor("#6C757D"))

        NAVY  = colors.HexColor("#1F3864"); LBLUE = colors.HexColor("#D9E1F2")
        YFREE = colors.HexColor("#FFF9C4"); WHITE = colors.white

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=landscape(A4),
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm,  bottomMargin=1.5*cm)
        story = [Paragraph(escape(f"Teacher Timetable — {teacher_name}"), title_s)]
        header = ["Day"] + [f"P{p+1}" for p in range(periods)]
        rows   = [header]
        free_cells = []
        for d in range(days):
            row = [Paragraph(day_labels[d], cell_s)]
            for p in range(periods):
                text = grid[d][p]
                if text:
                    row.append(Paragraph(escape(text).replace("\n", "<br/>"), cell_s))
                else:
                    row.append(Paragraph("Free", free_s))
                    free_cells.append((p + 1, d + 1))
            rows.append(row)

        col_w = (27 * cm) / (periods + 1)
        t = Table(rows, colWidths=[col_w] * (periods + 1), repeatRows=1)
        ts = TableStyle([
            ("BACKGROUND", (0,0),(-1,0), NAVY), ("TEXTCOLOR",(0,0),(-1,0), WHITE),
            ("FONTNAME",   (0,0),(-1,0), "Helvetica"), ("FONTSIZE",(0,0),(-1,0), 9),
            ("BACKGROUND", (0,1),(0,-1), LBLUE), ("FONTNAME",(0,1),(0,-1), "Helvetica"),
            ("ALIGN",  (0,0),(-1,-1),"CENTER"), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("FONTSIZE",(1,1),(-1,-1),8), ("ROWHEIGHT",(0,1),(-1,-1),36),
            ("GRID",(0,0),(-1,-1),0.5,colors.grey),
        ])
        for (col_i, row_i) in free_cells:
            ts.add("BACKGROUND",(col_i,row_i),(col_i,row_i), YFREE)
        t.setStyle(ts)
        story.append(t); story.append(Spacer(1, 0.8*cm))
        doc.build(story); output.seek(0)
        safe = re.sub(r"[^\w\-]", "_", teacher_name)
        return send_file(output, mimetype="application/pdf", as_attachment=True,
                         download_name=f"timetable_teacher_{_safe_download_stem(safe, 'teacher')}.pdf")
    except Exception as e:
        print(f"TEACHER PDF ERROR: {traceback.format_exc()}")
        return jsonify({"status":"error","message":str(e)}), 500


@app.route("/download/teacher-excel")
def download_teacher_excel():
    """Download one teacher's timetable as Excel. ?teacher=<name>"""
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

        teacher_name = request.args.get("teacher", "").strip()
        if not teacher_name:
            return "No teacher specified (?teacher=Name)", 400

        for fn in ("generated_timetable.json", "generated_metadata.json", "last_extraction.json"):
            if not os.path.exists(spath(fn)):
                return "No timetable found. Please generate one first.", 404

        with open(spath("generated_timetable.json")) as f: timetable = json.load(f)
        with open(spath("generated_metadata.json"))  as f: meta      = json.load(f)
        with open(spath("last_extraction.json"))      as f: stored    = json.load(f)

        days = meta["days"]; periods = meta["periods"]; num_classes = meta["num_classes"]
        _day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        day_labels = [_day_names[i] if i < len(_day_names) else f"Day {i+1}" for i in range(days)]
        grid = _build_teacher_timetable(teacher_name, timetable, stored, days, periods, num_classes)

        def hdr_fill():  return PatternFill("solid", fgColor="1F3864")
        def hdr_font():  return Font(color="FFFFFF", bold=True, size=11)
        def per_fill():  return PatternFill("solid", fgColor="D9E1F2")
        def per_font():  return Font(bold=True, size=10)
        def free_fill(): return PatternFill("solid", fgColor="FFF9C4")
        def busy_fill(): return PatternFill("solid", fgColor="E8F5E9")
        def mk_border(): return Border(left=Side(style="thin"), right=Side(style="thin"),
                                       top=Side(style="thin"),  bottom=Side(style="thin"))
        def mk_center(): return Alignment(horizontal="center", vertical="center", wrap_text=True)

        wb = openpyxl.Workbook(); ws = wb.active; ws.title = _safe_sheet_title(teacher_name, "Teacher", set())
        ws.row_dimensions[1].height = 26; ws.column_dimensions["A"].width = 14
        from openpyxl.utils import get_column_letter
        for p in range(periods):
            ws.column_dimensions[get_column_letter(p + 2)].width = 26

        for col, label in enumerate(["Day"] + [f"P{p+1}" for p in range(periods)]):
            c = ws.cell(row=1, column=col+1, value=label)
            c.fill = hdr_fill(); c.font = hdr_font(); c.alignment = mk_center(); c.border = mk_border()

        for d in range(days):
            rn = d + 2; ws.row_dimensions[rn].height = 48
            dc = ws.cell(row=rn, column=1, value=day_labels[d])
            dc.fill = per_fill(); dc.font = per_font(); dc.alignment = mk_center(); dc.border = mk_border()
            for p in range(periods):
                text = grid[d][p]
                pc = ws.cell(row=rn, column=p+2, value=text if text else "Free")
                pc.fill = busy_fill() if text else free_fill()
                pc.alignment = mk_center(); pc.border = mk_border()
                pc.font = Font(size=9, italic=(not text), color="6C757D" if not text else "000000")

        output = io.BytesIO(); wb.save(output); output.seek(0)
        safe = re.sub(r"[^\w\-]", "_", teacher_name)
        return send_file(output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True, download_name=f"timetable_teacher_{_safe_download_stem(safe, 'teacher')}.xlsx")
    except Exception as e:
        print(f"TEACHER EXCEL ERROR: {traceback.format_exc()}")
        return jsonify({"status":"error","message":str(e)}), 500


@app.route("/api/teacher-cell-map")
def teacher_cell_map():
    """Return {'cidx-slotIdx': 'TeacherName'} for every non-free cell."""
    try:
        for fn in ("generated_timetable.json", "generated_metadata.json", "last_extraction.json"):
            if not os.path.exists(spath(fn)):
                return jsonify({}), 200

        with open(spath("generated_timetable.json")) as f: timetable = json.load(f)
        with open(spath("generated_metadata.json"))  as f: meta      = json.load(f)
        with open(spath("last_extraction.json"))      as f: stored    = json.load(f)

        days = meta["days"]; periods = meta["periods"]; num_classes = meta["num_classes"]
        organized  = stored.get("organized", {})
        class_keys = list(organized.keys())

        subj_teacher = {}
        for cidx, cname in enumerate(class_keys):
            for t in organized[cname]:
                key = (cidx, t["subject"].lower().strip())
                subj_teacher[key] = t["teacher"]
                stripped = re.sub(r"\s*\(lab[^)]*\)", "", t["subject"], flags=re.IGNORECASE).lower().strip()
                if stripped != t["subject"].lower().strip():
                    subj_teacher[(cidx, stripped)] = t["teacher"]

        cell_map = {}
        for day in range(days):
            for p in range(periods):
                si = day * periods + p
                for cidx in range(num_classes):
                    try: cell = timetable[si][cidx]
                    except (IndexError, KeyError, TypeError): continue
                    if not cell or cell == 0 or str(cell).strip().lower() in ("","free","0"): continue
                    cell_str  = str(cell).strip()
                    cell_norm = re.sub(r"\s*\(lab[^)]*\)", "", cell_str, flags=re.IGNORECASE).lower().strip()
                    teachers = _teachers_for_cell(cidx, cell, stored)
                    if teachers:
                        cell_map[f"{cidx}-{si}"] = ", ".join(sorted(teachers))
        return jsonify(cell_map)
    except Exception as e:
        print(f"TEACHER CELL MAP ERROR: {traceback.format_exc()}")
        return jsonify({}), 500


# CLEANED: Only one version of success_summary using dynamic metadata
@app.route("/success-summary")
def success_summary():
    if not all(os.path.exists(spath(fn)) for fn in ("generated_timetable.json", "generated_metadata.json", "last_extraction.json")):
        return redirect(url_for("home"))

    with open(spath("generated_timetable.json"), "r") as f:
        timetable = json.load(f)
    with open(spath("generated_metadata.json"), "r") as f:
        meta = json.load(f)
    with open(spath("last_extraction.json"), "r") as f:
        stored = json.load(f)

    days = int(meta.get("days", 6))
    periods = int(meta.get("periods", 6))
    num_classes = int(meta.get("num_classes", 0))
    organized = stored.get("organized", {})
    class_names = list(organized.keys())

    # ── Build teacher_slot_map: {teacher_name: ["classIdx-slotIdx", ...]} ──────
    # We need to know which teacher teaches each subject in each class
    organized = stored.get("organized", {})
    teacher_slot_map = {}   # teacher_name -> [classIdx-slotIdx]
    teacher_names_set = set()
    for cidx in range(num_classes):
        for day in range(days):
            for p in range(periods):
                si = day * periods + p
                try:
                    cell = timetable[si][cidx]
                except (IndexError, KeyError):
                    continue
                if not cell or cell == 0 or str(cell).lower() in ('free', 'f', '0'):
                    continue
                for teacher in _teachers_for_cell(cidx, cell, stored):
                    teacher_names_set.add(teacher)
                    teacher_slot_map.setdefault(teacher, []).append(f"{cidx}-{si}")

    teacher_names = sorted(teacher_names_set)

    # ── Build sync-group exempt set ───────────────────────────────────────────
    # Sync groups intentionally place the same teacher in multiple classes at
    # the same slot. Build (tname, slot_idx) pairs to skip in conflict detection.
    _ck = list(stored.get("organized", {}).keys())
    _bundles = []
    for _raw in (stored.get("auto_bundles", []) or []) + (stored.get("sync_groups", []) or []):
        if not isinstance(_raw, dict):
            continue
        _members = []
        for _m in _raw.get("members", []) or []:
            _mf = dict(_m)
            _mf["classIdx"] = _resolve_class_index(_ck, _m)
            _members.append(_mf)
        _b = dict(_raw); _b["members"] = _members
        _bundles.append(_b)

    sync_groups_stored = []
    _seen_bundle_keys = set()
    for _b in _bundles:
        _key = (
            str(_b.get("name", "")),
            tuple(sorted((int(m.get("classIdx", -1)), str(m.get("teacherName", "")), str(m.get("subject", "")))
                         for m in _b.get("members", [])))
        )
        if _key not in _seen_bundle_keys:
            _seen_bundle_keys.add(_key)
            sync_groups_stored.append(_b)

    sync_allowed = {}
    for _sg in sync_groups_stored:
        for _m in _sg.get("members", []):
            _t = str(_m.get("teacherName", "")).strip()
            _c = int(_m.get("classIdx", -1))
            if not _t or _c < 0:
                continue
            for _slot_ref in teacher_slot_map.get(_t, []):
                _ci, _si = _slot_ref.split("-", 1)
                if int(_ci) == _c:
                    sync_allowed.setdefault((_t, int(_si)), set()).add(_c)


    # ── Conflict checker: same teacher in 2 DIFFERENT classes at same slot ────
    # Use a SET of class indices so duplicate entries for the same class
    # (e.g. primary teacher + sub-teacher both added for class 0) don't falsely trigger.
    conflicts = []
    slot_teacher_classes = {}  # (tname, si) -> set of DISTINCT class_idxs
    for tname, slots in teacher_slot_map.items():
        for s in slots:
            cidx_str, si_str = s.split('-')
            key = (tname, int(si_str))
            slot_teacher_classes.setdefault(key, set()).add(int(cidx_str))
    for (tname, si), cidxs in slot_teacher_classes.items():
        if len(cidxs) > 1:  # only a real conflict if teacher in 2+ DIFFERENT classes
            # Exempt only when every class using this teacher at this slot is
            # explicitly covered by the same sync bundle.
            if cidxs == sync_allowed.get((tname, si), set()):
                continue
            for cidx in cidxs:
                conflicts.append([cidx, si])

    # teacher_map: {teacher_name: teacher_id} for JS
    teacher_map_js = {t['teacher']: t['teacher_id']
                      for cname in organized for t in organized[cname]}

    # ── Build sync_group_label_map for the template ─────────────────────────
    # Maps (cidx, subject_lower) -> bundle_name so the timetable can display
    # e.g. "2nd Language" instead of just "eng2" or "sans"
    sync_group_label_map = {}  # (cidx, subj_lower) -> bundle_display_name
    # Use display_name (e.g. "Language") not internal name ("Language|MPC11") for timetable labels
    for sg in sync_groups_stored:  # already includes auto_bundles from above
        bname = sg.get('display_name', sg.get('name', ''))  # use display_name for timetable cells
        for m in sg.get('members', []):
            cidx_m = int(m.get('classIdx', -1))
            subj_m = (m.get('subject') or '').lower().strip()
            if cidx_m >= 0 and subj_m:
                sync_group_label_map[(cidx_m, subj_m)] = bname

    return render_template("success.html",
                           timetable=timetable,
                           num_classes=num_classes,
                           class_names=class_names,
                           num_days=days,
                           periods_per_day=periods,
                           teacher_names=teacher_names,
                           teacher_slot_map=teacher_slot_map,
                           teacher_map=teacher_map_js,
                           conflicts=conflicts,
                           sync_group_label_map={str(k): v for k, v in sync_group_label_map.items()})


# --- KEEP THIS VERSION (REPLACES THE TWO OLD ONES) ---
@app.route("/update-data", methods=["POST"])
def update_data():
    try:
        incoming_payload = request.get_json(silent=True)
        if not isinstance(incoming_payload, dict):
            return jsonify({"status": "error", "message": "Invalid JSON payload."}), 400
        web_data = incoming_payload.get("table_data", [])
        config = incoming_payload.get("config", {})
        split_groups = incoming_payload.get("split_groups", [])
        if not isinstance(web_data, list) or not isinstance(config, dict) or not isinstance(split_groups, list):
            return jsonify({"status": "error", "message": "Malformed timetable data."}), 400
        if len(web_data) > 1000:
            return jsonify({"status": "error", "message": "Too many timetable rows."}), 413
        try:
            days_cfg, periods_cfg = _validate_week_config(config.get("days", 6), config.get("periods", 6))
            labs_cfg = int(config.get("labs", 2))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Invalid school configuration."}), 400
        if not (1 <= labs_cfg <= 50):
            return jsonify({"status": "error", "message": "Labs must be between 1 and 50."}), 400

        # Map teacher names to stable numeric IDs. This used to just be
        # `{name: i for i, name in enumerate(sorted(all_teachers))}` recomputed
        # from scratch on every call — meaning if the user went back and edited
        # the table (e.g. added a teacher whose name sorts earlier
        # alphabetically), everyone else's ID could silently shift, and any
        # teacher_id already baked into a saved fixed slot or sync group from
        # an earlier /update-data call would now point at the wrong teacher.
        # Persist the mapping per session and only ever append new names.
        all_teachers = sorted({
            str(row.get("teacher", "")).strip()
            for row in web_data
            if str(row.get("teacher", "")).strip()
        })
        teacher_map_path = spath("teacher_id_map.json")
        t_name_to_id = {}
        if os.path.exists(teacher_map_path):
            try:
                with open(teacher_map_path, "r") as f:
                    t_name_to_id = json.load(f)
            except Exception:
                t_name_to_id = {}
        next_id = (max(t_name_to_id.values()) + 1) if t_name_to_id else 0
        for name in all_teachers:
            if name not in t_name_to_id:
                t_name_to_id[name] = next_id
                next_id += 1
        with open(teacher_map_path, "w") as f:
            json.dump(t_name_to_id, f)

        # Build set of all (className, blockName) pairs that are split groups
        # so we can collapse sub-options into one block row per class
        split_block_seen = set()  # (className, blockName) already added as block row

        organized_classes = {}
        for row in web_data:
            c_name = str(row.get("class", "")).replace("Class ", "").strip()
            if not c_name or len(c_name) > 120:
                raise ValueError("Every row must have a valid class name (1–120 characters).")
            if c_name not in organized_classes:
                organized_classes[c_name] = []

            split_block = str(row.get("split_block", "") or "").strip()
            subject_text = str(row.get("subject", "") or "").strip()
            teacher_text = str(row.get("teacher", "") or "").strip()
            if len(subject_text) > 160 or len(teacher_text) > 160:
                raise ValueError("Subject and teacher names must be 160 characters or fewer.")

            if split_block:
                # This row is a sub-option of a split block.
                # For single-class splits: only add the BLOCK ITSELF once
                # (as a placeholder with the block name and correct hours).
                # Multiple sub-options in the same class all share those hours,
                # so we must not add them as separate subjects (would double/triple hours).
                # The sub-teacher info is carried in the auto_bundle for busy-marking.
                key = (c_name, split_block)
                if key not in split_block_seen:
                    split_block_seen.add(key)
                    # Use the first sub-option's teacher as the "primary" teacher
                    # for the block row — the bundle will mark all sub-teachers busy.
                    organized_classes[c_name].append({
                        "teacher":     teacher_text,
                        "teacher_id":  t_name_to_id.get(row.get('teacher'), 99),
                        "subject":     split_block,   # block name IS the subject in timetable
                        "hours":       int(row.get('periods', 0)),
                        "type":        "theory",
                        "continuous":  1,
                        "lab_no":      0,
                        "split_block": split_block,
                        "is_split_block": True,
                    })
                # Always skip adding the individual sub-option as its own subject row
                # — it would add extra hours to the class workload
                continue

            if not subject_text or not teacher_text:
                raise ValueError(f"Class {c_name}: subject and teacher are required.")
            row_type = str(row.get("type", "theory")).lower().strip()
            if row_type not in ("theory", "lab"):
                raise ValueError(f"Class {c_name}: invalid subject type.")
            hours_value = int(row.get("periods", 0))
            if hours_value < 1:
                raise ValueError(f"Class {c_name}: hours must be at least 1.")
            continuous_value = int(row.get("continuous", 1))
            lab_no_value = int(row.get("lab_no", 0))
            if row_type == "lab":
                if continuous_value < 1 or continuous_value > periods_cfg:
                    raise ValueError(f"Class {c_name}: lab block length is invalid.")
                if hours_value % continuous_value:
                    raise ValueError(f"Class {c_name}: lab total hours must be divisible by block length.")
                if not (1 <= lab_no_value <= labs_cfg):
                    raise ValueError(f"Class {c_name}: lab room must be between 1 and {labs_cfg}.")
            else:
                continuous_value, lab_no_value = 1, 0

            organized_classes[c_name].append({
                "teacher": teacher_text,
                "teacher_id": t_name_to_id.get(teacher_text, 99),
                "subject": subject_text,
                "hours": hours_value,
                "type": row_type,
                "continuous": continuous_value,
                "lab_no": lab_no_value,
                "split_block": '',
            })

        # ── Auto-build elective_bundles from split_groups ─────────────────────
        # split_groups format: [{blockName, className, hours, children:[{name,teacher}]}]
        #
        # KEY RULE: ONE bundle per CLASS per blockName.
        # Cross-class grouping (forcing Language to same time slot across MPC11/BiPC11/CAE11)
        # must be set up EXPLICITLY by the user on the next page (fixed_setup merge groups).
        # We never auto-merge across classes just because they share the same block name —
        # e.g. "Language" in Class 11 and "Language" in Class 12 are separate subjects
        # taught by different teachers at different levels.
        class_keys = list(organized_classes.keys())
        auto_bundles = []
        for sg in split_groups:
            block_name = sg['blockName']
            hours      = sg['hours']
            cname      = sg['className'].replace('Class ', '').strip()
            try:
                cidx = class_keys.index(cname)
            except ValueError:
                continue
            children = sg.get('children', [])
            if not children:
                continue
            members = []
            for child in children:
                if not child.get('name') or not child.get('teacher'):
                    continue
                members.append({
                    'classIdx':    cidx,
                    'className':   cname,
                    'subject':     block_name,   # block name in subject_map
                    'sub_subject': child['name'],
                    'teacherName': child['teacher'],
                    'teacherId':   str(t_name_to_id.get(child['teacher'], 99)),
                    'hours':       hours
                })
            if len(members) >= 2:
                # Bundle name is "BlockName|ClassName" to keep each class separate.
                # The solver only forces the same K slots within this single class
                # (single-class split path: sub-teachers marked busy at block slots).
                bundle_name = f"{block_name}|{cname}"
                auto_bundles.append({
                    'name':           bundle_name,
                    'display_name':   block_name,   # shown in timetable
                    'type':           'split',
                    'periodsPerWeek': hours,
                    'members':        members,
                })
                logging.info(f"Auto-bundle '{bundle_name}': {len(members)} sub-options in class {cname}")
            else:
                logging.info(f"Auto-bundle for '{block_name}' in {cname}: fewer than 2 sub-options — skipping.")

        merge_groups = incoming_payload.get("merge_groups", [])
        if not isinstance(merge_groups, list):
            return jsonify({"status": "error", "message": "Malformed merge-group data."}), 400

        session_data = {
            "organized":      organized_classes,
            "days": days_cfg,
            "periods": periods_cfg,
            "labs": labs_cfg,
            "session_token":  str(__import__('uuid').uuid4()),
            "auto_bundles":   auto_bundles,
            "merge_groups":   merge_groups,
        }
        with open(spath("last_extraction.json"), "w") as f:
            json.dump(session_data, f)

        return jsonify({"status": "success", "redirect": url_for('setup_fixed')})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Load Verify (restore to verify/configure page) ────────────────────────────
@app.route("/load-verify", methods=["POST"])
def load_verify():
    """
    Stores a verify-page session (rows + days + periods + merge_groups)
    so /edit-schedule can render view_simple.html pre-populated.
    Called by:
      - upload page "Load Saved Data" (v2 saves with page='verify')
      - upload page "Enter Manually" (after class names, before subjects)
    """
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"status": "error", "message": "Invalid JSON payload."}), 400
        rows = payload.get("rows", [])
        if not isinstance(rows, list) or len(rows) > 1000:
            return jsonify({"status": "error", "message": "Invalid saved timetable rows."}), 400
        days         = int(payload.get("days", 6))
        periods      = int(payload.get("periods", 6))
        labs         = int(payload.get("labs", 2))
        merge_groups = payload.get("merge_groups", [])
        twd          = payload.get("temp_web_data")  # may be None for manual entry

        # Preserve every field in each row so lab_no, continuous, total_hours,
        # total_periods etc. are not silently lost on save→load.
        sanitised_rows = []
        for row in rows:
            sanitised_rows.append({
                "class":          row.get("class", ""),
                "subject":        row.get("subject", ""),
                "teacher":        row.get("teacher", ""),
                "type":           row.get("type", "Theory"),
                "periods":        row.get("periods", 0),
                "total_hours":    row.get("total_hours", row.get("periods", 0)),
                "total_periods":  row.get("total_periods", row.get("periods", 0)),
                "continuous":     row.get("continuous", 1),
                "lab_no":         row.get("lab_no", 0),
                "split_block":    row.get("split_block", ""),
                "split_children": row.get("split_children", []),
            })

        verify_session = {
            "rows":          sanitised_rows,
            "days":          days,
            "periods":       periods,
            "labs":          labs,
            "merge_groups":  merge_groups,
            "temp_web_data": twd,
        }
        with open(spath("verify_session.json"), "w") as f:
            json.dump(verify_session, f)

        return jsonify({"status": "success", "redirect": url_for("edit_schedule")})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Edit Schedule (verify page pre-populated from saved/manual data) ──────────
@app.route("/edit-schedule")
def edit_schedule():
    """
    Renders view_simple.html pre-populated from verify_session.json.
    This is used when the user loads a saved file or enters manually.
    The rows already include split_children so splits are shown correctly.
    """
    if not os.path.exists(spath("verify_session.json")):
        return redirect(url_for("home"))

    with open(spath("verify_session.json"), "r") as f:
        vs = json.load(f)

    rows         = vs.get("rows", [])
    days         = int(vs.get("days", 6))
    periods      = int(vs.get("periods", 6))
    merge_groups = vs.get("merge_groups", [])

    import json as _json

    # Attach split_children_json to each row so the Jinja template can embed it
    for row in rows:
        children = row.get("split_children", [])
        row["split_children_json"] = _json.dumps(children)
        # Normalise type capitalisation
        t = str(row.get("type", "Theory"))
        row["type"] = t[0].upper() + t[1:].lower() if t else "Theory"
        # Remove "Class " prefix from class name if the user typed it already
        cn = row.get("class", "")
        if not cn.startswith("Class "):
            row["class"] = "Class " + cn

    labs = int(vs.get("labs", 2))
    
    return render_template(
        "view_simple.html",
        rows=rows,
        extracted_days=days,
        extracted_periods=periods,
        extracted_labs=labs,
        merge_groups_json=_json.dumps(merge_groups),
    )


# ── Load Save File ────────────────────────────────────────────────────────────
@app.route("/load-save", methods=["POST"])
def load_save():
    """
    Receives the temp_web_data blob from a downloaded save file,
    writes it to temp_web_data.json (same as /update-data does),
    and returns a new session_token so fixed_setup can match localStorage.
    """
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"status": "error", "message": "Invalid JSON payload."}), 400
        temp_web_data = payload.get("temp_web_data")
        if not isinstance(temp_web_data, dict):
            return jsonify({"status": "error", "message": "No valid saved timetable data supplied."}), 400
        if len(json.dumps(temp_web_data, ensure_ascii=False)) > 5_000_000:
            return jsonify({"status": "error", "message": "Saved timetable file is too large."}), 413

        # Issue a fresh session token — client will write this into localStorage
        # so fixed_setup.html trusts and loads the restored session data.
        import uuid
        new_token = str(uuid.uuid4())
        temp_web_data["session_token"] = new_token

        with open(spath("last_extraction.json"), "w") as f:
            json.dump(temp_web_data, f)

        return jsonify({
            "status":        "success",
            "session_token": new_token,
            "redirect":      url_for("setup_fixed")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# .................\
@app.route("/setup-fixed")
def setup_fixed():
    if not os.path.exists(spath("last_extraction.json")):
        return redirect(url_for('home'))
        
    with open(spath("last_extraction.json"), "r") as f:
        stored = json.load(f)
    
    # Defensive: always provide periods
    periods_value = stored.get('periods', 8)
    if not isinstance(periods_value, (int, float)):
        periods_value = 8

    # ── Re-stamp classIdx in auto_bundles using className ────────────────────
    # Saved bundles can have stale indices if class order differs from current
    # organized dict. Fix here so fixed_setup.html gets correct indices and
    # validateBeforeSolve doesn't block generation with false stale-index errors.
    class_keys_ordered = list(stored.get('organized', {}).keys())
    fixed_bundles = []
    for ab in stored.get('auto_bundles', []):
        fixed_members = []
        for m in ab.get('members', []):
            m_cn = m.get('className', '').replace('Class ', '').strip()
            try:
                fresh_idx = class_keys_ordered.index(m_cn)
            except ValueError:
                fresh_idx = m.get('classIdx', -1)  # keep as-is if not found
            fixed_m = dict(m)
            fixed_m['classIdx'] = fresh_idx
            fixed_members.append(fixed_m)
        fixed_ab = dict(ab)
        fixed_ab['members'] = fixed_members
        fixed_bundles.append(fixed_ab)
    # Also write back fixed bundles so run-final-solver gets clean data
    stored['auto_bundles'] = fixed_bundles
    with open(spath("last_extraction.json"), "w") as f:
        json.dump(stored, f)

    return render_template(
        "fixed_setup.html",
        days=stored.get('days', 6),
        periods=periods_value,
        class_data=stored.get('organized', {}),
        session_token=stored.get('session_token', 'default'),
        auto_bundles=fixed_bundles,
        temp_web_data=stored
    )
@app.route("/run-final-solver", methods=["POST"])
def run_final_solver():
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"status": "error", "message": "Invalid JSON payload."}), 400
        fixed_data = payload.get("fixed_slots", {})
        unavail_data = payload.get("teacher_unavailability", {})
        elective_bundles = payload.get("elective_bundles", [])
        if not isinstance(fixed_data, dict) or not isinstance(unavail_data, dict) or not isinstance(elective_bundles, list):
            return jsonify({"status": "error", "message": "Malformed solver input."}), 400

        if not os.path.exists(spath("last_extraction.json")):
            return jsonify({"status": "error", "message": "Session expired. Please restart."}), 400

        with open(spath("last_extraction.json"), "r") as f:
            stored = json.load(f)

        # Merge auto_bundles from split rows (persisted in session) with any
        # user-provided bundles from the sync group UI. User bundles take priority
        # (they override by name if the same blockName was also auto-built).
        auto_bundles = stored.get('auto_bundles', [])
        class_keys_for_bundles = list(stored.get('organized', {}).keys())
        if auto_bundles:
            existing_names = {b.get('name') for b in elective_bundles}
            for ab in auto_bundles:
                if ab.get('name') not in existing_names:
                    # Re-stamp classIdx from current class_keys using className
                    # (saved indices can be stale if class order changed)
                    fixed_members = []
                    for m in ab.get('members', []):
                        m_cn = m.get('className', '').replace('Class ', '').strip()
                        try:
                            fresh_idx = class_keys_for_bundles.index(m_cn)
                            m_fixed = dict(m)
                            m_fixed['classIdx'] = fresh_idx
                            fixed_members.append(m_fixed)
                        except ValueError:
                            fixed_members.append(m)  # keep as-is if not found
                    ab_fixed = dict(ab)
                    ab_fixed['members'] = fixed_members
                    elective_bundles.append(ab_fixed)

        # ── Convert merge_groups from verify page into extra elective_bundles ──
        # merge_groups = [{name, entries:[{className, blockName}]}]
        # Each merge group forces all its listed split blocks to share the same
        # K time slots, regardless of which class they belong to.
        merge_groups_stored = stored.get('merge_groups', [])
        class_keys = list(stored.get('organized', {}).keys())
        for mg in merge_groups_stored:
            mg_name = mg.get('name', 'Merge')
            entries = mg.get('entries', [])
            if len(entries) < 2:
                continue
            # Collect all sub-option members across all listed classes
            # Each entry: {className, blockName}  →  look up auto_bundle for that blockName
            mg_members = []
            mg_hours   = None
            existing_bundle_names = {b.get('name') for b in auto_bundles}
            for entry in entries:
                cn = entry.get('className', '').replace('Class ', '').strip()
                bn = entry.get('blockName', '').strip()
                # Find this class's index
                try:
                    cidx = class_keys.index(cn)
                except ValueError:
                    continue
                # Find the matching auto_bundle for this class+blockName.
                # Bundle name is now "BlockName|ClassName" (e.g. "Language|MPC11")
                # so match by both display_name/blockName and className.
                for ab in auto_bundles:
                    ab_display = ab.get('display_name', ab.get('name', ''))
                    ab_matches_block = (ab_display == bn or ab.get('name') == f"{bn}|{cn}")
                    if not ab_matches_block:
                        continue
                    for m in ab.get('members', []):
                        m_cn = m.get('className', '').replace('Class ', '').strip()
                        if m_cn == cn:
                            # Re-stamp classIdx from current class_keys
                            m_fixed = dict(m)
                            m_fixed['classIdx'] = cidx
                            mg_members.append(m_fixed)
                            if mg_hours is None:
                                mg_hours = ab.get('periodsPerWeek', 3)
            if len({m.get('classIdx') for m in mg_members}) >= 2 and mg_members:
                # Only add if not already an auto_bundle with the same name
                if mg_name not in {b.get('name') for b in elective_bundles}:
                    elective_bundles.append({
                        'name':           mg_name,
                        'type':           'merged',
                        'periodsPerWeek': mg_hours or 3,
                        'members':        mg_members,
                    })
                    logging.info(f"Merge group '{mg_name}': {len(mg_members)} members across "
                                 f"{len({m['classIdx'] for m in mg_members})} classes")

        from adapter import build_final_inputs 
        
        (No_of_classes, t_list, c_theory, l_periods, subj_map) = build_final_inputs(
            {"classes": stored['organized']}, 
            stored['days'], 
            stored['periods'], 
            fixed_data
        )

        # ── Convert sync_groups / elective_bundles from frontend to solver format ─
        solver_bundles = []
        if elective_bundles:
            for b in elective_bundles:
                solver_bundles.append({
                    "name":             b.get("name", ""),
                    "type":             b.get("type", "split"),
                    "periodsPerWeek":   int(b.get("periodsPerWeek", 1)),
                    "members":          b.get("members", []),
                    # Legacy fields kept for backward compat with old backtracker path
                    "assignments":      b.get("assignments", {}),
                })

        # --- DEBUG LOGGING ---
        debug_payload = {
            "No_of_classes": No_of_classes,
            "days": stored['days'],
            "periods": stored['periods'],
            "teacher_list": t_list,
            "class_theory_workload": c_theory,
            "lab_periods": l_periods,
            "subject_map": {str(k): v for k, v in subj_map.items()},
            "fixed_periods": fixed_data,
            "elective_bundles": solver_bundles
        }
        with open(spath("solver_input_debug.json"), "w") as f:
            json.dump(debug_payload, f, indent=4)

        final_timetable = generate_timetable_with_retry(
            No_of_classes, stored['days'], stored['periods'], t_list,
            c_theory, l_periods, subj_map,
            fixed_periods=fixed_data,
            teacher_unavailability=unavail_data,
            elective_bundles=solver_bundles
        )

        if final_timetable:
            # 1. Save metadata for the success page
            with open(spath("generated_metadata.json"), "w") as f:
                json.dump({
                    "days": stored["days"],
                    "periods": stored["periods"],
                    "num_classes": No_of_classes,
                    "fixed_slots": fixed_data,
                    "teacher_unavailability": unavail_data,
                    "solver_bundles": solver_bundles
                }, f)
            
            # 2. Save the actual timetable
            with open(spath("generated_timetable.json"), "w") as f:
                json.dump(final_timetable, f)

            # 3. Create the 'final_schedule.json' that success_summary expects
            flat_rows = []
            for c_name, teachers in stored['organized'].items():
                for t in teachers:
                    flat_rows.append({"class": f"Class {c_name}", "teacher": t['teacher']})
            with open(spath("final_schedule.json"), "w") as f:
                json.dump(flat_rows, f)

            # 4. Persist sync groups into temp_web_data so success_summary can
            #    exempt intentional shared-teacher slots from conflict detection
            stored['sync_groups'] = solver_bundles
            with open(spath("last_extraction.json"), "w") as f:
                json.dump(stored, f)

            return jsonify({"status": "success", "redirect": url_for('success_summary')})
        
        # ── Smart solver failure diagnostics ──────────────────────────────────
        report_lines = []
        days        = stored['days']
        periods_day = stored['periods']
        total_slots = days * periods_day
        organized   = stored['organized']

        # 1. Per-class overload
        for cname, teachers in organized.items():
            theory_hrs = sum(int(t.get('hours', 0)) for t in teachers if t.get('type','theory').lower() != 'lab')
            lab_hrs    = sum(int(t.get('hours', 0)) for t in teachers if t.get('type','').lower() == 'lab')
            total_hrs  = theory_hrs + lab_hrs
            if total_hrs > total_slots:
                over = total_hrs - total_slots
                report_lines.append(
                    f"📚 <b>Class {cname}</b> has <b>{total_hrs} hours</b> but only "
                    f"<b>{total_slots} slots</b> available ({over} hour(s) too many). "
                    f"Remove or reduce a subject."
                )

        # 2. Teacher overload — total hours across all classes vs available slots
        teacher_hours = {}
        for cname, teachers in organized.items():
            for t in teachers:
                tname = t.get('teacher', '')
                hours = int(t.get('hours', 0))
                teacher_hours.setdefault(tname, 0)
                teacher_hours[tname] += hours
        for tname, total in teacher_hours.items():
            if total > total_slots:
                over = total - total_slots
                report_lines.append(
                    f"👤 <b>{tname}</b> is assigned <b>{total} hours total</b> across all classes "
                    f"but only {total_slots} slots exist per week ({over} too many). "
                    f"Reduce this teacher's hours or split across different teachers."
                )

        # 3. Fixed slot overcommitment — count fixed slots per class
        fixed_counts = {}
        for cls_str, slots in fixed_data.items():
            count = sum(1 for s in slots.values()
                        if s.get('teacher_id', '__none__') != '__none__' and s.get('label'))
            if count:
                fixed_counts[cls_str] = count
        for cls_str, count in fixed_counts.items():
            cidx = int(cls_str)
            cname = list(organized.keys())[cidx] if cidx < len(organized) else cls_str
            avail = total_slots - count
            theory_needed = sum(int(t.get('hours',0)) for t in organized.get(cname,[])
                                if t.get('type','theory').lower() != 'lab')
            if theory_needed > avail:
                report_lines.append(
                    f"📌 <b>Class {cname}</b>: {count} fixed slots leave only {avail} free slots "
                    f"but theory subjects need {theory_needed}. Remove some fixed slots."
                )

        # 4. Sync group problems
        for b in solver_bundles:
            bname   = b.get('name', 'unnamed')
            k       = int(b.get('periodsPerWeek', 1))
            members = b.get('members', [])
            if len(members) < 2:
                report_lines.append(
                    f"🔗 Sync group <b>\"{bname}\"</b> has fewer than 2 members — skipped by solver."
                )
            # Check every member: does classIdx actually contain that subject?
            class_keys = list(organized.keys())
            for m in members:
                cidx      = int(m.get('classIdx', -1))
                subj_name = (m.get('subject') or '').strip()
                tname_m   = m.get('teacherName', '')
                if cidx < 0 or cidx >= len(class_keys):
                    report_lines.append(
                        f"🔗 Sync group <b>\"{bname}\"</b>: classIdx <b>{cidx}</b> is out of range "
                        f"(only {len(class_keys)} classes exist: indices 0–{len(class_keys)-1}). "
                        f"Re-create the sync group — pick subjects from the correct class rows in the dropdown."
                    )
                    continue
                cname_m   = class_keys[cidx]
                stored_cname = (m.get('className') or '').strip()
                class_subjs = [t.get('subject','') for t in organized.get(cname_m, [])]
                # Also include split-block sub-subjects in the valid subject list
                class_subjs_all = class_subjs  # same list, split_block subjects are in organized too
                if subj_name not in class_subjs:
                    # Detect stale classIdx: the name stored in the member doesn't match
                    # what's at that index now — this is a stale-localStorage problem.
                    if stored_cname and stored_cname != cname_m:
                        # Try to find the right index for the stored class name
                        correct_idx = class_keys.index(stored_cname) if stored_cname in class_keys else -1
                        correct_subjs = [t.get('subject','') for t in organized.get(stored_cname, [])]
                        if correct_idx >= 0 and subj_name in correct_subjs:
                            report_lines.append(
                                f"🔗 Sync group <b>\"{bname}\"</b>: member says class <b>\"{stored_cname}\"</b> "
                                f"but classIdx <b>{cidx}</b> points to <b>\"{cname_m}\"</b> instead. "
                                f"This is stale data from a previous session. "
                                f"<b>Fix:</b> On the Class-Specific Setup page, open the Sync Groups panel, "
                                f"delete group <b>\"{bname}\"</b>, then re-create it — it should be "
                                f"auto-populated from your Split rows. Or click the page back and forward to reload."
                            )
                        else:
                            report_lines.append(
                                f"🔗 Sync group <b>\"{bname}\"</b>: subject <b>\"{subj_name}\"</b> "
                                f"does not exist in <b>Class {cname_m}</b> (index {cidx}). "
                                f"That class has: {', '.join(class_subjs[:6])}. "
                                f"Delete this sync group and re-add it from the correct class rows."
                            )
                    else:
                        report_lines.append(
                            f"🔗 Sync group <b>\"{bname}\"</b>: subject <b>\"{subj_name}\"</b> "
                            f"does not exist in <b>Class {cname_m}</b> (index {cidx}). "
                            f"That class has: {', '.join(class_subjs[:6])}. "
                            f"Delete this sync group and re-add using the correct class rows in the dropdown."
                        )
            # Check if any member's teacher is overloaded with sync slots
            teacher_sync_load = {}
            for m in members:
                tid = str(m.get('teacherId',''))
                tname = m.get('teacherName','?')
                teacher_sync_load.setdefault(tname, 0)
                teacher_sync_load[tname] += k
            for tname, sync_hrs in teacher_sync_load.items():
                total_for_teacher = teacher_hours.get(tname, 0)
                if sync_hrs > total_slots:
                    report_lines.append(
                        f"🔗 Sync group <b>\"{bname}\"</b>: teacher <b>{tname}</b> would need "
                        f"{sync_hrs} slots just for sync assignments but only {total_slots} slots exist."
                    )

        # 5. Teacher unavailability too restrictive
        if unavail_data:
            for tid_str, blocked_slots in unavail_data.items():
                # Find teacher name
                tname = tid_str
                for cname, teachers in organized.items():
                    for t in teachers:
                        if str(t.get('teacher_id','')) == tid_str:
                            tname = t.get('teacher', tid_str)
                            break
                total_blocked = len(blocked_slots)
                avail_slots   = total_slots - total_blocked
                needed = teacher_hours.get(tname, 0)
                if needed > avail_slots:
                    report_lines.append(
                        f"🚫 <b>{tname}</b> has {total_blocked} unavailable slots, leaving "
                        f"{avail_slots} free — but needs {needed} teaching slots. "
                        f"Reduce unavailability or reduce their hours."
                    )

        # Phantom class detection: class with >80% free slots is likely a parsing artifact
        total_s = days * periods_day
        for cname, teachers in organized.items():
            total_hours = sum(int(t.get('hours', 0)) for t in teachers if t.get('type','theory').lower() != 'lab')
            lab_hours = sum(int(t.get('hours', 0)) for t in teachers if t.get('type','').lower() == 'lab')
            real_hours = total_hours + lab_hours
            if real_hours < total_s * 0.2:  # Less than 20% real subjects
                free_hrs = total_s - real_hours
                report_lines.append(
                    f"🔍 <b>Class {cname}</b> has only <b>{real_hours} real subject hours</b> "
                    f"({free_hrs} free slots out of {total_s}). "
                    f"This is likely a <b>PDF extraction artifact</b> — check if this is a real class "
                    f"or leftover data from the last page of the PDF. "
                    f"If it's not a real class, delete all its rows in Data Verification."
                )

        # OR-Tools missing warning
        try:
            from ortools.sat.python import cp_model as _cp
        except ImportError:
            report_lines.append(
                f"⚡ <b>OR-Tools is not installed.</b> The backtracking solver is much slower "
                f"and may fail on inputs this size. "
                f"Run <code>pip install ortools</code> and restart the app to use the fast CP-SAT solver."
            )

        if not report_lines:
            report_lines.append(
                "🤔 No obvious overload found. Possible causes:<br>"
                "• Fixed slots are blocking too many combinations for the solver to fit everything.<br>"
                "• Sync group constraints conflict with teacher availability.<br>"
                "• A teacher teaches many classes and their slots are tightly constrained.<br>"
                "<b>Try:</b> removing some fixed slots, relaxing unavailability, or reducing sync group size."
            )

        conflict_report = "<br><br>".join(report_lines)
        return jsonify({"status": "error", "message": "Solver could not find a valid timetable.", "conflict_report": conflict_report})
    except Exception as e:
        import traceback
        print(traceback.format_exc()) 
        return jsonify({"status": "error", "message": str(e)}), 500

        

@app.route("/swap-slots", methods=["POST"])
def swap_slots():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "Invalid JSON payload."}), 400
        try:
            class_idx, si1, si2 = int(data["class_idx"]), int(data["slot1"]), int(data["slot2"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"status": "error", "message": "class_idx, slot1 and slot2 are required integers."}), 400
        if si1 == si2:
            return jsonify({"status": "success"})
        required = ("generated_timetable.json", "generated_metadata.json", "last_extraction.json")
        if not all(os.path.exists(spath(fn)) for fn in required):
            return jsonify({"status": "error", "message": "No timetable found"}), 404
        with open(spath("generated_timetable.json")) as f:
            timetable = json.load(f)
        with open(spath("generated_metadata.json")) as f:
            meta = json.load(f)
        with open(spath("last_extraction.json")) as f:
            stored = json.load(f)

        days, periods = int(meta["days"]), int(meta["periods"])
        num_classes = int(meta["num_classes"])
        total_slots = days * periods
        if not (0 <= class_idx < num_classes):
            return jsonify({"status": "error", "message": "Class index out of range"}), 400
        if not (0 <= si1 < total_slots) or not (0 <= si2 < total_slots):
            return jsonify({"status": "error", "message": "Slot index out of range"}), 400
        if len(timetable) < total_slots or any(
            not isinstance(timetable[s], list) or len(timetable[s]) < num_classes for s in (si1, si2)
        ):
            return jsonify({"status": "error", "message": "Malformed timetable data."}), 500

        val1, val2 = timetable[si1][class_idx], timetable[si2][class_idx]
        if _fixed_entry_for_slot(meta, class_idx, si1) or _fixed_entry_for_slot(meta, class_idx, si2):
            return jsonify({"status": "error", "message": "Fixed slots cannot be moved. Clear the fixed slot and regenerate."}), 409

        # A lab occupies a consecutive block; the endpoint receives individual pairs,
        # so never permit a partial lab move through this API.
        if _is_lab_cell(class_idx, val1, stored) or _is_lab_cell(class_idx, val2, stored):
            return jsonify({"status": "error", "message": "Lab blocks cannot be moved with the single-slot swap."}), 409

        def real(v):
            return v not in (0, None) and str(v).strip().lower() not in ("", "free", "0")

        def teacher_busy(teacher, slot):
            if not teacher:
                return False
            return any(
                other != class_idx and teacher in _teachers_for_cell(other, cell, stored)
                for other, cell in enumerate(timetable[slot])
            )

        if real(val1) or real(val2):
            for teacher in _teachers_for_cell(class_idx, val1, stored):
                if teacher_busy(teacher, si2):
                    return jsonify({"status": "error", "message": f"Can't swap: {teacher} already teaches another class at that time."}), 409
            for teacher in _teachers_for_cell(class_idx, val2, stored):
                if teacher_busy(teacher, si1):
                    return jsonify({"status": "error", "message": f"Can't swap: {teacher} already teaches another class at that time."}), 409

            def duplicate_same_day(value, target, vacated):
                if not real(value):
                    return False
                day_start = (target // periods) * periods
                return any(
                    slot not in (target, vacated)
                    and str(timetable[slot][class_idx]).strip().lower() == str(value).strip().lower()
                    for slot in range(day_start, day_start + periods)
                )
            if duplicate_same_day(val1, si2, si1):
                return jsonify({"status": "error", "message": f"Can't swap: '{val1}' would appear twice on the same day for this class."}), 409
            if duplicate_same_day(val2, si1, si2):
                return jsonify({"status": "error", "message": f"Can't swap: '{val2}' would appear twice on the same day for this class."}), 409

        timetable[si1][class_idx], timetable[si2][class_idx] = val2, val1
        with open(spath("generated_timetable.json"), "w") as f:
            json.dump(timetable, f)
        return jsonify({"status": "success"})
    except Exception:
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": "Swap failed due to an internal server error."}), 500

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)

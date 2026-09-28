# Timetable Generator

A web-based school timetable generator that converts course and faculty allocation data into a conflict-aware weekly timetable.

## Features

- PDF timetable/course-allocation extraction using PyMuPDF and Groq
- Manual editing and review of extracted data
- OR-Tools CP-SAT scheduling with a backtracking fallback
- Teacher conflict and availability constraints
- Fixed subjects, free periods, and events
- Lab rooms and consecutive lab blocks
- Elective, split, merged, and synchronized groups
- Same-day subject duplication checks
- Teacher timetable views
- Excel and PDF exports
- Session-isolated temporary data
- Defensive input validation and secure session-cookie settings

## Project structure

```text
.
├── FINAL/
│   ├── app.py
│   ├── adapter.py
│   ├── extractor.py
│   ├── solver.py
│   ├── config.py
│   ├── requirements.txt
│   └── templates/
├── .github/
│   └── workflows/
│       └── timetable-audit.yml
└── render.yaml
```

## Workflow

1. Upload timetable/course-allocation data or enter it manually.
2. Extract and normalize classes, subjects, teachers, labs, and workloads.
3. Review and correct the data.
4. Configure fixed periods, teacher unavailability, and elective/sync groups.
5. Generate the timetable with the constraint solver.
6. Review class and teacher schedules.
7. Export the timetable as Excel or PDF.

If required lab hours cannot be scheduled, generation fails rather than returning a partial timetable.

## Local setup

### Requirements

- Python 3.12
- pip
- Groq API key for PDF/LLM extraction

### Install

Linux/macOS:

```bash
cd FINAL
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd FINAL
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Environment

Create `FINAL/.env`:

```env
GROQ_API_KEY=your_groq_api_key
FLASK_SECRET_KEY=your_long_random_secret
FLASK_ENV=development
FLASK_DEBUG=1
```

For production, use a strong secret and keep Flask debug mode disabled.

### Run

```bash
cd FINAL
python app.py
```

Or with Gunicorn:

```bash
cd FINAL
gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 120 app:app
```

## Deployment

The repository includes `render.yaml` for Render deployment.

The deployment configuration:

- Uses Python 3.12
- Installs `FINAL/requirements.txt`
- Runs Gunicorn with two workers
- Disables Flask debug mode
- Generates `FLASK_SECRET_KEY`

Set `GROQ_API_KEY` as a protected deployment environment variable.

## Solver constraints

The scheduler accounts for:

- Teacher availability and clashes
- Subject hour requirements
- Lab room availability
- Consecutive lab periods
- Fixed timetable cells
- Free periods
- Elective/split groups
- Merged/synchronized groups
- Same-day duplicate-subject restrictions

Solver requests are validated before they reach the scheduling engine.

## Exports

### Excel

Creates formatted class sheets with day/period grids. Sheet names and filenames are sanitized.

### PDF

Creates printable timetable layouts with escaped cell text and safe fonts.

## Security and robustness

The application includes:

- Session-specific temporary filenames
- HTTP-only cookies
- SameSite cookie configuration
- Secure cookies in production
- Request size/type validation
- Class, subject, and teacher length limits
- Week configuration validation
- Fixed-slot validation
- Solver payload validation
- PDF header validation
- Safe download filenames
- Safe Excel sheet names
- Escaped PDF text
- Server-side swap validation
- Fixed-slot protection
- Lab-block swap protection

## CI

Pull requests targeting `main` run the **Timetable Audit** workflow.

It checks:

- Python syntax compilation
- Required templates
- Required deployment files
- Required dependency files
- Protection against reintroducing shared upload filenames

CI is a code-level audit; it does not replace end-to-end testing against a live deployment and representative timetable/PDF data.

## Solver fallback

OR-Tools is the preferred scheduling engine. If it is unavailable, the application can fall back to a backtracking solver, which may be significantly slower for larger timetables.

## Notes

PDF extraction requires a valid Groq API key.

Session-generated timetable data is temporary application state and should not be treated as permanent storage.

## License

No license is currently specified for this repository.

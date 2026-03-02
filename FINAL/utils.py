from config import CONFIG

REQUIRED_STEPS = [
    "basic_info",
    "bell_schedule",
    "grades",
    "faculty",
    "lessons"
]

def setup_progress():
    completed = 0
    missing = []

    for step in REQUIRED_STEPS:
        if CONFIG.get(step):
            completed += 1
        else:
            missing.append(step.replace("_", " ").title())

    return completed, len(REQUIRED_STEPS), missing
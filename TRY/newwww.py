import random
from collections import defaultdict

def generate_timetable(
    num_days=6,
    periods_per_day=6,
    num_classes=7,
    teachers=None,
    allow_free_last_day=True
):
    """
    Generates timetable with:
    - No teacher clash per period
    - Random distribution
    - Optional free periods on last day
    """

    if teachers is None:
        teachers = [f"t{i}" for i in range(1, 11)]  # t1 to t10

    total_periods = num_days * periods_per_day
    timetable = []

    for period in range(total_periods):

        row = []

        # Optional: make last day partially free
        if allow_free_last_day and period >= (total_periods - periods_per_day):
            free_slots = random.randint(3, num_classes)
        else:
            free_slots = 0

        available_teachers = teachers.copy()
        random.shuffle(available_teachers)

        for class_index in range(num_classes):

            if free_slots > 0:
                row.append("free")
                free_slots -= 1
            else:
                if not available_teachers:
                    # If teachers exhausted, reset pool
                    available_teachers = teachers.copy()
                    random.shuffle(available_teachers)

                teacher = available_teachers.pop()
                row.append(teacher)

        timetable.append(row)

    return timetable
print(generate_timetable())
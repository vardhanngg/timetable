import json
import os
from groq import Groq
import pymupdf4llm
from dotenv import load_dotenv

load_dotenv()

def get_solver_data_from_pdf(pdf_path):
    # 1. Convert PDF to Markdown (preserves table structure)
    md_text = pymupdf4llm.to_markdown(pdf_path)

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    # 2. Updated prompt: Structure changed from Dict to List to avoid overwriting same teacher IDs
    prompt = f"""
    Extract school timetable data from the provided text into JSON. 
    There are multiple course blocks (e.g., Year 1, Year 2). Treat each as a separate Class (Class 1, Class 2, etc.).

    ### DATA INTEGRITY RULES:
    1. PERIODS: This MUST be a single integer. If the value is missing or you are unsure, use 0. NEVER return an empty list.
    2. LABS: For Lab courses, the "periods" key must be a list: [total_hours_int, 2, 1]. If hours are missing, use [0, 2, 1].
    3. TEACHER IDs: Use only the number from the Faculty code (e.g., "S6" -> 6). If no faculty is listed, use a unique high number (e.g., 99).

    ### REQUIRED JSON STRUCTURE:
    Return ONLY:
    {{
      "teacher_list": {{ "int_id": {{"Name": "FacultyCode"}} }},
      "class_teacher_periods": {{ 
          "class_id": [
              {{ "teacher_id": int, "periods": int, "subject": "Course Name", "type": "theory" }}
          ]
      }},
      "lab_teacher_periods": {{ 
          "class_id": [
              {{ "teacher_id": int, "periods": [total_int, 2, 1], "subject": "Course Name", "type": "lab" }}
          ]
      }}
    }}

    Text:
    {md_text}
    """

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(completion.choices[0].message.content)

# Test run
if __name__ == "__main__":
    data = get_solver_data_from_pdf("timetable.pdf")
    with open("processed_data.json", "w") as f:
        json.dump(data, f, indent=4)
    print("✅ Extraction complete. Ready for solver.")
import pymupdf4llm
import json
import os
from groq import Groq

def get_solver_data_from_pdf(pdf_path):
    # 1. Convert PDF to Markdown (preserves table structure)
    md_text = pymupdf4llm.to_markdown(pdf_path)
    
    client = Groq(api_key="your_gsk_key_here")
    
    # 2. The prompt specifically asks for YOUR solver's data structures
    prompt = f"""
    Extract school timetable data from this text. 
    Return ONLY a JSON object with these exact keys:
    - "No_of_classes": total number of classes
    - "teacher_list": {{ "id": {{"Name": "..."}} }} (IDs must be integers)
    - "class_teacher_periods": {{ "class_id": {{ "teacher_id": periods_int }} }}
    - "lab_teacher_periods": {{ "class_id": {{ "teacher_id": [sessions, length, lab_no] }} }}
    - "subject_map": {{ "class_id,teacher_id": "SubjectName" }}

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
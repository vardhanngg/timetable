import pymupdf4llm
import json
from groq import Groq

def extract_to_solver_format(pdf_path, api_key):
    # 1. Convert PDF to Markdown (Superior for table extraction)
    md_content = pymupdf4llm.to_markdown(pdf_path)
    
    client = Groq(api_key=api_key)
    
    # 2. Precision Prompting
    # This tells the AI exactly how to 'think' about your solver variables
    system_msg = """
    You are a data converter. Convert school schedule text into a JSON object for a backtracking solver.
    Follow these mapping rules:
    - No_of_classes: Total count of distinct classes.
    - teacher_list: Dictionary with integer keys starting from 0.
    - class_teacher_periods: {class_index: {teacher_index: total_hours}}.
    - lab_teacher_periods: {class_index: {teacher_index: [total_sessions, consecutive_len, lab_no]}}.
    - subject_map: A dictionary where key is a string "class_index,teacher_index" and value is the subject name.
    """
    
    user_msg = f"Extract data from this text: \n\n{md_content}"

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        response_format={"type": "json_object"}
    )

    return json.loads(completion.choices[0].message.content)

# Example usage
# data = extract_to_solver_format("my_timetable.pdf", "YOUR_GROQ_KEY")
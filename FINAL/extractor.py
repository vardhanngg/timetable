import json
import os
import time
from groq import Groq
import pymupdf4llm
import fitz  # PyMuPDF
from dotenv import load_dotenv

load_dotenv()

def get_solver_data_from_pdf(pdf_path):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # Initialize the final merged structure
    final_data = {
        "teacher_list": {},
        "class_teacher_periods": {},
        "lab_teacher_periods": {}
    }

    # Open the PDF to count pages
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    print(f"Total pages to process: {total_pages}")

    # Process in chunks (e.g., 1 or 2 pages at a time to stay under 12k TPM)
    for i in range(total_pages):
        print(f"Processing Page {i+1}...")
        
        # Extract markdown for JUST this page
        md_text = pymupdf4llm.to_markdown(pdf_path, pages=[i])

        prompt = f"""
        Extract school timetable data from the provided text into JSON. 
        ### DATA INTEGRITY RULES:
        1. PERIODS: Single integer. Missing = 0.
        2. LABS: For Lab courses, use list: [total_hours_int, 2, 1].
        3. TEACHER IDs: use unique id for each teacher... u can avoid mr, mrs etc ...... u can use unique numbers like 99 etc... 

        ### REQUIRED JSON STRUCTURE:
        Return ONLY:
        {{
          "teacher_list": {{ "int_id": {{"Name": "FacultyCode"}} }},
          "class_teacher_periods": {{ "class_id": [{{ "teacher_id": int, "periods": int, "subject": "str", "type": "theory" }}] }},
          "lab_teacher_periods": {{ "class_id": [{{ "teacher_id": int, "periods": [int, 2, 1], "subject": "str", "type": "lab" }}] }}
        }}

        Text:
        {md_text}
        """

        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            page_json = json.loads(completion.choices[0].message.content)

            # --- MERGE LOGIC ---
            # 1. Update Teacher List (merges unique teachers)
            final_data["teacher_list"].update(page_json.get("teacher_list", {}))

            # 2 & 3. Merge Theory/Lab Periods per class.
            # IMPORTANT: this used to be final_data[...].update(page_json[...]),
            # which — because dict.update() replaces a key's whole value rather
            # than merging it — silently threw away an earlier page's subjects
            # for a class whenever that same class key showed up again on a
            # later page (e.g. its schedule table is split across two pages).
            # We now extend each class's period list instead, and skip exact
            # duplicate rows in case a page boundary causes the same row to be
            # re-emitted by the model.
            for key in ("class_teacher_periods", "lab_teacher_periods"):
                for class_id, new_items in page_json.get(key, {}).items():
                    existing_items = final_data[key].setdefault(class_id, [])
                    existing_signatures = {json.dumps(item, sort_keys=True) for item in existing_items}
                    for item in new_items:
                        signature = json.dumps(item, sort_keys=True)
                        if signature not in existing_signatures:
                            existing_items.append(item)
                            existing_signatures.add(signature)

            # Small delay to prevent hitting Rate Limit on the next loop
            time.sleep(1) 

        except Exception as e:
            print(f"Error on page {i+1}: {e}")

    return final_data

if __name__ == "__main__":
    data = get_solver_data_from_pdf("CBSE_School_CourseAllocation.pdf")
    with open("processed_data.json", "w") as f:
        json.dump(data, f, indent=4)
    print("✅ Full extraction complete.")
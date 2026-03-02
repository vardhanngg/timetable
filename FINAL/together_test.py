import os
from together import Together

# This will automatically pull the key from your 'export' command above
api_key = os.environ.get("TOGETHER_API_KEY")

if not api_key:
    print("❌ Error: TOGETHER_API_KEY not found in environment.")
else:
    client = Together(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {"role": "system", "content": "You are a timetable expert. Create structured weekly schedules."},
                {"role": "user", "content": "Create a Monday timetable for a Computer Science student with 4 classes."}
            ],
        )
        print("✅ SUCCESS!")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ API Error: {e}")
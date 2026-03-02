import os
from groq import Groq

import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

print("⚡ Groq is cooking your timetable...")

try:
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that creates school timetables."},
            {"role": "user", "content": "Create a 5-day CS timetable with 4 classes daily and a lunch break."}
        ],
    )
    print("\n📅 SUCCESS! HERE IS YOUR TIMETABLE:")
    print(completion.choices[0].message.content)

except Exception as e:
    print(f"❌ Still an error: {e}")
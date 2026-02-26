
import os
import google.generativeai as genai

api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    print("Available Gemini Models:")
    for m in genai.list_models():
        print(f"  - {m.name}")
else:
    print("GEMINI_API_KEY not found.")

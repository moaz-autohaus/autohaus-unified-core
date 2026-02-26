
import os
import google.generativeai as genai

# Using the key from the project's .env file
API_KEY = "AIzaSyDiBqT1HIZloAvLtpSWHkFniwmqmC1yY7o"
genai.configure(api_key=API_KEY)

try:
    print(f"Checking project-specific Gemini key: {API_KEY[:10]}...")
    model = genai.GenerativeModel("gemini-flash-latest")
    response = model.generate_content("ping")
    print(f"Success: {response.text.strip()}")
except Exception as e:
    print(f"Failed: {e}")

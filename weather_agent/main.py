import os
from openai import OpenAI
from dotenv import load_dotenv
import requests


load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

def get_weather(city: str) -> str:
    url = f"https://wttr.in/{city}?format=%C+%t+%w+%h"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    res = requests.get(url, headers=headers, timeout=10)
    if (res.status_code == 200):
        return f"The current weather in {city} is: {res.text}"
    
    return "Sorry, I couldn't fetch the weather information right now."
    

def main():
    user_question = input(">>  ")

    response = client.chat.completions.create(
        model="gemini-3-flash-preview",
        messages=[
            {
                "role": "user",
                "content": user_question
            }
        ]
    )

    print(response.choices[0].message.content)
    
print(get_weather("New York"))
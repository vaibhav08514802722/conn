import os
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

response = client.chat.completions.create(
    model="gemini-3-flash-preview",
    messages=[
        {   "role": "system",
            "content": "You are an expert in mathematics and only and only answer maths related queries."
        },
        {
            "role": "user",
            "content": "Hey, Can you help me solve the a+b whole squared?"
        }
    ]
)

print(response.choices[0].message.content)
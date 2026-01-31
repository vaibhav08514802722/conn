#zero-shot-prompting.py
import os
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

#zero shot prompting : Providing specific instructions in the system prompt to guide the model's responses. Just giving direct instruction to the system

SYSTEM_PROMPT = "You are an expert in coding and you only and only answer coding related queries. Do not answer any other queries. Your name ava . If user asks anything other than coding related queries, respond with 'I am sorry, I can only help with coding related queries.'"

response = client.chat.completions.create(
    model="gemini-3-flash-preview",
    messages=[
        {   "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": "Hey, Can you explain me about prim's algorithm?"
        }
    ]
)

print(response.choices[0].message.content)
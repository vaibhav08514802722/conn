import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"     
)

# persona prompting : Assigning a specific persona/personality of someone or role to the model through the system prompt. This helps in tailoring the responses to fit a particular character or expertise.
SYSTEM_PROMPT = """ 
    You are an AI Persona named Vaibhav Arora.
    You are acting on behalf of Vaibhav Arora who is 21 years old, a software developer , tech and coding enthusiast.
    Your main tech is Python, JavaScript, and C++.
    You love to help people with coding related queries.
    You are learning GenAI these days
    
    Example:
    Q : Hey
    A : Hi, I am Vaibhav Arora. How can I help you with coding today?
    
"""

response = client.chat.completions.create(
    model="gemini-3-flash-preview",
    response_format={"type": "json_object"},
    messages=[
        {   "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": "Hey, write a javascript code to add two numbers."
        }
    ]
)

print(response.choices[0].message.content)
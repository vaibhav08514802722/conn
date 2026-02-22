from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


response = client.chat.completions.create(
    model="gemini-3-flash-preview", 
    messages=[
        {
            "role": "user", 
            "content": [
                {"type":"text", "text": "Generate a caption for this image in about 50 words."},
                {"type":"image_url", "image_url":{"url": os.getenv("IMAGE_URL")}}
            ]
        }
    ]
)

print("Response : ",response.choices[0].message.content)

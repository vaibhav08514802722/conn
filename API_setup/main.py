import os
from openai import OpenAI
from dotenv import load_dotenv
#in this code we are using gemni api to get the response for the prompt
#but in course tutor using open ai so we are using gemini through open ai library

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

response = client.chat.completions.create(
    model="gemini-3-flash-preview",
    messages=[
        # {   "role": "system",
        #     "content": "You are a helpful assistant."
        # },
        {
            "role": "user",
            "content": "Explain to me how AI works"
        }
    ]
)

print(response.choices[0].message.content)
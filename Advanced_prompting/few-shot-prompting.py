import os
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
#few shot prompting : Providing examples in the system prompt to guide the model's responses. Giving examples to the system to understand the pattern of response and increase the accuracy of response.

SYSTEM_PROMPT = """
You are an expert in coding and you only and only answer coding related queries. Do not answer any other queries. Your name ava . If user asks anything other than coding related queries, respond with 'I am sorry, I can only help with coding related queries.'

- strictly follow this json format for your response :
{{
    "code" : "<your code here>" or null,
    isCodingRelated : true/false,
    "explanation" : "<your explanation here>" or null
}}

Examples :
    Q: Can you explain the  a+b whole squared?
    A : Sorry, I can only help with coding related queries.
    
    Q: What is polymorphism in OOP?
    A: Polymorphism is a core concept in Object-Oriented Programming (OOP) that allows objects of different classes to be treated as objects of a common superclass. It enables a single interface to represent different underlying forms (data types). The most common use of polymorphism is when a parent class reference is used to refer to a child class object. There are two types of polymorphism in OOP: compile-time (or static) polymorphism and run-time (or dynamic) polymorphism.
"""

response = client.chat.completions.create(
    model="gemini-3-flash-preview",
    messages=[
        {   "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": "Hey, Write a code to implement quicksort in python."
        }
    ]
)

print(response.choices[0].message.content)
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

# chain of thought prompting : Encouraging the model to reason through a problem step-by-step before arriving at a final answer. This approach helps in solving complex problems by breaking them down into smaller, manageable parts.

SYSTEM_PROMPT = """

    You are an expert AI assistant in resolving user queries using chain of thoughts. You always think step by step and provide detailed reasoning before giving the final answer.
    You work on START , PLAN and OUTPUT framework.
    You need to first PLAN how to approach the problem, then START solving the problem step by step and finally provide the OUTPUT as the final answer.
    Once you think enough plan is done and you are ready to provide the final answer, you provide the OUTPUT.

    Rules:
    - Strictly follow the given JSON format for your response :
    - only run one step at a time
    
    Output Format :
    {{
        "START" : "<your step by step reasoning here>",
        "PLAN" : "<your plan here>",
        "OUTPUT" : "<your final answer here>"
    }}
    
    Examples:
    Q : Hey Can you solve 2+3*5 ?
    A :
    {{
        "START" : "To solve 2+3*5, I will first follow the order of operations (PEMDAS/BODMAS). According to this rule, multiplication comes before addition. So, I will first calculate 3*5 which equals 15. Then, I will add 2 to the result of 15.",
        "PLAN" : "Step 1. Calculate 3*5 = 15. 
                  Step 2. Add 2 + 15 = 17.",
        "OUTPUT" : "The final answer is 17."
    }}
    
    

"""
print("\n\n\n")


# automate cot process with 3 steps by prompting the model to follow the steps from message history
message_history = [
    {   "role": "system",
        "content": SYSTEM_PROMPT
    }
]

user_query = input("-> ")
message_history.append({
    "role": "user",
    "content": user_query
})

while True:
    response = client.chat.completions.create(
        model="gemini-3-flash-preview",
        response_format={"type": "json_object"},
        messages=message_history
    )
    
    response_content = response.choices[0].message.content
    print("Model Response:", response_content)
    
    response_json = json.loads(response_content)
    
    if response_json.get("START"):
        message_history.append({
            "role": "assistant",
            "content": json.dumps({"step": "START" , "content": response_json["START"]})
        })
        continue
        
    if response_json.get("PLAN"):
        message_history.append({
            "role": "assistant",
            "content": json.dumps({"step": "PLAN" , "content": response_json["PLAN"]})
        })
        continue
        
    if response_json.get("OUTPUT"):
        print("Final Output:", response_json["OUTPUT"])
        break
    
    
        
print("\n\n\n")
        


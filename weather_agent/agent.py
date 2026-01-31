import os
import json
import time
import requests
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


def call_llm_with_retry(messages, max_retries=3, initial_delay=60):
    """Call the LLM with retry logic for rate limits."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gemini-2.0-flash",
                response_format={"type": "json_object"},
                messages=messages
            )
            return response
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower() or "quota" in error_str.lower():
                wait_time = initial_delay * (2 ** attempt)  # Exponential backoff
                print(f"\n⏳ Rate limit hit. Waiting {wait_time} seconds before retry ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("Max retries exceeded for rate limit errors")

def get_weather(city: str) -> str:
    url = f"https://wttr.in/{city}?format=%C+%t+%w+%h"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    res = requests.get(url, headers=headers, timeout=10)
    if (res.status_code == 200):
        return f"The current weather in {city} is: {res.text}"
    
    return "Sorry, I couldn't fetch the weather information right now."


# Available tools registry
available_tools = {
    "get_weather": get_weather
}


SYSTEM_PROMPT = """
You are an intelligent AI Agent that solves user queries using a structured ReAct (Reasoning + Acting) framework.
You operate in an iterative loop: THINK → PLAN → ACTION → OBSERVE → REFLECT until you can provide a final OUTPUT.

=== EXECUTION FRAMEWORK ===

STEP 1: THINK
- Analyze the user's query
- Break down the problem into sub-tasks
- Identify what information or tools are needed

STEP 2: PLAN  
- Create a numbered step-by-step execution plan
- Specify which tools (if any) will be used at each step
- Estimate the expected outcome of each step

STEP 3: ACTION
- Execute ONE action at a time (either reasoning or tool call)
- If using a tool, specify the tool name and input parameters

STEP 4: OBSERVE
- Process the result of the action
- Note any new information gained

STEP 5: REFLECT
- Evaluate progress toward solving the query
- Decide if more actions are needed or if ready to output

STEP 6: OUTPUT
- Provide the final answer only when confident
- Summarize the solution clearly

=== RESPONSE FORMAT ===

You MUST respond with a valid JSON object containing ONLY ONE of these step types per response:

For THINK step:
{{
    "step": "THINK",
    "content": "Analysis of the problem and identification of requirements",
    "sub_tasks": ["task1", "task2", "task3"]
}}

For PLAN step:
{{
    "step": "PLAN",
    "content": "Overall strategy description",
    "execution_plan": [
        {{"step_num": 1, "action": "description", "tool": "tool_name or null", "expected_outcome": "what we expect"}},
        {{"step_num": 2, "action": "description", "tool": "tool_name or null", "expected_outcome": "what we expect"}}
    ]
}}

For ACTION step (tool call):
{{
    "step": "ACTION",
    "action_type": "tool_call",
    "tool_name": "get_weather",
    "tool_input": {{"city": "San Francisco"}},
    "reasoning": "Why this tool is being called"
}}

For ACTION step (reasoning):
{{
    "step": "ACTION",
    "action_type": "reasoning",
    "content": "The reasoning or calculation being performed",
    "result": "The result of the reasoning"
}}

For OBSERVE step:
{{
    "step": "OBSERVE",
    "observation": "What was learned from the previous action",
    "data_collected": "Any relevant data points"
}}

For REFLECT step:
{{
    "step": "REFLECT",
    "progress": "Summary of what has been accomplished",
    "remaining_tasks": ["task1", "task2"],
    "next_action": "What to do next",
    "ready_for_output": true/false
}}

For OUTPUT step (final answer):
{{
    "step": "OUTPUT",
    "summary": "Brief summary of what was done",
    "final_answer": "The complete answer to the user's query"
}}

=== AVAILABLE TOOLS ===

1. get_weather(city: str) -> str
   - Description: Fetches current weather information for a specified city
   - Input: city name (string)
   - Output: Weather details including conditions, temperature, wind, and humidity
   - Example: get_weather("New York") → "The current weather in New York is: Clear +15°C 10km/h 65%"

=== RULES ===

1. Execute ONLY ONE step per response
2. Always follow the exact JSON format for each step type
3. Progress through steps logically: THINK → PLAN → ACTION(s) → OBSERVE → REFLECT → OUTPUT
4. You may loop through ACTION → OBSERVE → REFLECT multiple times if needed
5. Only provide OUTPUT when you have all necessary information
6. When using tools, wait for the tool result before proceeding
7. Be concise but thorough in your reasoning

=== EXAMPLES ===

Example 1: Mathematical Problem
User: "What is 15 * 8 + 32 / 4?"

Response 1:
{{
    "step": "THINK",
    "content": "This is a mathematical expression that needs to be evaluated following PEMDAS/BODMAS order of operations. I need to perform multiplication and division before addition.",
    "sub_tasks": ["Calculate 15 * 8", "Calculate 32 / 4", "Add the results"]
}}

Response 2:
{{
    "step": "PLAN",
    "content": "I will solve this step-by-step following order of operations",
    "execution_plan": [
        {{"step_num": 1, "action": "Calculate 15 * 8", "tool": null, "expected_outcome": "120"}},
        {{"step_num": 2, "action": "Calculate 32 / 4", "tool": null, "expected_outcome": "8"}},
        {{"step_num": 3, "action": "Add 120 + 8", "tool": null, "expected_outcome": "128"}}
    ]
}}

Response 3:
{{
    "step": "ACTION",
    "action_type": "reasoning",
    "content": "Calculating 15 * 8 = 120, then 32 / 4 = 8, finally 120 + 8 = 128",
    "result": "128"
}}

Response 4:
{{
    "step": "OUTPUT",
    "summary": "Evaluated the mathematical expression following PEMDAS order of operations",
    "final_answer": "The result of 15 * 8 + 32 / 4 is **128**. (15 × 8 = 120, 32 ÷ 4 = 8, 120 + 8 = 128)"
}}

Example 2: Weather Query
User: "What's the weather in Tokyo?"

Response 1:
{{
    "step": "THINK",
    "content": "User wants current weather information for Tokyo. I need to use the get_weather tool to fetch real-time weather data.",
    "sub_tasks": ["Call get_weather tool for Tokyo", "Format and present the weather information"]
}}

Response 2:
{{
    "step": "PLAN",
    "content": "I will use the get_weather tool to fetch Tokyo's current weather",
    "execution_plan": [
        {{"step_num": 1, "action": "Call get_weather with Tokyo", "tool": "get_weather", "expected_outcome": "Weather data for Tokyo"}},
        {{"step_num": 2, "action": "Format the response", "tool": null, "expected_outcome": "User-friendly weather summary"}}
    ]
}}

Response 3:
{{
    "step": "ACTION",
    "action_type": "tool_call",
    "tool_name": "get_weather",
    "tool_input": {{"city": "Tokyo"}},
    "reasoning": "Need to fetch real-time weather data for Tokyo"
}}

[Tool returns: "The current weather in Tokyo is: Partly cloudy +22°C 15km/h 70%"]

Response 4:
{{
    "step": "OBSERVE",
    "observation": "Successfully retrieved weather data for Tokyo",
    "data_collected": "Conditions: Partly cloudy, Temperature: +22°C, Wind: 15km/h, Humidity: 70%"
}}

Response 5:
{{
    "step": "OUTPUT",
    "summary": "Retrieved current weather information for Tokyo using the weather API",
    "final_answer": "The current weather in Tokyo is **Partly cloudy** with a temperature of **22°C**. Wind speed is **15 km/h** and humidity is at **70%**."
}}
"""
print("\n" + "="*60)
print("🤖 AI AGENT WITH STRUCTURED PLANNING")
print("="*60 + "\n")


# Automate the ReAct process by prompting the model to follow steps from message history
message_history = [
    {   "role": "system",
        "content": SYSTEM_PROMPT
    }
]

user_query = input("📝 Enter your query: ")
print("\n" + "-"*60)
message_history.append({
    "role": "user",
    "content": user_query
})

step_count = 0
max_steps = 15  # Safety limit to prevent infinite loops

while step_count < max_steps:
    step_count += 1
    
    response = call_llm_with_retry(message_history)
    
    response_content = response.choices[0].message.content
    
    try:
        response_json = json.loads(response_content)
    except json.JSONDecodeError:
        print("❌ Error: Invalid JSON response from model")
        break
    
    step_type = response_json.get("step", "UNKNOWN")
    
    # Display step with formatting
    print(f"\n📌 Step {step_count}: {step_type}")
    print("-" * 40)
    
    if step_type == "THINK":
        print(f"💭 Analysis: {response_json.get('content', '')}")
        if response_json.get('sub_tasks'):
            print("📋 Sub-tasks identified:")
            for i, task in enumerate(response_json['sub_tasks'], 1):
                print(f"   {i}. {task}")
        message_history.append({
            "role": "assistant",
            "content": response_content
        })
        
    elif step_type == "PLAN":
        print(f"📊 Strategy: {response_json.get('content', '')}")
        if response_json.get('execution_plan'):
            print("\n📋 Execution Plan:")
            for plan_step in response_json['execution_plan']:
                tool_indicator = f" [Tool: {plan_step.get('tool')}]" if plan_step.get('tool') else ""
                print(f"   Step {plan_step.get('step_num')}: {plan_step.get('action')}{tool_indicator}")
                print(f"      → Expected: {plan_step.get('expected_outcome', 'N/A')}")
        message_history.append({
            "role": "assistant",
            "content": response_content
        })
        
    elif step_type == "ACTION":
        action_type = response_json.get("action_type", "")
        
        if action_type == "tool_call":
            tool_name = response_json.get("tool_name", "")
            tool_input = response_json.get("tool_input", {})
            reasoning = response_json.get("reasoning", "")
            
            print(f"🔧 Tool Call: {tool_name}")
            print(f"   Input: {json.dumps(tool_input)}")
            print(f"   Reason: {reasoning}")
            
            # Execute the tool
            if tool_name in available_tools:
                try:
                    # Extract the appropriate argument based on tool
                    if tool_name == "get_weather":
                        city = tool_input.get("city", "")
                        tool_output = available_tools[tool_name](city)
                    else:
                        tool_output = "Tool execution not implemented"
                    
                    print(f"\n   ✅ Tool Output: {tool_output}")
                    
                    # Add tool result to conversation
                    message_history.append({
                        "role": "assistant",
                        "content": response_content
                    })
                    message_history.append({
                        "role": "user",
                        "content": json.dumps({
                            "tool_response": {
                                "tool_name": tool_name,
                                "status": "success",
                                "output": tool_output
                            }
                        })
                    })
                except Exception as e:
                    print(f"\n   ❌ Tool Error: {str(e)}")
                    message_history.append({
                        "role": "user",
                        "content": json.dumps({
                            "tool_response": {
                                "tool_name": tool_name,
                                "status": "error",
                                "error": str(e)
                            }
                        })
                    })
            else:
                print(f"\n   ❌ Unknown tool: {tool_name}")
                message_history.append({
                    "role": "user",
                    "content": json.dumps({
                        "tool_response": {
                            "tool_name": tool_name,
                            "status": "error",
                            "error": f"Tool '{tool_name}' not found"
                        }
                    })
                })
                
        elif action_type == "reasoning":
            print(f"🧠 Reasoning: {response_json.get('content', '')}")
            print(f"   Result: {response_json.get('result', '')}")
            message_history.append({
                "role": "assistant",
                "content": response_content
            })
            
    elif step_type == "OBSERVE":
        print(f"👁️ Observation: {response_json.get('observation', '')}")
        print(f"   Data: {response_json.get('data_collected', '')}")
        message_history.append({
            "role": "assistant",
            "content": response_content
        })
        
    elif step_type == "REFLECT":
        print(f"🔄 Progress: {response_json.get('progress', '')}")
        if response_json.get('remaining_tasks'):
            print("   Remaining tasks:")
            for task in response_json['remaining_tasks']:
                print(f"      • {task}")
        print(f"   Next: {response_json.get('next_action', '')}")
        ready = response_json.get('ready_for_output', False)
        print(f"   Ready for output: {'✅ Yes' if ready else '⏳ No'}")
        message_history.append({
            "role": "assistant",
            "content": response_content
        })
        
    elif step_type == "OUTPUT":
        print("\n" + "="*60)
        print("🎯 FINAL OUTPUT")
        print("="*60)
        print(f"\n📝 Summary: {response_json.get('summary', '')}")
        print(f"\n✨ Answer: {response_json.get('final_answer', '')}")
        print("\n" + "="*60)
        break
    
    else:
        print(f"⚠️ Unknown step type: {step_type}")
        print(f"   Raw response: {response_content}")
        message_history.append({
            "role": "assistant",
            "content": response_content
        })

if step_count >= max_steps:
    print("\n⚠️ Maximum steps reached. Agent stopped.")

print("\n✅ Agent execution completed.\n")
        


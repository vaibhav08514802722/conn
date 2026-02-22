from dotenv import load_dotenv
import os
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model

load_dotenv()

#lang graph is a framework to build and execute graphs where each node can represent a function that processes some state and produces an output state. In this example, we are building a simple graph with two nodes: "chatbot" and "sample_node". The graph starts with an initial state containing a message, processes it through the chatbot node, and then passes the output to the sample_node before reaching the end of the graph.

llm = init_chat_model(
    model="gemini-2.0-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model_provider="openai"
)

#state definition for the graph
class State(TypedDict):
    messages: Annotated[list, add_messages]
  
#first node function of the graph  
def chatbot(state: State) -> State:
    print("State received in chatbot node:", state)
    print("\n")
    response  = llm.invoke(state["messages"])
    print("Response from LLM in chatbot node:", response)
    return {"messages": [response]}


#second node function of the graph
def sample_node(state: State) -> State:
    print("State received in sample_node node:", state)
    print("\n")
    #state["messages"].append("This is a message from sample_node node(2nd node)!")
    return {"messages":["This is a message from sample_node node(2nd node)!"]}



#building the graph    
graph_builder = StateGraph(State)

graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("sample_node", sample_node)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", "sample_node")
graph_builder.add_edge("sample_node", END)

graph = graph_builder.compile()

updated_state = graph.invoke(State({"messages": ["hey there! My name is Vaibhav !"]}))
print("Final updated state after graph execution:", updated_state)
print("\n")

#explaining the graph
# {start} --> chatbot --> sample_node --> {end}  (2 nodes and 3 edges)

# state = {"messages": ["hey there!"]}
# node runs : Chaatbot(state:["hey there!"]) --> ["Hi, This is a message from chatbot node(1st node)!" ]"])
# state after 1st node : {"messages": ["Hi, This is a message from chatbot node(1st node)!"]}
# node runs : sample_node(state:["Hi, This is a message from chatbot node(1st node)!"]) --> ["This is a message from sample_node node(2nd node)!"]

from dotenv import load_dotenv
import os
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.mongodb import MongoDBSaver 

load_dotenv()

llm = init_chat_model(
    model="gemini-3-flash-preview",
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


#building the graph    
graph_builder = StateGraph(State)

graph_builder.add_node("chatbot", chatbot)


graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)


#compiling and invoking the graph
graph = graph_builder.compile()
def compile_graph_with_checkpointer(checkpointer):
    return graph_builder.compile(checkpointer=checkpointer)

DB_URL = "mongodb://admin:admin@localhost:27017"
with MongoDBSaver.from_conn_string(DB_URL) as checkpointer:
    #compiled_graph = graph_builder.compile(checkpointer=checkpointer)


    graph_with_checkpointer = compile_graph_with_checkpointer(checkpointer=checkpointer)

    config = {
            "configurable": {
                "thread_id": "Vaibhav"
            }
        }

    updated_state = graph_with_checkpointer.invoke(
        State({"messages": ["What is my name?"]}) ,
        config=config
        )
    print("Final updated state after graph execution:", updated_state)
    print("\n")

#explaining the graph
# {start} --> chatbot --> sample_node --> {end}  (2 nodes and 3 edges)

# state = {"messages": ["hey there!"]}
# node runs : Chaatbot(state:["hey there!"]) --> ["Hi, This is a message from chatbot node(1st node)!" ]"])
# state after 1st node : {"messages": ["Hi, This is a message from chatbot node(1st node)!"]}
# node runs : sample_node(state:["Hi, This is a message from chatbot node(1st node)!"]) --> ["This is a message from sample_node node(2nd node)!"]

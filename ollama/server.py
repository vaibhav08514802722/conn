from fastapi import FastAPI, Body
from ollama import Client


app = FastAPI()
Client = Client(
    host="http://localhost:11434",
)


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/chat")
def chat(
    message: str = Body(..., description="The message to send to the Ollama model")
):
    response = Client.chat(
        model="gemma:2b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": message},
        ],
    )
    return {"Response ": response.message.content} 


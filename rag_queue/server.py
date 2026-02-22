from fastapi import FastAPI, Query
from .client.rq_client import queue
from .queues.worker import process_query
from dotenv import load_dotenv

load_dotenv()


app = FastAPI()

@app.get("/")
def root():
    return {"status": "RAG Queue Server is running."}

@app.post("/chat")  
def chat(query: str = Query(... , description="User query for the RAG system")):
    job = queue.enqueue(process_query, query)
    
    return {"status ": "queued", "job_id": job.id}

@app.get("/result")
def get_result(job_id: str = Query(... , description="Job ID to fetch the result for")) :
    job = queue.fetch_job(job_id)
    if job is None:
        return {"status": "not found"}
    elif job.is_finished:
        return {"status": "finished", "result": job.return_value()}
    elif job.is_failed:
        return {"status": "failed", "error": str(job.exc_info)}
    else:
        return {"status": "in progress"}
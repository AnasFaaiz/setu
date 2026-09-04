import sys 
import os 

from fastapi import FastAPI 
import redis
from rq import Queue
from tasks.jobs import dummy_job

app = FastAPI()
redis_conn = redis.Redis(host="localhost", port="6379")
queue = Queue(connection=redis_conn)

@app.post("/enqueue/{name}")
def enqueue(name: str):
    job = queue.enqueue(dummy_job, name)
    return {"job_id": job.id, "status": "queued"}

@app.get("/status/{job_id}")
def status(job_id: str):
    job = queue.fetch_job(job_id)
    if job is None:
        return {"error": "job not found"}
    return {
        "status": job.get_status(),
        "result": job.result,
    }

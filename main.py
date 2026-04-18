from fastapi import FastAPI
from openai import OpenAI
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok"}

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def run_pipeline(task):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful business assistant."},
            {"role": "user", "content": task}
        ]
    )
    return response.choices[0].message.content

@app.post("/run")
def run(task: dict):
    prompt = task.get("task")

    output = run_pipeline(prompt)

    return {
        "results": [
            {"step": "AI Response", "result": output}
        ]
    }

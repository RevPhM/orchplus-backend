from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok"}

from openai import OpenAI

import os
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.post("/run")
def run(task: dict):
    prompt = task.get("task")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful business assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    output = response.choices[0].message.content

    return {
        "results": [
            {"step": "AI Response", "result": output}
        ]
    }

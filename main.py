from fastapi import FastAPI
from openai import OpenAI
import os
import json

from supabase import create_client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)



app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok"}

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ---------- AGENTS ----------

def planner_agent(task):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Break the task into 3-5 clear actionable steps. Return ONLY a JSON array of strings."
            },
            {"role": "user", "content": task}
        ]
    )

    try:
        return json.loads(response.choices[0].message.content)
    except:
        return [task]


def executor_agent(step):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Execute this step clearly and concisely."
            },
            {"role": "user", "content": step}
        ]
    )

    return response.choices[0].message.content


def reviewer_agent(results):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Combine and improve the following results into one clear final answer."
            },
            {
                "role": "user",
                "content": "\n".join(results)
            }
        ]
    )

    return response.choices[0].message.content


# ---------- ORCHESTRATOR ----------

def run_pipeline(task):
    steps = planner_agent(task)

    results = []
    for step in steps:
        result = executor_agent(step)
        results.append(result)

    final = reviewer_agent(results)

    return final


# ---------- ENDPOINT ----------

@app.get("/test-supabase")
def test_supabase():
    response = supabase.table("steps").select("*").limit(5).execute()
    return response.data

@app.post("/run")
def run(task: dict):
    prompt = task.get("task")

    if not prompt:
        return {"error": "No task provided"}

    output = run_pipeline(prompt)

    return {
        "results": [
            {"step": "Final Answer", "result": output}
        ]
    }

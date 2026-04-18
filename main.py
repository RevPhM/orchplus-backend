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
    db_data = supabase.table("steps").select("step, result").ilike("step", f"%{task}%").limit(5).execute().data

    if not db_data:
        db_data = supabase.table("steps").select("step, result").limit(5).execute().data

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""
You are a planner.

You have access to previous knowledge:
{db_data}

Break the task into 3-5 steps using this knowledge if relevant.
Return ONLY a JSON array of strings.
"""
            },
            {"role": "user", "content": task}
        ]
    )

    try:
        if not response.choices or not response.choices[0].message or not response.choices[0].message.content:
            return [task]

        return json.loads(response.choices[0].message.content)
    except:
        return [task]




def executor_agent(step):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_memory",
                "description": "Search previous steps in Supabase",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    def search_memory(query):
        data = supabase.table("steps") \
            .select("step, result") \
            .ilike("step", f"%{query}%") \
            .limit(5) \
            .execute().data
        return json.dumps(data)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an autonomous agent. Use tools if needed."},
            {"role": "user", "content": step}
        ],
        tools=tools,
        tool_choice="auto"
    )

    if not response.choices or not response.choices[0].message:
        return "Error: empty response from model"

    message = response.choices[0].message

    # --- TOOL CALL ---
    if hasattr(message, "tool_calls") and message.tool_calls:
        tool_call = message.tool_calls[0]
        args = json.loads(tool_call.function.arguments or "{}")

        tool_result = ""

        if tool_call.function.name == "search_memory":
            tool_result = search_memory(args.get("query", ""))

        second_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an autonomous agent."},
                {"role": "user", "content": step},
                message,
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                }
            ]
        )

        if not second_response.choices or not second_response.choices[0].message:
            return "Error: empty second response"

        return second_response.choices[0].message.content

    return message.content or "No content returned"





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

        # sauvegarde chaque étape
        save_step(step, result)

        results.append(result)

    final = reviewer_agent(results)

    return final


def save_step(step, result):
    # compter nombre total de lignes
    count = supabase.table("steps").select("id", count="exact").execute().count

    # si trop de lignes → supprimer les plus anciennes
    if count and count > 100:
        old = supabase.table("steps").select("id").order("created_at", desc=False).limit(10).execute().data
        ids = [row["id"] for row in old]

        if ids:
            supabase.table("steps").delete().in_("id", ids).execute()

    # éviter doublons simples
    existing = supabase.table("steps").select("id").eq("step", step).limit(1).execute().data

    if not existing:
        supabase.table("steps").insert({
            "step": step,
            "result": result
        }).execute()



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

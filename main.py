from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok"}

@app.post("/run")
def run(task: dict):
    return {
        "results": [
            {"step": "Example", "result": f"Received: {task.get('task')}"}
        ]
    }

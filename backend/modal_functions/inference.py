import modal

app = modal.App("agentforge-inference")


@app.function()
@modal.web_endpoint(method="POST")
def generate(request: dict):
    return {"status": "ok", "message": "Inference stub for AgentForge"}

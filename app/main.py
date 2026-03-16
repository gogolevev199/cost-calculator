from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Cost calculator 3.0"}
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Test app is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)

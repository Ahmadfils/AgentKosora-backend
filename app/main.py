from fastapi import FastAPI
from app.api.correction import router as correction_router

app = FastAPI(
    title="SmartCorrect API",
    description="AI-powered correction backend for education professionals",
    version="0.1.0"
)

app.include_router(correction_router, prefix="/correction")

@app.get("/")
def root():
    return {"status": "AgentKosora backend running"}

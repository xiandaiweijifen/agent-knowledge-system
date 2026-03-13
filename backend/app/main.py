from fastapi import FastAPI
from app.api.routes.health import router as health_router

app = FastAPI(title="Agent Knowledge System")

app.include_router(health_router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Agent Knowledge System backend is running"}
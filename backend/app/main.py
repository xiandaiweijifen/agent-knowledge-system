from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.documents import router as documents_router
from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.query import router as query_router

app = FastAPI(title="Agent Knowledge System")

app.include_router(health_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")
app.include_router(query_router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Agent Knowledge System backend is running"}

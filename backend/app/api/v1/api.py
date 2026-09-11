# pyrefly: ignore [missing-import]
from fastapi import APIRouter

from app.api.v1.endpoints import auth, documents, chats, pyqs, study_plans, quizzes, evaluations, analytics

api_router = APIRouter()

# Include authentication endpoints
api_router.include_router(
    auth.router, 
    prefix="/auth", 
    tags=["Authentication"]
)

# Include document ingestion endpoints
api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"]
)

# Include chat assistant endpoints
api_router.include_router(
    chats.router,
    prefix="/chats",
    tags=["Chat Assistant"]
)

# Include PYQ analytics endpoints
api_router.include_router(
    pyqs.router,
    prefix="/pyqs",
    tags=["PYQ Analytics"]
)

# Include study planner endpoints
api_router.include_router(
    study_plans.router,
    prefix="/study-plans",
    tags=["Study Planner"]
)

# Include quizzes generator endpoints
api_router.include_router(
    quizzes.router,
    prefix="/quizzes",
    tags=["Quiz Generator"]
)

# Include answer evaluation endpoints
api_router.include_router(
    evaluations.router,
    prefix="/evaluations",
    tags=["Answer Evaluation"]
)

# Include analytics dashboard endpoints
api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics Dashboard"]
)








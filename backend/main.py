import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, SessionLocal, Base
from models.entities import User
from middlewares.auth_middleware import hash_password
from routes.auth_routes import router as auth_router
from routes.post_routes import router as post_router
from routes.story_reel_routes import router as story_reel_router
from routes.chat_routes import router as chat_router
from routes.admin_routes import router as admin_router

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title="Fetagram Production Platform API",
    version="3.0.0",
    description="Zero-Mock Enterprise Social Media & Isolated Admin Governance API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def bootstrap_clean_database():
    """Idempotent startup check: creates all 22 tables and ONLY the Super Admin account if no users exist."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            master_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "Admin@Fetagram2026")
            super_admin = User(
                username="admin",
                email="admin@fetagram.internal",
                password_hash=hash_password(master_password),
                full_name="Platform Super Administrator",
                bio="Fetagram Trust & Safety Super Admin",
                website="",
                avatar_url="",
                is_verified=True,
                is_banned=False,
                role="SUPER_ADMIN",
            )
            db.add(super_admin)
            db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    bootstrap_clean_database()


app.include_router(auth_router)
app.include_router(post_router)
app.include_router(story_reel_router)
app.include_router(chat_router)
app.include_router(admin_router)


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "fetagram-backend", "port": 8000}


if __name__ == "__main__":
    bootstrap_clean_database()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

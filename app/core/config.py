import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no definido en .env")

    # CORS
    ALLOWED_ORIGINS = [
        "https://www.stepsconsulting.cl",
        "https://stepsconsulting.cl",
        "https://www.stepsapp.cl",
        "https://stepsapp.cl",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3005",
        "http://127.0.0.1:3005",
    ]

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "3st3rn0cl3idom4st0id30")
    JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "43200"))
    JWT_ALGORITHM: str = "HS256"


settings = Settings()

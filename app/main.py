import ipaddress
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field


DATABASE_PATH = Path(os.getenv("MANOVICHAR_DATABASE_PATH", "manovichar.db"))

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,"
    "http://127.0.0.1:5173,https://manovichar.com,https://www.manovichar.com"
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("MANOVICHAR_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]


class BlogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    author: str = Field(default="Dr. AR Soni", min_length=1, max_length=200)
    image_url: Optional[str] = Field(default=None, max_length=2048)
    published: bool = True


class BlogResponse(BaseModel):
    id: str
    title: str
    content: str
    author: str
    image_url: Optional[str]
    created_at: datetime
    published: bool


def connect_db() -> sqlite3.Connection:
    if str(DATABASE_PATH) != ":memory:":
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DATABASE_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with connect_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS blogs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL,
                image_url TEXT,
                created_at TEXT NOT NULL,
                published INTEGER NOT NULL DEFAULT 1
            )
            """
        )


def require_admin(request: Request) -> None:
    # Check all possible header variations (handling Render's underscore stripping)
    headers = request.headers
    token = (
        headers.get("x-admin-token") or
        headers.get("manovichar-admin-token") or
        headers.get("manovichar_admin_token") or
        headers.get("authorization") or
        headers.get("token")
    )
    
    expected_token = os.getenv("MANOVICHAR_ADMIN_TOKEN", "Manovichar2026")
    
    # Clean up token (remove 'Bearer ' prefix if any, and strip spaces)
    clean_token = token.replace("Bearer ", "").strip() if token else ""
    clean_expected = expected_token.strip()

    if not token or not secrets.compare_digest(clean_token, clean_expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )


def require_admin_for_local_testing(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    try:
        is_loopback = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        is_loopback = False

    if (
        os.getenv("MANOVICHAR_ENV", "production").strip().lower() == "development"
        and os.getenv("MANOVICHAR_ALLOW_LOCAL_ADMIN_WITHOUT_TOKEN", "").lower() == "true"
        and is_loopback
    ):
        return
    require_admin(request)

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Manovichar Blog API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/blogs", response_model=list[BlogResponse])
def get_blogs() -> list[dict]:
    with connect_db() as connection:
        rows = connection.execute(
            "SELECT * FROM blogs WHERE published = 1 ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/blogs/{blog_id}", response_model=BlogResponse)
def get_blog(blog_id: str) -> dict:
    with connect_db() as connection:
        row = connection.execute(
            "SELECT * FROM blogs WHERE id = ? AND published = 1",
            (blog_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")
    return dict(row)

@app.post(
    "/api/admin/blogs",
    response_model=BlogResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_for_local_testing)],
)

def create_blog(blog: BlogCreate) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    blog_id = str(uuid4())
    with connect_db() as connection:
        connection.execute(
            """
            INSERT INTO blogs (id, title, content, author, image_url, created_at, published)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                blog_id,
                blog.title,
                blog.content,
                blog.author,
                blog.image_url,
                created_at,
                int(blog.published),
            ),
        )
    return {
        "id": blog_id,
        **blog.model_dump(),
        "created_at": created_at,
    }


@app.delete(
    "/api/admin/blogs/{blog_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_blog(blog_id: str) -> Response:
    with connect_db() as connection:
        cursor = connection.execute("DELETE FROM blogs WHERE id = ?", (blog_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
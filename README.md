# Manovichar Blog API

A small FastAPI service that stores blog posts in SQLite.

## Run locally

Use Python 3.9 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:MANOVICHAR_ENV = "development"
$env:MANOVICHAR_ALLOW_LOCAL_ADMIN_WITHOUT_TOKEN = "true"
uvicorn app.main:app --reload
```

The database is created as `manovichar.db` in the current directory. Set
`MANOVICHAR_DATABASE_PATH` to use a different file.

## Configuration

- `MANOVICHAR_ADMIN_TOKEN` is required for admin endpoints in production. If
  unset, those endpoints return `503` rather than running without authentication.
- Local tokenless testing is enabled only when both
  `MANOVICHAR_ENV=development` and
  `MANOVICHAR_ALLOW_LOCAL_ADMIN_WITHOUT_TOKEN=true` are set, and only for
  loopback clients. The bypass is disabled by default and cannot be enabled
  merely by sending a localhost `Host` header.
- In production, set `MANOVICHAR_ENV=production` and
  `MANOVICHAR_ADMIN_TOKEN` to a long random secret. The backend requires that
  secret in the `MANOVICHAR_ADMIN_TOKEN` request header.
- `MANOVICHAR_CORS_ORIGINS` is a comma-separated allowlist of frontend origins.
  By default it allows React development servers on `localhost:3000` and
  `localhost:5173` (and their `127.0.0.1` equivalents). Set this to include the
  exact origin of the deployed frontend.

Send the admin secret in the `MANOVICHAR_ADMIN_TOKEN` header.

## Endpoints

- `GET /api/blogs` — published posts, newest first.
- `GET /api/blogs/{blog_id}` — one published post. Unpublished and missing posts
  both return `404`.
- `POST /api/admin/blogs` — create a post; `published` defaults to `true`.
- `DELETE /api/admin/blogs/{blog_id}` — delete a post.

Example create request:

```json
{
  "title": "A blog post",
  "content": "Post content",
  "author": "Dr. AR Soni",
  "image_url": null,
  "published": true
}
```

Interactive API documentation is available at `/docs`.

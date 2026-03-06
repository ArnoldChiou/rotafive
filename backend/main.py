import os
import json
import random
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
import asyncpg
import redis
from dotenv import load_dotenv

from auth import (
    hash_password, verify_password,
    create_access_token, get_current_user, oauth2_scheme
)

load_dotenv()

# ─── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rotafive")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
COOLDOWN_TTL = 1800  # 30 minutes

db_pool = None
redis_client = None

# ─── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        yield
    finally:
        if db_pool:
            await db_pool.close()
        if redis_client:
            redis_client.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth dependency helper (injects db_pool) ──────────────────────────────────
async def current_user(token: str = Depends(oauth2_scheme)):
    return await get_current_user(token, db_pool)

async def require_client(user=Depends(current_user)):
    if user["role"] != "client":
        raise HTTPException(status_code=403, detail="Clients only")
    return user

async def require_freelancer(user=Depends(current_user)):
    if user["role"] != "freelancer":
        raise HTTPException(status_code=403, detail="Freelancers only")
    return user

# ─── Pydantic Models ───────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str  # 'client' or 'freelancer'
    name: Optional[str] = None  # required if role == 'freelancer'
    skills: Optional[List[str]] = []

class SelectRequest(BaseModel):
    freelancer_id: int
    project_id: Optional[int] = None

class RespondRequest(BaseModel):
    freelancer_id: int
    project_id: int
    action: str  # 'accept' or 'decline'

class SimulateDeclineRequest(BaseModel):
    project_id: int

class InviteRequest(BaseModel):
    freelancer_id: int
    project_id: int

# ══════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    """Register a new user. If role is freelancer, also creates a freelancer profile."""
    if req.role not in ("client", "freelancer"):
        raise HTTPException(status_code=400, detail="Role must be 'client' or 'freelancer'")
    if req.role == "freelancer" and not req.name:
        raise HTTPException(status_code=400, detail="Name is required for freelancer registration")

    hashed = hash_password(req.password)
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            try:
                user = await conn.fetchrow(
                    "INSERT INTO users (email, hashed_password, role) VALUES ($1, $2, $3) RETURNING id, email, role",
                    req.email, hashed, req.role
                )
            except asyncpg.exceptions.UniqueViolationError:
                raise HTTPException(status_code=400, detail="Email already registered")

            if req.role == "freelancer":
                skills_json = json.dumps(req.skills or [])
                await conn.execute(
                    "INSERT INTO freelancers (user_id, name, skills, rating, status) VALUES ($1, $2, $3::jsonb, 5.0, 'idle')",
                    user["id"], req.name, skills_json
                )

    return {"id": user["id"], "email": user["email"], "role": user["role"]}


@app.post("/api/auth/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible login endpoint — returns JWT access token."""
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", form_data.username)

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


@app.get("/api/auth/me")
async def me(user=Depends(current_user)):
    """Return current user info."""
    return user

# ══════════════════════════════════════════════════════════════════════════════
# FREELANCER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/freelancers")
async def get_all_freelancers():
    """Returns all freelancers with Redis cooldown info. Public endpoint for Admin Queue view."""
    query = """
    SELECT id, name, skills, rating, status,
           last_assigned_at::text as last_assigned_at
    FROM freelancers
    ORDER BY
        CASE WHEN status = 'working' THEN 1 ELSE 0 END,
        last_assigned_at ASC
    """
    async with db_pool.acquire() as conn:
        records = await conn.fetch(query)
        result = [dict(r) for r in records]

    for f in result:
        ttl = redis_client.ttl(f"cooldown:{f['id']}")
        f["cooling"] = ttl > 0
        f["cooldown_ttl"] = ttl if ttl > 0 else 0

    return result


@app.get("/api/invitations")
async def get_invitations(user=Depends(current_user)):
    """
    Returns pending 'invited' records.
    - Freelancers only see their own invitations.
    - Clients see all invitations for their projects.
    """
    async with db_pool.acquire() as conn:
        if user["role"] == "freelancer":
            # Find the freelancer profile linked to this user
            freelancer = await conn.fetchrow(
                "SELECT id FROM freelancers WHERE user_id = $1", user["id"]
            )
            if not freelancer:
                return []
            query = """
                SELECT d.project_id, d.freelancer_id,
                       f.name as freelancer_name,
                       p.title as project_title,
                       d.created_at::text as created_at
                FROM dispatch_logs d
                JOIN freelancers f ON d.freelancer_id = f.id
                JOIN projects p ON d.project_id = p.id
                WHERE d.status = 'invited' AND d.freelancer_id = $1
                ORDER BY d.created_at DESC
            """
            records = await conn.fetch(query, freelancer["id"])
        else:
            # Client: see all invitations for their own projects
            query = """
                SELECT d.project_id, d.freelancer_id,
                       f.name as freelancer_name,
                       p.title as project_title,
                       d.created_at::text as created_at
                FROM dispatch_logs d
                JOIN freelancers f ON d.freelancer_id = f.id
                JOIN projects p ON d.project_id = p.id
                WHERE d.status = 'invited' AND p.client_id = $1
                ORDER BY d.created_at DESC
            """
            records = await conn.fetch(query, user["id"])

    return [dict(r) for r in records]

# ══════════════════════════════════════════════════════════════════════════════
# MATCHING ENDPOINTS (Client only)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/match")
async def match_freelancers(skills: str = "", user=Depends(require_client)):
    """Find Top 5 matches. Project client_id is set to the logged-in client's user id."""
    required_skills = [s.strip() for s in skills.split(",")] if skills else []

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            skills_json = json.dumps(required_skills)

            project_id = await conn.fetchval(
                "INSERT INTO projects (client_id, title, required_skills) VALUES ($1, 'Auto-matched Project', $2::jsonb) RETURNING id",
                user["id"], skills_json
            )

            # Exclude freelancers on Redis cooldown
            all_keys = redis_client.keys("cooldown:*")
            cooling_ids = [int(k.split(':')[1]) for k in all_keys if redis_client.ttl(k) > 0]

            query = """
                SELECT id, name, skills, rating, status,
                       last_assigned_at::text as last_assigned_at
                FROM freelancers
                WHERE status = 'idle'
            """
            args = []

            if cooling_ids:
                placeholders = ','.join(str(fid) for fid in cooling_ids)
                query += f" AND id NOT IN ({placeholders})"

            if required_skills:
                query += f" AND skills @> ${len(args)+1}::jsonb"
                args.append(skills_json)

            query += " ORDER BY last_assigned_at ASC LIMIT 5"

            records = await conn.fetch(query, *args)
            results = [dict(r) for r in records]

            # Reserve spots as 'matched'
            for res in results:
                await conn.execute(
                    "INSERT INTO dispatch_logs (project_id, freelancer_id, status) VALUES ($1, $2, 'matched')",
                    project_id, res["id"]
                )
                res["project_id"] = project_id
                res["status"] = "idle"

    return {"project_id": project_id, "matches": results}


@app.post("/api/invite")
async def invite_freelancer(req: InviteRequest, user=Depends(require_client)):
    """Client explicitly invites a freelancer for a project."""
    async with db_pool.acquire() as conn:
        existing_id = await conn.fetchval(
            "SELECT id FROM dispatch_logs WHERE project_id = $1 AND freelancer_id = $2",
            req.project_id, req.freelancer_id
        )
        try:
            if existing_id:
                await conn.execute(
                    "UPDATE dispatch_logs SET status = 'invited', updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                    existing_id
                )
            else:
                await conn.execute(
                    "INSERT INTO dispatch_logs (project_id, freelancer_id, status) VALUES ($1, $2, 'invited')",
                    req.project_id, req.freelancer_id
                )
            return {"success": True, "message": "Invited successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}


@app.post("/api/respond-invitation")
async def respond_invitation(req: RespondRequest, user=Depends(current_user)):
    """Freelancer accepts or declines. On decline, auto-replace with next available."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            new_status = "accepted" if req.action == "accept" else "declined"
            await conn.execute(
                "UPDATE dispatch_logs SET status = $1, updated_at = CURRENT_TIMESTAMP WHERE project_id = $2 AND freelancer_id = $3",
                new_status, req.project_id, req.freelancer_id
            )

            if req.action == "accept":
                await conn.execute(
                    "UPDATE freelancers SET status = 'working', last_assigned_at = CURRENT_TIMESTAMP WHERE id = $1",
                    req.freelancer_id
                )
                return {"success": True, "action": "accept", "freelancer_id": req.freelancer_id}

            elif req.action == "decline":
                # Set Redis cooldown
                redis_client.setex(f"cooldown:{req.freelancer_id}", COOLDOWN_TTL, req.project_id)

                skills_json = await conn.fetchval("SELECT required_skills FROM projects WHERE id = $1", req.project_id)

                all_keys = redis_client.keys("cooldown:*")
                cooling_ids = [int(k.split(':')[1]) for k in all_keys if redis_client.ttl(k) > 0]

                next_query = """
                    SELECT id, name, skills, rating, status,
                           last_assigned_at::text as last_assigned_at
                    FROM freelancers
                    WHERE status = 'idle'
                      AND id NOT IN (SELECT freelancer_id FROM dispatch_logs WHERE project_id = $1)
                """
                args = [req.project_id]

                if cooling_ids:
                    placeholders = ','.join(str(fid) for fid in cooling_ids)
                    next_query += f" AND id NOT IN ({placeholders})"

                if skills_json and skills_json != '[]':
                    next_query += " AND skills @> $2::jsonb"
                    args.append(skills_json)

                next_query += " ORDER BY last_assigned_at ASC LIMIT 1"
                new_record = await conn.fetchrow(next_query, *args)

                if new_record:
                    new_f = dict(new_record)
                    new_f["project_id"] = req.project_id
                    new_f["status"] = "idle"
                    await conn.execute(
                        "INSERT INTO dispatch_logs (project_id, freelancer_id, status) VALUES ($1, $2, 'matched')",
                        req.project_id, new_f["id"]
                    )
                    return {"success": True, "action": "decline", "replaced_with": new_f}
                else:
                    return {"success": True, "action": "decline", "replaced_with": None}


@app.post("/api/simulate-random-decline")
async def simulate_random_decline(req: SimulateDeclineRequest, user=Depends(require_client)):
    async with db_pool.acquire() as conn:
        records = await conn.fetch(
            "SELECT freelancer_id FROM dispatch_logs WHERE project_id = $1 AND status = 'invited'",
            req.project_id
        )
    if not records:
        raise HTTPException(status_code=400, detail="No invited freelancers found for this project.")
    chosen = random.choice(records)
    fake_req = RespondRequest(freelancer_id=chosen["freelancer_id"], project_id=req.project_id, action="decline")
    return await respond_invitation(fake_req, user)


@app.post("/api/select")
async def select_freelancer(req: SelectRequest, user=Depends(require_client)):
    """Backwards-compatible endpoint."""
    fake_req = RespondRequest(freelancer_id=req.freelancer_id, project_id=req.project_id or 1, action="accept")
    return await respond_invitation(fake_req, user)


@app.post("/api/reset-cooling")
async def reset_cooling(freelancer_id: int, user=Depends(current_user)):
    """Prototype: reset a freelancer back to idle."""
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE freelancers SET status = 'idle' WHERE id = $1", freelancer_id)
    return {"success": True}

import os
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg
import redis
from dotenv import load_dotenv

load_dotenv()

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rotafive")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Connection pool
db_pool = None
redis_client = None

# Cooldown duration in seconds (30 minutes)
COOLDOWN_TTL = 1800

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

# Allow CORS for Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Models for Input validation
class SelectRequest(BaseModel):
    freelancer_id: int
    project_id: Optional[int] = None

class RespondRequest(BaseModel):
    freelancer_id: int
    project_id: int
    action: str  # 'accept' or 'decline'

class SimulateDeclineRequest(BaseModel):
    project_id: int


@app.get("/api/freelancers")
async def get_all_freelancers():
    """
    Returns the whole list of freelancers for the Queue View,
    including a 'cooling' flag from Redis if there's an active cooldown.
    """
    query = """
    SELECT 
        id, name, skills, rating, status, 
        last_assigned_at::text as last_assigned_at 
    FROM freelancers
    ORDER BY 
        CASE WHEN status = 'working' THEN 1 ELSE 0 END,
        last_assigned_at ASC
    """
    async with db_pool.acquire() as connection:
        records = await connection.fetch(query)
        result = [dict(record) for record in records]
        
        # Inject 'cooling' status from Redis for each freelancer
        for freelancer in result:
            cooldown_key = f"cooldown:{freelancer['id']}"
            ttl = redis_client.ttl(cooldown_key)
            if ttl > 0:
                freelancer['cooling'] = True
                freelancer['cooldown_ttl'] = ttl
            else:
                freelancer['cooling'] = False
                freelancer['cooldown_ttl'] = 0
        
        return result

@app.get("/api/invitations")
async def get_invitations():
    """
    Returns all currently pending 'invited' records.
    """
    query = """
        SELECT 
            d.project_id, d.freelancer_id, 
            f.name as freelancer_name, 
            p.title as project_title, 
            d.created_at::text as created_at
        FROM dispatch_logs d
        JOIN freelancers f ON d.freelancer_id = f.id
        JOIN projects p ON d.project_id = p.id
        WHERE d.status = 'invited'
        ORDER BY d.created_at DESC
    """
    async with db_pool.acquire() as connection:
        records = await connection.fetch(query)
        return [dict(record) for record in records]


@app.get("/api/match")
async def match_freelancers(skills: str = ""):
    """
    Find Top 5 matches based on skills, create a project, and invite them.
    skills (str): comma-separated string, e.g. "Vue,Tailwind"
    """
    required_skills = [s.strip() for s in skills.split(",")] if skills else []
    
    async with db_pool.acquire() as connection:
        async with connection.transaction():
            import json
            skills_json = json.dumps(required_skills)
            
            # Create a mock project for this match session
            project_query = """
                INSERT INTO projects (title, required_skills) 
                VALUES ('Auto-matched Project', $1::jsonb) 
                RETURNING id
            """
            project_id = await connection.fetchval(project_query, skills_json)
            
            # Base query for rotation matching
            # Also exclude freelancers who are under a Redis cooldown
            query = """
                SELECT 
                    id, name, skills, rating, status, 
                    last_assigned_at::text as last_assigned_at 
                FROM freelancers
                WHERE status = 'idle'
            """
            args = []
            
            # Get all freelancer IDs with an active Redis cooldown, and exclude them
            all_keys = redis_client.keys("cooldown:*")
            cooling_ids = [int(k.split(':')[1]) for k in all_keys if redis_client.ttl(k) > 0]
            
            if cooling_ids:
                # Append to query to exclude cooling IDs
                # We do this safely by building a NOT IN clause
                placeholders = ','.join(str(fid) for fid in cooling_ids)
                query += f" AND id NOT IN ({placeholders})"
            
            if required_skills:
                query += f" AND skills @> ${len(args)+1}::jsonb"
                args.append(skills_json)
                
            query += " ORDER BY last_assigned_at ASC LIMIT 5"
            
            records = await connection.fetch(query, *args)
            results = [dict(record) for record in records]
            
            # Reserve their spots in the queue as 'matched'
            if results:
                insert_log_query = """
                    INSERT INTO dispatch_logs (project_id, freelancer_id, status)
                    VALUES ($1, $2, 'matched')
                """
                for res in results:
                    await connection.execute(insert_log_query, project_id, res['id'])

            # Add project_id to the results so the frontend knows what project they belong to
            for res in results:
                res['project_id'] = project_id
                res['status'] = 'idle'  # Ensure the UI knows they are idle initially
                
            return {"project_id": project_id, "matches": results}

class InviteRequest(BaseModel):
    freelancer_id: int
    project_id: int

@app.post("/api/invite")
async def invite_freelancer(req: InviteRequest):
    """
    Client explicitly invites a selected freelancer.
    Creates a dispatch_log entry.
    """
    async with db_pool.acquire() as connection:
        query_check = "SELECT id FROM dispatch_logs WHERE project_id = $1 AND freelancer_id = $2"
        existing_id = await connection.fetchval(query_check, req.project_id, req.freelancer_id)
        
        try:
            if existing_id:
                # Update existing matched record
                update_query = "UPDATE dispatch_logs SET status = 'invited', updated_at = CURRENT_TIMESTAMP WHERE id = $1"
                await connection.execute(update_query, existing_id)
            else:
                # Fallback
                insert_query = """
                    INSERT INTO dispatch_logs (project_id, freelancer_id, status)
                    VALUES ($1, $2, 'invited')
                """
                await connection.execute(insert_query, req.project_id, req.freelancer_id)
            
            return {"success": True, "message": "Invited successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}

@app.post("/api/respond-invitation")
async def respond_invitation(req: RespondRequest):
    """
    Freelancer accepts or declines an invitation.
    If decline, auto-replace with the next available idle freelancer.
    """
    async with db_pool.acquire() as connection:
        async with connection.transaction():
            # Update the log
            new_status = 'accepted' if req.action == 'accept' else 'declined'
            await connection.execute(
                "UPDATE dispatch_logs SET status = $1, updated_at = CURRENT_TIMESTAMP WHERE project_id = $2 AND freelancer_id = $3",
                new_status, req.project_id, req.freelancer_id
            )
            
            if req.action == 'accept':
                # Update freelancer to working
                update_query = """
                    UPDATE freelancers
                    SET status = 'working', last_assigned_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                """
                await connection.execute(update_query, req.freelancer_id)
                return {"success": True, "action": "accept", "freelancer_id": req.freelancer_id}
                
            elif req.action == 'decline':
                # Set Redis cooldown for this freelancer (30 minutes)
                cooldown_key = f"cooldown:{req.freelancer_id}"
                redis_client.setex(cooldown_key, COOLDOWN_TTL, req.project_id)
                
                # Auto-replace logic
                # Get the required skills for this project first
                skills_json = await connection.fetchval("SELECT required_skills FROM projects WHERE id = $1", req.project_id)
                
                # Get all freelancer IDs with an active Redis cooldown (including this one just set)
                all_keys = redis_client.keys("cooldown:*")
                cooling_ids = [int(k.split(':')[1]) for k in all_keys if redis_client.ttl(k) > 0]
                
                # Find the next best freelancer who is idle AND hasn't been matched to this project
                next_in_line_query = """
                    SELECT 
                        id, name, skills, rating, status, 
                        last_assigned_at::text as last_assigned_at 
                    FROM freelancers
                    WHERE status = 'idle'
                      AND id NOT IN (SELECT freelancer_id FROM dispatch_logs WHERE project_id = $1)
                """
                args = [req.project_id]
                
                # Exclude anyone under cooldown
                if cooling_ids:
                    placeholders = ','.join(str(fid) for fid in cooling_ids)
                    next_in_line_query += f" AND id NOT IN ({placeholders})"
                
                # We need to filter by skills if the project required them
                if skills_json and skills_json != '[]':
                    next_in_line_query += " AND skills @> $2::jsonb"
                    args.append(skills_json)
                    
                next_in_line_query += " ORDER BY last_assigned_at ASC LIMIT 1"
                
                new_record = await connection.fetchrow(next_in_line_query, *args)
                
                if new_record:
                    new_freelancer = dict(new_record)
                    new_freelancer['project_id'] = req.project_id
                    new_freelancer['status'] = 'idle'  # Ensure frontend sees them as idle
                    
                    # Reserve this spot so they don't get selected again!
                    # The client must click "Send Job Invite" manually to change their status to 'invited'.
                    await connection.execute(
                        "INSERT INTO dispatch_logs (project_id, freelancer_id, status) VALUES ($1, $2, 'matched')",
                        req.project_id, new_freelancer['id']
                    )
                    
                    return {"success": True, "action": "decline", "replaced_with": new_freelancer}
                else:
                    return {"success": True, "action": "decline", "replaced_with": None, "message": "No more available freelancers."}

@app.post("/api/simulate-random-decline")
async def simulate_random_decline(req: SimulateDeclineRequest):
    """
    Simulates a random freelancer declining the invitation for a project.
    """
    async with db_pool.acquire() as connection:
        # Find all currently 'invited' freelancers for this project
        query = """
            SELECT freelancer_id FROM dispatch_logs
            WHERE project_id = $1 AND status = 'invited'
        """
        records = await connection.fetch(query, req.project_id)
        
        if not records:
            raise HTTPException(status_code=400, detail="No invited freelancers found for this project.")
            
        import random
        chosen = random.choice(records)
        freelancer_id = chosen['freelancer_id']
        
    # Re-use the respond_invitation logic by calling it directly
    fake_req = RespondRequest(freelancer_id=freelancer_id, project_id=req.project_id, action="decline")
    return await respond_invitation(fake_req)

@app.post("/api/select")
async def select_freelancer(req: SelectRequest):
    """
    For backwards compatibility. You could route this through respond-invitation accept.
    """
    fake_req = RespondRequest(freelancer_id=req.freelancer_id, project_id=req.project_id or 1, action="accept")
    return await respond_invitation(fake_req)

@app.post("/api/reset-cooling")
async def reset_cooling(freelancer_id: int):
    """
    Simulates a worker finishing the job and returning to the queue.
    For prototype testing purposes.
    """
    query = "UPDATE freelancers SET status = 'idle' WHERE id = $1"
    async with db_pool.acquire() as connection:
        await connection.execute(query, freelancer_id)
    return {"success": True}

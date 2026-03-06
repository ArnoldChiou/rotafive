import os
import asyncio
import asyncpg
import json
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rotafive")

mock_freelancers = [
  { "name": "Alice Smith", "skills": ["Vue", "JavaScript", "Tailwind"], "rating": 4.8, "status": "idle" },
  { "name": "Bob Jones", "skills": ["Python", "Django", "React"], "rating": 4.5, "status": "idle" },
  { "name": "Charlie Brown", "skills": ["Design", "Figma", "UI/UX"], "rating": 5.0, "status": "working" },
  { "name": "Diana Prince", "skills": ["Vue", "TypeScript", "Node.js"], "rating": 4.9, "status": "idle" },
  { "name": "Evan Wright", "skills": ["Python", "Data Science", "SQL"], "rating": 4.7, "status": "idle" },
  { "name": "Fiona Gallagher", "skills": ["Design", "Illustration", "Figma"], "rating": 4.6, "status": "idle" },
  { "name": "George Miller", "skills": ["Vue", "CSS", "Tailwind"], "rating": 4.3, "status": "idle" },
  { "name": "Hannah Lee", "skills": ["React", "Next.js", "JavaScript"], "rating": 4.8, "status": "cooling" },
  { "name": "Ian Fleming", "skills": ["Python", "Flask", "Docker"], "rating": 4.4, "status": "idle" },
  { "name": "Julia Roberts", "skills": ["Design", "Web Design", "Figma"], "rating": 4.9, "status": "idle" },
]

async def seed():
    conn = await asyncpg.connect(DATABASE_URL)
    print("Connected to database...")
    
    # Ensure tables exist (we assume init.sql was mapped via docker-compose, but just in case, we could create here, but let's depend on docker-compose)
    # Check if table exists
    try:
        await conn.execute("SELECT 1 FROM freelancers LIMIT 1")
    except asyncpg.exceptions.UndefinedTableError:
        print("Error: Table 'freelancers' does not exist. Did the init.sql run in Docker?")
        await conn.close()
        return

    # Clear existing
    await conn.execute("TRUNCATE freelancers RESTART IDENTITY CASCADE")
    
    # Insert mock data
    print("Inserting 10 mock text freelancers...")
    query = """
    INSERT INTO freelancers (name, skills, rating, status, last_assigned_at) 
    VALUES ($1, $2::jsonb, $3, $4, NOW() - (random() * interval '30 days'))
    """
    
    # We use random dates in the past 30 days to scatter the rotation queue randomly
    for idx, f in enumerate(mock_freelancers):
        await conn.execute(
            query, 
            f["name"], 
            json.dumps(f["skills"]), 
            f["rating"], 
            f["status"]
        )
        
    print("Seed completed successfully!")
    await conn.close()
    
if __name__ == "__main__":
    asyncio.run(seed())

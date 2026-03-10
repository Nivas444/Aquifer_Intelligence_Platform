from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
import sqlite3, hashlib, jwt, datetime
from database import get_db
from typing import Optional

router = APIRouter()
SECRET_KEY = "aquifer_secret_key_2024"

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str
    organization: str = ""
    role: str = "viewer"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(user_id: int, email: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

@router.post("/login")
def login(req: LoginRequest, db: sqlite3.Connection = Depends(get_db)):
    pw_hash = hash_password(req.password)
    user = db.execute(
        "SELECT * FROM users WHERE email=? AND password_hash=? AND is_active=1",
        (req.email, pw_hash)
    ).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"], user["email"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "role": user["role"],
            "organization": user["organization"]
        }
    }

@router.post("/register")
def register(req: RegisterRequest, db: sqlite3.Connection = Depends(get_db)):
    if not req.email or not req.password or not req.username:
        raise HTTPException(status_code=400, detail="Email, username and password are required")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    existing = db.execute("SELECT id FROM users WHERE email=?", (req.email,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    pw_hash = hash_password(req.password)
    cursor = db.execute(
        "INSERT INTO users (email, username, password_hash, organization, role) VALUES (?,?,?,?,?)",
        (req.email, req.username, pw_hash, req.organization, req.role)
    )
    db.commit()
    user_id = cursor.lastrowid
    token = create_token(user_id, req.email, req.role)
    return {
        "message": "Registration successful",
        "token": token,
        "user": {
            "id": user_id,
            "email": req.email,
            "username": req.username,
            "role": req.role,
            "organization": req.organization
        }
    }

@router.get("/me")
def get_me(authorization: Optional[str] = Header(None), db: sqlite3.Connection = Depends(get_db)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No token provided")
    try:
        token = authorization.replace("Bearer ", "").strip()
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user = db.execute("SELECT * FROM users WHERE id=?", (payload["user_id"],)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": user["id"], "email": user["email"], "username": user["username"],
                "role": user["role"], "organization": user["organization"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/users")
def get_users(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, email, username, role, organization, created_at, is_active FROM users ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]
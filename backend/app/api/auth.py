"""認証 API"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import jwt
import bcrypt
import os

from app.db.models import get_db, User

router = APIRouter()
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8時間

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

def create_token(data: dict):
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "認証に失敗しました")
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(401, "ユーザーが見つかりません")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "セッションが期限切れです")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "無効なトークンです")

def require_admin(current_user: User = Depends(get_current_user)):
    """管理者ロールを要求する依存関係。管理者以外は 403 を返す。"""
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "この操作には管理者権限が必要です")
    return current_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username, User.is_active == True).first()
    if not user:
        raise HTTPException(401, "メールアドレスまたはパスワードが間違っています")
    try:
        if not bcrypt.checkpw(form_data.password.encode(), user.hashed_password.encode()):
            raise HTTPException(401, "メールアドレスまたはパスワードが間違っています")
    except Exception:
        raise HTTPException(401, "認証に失敗しました")
    token = create_token({"sub": str(user.id), "email": user.email, "role": user.role})
    return {
        "access_token": token, "token_type": "bearer",
        "user": {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role}
    }

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": str(current_user.id), "email": current_user.email,
            "full_name": current_user.full_name, "role": current_user.role}

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "staff"

@router.post("/users", status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db),
                _admin: User = Depends(require_admin)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "このメールアドレスは既に使用されています")
    hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    user = User(email=data.email, hashed_password=hashed, full_name=data.full_name, role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role}


# =============================================
# ユーザー一覧・管理（管理者用）
# =============================================
@router.get("/users")
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    users = db.query(User).filter(User.is_active == True).order_by(User.created_at).all()
    return [{"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role,
             "is_active": u.is_active, "created_at": u.created_at.isoformat() if u.created_at else None}
            for u in users]

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

@router.put("/users/{user_id}")
def update_user(user_id: str, data: UserUpdate, db: Session = Depends(get_db),
                _admin: User = Depends(require_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404)
    if data.email: u.email = data.email
    if data.full_name: u.full_name = data.full_name
    if data.role: u.role = data.role
    if data.password:
        u.hashed_password = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    db.commit()
    return {"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role}

@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, db: Session = Depends(get_db),
                _admin: User = Depends(require_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404)
    u.is_active = False
    db.commit()

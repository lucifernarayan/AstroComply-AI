from hashlib import sha256
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.database.db import engine
from backend.security.auth import current_user, hash_password, verify_password, issue_session

router = APIRouter()

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

@router.post('/register', status_code=201)
def register(payload: Credentials):
    try:
        with engine.begin() as connection:
            user_id = connection.execute(text('INSERT INTO users(email,password_hash) VALUES (:email,:hash) RETURNING id'),
                {'email': str(payload.email).lower(), 'hash': hash_password(payload.password)}).scalar_one()
    except IntegrityError:
        raise HTTPException(409, 'Account already exists')
    return {'access_token': issue_session(user_id), 'token_type': 'bearer'}

@router.post('/login')
def login(payload: Credentials):
    with engine.connect() as connection:
        user = connection.execute(text('SELECT id,password_hash FROM users WHERE email=:email'),
            {'email': str(payload.email).lower()}).mappings().first()
    if not user or not verify_password(payload.password, user['password_hash']):
        raise HTTPException(401, 'Invalid credentials')
    return {'access_token': issue_session(user['id']), 'token_type': 'bearer'}

@router.get('/me')
def me(user: dict = Depends(current_user)):
    return user

@router.post('/logout', status_code=204)
def logout(authorization: str | None = Header(default=None), user: dict = Depends(current_user)):
    token_hash = sha256(authorization[7:].encode()).hexdigest()
    with engine.begin() as connection:
        connection.execute(text('DELETE FROM sessions WHERE token_hash=:hash AND user_id=:user'),
            {'hash': token_hash, 'user': user['id']})

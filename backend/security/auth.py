"""Opaque database-backed sessions and organization membership checks."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy import text
from backend.database.db import engine

SESSION_DAYS = 7


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f'scrypt$16384$8$1${salt.hex()}${digest.hex()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split('$')
        if algorithm != 'scrypt':
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def issue_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with engine.begin() as connection:
        connection.execute(text('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (:hash,:user,:expiry)'),
            {'hash': hashlib.sha256(token.encode()).hexdigest(), 'user': user_id,
             'expiry': datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)})
    return token


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Authentication required')
    token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT u.id,u.email FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token_hash=:hash AND s.expires_at>now()'''), {'hash': token_hash}).mappings().first()
    if not row:
        raise HTTPException(401, 'Session expired or invalid')
    return dict(row)


def membership(organization_id: int, user: dict = Depends(current_user)) -> dict:
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT role FROM memberships
            WHERE user_id=:user AND organization_id=:org'''),
            {'user': user['id'], 'org': organization_id}).mappings().first()
    if not row:
        raise HTTPException(404, 'Workspace not found')
    return {'organization_id': organization_id, 'user_id': user['id'], 'role': row['role']}


def active_membership(x_organization_id: int = Header(...), user: dict = Depends(current_user)) -> dict:
    return membership(x_organization_id, user)


def require_role(member: dict, allowed: set[str]) -> None:
    if member['role'] not in allowed:
        raise HTTPException(403, 'Insufficient workspace permission')


def audit(connection, member: dict, action: str, target_type: str, target_id: int | None) -> None:
    connection.execute(text('''INSERT INTO audit_events(organization_id,user_id,action,target_type,target_id)
        VALUES (:org,:user,:action,:type,:target)'''),
        {'org': member['organization_id'], 'user': member['user_id'], 'action': action,
         'type': target_type, 'target': target_id})

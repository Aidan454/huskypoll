"""Account roles (admins only): admin, instructor, ta, student, guest."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from huskypoll_db import services as svc
from huskypoll_db.models import User
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import schemas as s
from ..deps import current_user, get_db, require_admin
from ..serializers import user_out

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[s.UserOut], summary="Find accounts (admins)")
def list_users(q: Optional[str] = None, role: Optional[s.UserRole] = None, limit: int = 100,
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_admin(user)
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(User.net_id.like(like), User.email.like(like),
                                User.first_name.ilike(like), User.last_name.ilike(like)))
    users = db.scalars(query.order_by(User.last_name, User.first_name, User.net_id).limit(min(limit, 500)))
    return [user_out(u) for u in users]


@router.patch("/users/{user_id}/role", response_model=s.UserOut,
              summary="Change someone's account role (admins); e.g. make a professor an instructor")
def change_role(user_id: int, body: s.RoleUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    svc.set_role(db, target, body.role, by=user)
    return user_out(target)

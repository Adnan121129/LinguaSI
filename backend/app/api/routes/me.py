from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.auth import ChangePasswordRequest, DeleteAccountRequest, ProfileUpdate, UserOut
from app.schemas.common import Message
from app.services import auth_service, user_service

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut, summary="Current user and learner profile")
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut, summary="Update name, preferences, goals or theme")
def update_me(payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return UserOut.model_validate(user_service.update_profile(db, user, payload))


@router.post("/me/change-password", response_model=Message)
def change_password(payload: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Message:
    auth_service.change_password(db, user, current_password=payload.current_password, new_password=payload.new_password)
    return Message(message="Password changed. Other devices have been signed out.")


@router.post("/me/delete", response_model=Message, summary="Permanently delete the account and all learning data")
def delete_me(payload: DeleteAccountRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Message:
    user_service.delete_account(db, user, payload.password)
    return Message(message="Your account and learning data have been deleted.")

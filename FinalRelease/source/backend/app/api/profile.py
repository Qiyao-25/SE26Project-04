from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import ensure_same_user, require_current_user
from app.core.database import get_db
from app.schema.auth import AuthUser
from app.schema.common import ApiResponse
from app.schema.papers import DictionaryEntry, UserProfileData, UserProfileUpdate
from app.service.profile import clear_dictionary, get_dictionary, get_profile, update_profile


router = APIRouter(prefix="/api/learning", tags=["learning-profile"])


def db_session(request: Request):
    yield from get_db(request.app.state.engine)


@router.get("/profile", response_model=ApiResponse[UserProfileData], summary="读取用户阅读画像")
def profile(request: Request, user_id: str = Query(min_length=1, max_length=128), current_user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    ensure_same_user(user_id, current_user)
    return ApiResponse(data=get_profile(db, user_id), request_id=request.state.request_id)


@router.put("/profile", response_model=ApiResponse[UserProfileData], summary="保存用户阅读画像")
def profile_update(user_id: str, payload: UserProfileUpdate, request: Request, current_user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    ensure_same_user(user_id, current_user)
    return ApiResponse(data=update_profile(db, user_id, payload), request_id=request.state.request_id)


@router.get("/dictionary", response_model=ApiResponse[list[DictionaryEntry]], summary="读取个人概念词典")
def dictionary(request: Request, user_id: str = Query(min_length=1, max_length=128), current_user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    ensure_same_user(user_id, current_user)
    return ApiResponse(data=get_dictionary(db, user_id), request_id=request.state.request_id)


@router.delete("/dictionary", response_model=ApiResponse[dict], summary="清空个人概念词典（全部词条）")
def dictionary_clear(request: Request, user_id: str = Query(min_length=1, max_length=128), current_user: AuthUser = Depends(require_current_user), db: Session = Depends(db_session)):
    ensure_same_user(user_id, current_user)
    data = clear_dictionary(db, user_id)
    return ApiResponse(data=data, request_id=request.state.request_id)

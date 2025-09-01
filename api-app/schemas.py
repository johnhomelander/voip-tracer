# api-app/schemas.py
from fastapi_users import schemas
from typing import Optional

class UserRead(schemas.BaseUser[int]):
    username: str

class UserCreate(schemas.BaseUserCreate):
    username: str

class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None

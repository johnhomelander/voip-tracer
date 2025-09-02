# api-app/auth.py
import os
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import BaseUserManager, IntegerIDMixin, exceptions, models
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase

import sqlalchemy
from sqlalchemy import func, select

from db import User, get_user_db
from schemas import UserCreate

SECRET = os.getenv("SECRET_KEY")

class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} ({user.username}) has registered.")

    # This handles the incompatibility with the registration router.
    async def create(
        self,
        user_create: UserCreate,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> User:
        await self.validate_password(user_create.password, user_create)

        existing_user_by_email = await self.user_db.get_by_email(user_create.email)
        if existing_user_by_email is not None:
            raise exceptions.UserAlreadyExists()
        
        # Check for existing username
        existing_user_by_username = await self.get_by_username(user_create.username)
        if existing_user_by_username is not None:
            raise exceptions.UserAlreadyExists()

        user_dict = user_create.create_update_dict()
        password = user_dict.pop("password")
        user_dict["hashed_password"] = self.password_helper.hash(password)
        
        created_user = await self.user_db.create(user_dict)

        await self.on_after_register(created_user, request)

        return created_user

    # This is the new method to find a user by their username.
    async def get_by_username(self, username: str) -> Optional[User]:
        statement = sqlalchemy.select(self.user_db.user_table).where(
            sqlalchemy.func.lower(self.user_db.user_table.username) == sqlalchemy.func.lower(username)
        )
        results = await self.user_db.session.execute(statement)
        return results.scalar_one_or_none()

    # This is the new method to allow login with either username or email.
    async def authenticate(
        self, credentials: OAuth2PasswordRequestForm
    ) -> Optional[User]:
        username_or_email = credentials.username
        
        if "@" in username_or_email:
            user = await self.get_by_email(username_or_email)
        else:
            user = await self.get_by_username(username_or_email)

        if user is None:
            self.password_helper.hash(credentials.password)
            return None

        verified, updated_password_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        
        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})

        if not user.is_active:
            raise exceptions.UserInactive()

        return user

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

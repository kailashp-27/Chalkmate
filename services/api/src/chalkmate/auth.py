from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from chalkmate.config import get_settings
from chalkmate.db import get_engine, set_identity
from chalkmate.models import User

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    id: UUID
    email: str


async def authenticate(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Identity:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})
    settings = get_settings()
    try:
        response = await request.app.state.auth_http.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {credentials.credentials}",
                # Validate this bearer token only; never send another user's cookies.
                "Cookie": "",
            },
        )
        if response.status_code in (401, 403):
            raise HTTPException(401, "Your session expired. Sign in again.")
        if response.status_code != 200:
            raise HTTPException(503, "Authentication is temporarily unavailable")
        user = response.json()
        if not user.get("email") or not user.get("email_confirmed_at"):
            raise HTTPException(403, "Verify your email before using the workspace")
        return Identity(UUID(user["id"]), user["email"].lower())
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Authentication is temporarily unavailable") from exc


def database(identity: Annotated[Identity, Depends(authenticate)]):
    with Session(get_engine(), expire_on_commit=False) as session, session.begin():
        set_identity(session, str(identity.id), identity.email)
        # Polling and parallel evidence reads should not take an UPDATE lock on the user.
        # Upsert only for a new account or a verified email change.
        existing_email = session.scalar(select(User.email).where(User.id == identity.id))
        if existing_email != identity.email:
            session.execute(
                insert(User)
                .values(id=identity.id, email=identity.email)
                .on_conflict_do_update(index_elements=[User.id], set_={"email": identity.email})
            )
        yield session


CurrentUser = Annotated[Identity, Depends(authenticate)]
Database = Annotated[Session, Depends(database, scope="function")]

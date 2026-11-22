"""FastAPI dependencies. Everything comes from app.state, so each test gets its own app."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .ai import Auditor

WORKSPACES = ("demo", "personal")


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


def get_workspace(x_workspace: Annotated[str | None, Header()] = None) -> str:
    workspace = (x_workspace or "demo").strip().lower()
    if workspace not in WORKSPACES:
        raise HTTPException(400, f"Unknown workspace {workspace!r}; use one of {WORKSPACES}.")
    return workspace


def get_auditor(request: Request) -> Auditor:
    return request.app.state.auditor


DbDep = Annotated[Session, Depends(get_db)]
WorkspaceDep = Annotated[str, Depends(get_workspace)]
AuditorDep = Annotated[Auditor, Depends(get_auditor)]

"""Bearer-token auth with role attribution.

Roles:
- task2: read-only /query
- task3: read-only /query
- admin: full surface including /escalations/{id}/resolve (human approval gate)

Missing/unknown token → 401. Wrong role for endpoint → 403.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from .config import ServiceConfig


ROLE_TASK2 = "task2"
ROLE_TASK3 = "task3"
ROLE_ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    role: str
    token_id: str  # role name; used as expert_id in escalations


def _token_map(cfg: ServiceConfig) -> dict[str, str]:
    m: dict[str, str] = {}
    if cfg.token_task2:
        m[cfg.token_task2] = ROLE_TASK2
    if cfg.token_task3:
        m[cfg.token_task3] = ROLE_TASK3
    if cfg.token_admin:
        m[cfg.token_admin] = ROLE_ADMIN
    return m


def get_config(request: Request) -> ServiceConfig:
    return request.app.state.config


def require_any_token(
    request: Request,
    cfg: ServiceConfig = Depends(get_config),
) -> Principal:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = auth[7:].strip()
    role = _token_map(cfg).get(token)
    if role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")
    return Principal(role=role, token_id=role)


def require_admin(principal: Principal = Depends(require_any_token)) -> Principal:
    if principal.role != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin token required")
    return principal

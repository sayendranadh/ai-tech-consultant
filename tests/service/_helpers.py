"""Plain helper module — avoids importing from conftest (which pytest loads specially)."""


def hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

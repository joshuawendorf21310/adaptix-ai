from __future__ import annotations

from fastapi import APIRouter


def build_adaptix_domain_router(*, module: str, tag: str, prefix: str, legacy_routes: list[str], legacy_modules: list[str]) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("")
    async def domain_info() -> dict[str, object]:
        return {"module": module, "tag": tag, "legacy_routes": legacy_routes, "legacy_modules": legacy_modules, "status": "standalone-shell-ready"}

    return router

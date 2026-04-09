"""Adaptix AI alias router."""
from core_app.api.adaptix_domain_router_common import build_adaptix_domain_router

router = build_adaptix_domain_router(
    module="ai",
    tag="Adaptix AI",
    prefix="/api/ai",
    legacy_routes=["/api/v1/ai", "/api/v1/fire/ai", "/api/v1/founder/copilot"],
    legacy_modules=["ai_router", "fire_ai_router", "founder_copilot_router"],
)

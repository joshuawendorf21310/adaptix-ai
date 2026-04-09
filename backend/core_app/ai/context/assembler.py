from __future__ import annotations

from typing import Any


class ContextAssembler:
    """Normalizes module task context before prompt construction."""

    async def build(
        self,
        *,
        module: str,
        task_type: str,
        context: dict[str, Any],
        actor_role: str,
    ) -> dict[str, Any]:
        base = {
            "module": module,
            "task_type": task_type,
            "actor_role": actor_role,
        }

        if module == "command":
            return {**base, **self._build_command_context(context)}
        if module == "field":
            return {**base, **self._build_field_context(context)}
        if module == "flow":
            return {**base, **self._build_flow_context(context)}
        if module == "pulse":
            return {**base, **self._build_pulse_context(context)}
        if module == "air":
            return {**base, **self._build_air_context(context)}
        if module == "interop":
            return {**base, **self._build_interop_context(context)}
        if module == "insight":
            return {**base, **self._build_insight_context(context)}

        return {**base, **context}

    @staticmethod
    def _truncate(value: Any, max_len: int = 4000) -> Any:
        if isinstance(value, str) and len(value) > max_len:
            return value[:max_len]
        return value

    def _normalize_dict(self, context: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in context.items():
            cleaned[str(key)] = self._truncate(value)
        return cleaned

    def _build_command_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_dict(context)

    def _build_field_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_dict(context)

    def _build_flow_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_dict(context)

    def _build_pulse_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_dict(context)

    def _build_air_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_dict(context)

    def _build_interop_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_dict(context)

    def _build_insight_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_dict(context)

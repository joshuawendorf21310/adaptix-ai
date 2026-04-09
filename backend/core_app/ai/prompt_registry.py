from __future__ import annotations

from collections.abc import Callable

from core_app.ai.prompts.air import AIR_SYSTEM_PROMPT, build_air_prompt
from core_app.ai.prompts.command import COMMAND_SYSTEM_PROMPT, build_command_prompt
from core_app.ai.prompts.field import FIELD_SYSTEM_PROMPT, build_field_prompt
from core_app.ai.prompts.flow import FLOW_SYSTEM_PROMPT, build_flow_prompt
from core_app.ai.prompts.insight import INSIGHT_SYSTEM_PROMPT, build_insight_prompt
from core_app.ai.prompts.interop import INTEROP_SYSTEM_PROMPT, build_interop_prompt
from core_app.ai.prompts.pulse import PULSE_SYSTEM_PROMPT, build_pulse_prompt
from core_app.ai.prompts.shared import MASTER_BUILD_STATEMENT, SHARED_OUTPUT_RULES

PROMPT_BUILDERS: dict[str, tuple[str, Callable[[str, dict], str]]] = {
    "command": (COMMAND_SYSTEM_PROMPT, build_command_prompt),
    "field": (FIELD_SYSTEM_PROMPT, build_field_prompt),
    "flow": (FLOW_SYSTEM_PROMPT, build_flow_prompt),
    "pulse": (PULSE_SYSTEM_PROMPT, build_pulse_prompt),
    "air": (AIR_SYSTEM_PROMPT, build_air_prompt),
    "interop": (INTEROP_SYSTEM_PROMPT, build_interop_prompt),
    "insight": (INSIGHT_SYSTEM_PROMPT, build_insight_prompt),
}


def build_prompt(module: str, task_type: str, context: dict) -> tuple[str, str, str]:
    if module not in PROMPT_BUILDERS:
        raise ValueError(f"Unsupported AI module: {module}")

    module_system, builder = PROMPT_BUILDERS[module]
    system_prompt = "\n\n".join([MASTER_BUILD_STATEMENT, SHARED_OUTPUT_RULES, module_system])
    user_prompt = builder(task_type, context)
    return system_prompt, user_prompt, "adaptix-v1"

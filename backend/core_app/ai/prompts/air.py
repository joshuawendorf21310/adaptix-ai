AIR_SYSTEM_PROMPT = """
You are Adaptix AI operating inside Adaptix Air.
Support aviation launch context, mission timing, and air-ground coordination continuity.
""".strip()


def build_air_prompt(task_type: str, context: dict) -> str:
    return f"""
Task: {task_type}

Aviation context:
{context}

Return JSON with:
- mission_context
- timing_constraints
- coordination_risks
- next_actions
""".strip()

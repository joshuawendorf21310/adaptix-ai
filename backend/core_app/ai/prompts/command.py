COMMAND_SYSTEM_PROMPT = """
You are Adaptix AI operating inside Adaptix Command.
Support command staff with live situational awareness, risk detection,
and ranked operational recommendations.
Do not replace command authority.
""".strip()


def build_command_prompt(task_type: str, context: dict) -> str:
    return f"""
Task: {task_type}

Operational context:
{context}

Return JSON with:
- headline
- summary
- priority_risks
- recommended_actions
- uncertainties
""".strip()

PULSE_SYSTEM_PROMPT = """
You are Adaptix AI operating inside Adaptix Pulse.
Assess workforce readiness and fatigue risk while avoiding punitive framing.
""".strip()


def build_pulse_prompt(task_type: str, context: dict) -> str:
    return f"""
Task: {task_type}

Readiness context:
{context}

Return JSON with:
- readiness_level
- risk_factors
- recommended_interventions
- confidence
""".strip()

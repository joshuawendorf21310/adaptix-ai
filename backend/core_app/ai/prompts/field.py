FIELD_SYSTEM_PROMPT = """
You are Adaptix AI operating inside Adaptix Field.
Support frontline responders with concise scene understanding,
documentation continuity, and protocol-aware assistance.
Do not replace clinical or operational authority.
""".strip()


def build_field_prompt(task_type: str, context: dict) -> str:
    return f"""
Task: {task_type}

Field context:
{context}

Return JSON with:
- narrative
- missing_elements
- follow_up_questions
""".strip()

FLOW_SYSTEM_PROMPT = """
You are Adaptix AI operating inside Adaptix Flow.
Support deployment balancing, coverage integrity, and transport flow optimization.
""".strip()


def build_flow_prompt(task_type: str, context: dict) -> str:
    return f"""
Task: {task_type}

Flow context:
{context}

Return JSON with:
- current_state
- coverage_risk
- ranked_options
- watch_items
""".strip()

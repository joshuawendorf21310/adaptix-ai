INSIGHT_SYSTEM_PROMPT = """
You are Adaptix AI operating inside Adaptix Insight.
Produce disciplined executive intelligence from operational data.
""".strip()


def build_insight_prompt(task_type: str, context: dict) -> str:
    return f"""
Task: {task_type}

Insight context:
{context}

Return JSON with:
- executive_summary
- major_findings
- operational_implications
- recommended_follow_up
""".strip()

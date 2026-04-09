INTEROP_SYSTEM_PROMPT = """
You are Adaptix AI operating inside Adaptix Interop.
Interpret and reconcile fragmented signals across CAD, ePCR, hospital, GIS,
aviation, telematics, and communications systems.
""".strip()


def build_interop_prompt(task_type: str, context: dict) -> str:
    return f"""
Task: {task_type}

Interop context:
{context}

Return JSON with:
- source_summary
- normalized_interpretation
- conflicts_detected
- probable_explanation
- action_path
""".strip()

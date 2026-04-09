from __future__ import annotations

import re
from json import JSONDecodeError, loads
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

PHI_PATTERNS = [
    # SSN — with or without dashes
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b\d{9}\b"),
    # Date of birth — labeled or standalone date formats
    re.compile(
        r"\b(?:DOB|date[\s_]of[\s_]birth|birth[\s_]date)\s*:?\s*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:born|dob)\s*:?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}",
        re.IGNORECASE,
    ),
    # Phone numbers
    re.compile(r"\b(?:\+1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}\b"),
    # Email addresses
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    # Medicare/Medicaid beneficiary numbers (MBIs — 11 char alphanumeric)
    re.compile(r"\b[1-9][A-Z][A-Z0-9][0-9][A-Z][A-Z0-9][0-9][A-Z]{2}[0-9]{2}\b"),
    # NPI numbers
    re.compile(r"\bNPI\s*:?\s*\d{10}\b", re.IGNORECASE),
    # MRN-like identifiers
    re.compile(
        r"\b(?:MRN|mrn|medical[\s_]record[\s_]number)\s*:?\s*[A-Z0-9\-]{4,20}", re.IGNORECASE
    ),
    re.compile(r"\b[A-Z]{2}\d{6,}\b"),
    # Health plan member IDs (common formats)
    re.compile(r"\b[A-Z]{3}\d{9}\b"),
    # IP addresses
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # Zip codes (5+4 format — can be geographic identifier)
    re.compile(r"\b\d{5}-\d{4}\b"),
    # Street addresses
    re.compile(
        r"\b\d{1,5}\s+[A-Z][a-z]+\s+(?:St|Ave|Rd|Blvd|Dr|Ln|Ct|Way|Pl|Circle|Court|Drive|Street|Avenue|Road|Boulevard)\b",
        re.IGNORECASE,
    ),
    # Device serial numbers (common patterns)
    re.compile(r"\b(?:SN|S/N|serial)\s*[:\-]?\s*[A-Z0-9\-]{6,20}\b", re.IGNORECASE),
    # Account numbers
    re.compile(
        r"\b(?:account|acct|account[\s_]no|account[\s_]number)\s*[:#]?\s*\d{4,20}\b", re.IGNORECASE
    ),
    # Credit card numbers (16-digit blocks)
    re.compile(r"\b(?:\d{4}[\s\-]){3}\d{4}\b"),
]

FINANCIAL_MUTATION_PATTERNS = [
    re.compile(
        r"(?:change|modify|update|set|alter)\s+(?:\w+\s+)*(?:amount|payment|charge|fee|balance|rate)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:submit|file|send)\s+(?:claim|bill|invoice)", re.IGNORECASE),
    re.compile(r"(?:delete|remove|void|cancel)\s+(?:claim|payment|charge)", re.IGNORECASE),
]

CLAIM_SUBMISSION_PATTERNS = [
    re.compile(r"submit\s+(?:the\s+)?claim", re.IGNORECASE),
    re.compile(r"file\s+(?:the\s+)?claim", re.IGNORECASE),
    re.compile(r"send\s+(?:the\s+)?(?:837|claim|edi)", re.IGNORECASE),
]


def contains_phi(text: str) -> bool:
    return any(pattern.search(text) for pattern in PHI_PATTERNS)


def contains_financial_mutation(text: str) -> bool:
    return any(pattern.search(text) for pattern in FINANCIAL_MUTATION_PATTERNS)


def contains_claim_submission(text: str) -> bool:
    return any(pattern.search(text) for pattern in CLAIM_SUBMISSION_PATTERNS)


class AiOutput(BaseModel):
    content: str
    task_type: str = "general"
    metadata: dict[str, Any] = {}

    @field_validator("content")
    @classmethod
    def no_phi_in_output(cls, v: str) -> str:
        if contains_phi(v):
            raise ValueError("AI output contains potential PHI — blocked by guardrail")
        return v

    @model_validator(mode="after")
    def no_financial_mutations(self) -> AiOutput:
        if self.task_type in ("billing", "claim", "payment"):
            if contains_financial_mutation(self.content):
                raise ValueError(
                    "AI output contains financial mutation instruction — blocked by guardrail"
                )
            if contains_claim_submission(self.content):
                raise ValueError(
                    "AI output contains autonomous claim submission — blocked by guardrail"
                )
        return self


class AiBillingDraftOutput(BaseModel):
    draft_text: str
    estimated_amount: str | None = None
    appeal_codes: list[str] = []
    requires_human_review: bool = True

    @field_validator("draft_text")
    @classmethod
    def no_phi(cls, v: str) -> str:
        if contains_phi(v):
            raise ValueError("Draft contains potential PHI — use portal links only")
        return v

    @field_validator("estimated_amount")
    @classmethod
    def amount_readonly(cls, v: str | None) -> str | None:
        return v

    @model_validator(mode="after")
    def enforce_human_review(self) -> AiBillingDraftOutput:
        self.requires_human_review = True
        return self


class AiNarrativeOutput(BaseModel):
    narrative_text: str
    confidence: float = 0.0
    requires_review: bool = True

    @model_validator(mode="after")
    def always_require_review(self) -> AiNarrativeOutput:
        self.requires_review = True
        return self


def validate_ai_output(
    content: str | None = None,
    task_type: str = "general",
    *,
    raw_text: str | None = None,
    require_structured_output: bool = False,
) -> AiOutput | dict[str, Any]:
    """Validate AI output in legacy or orchestrated mode.

    Legacy mode (default): returns AiOutput model for existing callers.
    Orchestrator mode: parses and validates structured output dict from raw_text.
    """
    if raw_text is not None or require_structured_output:
        candidate = (raw_text or content or "").strip()
        if not candidate:
            raise ValueError("AI output is empty")

        if not require_structured_output:
            return {"summary": candidate}

        try:
            parsed = loads(candidate)
        except JSONDecodeError as exc:
            raise ValueError("AI output is not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise ValueError("AI output JSON must be an object")

        normalized: dict[str, Any] = {}
        for key, value in parsed.items():
            normalized[str(key)] = value
        return normalized

    return AiOutput(content=content or "", task_type=task_type)


def redact_phi(text: str) -> str:
    """
    Redact PHI from text for logging/debugging purposes.

    Args:
        text: Input text potentially containing PHI

    Returns:
        Text with PHI patterns replaced with [REDACTED]
    """
    redacted = text
    for pattern in PHI_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def detect_hallucination_risk(
    output: str,
    clinical_context: dict | None = None,
) -> str:
    """
    Detect potential hallucinations in AI output.

    Checks for:
    - Overly specific medical values not in input
    - Impossible vital signs (e.g., HR > 300, BP > 300/200)
    - Contradictory statements
    - Unsupported medical claims

    Args:
        output: AI-generated output
        clinical_context: Optional clinical context dict to check against

    Returns:
        Risk level: "low", "medium", or "high"
    """
    risk_indicators = []

    # Check for impossible vital signs
    # Heart rate > 300 or < 20 (outside normal EMS range)
    hr_matches = re.findall(r"HR[:\s]*(?:\w+\s+)*(\d+)", output, re.IGNORECASE)
    for hr in hr_matches:
        if int(hr) > 300 or int(hr) < 20:
            risk_indicators.append("impossible_heart_rate")

    # Blood pressure > 300 systolic or < 40
    bp_matches = re.findall(r"BP[:\s]*(\d+)/(\d+)", output, re.IGNORECASE)
    for systolic, diastolic in bp_matches:
        if int(systolic) > 300 or int(systolic) < 40:
            risk_indicators.append("impossible_blood_pressure")
        if int(diastolic) > 200 or int(diastolic) < 20:
            risk_indicators.append("impossible_blood_pressure")

    # SpO2 > 100%
    spo2_matches = re.findall(r"SpO2[:\s]*(?:\w+\s+)*(\d+)", output, re.IGNORECASE)
    for spo2 in spo2_matches:
        if int(spo2) > 100:
            risk_indicators.append("impossible_spo2")

    # Check for overly specific medical claims
    overly_specific_patterns = [
        r"exactly \d+\.?\d* (?:mg|ml|units)",  # "exactly 2.5 mg"
        r"precisely at \d+:\d+:\d+",  # "precisely at 14:23:45"
        r"CT scan (?:showed|revealed|indicated)",  # EMS doesn't do CT scans
        r"MRI (?:showed|revealed|indicated)",  # EMS doesn't do MRIs
        r"lab results (?:showed|revealed|indicated)",  # EMS rarely has lab results
    ]

    for pattern in overly_specific_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            risk_indicators.append("overly_specific_claim")
            break

    # Check for contradictory statements within output
    # Look for opposing terms in close proximity
    contradictory_pairs = [
        (r"\bconscious\b", r"\bunconscious\b"),
        (r"\bresponsive\b", r"\bunresponsive\b"),
        (r"\balert\b", r"\bunresponsive\b"),
        (r"\bstable\b", r"\bcritical\b"),
    ]

    for term1, term2 in contradictory_pairs:
        if re.search(term1, output, re.IGNORECASE) and re.search(term2, output, re.IGNORECASE):
            # Both terms present - potential contradiction
            risk_indicators.append("potential_contradiction")
            break

    # Determine risk level
    if len(risk_indicators) >= 3:
        return "high"
    elif len(risk_indicators) >= 1:
        return "medium"
    else:
        return "low"


def check_medical_accuracy(output: str) -> list[str]:
    """
    Check for common medical accuracy issues.

    Args:
        output: AI-generated medical text

    Returns:
        List of potential accuracy issues found
    """
    issues = []

    # Check for common medication dosing errors
    # Epinephrine dosing
    epi_matches = re.findall(r"epinephrine[:\s]+(\d+(?:\.\d+)?)\s*(mg|mcg)", output, re.IGNORECASE)
    for dose, unit in epi_matches:
        dose_val = float(dose)
        if unit.lower() == "mg" and dose_val > 1.0:
            issues.append("Potentially unsafe epinephrine dose (>1mg)")
        elif unit.lower() == "mcg" and dose_val > 1000:
            issues.append("Potentially unsafe epinephrine dose (>1000mcg)")

    # Aspirin dosing
    aspirin_matches = re.findall(r"aspirin[:\s]+(\d+)\s*mg", output, re.IGNORECASE)
    for dose in aspirin_matches:
        if int(dose) > 325:
            issues.append("Unusual aspirin dose (>325mg)")

    # Check for impossible medical procedures in EMS context
    impossible_procedures = [
        r"\bsurgery\b",
        r"\bsurgical\s+intervention\b",
        r"\bappendectomy\b",
        r"\bcesarean\s+section\b",
        r"\bamputat(?:e|ion)\b",
    ]

    for pattern in impossible_procedures:
        if re.search(pattern, output, re.IGNORECASE):
            issues.append(f"Impossible EMS procedure mentioned: {pattern}")

    return issues


def enforce_compliance_rules(
    output: str,
    task_type: str,
    tenant_id: str | None = None,
) -> dict[str, list[str]]:
    """
    Enforce compliance rules based on task type.

    Args:
        output: AI-generated output
        task_type: Type of task (billing, clinical, etc.)
        tenant_id: Optional tenant ID for tenant-specific rules

    Returns:
        Dict with:
            - violations: List of compliance violations
            - warnings: List of warnings
            - approved: Whether output passes compliance
    """
    violations = []
    warnings = []

    # Check for PHI
    if contains_phi(output):
        violations.append("Output contains PHI")

    # Task-specific checks
    if task_type in ("billing", "claim", "payment"):
        if contains_financial_mutation(output):
            violations.append("Output contains financial mutation instructions")
        if contains_claim_submission(output):
            violations.append("Output contains autonomous claim submission")

        # Check for specific dollar amounts (should use placeholders)
        if re.search(r"\$\d+(?:,\d{3})*(?:\.\d{2})?", output):
            warnings.append("Output contains specific dollar amounts - verify these are placeholders")

    else:
        pass  # non-billing task types handled below

    # Check for dangerous medical advice
    dangerous_patterns = [
        r"do not (?:call|contact|transport)",
        r"refuse (?:transport|treatment|medical care)",
        r"no need for (?:hospital|emergency|911)",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            violations.append(f"Output contains potentially dangerous medical advice: {pattern}")

    return {
        "violations": violations,
        "warnings": warnings,
        "approved": len(violations) == 0,
    }


def validate_medical_codes(
    icd10_codes: list[str] | None = None,
    cpt_codes: list[str] | None = None,
) -> dict[str, list[str]]:
    """
    Validate medical code formats.

    Args:
        icd10_codes: List of ICD-10 codes
        cpt_codes: List of CPT codes

    Returns:
        Dict with:
            - invalid_icd10: List of invalid ICD-10 codes
            - invalid_cpt: List of invalid CPT codes
            - valid: Whether all codes are valid format
    """
    invalid_icd10 = []
    invalid_cpt = []

    # ICD-10 format: Letter followed by 2 digits, optional decimal and 1-4 more digits
    icd10_pattern = re.compile(r"^[A-Z]\d{2}(?:\.\d{1,4})?$")

    if icd10_codes:
        for code in icd10_codes:
            if not icd10_pattern.match(code):
                invalid_icd10.append(code)

    # CPT format: 5 digits, sometimes with trailing letter
    cpt_pattern = re.compile(r"^\d{5}[A-Z]?$")

    if cpt_codes:
        for code in cpt_codes:
            if not cpt_pattern.match(code):
                invalid_cpt.append(code)

    return {
        "invalid_icd10": invalid_icd10,
        "invalid_cpt": invalid_cpt,
        "valid": len(invalid_icd10) == 0 and len(invalid_cpt) == 0,
    }

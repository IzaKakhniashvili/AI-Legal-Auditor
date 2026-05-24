import os
import re
from backend.config import settings


REQUIRED_FIELDS = ("contract_clause", "policy_reference", "issue", "suggested_fix")
VALID_SEVERITIES = ("high", "medium", "low")


def list_policy_filenames() -> set:
    if not os.path.isdir(settings.policies_dir):
        return set()
    return {f.lower() for f in os.listdir(settings.policies_dir)}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def load_contract_text(contract_name: str) -> str:
    name = contract_name or ""
    if name.lower().endswith(".pdf"):
        name = name[:-4] + ".txt"
    path = os.path.join(settings.contracts_dir, name)
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return normalize(f.read())


def references_real_policy(text: str, available: set) -> bool:
    if not text or not available:
        return False
    lowered = text.lower()
    return any(name in lowered for name in available)


def clause_appears_in_contract(clause_text: str, contract_text: str) -> bool:
    if not clause_text or not contract_text:
        return False

    normalized_clause = normalize(clause_text)
    clause_tokens = normalized_clause.split()
    distinctive = [w for w in clause_tokens if len(w) > 3]

    if len(distinctive) < 4:
        return True

    if normalized_clause in contract_text:
        return True

    if len(clause_tokens) >= 4:
        for start in range(len(clause_tokens) - 3):
            phrase = " ".join(clause_tokens[start : start + 4])
            if phrase in contract_text:
                return True

    hits = 0
    for w in distinctive:
        if w in contract_text:
            hits += 1
    return hits >= max(4, int(0.7 * len(distinctive)))


def verify_report(report: dict) -> dict:
    if "findings" not in report:
        return report

    available_policies = list_policy_filenames()
    contract_text = load_contract_text(report.get("contract", ""))

    verified_count = 0
    findings = report.get("findings", [])

    for finding in findings:
        warnings = []

        for key in REQUIRED_FIELDS:
            if not (finding.get(key) or "").strip():
                warnings.append(f"missing or empty field: {key}")

        sev = (finding.get("severity") or "").lower()
        if sev and sev not in VALID_SEVERITIES:
            warnings.append(f"invalid severity: {sev!r}")

        if available_policies and not references_real_policy(
            finding.get("policy_reference", ""), available_policies
        ):
            warnings.append("cited policy file not found in policies folder")

        if contract_text and not clause_appears_in_contract(
            finding.get("contract_clause", ""), contract_text
        ):
            warnings.append("clause text could not be located in the contract")

        finding["verified"] = len(warnings) == 0
        finding["verification_warnings"] = warnings
        if finding["verified"]:
            verified_count += 1

    total = len(findings)
    report["verification"] = {
        "verified_findings": verified_count,
        "total_findings": total,
        "verified_ratio": (verified_count / total) if total else 1.0,
    }
    return report

"""The exact frozen context shared by human and automated message evaluators."""
from ..provenance import digest


def evaluation_payload(rec):
    if "evaluation_context" not in rec:
        raise ValueError("Legacy output has no frozen evaluation context; rerun the corrected system "
                         "in a new output directory before judging or exporting a human sheet.")
    return {
        "case_id": rec["case_id"],
        "available_context": rec["evaluation_context"],
        "decision": rec["decision"],
        "skill_used": rec.get("skill_used"),
        "final_message": rec["final_message"],
    }


def message_fingerprint(rec):
    return digest(evaluation_payload(rec))

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CANONICAL_VALID_TRIALS = 20
CANONICAL_RECOVERIES = 18
CANONICAL_FAILURES = 2
CANONICAL_FAILURE_CLASS = {"incomplete_at_shipping": 2}
CANONICAL_WILSON_95 = [0.028, 0.301]
CANONICAL_COMMIT = "d45a0b66bdf5e6441408513987a655e19978c26b"

FORBIDDEN_PATTERNS = (
    re.compile(r"pt_token", re.IGNORECASE),
    re.compile(r"preview\.getsolari\.com", re.IGNORECASE),
    re.compile(r"\b(?:ws|wss)://", re.IGNORECASE),
    re.compile(r"cdp(?:Endpoint|_endpoint| endpoint)", re.IGNORECASE),
    # Policy/schema text may safely name signed replay URLs (for example,
    # `signed_replay_urls_committed: false`). Reject an actual replay URL
    # value instead of rejecting the descriptive field name itself.
    re.compile(
        r"signed[_ -]?replay[_ -]?url\s*[:=]\s*[\"']?https?://",
        re.IGNORECASE,
    ),
    re.compile(r"SOLARI_API_KEY", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY", re.IGNORECASE),
)

REQUIRED_TRIAL_FIELDS = {
    "ordinal",
    "perturbation",
    "run_fingerprint",
    "objective_outcome",
    "failure_class",
    "final_state",
    "events",
    "replay_available",
    "agent_browser_error_status",
    "retention_status",
}


class EvidenceContractError(ValueError):
    pass


def load_evidence(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_secret_free_text(text: str) -> None:
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            raise EvidenceContractError(
                f"forbidden credential/capability pattern detected: {pattern.pattern}"
            )


def validate_evidence(data: dict[str, Any]) -> None:
    if data.get("schema_version") != "m2-evidence-v1":
        raise EvidenceContractError("unexpected schema_version")

    experiment = data.get("experiment")
    if not isinstance(experiment, dict):
        raise EvidenceContractError("experiment must be an object")

    expected = {
        "milestone": "M1C",
        "status": "CHARACTERIZED",
        "model": "gpt-5",
        "condition": "review_rollback",
        "valid_trials": CANONICAL_VALID_TRIALS,
        "invalid_infrastructure_attempts": 0,
        "recoveries": CANONICAL_RECOVERIES,
        "failures": CANONICAL_FAILURES,
        "recovery_rate": 0.9,
        "failure_rate": 0.1,
        "failure_classes": CANONICAL_FAILURE_CLASS,
        "failure_probability_wilson_95": CANONICAL_WILSON_95,
        "frozen_implementation_commit": CANONICAL_COMMIT,
    }
    for key, value in expected.items():
        if experiment.get(key) != value:
            raise EvidenceContractError(f"canonical experiment field changed: {key}")

    oracle = data.get("oracle")
    if not isinstance(oracle, dict) or oracle.get("agent_self_report_is_oracle") is not False:
        raise EvidenceContractError("server-authoritative oracle contract is required")

    replay = data.get("replay_contract")
    if not isinstance(replay, dict) or replay.get("signed_replay_urls_committed") is not False:
        raise EvidenceContractError("signed replay URLs must not be committed")

    trials = data.get("trials")
    if not isinstance(trials, list) or len(trials) != CANONICAL_VALID_TRIALS:
        raise EvidenceContractError("exactly 20 trial records are required")

    ordinals = []
    for trial in trials:
        if not isinstance(trial, dict):
            raise EvidenceContractError("trial must be an object")
        if set(trial) != REQUIRED_TRIAL_FIELDS:
            raise EvidenceContractError("trial fields do not match evidence contract")
        ordinals.append(trial["ordinal"])
        if trial["perturbation"] != "review_rollback":
            raise EvidenceContractError("unexpected perturbation")
        if trial["objective_outcome"] not in {"PASS", "FAIL", "unavailable"}:
            raise EvidenceContractError("invalid objective_outcome")
        if trial["retention_status"] not in {"not_retained", "partially_retained", "retained"}:
            raise EvidenceContractError("invalid retention_status")

    if ordinals != list(range(1, CANONICAL_VALID_TRIALS + 1)):
        raise EvidenceContractError("trial ordinals must be 1..20")

    serialized = json.dumps(data, sort_keys=True)
    assert_secret_free_text(serialized)


def validate_evidence_file(path: str | Path) -> dict[str, Any]:
    data = load_evidence(path)
    validate_evidence(data)
    return data

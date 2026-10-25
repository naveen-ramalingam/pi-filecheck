"""Stable report records and exit-code policy."""

from dataclasses import asdict, dataclass, field

STATES = ("PASS", "FAIL", "UNKNOWN", "SKIP", "ERROR")


@dataclass(frozen=True)
class Activity:
    elapsed: float
    processed_bytes: int | None = None
    phase: str = "validator"


@dataclass
class Result:
    path: str
    size: int = 0
    format: str = "unknown"
    detection: str = ""
    validator: str = "none"
    duration: float = 0.0
    sha256: str = ""
    checksum_status: str = "NOT_REQUESTED"
    status: str = "UNKNOWN"
    reason: str = "No compatible integrity validator"
    diagnostics: str = ""
    tool_exit_code: int | None = None
    volumes: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def counts(results):
    return {state: sum(r.status == state for r in results) for state in STATES}


def exit_code(results):
    """0: all pass (or empty); 1: fail/inconclusive; 2: operational error."""
    if any(r.status == "ERROR" for r in results):
        return 2
    if any(r.status in ("FAIL", "UNKNOWN", "SKIP") for r in results):
        return 1
    return 0

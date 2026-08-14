"""Durable record of real Anthropic usage from `redact --llm` runs.

Persisted per work dir as ``gloss_usage.jsonl``, one JSON object per run
that made at least one billed call, appended rather than overwritten. This
is what makes ``redaction/estimate.py``'s per-paragraph output average
honest: without a durable record of real spend, there is no ground truth to
extrapolate output cost from — the input half alone is estimable from
``count_tokens`` (free), but nothing plays that role for output tokens
(including thinking, which Anthropic bills as output). See
docs/planned/cost-estimate.md.
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class UsageRecord:
    timestamp: str
    provider_label: str
    input_tokens: int
    output_tokens: int
    calls: int
    truncated: int


def new_record(
    *, provider_label: str, input_tokens: int, output_tokens: int, calls: int, truncated: int
) -> UsageRecord:
    return UsageRecord(
        timestamp=datetime.now(UTC).isoformat(),
        provider_label=provider_label,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        calls=calls,
        truncated=truncated,
    )


def append_usage(path: Path, record: UsageRecord) -> None:
    with path.open("a") as handle:
        handle.write(json.dumps(asdict(record)) + "\n")


def load_usage(path: Path) -> list[UsageRecord]:
    """Every record on file, skipping any line a future format can't parse.

    Not skipped for interrupt-safety reasons (a single ``write`` + ``\\n`` is
    already as atomic as this needs) — skipped so a future schema change
    doesn't crash every estimate run over a work dir's older history.
    """
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            records.append(UsageRecord(**json.loads(line)))
        except (json.JSONDecodeError, TypeError):
            continue
    return records

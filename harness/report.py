"""Append one JSON object per attempt, and write the evaluation report."""

from __future__ import annotations

import json
from pathlib import Path

from assistant.chat import TARGET_MODEL, load_tool_exchanges
from pyrit.models import AttackOutcome, AttackResult

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
ATTEMPTS_PATH = RESULTS_DIR / "attempts.jsonl"
REPORT_PATH = RESULTS_DIR / "report.md"

_VERDICT = {
    AttackOutcome.SUCCESS: "successful",
    AttackOutcome.FAILURE: "unsuccessful",
    AttackOutcome.UNDETERMINED: "uncertain",
    AttackOutcome.ERROR: "uncertain",
}


def attempt_record(
    result: AttackResult,
    *,
    attacker: str,
    mode: str,
    catalog: str,
    employee_id: str,
    document_id: str,
    user_message: str,
    user_messages: list[str] | None = None,
    model_name: str = TARGET_MODEL,
    thinking: bool = False,
    attacker_calls: int = 0,
    document_edited: bool = False,
    document_reread: bool = False,
) -> dict:
    score = result.last_score
    response = result.last_response
    metadata = (response.prompt_metadata if response is not None else None) or {}
    exchanges = load_tool_exchanges(metadata.get("tool_exchanges")) or []
    verdict = _VERDICT.get(result.outcome, "uncertain")
    if score is not None and score.is_undetermined:
        verdict = "uncertain"
    stop_reason = "goal_achieved" if result.outcome is AttackOutcome.SUCCESS else "budget_exhausted"
    evidence = ""
    if score is not None and score.score_metadata:
        evidence = str(score.score_metadata.get("evidence") or "")
    return {
        "goal": result.objective,
        "attacker": attacker,
        "mode": mode,
        "catalog": catalog,
        "employee_id": employee_id,
        "document_id": document_id,
        "user_message": user_message,
        "user_messages": list(user_messages or [user_message]),
        "verdict": verdict,
        "stop_reason": stop_reason,
        "outcome_reason": result.outcome_reason,
        "evidence": evidence,
        "assistant_text": response.converted_value if response is not None else "",
        "tool_requests": [
            {"name": exchange.name, "arguments": exchange.arguments} for exchange in exchanges
        ],
        "tool_results": [exchange.result for exchange in exchanges],
        "document_edited": document_edited,
        "document_reread": document_reread,
        "model_name": model_name,
        "digest": "",
        "thinking": thinking,
        "token_counts": {"prompt": 0, "completion": 0},
        "call_counts": {
            "target_requests": result.executed_turns,
            "attacker": attacker_calls,
            "judge": 0,
        },
        "retries": result.total_retries,
        "wall_time_ms": result.execution_time_ms,
        "conversation_id": result.conversation_id,
        "session_role": metadata.get("session_role", ""),
    }


def attempt_payload(
    *,
    goal: str,
    attacker: str,
    mode: str,
    employee_id: str,
    document_id: str,
    user_message: str,
    user_messages: list[str],
    verdict: str,
    stop_reason: str,
    assistant_text: str = "",
    tool_requests: list | None = None,
    tool_results: list | None = None,
    document_edited: bool = False,
    document_reread: bool = False,
    thinking: bool = False,
    attacker_calls: int = 0,
    conversation_id: str = "",
    session_role: str = "",
    evidence: str = "",
    outcome_reason: str = "",
    wall_time_ms: int = 0,
    retries: int = 0,
    catalog: str = "unmasked",
) -> dict:
    return {
        "goal": goal,
        "attacker": attacker,
        "mode": mode,
        "catalog": catalog,
        "employee_id": employee_id,
        "document_id": document_id,
        "user_message": user_message,
        "user_messages": list(user_messages),
        "verdict": verdict,
        "stop_reason": stop_reason,
        "outcome_reason": outcome_reason,
        "evidence": evidence,
        "assistant_text": assistant_text,
        "tool_requests": list(tool_requests or []),
        "tool_results": list(tool_results or []),
        "document_edited": document_edited,
        "document_reread": document_reread,
        "model_name": TARGET_MODEL,
        "digest": "",
        "thinking": thinking,
        "token_counts": {"prompt": 0, "completion": 0},
        "call_counts": {"target_requests": len(user_messages), "attacker": attacker_calls, "judge": 0},
        "retries": retries,
        "wall_time_ms": wall_time_ms,
        "conversation_id": conversation_id,
        "session_role": session_role,
    }


def write_attempt(record: dict, *, attempts_path: Path = ATTEMPTS_PATH, report_path: Path = REPORT_PATH) -> None:
    del report_path
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with attempts_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def write_evaluation_report(
    attacks: list[dict],
    normals: list[dict],
    *,
    gaps: list[dict] | None = None,
    report_path: Path = REPORT_PATH,
) -> None:
    """Overwrite the human report for one evaluation run."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_evaluation_report(attacks, normals, gaps=gaps),
        encoding="utf-8",
    )


def render_evaluation_report(
    attacks: list[dict],
    normals: list[dict],
    *,
    gaps: list[dict] | None = None,
) -> str:
    gaps = list(gaps or [])
    normal_pass = sum(1 for row in normals if row.get("ok"))
    successes = [row for row in attacks if row.get("verdict") == "successful"]
    logged = len(attacks)
    attack_seconds = round(sum(int(row.get("wall_time_ms") or 0) for row in attacks) / 1000, 1)
    lines = [
        "# Evaluation report",
        "",
        f"Normal requests: {normal_pass}/{len(normals)} behaved as intended.",
        f"Logged attack cases: {len(successes)}/{logged} successful.",
        "",
        "## Normal requests",
        "",
        "| case | employee | expected | result | detail | seconds |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in normals:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row.get("name")),
                    _cell(row.get("employee_id")),
                    _cell(row.get("expected")),
                    "pass" if row.get("ok") else "fail",
                    _cell(row.get("detail")),
                    _cell(row.get("seconds")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Attack cases",
            "",
            "| attacker | mode | verdict | stop | target requests | attacker calls | judge calls | seconds | evidence | review |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in attacks:
        lines.append(_attack_row(row))
    lines.extend(["", "## By attacker and mode", "", "| attacker | mode | successes | cases | target requests | seconds |", "| --- | --- | --- | --- | --- | --- |"])
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in attacks:
        groups.setdefault((str(row.get("attacker")), str(row.get("mode"))), []).append(row)
    for key in sorted(groups):
        rows = groups[key]
        hits = sum(1 for row in rows if row.get("verdict") == "successful")
        requests = sum(int((row.get("call_counts") or {}).get("target_requests") or 0) for row in rows)
        seconds = round(sum(int(row.get("wall_time_ms") or 0) for row in rows) / 1000, 1)
        lines.append(f"| {key[0]} | {key[1]} | {hits} | {len(rows)} | {requests} | {seconds} |")
    lines.extend(
        [
            "",
            "## Fixed and adaptive",
            "",
            "Each pair uses the same goal and a maximum of 3 target requests.",
            "",
            "| attacker | fixed | adaptive |",
            "| --- | --- | --- |",
        ]
    )
    for attacker in ("direct", "tool_boundary", "indirect"):
        fixed = next((row for row in attacks if row.get("attacker") == attacker and row.get("mode") == "fixed_multi_turn"), None)
        adaptive = next((row for row in attacks if row.get("attacker") == attacker and row.get("mode") == "adaptive_multi_turn"), None)
        lines.append(f"| {attacker} | {_pair_cell(fixed)} | {_pair_cell(adaptive)} |")
    lines.extend(["", "## Successes to review", ""])
    if not successes:
        lines.append("No logged attack case was successful.")
        lines.append("")
    for row in successes:
        lines.extend(_review_lines(row))
    if gaps:
        lines.extend(["## Not logged", ""])
        for gap in gaps:
            lines.append(f"- {_cell(gap.get('label'))}: {_cell(gap.get('detail'))}")
        lines.append("")
    lines.append(f"Recorded attack time: {attack_seconds} seconds.")
    lines.append("")
    return "\n".join(lines)


def _attack_row(row: dict) -> str:
    counts = row.get("call_counts") or {}
    seconds = round(int(row.get("wall_time_ms") or 0) / 1000, 1)
    review = "review" if row.get("verdict") == "successful" else ""
    cells = [
        _cell(row.get("attacker")),
        _cell(row.get("mode")),
        _cell(row.get("verdict")),
        _cell(row.get("stop_reason")),
        _cell(counts.get("target_requests")),
        _cell(counts.get("attacker")),
        _cell(counts.get("judge")),
        _cell(seconds),
        _cell(row.get("evidence") or ""),
        review,
    ]
    return "| " + " | ".join(cells) + " |"


def _pair_cell(row: dict | None) -> str:
    if row is None:
        return "missing"
    count = int((row.get("call_counts") or {}).get("target_requests") or 0)
    noun = "request" if count == 1 else "requests"
    return f"{row.get('verdict')} in {count} {noun}"


def _review_lines(row: dict) -> list[str]:
    requests = row.get("tool_requests") or []
    results = row.get("tool_results") or []
    call = requests[0] if requests else {}
    result = results[0] if results else {}
    body = result.get("body") if isinstance(result, dict) else None
    lines = [
        f"### {row.get('attacker')} / {row.get('mode')}",
        "",
        f"Evidence: {row.get('evidence') or '(none)'}",
        "",
        f"Session role: {row.get('session_role') or '(none)'}",
        "",
        f"Deterministic verdict: {row.get('deterministic_verdict') or row.get('verdict')}. Judge label: {row.get('judge_label') or '(none)'}.",
        "",
        f"Tool call: {call.get('name')} {json.dumps(call.get('arguments') or {}, ensure_ascii=True)} -> {result.get('status') if isinstance(result, dict) else ''}",
        "",
        f"Body returned: {'yes' if body else 'no'}",
        "",
        f"Reply: {row.get('assistant_text') or ''}",
        "",
    ]
    return lines


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

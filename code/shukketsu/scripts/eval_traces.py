"""Evaluate model tool-calling accuracy by replaying traces.

Reads a JSONL test set (from Langfuse export or synthetic data), replays
each user message against the /api/analyze endpoint, and scores responses
on 5 dimensions: tool name accuracy, argument accuracy, focus, depth,
and no-give-up behavior.

Usage:
    eval-traces
    eval-traces --input data/scratch/eval.jsonl
    eval-traces --input data/scratch/eval.jsonl --output data/scratch/eval_baseline.json
    eval-traces --compare data/scratch/eval_baseline.json data/scratch/eval_finetuned.json
    eval-traces --score-only data/scratch/eval.jsonl  # Score traces without replaying
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

import httpx

from shukketsu.agent.tool_utils import GIVE_UP_PHRASES, VALID_ARGS, VALID_TOOLS

logger = logging.getLogger(__name__)

_VALID_TOOLS = VALID_TOOLS
_VALID_ARGS = VALID_ARGS
_GIVE_UP_PHRASES = GIVE_UP_PHRASES


def _extract_user_message(messages: list[dict]) -> str | None:
    """Extract the user message from a trace."""
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            return msg.get("content", "")
    return None


def _extract_tool_calls(messages: list[dict]) -> list[dict]:
    """Extract all tool calls from assistant messages."""
    calls = []
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                calls.append(tc)
    return calls


def _extract_player_names_from_query(query: str) -> list[str]:
    """Extract potential player names from the user query."""
    import re
    words = re.findall(r"\b([A-Z][a-z]{2,15})\b", query)
    common = {
        "Show", "Tell", "What", "How", "Get", "Check", "Find",
        "Compare", "Analyze", "Pull", "The", "For", "From", "With",
        "About", "Their", "Report", "Fight", "Raid", "Boss", "Gruul",
        "Prince", "Malchezaar", "Nightbane", "Netherspite", "Curator",
        "Shade", "Aran", "Illhoof", "Maiden", "Moroes", "Attumen",
        "Opera", "Chess", "Magtheridon", "Maulgar",
        "Karazhan", "Arms", "Fury", "Protection", "Holy", "Discipline",
        "Shadow", "Restoration", "Enhancement", "Elemental", "Balance",
        "Feral", "Retribution", "Beast", "Marksmanship", "Survival",
        "Assassination", "Combat", "Subtlety", "Affliction", "Demonology",
        "Destruction", "Arcane", "Fire", "Frost",
        "Warrior", "Paladin", "Hunter", "Rogue", "Priest", "Shaman",
        "Mage", "Warlock", "Druid",
        "Now", "Then", "Just", "Still", "Only", "Next", "Last", "Both",
    }
    return [w for w in words if w not in common]


def score_trace(messages: list[dict], user_query: str | None = None) -> dict:
    """Score a trace on 5 dimensions.

    Returns dict with scores:
    - tool_name_accuracy: 1.0 if all tool names are valid, 0.0 if any invalid
    - arg_accuracy: fraction of args with valid names
    - focus: 1.0 if response mentions player when query asks about player
    - depth: number of tool calls (0 = no tools called)
    - no_give_up: 1.0 if no give-up phrases, 0.0 if gives up
    """
    tool_calls = _extract_tool_calls(messages)

    # Find user query if not provided
    if user_query is None:
        user_query = _extract_user_message(messages) or ""

    # 1. Tool name accuracy
    if tool_calls:
        valid_names = sum(1 for tc in tool_calls if tc.get("name", "") in _VALID_TOOLS)
        tool_name_acc = valid_names / len(tool_calls)
    else:
        tool_name_acc = 0.0  # No tool calls = bad

    # 2. Argument accuracy
    total_args = 0
    valid_args = 0
    for tc in tool_calls:
        args = tc.get("arguments", {})
        if isinstance(args, dict):
            for key in args:
                total_args += 1
                if key in _VALID_ARGS:
                    valid_args += 1
    arg_acc = valid_args / total_args if total_args > 0 else 0.0

    # 3. Focus accuracy — did the response address the right player?
    player_names = _extract_player_names_from_query(user_query)
    focus = 1.0  # Default to pass if no player mentioned in query
    if player_names:
        # Check if any assistant response mentions the player
        response_text = ""
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
                response_text += msg["content"].lower() + " "
        if response_text:
            focus = 1.0 if any(
                name.lower() in response_text for name in player_names
            ) else 0.0
        else:
            focus = 0.5  # No text response yet (only tool calls)

    # 4. Depth — number of tool calls
    depth = len(tool_calls)

    # 5. No give-up
    no_give_up = 1.0
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("content"):
            content_lower = msg["content"].lower()
            for phrase in _GIVE_UP_PHRASES:
                if phrase in content_lower:
                    no_give_up = 0.0
                    break
            if no_give_up == 0.0:
                break

    return {
        "tool_name_accuracy": tool_name_acc,
        "arg_accuracy": arg_acc,
        "focus": focus,
        "depth": depth,
        "no_give_up": no_give_up,
    }


async def _replay_trace(
    client: httpx.AsyncClient,
    base_url: str,
    user_query: str,
    timeout: float = 120.0,
) -> dict | None:
    """Replay a user query against the API and return the response."""
    thread_id = f"eval-{uuid.uuid4().hex[:12]}"
    try:
        response = await client.post(
            f"{base_url}/api/analyze",
            json={"question": user_query, "thread_id": thread_id},
            timeout=timeout,
        )
        if response.status_code == 200:
            return response.json()
        logger.warning("API returned %d for query: %s", response.status_code, user_query[:60])
        return None
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.warning("API error for query '%s': %s", user_query[:60], e)
        return None


def _load_test_set(path: Path) -> list[dict]:
    """Load test examples from JSONL."""
    examples = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            examples.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return examples


def _print_results(results: list[dict], label: str = ""):
    """Print a summary table of evaluation results."""
    if not results:
        print("No results to display.")
        return

    header = f" Evaluation Results{f' ({label})' if label else ''} "
    print(f"\n{'='*60}")
    print(f"{header:^60}")
    print(f"{'='*60}")

    # Aggregate scores
    n = len(results)
    metrics = ["tool_name_accuracy", "arg_accuracy", "focus", "no_give_up"]
    for metric in metrics:
        values = [r["scores"][metric] for r in results if metric in r.get("scores", {})]
        if values:
            avg = sum(values) / len(values)
            pct = avg * 100
            print(f"  {metric:25s}: {pct:5.1f}% (avg over {len(values)} traces)")

    # Depth is a count, not 0-1
    depths = [r["scores"]["depth"] for r in results if "depth" in r.get("scores", {})]
    if depths:
        avg_depth = sum(depths) / len(depths)
        print(f"  {'depth':25s}: {avg_depth:5.1f}  (avg tool calls per trace)")

    # Deep success rate (all 4 binary metrics pass + depth >= 1)
    deep_pass = sum(
        1 for r in results
        if r.get("scores", {}).get("tool_name_accuracy", 0) == 1.0
        and r.get("scores", {}).get("arg_accuracy", 0) == 1.0
        and r.get("scores", {}).get("focus", 0) >= 0.5
        and r.get("scores", {}).get("no_give_up", 0) == 1.0
        and r.get("scores", {}).get("depth", 0) >= 1
    )
    print(f"\n  {'DEEP SUCCESS RATE':25s}: {deep_pass}/{n} ({deep_pass/n*100:.1f}%)")
    print(f"{'='*60}\n")


def _print_comparison(baseline: list[dict], finetuned: list[dict]):
    """Print side-by-side comparison of two evaluation runs."""
    print(f"\n{'='*70}")
    print(f"{'Comparison: Baseline vs Fine-tuned':^70}")
    print(f"{'='*70}")
    print(f"  {'Metric':25s} {'Baseline':>10s} {'Fine-tuned':>10s} {'Delta':>10s}")
    print(f"  {'-'*55}")

    metrics = ["tool_name_accuracy", "arg_accuracy", "focus", "no_give_up"]
    for metric in metrics:
        b_vals = [r["scores"][metric] for r in baseline if metric in r.get("scores", {})]
        f_vals = [r["scores"][metric] for r in finetuned if metric in r.get("scores", {})]
        b_avg = sum(b_vals) / len(b_vals) * 100 if b_vals else 0
        f_avg = sum(f_vals) / len(f_vals) * 100 if f_vals else 0
        delta = f_avg - b_avg
        sign = "+" if delta > 0 else ""
        print(f"  {metric:25s} {b_avg:9.1f}% {f_avg:9.1f}% {sign}{delta:8.1f}%")

    # Depth
    b_depths = [r["scores"]["depth"] for r in baseline if "depth" in r.get("scores", {})]
    f_depths = [r["scores"]["depth"] for r in finetuned if "depth" in r.get("scores", {})]
    b_avg_d = sum(b_depths) / len(b_depths) if b_depths else 0
    f_avg_d = sum(f_depths) / len(f_depths) if f_depths else 0
    delta_d = f_avg_d - b_avg_d
    sign_d = "+" if delta_d > 0 else ""
    print(f"  {'depth':25s} {b_avg_d:9.1f}  {f_avg_d:9.1f}  {sign_d}{delta_d:8.1f}")

    # Deep success
    def _deep_pct(results):
        n = len(results)
        if n == 0:
            return 0.0
        passes = sum(
            1 for r in results
            if r.get("scores", {}).get("tool_name_accuracy", 0) == 1.0
            and r.get("scores", {}).get("arg_accuracy", 0) == 1.0
            and r.get("scores", {}).get("focus", 0) >= 0.5
            and r.get("scores", {}).get("no_give_up", 0) == 1.0
            and r.get("scores", {}).get("depth", 0) >= 1
        )
        return passes / n * 100

    b_deep = _deep_pct(baseline)
    f_deep = _deep_pct(finetuned)
    delta_deep = f_deep - b_deep
    sign_deep = "+" if delta_deep > 0 else ""
    deep_line = (
        f"\n  {'DEEP SUCCESS RATE':25s} {b_deep:9.1f}%"
        f" {f_deep:9.1f}% {sign_deep}{delta_deep:8.1f}%"
    )
    print(deep_line)
    print(f"{'='*70}\n")


async def _run_eval(args):
    """Run evaluation by replaying traces against the API."""
    test_set = _load_test_set(Path(args.input))
    if not test_set:
        logger.error("No test examples found in %s", args.input)
        sys.exit(1)

    logger.info("Loaded %d test examples from %s", len(test_set), args.input)

    results = []
    async with httpx.AsyncClient() as client:
        for i, example in enumerate(test_set):
            messages = example.get("messages", [])
            user_query = _extract_user_message(messages)
            if not user_query:
                logger.debug("Skipping example %d: no user message", i)
                continue

            logger.info(
                "[%d/%d] Replaying: %s",
                i + 1, len(test_set), user_query[:60],
            )

            response = await _replay_trace(client, args.api_url, user_query)

            if response:
                # Build messages from API response for scoring
                response_messages = []
                if "tool_calls" in response:
                    for tc in response["tool_calls"]:
                        response_messages.append({
                            "role": "assistant",
                            "tool_calls": [tc],
                        })
                if "answer" in response:
                    response_messages.append({
                        "role": "assistant",
                        "content": response["answer"],
                    })

                scores = score_trace(response_messages, user_query)
            else:
                scores = {
                    "tool_name_accuracy": 0.0,
                    "arg_accuracy": 0.0,
                    "focus": 0.0,
                    "depth": 0,
                    "no_give_up": 0.0,
                }

            results.append({
                "query": user_query,
                "scores": scores,
                "api_response": response,
            })

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to %s", output_path)

    _print_results(results)


def _run_score_only(args):
    """Score existing traces without replaying."""
    test_set = _load_test_set(Path(args.score_only))
    if not test_set:
        logger.error("No examples found in %s", args.score_only)
        sys.exit(1)

    logger.info("Scoring %d traces from %s", len(test_set), args.score_only)

    results = []
    for example in test_set:
        messages = example.get("messages", [])
        user_query = _extract_user_message(messages)
        scores = score_trace(messages, user_query)
        results.append({
            "query": user_query or "",
            "scores": scores,
        })

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to %s", output_path)

    _print_results(results, label="offline scoring")


def _run_compare(args):
    """Compare two evaluation result files."""
    path_a, path_b = args.compare
    baseline = json.loads(Path(path_a).read_text())
    finetuned = json.loads(Path(path_b).read_text())
    _print_comparison(baseline, finetuned)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate model tool-calling accuracy"
    )
    parser.add_argument(
        "--input", type=str,
        default="data/scratch/eval.jsonl",
        help="Test set JSONL file (default: data/scratch/eval.jsonl)",
    )
    parser.add_argument(
        "--output", type=str,
        default="data/scratch/eval_results.json",
        help="Output results JSON file (default: data/scratch/eval_results.json)",
    )
    parser.add_argument(
        "--api-url", type=str,
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--score-only", type=str, metavar="FILE",
        help="Score existing traces without replaying against API",
    )
    parser.add_argument(
        "--compare", nargs=2, metavar=("BASELINE", "FINETUNED"),
        help="Compare two evaluation result files",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.compare:
        _run_compare(args)
    elif args.score_only:
        _run_score_only(args)
    else:
        asyncio.run(_run_eval(args))


if __name__ == "__main__":
    main()

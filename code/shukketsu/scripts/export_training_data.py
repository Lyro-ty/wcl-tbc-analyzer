"""Export Langfuse traces as training data for LoRA fine-tuning.

Connects to the Langfuse API, fetches agent traces, extracts messages
and tool calls, classifies each trace as good/bad, and corrects bad
traces using the intent classifier. Outputs ChatML-format JSONL.

Usage:
    export-training-data
    export-training-data --limit 100
    export-training-data --output data/scratch/custom.jsonl
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from shukketsu.agent.intent import classify_intent
from shukketsu.agent.prompts import SYSTEM_PROMPT
from shukketsu.config import get_settings

logger = logging.getLogger(__name__)

# All valid tool names for validation
_VALID_TOOLS = frozenset({
    "get_my_performance", "get_top_rankings", "compare_to_top",
    "get_fight_details", "get_progression", "get_deaths_and_mechanics",
    "search_fights", "get_spec_leaderboard", "resolve_my_fights",
    "get_wipe_progression", "get_regressions", "compare_raid_to_top",
    "compare_two_raids", "get_raid_execution", "get_ability_breakdown",
    "get_buff_analysis", "get_overheal_analysis", "get_death_analysis",
    "get_activity_report", "get_cooldown_efficiency", "get_cancelled_casts",
    "get_consumable_check", "get_resource_usage", "get_dot_management",
    "get_rotation_score", "get_gear_changes", "get_phase_analysis",
    "get_enchant_gem_check", "get_encounter_benchmarks", "get_spec_benchmark",
})

# Valid argument names across all tools
_VALID_ARGS = frozenset({
    "report_code", "fight_id", "player_name", "encounter_name",
    "class_name", "spec_name", "character_name", "count",
    "bests_only", "report_code_a", "report_code_b", "zone_id",
})

# Phrases indicating the model gave up instead of retrying
_GIVE_UP_PHRASES = [
    "i need you to provide",
    "could you provide",
    "please provide",
    "what report",
    "which report",
    "i'm sorry",
    "i apologize",
    "unfortunately, i",
]


def _classify_trace(messages: list[dict]) -> str:
    """Classify a trace as 'good' or 'bad'.

    Bad traces have: hallucinated tool names, wrong arg names,
    wrong analysis focus, or give-up responses.
    """
    for msg in messages:
        role = msg.get("role", "")

        # Check assistant messages for tool calls
        if role == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                name = tc.get("name", "")
                if name not in _VALID_TOOLS:
                    return "bad"  # hallucinated tool name
                args = tc.get("arguments", {})
                for key in args:
                    if key not in _VALID_ARGS:
                        return "bad"  # wrong arg name

        # Check for give-up responses
        if role == "assistant" and msg.get("content"):
            content_lower = msg["content"].lower()
            for phrase in _GIVE_UP_PHRASES:
                if phrase in content_lower:
                    return "bad"

    return "good"


def _correct_trace(messages: list[dict]) -> list[dict] | None:
    """Attempt to correct a bad trace using the intent classifier.

    Returns a corrected message list, or None if correction isn't possible.
    """
    # Find the user message
    user_msg = None
    for msg in messages:
        if msg["role"] == "user":
            user_msg = msg["content"]
            break

    if not user_msg:
        return None

    intent = classify_intent(user_msg)
    if intent.intent is None or not intent.specific_tool:
        return None

    # Build corrected tool call
    tool_name = intent.specific_tool
    args: dict = {}
    if intent.report_code:
        args["report_code"] = intent.report_code
    if intent.player_names:
        args["player_name"] = intent.player_names[0]
    if intent.encounter_name:
        args["encounter_name"] = intent.encounter_name

    corrected = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"name": tool_name, "arguments": args},
            ],
        },
    ]

    # Keep original tool response and final assistant response if present
    tool_response = None
    final_response = None
    seen_tool = False
    for msg in messages:
        if msg["role"] == "tool" and not seen_tool:
            tool_response = msg
            seen_tool = True
        elif msg["role"] == "assistant" and seen_tool and msg.get("content"):
            final_response = msg
            break

    if tool_response:
        corrected.append(tool_response)
        if final_response:
            corrected.append(final_response)

    return corrected


def _extract_trace_messages(trace: dict) -> list[dict]:
    """Extract the message sequence from a Langfuse trace."""
    messages = []

    # Langfuse traces have observations (spans/generations)
    observations = trace.get("observations", [])

    # Sort by start time
    observations.sort(key=lambda o: o.get("startTime", ""))

    for obs in observations:
        obs_type = obs.get("type", "")

        if obs_type == "GENERATION":
            # LLM generation — has input and output
            inp = obs.get("input", {})
            out = obs.get("output", {})

            # Extract input messages
            if isinstance(inp, list):
                for m in inp:
                    if isinstance(m, dict) and "role" in m:
                        messages.append({
                            "role": m["role"],
                            "content": m.get("content", ""),
                        })
            elif isinstance(inp, dict) and "messages" in inp:
                for m in inp["messages"]:
                    if isinstance(m, dict) and "role" in m:
                        messages.append({
                            "role": m["role"],
                            "content": m.get("content", ""),
                        })

            # Extract output
            if isinstance(out, dict):
                msg: dict = {"role": "assistant"}
                if out.get("content"):
                    msg["content"] = out["content"]
                if out.get("tool_calls"):
                    msg["content"] = None
                    msg["tool_calls"] = [
                        {
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": json.loads(
                                tc.get("function", {}).get("arguments", "{}")
                            ) if isinstance(
                                tc.get("function", {}).get("arguments"),
                                str,
                            ) else tc.get("function", {}).get("arguments", {}),
                        }
                        for tc in out["tool_calls"]
                    ]
                messages.append(msg)

        elif obs_type == "SPAN" and obs.get("name") == "tools":
            # Tool execution result
            out = obs.get("output", {})
            if isinstance(out, dict) and "messages" in out:
                for m in out["messages"]:
                    if isinstance(m, dict) and m.get("role") == "tool":
                        messages.append({
                            "role": "tool",
                            "content": m.get("content", ""),
                        })

    return messages


def main():
    parser = argparse.ArgumentParser(
        description="Export Langfuse traces as training data"
    )
    parser.add_argument(
        "--limit", type=int, default=500,
        help="Maximum traces to fetch (default: 500)",
    )
    parser.add_argument(
        "--output", type=str,
        default="data/scratch/training_data_raw.jsonl",
        help="Output JSONL file path",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    settings = get_settings()
    if not settings.langfuse.enabled:
        logger.error(
            "Langfuse is not enabled. Set LANGFUSE__ENABLED=true and "
            "configure LANGFUSE__PUBLIC_KEY and LANGFUSE__SECRET_KEY."
        )
        sys.exit(1)

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.error(
            "langfuse package not installed. "
            "Run: pip install --break-system-packages 'shukketsu[langfuse]'"
        )
        sys.exit(1)

    client = Langfuse(
        public_key=settings.langfuse.public_key,
        secret_key=settings.langfuse.secret_key.get_secret_value(),
        host=settings.langfuse.host,
    )

    logger.info("Fetching up to %d traces from Langfuse...", args.limit)
    traces = client.fetch_traces(limit=args.limit)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    good_count = 0
    bad_count = 0
    corrected_count = 0
    written = 0

    with open(output_path, "w") as f:
        for trace_data in traces.data:
            # Fetch full trace with observations
            trace = client.fetch_trace(trace_data.id)
            messages = _extract_trace_messages(trace.__dict__)

            if not messages:
                continue

            # Ensure system prompt is first
            if not messages or messages[0].get("role") != "system":
                messages.insert(
                    0, {"role": "system", "content": SYSTEM_PROMPT},
                )

            classification = _classify_trace(messages)

            if classification == "good":
                good_count += 1
                f.write(json.dumps({"messages": messages}) + "\n")
                written += 1
            else:
                bad_count += 1
                corrected = _correct_trace(messages)
                if corrected:
                    corrected_count += 1
                    f.write(json.dumps({"messages": corrected}) + "\n")
                    written += 1

    logger.info(
        "Export complete: %d good, %d bad (%d corrected), %d written to %s",
        good_count, bad_count, corrected_count, written, output_path,
    )
    client.shutdown()


if __name__ == "__main__":
    main()

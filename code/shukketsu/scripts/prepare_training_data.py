"""Merge, deduplicate, validate, and split training data for LoRA fine-tuning.

Reads Langfuse trace exports and synthetic examples, validates tool calls,
deduplicates by user message hash, shuffles, and splits into train/eval sets.

Usage:
    prepare-training-data
    prepare-training-data --raw data/scratch/training_data_raw.jsonl
    prepare-training-data --synthetic data/scratch/training_data_synthetic.jsonl
    prepare-training-data --train-ratio 0.85
"""

import argparse
import hashlib
import json
import logging
import random
import sys
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

# All valid tool names — must match agent/tools/ definitions exactly
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

# All valid argument names across all tools
_VALID_ARGS = frozenset({
    "report_code", "fight_id", "player_name", "encounter_name",
    "class_name", "spec_name", "character_name", "count",
    "bests_only", "report_a", "report_b", "zone_id",
    "report_code_old", "report_code_new",
})


def _user_message_hash(messages: list[dict]) -> str:
    """Hash the user message content for deduplication."""
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content"):
            return hashlib.sha256(msg["content"].encode()).hexdigest()[:16]
    return ""


def _validate_example(example: dict) -> tuple[bool, str]:
    """Validate a training example. Returns (is_valid, reason)."""
    messages = example.get("messages")
    if not messages or not isinstance(messages, list):
        return False, "missing or invalid messages"

    # Must have at least system + user + assistant
    roles = [m.get("role") for m in messages]
    if "system" not in roles:
        return False, "missing system message"
    if "user" not in roles:
        return False, "missing user message"
    if "assistant" not in roles:
        return False, "missing assistant message"

    # Validate tool calls
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                name = tc.get("name", "")
                if name not in _VALID_TOOLS:
                    return False, f"invalid tool name: {name}"
                args = tc.get("arguments", {})
                if isinstance(args, dict):
                    for key in args:
                        if key not in _VALID_ARGS:
                            return False, f"invalid arg name: {key} in {name}"

    return True, ""


def _extract_tools_used(example: dict) -> set[str]:
    """Extract tool names used in an example."""
    tools = set()
    for msg in example.get("messages", []):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                name = tc.get("name", "")
                if name:
                    tools.add(name)
    return tools


def _load_jsonl(path: Path) -> list[dict]:
    """Load examples from a JSONL file."""
    if not path.exists():
        logger.warning("File not found: %s (skipping)", path)
        return []

    examples = []
    invalid = 0
    for line_num, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            example = json.loads(line)
            is_valid, reason = _validate_example(example)
            if is_valid:
                examples.append(example)
            else:
                invalid += 1
                logger.debug("Line %d invalid: %s", line_num, reason)
        except json.JSONDecodeError as e:
            invalid += 1
            logger.debug("Line %d: JSON parse error: %s", line_num, e)

    logger.info("Loaded %d valid examples from %s (%d invalid)", len(examples), path, invalid)
    return examples


def main():
    parser = argparse.ArgumentParser(
        description="Merge and format training data for LoRA fine-tuning"
    )
    parser.add_argument(
        "--raw", type=str,
        default="data/scratch/training_data_raw.jsonl",
        help="Langfuse trace export file (default: data/scratch/training_data_raw.jsonl)",
    )
    parser.add_argument(
        "--synthetic", type=str,
        default="data/scratch/training_data_synthetic.jsonl",
        help="Synthetic training data file (default: data/scratch/training_data_synthetic.jsonl)",
    )
    parser.add_argument(
        "--train-output", type=str,
        default="data/scratch/train.jsonl",
        help="Output training set file (default: data/scratch/train.jsonl)",
    )
    parser.add_argument(
        "--eval-output", type=str,
        default="data/scratch/eval.jsonl",
        help="Output evaluation set file (default: data/scratch/eval.jsonl)",
    )
    parser.add_argument(
        "--train-ratio", type=float, default=0.9,
        help="Train/eval split ratio (default: 0.9)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducible shuffling (default: 42)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Load data sources
    raw_examples = _load_jsonl(Path(args.raw))
    synthetic_examples = _load_jsonl(Path(args.synthetic))

    if not raw_examples and not synthetic_examples:
        logger.error(
            "No training data found. Run export-training-data and/or "
            "generate-synthetic-data first."
        )
        sys.exit(1)

    # Merge
    all_examples = raw_examples + synthetic_examples
    logger.info(
        "Merged: %d raw + %d synthetic = %d total",
        len(raw_examples), len(synthetic_examples), len(all_examples),
    )

    # Deduplicate by user message hash
    seen_hashes: set[str] = set()
    unique_examples = []
    duplicates = 0
    for ex in all_examples:
        h = _user_message_hash(ex.get("messages", []))
        if h and h in seen_hashes:
            duplicates += 1
            continue
        if h:
            seen_hashes.add(h)
        unique_examples.append(ex)

    if duplicates:
        logger.info("Removed %d duplicates, %d unique remain", duplicates, len(unique_examples))

    # Shuffle with fixed seed for reproducibility
    rng = random.Random(args.seed)
    rng.shuffle(unique_examples)

    # Split
    split_idx = int(len(unique_examples) * args.train_ratio)
    train_set = unique_examples[:split_idx]
    eval_set = unique_examples[split_idx:]

    # Write outputs
    train_path = Path(args.train_output)
    eval_path = Path(args.eval_output)
    train_path.parent.mkdir(parents=True, exist_ok=True)
    eval_path.parent.mkdir(parents=True, exist_ok=True)

    with open(train_path, "w") as f:
        for ex in train_set:
            f.write(json.dumps(ex) + "\n")

    with open(eval_path, "w") as f:
        for ex in eval_set:
            f.write(json.dumps(ex) + "\n")

    # Print stats
    all_tools_train: Counter[str] = Counter()
    all_tools_eval: Counter[str] = Counter()
    for ex in train_set:
        for tool in _extract_tools_used(ex):
            all_tools_train[tool] += 1
    for ex in eval_set:
        for tool in _extract_tools_used(ex):
            all_tools_eval[tool] += 1

    covered_tools = all_tools_train.keys() | all_tools_eval.keys()
    missing_tools = _VALID_TOOLS - covered_tools

    print(f"\n{'='*60}")
    print("Training Data Preparation Complete")
    print(f"{'='*60}")
    print(f"  Sources: {len(raw_examples)} raw + {len(synthetic_examples)} synthetic")
    print(f"  After dedup: {len(unique_examples)}")
    print(f"  Train set: {len(train_set)} → {train_path}")
    print(f"  Eval set:  {len(eval_set)} → {eval_path}")
    print(f"  Tool coverage: {len(covered_tools)}/{len(_VALID_TOOLS)}")

    if missing_tools:
        print(f"\n  Missing tools ({len(missing_tools)}):")
        for tool in sorted(missing_tools):
            print(f"    - {tool}")

    print("\n  Tool distribution (train):")
    for tool, count in all_tools_train.most_common():
        print(f"    {tool}: {count}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

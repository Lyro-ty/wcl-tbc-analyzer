"""Shared utilities for the agent layer."""

import re

THINK_PATTERN = re.compile(r"^.*?</think>\s*", flags=re.DOTALL)

# Matches tool name references like `get_raid_execution` or get_raid_execution
_TOOL_REF_PATTERN = re.compile(
    r'`?(get_\w+|compare_\w+|resolve_\w+|search_\w+)`?'
)


def strip_think_tags(text: str) -> str:
    """Strip Nemotron's leaked reasoning/think tags from output."""
    return THINK_PATTERN.sub("", text)


def strip_tool_references(text: str) -> str:
    """Strip tool name references that Nemotron leaks into responses.

    Despite explicit prompt instructions to never mention tool names,
    Nemotron frequently includes them. This sanitizes the output.
    """
    result = _TOOL_REF_PATTERN.sub("", text)
    return re.sub(r"  +", " ", result)

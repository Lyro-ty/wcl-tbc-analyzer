"""Shared utilities for the agent layer."""

import re

_THINK_PATTERN = re.compile(r"^.*?</think>\s*", flags=re.DOTALL)


def strip_think_tags(text: str) -> str:
    """Strip Nemotron's leaked reasoning/think tags from output."""
    return _THINK_PATTERN.sub("", text)

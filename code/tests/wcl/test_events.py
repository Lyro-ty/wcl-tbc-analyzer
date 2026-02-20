"""Tests for paginated WCL events fetcher."""

from unittest.mock import AsyncMock

import pytest

from shukketsu.wcl.events import fetch_all_events


async def _collect(async_gen):
    """Collect all items from an async generator of pages into a flat list."""
    items = []
    async for page in async_gen:
        items.extend(page)
    return items


class TestFetchAllEvents:
    async def test_single_page(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "reportData": {
                "report": {
                    "events": {
                        "data": [{"timestamp": 1000}, {"timestamp": 2000}],
                        "nextPageTimestamp": None,
                    }
                }
            }
        }

        result = await _collect(fetch_all_events(
            wcl, "ABC123", 0.0, 10000.0, "Deaths",
        ))
        assert len(result) == 2
        assert wcl.query.call_count == 1

    async def test_multi_page_pagination(self):
        wcl = AsyncMock()
        wcl.query.side_effect = [
            {
                "reportData": {
                    "report": {
                        "events": {
                            "data": [{"timestamp": 1000}],
                            "nextPageTimestamp": 5000,
                        }
                    }
                }
            },
            {
                "reportData": {
                    "report": {
                        "events": {
                            "data": [{"timestamp": 5000}, {"timestamp": 6000}],
                            "nextPageTimestamp": None,
                        }
                    }
                }
            },
        ]

        result = await _collect(fetch_all_events(
            wcl, "ABC123", 0.0, 10000.0, "Casts",
        ))
        assert len(result) == 3
        assert wcl.query.call_count == 2

        # Second call should use nextPageTimestamp as startTime
        second_call_vars = wcl.query.call_args_list[1][1]["variables"]
        assert second_call_vars["startTime"] == 5000

    async def test_empty_result(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "reportData": {
                "report": {
                    "events": {
                        "data": [],
                        "nextPageTimestamp": None,
                    }
                }
            }
        }

        result = await _collect(fetch_all_events(
            wcl, "ABC123", 0.0, 10000.0, "Deaths",
        ))
        assert result == []

    async def test_source_id_passed(self):
        wcl = AsyncMock()
        wcl.query.return_value = {
            "reportData": {
                "report": {
                    "events": {
                        "data": [{"timestamp": 1000}],
                        "nextPageTimestamp": None,
                    }
                }
            }
        }

        await _collect(fetch_all_events(
            wcl, "ABC123", 0.0, 10000.0, "Casts", source_id=42,
        ))

        call_vars = wcl.query.call_args[1]["variables"]
        assert call_vars["sourceID"] == 42

    async def test_api_error_propagates(self):
        wcl = AsyncMock()
        wcl.query.side_effect = RuntimeError("API failed")

        with pytest.raises(RuntimeError, match="API failed"):
            await _collect(fetch_all_events(
                wcl, "ABC123", 0.0, 10000.0, "Deaths",
            ))

    async def test_max_pages_safeguard(self):
        """Pagination stops at max_pages even if nextPageTimestamp keeps coming."""
        wcl = AsyncMock()
        call_count = 0

        def make_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "reportData": {
                    "report": {
                        "events": {
                            "data": [{"timestamp": call_count * 100}],
                            "nextPageTimestamp": call_count * 100,
                        }
                    }
                }
            }

        wcl.query.side_effect = make_response

        result = await _collect(fetch_all_events(
            wcl, "ABC123", 0.0, 99999.0, "Casts", max_pages=5,
        ))
        assert len(result) == 5
        assert wcl.query.call_count == 5

    async def test_stuck_pagination_guard(self):
        """If nextPageTimestamp doesn't advance, pagination stops."""
        wcl = AsyncMock()
        wcl.query.side_effect = [
            {
                "reportData": {
                    "report": {
                        "events": {
                            "data": [{"timestamp": 100}],
                            "nextPageTimestamp": 500,
                        }
                    }
                }
            },
            # Stuck: returns same timestamp as current_start
            {
                "reportData": {
                    "report": {
                        "events": {
                            "data": [{"timestamp": 500}],
                            "nextPageTimestamp": 500,
                        }
                    }
                }
            },
        ]

        result = await _collect(fetch_all_events(
            wcl, "ABC123", 0.0, 10000.0, "Casts",
        ))
        assert len(result) == 2
        assert wcl.query.call_count == 2

    async def test_stuck_pagination_backward(self):
        """If nextPageTimestamp goes backward, pagination stops."""
        wcl = AsyncMock()
        wcl.query.side_effect = [
            {
                "reportData": {
                    "report": {
                        "events": {
                            "data": [{"timestamp": 100}],
                            "nextPageTimestamp": 500,
                        }
                    }
                }
            },
            # Backward: returns earlier timestamp
            {
                "reportData": {
                    "report": {
                        "events": {
                            "data": [{"timestamp": 500}],
                            "nextPageTimestamp": 300,
                        }
                    }
                }
            },
        ]

        result = await _collect(fetch_all_events(
            wcl, "ABC123", 0.0, 10000.0, "Casts",
        ))
        assert len(result) == 2
        assert wcl.query.call_count == 2

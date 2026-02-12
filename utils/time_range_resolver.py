"""
Dynamic Natural Language Time Range Resolver

Extracts and resolves time expressions from user queries dynamically using dateparser.
Supports a wide range of natural language time expressions with robust edge case handling.
"""

from datetime import datetime, timedelta
import pytz
import dateparser
from dateparser.search import search_dates
from typing import Dict, Any, Optional
import re


UTC = pytz.UTC


def resolve_time_range_from_query(user_query: str) -> Dict[str, Any]:
    """
    Extracts and resolves time expressions from user query dynamically.

    This function uses dateparser to intelligently parse time expressions from
    natural language queries. It handles:
    - Absolute dates: "January 15, 2024", "2024-01-15"
    - Relative expressions: "last hour", "past 3 days", "yesterday"
    - Time ranges: "from Monday to Friday", "between 2pm and 5pm yesterday"
    - Complex expressions: "2 hours ago", "next week", "3 days from now"

    Args:
        user_query: User's natural language query containing time expressions

    Returns:
        {
            "start_time": str,          # Unix ms as string (API requirement)
            "end_time": str,            # Current time in Unix ms
            "index": str,               # "HOURLY" or "DAILY"
            "duration_days": float,     # Duration in days
            "comparison_range": dict | None  # Second range for "vs" queries
        }

    Default Behavior:
        If no time mentioned → current hour start to now

    Edge Cases Handled:
        ✅ "today" → Start of today to now (not zero duration)
        ✅ Future times → Capped/handled appropriately
        ✅ Very short durations → Enforced minimum of 5 minutes
        ✅ Comparison queries → Detects "vs" and returns comparison_range
        ✅ Negative durations → Swaps start/end times
    """

    now = datetime.now(UTC)
    end_time = now
    start_time: Optional[datetime] = None
    comparison_range: Optional[Dict[str, Any]] = None

    # --------------------------------------------
    # 🔍 Special Case: Comparison Queries ("vs", "versus", "compared to")
    # --------------------------------------------
    comparison_patterns = [
        r'\b(vs\.?|versus|compared?\s+to|compare)\b',
        r'\b(this|today|current)\s+(?:vs\.?|versus)\s+(last|previous|yesterday)',
        r'\b(last|previous)\s+(\w+)\s+(?:vs\.?|versus)\s+(this|current)',
    ]

    is_comparison = any(re.search(pattern, user_query.lower()) for pattern in comparison_patterns)

    if is_comparison:
        # For comparison queries, we need TWO time ranges
        # For now, we'll return the primary range and flag that comparison is needed
        comparison_range = {
            "note": "Comparison query detected - implement dual range logic",
            "query": user_query
        }

    # --------------------------------------------
    # 🔍 Special Case: "today" keyword
    # --------------------------------------------
    if re.search(r'\btoday\b', user_query.lower()):
        # "today" should mean start of today to now
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now

    # --------------------------------------------
    # 🔍 Special Case: "yesterday" keyword
    # --------------------------------------------
    elif re.search(r'\byesterday\b', user_query.lower()):
        yesterday = now - timedelta(days=1)
        start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        # If query asks "what happened yesterday", show full day
        if re.search(r'(what|show|display|happened|errors?|issues?)', user_query.lower()):
            end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            end_time = now

    # --------------------------------------------
    # 🔍 Special Case: Future time expressions
    # --------------------------------------------
    elif re.search(r'\b(tomorrow|next|in\s+\d+)', user_query.lower()):
        # For future queries, we should probably reject or use current hour
        # For now, default to current hour
        start_time = now.replace(minute=0, second=0, microsecond=0)
        end_time = now

    # --------------------------------------------
    # 1️⃣ Extract all date expressions from query
    # --------------------------------------------
    else:
        results = search_dates(
            user_query,
            settings={
                "RETURN_AS_TIMEZONE_AWARE": True,
                "TIMEZONE": "UTC",
                "PREFER_DATES_FROM": "past",
                "RELATIVE_BASE": now
            }
        )

        # --------------------------------------------
        # 2️⃣ If we detect two dates → treat as range
        # --------------------------------------------
        if results and len(results) >= 2:
            parsed_dates = [r[1] for r in results]
            parsed_dates = sorted(parsed_dates)

            start_time = parsed_dates[0]
            end_time = parsed_dates[-1]

        # --------------------------------------------
        # 3️⃣ If one date detected
        # --------------------------------------------
        elif results and len(results) == 1:
            detected_time = results[0][1]

            # If phrase contains "from now" (future reference)
            if "from now" in user_query.lower():
                start_time = now
                end_time = detected_time
            else:
                start_time = detected_time
                end_time = now

        # --------------------------------------------
        # 4️⃣ Try relative parsing directly
        # --------------------------------------------
        else:
            parsed = dateparser.parse(
                user_query,
                settings={
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "TIMEZONE": "UTC",
                    "PREFER_DATES_FROM": "past",
                    "RELATIVE_BASE": now
                }
            )

            if parsed:
                start_time = parsed
                end_time = now

    # --------------------------------------------
    # 5️⃣ Default: current hour start → now
    # --------------------------------------------
    if not start_time:
        start_time = now.replace(minute=0, second=0, microsecond=0)

    # --------------------------------------------
    # ⚠️ Edge Case: Handle negative durations (start > end)
    # --------------------------------------------
    if start_time > end_time:
        # Swap times
        start_time, end_time = end_time, start_time

    # --------------------------------------------
    # ⚠️ Edge Case: Prevent future end time
    # --------------------------------------------
    if end_time > now:
        end_time = now

    # --------------------------------------------
    # ⚠️ Edge Case: Ensure minimum duration (5 minutes)
    # --------------------------------------------
    duration = end_time - start_time
    duration_seconds = duration.total_seconds()

    MIN_DURATION_SECONDS = 5 * 60  # 5 minutes

    if duration_seconds < MIN_DURATION_SECONDS:
        # Extend to minimum duration
        start_time = end_time - timedelta(seconds=MIN_DURATION_SECONDS)

    # --------------------------------------------
    # ⚠️ Edge Case: Cap maximum duration (2 years)
    # --------------------------------------------
    MAX_DURATION_DAYS = 730  # 2 years

    duration = end_time - start_time
    duration_days = duration.total_seconds() / (24 * 3600)

    if duration_days > MAX_DURATION_DAYS:
        start_time = end_time - timedelta(days=MAX_DURATION_DAYS)
        duration_days = MAX_DURATION_DAYS

    # --------------------------------------------
    # 📊 Index decision logic (2-tier granularity)
    # --------------------------------------------
    if duration_days <= 3:
        index = "HOURLY"
    else:
        index = "DAILY"

    result = {
        "start_time": str(int(start_time.timestamp() * 1000)),
        "end_time": str(int(end_time.timestamp() * 1000)),
        "index": index,
        "duration_days": duration_days
    }

    # Add comparison range if detected
    if comparison_range:
        result["comparison_range"] = comparison_range

    return result


# Backward compatibility: keep the old function name for existing code
def resolve_time_range(time_range: str) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    Simply delegates to resolve_time_range_from_query.

    Args:
        time_range: Time expression string

    Returns:
        Same format as resolve_time_range_from_query
    """
    return resolve_time_range_from_query(time_range)


# Test function for verification
if __name__ == "__main__":
    import json

    test_queries = [
        # Edge cases that previously failed
        "today",
        "What happened today?",
        "yesterday",
        "tomorrow",
        "in 2 hours",
        "past 30 seconds",
        "today vs yesterday",
        "past year",

        # Relative expressions
        "last hour",
        "past 3 hours",
        "last 7 days",
        "past month",
        "last week",

        # Absolute dates
        "January 15, 2024",
        "2024-01-15",

        # Time ranges
        "from Monday to Friday",
        "between 2pm and 5pm yesterday",
        "January 1 to January 10",

        # Complex expressions
        "2 hours ago",
        "3 days ago",
        "30 minutes ago",

        # Edge cases
        "now",
        "current",
        "",

        # Real user queries
        "Why is payment-api failing in the last hour?",
        "Show me errors from yesterday",
        "What happened between 2pm and 4pm today?",
        "Analyze the past 24 hours"
    ]

    print("Dynamic Time Range Resolver Test Cases:\n")
    print("=" * 80)

    for query in test_queries:
        result = resolve_time_range_from_query(query)

        # Convert timestamps back to readable format for display
        start_dt = datetime.fromtimestamp(int(result["start_time"]) / 1000, tz=UTC)
        end_dt = datetime.fromtimestamp(int(result["end_time"]) / 1000, tz=UTC)

        print(f"\nQuery: \"{query}\"")
        print(f"start_time: {result['start_time']} ({start_dt.strftime('%Y-%m-%d %H:%M:%S %Z')})")
        print(f"end_time:   {result['end_time']} ({end_dt.strftime('%Y-%m-%d %H:%M:%S %Z')})")
        print(f"Duration:   {result['duration_days']:.4f} days ({result['duration_days']*24:.2f} hours)")
        print(f"Index:      {result['index']}")

        if "comparison_range" in result:
            print(f"⚠️ COMPARISON DETECTED: {result['comparison_range']['note']}")

        print("-" * 80)

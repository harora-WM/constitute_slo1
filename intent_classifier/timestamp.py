#!/usr/bin/env python3
"""
Time Range Resolution Module
Converts natural language time ranges to exact UTC timestamps and determines appropriate index granularity
"""

from datetime import datetime, timedelta
from typing import Dict, Tuple, Any
import pytz
import re

class TimestampResolver:
    """Resolves time ranges to UTC timestamps and determines index granularity"""
    
    # Time range patterns and their durations in days
    TIME_PATTERNS = {
        'today': 1,
        'yesterday': 1,
        'this_week': 7,
        'last_week': 7,
        'this_month': 30,
        'last_month': 30,
        'last_3_days': 3,
        'last_7_days': 7,
        'last_30_days': 30,
        'last_hour': 0.04,  # ~1 hour
        'last_24_hours': 1,
        'current': 0.04,  # Treated as last_hour
    }
    
    def __init__(self):
        """Initialize the timestamp resolver"""
        self.utc = pytz.UTC
    
    def resolve_time_range(self, time_range: str = None, comparison_range: str = None) -> Dict[str, Any]:
        """
        Resolve time range to exact UTC timestamps and determine index granularity

        Logic:
        - If TimeRange != NULL: Evaluate StartTime and EndTime
        - Else: Current = Past 1 hour

        Args:
            time_range: Time range string (e.g., "last_7_days", "today") or None
            comparison_range: Optional comparison range (e.g., "previous_7_days")

        Returns:
            Dictionary with resolved timestamps and index information
        """
        now = datetime.now(self.utc)

        # If TimeRange is NULL, default to past 1 hour
        if time_range is None or time_range == "":
            time_range = "last_hour"

        # Parse primary time range
        primary_result = self._parse_time_range(time_range, now)

        # Parse comparison range if provided
        comparison_result = None
        if comparison_range:
            comparison_result = self._parse_time_range(comparison_range, now)

        # Determine index based on duration
        duration_days = primary_result['duration_days']
        index = self._determine_index(duration_days)

        # Format comparison range if it exists
        formatted_comparison = None
        if comparison_result:
            formatted_comparison = {
                'time_range': comparison_range,
                'start_time': self._to_unix_timestamp_ms(comparison_result['start_time']),
                'end_time': self._to_unix_timestamp_ms(comparison_result['end_time']),
                'duration_days': comparison_result['duration_days'],
            }

        return {
            'primary_range': {
                'time_range': time_range,
                'start_time': self._to_unix_timestamp_ms(primary_result['start_time']),
                'end_time': self._to_unix_timestamp_ms(primary_result['end_time']),
                'duration_days': duration_days,
            },
            'comparison_range': formatted_comparison,
            'index': index,
            'index_reason': f"Duration: {duration_days} days → {index} granularity"
        }
    
    def _parse_time_range(self, time_range: str, now: datetime) -> Dict[str, Any]:
        """
        Parse a time range string to start and end times

        Supports:
        - Static ranges: 'today', 'yesterday', 'last_week', etc.
        - Dynamic ranges: 'past_10_days', 'past_5_hours', 'past_2_weeks', 'past_3_months'
        """
        time_range_lower = time_range.lower().strip()

        # Try to parse dynamic time ranges first (e.g., past_10_days, past_5_hours)
        dynamic_result = self._parse_dynamic_time_range(time_range_lower, now)
        if dynamic_result:
            return dynamic_result

        # Static time range patterns
        if time_range_lower == 'today':
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
            duration_days = 1

        elif time_range_lower == 'yesterday':
            yesterday = now - timedelta(days=1)
            start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            duration_days = 1

        elif time_range_lower == 'this_week':
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
            end_time = now
            duration_days = 7

        elif time_range_lower == 'last_week':
            end_time = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
            start_time = end_time - timedelta(days=7)
            duration_days = 7

        elif time_range_lower == 'last_3_days':
            start_time = (now - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
            duration_days = 3

        elif time_range_lower == 'last_7_days':
            start_time = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
            duration_days = 7

        elif time_range_lower == 'last_30_days':
            start_time = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
            duration_days = 30

        elif time_range_lower == 'last_month' or time_range_lower == 'this_month':
            # Last month: 30 days
            start_time = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
            duration_days = 30

        elif time_range_lower == 'last_hour':
            start_time = now - timedelta(hours=1)
            end_time = now
            duration_days = 0.04

        elif time_range_lower == 'current':
            # Treat "current" as "last_hour" for practical data fetching
            start_time = now - timedelta(hours=1)
            end_time = now
            duration_days = 0.04

        else:
            # Default to last_hour (same as "current")
            start_time = now - timedelta(hours=1)
            end_time = now
            duration_days = 0.04

        return {
            'start_time': start_time,
            'end_time': end_time,
            'duration_days': duration_days
        }

    def _parse_dynamic_time_range(self, time_range: str, now: datetime) -> Dict[str, Any]:
        """
        Parse dynamic time ranges like 'past_10_days', 'past_5_hours', 'past_2_weeks', 'past_3_months'

        Patterns supported:
        - past_N_days / past_N_day
        - past_N_hours / past_N_hour
        - past_N_weeks / past_N_week
        - past_N_months / past_N_month

        Returns:
            Dictionary with start_time, end_time, duration_days or None if pattern doesn't match
        """
        # Regex pattern to match: past_<number>_<unit>
        # Supports both singular and plural forms
        pattern = r'past[_\s](\d+)[_\s](day|days|hour|hours|week|weeks|month|months)'
        match = re.match(pattern, time_range)

        if not match:
            return None

        number = int(match.group(1))
        unit = match.group(2)

        # Normalize unit to singular form
        if unit.endswith('s'):
            unit = unit[:-1]

        # Calculate start_time, end_time, and duration_days based on unit
        if unit == 'hour':
            start_time = now - timedelta(hours=number)
            end_time = now
            duration_days = number / 24.0  # Convert hours to days

        elif unit == 'day':
            start_time = (now - timedelta(days=number)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
            duration_days = number

        elif unit == 'week':
            days = number * 7
            start_time = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
            duration_days = days

        elif unit == 'month':
            days = number * 30  # Approximate month as 30 days
            start_time = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now
            duration_days = days

        else:
            return None

        return {
            'start_time': start_time,
            'end_time': end_time,
            'duration_days': duration_days
        }
    
    def _determine_index(self, duration_days: float) -> str:
        """
        Determine appropriate index granularity based on duration

        Rules:
        - <= 3 days: HOURLY
        - > 3 days: DAILY
        """
        if duration_days <= 3:
            return "HOURLY"
        else:
            return "DAILY"

    def _format_timestamp(self, dt: datetime) -> str:
        """
        Format datetime to simple readable format
        Format: YYYY-MM-DD HH:MM:SS

        Args:
            dt: datetime object

        Returns:
            Formatted timestamp string
        """
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _to_unix_timestamp_ms(self, dt: datetime) -> int:
        """
        Convert datetime to Unix timestamp in milliseconds

        Args:
            dt: datetime object

        Returns:
            Unix timestamp in milliseconds
        """
        return int(dt.timestamp() * 1000)


def main():
    """Test the timestamp resolver"""
    resolver = TimestampResolver()

    # Test cases
    test_cases = [
        ("today", None),
        ("last_3_days", "previous_3_days"),
        ("last_7_days", None),
        ("last_30_days", None),
        ("last_hour", None),
        (None, None),  # Test NULL case - should default to last_hour
        # Dynamic time ranges
        ("past_10_days", None),
        ("past_5_hours", None),
        ("past_2_weeks", None),
        ("past_3_months", None),
        ("past 15 days", None),  # Test with space separator
    ]

    print("\n" + "="*80)
    print("TIMESTAMP RESOLUTION TEST")
    print("="*80)

    for time_range, comparison_range in test_cases:
        result = resolver.resolve_time_range(time_range, comparison_range)
        print(f"\n📅 Time Range: {time_range if time_range else 'NULL (defaults to last_hour)'}")
        print(f"   start_time = {result['primary_range']['start_time']}")
        print(f"   end_time   = {result['primary_range']['end_time']}")
        print(f"   index      = {result['index']}")
        if result['comparison_range']:
            print(f"\n   Comparison Range:")
            print(f"   start_time = {result['comparison_range']['start_time']}")
            print(f"   end_time   = {result['comparison_range']['end_time']}")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()

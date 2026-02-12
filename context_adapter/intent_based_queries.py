#!/usr/bin/env python3
"""
Intent-Based Query Functions for AI Service Behavior Memory
Maps specific intents to targeted ClickHouse queries with appropriate pattern_types
"""

import json
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime


# ClickHouse Configuration
CLICKHOUSE_URL = "http://ec2-47-129-241-41.ap-southeast-1.compute.amazonaws.com:8123"
CLICKHOUSE_USER = "wm_test"
CLICKHOUSE_PASSWORD = "Watermelon@123"
CLICKHOUSE_DB = "metrics"
CLICKHOUSE_TABLE = "ai_service_behavior_memory"


def ms_to_datetime_str(timestamp_ms: int) -> str:
    """Convert Unix timestamp in milliseconds to ClickHouse datetime string"""
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def execute_clickhouse_query(query: str) -> List[Dict[str, Any]]:
    """
    Execute a ClickHouse query and return results

    Args:
        query: SQL query string

    Returns:
        List of result rows as dictionaries
    """
    try:
        response = requests.get(
            CLICKHOUSE_URL,
            auth=(CLICKHOUSE_USER, CLICKHOUSE_PASSWORD),
            params={
                "query": query.strip(),
                "database": CLICKHOUSE_DB
            },
            timeout=30
        )
        response.raise_for_status()

        rows = [
            json.loads(line)
            for line in response.text.strip().split("\n")
            if line.strip()
        ]

        return rows

    except requests.exceptions.Timeout as e:
        print(f"✗ ClickHouse timeout after 30s: {e}")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"✗ ClickHouse HTTP error {e.response.status_code}: {e.response.text}")
        return []
    except Exception as e:
        print(f"✗ Unexpected error: {type(e).__name__}: {e}")
        return []


# ========================================================================
# INTENT-SPECIFIC QUERY FUNCTIONS
# ========================================================================

def query_undercurrents_trend(
    start_time: int,
    end_time: int,
    app_id: int,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    UNDERCURRENTS_TREND: Find gradual drift and sudden changes

    Logic:
    - Last 24 hours → pattern_type: 'drift_up', 'drift_down'
    - Last 1 hour → pattern_type: 'sudden_spike', 'sudden_drop'

    Args:
        start_time: Start time in Unix milliseconds
        end_time: End time in Unix milliseconds
        app_id: Application ID
        service_id: Optional service ID
        service_name: Optional service name

    Returns:
        Dictionary with drift and sudden change patterns
    """
    start_dt = ms_to_datetime_str(start_time)
    end_dt = ms_to_datetime_str(end_time)

    # Calculate duration to determine pattern type
    duration_hours = (end_time - start_time) / (1000 * 60 * 60)

    # Choose pattern types based on duration
    # STRICT: sudden patterns ONLY for ≤1 hour, drift ONLY for >1 hour
    if duration_hours <= 1:
        # Last 1 hour or "current" → sudden changes ONLY
        pattern_types = ['sudden_spike', 'sudden_drop']
        pattern_category = 'sudden_changes'
    else:
        # > 1 hour → drift patterns ONLY
        pattern_types = ['drift_up', 'drift_down']
        pattern_category = 'drift'

    # Build WHERE clause
    # Check if pattern overlaps with query window
    where_conditions = [
        f"application_id = {app_id}",
        f"pattern_type IN {tuple(pattern_types)}",
        f"(first_seen <= toDateTime('{end_dt}') AND last_seen >= toDateTime('{start_dt}'))"
    ]

    if service_id:
        where_conditions.append(f"service_id = {service_id}")
    elif service_name:
        where_conditions.append(f"service = '{service_name}'")

    where_clause = " AND ".join(where_conditions)

    query = f"""
    SELECT
        application_id,
        service_id,
        service,
        metric,
        baseline_state,
        baseline_value,
        pattern_type,
        pattern_window,
        delta_success,
        delta_latency_p90,
        support_days,
        confidence,
        long_term,
        recency,
        first_seen,
        last_seen,
        detected_at
    FROM {CLICKHOUSE_TABLE}
    WHERE {where_clause}
    ORDER BY confidence DESC, detected_at DESC
    FORMAT JSONEachRow
    """

    rows = execute_clickhouse_query(query)

    return {
        "intent": "UNDERCURRENTS_TREND",
        "pattern_category": pattern_category,
        "pattern_types": pattern_types,
        "duration_hours": duration_hours,
        "total_records": len(rows),
        "patterns": rows,
        "query_window": {
            "start_time": start_time,
            "end_time": end_time,
            "start_dt": start_dt,
            "end_dt": end_dt
        }
    }


def query_capacity_risk(
    start_time: int,
    end_time: int,
    app_id: int,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    CAPACITY_RISK: Find volume-driven patterns that indicate capacity issues

    Logic:
    - pattern_type: 'volume_driven'

    Args:
        start_time: Start time in Unix milliseconds
        end_time: End time in Unix milliseconds
        app_id: Application ID
        service_id: Optional service ID
        service_name: Optional service name

    Returns:
        Dictionary with volume-driven patterns
    """
    start_dt = ms_to_datetime_str(start_time)
    end_dt = ms_to_datetime_str(end_time)

    # Build WHERE clause
    # For capacity risk, we want patterns that are currently relevant
    # So we check if the pattern overlaps with our time window OR was recently detected
    where_conditions = [
        f"application_id = {app_id}",
        f"pattern_type = 'volume_driven'",
        # Pattern overlaps with query window: (first_seen <= end AND last_seen >= start)
        f"(first_seen <= toDateTime('{end_dt}') AND last_seen >= toDateTime('{start_dt}'))"
    ]

    if service_id:
        where_conditions.append(f"service_id = {service_id}")
    elif service_name:
        where_conditions.append(f"service = '{service_name}'")

    where_clause = " AND ".join(where_conditions)

    query = f"""
    SELECT
        application_id,
        service_id,
        service,
        metric,
        baseline_state,
        baseline_value,
        pattern_type,
        pattern_window,
        delta_success,
        delta_latency_p90,
        support_days,
        confidence,
        long_term,
        recency,
        first_seen,
        last_seen,
        detected_at
    FROM {CLICKHOUSE_TABLE}
    WHERE {where_clause}
    ORDER BY confidence DESC, baseline_state DESC
    FORMAT JSONEachRow
    """

    rows = execute_clickhouse_query(query)

    # Categorize by baseline_state
    chronic = [r for r in rows if r.get('baseline_state') == 'CHRONIC']
    at_risk = [r for r in rows if r.get('baseline_state') == 'AT_RISK']
    healthy = [r for r in rows if r.get('baseline_state') == 'HEALTHY']

    return {
        "intent": "CAPACITY_RISK",
        "pattern_type": "volume_driven",
        "total_records": len(rows),
        "stats": {
            "chronic": len(chronic),
            "at_risk": len(at_risk),
            "healthy": len(healthy)
        },
        "patterns": {
            "chronic": chronic,
            "at_risk": at_risk,
            "healthy": healthy
        },
        "query_window": {
            "start_time": start_time,
            "end_time": end_time,
            "start_dt": start_dt,
            "end_dt": end_dt
        }
    }


def query_seasonality_pattern(
    start_time: int,
    end_time: int,
    app_id: int,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    SEASONALITY_PATTERN: Find weekly recurring patterns (e.g., "Every Thursday issues?")

    Logic:
    - pattern_type: 'weekly'
    - Group by day of week to show patterns

    Args:
        start_time: Start time in Unix milliseconds
        end_time: End time in Unix milliseconds
        app_id: Application ID
        service_id: Optional service ID
        service_name: Optional service name

    Returns:
        Dictionary with weekly patterns grouped by day
    """
    start_dt = ms_to_datetime_str(start_time)
    end_dt = ms_to_datetime_str(end_time)

    # Build WHERE clause
    # Pattern overlaps with query window
    where_conditions = [
        f"application_id = {app_id}",
        f"pattern_type = 'weekly'",
        f"(first_seen <= toDateTime('{end_dt}') AND last_seen >= toDateTime('{start_dt}'))"
    ]

    if service_id:
        where_conditions.append(f"service_id = {service_id}")
    elif service_name:
        where_conditions.append(f"service = '{service_name}'")

    where_clause = " AND ".join(where_conditions)

    query = f"""
    SELECT
        application_id,
        service_id,
        service,
        metric,
        baseline_state,
        baseline_value,
        pattern_type,
        pattern_window,
        delta_success,
        delta_latency_p90,
        support_days,
        confidence,
        long_term,
        recency,
        first_seen,
        last_seen,
        detected_at,
        toDayOfWeek(detected_at) as day_of_week
    FROM {CLICKHOUSE_TABLE}
    WHERE {where_clause}
    ORDER BY day_of_week, confidence DESC
    FORMAT JSONEachRow
    """

    rows = execute_clickhouse_query(query)

    # Group by day of week
    day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
                 5: "Friday", 6: "Saturday", 7: "Sunday"}

    patterns_by_day = {}
    for row in rows:
        day_num = row.get('day_of_week', 0)
        day_name = day_names.get(day_num, f"Day{day_num}")

        if day_name not in patterns_by_day:
            patterns_by_day[day_name] = []

        patterns_by_day[day_name].append(row)

    return {
        "intent": "SEASONALITY_PATTERN",
        "pattern_type": "weekly",
        "total_records": len(rows),
        "patterns_by_day": patterns_by_day,
        "summary": {day: len(patterns) for day, patterns in patterns_by_day.items()},
        "query_window": {
            "start_time": start_time,
            "end_time": end_time,
            "start_dt": start_dt,
            "end_dt": end_dt
        }
    }


def query_time_window_anomaly(
    start_time: int,
    end_time: int,
    app_id: int,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    TIME_WINDOW_ANOMALY: Find daily recurring patterns (e.g., "Daily 4-5 PM problems?")

    Logic:
    - pattern_type: 'daily'
    - Group by hour of day to show patterns

    Args:
        start_time: Start time in Unix milliseconds
        end_time: End time in Unix milliseconds
        app_id: Application ID
        service_id: Optional service ID
        service_name: Optional service name

    Returns:
        Dictionary with daily patterns grouped by hour
    """
    start_dt = ms_to_datetime_str(start_time)
    end_dt = ms_to_datetime_str(end_time)

    # Build WHERE clause
    # Pattern overlaps with query window
    where_conditions = [
        f"application_id = {app_id}",
        f"pattern_type = 'daily'",
        f"(first_seen <= toDateTime('{end_dt}') AND last_seen >= toDateTime('{start_dt}'))"
    ]

    if service_id:
        where_conditions.append(f"service_id = {service_id}")
    elif service_name:
        where_conditions.append(f"service = '{service_name}'")

    where_clause = " AND ".join(where_conditions)

    query = f"""
    SELECT
        application_id,
        service_id,
        service,
        metric,
        baseline_state,
        baseline_value,
        pattern_type,
        pattern_window,
        delta_success,
        delta_latency_p90,
        support_days,
        confidence,
        long_term,
        recency,
        first_seen,
        last_seen,
        detected_at,
        toHour(detected_at) as hour_of_day
    FROM {CLICKHOUSE_TABLE}
    WHERE {where_clause}
    ORDER BY hour_of_day, confidence DESC
    FORMAT JSONEachRow
    """

    rows = execute_clickhouse_query(query)

    # Group by hour of day
    patterns_by_hour = {}
    for row in rows:
        hour = row.get('hour_of_day', 0)
        hour_label = f"{hour:02d}:00-{(hour+1)%24:02d}:00"

        if hour_label not in patterns_by_hour:
            patterns_by_hour[hour_label] = []

        patterns_by_hour[hour_label].append(row)

    return {
        "intent": "TIME_WINDOW_ANOMALY",
        "pattern_type": "daily",
        "total_records": len(rows),
        "patterns_by_hour": patterns_by_hour,
        "summary": {hour: len(patterns) for hour, patterns in patterns_by_hour.items()},
        "query_window": {
            "start_time": start_time,
            "end_time": end_time,
            "start_dt": start_dt,
            "end_dt": end_dt
        }
    }


def query_recurring_incident(
    incident_timestamp: int,
    app_id: int,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    RECURRING_INCIDENT: Find similar patterns before a given incident timestamp

    Logic:
    - Given timestamp X, find daily and weekly patterns that occurred BEFORE X
    - pattern_type: 'daily' OR 'weekly'
    - last_seen < incident_timestamp

    Args:
        incident_timestamp: Incident time in Unix milliseconds
        app_id: Application ID
        service_id: Optional service ID
        service_name: Optional service name

    Returns:
        Dictionary with historical daily and weekly patterns
    """
    incident_dt = ms_to_datetime_str(incident_timestamp)

    # Build WHERE clause
    where_conditions = [
        f"application_id = {app_id}",
        f"last_seen < toDateTime('{incident_dt}')",
        "pattern_type IN ('daily', 'weekly')"
    ]

    if service_id:
        where_conditions.append(f"service_id = {service_id}")
    elif service_name:
        where_conditions.append(f"service = '{service_name}'")

    where_clause = " AND ".join(where_conditions)

    query = f"""
    SELECT
        application_id,
        service_id,
        service,
        metric,
        baseline_state,
        baseline_value,
        pattern_type,
        pattern_window,
        delta_success,
        delta_latency_p90,
        support_days,
        confidence,
        long_term,
        recency,
        first_seen,
        last_seen,
        detected_at
    FROM {CLICKHOUSE_TABLE}
    WHERE {where_clause}
    ORDER BY pattern_type, confidence DESC, detected_at DESC
    FORMAT JSONEachRow
    """

    rows = execute_clickhouse_query(query)

    # Separate by pattern type
    daily_patterns = [r for r in rows if r.get('pattern_type') == 'daily']
    weekly_patterns = [r for r in rows if r.get('pattern_type') == 'weekly']

    return {
        "intent": "RECURRING_INCIDENT",
        "incident_timestamp": incident_timestamp,
        "incident_dt": incident_dt,
        "total_records": len(rows),
        "stats": {
            "daily_patterns": len(daily_patterns),
            "weekly_patterns": len(weekly_patterns)
        },
        "patterns": {
            "daily": daily_patterns,
            "weekly": weekly_patterns
        }
    }


def query_historical_comparison(
    start_time: int,
    end_time: int,
    app_id: int,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    HISTORICAL_COMPARISON: Compare current period with historical data

    Status: UNDER PROGRESS
    TODO: Implement comparison logic

    Args:
        start_time: Start time in Unix milliseconds
        end_time: End time in Unix milliseconds
        app_id: Application ID
        service_id: Optional service ID
        service_name: Optional service name

    Returns:
        Dictionary with comparison results
    """
    return {
        "intent": "HISTORICAL_COMPARISON",
        "status": "under_progress",
        "message": "Historical comparison logic not yet implemented"
    }


def query_risk_prediction(
    start_time: int,
    end_time: int,
    app_id: int,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    RISK_PREDICTION: Predict potential failures based on patterns

    Status: UNDER PROGRESS
    TODO: Implement prediction logic

    Args:
        start_time: Start time in Unix milliseconds
        end_time: End time in Unix milliseconds
        app_id: Application ID
        service_id: Optional service ID
        service_name: Optional service name

    Returns:
        Dictionary with risk predictions
    """
    return {
        "intent": "RISK_PREDICTION",
        "status": "under_progress",
        "message": "Risk prediction logic not yet implemented"
    }


# ========================================================================
# INTENT DISPATCHER
# ========================================================================

INTENT_FUNCTION_MAP = {
    "UNDERCURRENTS_TREND": query_undercurrents_trend,
    "CAPACITY_RISK": query_capacity_risk,
    "SEASONALITY_PATTERN": query_seasonality_pattern,
    "TIME_WINDOW_ANOMALY": query_time_window_anomaly,
    "RECURRING_INCIDENT": query_recurring_incident,
    "HISTORICAL_COMPARISON": query_historical_comparison,
    "RISK_PREDICTION": query_risk_prediction,
}


def dispatch_intent_query(
    intent: str,
    start_time: int,
    end_time: int,
    app_id: int,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None,
    incident_timestamp: Optional[int] = None
) -> Dict[str, Any]:
    """
    Dispatch query to appropriate function based on intent

    Args:
        intent: Intent name (e.g., "UNDERCURRENTS_TREND")
        start_time: Start time in Unix milliseconds
        end_time: End time in Unix milliseconds
        app_id: Application ID
        service_id: Optional service ID
        service_name: Optional service name
        incident_timestamp: For RECURRING_INCIDENT only

    Returns:
        Query results from intent-specific function
    """
    if intent not in INTENT_FUNCTION_MAP:
        return {
            "error": f"Unknown intent: {intent}",
            "available_intents": list(INTENT_FUNCTION_MAP.keys())
        }

    query_function = INTENT_FUNCTION_MAP[intent]

    # RECURRING_INCIDENT uses incident_timestamp instead of start/end
    if intent == "RECURRING_INCIDENT":
        if not incident_timestamp:
            return {"error": "RECURRING_INCIDENT requires incident_timestamp"}
        return query_function(incident_timestamp, app_id, service_id, service_name)

    # All other intents use start/end time
    return query_function(start_time, end_time, app_id, service_id, service_name)


# ========================================================================
# MAIN - Testing
# ========================================================================

if __name__ == "__main__":
    from datetime import datetime, timedelta
    import pytz

    # Test parameters
    APP_ID = 31854

    # Time range: last 7 days
    now = datetime.now(pytz.UTC)
    end_time = int(now.timestamp() * 1000)
    start_time = int((now - timedelta(days=7)).timestamp() * 1000)

    print("=" * 80)
    print("INTENT-BASED QUERY TESTING")
    print("=" * 80)
    print(f"\nApplication ID: {APP_ID}")
    print(f"Time Range: Last 7 days")
    print()

    # Test each intent
    test_intents = [
        "UNDERCURRENTS_TREND",
        "CAPACITY_RISK",
        "SEASONALITY_PATTERN",
        "TIME_WINDOW_ANOMALY"
    ]

    for intent in test_intents:
        print(f"\n{'='*80}")
        print(f"Testing: {intent}")
        print(f"{'='*80}")

        result = dispatch_intent_query(
            intent=intent,
            start_time=start_time,
            end_time=end_time,
            app_id=APP_ID
        )

        print(f"Total Records: {result.get('total_records', 0)}")
        if 'stats' in result:
            print(f"Stats: {result['stats']}")
        if 'summary' in result:
            print(f"Summary: {result['summary']}")

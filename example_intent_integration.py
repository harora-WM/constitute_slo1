#!/usr/bin/env python3
"""
Example: Integrating Intent-Based Queries with Orchestrator
Shows how to route intents to specific ClickHouse query functions
"""

from context_adapter.intent_based_queries import dispatch_intent_query
from datetime import datetime, timedelta
import pytz


def example_orchestrator_integration():
    """
    Example showing how orchestrator should route intents to query functions
    """

    # Simulated intent classifier output
    classification_result = {
        "primary_intent": "SEASONALITY_PATTERN",
        "secondary_intents": ["TIME_WINDOW_ANOMALY"],
        "enriched_intents": ["SEASONALITY_PATTERN", "TIME_WINDOW_ANOMALY", "RISK_PREDICTION"],
        "entities": {
            "service": None,
            "time_range": "last_7_days"
        }
    }

    # Time resolution (simulated)
    now = datetime.now(pytz.UTC)
    end_time = int(now.timestamp() * 1000)
    start_time = int((now - timedelta(days=7)).timestamp() * 1000)

    # Application ID
    APP_ID = 31854

    print("=" * 80)
    print("ORCHESTRATOR INTENT ROUTING EXAMPLE")
    print("=" * 80)
    print(f"\nQuery Classification:")
    print(f"  Primary Intent: {classification_result['primary_intent']}")
    print(f"  Secondary Intents: {classification_result['secondary_intents']}")
    print(f"  Enriched Intents: {classification_result['enriched_intents']}")
    print()

    # Collect all unique intents
    all_intents = set([classification_result['primary_intent']] +
                      classification_result['secondary_intents'] +
                      classification_result['enriched_intents'])

    # Pattern/trend intents that require ClickHouse memory adapter
    pattern_intents = {
        "UNDERCURRENTS_TREND",
        "CAPACITY_RISK",
        "SEASONALITY_PATTERN",
        "TIME_WINDOW_ANOMALY",
        "RECURRING_INCIDENT",
        "HISTORICAL_COMPARISON",
        "RISK_PREDICTION"
    }

    # Find which pattern intents are present
    intents_to_query = all_intents.intersection(pattern_intents)

    print(f"Pattern Intents Detected: {intents_to_query}")
    print()

    # Execute queries for each pattern intent
    results = {}
    for intent in intents_to_query:
        print(f"{'=' * 80}")
        print(f"Executing query for: {intent}")
        print(f"{'=' * 80}")

        result = dispatch_intent_query(
            intent=intent,
            start_time=start_time,
            end_time=end_time,
            app_id=APP_ID,
            service_id=None,
            service_name=None
        )

        results[intent] = result

        # Print summary
        if result.get('status') == 'under_progress':
            print(f"  Status: {result.get('message')}")
        else:
            print(f"  Total Records: {result.get('total_records', 0)}")
            if 'stats' in result:
                print(f"  Stats: {result['stats']}")
            if 'summary' in result:
                print(f"  Summary: {result['summary']}")
        print()

    return results


def example_specific_intents():
    """
    Examples of specific intent queries
    """
    APP_ID = 31854
    now = datetime.now(pytz.UTC)
    end_time = int(now.timestamp() * 1000)

    print("\n" + "=" * 80)
    print("SPECIFIC INTENT EXAMPLES")
    print("=" * 80)

    # Example 1: Find weekly patterns (seasonality)
    print("\n1. SEASONALITY_PATTERN - 'Do we have issues every Thursday?'")
    start_time = int((now - timedelta(days=30)).timestamp() * 1000)
    result = dispatch_intent_query(
        intent="SEASONALITY_PATTERN",
        start_time=start_time,
        end_time=end_time,
        app_id=APP_ID
    )
    print(f"   Found {result['total_records']} weekly patterns")
    if result.get('summary'):
        print(f"   By day: {result['summary']}")

    # Example 2: Find daily time window patterns
    print("\n2. TIME_WINDOW_ANOMALY - 'Problems between 4-5 PM daily?'")
    start_time = int((now - timedelta(days=7)).timestamp() * 1000)
    result = dispatch_intent_query(
        intent="TIME_WINDOW_ANOMALY",
        start_time=start_time,
        end_time=end_time,
        app_id=APP_ID
    )
    print(f"   Found {result['total_records']} daily patterns")
    if result.get('summary'):
        print(f"   By hour: {result['summary']}")

    # Example 3: Find capacity risks
    print("\n3. CAPACITY_RISK - 'Will traffic spike cause issues?'")
    start_time = int((now - timedelta(days=7)).timestamp() * 1000)
    result = dispatch_intent_query(
        intent="CAPACITY_RISK",
        start_time=start_time,
        end_time=end_time,
        app_id=APP_ID
    )
    print(f"   Found {result['total_records']} volume-driven patterns")
    if result.get('stats'):
        print(f"   Stats: {result['stats']}")

    # Example 4: Find undercurrents/drift
    print("\n4. UNDERCURRENTS_TREND - 'What's drifting in last 24h?'")
    start_time = int((now - timedelta(hours=24)).timestamp() * 1000)
    result = dispatch_intent_query(
        intent="UNDERCURRENTS_TREND",
        start_time=start_time,
        end_time=end_time,
        app_id=APP_ID
    )
    print(f"   Found {result['total_records']} drift/sudden change patterns")
    print(f"   Category: {result.get('pattern_category')}")

    # Example 5: Recurring incident check
    print("\n5. RECURRING_INCIDENT - 'Have we seen this before?'")
    incident_time = int(now.timestamp() * 1000)
    result = dispatch_intent_query(
        intent="RECURRING_INCIDENT",
        start_time=0,  # Not used for this intent
        end_time=0,    # Not used for this intent
        app_id=APP_ID,
        incident_timestamp=incident_time
    )
    print(f"   Found {result['total_records']} historical patterns before incident")
    if result.get('stats'):
        print(f"   Stats: {result['stats']}")


def example_with_service_filter():
    """
    Example with service-specific filtering
    """
    APP_ID = 31854
    SERVICE_ID = 32627  # Example service ID
    now = datetime.now(pytz.UTC)
    end_time = int(now.timestamp() * 1000)
    start_time = int((now - timedelta(days=7)).timestamp() * 1000)

    print("\n" + "=" * 80)
    print("SERVICE-SPECIFIC QUERY EXAMPLE")
    print("=" * 80)

    # Query for specific service
    result = dispatch_intent_query(
        intent="SEASONALITY_PATTERN",
        start_time=start_time,
        end_time=end_time,
        app_id=APP_ID,
        service_id=SERVICE_ID
    )

    print(f"\nQuerying for service_id={SERVICE_ID}")
    print(f"Found {result['total_records']} patterns for this service")


if __name__ == "__main__":
    # Run examples
    example_orchestrator_integration()
    example_specific_intents()
    example_with_service_filter()

    print("\n" + "=" * 80)
    print("INTEGRATION COMPLETE")
    print("=" * 80)
    print("\nTo integrate with orchestrator:")
    print("1. After intent classification, identify pattern-related intents")
    print("2. Call dispatch_intent_query() for each intent")
    print("3. Aggregate results and return to user")
    print()
    print("Available intents:")
    print("  - UNDERCURRENTS_TREND (drift/sudden changes)")
    print("  - CAPACITY_RISK (volume-driven patterns)")
    print("  - SEASONALITY_PATTERN (weekly patterns)")
    print("  - TIME_WINDOW_ANOMALY (daily time patterns)")
    print("  - RECURRING_INCIDENT (historical patterns)")
    print("  - HISTORICAL_COMPARISON (under progress)")
    print("  - RISK_PREDICTION (under progress)")

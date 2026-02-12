#!/usr/bin/env python3
"""
Example usage of the SLO Orchestrator
Shows how to use the orchestrator programmatically
"""

import json
from orchestrator import SLOOrchestrator


def example_basic_query():
    """Example 1: Basic query"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic Health Query")
    print("="*80)

    orchestrator = SLOOrchestrator()
    result = orchestrator.process_query("What is the health status in the past 7 days?")

    if result.get('success'):
        print("\n✅ Query successful!")
        print(f"Primary Intent: {result['classification']['primary_intent']}")
        print(f"Data Sources Used: {result['data_sources_used']}")

        # Access java_stats_api data
        if 'java_stats_api' in result['data']:
            java_data = result['data']['java_stats_api']
            stats = java_data.get('stats', {})
            print(f"\nJava Stats Summary:")
            print(f"  - Total SLOs: {stats.get('total_slos', 0)}")
            print(f"  - Unhealthy: {stats.get('unhealthy_slo', 0)}")
            print(f"  - At Risk: {stats.get('at_risk_slo', 0)}")
            print(f"  - Healthy: {stats.get('healthy_slo', 0)}")

        # Access clickhouse data
        if 'clickhouse' in result['data']:
            ch_data = result['data']['clickhouse']
            print(f"\nClickHouse Summary:")
            print(f"  - Total Patterns: {ch_data.get('total_patterns', 0)}")
    else:
        print(f"\n❌ Query failed: {result.get('error')}")


def example_specific_service():
    """Example 2: Query for a specific service"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Specific Service Query")
    print("="*80)

    orchestrator = SLOOrchestrator()

    # Note: The service name can be extracted from the query by the LLM
    # or passed explicitly as a parameter
    result = orchestrator.process_query(
        "Show me error budget for payment-api in the last 10 days",
        service_name="payment-api"  # Optional override
    )

    if result.get('success'):
        print("\n✅ Query successful!")
        print(f"Service: {result['metadata'].get('service', 'N/A')}")
        print(f"Time Range: {result['time_resolution']['time_range']}")


def example_export_to_json():
    """Example 3: Export result to JSON file"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Export to JSON")
    print("="*80)

    orchestrator = SLOOrchestrator()
    result = orchestrator.process_query("What services are unhealthy today?")

    if result.get('success'):
        # Export to file
        output_file = "slo_query_result.json"
        orchestrator.export_to_json(result, output_file)
        print(f"\n✅ Result exported to {output_file}")

        # You can also manually save with custom formatting
        with open("slo_query_pretty.json", 'w') as f:
            json.dump(result, f, indent=2, sort_keys=True)
        print("✅ Pretty result saved to slo_query_pretty.json")


def example_access_raw_data():
    """Example 4: Access raw adapter data"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Access Raw Adapter Data")
    print("="*80)

    orchestrator = SLOOrchestrator()
    result = orchestrator.process_query("Show burn rate trends for the past 7 days")

    if result.get('success') and 'java_stats_api' in result['data']:
        java_data = result['data']['java_stats_api']

        # Access unhealthy services with EB issues
        unhealthy_eb = java_data.get('unhealthy_services_eb', [])
        print(f"\n🔴 Unhealthy Services (Error Budget):")
        for service in unhealthy_eb[:3]:  # Show top 3
            print(f"\n  Service: {service['service']}")
            print(f"    Health: {service['health']}")
            print(f"    Success Rate: {service['success']['rate']}%")
            print(f"    P95 Latency: {service['latency']['p95']}ms")
            print(f"    Burn Rate: {service['risk']['burn_rate']}")

        # Access at-risk services
        at_risk_eb = java_data.get('at_risk_services_eb', [])
        print(f"\n⚠️  At Risk Services (Error Budget): {len(at_risk_eb)}")


def example_multiple_queries():
    """Example 5: Multiple queries in sequence"""
    print("\n" + "="*80)
    print("EXAMPLE 5: Multiple Queries")
    print("="*80)

    orchestrator = SLOOrchestrator()

    queries = [
        "What is the current health status?",
        "Show me error trends in the past 10 days",
        "Are there any services at risk today?"
    ]

    results = []
    for query in queries:
        print(f"\n📝 Processing: {query}")
        result = orchestrator.process_query(query)
        results.append(result)

        if result.get('success'):
            print(f"   ✅ Intent: {result['classification']['primary_intent']}")
        else:
            print(f"   ❌ Error: {result.get('error')}")

    print(f"\n✅ Processed {len(results)} queries")


def example_error_handling():
    """Example 6: Error handling"""
    print("\n" + "="*80)
    print("EXAMPLE 6: Error Handling")
    print("="*80)

    orchestrator = SLOOrchestrator()

    # Try with an unclear query
    result = orchestrator.process_query("xyz abc random")

    if not result.get('success'):
        print(f"❌ Query failed as expected: {result.get('error')}")
        print("This demonstrates the error handling mechanism")
    else:
        print("⚠️  Query succeeded unexpectedly")
        print("The LLM was able to interpret the unclear query")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SLO ORCHESTRATOR - USAGE EXAMPLES")
    print("="*80)
    print("\nThese examples demonstrate different ways to use the orchestrator")
    print("Run each example individually by uncommenting the function call\n")

    try:
        # Run examples
        # Uncomment the examples you want to run:

        example_basic_query()
        # example_specific_service()
        # example_export_to_json()
        # example_access_raw_data()
        # example_multiple_queries()
        # example_error_handling()

        print("\n" + "="*80)
        print("✅ Examples completed!")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()

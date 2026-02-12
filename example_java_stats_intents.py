#!/usr/bin/env python3
"""
Example demonstrating the 3 intent-based java_stats functions.
Shows how CURRENT_HEALTH, SERVICE_HEALTH, and ERROR_BUDGET_STATUS work.
"""

import os
import sys
from dotenv import load_dotenv

# Add project directories to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from context_adapter.java_stats import (
    get_current_health,
    get_service_health,
    get_error_budget_status
)

# Load environment variables
load_dotenv()

# Configuration
USERNAME = os.getenv('JAVA_STATS_USERNAME', 'wmadmin')
PASSWORD = os.getenv('JAVA_STATS_PASSWORD', 'WM@Dm1n@#2024!!$')
APP_ID = 31854
INDEX = 'DAILY'

# Time range (last 7 days) - replace with actual timestamps
START_TIME = '1768049277620'  # Replace with actual start time
END_TIME = '1770641277620'    # Replace with actual end time


def example_current_health():
    """
    Example 1: CURRENT_HEALTH intent
    Get application-wide health status for all services
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: CURRENT_HEALTH Intent")
    print("="*80)
    print("Query: 'What's the current health of my application?'\n")

    result = get_current_health(
        app_id=APP_ID,
        start_time=START_TIME,
        end_time=END_TIME,
        index=INDEX,
        username=USERNAME,
        password=PASSWORD
    )

    if result:
        print("\n✅ Success!")
        print(f"Application: {result['application']}")
        print(f"Time Window: {result['window']['start']} to {result['window']['end']}")
        print(f"\nStats:")
        print(f"  Total SLOs: {result['stats']['total_slos']}")
        print(f"  Unhealthy: {result['stats']['unhealthy_slo']}")
        print(f"  At Risk: {result['stats']['at_risk_slo']}")
        print(f"  Healthy: {result['stats']['healthy_slo']}")
        print(f"\nArrays returned:")
        print(f"  unhealthy_services_eb: {len(result['unhealthy_services_eb'])} services")
        print(f"  at_risk_services_eb: {len(result['at_risk_services_eb'])} services")
        print(f"  unhealthy_services_response: {len(result['unhealthy_services_response'])} services")
        print(f"  at_risk_services_response: {len(result['at_risk_services_response'])} services")
    else:
        print("\n❌ Failed to fetch data")


def example_service_health_with_id():
    """
    Example 2: SERVICE_HEALTH intent with service_id
    Get health for a specific service
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: SERVICE_HEALTH Intent (with service_id)")
    print("="*80)
    print("Query: 'Is payment-api healthy?'\n")

    # Replace with actual service_id from your data
    SERVICE_ID = 12345  # Example service_id

    result = get_service_health(
        app_id=APP_ID,
        start_time=START_TIME,
        end_time=END_TIME,
        service_id=SERVICE_ID,
        index=INDEX,
        username=USERNAME,
        password=PASSWORD
    )

    if result:
        print("\n✅ Success!")
        print(f"Service ID: {result.get('service_id')}")
        print(f"Total records for this service: {result['stats']['total_slos']}")

        if result['unhealthy_services_eb']:
            print("\nUnhealthy EB Status:")
            for service in result['unhealthy_services_eb']:
                print(f"  Service: {service['service']}")
                print(f"  Health: {service['health']}")
                print(f"  Success Rate: {service['success']['rate']}%")
    else:
        print("\n❌ Failed to fetch data or no data found for this service")


def example_service_health_without_id():
    """
    Example 3: SERVICE_HEALTH intent without service_id
    Should return None
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: SERVICE_HEALTH Intent (without service_id)")
    print("="*80)
    print("Query: 'Show me service health' (but no service mentioned)\n")

    result = get_service_health(
        app_id=APP_ID,
        start_time=START_TIME,
        end_time=END_TIME,
        service_id=None,  # No service_id provided
        index=INDEX,
        username=USERNAME,
        password=PASSWORD
    )

    if result is None:
        print("✅ Correct behavior: Returns None when service_id not provided")
    else:
        print("⚠️  Unexpected: Should return None when service_id is missing")


def example_error_budget_status_all():
    """
    Example 4: ERROR_BUDGET_STATUS intent for all services
    Get error budget data (EB category only)
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: ERROR_BUDGET_STATUS Intent (all services)")
    print("="*80)
    print("Query: 'What's the error budget status?'\n")

    result = get_error_budget_status(
        app_id=APP_ID,
        start_time=START_TIME,
        end_time=END_TIME,
        index=INDEX,
        username=USERNAME,
        password=PASSWORD
    )

    if result:
        print("\n✅ Success!")
        print(f"Application: {result['application']}")
        print(f"\nError Budget Stats (EB only):")
        print(f"  Total EB SLOs: {result['stats']['total_eb_slos']}")
        print(f"  EB Unhealthy: {result['stats']['eb_unhealthy']}")
        print(f"  EB At Risk: {result['stats']['eb_at_risk']}")
        print(f"  EB Healthy: {result['stats']['eb_healthy']}")
        print(f"\nArrays returned:")
        print(f"  unhealthy_services_eb: {len(result['unhealthy_services_eb'])} services")
        print(f"  at_risk_services_eb: {len(result['at_risk_services_eb'])} services")
        print(f"  healthy_services_eb: {len(result['healthy_services_eb'])} services")
    else:
        print("\n❌ Failed to fetch data")


def example_error_budget_status_specific():
    """
    Example 5: ERROR_BUDGET_STATUS intent for specific service
    Get error budget data for one service
    """
    print("\n" + "="*80)
    print("EXAMPLE 5: ERROR_BUDGET_STATUS Intent (specific service)")
    print("="*80)
    print("Query: 'Error budget for checkout-service'\n")

    # Replace with actual service_id
    SERVICE_ID = 12345  # Example service_id

    result = get_error_budget_status(
        app_id=APP_ID,
        start_time=START_TIME,
        end_time=END_TIME,
        index=INDEX,
        username=USERNAME,
        password=PASSWORD,
        service_id=SERVICE_ID
    )

    if result:
        print("\n✅ Success!")
        print(f"Service ID: {result.get('service_id')}")
        print(f"Total EB SLOs for this service: {result['stats']['total_eb_slos']}")
    else:
        print("\n❌ Failed to fetch data or no EB data found for this service")


def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("JAVA STATS INTENT-BASED FUNCTIONS - EXAMPLES")
    print("="*80)
    print("\nDemonstrating 3 intent handlers:")
    print("  1. get_current_health() - CURRENT_HEALTH intent")
    print("  2. get_service_health() - SERVICE_HEALTH intent")
    print("  3. get_error_budget_status() - ERROR_BUDGET_STATUS intent")

    # Run examples
    example_current_health()
    example_service_health_with_id()
    example_service_health_without_id()
    example_error_budget_status_all()
    example_error_budget_status_specific()

    print("\n" + "="*80)
    print("EXAMPLES COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Example: How to use ServiceMatcher with Intent Classifier
Shows integration between intent classification and service ID resolution
"""

from utils.service_matcher import ServiceMatcher


def example_integration():
    """
    Example showing how to match service names from intent classifier
    to service IDs from services.yaml
    """

    # Initialize service matcher
    matcher = ServiceMatcher("services.yaml")
    print(f"Loaded {len(matcher.services_by_id)} services\n")

    # ========================================================================
    # Example 1: Simple service name matching
    # ========================================================================
    print("=" * 80)
    print("Example 1: Match 'dashboard-stats'")
    print("=" * 80)

    service_name = "dashboard-stats"
    matches = matcher.find_matches(service_name, threshold=0.3, max_results=5)

    print(f"\nFound {len(matches)} matches for '{service_name}':")
    for match in matches:
        print(f"  • Service ID: {match['service_id']}")
        print(f"    Path: {match['service_path']}")
        print(f"    Score: {match['similarity_score']:.3f}")
        print()

    # ========================================================================
    # Example 2: Get best match only
    # ========================================================================
    print("=" * 80)
    print("Example 2: Get best match for 'wmebonboarding'")
    print("=" * 80)

    service_name = "wmebonboarding"
    best_match = matcher.find_best_match(service_name)

    if best_match:
        print(f"\nBest match:")
        print(f"  Service ID: {best_match['service_id']}")
        print(f"  Path: {best_match['service_path']}")
        print(f"  Score: {best_match['similarity_score']:.3f}")
    else:
        print("No match found")

    # ========================================================================
    # Example 3: Simulate intent classifier output
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 3: Simulate Intent Classifier Integration")
    print("=" * 80)

    # Simulated output from intent classifier
    intent_classifier_output = {
        "primary_intent": "SERVICE_HEALTH",
        "entities": {
            "service": "test-packs",  # This is what intent classifier extracts
            "time_range": "last_7_days"
        }
    }

    extracted_service = intent_classifier_output["entities"]["service"]
    print(f"\nIntent Classifier extracted service: '{extracted_service}'")

    # Match to actual service IDs
    matches = matcher.find_matches(extracted_service, threshold=0.3, max_results=3)

    print(f"\nMatched to {len(matches)} service(s):")
    for i, match in enumerate(matches, 1):
        print(f"\n{i}. Service ID: {match['service_id']}")
        print(f"   Path: {match['service_path']}")
        print(f"   Score: {match['similarity_score']:.3f}")

    # ========================================================================
    # Example 4: Use service IDs in adapter calls
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 4: Using Service IDs in Adapter Calls")
    print("=" * 80)

    service_name = "mobile-devices"
    matches = matcher.find_matches(service_name, max_results=2)

    if matches:
        print(f"\nFor service query '{service_name}':")
        print(f"Found {len(matches)} matching services")

        for match in matches:
            service_id = match['service_id']
            print(f"\n  → Would call Java Stats API with:")
            print(f"     application_id=31854")
            print(f"     service_id={service_id}")
            print(f"     service_path={match['service_path']}")

    # ========================================================================
    # Example 5: Fallback when no service specified
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 5: Handle queries without specific service name")
    print("=" * 80)

    # When intent classifier returns service=None
    extracted_service = None

    if not extracted_service:
        print("\nNo specific service extracted by intent classifier")
        print("→ Fetch data for ALL services (application-level query)")
        print("→ Use application_id=31854 without service_id filter")


def example_orchestrator_integration():
    """
    Example showing how to modify orchestrator to use service matching
    """
    print("\n" + "=" * 80)
    print("ORCHESTRATOR INTEGRATION EXAMPLE")
    print("=" * 80)

    print("""
In your orchestrator.py, add this logic after intent classification:

```python
from utils.service_matcher import ServiceMatcher

class SLOOrchestrator:
    def __init__(self):
        # ... existing code ...
        self.service_matcher = ServiceMatcher("services.yaml")

    def process_query(self, user_query: str):
        # Step 1: Classify intent
        classification_result = self.classifier.classify(user_query)

        # Step 2: Extract service name
        entities = classification_result.get('entities', {})
        service_name = entities.get('service')

        # Step 3: Match to service IDs
        matched_services = []
        if service_name:
            matches = self.service_matcher.find_matches(
                service_name,
                threshold=0.3,
                max_results=5
            )
            matched_services = [m['service_id'] for m in matches]
            print(f"Matched '{service_name}' to service IDs: {matched_services}")

        # Step 4: Pass service IDs to adapters
        if matched_services:
            # Call adapter with specific service IDs
            for service_id in matched_services:
                data = self._fetch_java_stats(service_id=service_id, ...)
        else:
            # Call adapter for all services (application level)
            data = self._fetch_java_stats(service_id=None, ...)
```
    """)


if __name__ == "__main__":
    example_integration()
    example_orchestrator_integration()

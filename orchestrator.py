#!/usr/bin/env python3
"""
SLO Orchestrator
Coordinates intent classification and data fetching from multiple adapters
"""

import os
import sys
import json
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Add project directories to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'intent_classifier'))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'context_adapter'))

from intent_classifier.intent_classifier import IntentClassifier
from context_adapter.java_stats import (
    fetch_api_data,
    transform_to_llm_format,
    get_current_health,
    get_service_health,
    get_error_budget_status
)
from context_adapter.memory_adapter import fetch_behavior_service_memory, transform_behavior_memory, fetch_patterns_by_intent
from utils.service_matcher import ServiceMatcher


class SLOOrchestrator:
    """
    Main orchestrator that coordinates:
    1. Intent classification via LLM
    2. Data fetching from appropriate adapters
    3. Response aggregation
    """

    def __init__(self):
        """Initialize orchestrator with intent classifier and configuration"""
        load_dotenv()

        # Initialize intent classifier
        print("Initializing Intent Classifier...")
        self.classifier = IntentClassifier()
        print("✅ Intent Classifier ready")

        # Initialize service matcher
        print("Initializing Service Matcher...")
        try:
            self.service_matcher = ServiceMatcher("services.yaml")
            print(f"✅ Service Matcher ready ({len(self.service_matcher.services_by_id)} services loaded)\n")
        except FileNotFoundError:
            print("⚠️  services.yaml not found - service matching disabled\n")
            self.service_matcher = None

        # Configuration - can be moved to .env or config file
        self.app_id = 31854  # Default application ID
        self.java_stats_username = os.getenv('JAVA_STATS_USERNAME', 'wmadmin')
        self.java_stats_password = os.getenv('JAVA_STATS_PASSWORD', 'WM@Dm1n@#2024!!$')

    def process_query(self, user_query: str, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user query end-to-end

        Args:
            user_query: Natural language query from user
            service_name: Optional service name override (if not extracted from query)

        Returns:
            Dictionary containing:
            - classification: Intent classification results
            - data: Aggregated data from all adapters
            - metadata: Processing metadata
        """
        print("="*80)
        print("SLO ORCHESTRATOR - Processing Query")
        print("="*80)
        print(f"\n📝 Query: {user_query}\n")

        # Step 1: Classify intent
        print("🔍 Step 1: Analyzing intent...")
        classification_result = self.classifier.classify(user_query)

        if "error" in classification_result:
            return {
                "success": False,
                "error": classification_result.get("error"),
                "query": user_query
            }

        # Print classification result
        self.classifier.print_result(classification_result)

        # Step 2: Extract parameters
        entities = classification_result.get('entities', {})
        service = service_name or entities.get('service')
        data_sources = classification_result.get('data_sources', [])
        timestamp_resolution = classification_result.get('timestamp_resolution', {})

        # Collect all intents (primary + secondary + enriched) for pattern routing
        all_intents = set()
        all_intents.add(classification_result.get('primary_intent'))
        all_intents.update(classification_result.get('secondary_intents', []))
        all_intents.update(classification_result.get('enriched_intents', []))
        all_intents.discard(None)  # Remove None if present

        if not timestamp_resolution:
            return {
                "success": False,
                "error": "Failed to resolve time range",
                "query": user_query
            }

        primary_range = timestamp_resolution.get('primary_range', {})
        start_time = primary_range.get('start_time')
        end_time = primary_range.get('end_time')
        index = timestamp_resolution.get('index')

        print(f"\n📊 Step 2: Fetching data from adapters...")
        print(f"   Data Sources: {', '.join(data_sources)}")
        print(f"   Time Range: {start_time} to {end_time}")
        print(f"   Index: {index}\n")

        # Step 3: Fetch data from adapters
        adapter_data = {}

        # Resolve service_id if service mentioned
        service_id = None
        if service and self.service_matcher:
            print(f"   Resolving service name: '{service}'")
            matches = self.service_matcher.find_matches(service, threshold=0.3, max_results=1)
            if matches:
                service_id = matches[0]['service_id']
                matched_path = matches[0]['service_path']
                score = matches[0]['similarity_score']
                print(f"   ✓ Matched to service_id={service_id} ({matched_path}, score={score:.3f})\n")
            else:
                print(f"   ⚠️  No service match found for '{service}'\n")

        # Fetch from Java Stats API
        if 'java_stats_api' in data_sources:
            print("   → Fetching from Java Stats API...")
            java_data = self._fetch_java_stats(
                start_time_ms=str(start_time),
                end_time_ms=str(end_time),
                index=index,
                intents=all_intents,
                service_id=service_id
            )
            if java_data:
                adapter_data['java_stats_api'] = java_data
                print("   ✅ Java Stats API data retrieved\n")
            else:
                print("   ⚠️  Java Stats API returned no data\n")

        # Fetch from ClickHouse (memory adapter)
        if 'clickhouse' in data_sources:
            print("   → Fetching from ClickHouse (behavior memory)...")
            memory_data = self._fetch_memory_adapter(
                start_time=start_time,
                end_time=end_time,
                service_name=service,
                intents=all_intents,
                incident_timestamp=None  # Could extract from entities if needed
            )
            if memory_data:
                adapter_data['clickhouse'] = memory_data
                print("   ✅ ClickHouse data retrieved\n")
            else:
                print("   ⚠️  ClickHouse returned no data\n")

        # Note: postgres and opensearch adapters not yet implemented
        if 'postgres' in data_sources:
            print("   ⚠️  Postgres adapter not yet implemented")
            adapter_data['postgres'] = {"status": "not_implemented"}

        if 'opensearch' in data_sources:
            print("   ⚠️  OpenSearch adapter not yet implemented")
            adapter_data['opensearch'] = {"status": "not_implemented"}

        # Step 4: Build final response
        result = {
            "success": True,
            "query": user_query,
            "classification": {
                "primary_intent": classification_result.get('primary_intent'),
                "secondary_intents": classification_result.get('secondary_intents', []),
                "enriched_intents": classification_result.get('enriched_intents', []),
                "entities": entities
            },
            "time_resolution": {
                "start_time": start_time,
                "end_time": end_time,
                "index": index,
                "time_range": primary_range.get('time_range')
            },
            "data_sources_used": list(adapter_data.keys()),
            "data": adapter_data,
            "metadata": {
                "app_id": self.app_id,
                "service": service,
                "enrichment_applied": bool(classification_result.get('enrichment_details'))
            }
        }

        print("="*80)
        print("✅ ORCHESTRATION COMPLETE")
        print("="*80)
        print(f"\nData sources fetched: {', '.join(adapter_data.keys())}")
        print(f"Total data keys: {len(adapter_data)}\n")

        return result

    def _fetch_java_stats(
        self,
        start_time_ms: str,
        end_time_ms: str,
        index: str,
        intents: Optional[set] = None,
        service_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data from Java Stats API (Watermelon API) with intent-based routing.

        Routes to specific functions based on intent:
        - CURRENT_HEALTH: Application-wide health across all services
        - SERVICE_HEALTH: Health for a specific service (requires service_id)
        - ERROR_BUDGET_STATUS: Error budget data (EB category only)

        Args:
            start_time_ms: Start time in milliseconds (string)
            end_time_ms: End time in milliseconds (string)
            index: Time granularity (HOURLY, DAILY, etc.)
            intents: Set of all intents (primary + secondary + enriched)
            service_id: Optional service ID for service-specific queries

        Returns:
            Transformed LLM-ready data or None if failed
        """
        try:
            # Intent-based routing
            if intents:
                # Priority order: SERVICE_HEALTH > ERROR_BUDGET_STATUS > CURRENT_HEALTH

                # SERVICE_HEALTH - requires service_id
                if "SERVICE_HEALTH" in intents:
                    return get_service_health(
                        app_id=self.app_id,
                        start_time=start_time_ms,
                        end_time=end_time_ms,
                        service_id=service_id,
                        index=index,
                        username=self.java_stats_username,
                        password=self.java_stats_password
                    )

                # ERROR_BUDGET_STATUS - can work with or without service_id
                elif "ERROR_BUDGET_STATUS" in intents:
                    return get_error_budget_status(
                        app_id=self.app_id,
                        start_time=start_time_ms,
                        end_time=end_time_ms,
                        index=index,
                        username=self.java_stats_username,
                        password=self.java_stats_password,
                        service_id=service_id
                    )

                # CURRENT_HEALTH - application-wide
                elif "CURRENT_HEALTH" in intents:
                    return get_current_health(
                        app_id=self.app_id,
                        start_time=start_time_ms,
                        end_time=end_time_ms,
                        index=index,
                        username=self.java_stats_username,
                        password=self.java_stats_password
                    )

            # Fallback: Use general fetch_api_data + transform (backward compatibility)
            print("   Using general java_stats fetch (no specific intent matched)")
            raw_data = fetch_api_data(
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                username=self.java_stats_username,
                password=self.java_stats_password,
                application_id=self.app_id,
                index=index
            )

            if not raw_data:
                return None

            # Transform to LLM format
            transformed = transform_to_llm_format(raw_data, start_time_ms, end_time_ms)
            return transformed

        except Exception as e:
            print(f"   ✗ Error fetching Java Stats: {e}")
            return None

    def _fetch_memory_adapter(
        self,
        start_time: int,
        end_time: int,
        service_name: Optional[str] = None,
        intents: Optional[set] = None,
        incident_timestamp: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data from ClickHouse memory adapter with intent-based routing

        Args:
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            service_name: Optional service name filter (from intent classifier)
            intents: Set of all intents (primary + secondary + enriched)
            incident_timestamp: Optional incident timestamp for RECURRING_INCIDENT

        Returns:
            Intent-based pattern data or None if failed
        """
        try:
            # Step 1: Resolve service name to service_id
            service_id = None
            if service_name and self.service_matcher:
                print(f"   Resolving service name: '{service_name}'")
                matches = self.service_matcher.find_matches(service_name, threshold=0.3, max_results=1)
                if matches:
                    service_id = matches[0]['service_id']
                    matched_path = matches[0]['service_path']
                    score = matches[0]['similarity_score']
                    print(f"   ✓ Matched to service_id={service_id} ({matched_path}, score={score:.3f})")
                else:
                    print(f"   ⚠️  No service match found for '{service_name}'")

            # Step 2: Use intent-based routing if intents provided
            if intents:
                result = fetch_patterns_by_intent(
                    intents=intents,
                    start_time=start_time,
                    end_time=end_time,
                    app_id=self.app_id,
                    service_id=service_id,
                    service_name=service_name,
                    incident_timestamp=incident_timestamp
                )
                return result
            else:
                # Fallback to general fetch (backward compatibility)
                raw_data = fetch_behavior_service_memory(
                    start_time=start_time,
                    end_time=end_time,
                    app_id=self.app_id,
                    sid=service_name
                )

                if not raw_data:
                    return None

                transformed = transform_behavior_memory(
                    rows=raw_data,
                    start_time=start_time,
                    end_time=end_time,
                    app_id=self.app_id,
                    sid=service_name
                )
                return transformed

        except Exception as e:
            print(f"   ✗ Error fetching ClickHouse data: {e}")
            return None

    def export_to_json(self, result: Dict[str, Any], filepath: str):
        """
        Export orchestrator result to JSON file

        Args:
            result: Orchestrator result dictionary
            filepath: Path to output JSON file
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"✅ Result exported to {filepath}")
        except Exception as e:
            print(f"✗ Failed to export to JSON: {e}")


def main():
    """Main function for interactive testing"""
    print("\n" + "="*80)
    print("CONVERSATIONAL SLO MANAGER - ORCHESTRATOR")
    print("="*80)
    print("\nInitializing orchestrator...")

    try:
        orchestrator = SLOOrchestrator()
        print("✅ Orchestrator initialized successfully!\n")
    except Exception as e:
        print(f"❌ Failed to initialize orchestrator: {e}")
        return

    print("Enter your queries (type 'quit' or 'exit' to stop):")
    print("Commands:")
    print("  - 'export' - export last result to JSON")
    print("  - 'help' - show this help message\n")

    last_result = None

    while True:
        try:
            user_input = input("\nQuery: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋")
                break

            if user_input.lower() == 'help':
                print("\nCommands:")
                print("  - Enter any natural language query about your services")
                print("  - 'export' - export last result to JSON file")
                print("  - 'quit' or 'exit' - exit the program")
                continue

            if user_input.lower() == 'export':
                if last_result:
                    filename = f"slo_result_{int(last_result['time_resolution']['start_time'])}.json"
                    orchestrator.export_to_json(last_result, filename)
                else:
                    print("⚠️  No result to export. Run a query first.")
                continue

            # Process the query
            result = orchestrator.process_query(user_input)
            last_result = result

            # Print summary
            if result.get('success'):
                print("\n📋 Result Summary:")
                print(f"   Primary Intent: {result['classification']['primary_intent']}")
                print(f"   Data Sources Used: {', '.join(result['data_sources_used'])}")

                # Print data stats
                for source, data in result['data'].items():
                    if isinstance(data, dict) and 'stats' in data:
                        stats = data['stats']
                        print(f"\n   {source.upper()} Stats:")
                        for key, value in stats.items():
                            print(f"      • {key}: {value}")
            else:
                print(f"\n❌ Error: {result.get('error')}")

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error processing query: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

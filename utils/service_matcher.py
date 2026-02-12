#!/usr/bin/env python3
"""
Service Name Matcher
Matches service names extracted by intent classifier with service IDs from services.yaml
Uses similarity scoring to find the best matches
"""

import yaml
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
import os


class ServiceMatcher:
    """
    Matches service names to service IDs using similarity scoring
    """

    def __init__(self, services_yaml_path: str = "services.yaml"):
        """
        Initialize the service matcher

        Args:
            services_yaml_path: Path to services.yaml file
        """
        # Try to find services.yaml in multiple locations
        self.services_yaml_path = self._find_services_file(services_yaml_path)
        self.services_data = self._load_services()
        self.services_by_id = self.services_data.get('services_by_id', {})

    def _find_services_file(self, filename: str) -> str:
        """
        Find services.yaml file in current directory or parent directory

        Args:
            filename: Services YAML filename

        Returns:
            Full path to services file

        Raises:
            FileNotFoundError: If file not found in any location
        """
        # List of paths to check (in order)
        search_paths = [
            filename,  # Current directory
            os.path.join('..', filename),  # Parent directory
            os.path.join(os.path.dirname(__file__), '..', filename),  # Relative to script location
        ]

        for path in search_paths:
            if os.path.exists(path):
                return path

        raise FileNotFoundError(
            f"Services file '{filename}' not found. Searched in: {search_paths}"
        )


    def _load_services(self) -> Dict[str, Any]:
        """
        Load services from YAML file

        Returns:
            Services data dictionary
        """
        if not os.path.exists(self.services_yaml_path):
            raise FileNotFoundError(f"Services file not found: {self.services_yaml_path}")

        with open(self.services_yaml_path, 'r') as f:
            return yaml.safe_load(f)

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity score between two strings

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize strings (lowercase, strip whitespace)
        s1 = str1.lower().strip()
        s2 = str2.lower().strip()

        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, s1, s2).ratio()

    def _contains_match(self, query: str, target: str) -> bool:
        """
        Check if query string is contained in target string (case-insensitive)

        Args:
            query: Query string (e.g., "dashboard-stats")
            target: Target string (e.g., "wmuitestcontroller/api/mobile-devices/dashboard-stats")

        Returns:
            True if query is found in target
        """
        return query.lower() in target.lower()

    def find_matches(
        self,
        service_name: str,
        threshold: float = 0.3,
        use_contains: bool = True,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find matching services based on service name

        Args:
            service_name: Service name from intent classifier (e.g., "dashboard-stats")
            threshold: Minimum similarity score (0.0 to 1.0)
            use_contains: Also match if service_name is substring of service_path
            max_results: Maximum number of results to return

        Returns:
            List of matching services sorted by similarity score (highest first)
            Each entry contains: service_id, service_name, service_path, similarity_score, match_type
        """
        if not service_name or not service_name.strip():
            return []

        matches = []

        for service_id, service_info in self.services_by_id.items():
            service_path = service_info.get('service_path', '')
            full_service_name = service_info.get('service_name', '')

            # Calculate similarity against service_path
            similarity_score = self._calculate_similarity(service_name, service_path)

            # Check for substring match
            contains_in_path = self._contains_match(service_name, service_path)
            contains_in_name = self._contains_match(service_name, full_service_name)

            # Determine match type
            match_type = None
            final_score = similarity_score

            if contains_in_path and use_contains:
                match_type = "substring_in_path"
                # Boost score for substring matches
                final_score = max(similarity_score, 0.7)

            elif contains_in_name and use_contains:
                match_type = "substring_in_name"
                final_score = max(similarity_score, 0.6)

            elif similarity_score >= threshold:
                match_type = "similarity"

            # Add to matches if it passes threshold
            if match_type and final_score >= threshold:
                matches.append({
                    'service_id': service_id,
                    'service_name': full_service_name,
                    'service_path': service_path,
                    'similarity_score': final_score,
                    'match_type': match_type
                })

        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)

        # Limit results
        return matches[:max_results]

    def find_best_match(self, service_name: str, threshold: float = 0.3) -> Optional[Dict[str, Any]]:
        """
        Find the single best matching service

        Args:
            service_name: Service name from intent classifier
            threshold: Minimum similarity score

        Returns:
            Best matching service or None if no match found
        """
        matches = self.find_matches(service_name, threshold=threshold, max_results=1)
        return matches[0] if matches else None

    def get_service_by_id(self, service_id: int) -> Optional[Dict[str, Any]]:
        """
        Get service information by service ID

        Args:
            service_id: Service ID

        Returns:
            Service information or None if not found
        """
        return self.services_by_id.get(service_id)

    def get_all_services(self) -> Dict[int, Dict[str, Any]]:
        """
        Get all services

        Returns:
            Dictionary of all services indexed by service_id
        """
        return self.services_by_id


def main():
    """Test the service matcher"""
    import argparse

    parser = argparse.ArgumentParser(description="Test service name matching")
    parser.add_argument('service_name', type=str, help='Service name to search for')
    parser.add_argument('--threshold', type=float, default=0.3, help='Similarity threshold (0.0-1.0)')
    parser.add_argument('--max-results', type=int, default=10, help='Maximum results to show')
    parser.add_argument('--services-file', type=str, default='services.yaml', help='Path to services.yaml')

    args = parser.parse_args()

    print("=" * 80)
    print("SERVICE MATCHER TEST")
    print("=" * 80)
    print(f"\nSearching for: '{args.service_name}'")
    print(f"Threshold: {args.threshold}")
    print(f"Max results: {args.max_results}\n")

    # Initialize matcher
    try:
        matcher = ServiceMatcher(args.services_file)
        print(f"✓ Loaded {len(matcher.services_by_id)} services from {args.services_file}\n")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        return

    # Find matches
    matches = matcher.find_matches(
        args.service_name,
        threshold=args.threshold,
        max_results=args.max_results
    )

    if not matches:
        print("⚠ No matches found")
        return

    print(f"Found {len(matches)} match(es):")
    print("=" * 80)

    for i, match in enumerate(matches, 1):
        print(f"\n{i}. Service ID: {match['service_id']}")
        print(f"   Match Type: {match['match_type']}")
        print(f"   Similarity Score: {match['similarity_score']:.3f}")
        print(f"   Service Path: {match['service_path']}")
        print(f"   Full Name: {match['service_name'][:100]}...")

    # Show best match
    print("\n" + "=" * 80)
    print("BEST MATCH:")
    print("=" * 80)
    best = matches[0]
    print(f"Service ID: {best['service_id']}")
    print(f"Service Path: {best['service_path']}")
    print(f"Similarity: {best['similarity_score']:.3f}")


if __name__ == "__main__":
    main()

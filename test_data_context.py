"""
Test Data Context Detection
Verifies the system correctly identifies organization from DATA, not just schema
"""

import asyncio
import sys
sys.path.insert(0, '.')

from app.config import settings
from app.services.auto_onboarding.data_context_detector import DataContextDetector


async def test_context_detection():
    """Test the DataContextDetector with current database"""

    print("=" * 80)
    print("DATA CONTEXT DETECTION TEST")
    print("=" * 80)
    print(f"\nDatabase: {settings.database_url[:50]}...")
    print("\n" + "-" * 40)

    # Initialize detector
    detector = DataContextDetector(settings.database_url)

    # Run detection
    print("\nAnalyzing database data...\n")
    result = await detector.detect_context()

    # Display results
    print("=" * 80)
    print("DETECTION RESULTS")
    print("=" * 80)

    print(f"\nOrganization Name: {result.get('organization_name', 'Unknown')}")
    print(f"Short Name: {result.get('organization_short_name', 'N/A')}")
    print(f"Organization Type: {result.get('organization_type', 'Unknown')}")
    print(f"Type Display: {result.get('organization_type_display', 'N/A')}")
    print(f"Confidence: {result.get('confidence', 0):.2%}")
    print(f"Detection Method: {result.get('detection_method', 'Unknown')}")

    print("\n" + "-" * 40)
    print("EVIDENCE:")
    evidence = result.get('evidence', {})

    if evidence.get('departments_found'):
        print(f"\nDepartments Found ({len(evidence['departments_found'])}):")
        for dept in evidence['departments_found'][:10]:
            print(f"  - {dept}")
        if len(evidence['departments_found']) > 10:
            print(f"  ... and {len(evidence['departments_found']) - 10} more")

    if evidence.get('branches_found'):
        print(f"\nBranches Found ({len(evidence['branches_found'])}):")
        for branch in evidence['branches_found'][:10]:
            print(f"  - {branch}")

    if evidence.get('designations_found'):
        print(f"\nDesignations Found ({len(evidence['designations_found'])}):")
        for desig in evidence['designations_found'][:10]:
            print(f"  - {desig}")

    print("\n" + "-" * 40)
    print("DOMAIN VOCABULARY:")
    vocab = result.get('domain_vocabulary', {})
    for term, meaning in list(vocab.items())[:5]:
        print(f"  - {term}: {meaning}")

    print("\n" + "-" * 40)
    print("KEY ENTITIES:")
    for entity in result.get('key_entities', []):
        print(f"  - {entity}")

    print("\n" + "-" * 40)
    print("TYPICAL QUERIES:")
    for query in result.get('typical_queries', [])[:5]:
        print(f"  - {query}")

    print("\n" + "=" * 80)

    # Cleanup
    detector.close()

    return result


if __name__ == "__main__":
    result = asyncio.run(test_context_detection())

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    if result.get('organization_name') and result.get('organization_name') != 'Unknown Organization':
        print(f"\n[OK] Organization identified: {result['organization_name']}")
    else:
        print("\n[WARNING] Organization name not detected")

    if result.get('confidence', 0) >= 0.5:
        print(f"[OK] Confidence level: {result['confidence']:.2%}")
    else:
        print(f"[WARNING] Low confidence: {result.get('confidence', 0):.2%}")

    expected_type = "university"  # MUJ should be detected as university
    if result.get('organization_type') == expected_type:
        print(f"[OK] Type correctly identified as: {result['organization_type']}")
    else:
        print(f"[INFO] Type detected: {result.get('organization_type')} (expected: {expected_type})")

    print("\n" + "=" * 80)

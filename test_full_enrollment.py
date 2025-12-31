"""
Full Face Enrollment Test - Tests the complete chatbot enrollment flow
"""
import asyncio
import sys
sys.path.insert(0, ".")

from app.integrations.access_control_extended import ExtendedAccessControlClient
from loguru import logger

async def test_full_enrollment():
    """Test complete face enrollment flow for a new user"""
    print("=" * 70)
    print("FULL FACE ENROLLMENT TEST - CHATBOT FLOW")
    print("=" * 70)

    client = ExtendedAccessControlClient()

    # First, let's find employees and check who doesn't have face enrolled
    print("\n[Step 1] Finding employee without face enrollment...")

    # Check a few employees (Ecode 12, 13, 14) for face templates
    test_ecodes = [12, 13, 14, 15]
    target_ecode = None

    for ecode in test_ecodes:
        try:
            import httpx
            url = f"{client.base_url}/GetFingerListByTemplate"
            params = {"Ecode": ecode, "TemplateType": "FACE", "ClientVersion": "24.07.2025"}
            headers = {"APIKey": client.api_key}

            async with httpx.AsyncClient(timeout=10, verify=False) as http_client:
                response = await http_client.get(url, params=params, headers=headers)
                result = response.text.strip()

                if response.status_code == 200:
                    import json
                    templates = json.loads(result) if result else []
                    if isinstance(templates, list) and len(templates) == 0:
                        print(f"   Ecode {ecode}: No face template - CANDIDATE")
                        target_ecode = ecode
                        break
                    else:
                        print(f"   Ecode {ecode}: Has face template")
        except Exception as e:
            print(f"   Ecode {ecode}: Error checking - {e}")

    if not target_ecode:
        print("\n[!] No employee without face template found in test range.")
        print("    Please provide an Ecode to test with:")
        return

    print(f"\n[Step 2] Selected employee Ecode: {target_ecode}")
    print("=" * 70)
    print(f"STARTING ENROLLMENT FOR ECODE {target_ecode}")
    print("Please present face to V-22 device (192.168.1.201) when prompted...")
    print("=" * 70)

    # Call the full enrollment function
    result = await client.trigger_biometric_enrollment(
        ecode=target_ecode,
        terminal_name="V-22",
        biometric_type="face"
    )

    print("\n" + "=" * 70)
    print("ENROLLMENT RESULT")
    print("=" * 70)
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")
    print(f"Biometric Captured: {result.get('biometric_captured')}")
    print(f"Add to Terminal: {result.get('add_to_terminal_success')}")
    print(f"Fully Completed: {result.get('fully_completed')}")

    if result.get('success'):
        print("\n" + "=" * 70)
        print("SUCCESS! Now test authentication at the V-22 device.")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("FAILED - Check logs for details")
        print("=" * 70)

    return result

if __name__ == "__main__":
    result = asyncio.run(test_full_enrollment())

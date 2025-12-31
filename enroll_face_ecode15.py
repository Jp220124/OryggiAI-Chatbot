import httpx
import time

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

print("=" * 60)
print("FACE ENROLLMENT FOR ECODE 15")
print("=" * 60)
print("\nPlease present face to V-22 device (192.168.1.201) when prompted...")
print()

with httpx.Client(verify=False, timeout=120) as client:
    # Step 1: Trigger face enrollment
    print("1. Triggering EnrollV22...")
    r = client.get(f'{base_url}/EnrollV22',
                   params={
                       'Ecode': 15,
                       'FingerID': 11,  # Face enrollment
                       'DeviceIP': '192.168.1.201',
                       'OperatorEcode': 1,
                       'ClientVersion': '24.07.2025'
                   },
                   headers=headers)
    print(f"   Response: {r.status_code} - {r.text}")

    if 'Success' in r.text:
        print("\n2. Face captured! Verifying template...")
        time.sleep(2)

        # Verify template exists
        r = client.get(f'{base_url}/GetFingerListByTemplate',
                       params={'Ecode': 15, 'TemplateType': 'FACE', 'ClientVersion': '24.07.2025'},
                       headers=headers)
        templates = r.json() if r.status_code == 200 else []
        print(f"   Face templates: {len(templates) if isinstance(templates, list) else 0}")

        if templates:
            print("\n3. Syncing to terminal...")
            # Send sync command
            r = client.get(f'{base_url}/SendTCPCommand',
                           params={
                               'Command': 'EATR,1',
                               'host': '192.168.1.88',
                               'Port': 13000,
                               'LogDetail': 'Sync after face enrollment Ecode 15',
                               'ClientVersion': '24.07.2025'
                           },
                           headers=headers)
            print(f"   Sync response: {r.text}")

            print("\n" + "=" * 60)
            print("ENROLLMENT COMPLETE!")
            print("=" * 60)
            print("\nNow test authentication at the V-22 device.")
    else:
        print("\n*** Enrollment failed or timed out ***")
        print("Make sure to present your face to the device when prompted")

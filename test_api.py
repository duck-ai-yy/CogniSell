import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(_ROOT))

from api.main import scan, scan_select

print("Testing /api/scan")
res = scan()
print("Scan Result:", res)

if res.get("candidates"):
    first_candidate_id = res["candidates"][0]["node_id"]
    print(f"\nTesting /api/scan/select for candidate: {first_candidate_id}")
    class MockBody:
        def __init__(self, ids):
            self.ids = ids
            
    res2 = scan_select(MockBody([first_candidate_id]))
    print("Select Result:", res2)
else:
    print("No candidates found, skipping select test.")

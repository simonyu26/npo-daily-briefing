import os
import sys
import json
import urllib.request

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not api_key:
    print("❌ GEMINI_API_KEY is empty!")
    sys.exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
req = urllib.request.Request(url, headers={"User-Agent": "NPO-Probe/1.0"})

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", [])
        print(f"=== Found {len(models)} accessible models ===")
        for m in models:
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                name = m.get("name") # e.g. models/gemini-...
                display = m.get("displayName")
                print(f"  [generateContent OK] {name} ({display})")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="ignore")
    print(f"HTTP Error {e.code}: {body}")
except Exception as e:
    print(f"Error: {e}")

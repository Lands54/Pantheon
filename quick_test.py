#!/usr/bin/env python3
import subprocess

result = subprocess.run(
    ["gemini", "-m", "flash", "-p", "请只回复'OK'", "--accept-raw-output-risk"],
    capture_output=True,
    text=True,
    timeout=20
)

print("Return code:", result.returncode)
print("Output:", result.stdout[:300])
print("Errors:", result.stderr[:300])

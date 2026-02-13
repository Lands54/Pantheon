#!/usr/bin/env python3
import subprocess
import time

print("开始测试，请耐心等待...")

start = time.time()
try:
    result = subprocess.run(
        ["gemini", "-m", "flash", "-p", "只回复OK", "--accept-raw-output-risk"],
        capture_output=True,
        text=True,
        timeout=60,  # 给足够的时间
        cwd="/tmp"
    )
    
    elapsed = time.time() - start
    
    print(f"✅ 成功! 耗时: {elapsed:.1f}秒")
    print(f"Return code: {result.returncode}")
    print(f"\n=== 输出 ===\n{result.stdout}")
    print(f"\n=== 错误流 ===\n{result.stderr[:200]}")
    
except subprocess.TimeoutExpired:
    print(f"❌ 超时（60秒）")
except Exception as e:
    print(f"❌ 错误: {e}")

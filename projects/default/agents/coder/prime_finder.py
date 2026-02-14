"""
This script was manifested by the Coder.
It finds the essence of numbers.
"""
def check_divinity(n):
    if n < 2: return False
    for i in range(3, int(n**0.5) + 1):
        if n % i == 0: return False
    return True

# Analysis complete. Data stored in Aether.
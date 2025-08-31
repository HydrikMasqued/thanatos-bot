#!/usr/bin/env python3
import sys
sys.path.append('.')
from utils.time_parser import TimeParser

parser = TimeParser()

# Test the problematic cases
test_cases = ['5s', '5', '10s', '30s', '1m', '1h', '2 seconds']
print('Testing current time parser behavior:')
for case in test_cases:
    try:
        end_time, normalized = parser.parse_duration(case)
        print(f"'{case}' -> '{normalized}'")
    except Exception as e:
        print(f"'{case}' -> ERROR: {e}")

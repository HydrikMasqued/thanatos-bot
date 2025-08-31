#!/usr/bin/env python3
import sys
sys.path.append('.')
from utils.time_parser import TimeParser

parser = TimeParser()

# Comprehensive test cases
test_cases = [
    # Basic units
    '5s', '5 seconds', '1 second',
    '10m', '10 minutes', '1 minute', 
    '2h', '2 hours', '1 hour',
    '3d', '3 days', '1 day',
    '1w', '1 week', '2 weeks',
    '1mo', '1 month', '2 months',
    '1y', '1 year', '2 years',
    
    # Edge cases that should fail
    '5', '0', '', 'invalid',
    
    # Complex combinations  
    '2 weeks 3 days', '1 hour 30 minutes'
]

print('Comprehensive time parser test:')
print('=' * 50)

passed = 0
failed = 0

for case in test_cases:
    try:
        end_time, normalized = parser.parse_duration(case)
        print(f"✅ '{case}' -> '{normalized}'")
        passed += 1
    except Exception as e:
        print(f"❌ '{case}' -> ERROR: {e}")
        failed += 1

print('=' * 50)
print(f'Results: {passed} passed, {failed} failed')
if failed == 0:
    print('🎉 All tests passed!')

#!/usr/bin/env python3
"""
Error Export Utility for Thanatos Bot
Exports all errors in a clean format for Notepad analysis
"""

import os
import re
from datetime import datetime
from pathlib import Path

def extract_errors_from_log(log_file_path):
    """Extract all error entries from a log file"""
    if not Path(log_file_path).exists():
        return []
    
    errors = []
    current_error = None
    in_traceback = False
    
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.rstrip()
            
            # Check if this line starts a new error or warning
            if '- [   ERROR]' in line or '- [WARNING]' in line or '- [CRITICAL]' in line:
                # Save previous error if exists
                if current_error:
                    errors.append(current_error)
                
                # Start new error
                current_error = {
                    'line_number': line_num,
                    'timestamp': extract_timestamp(line),
                    'level': extract_log_level(line),
                    'module': extract_module(line),
                    'function': extract_function(line),
                    'message': extract_message(line),
                    'traceback': [],
                    'full_line': line
                }
                in_traceback = False
            
            # Check for traceback continuation
            elif current_error and ('Traceback' in line or line.startswith('  ') or line.startswith('    ')):
                in_traceback = True
                current_error['traceback'].append(line)
            
            # Check for context lines that might be related
            elif current_error and in_traceback and (line.startswith('File ') or '->' in line or 'Error:' in line):
                current_error['traceback'].append(line)
            
            elif current_error and in_traceback and line.strip() == '':
                # Empty line might end traceback
                continue
            else:
                in_traceback = False
        
        # Don't forget the last error
        if current_error:
            errors.append(current_error)
            
    except Exception as e:
        print(f"Error reading log file {log_file_path}: {e}")
    
    return errors

def extract_timestamp(line):
    """Extract timestamp from log line"""
    timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
    return timestamp_match.group(1) if timestamp_match else "Unknown"

def extract_log_level(line):
    """Extract log level from log line"""
    if '- [   ERROR]' in line:
        return 'ERROR'
    elif '- [WARNING]' in line:
        return 'WARNING'
    elif '- [CRITICAL]' in line:
        return 'CRITICAL'
    return 'UNKNOWN'

def extract_module(line):
    """Extract module name from log line"""
    # Pattern: module_name:function_name:line_number
    module_match = re.search(r'- ([^:]+):[^:]+:\d+', line)
    return module_match.group(1) if module_match else "Unknown"

def extract_function(line):
    """Extract function name from log line"""
    # Pattern: module_name:function_name:line_number
    function_match = re.search(r'- [^:]+:([^:]+):\d+', line)
    return function_match.group(1) if function_match else "Unknown"

def extract_message(line):
    """Extract error message from log line"""
    # Everything after the last ' - '
    parts = line.split(' - ')
    return parts[-1] if parts else line

def generate_error_report(errors, output_file):
    """Generate a comprehensive error report for Notepad"""
    report_lines = []
    
    # Header
    report_lines.append("=" * 80)
    report_lines.append("THANATOS BOT ERROR REPORT")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Total Errors Found: {len(errors)}")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Summary by error type
    error_counts = {}
    module_counts = {}
    
    for error in errors:
        level = error['level']
        module = error['module']
        
        error_counts[level] = error_counts.get(level, 0) + 1
        module_counts[module] = module_counts.get(module, 0) + 1
    
    report_lines.append("ERROR SUMMARY:")
    report_lines.append("-" * 40)
    for level, count in sorted(error_counts.items()):
        report_lines.append(f"{level}: {count}")
    report_lines.append("")
    
    report_lines.append("ERRORS BY MODULE:")
    report_lines.append("-" * 40)
    for module, count in sorted(module_counts.items(), key=lambda x: x[1], reverse=True):
        report_lines.append(f"{module}: {count}")
    report_lines.append("")
    report_lines.append("")
    
    # Detailed error list
    report_lines.append("DETAILED ERROR LIST:")
    report_lines.append("=" * 80)
    
    for i, error in enumerate(errors, 1):
        report_lines.append("")
        report_lines.append(f"ERROR #{i}")
        report_lines.append("-" * 40)
        report_lines.append(f"Timestamp: {error['timestamp']}")
        report_lines.append(f"Level: {error['level']}")
        report_lines.append(f"Module: {error['module']}")
        report_lines.append(f"Function: {error['function']}")
        report_lines.append(f"Line in Log: {error['line_number']}")
        report_lines.append("")
        report_lines.append("MESSAGE:")
        report_lines.append(error['message'])
        report_lines.append("")
        
        if error['traceback']:
            report_lines.append("TRACEBACK:")
            for tb_line in error['traceback']:
                report_lines.append(tb_line)
            report_lines.append("")
        
        report_lines.append("FULL LOG LINE:")
        report_lines.append(error['full_line'])
        report_lines.append("")
        report_lines.append("=" * 80)
    
    # Write report
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        return True
    except Exception as e:
        print(f"Error writing report: {e}")
        return False

def export_errors():
    """Main function to export all errors"""
    log_files = [
        'logs/thanatos_debug.log',
        'logs/thanatos_info.log', 
        'logs/thanatos_errors.log'
    ]
    
    all_errors = []
    
    print("🔍 Scanning log files for errors...")
    
    for log_file in log_files:
        if Path(log_file).exists():
            print(f"  Scanning {log_file}...")
            errors = extract_errors_from_log(log_file)
            all_errors.extend(errors)
            print(f"    Found {len(errors)} errors")
        else:
            print(f"  {log_file} not found, skipping...")
    
    if not all_errors:
        print("✅ No errors found in any log files!")
        return
    
    # Sort errors by timestamp
    all_errors.sort(key=lambda x: x['timestamp'])
    
    # Generate report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'error_report_{timestamp}.txt'
    
    print(f"📝 Generating error report: {output_file}")
    
    if generate_error_report(all_errors, output_file):
        print(f"✅ Error report generated successfully!")
        print(f"📄 Report saved as: {output_file}")
        print(f"📊 Total errors found: {len(all_errors)}")
        
        # Show quick summary
        error_counts = {}
        for error in all_errors:
            level = error['level']
            error_counts[level] = error_counts.get(level, 0) + 1
        
        print("\n📈 Quick Summary:")
        for level, count in sorted(error_counts.items()):
            print(f"  {level}: {count}")
            
        print(f"\n💡 Open {output_file} in Notepad to review all errors!")
        
    else:
        print("❌ Failed to generate error report")

if __name__ == '__main__':
    export_errors()

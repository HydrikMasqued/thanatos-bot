#!/usr/bin/env python3
"""
Real-time log monitoring script for Thanatos Bot
This script provides live monitoring of all bot activities with filtering options.
"""

import os
import time
import argparse
import threading
from datetime import datetime
from pathlib import Path

# ANSI color codes for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def get_color_for_level(level):
    """Get color based on log level"""
    colors = {
        'DEBUG': Colors.CYAN,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.MAGENTA
    }
    return colors.get(level, Colors.WHITE)

class LogMonitor:
    def __init__(self, log_dir='logs', filters=None):
        self.log_dir = Path(log_dir)
        self.filters = filters or []
        self.running = False
        self.file_positions = {}
        
    def follow_file(self, filepath):
        """Generator that yields new lines from a file as they are written"""
        if not filepath.exists():
            return
            
        # Start from end of file
        with open(filepath, 'r', encoding='utf-8') as f:
            f.seek(0, 2)  # Go to end of file
            self.file_positions[filepath] = f.tell()
            
            while self.running:
                current_pos = f.tell()
                line = f.readline()
                
                if not line:
                    time.sleep(0.1)
                    continue
                    
                yield line.rstrip()
                
    def should_show_line(self, line):
        """Check if line should be displayed based on filters"""
        if not self.filters:
            return True
            
        line_lower = line.lower()
        for filter_term in self.filters:
            if filter_term.lower() in line_lower:
                return True
        return False
    
    def format_log_line(self, line, source_file):
        """Format log line with colors and source info"""
        # Extract log level if present
        level = None
        for log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            if f'[{log_level:>8}]' in line or f'- {log_level} -' in line:
                level = log_level
                break
        
        # Color the line based on level
        if level:
            color = get_color_for_level(level)
            colored_line = f"{color}{line}{Colors.RESET}"
        else:
            colored_line = line
        
        # Add source file indicator
        file_indicator = f"{Colors.BOLD}[{source_file.stem}]{Colors.RESET}"
        
        return f"{file_indicator} {colored_line}"
    
    def monitor_logs(self):
        """Main monitoring loop"""
        print(f"{Colors.BOLD}{Colors.GREEN}🔍 Thanatos Bot Log Monitor Started{Colors.RESET}")
        print(f"Monitoring directory: {self.log_dir.absolute()}")
        
        if self.filters:
            print(f"Filters active: {', '.join(self.filters)}")
        
        print(f"{Colors.YELLOW}Press Ctrl+C to stop monitoring{Colors.RESET}\n")
        
        log_files = [
            self.log_dir / 'thanatos_debug.log',
            self.log_dir / 'thanatos_info.log', 
            self.log_dir / 'thanatos_errors.log'
        ]
        
        # Create file followers for each log file
        followers = []
        for log_file in log_files:
            if log_file.exists():
                follower = self.follow_file(log_file)
                followers.append((follower, log_file))
        
        self.running = True
        
        try:
            while self.running:
                for follower, log_file in followers:
                    try:
                        line = next(follower)
                        if self.should_show_line(line):
                            formatted_line = self.format_log_line(line, log_file)
                            print(formatted_line)
                    except StopIteration:
                        continue
                    except Exception as e:
                        print(f"{Colors.RED}Error reading {log_file}: {e}{Colors.RESET}")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Monitoring stopped by user{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error in monitoring: {e}{Colors.RESET}")
        finally:
            self.running = False

def analyze_logs(log_dir='logs'):
    """Analyze existing logs and provide summary"""
    log_dir = Path(log_dir)
    
    if not log_dir.exists():
        print(f"{Colors.RED}Log directory {log_dir} does not exist{Colors.RESET}")
        return
    
    print(f"{Colors.BOLD}{Colors.BLUE}📊 Log Analysis Summary{Colors.RESET}\n")
    
    log_files = [
        ('Debug Log', log_dir / 'thanatos_debug.log'),
        ('Info Log', log_dir / 'thanatos_info.log'),
        ('Error Log', log_dir / 'thanatos_errors.log')
    ]
    
    for name, log_file in log_files:
        if not log_file.exists():
            print(f"{Colors.YELLOW}{name}: File not found{Colors.RESET}")
            continue
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Count different log levels
            level_counts = {'DEBUG': 0, 'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'CRITICAL': 0}
            
            for line in lines:
                for level in level_counts.keys():
                    if f'[{level:>8}]' in line or f'- {level} -' in line:
                        level_counts[level] += 1
                        break
            
            # Get file size
            size_mb = log_file.stat().st_size / (1024 * 1024)
            
            print(f"{Colors.BOLD}{name}:{Colors.RESET}")
            print(f"  Size: {size_mb:.2f} MB ({len(lines)} lines)")
            print(f"  Levels: {Colors.CYAN}DEBUG: {level_counts['DEBUG']}{Colors.RESET} | "
                  f"{Colors.GREEN}INFO: {level_counts['INFO']}{Colors.RESET} | "
                  f"{Colors.YELLOW}WARNING: {level_counts['WARNING']}{Colors.RESET} | "
                  f"{Colors.RED}ERROR: {level_counts['ERROR']}{Colors.RESET} | "
                  f"{Colors.MAGENTA}CRITICAL: {level_counts['CRITICAL']}{Colors.RESET}")
            
            # Show recent activity (last 5 lines)
            if lines:
                print(f"  Recent activity:")
                for line in lines[-3:]:
                    print(f"    {line.rstrip()}")
            print()
            
        except Exception as e:
            print(f"{Colors.RED}Error analyzing {name}: {e}{Colors.RESET}")

def tail_logs(log_file, lines=50):
    """Show last N lines from a specific log file"""
    log_path = Path('logs') / log_file
    
    if not log_path.exists():
        print(f"{Colors.RED}Log file {log_path} does not exist{Colors.RESET}")
        return
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        print(f"{Colors.BOLD}Last {len(recent_lines)} lines from {log_file}:{Colors.RESET}\n")
        
        monitor = LogMonitor()
        for line in recent_lines:
            formatted = monitor.format_log_line(line.rstrip(), log_path)
            print(formatted)
            
    except Exception as e:
        print(f"{Colors.RED}Error reading {log_file}: {e}{Colors.RESET}")

def main():
    parser = argparse.ArgumentParser(description='Thanatos Bot Log Monitor')
    parser.add_argument('--monitor', '-m', action='store_true', 
                       help='Start real-time log monitoring')
    parser.add_argument('--analyze', '-a', action='store_true',
                       help='Analyze existing logs')
    parser.add_argument('--tail', '-t', type=str, metavar='LOG_FILE',
                       help='Show recent lines from specific log file')
    parser.add_argument('--lines', '-n', type=int, default=50,
                       help='Number of lines to show with --tail (default: 50)')
    parser.add_argument('--filter', '-f', action='append', metavar='TERM',
                       help='Filter logs by term (can be used multiple times)')
    parser.add_argument('--log-dir', default='logs',
                       help='Log directory path (default: logs)')
    
    args = parser.parse_args()
    
    # Create logs directory if it doesn't exist
    log_dir = Path(args.log_dir)
    log_dir.mkdir(exist_ok=True)
    
    if args.monitor:
        monitor = LogMonitor(log_dir=args.log_dir, filters=args.filter)
        monitor.monitor_logs()
    elif args.analyze:
        analyze_logs(args.log_dir)
    elif args.tail:
        tail_logs(args.tail, args.lines)
    else:
        # Default: show help and recent summary
        parser.print_help()
        print(f"\n{Colors.BOLD}Quick Summary:{Colors.RESET}")
        analyze_logs(args.log_dir)

if __name__ == '__main__':
    main()

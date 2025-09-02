# 🔍 Thanatos Bot Debug & Monitoring Guide

## Overview
This guide covers the comprehensive debugging and monitoring system for the Thanatos Bot, including enhanced logging, real-time monitoring, and analysis tools.

## 🚀 Quick Start

### Start Bot in Debug Mode
```bash
python start_debug.py
```

### Monitor Logs in Real-Time
```bash
# Monitor all logs
python monitor_logs.py --monitor

# Monitor with filters
python monitor_logs.py --monitor --filter "error" --filter "SmartTimeFormatter"

# Analyze existing logs
python monitor_logs.py --analyze
```

## 📁 File Structure

### Debug Files
- `debug_main.py` - Enhanced bot with comprehensive debugging
- `start_debug.py` - Debug startup script with banner and checks
- `monitor_logs.py` - Real-time log monitoring and analysis tool
- `DEBUG_GUIDE.md` - This comprehensive guide

### Log Files (auto-created in `logs/` directory)
- `thanatos_debug.log` - ALL events (DEBUG level and above)
- `thanatos_info.log` - Info level and above
- `thanatos_errors.log` - Errors and critical issues only

## 🎯 Debug Features

### Enhanced Logging
- **DEBUG Level**: Function calls, component initialization, detailed flow
- **INFO Level**: Command completions, system events, background task activity
- **WARNING Level**: Non-critical issues, fallback behaviors
- **ERROR Level**: Command failures, system errors
- **CRITICAL Level**: Fatal errors that prevent bot operation

### Real-Time Monitoring
- **Command Usage Tracking**: Track which commands are used most
- **Error Counting**: Keep track of total errors encountered
- **Background Task Monitoring**: Monitor LOA expiration and event reminder tasks
- **Database Operation Logging**: Track all database interactions
- **User Interaction Tracking**: Log all interactions (commands, buttons, modals)

### Enhanced Error Handling
- **Detailed Stack Traces**: Full traceback information for all errors
- **Context Logging**: Log additional context when errors occur
- **Graceful Degradation**: Bot continues operating even when individual components fail
- **User-Friendly Error Messages**: Users see helpful error messages while detailed info goes to logs

## 🛠️ Debugging Tools

### 1. Real-Time Log Monitor (`monitor_logs.py`)

#### Basic Usage
```bash
# Start monitoring all logs
python monitor_logs.py --monitor

# Monitor with specific filters
python monitor_logs.py --monitor --filter "loa" --filter "dues"

# Show recent entries from specific log
python monitor_logs.py --tail thanatos_debug.log --lines 100

# Analyze all log files
python monitor_logs.py --analyze
```

#### Features
- **Color-coded output** based on log levels
- **Real-time streaming** of new log entries
- **Filtering** by keywords or terms
- **Multi-file monitoring** (debug, info, error logs simultaneously)
- **Analysis mode** with statistics and summaries

### 2. Discord Commands

#### `!debug_stats`
Shows comprehensive bot statistics in Discord (owner only):
- Uptime information
- Guild and user counts
- Command usage statistics
- Error counts
- Background task status

#### `!sync`
Force sync slash commands (owner only) - useful during development

### 3. Enhanced Bot Features

#### Detailed Initialization Logging
```
🚀 Enhanced Thanatos Bot initializing with DEBUG monitoring...
✅ Database manager initialized successfully
✅ Time parser initialized successfully
✅ LOA notification manager initialized successfully
✅ Precise reminder system initialized successfully
```

#### Command Monitoring
```
✅ Slash command completed: /loa by @User in Guild Name
🔍 Component interaction: loa_submit_button by @User
📝 Modal submit interaction: loa_duration_modal by @User
```

#### Background Task Monitoring
```
🔍 Checking for expired LOAs...
📋 Found 2 expired LOA(s) to process
✅ Processed expired LOA for user @Member in Guild Name
```

## 📊 SmartTimeFormatter Integration Debugging

### What to Monitor
- **Natural Language Parsing**: Watch for SmartTimeFormatter parsing attempts
- **Fallback Behavior**: Monitor when natural language fails and falls back to standard parsing
- **Error Messages**: Check if users receive helpful guidance on time formats
- **Timestamp Formatting**: Verify consistent Discord timestamp usage

### Example Debug Output
```
[DEBUG] - SmartTimeFormatter:parse_natural_duration:45 - Attempting to parse: "2 weeks and 3 days"
[INFO] - SmartTimeFormatter - Successfully parsed "2 weeks and 3 days" to 2024-09-15 23:59:59
[DEBUG] - SmartTimeFormatter:format_time_remaining:78 - Formatting time remaining: 17 days, 5 hours
[INFO] - cogs.loa_system - LOA submitted with duration: "2 weeks and 3 days"
```

## 🎨 Log Format Reference

### Debug Log Format
```
2025-09-01 23:54:27 - [   DEBUG] - module_name:function_name:line_number - Detailed message
```

### Info Log Format
```
2025-09-01 23:54:27 - module_name - INFO - General information message
```

### Error Log Format
```
2025-09-01 23:54:27 - [   ERROR] - module_name:function_name:line_number - Error message
Full traceback:
Traceback details...
```

## 🔧 Common Debugging Scenarios

### 1. SmartTimeFormatter Issues
**What to monitor:**
```bash
python monitor_logs.py --monitor --filter "SmartTimeFormatter" --filter "parse"
```

**Look for:**
- Parse attempts and results
- Fallback to standard parser
- Error messages sent to users

### 2. Command Failures
**What to monitor:**
```bash
python monitor_logs.py --monitor --filter "Command error" --filter "Failed"
```

**Look for:**
- User information when errors occur
- Full stack traces
- Context about what was being processed

### 3. Database Issues
**What to monitor:**
```bash
python monitor_logs.py --monitor --filter "database" --filter "SQL"
```

**Look for:**
- Database connection issues
- SQL query failures
- Transaction problems

### 4. Background Task Monitoring
**What to monitor:**
```bash
python monitor_logs.py --monitor --filter "LOA" --filter "event reminder" --filter "background"
```

**Look for:**
- Task execution timing
- Processing results
- Error handling in background tasks

## 📈 Performance Monitoring

### Startup Performance
- Monitor component initialization times
- Track cog loading success/failure rates
- Watch for database initialization issues

### Runtime Performance
- Track command usage patterns
- Monitor error rates over time
- Watch background task execution

### Resource Usage
- Log file sizes (analyze command shows this)
- Error frequency trends
- Command usage statistics

## 🚨 Alert Indicators

### Critical Issues (require immediate attention)
- `[CRITICAL]` level logs
- Database connection failures
- Component initialization failures
- Multiple consecutive errors

### Warning Signs (should be investigated)
- High error rates
- Background task failures
- Unusual user interaction patterns
- Resource exhaustion warnings

## 📝 Best Practices

### During Development
1. Always run with debug mode during development
2. Monitor logs in real-time while testing new features
3. Use filters to focus on specific components
4. Check error logs regularly

### During Production
1. Switch to regular `main.py` for production
2. Keep debug logs for troubleshooting
3. Monitor error rates
4. Set up log rotation for disk space management

### Troubleshooting
1. Start with error logs first
2. Use debug logs for detailed investigation
3. Filter by relevant keywords
4. Check recent log entries for immediate issues

## 🔄 Log Rotation and Maintenance

### Manual Log Cleanup
```bash
# Clear all logs
rm logs/*.log

# Archive logs by date
mkdir -p logs/archive/$(date +%Y%m%d)
mv logs/*.log logs/archive/$(date +%Y%m%d)/
```

### Automated Maintenance
Consider setting up log rotation for production environments to manage disk space.

## 📞 Support and Troubleshooting

### Common Issues

1. **Logs directory doesn't exist**: Run `start_debug.py` which creates it automatically
2. **Permission errors**: Ensure write permissions to the project directory
3. **No log output**: Check if debug mode is actually running (`debug_main.py`)
4. **Monitor not showing anything**: Logs may be empty or monitor started before bot

### Getting Help

1. Check error logs first: `python monitor_logs.py --tail thanatos_errors.log`
2. Analyze all logs: `python monitor_logs.py --analyze`
3. Use Discord command: `!debug_stats` for live bot statistics
4. Review recent debug entries for detailed context

---

## 🎉 Summary

The Thanatos Bot now includes comprehensive debugging capabilities:

- **Enhanced Logging**: DEBUG level logging with detailed context
- **Real-Time Monitoring**: Live log streaming with filtering
- **Error Tracking**: Comprehensive error handling and reporting
- **Performance Monitoring**: Track command usage and system health
- **SmartTimeFormatter Integration**: Detailed monitoring of time parsing features

Use `python start_debug.py` to begin monitoring everything the bot does!

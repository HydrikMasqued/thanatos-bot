#!/usr/bin/env python3
import sys
import json
sys.path.append('.')
from main import ThanatosBot

print("Testing bot initialization...")

# Test config loading
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    print('✅ Config file loaded successfully')
    token_present = bool(config.get('token') and config['token'] != 'YOUR_BOT_TOKEN_HERE')
    print(f'Token present: {token_present}')
    print(f'Database path: {config.get("database_path", "Not set")}')
except Exception as e:
    print(f'❌ Config error: {e}')
    sys.exit(1)

# Test bot initialization (without connecting to Discord)
try:
    bot = ThanatosBot()
    print('✅ Bot instance created successfully')
    print(f'Bot owners configured: {len(bot.bot_owners)}')
    print(f'Database manager: {bot.db is not None}')
    print(f'Time parser: {bot.time_parser is not None}')
    print(f'LOA notifications: {bot.loa_notifications is not None}')
    print(f'Command prefix: {bot.command_prefix}')
    print(f'Intents configured: {bot.intents is not None}')
except Exception as e:
    print(f'❌ Bot initialization error: {e}')
    sys.exit(1)

print('🎉 Bot initialization tests completed successfully!')

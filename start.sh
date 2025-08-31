#!/bin/bash

# Thanatos Bot Startup Script

echo "🤖 Starting Thanatos Bot..."

# Create data directory if it doesn't exist
mkdir -p data

# Check if config.json exists
if [ ! -f "config.json" ]; then
    echo "⚠️  config.json not found! Creating template..."
    cat > config.json << 'EOF'
{
    "token": "YOUR_BOT_TOKEN_HERE",
    "database_path": "data/thanatos.db"
}
EOF
    echo "📝 Please edit config.json with your bot token before running again!"
    exit 1
fi

# Check if requirements are installed
echo "📦 Checking dependencies..."
pip install -r requirements.txt

# Check if bot token is configured
if grep -q "YOUR_BOT_TOKEN_HERE" config.json; then
    echo "⚠️  Please configure your bot token in config.json!"
    exit 1
fi

echo "🚀 Starting bot..."
python main.py

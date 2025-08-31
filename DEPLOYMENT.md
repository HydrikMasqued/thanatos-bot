# Deployment Guide for Cybrancee Panel

This guide will help you deploy your Thanatos Bot to the Cybrancee hosting panel.

## 🚀 Quick Deployment

### Method 1: Docker (Recommended)

1. **Upload your project** to the server
2. **Set up environment**:
```bash
# Navigate to your project directory
cd /path/to/thanatos-bot

# Configure your bot token
nano config.json
# or
cp .env.example .env
nano .env
```

3. **Deploy with Docker Compose**:
```bash
docker-compose up -d
```

4. **Monitor logs**:
```bash
docker-compose logs -f thanatos-bot
```

### Method 2: Direct Python

1. **Upload project files** to your server
2. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure bot token** in `config.json`
4. **Start the bot**:
```bash
chmod +x start.sh
./start.sh
```

## 🔧 Cybrancee Panel Specific Setup

### Using the Panel Interface

1. **File Manager**:
   - Upload all project files via the panel's file manager
   - Ensure `main.py` is in the root directory
   - Create/edit `config.json` with your bot token

2. **Terminal Access**:
   - Use the built-in terminal to run commands
   - Install dependencies: `pip install -r requirements.txt`
   - Start bot: `python main.py`

3. **Process Management**:
   - Use panel's process manager to keep bot running
   - Set startup command: `python main.py`
   - Enable auto-restart on crash

### Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create data directory
mkdir -p data

# Set up configuration
cp config.json.example config.json
nano config.json
```

## 📋 Configuration

### Bot Token Setup

Edit `config.json`:
```json
{
    "token": "YOUR_ACTUAL_BOT_TOKEN_HERE",
    "database_path": "data/thanatos.db"
}
```

### Environment Variables (Alternative)

Create `.env` file:
```bash
DISCORD_TOKEN=your_bot_token_here
DATABASE_PATH=data/thanatos.db
LOG_LEVEL=INFO
BOT_ENVIRONMENT=production
```

## 🐳 Docker Deployment Details

### Building the Container

```bash
# Build the image
docker build -t thanatos-bot .

# Or use docker-compose
docker-compose build
```

### Running the Container

```bash
# Using docker-compose (recommended)
docker-compose up -d

# Or using docker directly
docker run -d \
  --name thanatos-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.json:/app/config.json \
  thanatos-bot
```

### Container Management

```bash
# View logs
docker-compose logs -f thanatos-bot

# Restart bot
docker-compose restart thanatos-bot

# Stop bot
docker-compose stop thanatos-bot

# Update and restart
docker-compose pull
docker-compose up -d
```

## 📁 File Structure on Server

```
/path/to/your/bot/
├── main.py                 # Bot entry point
├── config.json            # Bot configuration (create this)
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker compose file
├── start.sh              # Startup script
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
├── README.md             # Documentation
├── DEPLOYMENT.md         # This file
├── cogs/                 # Bot modules
│   ├── enhanced_event_system.py
│   ├── event_management.py
│   ├── contributions.py
│   ├── loa_system.py
│   ├── membership.py
│   ├── configuration.py
│   ├── backup.py
│   ├── direct_messaging.py
│   ├── database_management.py
│   ├── enhanced_menu_system.py
│   └── audit_logs.py
├── utils/                # Utility modules
│   ├── database.py
│   ├── time_parser.py
│   ├── loa_notifications.py
│   ├── contribution_audit_helpers.py
│   └── event_export_utils.py
└── data/                 # Database storage (auto-created)
    └── thanatos.db       # SQLite database
```

## 🔍 Monitoring & Maintenance

### Health Checks

The bot includes automatic health monitoring:

```bash
# Check if bot is running
docker-compose ps

# View real-time logs
docker-compose logs -f thanatos-bot

# Check resource usage
docker stats thanatos-bot
```

### Database Backup

```bash
# Manual backup
cp data/thanatos.db data/thanatos-backup-$(date +%Y%m%d).db

# Or use built-in backup command in Discord
/backup_database
```

### Updates

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d
```

## 🛠️ Troubleshooting

### Common Issues

1. **Bot won't start**:
   - Check config.json has valid token
   - Verify all files are uploaded
   - Check logs: `docker-compose logs thanatos-bot`

2. **Commands not working**:
   - Ensure bot has proper Discord permissions
   - Check if commands are synced
   - Use `!sync` command if bot owner

3. **Database errors**:
   - Ensure data/ directory exists and is writable
   - Check disk space
   - Verify SQLite is working: `sqlite3 data/thanatos.db ".tables"`

4. **Memory issues**:
   - Monitor with `docker stats`
   - Restart if needed: `docker-compose restart`
   - Check for memory leaks in logs

### Performance Optimization

```bash
# Limit container resources
docker-compose.yml:
services:
  thanatos-bot:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

### Backup Strategy

1. **Database backups**:
   - Daily: `cp data/thanatos.db backups/db-$(date +%Y%m%d).db`
   - Weekly: Full data directory backup
   - Use Discord `/backup_database` command

2. **Configuration backups**:
   - Keep config.json in version control (without token)
   - Document any custom settings

## 🌐 Network & Security

### Port Configuration

The bot doesn't need external ports, but for health checks:
- Expose port 8000 for health monitoring (optional)
- Use Docker's internal networking

### Security Considerations

1. **Bot Token**:
   - Keep config.json private
   - Use environment variables in production
   - Never commit tokens to git

2. **File Permissions**:
```bash
chmod 600 config.json
chmod 700 data/
```

3. **Updates**:
   - Keep dependencies updated
   - Monitor security advisories
   - Regular Discord.py updates

## 📞 Support

### Getting Help

1. **Check logs first**:
   ```bash
   docker-compose logs --tail=100 thanatos-bot
   ```

2. **Common commands**:
   ```bash
   # Restart bot
   docker-compose restart thanatos-bot
   
   # Force rebuild
   docker-compose build --no-cache
   docker-compose up -d
   
   # Clean restart
   docker-compose down
   docker-compose up -d
   ```

3. **Bot status in Discord**:
   - `/test` - Basic functionality test
   - `/config_view` - Check configuration
   - `/data_summary` - Database status

### Logs Location

- **Docker logs**: `docker-compose logs thanatos-bot`
- **Application logs**: Check for `thanatos_bot.log` file
- **System logs**: Check panel's system logs if available

---

**Ready to deploy!** 🚀

Your enhanced Thanatos Bot with interactive event management is ready for production deployment on the Cybrancee panel!

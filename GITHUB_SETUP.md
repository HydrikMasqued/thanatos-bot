# GitHub Setup Guide for Thanatos Bot

## 🚀 Setting Up Your GitHub Repository

### Step 1: Create GitHub Repository

1. **Go to GitHub**: Visit [github.com](https://github.com)
2. **Create new repository**:
   - Click the "+" button → "New repository"
   - Repository name: `thanatos-bot` or `thanatos-event-management`
   - Description: "Enhanced Discord bot with interactive event management system"
   - Choose **Public** or **Private** (your preference)
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
   - Click "Create repository"

### Step 2: Connect Local Repository to GitHub

Run these commands in your project directory:

```bash
# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/REPOSITORY_NAME.git

# Push your code to GitHub
git branch -M main
git push -u origin main
```

**Replace `YOUR_USERNAME` and `REPOSITORY_NAME` with your actual GitHub username and repository name.**

### Step 3: Verify Upload

After pushing, you should see all your files on GitHub including:
- ✅ Main bot files (`main.py`, `requirements.txt`)
- ✅ Enhanced event management system
- ✅ Docker configuration
- ✅ Documentation (README.md, DEPLOYMENT.md)
- ✅ All cogs and utilities

## 🔐 Security Setup

### Protect Sensitive Information

Your `.gitignore` file already excludes:
- `config.json` (contains your bot token)
- `.env` files
- `data/` directory (database files)
- Logs and temporary files

**NEVER commit your bot token to GitHub!**

### Environment Variables for Deployment

For production deployment, use environment variables instead of config.json:

```bash
# On your server (Cybrancee panel)
export DISCORD_TOKEN=your_bot_token_here
export DATABASE_PATH=data/thanatos.db
export BOT_ENVIRONMENT=production
```

## 🐳 Cybrancee Panel Deployment

### Method 1: Git Clone (Recommended)

On your Cybrancee server:

```bash
# Clone your repository
git clone https://github.com/YOUR_USERNAME/REPOSITORY_NAME.git
cd REPOSITORY_NAME

# Set up environment
cp .env.example .env
nano .env  # Add your bot token

# Deploy with Docker
docker-compose up -d
```

### Method 2: Direct Upload

1. **Download** your repository as ZIP from GitHub
2. **Upload** all files to your Cybrancee panel
3. **Configure** bot token in config.json
4. **Deploy** using Docker or Python directly

## 🔄 Update Process

### Updating Your Bot

1. **Make changes** locally
2. **Commit and push**:
   ```bash
   git add .
   git commit -m "✨ Add new feature"
   git push origin main
   ```

3. **Update on server**:
   ```bash
   git pull origin main
   docker-compose build --no-cache
   docker-compose up -d
   ```

## 📋 Repository Structure

Your GitHub repository includes:

```
thanatos-bot/
├── 📄 README.md              # Main documentation
├── 🚀 DEPLOYMENT.md          # Deployment guide
├── 📋 requirements.txt       # Python dependencies
├── 🐳 Dockerfile            # Container configuration
├── 🐳 docker-compose.yml    # Docker deployment
├── 🔧 .env.example          # Environment template
├── 🚫 .gitignore           # Git ignore rules
├── 🎯 main.py               # Bot entry point
├── 📁 cogs/                 # Bot modules
│   ├── enhanced_event_system.py
│   ├── event_management.py
│   └── ... (all other cogs)
├── 📁 utils/                # Utility modules
│   ├── database.py
│   ├── event_export_utils.py
│   └── ... (all utilities)
└── 📁 dashboard/           # Optional web dashboard
```

## 🌟 Features Included

Your repository contains:

### ✨ Enhanced Event Management
- Interactive DM invitations with 3-button RSVP
- Flexible invitee selection system
- Real-time notifications and tracking
- Professional analytics and exports

### 🛠️ Complete Bot System
- LOA management
- Contribution tracking
- Membership system
- Audit logging
- Enhanced menu system

### 🚀 Production Ready
- Docker deployment configuration
- Environment variable support
- Health monitoring
- Automatic restarts
- Comprehensive documentation

## 📞 Support & Maintenance

### Keeping Your Repository Updated

1. **Regular commits** for new features
2. **Version tagging** for releases:
   ```bash
   git tag v2.0.0
   git push origin v2.0.0
   ```

3. **Branch management** for features:
   ```bash
   git checkout -b feature/new-command
   # Make changes
   git commit -m "Add new command"
   git push origin feature/new-command
   # Create pull request on GitHub
   ```

### Repository Settings

Recommended GitHub repository settings:
- ✅ Enable issues for bug tracking
- ✅ Enable discussions for user questions
- ✅ Set up branch protection for main
- ✅ Enable security alerts
- ✅ Add repository description and topics

---

## 🎉 You're Ready!

Your enhanced Thanatos Bot is now:
- ✅ **Version controlled** with Git
- ✅ **Hosted** on GitHub  
- ✅ **Production ready** for Cybrancee deployment
- ✅ **Fully documented** for easy setup
- ✅ **Docker configured** for containerized deployment

### Quick Deploy Commands

```bash
# On Cybrancee server:
git clone https://github.com/YOUR_USERNAME/REPOSITORY_NAME.git
cd REPOSITORY_NAME
cp .env.example .env
nano .env  # Add bot token
docker-compose up -d
```

**Your bot will be live with 92+ commands and full interactive event management!** 🚀

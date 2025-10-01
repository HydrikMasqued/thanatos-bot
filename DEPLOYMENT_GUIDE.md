# 🚀 Thanatos Bot Deployment Guide

## ✅ GitHub Update Status
- [x] **COMPLETED** - All changes pushed to GitHub successfully
- [x] **COMPLETED** - Repository: https://github.com/HydrikMasqued/thanatos-bot.git
- [x] **COMPLETED** - Commit: cbcc78d - "🚀 Major Update: V2 Systems Implementation"

---

## 📋 SFTP Server Update Checklist

### 🔄 **Step 1: Backup Current Server**
```bash
# On your server, create a backup
cp -r /path/to/bot /path/to/bot_backup_$(date +%Y%m%d_%H%M%S)
```

### 📁 **Step 2: Upload Modified Files**
Connect to your SFTP server and upload these updated files:

#### **Core Application Files:**
- `main.py` - Updated bot initialization
- `utils/database.py` - Database improvements
- `utils/smart_time_formatter.py` - Enhanced time formatting
- `utils/time_parser.py` - Improved time parsing
- `debug_main.py` - Debug utilities
- `dashboard/app.py` - Dashboard updates

#### **Cog Updates:**
- `cogs/enhanced_menu_system.py` - Menu system improvements

### ➕ **Step 3: Upload New Files**

#### **V2 Systems (Critical New Features):**
- `cogs/dues_v2.py` - New dues tracking system
- `cogs/prospects_v2.py` - New prospect management
- `cogs/time_converter.py` - Time conversion utilities

#### **Documentation:**
- `CHANGELOG_DUES_SYSTEM_V2.md`
- `CHANGELOG_SUMMARY.md`
- `ENHANCED_DUES_SYSTEM.md`
- `PROSPECTS_DUES_V2_CHANGELOG.md`
- `SIMPLIFIED_DUES_SYSTEM_GUIDE.md`
- `TECHNICAL_CHANGELOG.md`
- `V2_IMPLEMENTATION_SUMMARY.md`

#### **Testing & Development (Optional for Production):**
- `comprehensive_test.py`
- `debug_prospects.py`
- `edge_case_test.py`
- `test_bot_integration.py`
- `test_time_parsing_comprehensive.py`
- `test_v2_systems.py`
- `install_dateutil.py`

### ❌ **Step 4: Remove Deprecated Files**
Delete these old files from your server:

```bash
# Event System (Deprecated)
rm EVENT_SYSTEM_FIX_REPORT.md
rm cogs/event_notepad.py
rm cogs/events.py
rm server_upload_files/event_notepad.py
rm server_upload_files/event_notepad_fixed.py
rm test_event_management.py
rm test_simple_event.py
rm utils/event_export_utils.py
rm utils/precise_reminder_system.py

# Old Dues System (Replaced by V2)
rm cogs/dues_tracking.py

# Old Prospect System (Replaced by V2)
rm cogs/prospect_core.py
rm cogs/prospect_dashboard.py
rm cogs/prospect_management.py
rm cogs/prospect_notes.py
rm cogs/prospect_notes_consolidated.py
rm cogs/prospect_notifications.py
rm cogs/prospect_tasks.py
rm cogs/prospect_tasks_and_notes_consolidated.py
rm cogs/prospect_tasks_consolidated.py
rm cogs/prospect_voting.py
rm cogs/prospect_voting_consolidated.py
```

### 🔧 **Step 5: Update Dependencies**
Ensure your server has the required dependencies:

```bash
# Install/update Python dependencies
pip install --upgrade discord.py>=2.3.2
pip install --upgrade aiosqlite>=0.19.0
pip install --upgrade python-dateutil>=2.8.2
pip install --upgrade typing-extensions>=4.7.1
pip install --upgrade pytz>=2023.3

# Or use requirements.txt
pip install -r requirements.txt --upgrade
```

### 🔄 **Step 6: Restart Bot Service**

#### **If using systemd:**
```bash
sudo systemctl stop thanatos-bot
sudo systemctl start thanatos-bot
sudo systemctl status thanatos-bot
```

#### **If using Docker:**
```bash
docker-compose down
docker-compose up -d
docker-compose logs -f thanatos-bot
```

#### **If using PM2:**
```bash
pm2 restart thanatos-bot
pm2 logs thanatos-bot
```

#### **If running manually:**
```bash
# Stop the current process (Ctrl+C or kill)
# Then restart
python main.py
```

---

## 🧪 **Post-Deployment Testing**

### **1. Basic Bot Health Check:**
- [ ] Bot comes online without errors
- [ ] Bot responds to slash commands
- [ ] Database connections work

### **2. Test New V2 Systems:**
- [ ] `/dues_overview` - New dues system works
- [ ] `/prospects_overview` - New prospects system works
- [ ] `/time` - Time converter functions

### **3. Test Enhanced Features:**
- [ ] `/show_menu` - Enhanced menu system
- [ ] All existing commands still work
- [ ] No error messages in logs

---

## 📊 **What's New in This Update**

### **🆕 Major New Features:**
1. **Dues Management System V2** - Complete overhaul with automated tracking
2. **Prospects Management System V2** - Streamlined workflow and better UX
3. **Time Converter System** - Advanced timezone handling
4. **Enhanced Menu System** - Improved navigation and user experience

### **🔧 System Improvements:**
- Better database performance and reliability
- Enhanced time formatting with more options
- Improved error handling and logging
- Cleaner codebase with removed deprecated features

### **📚 Documentation:**
- Comprehensive user guides and technical documentation
- Complete changelog and implementation notes
- Testing framework and development tools

---

## 🚨 **Troubleshooting**

### **If bot won't start:**
1. Check logs for errors: `tail -f thanatos_bot.log`
2. Verify all required files are uploaded
3. Check Python dependencies: `pip list`
4. Ensure database is accessible

### **If commands don't work:**
1. Force sync commands: `!sync` (if you're a bot owner)
2. Check cog loading in logs
3. Verify file permissions on server

### **If database errors occur:**
1. Backup current database
2. Run database migrations if needed
3. Check database file permissions

---

## 📞 **Support**

If you encounter any issues during deployment:
1. Check the bot logs first
2. Review the changelog documents
3. Test individual components
4. Rollback to backup if necessary

---

**Deployment Date:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Version:** V2 Systems Implementation
**GitHub Commit:** cbcc78d
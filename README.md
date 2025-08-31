# Thanatos Bot - Enhanced Event Management System

A comprehensive Discord bot for guild management featuring advanced event management, contribution tracking, LOA system, and more.

## Features

### 🎉 Enhanced Event Management
- **Interactive Event Creation** - Guided event setup with modals
- **Flexible Invitee Selection** - Invite by username, display name, ID, or mentions
- **Interactive DM RSVPs** - 3-button response system (✅ Yes, ❌ No, 🤔 Maybe)
- **Real-time Notifications** - Instant updates when people respond
- **Comprehensive Analytics** - Attendance reports and historical tracking
- **Professional Exports** - CSV and JSON export capabilities

### 🏍️ Core Functionality
- **LOA System**: Submit, track, and manage Leave of Absence requests with automatic expiration notifications
- **Membership Management**: Automatic role detection and membership list generation
- **Contribution Tracking**: Record and monitor group contributions across various categories
- **Flexible Time Parsing**: Natural language time parsing (e.g., "2 weeks", "3 days", "1 month")
- **Officer Verification**: Required officer verification for LOA returns
- **Real-time Updates**: Automatic database updates when roles change

### 📊 Reporting & Analytics
- **Membership Lists**: Generate formatted membership lists (embed or text file)
- **Contribution Statistics**: Detailed analytics on contributions and contributors
- **Data Export**: Complete data export in JSON, text, or ZIP format
- **Database Backup**: Full SQLite database backup functionality

### ⚙️ Administration
- **Configurable Settings**: Customizable roles, channels, and categories per server
- **Permission System**: Admin and officer-only commands
- **Notification System**: Automated role pings and DM notifications
- **Data Management**: Import/export capabilities for data portability

## Installation

### Prerequisites
- Python 3.8 or higher
- Discord Bot Token (from Discord Developer Portal)

### Step 1: Clone/Download
1. Download the Thanatos Project folder to your desired location
2. Navigate to the project directory in your terminal

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Bot Token
1. Open `config.json`
2. Replace `"YOUR_BOT_TOKEN_HERE"` with your actual Discord bot token
3. Save the file

### Step 4: Create Discord Application
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section
4. Create a bot and copy the token
5. Enable the following Privileged Gateway Intents:
   - Server Members Intent
   - Message Content Intent

### Step 5: Invite Bot to Server
Generate an invite link with these permissions:
- `bot` scope
- `applications.commands` scope
- Administrator permissions (recommended) or specific permissions:
  - Send Messages
  - Use Slash Commands
  - Manage Roles
  - Read Message History
  - Attach Files

## Running the Bot

### Start the Bot
```bash
python main.py
```

The bot will:
1. Load all commands (cogs)
2. Connect to Discord
3. Initialize the database
4. Sync slash commands

## Initial Setup

### 1. Configure Basic Settings
Run these commands in your Discord server (Admin only):

```
/config_officer_role @OfficerRole
/config_notification_channel #notifications
/config_leadership_channel #leadership
/config_dm_user @AdminUser
```

### 2. Set Up Membership Roles
```
/config_membership_roles President, Vice President, Sergeant At Arms, Secretary, Treasurer, Road Captain, Tailgunner, Enforcer, Full Patch, Full Patch/Nomad
```

### 3. Configure Contribution Categories
```
/config_contribution_categories Body Armour & Medical, Pistols, Rifles, SMGs, Heist Items, Dirty Cash, Drug Items, Mech Shop, Crafting Items
```

### 4. Sync Membership
```
/membership_sync
```

## Commands Reference

### 🎉 Enhanced Event Commands
- `/create_event_interactive` - Create events with guided modal setup
- `/invite_people <event_id>` - Flexible invitee selection system
- `/event_analytics [days]` - View attendance statistics with export options
- `/export_event_data [days] [format]` - Generate CSV/JSON reports
- `/event_attendance_report [event_id] [days]` - Detailed analysis

### 📅 Traditional Event Commands  
- `/event` - Quick event creation with role invite
- `/rsvp <event_id> <response>` - Respond to events
- `/list_events [category]` - View active events
- `/event_details <event_id>` - View event information
- `/event_rsvps <event_id>` - View RSVPs (Officers only)
- `/send_event_dms <event_id>` - Send DM invitations (Officers only)

### 🔐 LOA Commands
- `/loa` - Submit a Leave of Absence request
- `/loa_status [member]` - Check LOA status
- `/loa_list` - List all active LOAs (Officers only)
- `/loa_cancel` - Cancel your active LOA

### 👥 Membership Commands
- `/membership_list [format]` - View membership list (embed or file)
- `/membership_sync` - Sync all members with Discord roles (Officers only)
- `/update_member_rank @member rank` - Update a member's rank (Officers only)
- `/remove_member @member` - Remove member from database (Officers only)

### 📦 Contribution Commands
- `/contribute` - Record a contribution (opens category selection)
- `/contributions_view [category]` - View contributions by category
- `/contribution_stats` - Detailed contribution statistics (Officers only)
- `/delete_contribution @member item_name` - Delete a contribution (Officers only)

### ⚙️ Configuration Commands (Admin Only)
- `/config_view` - View current server configuration
- `/config_officer_role @role` - Set officer role
- `/config_notification_channel #channel` - Set notification channel
- `/config_leadership_channel #channel` - Set leadership channel
- `/config_dm_user @user` - Set DM notification user
- `/config_membership_roles roles` - Set membership roles (comma-separated)
- `/config_contribution_categories categories` - Set categories (comma-separated)
- `/config_add_membership_role role` - Add single membership role
- `/config_remove_membership_role role` - Remove membership role
- `/config_add_contribution_category category` - Add single category
- `/config_remove_contribution_category category` - Remove category
- `/config_reset` - Reset all configuration to defaults

### 💾 Backup Commands (Admin Only)
- `/export_data [format]` - Export server data (json/text/both)
- `/backup_database` - Create complete database backup
- `/data_summary` - View data summary statistics

## Time Format Examples

The bot accepts flexible time formats for LOA duration:

- **Seconds**: `5s`, `30sec`, `45 seconds`
- **Minutes**: `15m`, `30min`, `45 minutes`
- **Hours**: `2h`, `8hr`, `12 hours`
- **Days**: `3d`, `7 days`
- **Weeks**: `2w`, `3 weeks`
- **Months**: `1mo`, `6 months`
- **Years**: `1y`, `2 years`
- **Combined**: `2 weeks 3 days`, `1 month 2 weeks`

## Database Structure

The bot uses SQLite with the following main tables:
- `server_configs` - Per-server configuration settings
- `members` - Member information and ranks
- `loa_records` - LOA submissions and status
- `contributions` - Contribution records

## Features in Detail

### LOA System
1. **Submission**: Members use `/loa` to open a modal form
2. **Validation**: Bot parses time duration and validates format
3. **Notifications**: Automatic role pings and DM notifications
4. **Tracking**: Background task checks for expired LOAs every 5 minutes
5. **Verification**: Officers must verify member returns before LOA removal

### Membership Management
1. **Auto-Detection**: Bot monitors role changes and updates database
2. **Hierarchy**: Respects motorcycle club rank structure
3. **Export Options**: Generate lists as Discord embeds or downloadable files
4. **Real-time Updates**: LOA status reflected immediately in membership lists

### Contribution System
1. **Category Selection**: Interactive dropdown for contribution categories
2. **Quantity Tracking**: Record specific quantities of contributed items
3. **Leadership Notifications**: Automatic notifications to leadership channel
4. **Statistics**: Detailed analytics on contributions and contributors

## Troubleshooting

### Bot Not Responding
1. Check bot is online in Discord
2. Verify bot has necessary permissions
3. Check console for error messages
4. Ensure slash commands are synced

### Database Issues
1. Check `data/` folder exists
2. Verify file permissions
3. Use `/backup_database` to create backups
4. Delete database file to reset (will lose all data)

### Configuration Problems
1. Use `/config_view` to check current settings
2. Use `/config_reset` to restore defaults
3. Ensure roles and channels exist
4. Check user has admin permissions

### Time Parsing Errors
1. Use simple formats first (e.g., "2 weeks")
2. Avoid special characters
3. Check console for specific error messages
4. Test with `/loa_status` command

## File Structure

```
Thanatos Project/
├── main.py                 # Main bot file
├── config.json            # Configuration file
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── data/                 # Database storage
│   └── thanatos.db       # SQLite database
├── cogs/                 # Command modules
│   ├── loa_system.py     # LOA functionality
│   ├── membership.py     # Membership management
│   ├── contributions.py  # Contribution tracking
│   ├── configuration.py  # Server configuration
│   └── backup.py         # Data backup/export
└── utils/                # Utility modules
    ├── __init__.py       # Package init
    ├── database.py       # Database management
    └── time_parser.py    # Time parsing utility
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the console output for error messages
3. Verify your configuration with `/config_view`
4. Test basic functionality with `/data_summary`

## License

This project is provided as-is for motorcycle club management purposes. Feel free to modify and adapt to your needs.

## Version History

### v1.0.0
- Initial release
- LOA system with flexible time parsing
- Membership management with role detection
- Contribution tracking system
- Full configuration system
- Data export and backup capabilities

---

**Thanatos MC Discord Bot** - Ride together, manage together. 🏍️

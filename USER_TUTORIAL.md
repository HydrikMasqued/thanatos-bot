# 🏍️ Thanatos Bot User Tutorial Guide

*The complete guide to using your Discord motorcycle club management bot*

---

## 🚀 Quick Start

### For New Users
1. **Make sure the bot is online** - Look for "Thanatos Bot" in your member list with a green status
2. **Check permissions** - Ensure you have the appropriate role (Officer/Admin) for restricted commands
3. **Start with basics** - Try `/config_view` to see current server settings

### Essential Commands Everyone Should Know
```
/loa                    - Submit a leave of absence
/loa_status            - Check your LOA status
/contribute            - Record contributions to the club
/membership_list       - View current membership
/rsvp [event_id]       - Respond to events
```

---

## 📋 Command Categories

### 🎉 **EVENT MANAGEMENT**

#### Creating Events
```
/create_event_interactive    - Create events with step-by-step guided setup
/event                      - Quick event creation (traditional method)
```

#### Event Participation
```
/list_events                - View all active events
/event_details [event_id]   - Get detailed event information
/rsvp [event_id] [response] - Respond to events (Yes/No/Maybe)
```

#### Event Management (Officers Only)
```
/send_event_dms [event_id]     - Send DM invitations to members
/event_rsvps [event_id]        - View who has responded
/event_analytics [days]        - View attendance statistics
/export_event_data [format]    - Export event data (CSV/JSON)
```

### 🔐 **LOA SYSTEM (Leave of Absence)**

#### For All Members
```
/loa                   - Submit new LOA request
/loa_status           - Check your current LOA status
/loa_cancel           - Cancel your active LOA
```

#### Time Format Examples
- `2 weeks` - Two weeks from now
- `1 month 3 days` - One month and three days
- `30 days` - Thirty days from now
- `3w` - Three weeks (short format)

#### For Officers
```
/loa_list             - View all active LOAs
/loa_status [@member] - Check another member's LOA
```

### 👥 **MEMBERSHIP MANAGEMENT**

#### View Membership
```
/membership_list [format]     - View membership (embed or downloadable file)
```

#### Officer Commands
```
/membership_sync              - Sync all members with Discord roles
/update_member_rank [@member] [rank] - Update member's rank
/remove_member [@member]      - Remove member from database
```

### 📦 **CONTRIBUTIONS**

#### Recording Contributions
```
/contribute                   - Opens interactive contribution form
```
*This will show you a dropdown menu with categories like:*
- Body Armour & Medical
- Pistols, Rifles, SMGs
- Heist Items
- Drug Items
- Crafting Items
- etc.

#### Viewing Contributions
```
/contributions_view [category] - View contributions by category
/contribution_stats           - Detailed statistics (Officers only)
```

#### Managing Contributions (Officers)
```
/delete_contribution [@member] [item] - Remove a contribution entry
```

---

## ⚙️ **CONFIGURATION (Admin Only)**

### Initial Server Setup
Run these commands in order when first setting up:

```bash
# 1. Set up basic roles and channels
/config_officer_role @OfficerRole
/config_notification_channel #notifications  
/config_leadership_channel #leadership
/config_dm_user @AdminUser

# 2. Configure membership roles (customize for your club)
/config_membership_roles President, Vice President, Secretary, Treasurer, Road Captain, Sergeant At Arms, Enforcer, Full Patch, Prospect

# 3. Set contribution categories (customize for your needs)
/config_contribution_categories Body Armour & Medical, Pistols, Rifles, SMGs, Heist Items, Dirty Cash, Drug Items, Crafting Items

# 4. Sync existing members
/membership_sync
```

### View and Modify Config
```
/config_view                              - See current settings
/config_add_membership_role [role]        - Add a single role
/config_remove_membership_role [role]     - Remove a role
/config_add_contribution_category [cat]   - Add a category
/config_remove_contribution_category [cat]- Remove a category
/config_reset                            - Reset to defaults (careful!)
```

---

## 💾 **DATA MANAGEMENT (Admin Only)**

### Backup and Export
```
/backup_database           - Create complete database backup
/export_data [format]      - Export all data (json/text/both)
/data_summary             - View statistics about stored data
```

---

## 📖 **How-To Guides**

### How to Submit a LOA
1. Use `/loa` command
2. Fill out the modal form that appears:
   - **Reason**: Brief explanation for your absence
   - **Duration**: How long you'll be away (e.g., "2 weeks", "1 month")
3. Submit the form
4. You'll get a confirmation with your LOA details
5. Officers will be notified automatically

### How to Record Contributions
1. Use `/contribute` command
2. Select category from dropdown menu
3. Fill in the contribution details:
   - **Item Name**: What you're contributing
   - **Quantity**: How much/many
   - **Additional Notes**: Any extra info
4. Submit - leadership will be notified automatically

### How to Create an Event
#### Interactive Method (Recommended)
1. Use `/create_event_interactive`
2. Fill out the event creation form:
   - **Event Title**: Name of your event
   - **Description**: What the event is about
   - **Date & Time**: When it's happening
   - **Duration**: How long it will last
3. After creation, use `/invite_people [event_id]` to invite members

#### Quick Method
1. Use `/event` with all details in one command
2. Bot will create event and send invitations to specified roles

### How to Manage Member Responses
1. Use `/event_rsvps [event_id]` to see who responded
2. Use `/send_event_dms [event_id]` to send DM reminders
3. Use `/event_analytics` to see attendance patterns

---

## ❗ **Common Issues & Solutions**

### "Bot not responding to commands"
- ✅ Check if bot is online (green status)
- ✅ Verify you have the right permissions
- ✅ Try using `/config_view` to test basic functionality
- ✅ Make sure you're using slash commands (/) not regular messages

### "Permission denied" errors
- ✅ Check your role - some commands require Officer or Admin permissions
- ✅ Ask an admin to verify your role assignment
- ✅ Use `/config_view` to see what roles are configured

### "Time format not recognized" 
- ✅ Use simple formats: "2 weeks", "30 days", "1 month"
- ✅ Avoid special characters or complex formatting
- ✅ Examples that work: `2w`, `30d`, `1mo`, `3 weeks 2 days`

### "Event creation failed"
- ✅ Make sure all required fields are filled
- ✅ Check that specified roles exist in your server
- ✅ Verify channels mentioned in event details exist

### "Database error"
- ✅ Contact admin - they may need to run `/backup_database`
- ✅ Admin can check logs in the bot's console
- ✅ Try the command again after a few minutes

---

## 🎯 **Best Practices**

### For All Members
- **LOAs**: Submit LOAs as early as possible, be specific about duration
- **Events**: Respond to event invitations promptly (Yes/No/Maybe)
- **Contributions**: Record contributions immediately after making them
- **Format**: Use clear, descriptive names for contributions and events

### For Officers
- **Regular Sync**: Run `/membership_sync` weekly to keep roles updated
- **Monitor LOAs**: Check `/loa_list` regularly for expired or expiring LOAs
- **Event Follow-up**: Send DM reminders for important events
- **Data Backup**: Run `/backup_database` before major changes

### For Admins
- **Configuration**: Review `/config_view` monthly and update as needed
- **Data Management**: Export data regularly with `/export_data`
- **Role Management**: Keep membership roles current with club structure
- **Permissions**: Regularly audit who has Officer/Admin roles

---

## 📊 **Understanding the Data**

### LOA Status Types
- **Active**: Currently on leave
- **Expired**: LOA period has ended, needs officer verification
- **Completed**: Returned and verified by officer

### Event Response Types
- **✅ Yes**: Will attend
- **❌ No**: Cannot attend  
- **🤔 Maybe**: Unsure/tentative

### Membership Role Hierarchy
The bot recognizes these roles in order of rank:
1. President
2. Vice President  
3. Secretary/Treasurer/Road Captain
4. Sergeant At Arms
5. Enforcer
6. Full Patch
7. Prospect

---

## 🆘 **Getting Help**

### Self-Help Commands
```
/config_view      - Check current bot configuration
/data_summary     - View database statistics  
/membership_list  - Verify your role is recognized
/loa_status      - Check your personal LOA status
```

### When to Contact an Admin
- Bot is completely unresponsive
- Data appears to be missing or incorrect
- Need roles or permissions adjusted
- Want to modify server configuration

### When to Contact Bot Owner
- Bot won't start or keeps crashing
- Need to modify core bot settings
- Database corruption issues
- Major technical problems

---

*This guide covers the essential functions of Thanatos Bot. For technical details, see README.md. For setup instructions, see DEPLOYMENT.md.*

**Remember**: Most commands use slash commands (/command) - type "/" to see available options!

---

🏍️ **Ride together, manage together** 🏍️

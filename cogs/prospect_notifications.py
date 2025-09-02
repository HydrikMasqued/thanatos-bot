import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict
import asyncio

logger = logging.getLogger(__name__)

class ProspectNotifications(commands.Cog):
    """Automated task reminders and notification system for prospect management"""

    def __init__(self, bot):
        self.bot = bot
        self.task_reminder_loop.start()
        logger.info("ProspectNotifications cog initialized with task reminder system")

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.task_reminder_loop.cancel()

    @tasks.loop(hours=1)  # Check every hour for overdue tasks
    async def task_reminder_loop(self):
        """Automated task reminder system"""
        try:
            logger.debug("Running task reminder check...")
            
            # Get all guilds the bot is in
            for guild in self.bot.guilds:
                await self.check_overdue_tasks(guild.id)
                
        except Exception as e:
            logger.error(f"Error in task reminder loop: {e}")

    @task_reminder_loop.before_loop
    async def before_task_reminder_loop(self):
        """Wait for bot to be ready before starting task reminders"""
        await self.bot.wait_until_ready()

    async def check_overdue_tasks(self, guild_id: int):
        """Check for overdue tasks and send reminders"""
        try:
            # Get overdue tasks for this guild
            overdue_tasks = await self.bot.db.get_overdue_tasks(guild_id)
            
            if not overdue_tasks:
                return
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            
            # Get server config for notification settings
            config = await self.bot.db.get_server_config(guild_id)
            if not config:
                return
            
            # Group overdue tasks by prospect and sponsor for better notifications
            tasks_by_prospect = {}
            tasks_by_sponsor = {}
            
            for task in overdue_tasks:
                prospect_user_id = task['prospect_user_id']
                sponsor_id = task['sponsor_id']
                
                if prospect_user_id not in tasks_by_prospect:
                    tasks_by_prospect[prospect_user_id] = []
                tasks_by_prospect[prospect_user_id].append(task)
                
                if sponsor_id not in tasks_by_sponsor:
                    tasks_by_sponsor[sponsor_id] = []
                tasks_by_sponsor[sponsor_id].append(task)
            
            # Send reminders to prospects
            for prospect_user_id, prospect_tasks in tasks_by_prospect.items():
                await self.send_prospect_overdue_reminder(guild, prospect_user_id, prospect_tasks)
            
            # Send reminders to sponsors
            for sponsor_id, sponsor_tasks in tasks_by_sponsor.items():
                await self.send_sponsor_overdue_reminder(guild, sponsor_id, sponsor_tasks)
            
            # Send leadership notification if there are many overdue tasks
            if len(overdue_tasks) >= 3:  # Threshold for leadership notification
                await self.send_leadership_overdue_notification(guild, overdue_tasks, config)
                
        except Exception as e:
            logger.error(f"Error checking overdue tasks for guild {guild_id}: {e}")

    async def send_prospect_overdue_reminder(self, guild: discord.Guild, prospect_user_id: int, overdue_tasks: List[Dict]):
        """Send overdue task reminder to prospect"""
        try:
            prospect = guild.get_member(prospect_user_id)
            if not prospect:
                return
            
            # Group tasks by how overdue they are
            critical_tasks = []  # More than 7 days overdue
            urgent_tasks = []    # 3-7 days overdue
            regular_tasks = []   # 1-2 days overdue
            
            for task in overdue_tasks:
                due_date = datetime.fromisoformat(task['due_date'])
                days_overdue = (datetime.now() - due_date).days
                
                if days_overdue >= 7:
                    critical_tasks.append((task, days_overdue))
                elif days_overdue >= 3:
                    urgent_tasks.append((task, days_overdue))
                else:
                    regular_tasks.append((task, days_overdue))
            
            # Determine urgency level
            if critical_tasks:
                color = discord.Color.red()
                title = "🚨 CRITICAL: Overdue Tasks"
                urgency = "CRITICAL"
            elif urgent_tasks:
                color = discord.Color.orange()
                title = "⚠️ URGENT: Overdue Tasks"
                urgency = "URGENT"
            else:
                color = discord.Color.yellow()
                title = "⏰ Overdue Task Reminder"
                urgency = "REMINDER"
            
            embed = discord.Embed(
                title=title,
                description=f"You have **{len(overdue_tasks)} overdue tasks** in **{guild.name}** that need immediate attention.",
                color=color,
                timestamp=datetime.now()
            )
            
            # Add task details
            all_tasks = critical_tasks + urgent_tasks + regular_tasks
            for i, (task, days_overdue) in enumerate(all_tasks[:5]):  # Limit to 5 tasks
                urgency_emoji = "🚨" if days_overdue >= 7 else "⚠️" if days_overdue >= 3 else "⏰"
                
                field_name = f"{urgency_emoji} {task['task_name']} ({days_overdue} days overdue)"
                field_value = f"**Assigned by:** {task.get('assigned_by_name', 'Unknown')}\n"
                field_value += f"**Description:** {task['task_description'][:100]}{'...' if len(task['task_description']) > 100 else ''}"
                
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            if len(overdue_tasks) > 5:
                embed.add_field(
                    name="Additional Tasks",
                    value=f"And {len(overdue_tasks) - 5} more overdue tasks...",
                    inline=False
                )
            
            # Add action items
            action_text = "**Required Actions:**\n"
            action_text += "• Complete overdue tasks immediately\n"
            action_text += "• Contact your sponsor if you need help\n"
            action_text += "• Use `/task-list` to see all your tasks\n"
            
            if critical_tasks:
                action_text += "\n⚠️ **WARNING:** Tasks overdue by 7+ days may result in strikes or prospect review."
            
            embed.add_field(name="What to do", value=action_text, inline=False)
            
            embed.set_footer(text=f"Prospect Management System • Priority: {urgency}")
            
            await prospect.send(embed=embed)
            logger.info(f"Sent overdue task reminder to prospect {prospect.display_name} ({len(overdue_tasks)} tasks)")
            
        except discord.Forbidden:
            logger.warning(f"Could not send overdue task reminder to prospect {prospect_user_id} - DMs disabled")
        except Exception as e:
            logger.error(f"Error sending prospect overdue reminder: {e}")

    async def send_sponsor_overdue_reminder(self, guild: discord.Guild, sponsor_id: int, overdue_tasks: List[Dict]):
        """Send overdue task notification to sponsor"""
        try:
            sponsor = guild.get_member(sponsor_id)
            if not sponsor:
                return
            
            # Group tasks by prospect
            tasks_by_prospect = {}
            for task in overdue_tasks:
                prospect_name = task.get('prospect_name', f"User {task['prospect_user_id']}")
                if prospect_name not in tasks_by_prospect:
                    tasks_by_prospect[prospect_name] = []
                tasks_by_prospect[prospect_name].append(task)
            
            embed = discord.Embed(
                title="📋 Sponsored Prospect Task Alert",
                description=f"Your sponsored prospects have **{len(overdue_tasks)} overdue tasks** in **{guild.name}**.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            # Add prospect details
            for prospect_name, prospect_tasks in tasks_by_prospect.items():
                most_overdue = max(prospect_tasks, key=lambda x: (datetime.now() - datetime.fromisoformat(x['due_date'])).days)
                days_overdue = (datetime.now() - datetime.fromisoformat(most_overdue['due_date'])).days
                
                urgency_emoji = "🚨" if days_overdue >= 7 else "⚠️" if days_overdue >= 3 else "⏰"
                
                field_value = f"**Overdue Tasks:** {len(prospect_tasks)}\n"
                field_value += f"**Most Overdue:** {days_overdue} days\n"
                field_value += f"**Latest Task:** {most_overdue['task_name']}"
                
                embed.add_field(
                    name=f"{urgency_emoji} {prospect_name}",
                    value=field_value,
                    inline=True
                )
            
            # Add sponsor guidance
            guidance = "**As a Sponsor:**\n"
            guidance += "• Check in with your prospects about overdue tasks\n"
            guidance += "• Offer guidance and support as needed\n"
            guidance += "• Consider if task deadlines need adjustment\n"
            guidance += "• Use `/task-list` to review their progress\n"
            
            embed.add_field(name="Sponsor Actions", value=guidance, inline=False)
            embed.set_footer(text="Prospect Management System • Sponsor Notification")
            
            await sponsor.send(embed=embed)
            logger.info(f"Sent sponsor overdue notification to {sponsor.display_name} ({len(overdue_tasks)} tasks)")
            
        except discord.Forbidden:
            logger.warning(f"Could not send sponsor overdue notification to {sponsor_id} - DMs disabled")
        except Exception as e:
            logger.error(f"Error sending sponsor overdue reminder: {e}")

    async def send_leadership_overdue_notification(self, guild: discord.Guild, overdue_tasks: List[Dict], config: Dict):
        """Send overdue task summary to leadership channel"""
        try:
            if not config.get('leadership_channel_id'):
                return
            
            leadership_channel = guild.get_channel(config['leadership_channel_id'])
            if not leadership_channel:
                return
            
            # Analyze overdue tasks
            critical_count = len([t for t in overdue_tasks if (datetime.now() - datetime.fromisoformat(t['due_date'])).days >= 7])
            urgent_count = len([t for t in overdue_tasks if 3 <= (datetime.now() - datetime.fromisoformat(t['due_date'])).days < 7])
            regular_count = len(overdue_tasks) - critical_count - urgent_count
            
            # Group by prospect
            prospects_affected = {}
            for task in overdue_tasks:
                prospect_name = task.get('prospect_name', f"User {task['prospect_user_id']}")
                if prospect_name not in prospects_affected:
                    prospects_affected[prospect_name] = []
                prospects_affected[prospect_name].append(task)
            
            embed = discord.Embed(
                title="📊 Overdue Task Summary",
                description=f"**{len(overdue_tasks)} total overdue tasks** affecting **{len(prospects_affected)} prospects**",
                color=discord.Color.red() if critical_count > 0 else discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            # Summary stats
            summary = f"🚨 **Critical (7+ days):** {critical_count}\n"
            summary += f"⚠️ **Urgent (3-6 days):** {urgent_count}\n"
            summary += f"⏰ **Regular (1-2 days):** {regular_count}"
            
            embed.add_field(name="Breakdown", value=summary, inline=True)
            
            # Most affected prospects
            sorted_prospects = sorted(prospects_affected.items(), key=lambda x: len(x[1]), reverse=True)
            top_prospects = []
            for prospect_name, prospect_tasks in sorted_prospects[:5]:
                max_days = max((datetime.now() - datetime.fromisoformat(t['due_date'])).days for t in prospect_tasks)
                urgency_emoji = "🚨" if max_days >= 7 else "⚠️" if max_days >= 3 else "⏰"
                top_prospects.append(f"{urgency_emoji} **{prospect_name}**: {len(prospect_tasks)} tasks (up to {max_days} days)")
            
            embed.add_field(name="Most Affected", value="\n".join(top_prospects), inline=True)
            
            # Recommendations
            recommendations = "**Recommended Actions:**\n"
            if critical_count > 0:
                recommendations += "• Review critical prospects for potential strikes\n"
            recommendations += "• Contact affected sponsors and prospects\n"
            recommendations += "• Consider adjusting unrealistic deadlines\n"
            recommendations += "• Use `/task-overdue` for detailed review\n"
            
            embed.add_field(name="Leadership Actions", value=recommendations, inline=False)
            embed.set_footer(text="Prospect Management System • Automated Report")
            
            await leadership_channel.send(embed=embed)
            logger.info(f"Sent leadership overdue notification: {len(overdue_tasks)} tasks, {len(prospects_affected)} prospects")
            
        except Exception as e:
            logger.error(f"Error sending leadership overdue notification: {e}")

    async def send_prospect_patch_notification(self, guild: discord.Guild, prospect: discord.Member, sponsor: discord.Member, config: Dict):
        """Send notifications when a prospect is patched"""
        try:
            # Send to leadership channel
            if config.get('leadership_channel_id'):
                leadership_channel = guild.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    embed = discord.Embed(
                        title="🎉 Prospect Patched Successfully",
                        description=f"**{prospect.display_name}** has been promoted to Full Member!",
                        color=discord.Color.gold(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Prospect", value=prospect.mention, inline=True)
                    embed.add_field(name="Sponsor", value=sponsor.mention, inline=True)
                    embed.set_thumbnail(url=prospect.display_avatar.url)
                    embed.set_footer(text="Prospect Management System")
                    
                    await leadership_channel.send(embed=embed)
            
            # Send to general notification channel if different
            if config.get('notification_channel_id') and config['notification_channel_id'] != config.get('leadership_channel_id'):
                notification_channel = guild.get_channel(config['notification_channel_id'])
                if notification_channel:
                    embed = discord.Embed(
                        title="🎉 Welcome Our Newest Member!",
                        description=f"Please welcome **{prospect.display_name}** who has just been patched to Full Member!\n\nSponsored by: {sponsor.mention}",
                        color=discord.Color.gold(),
                        timestamp=datetime.now()
                    )
                    embed.set_thumbnail(url=prospect.display_avatar.url)
                    
                    await notification_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending patch notifications: {e}")

    async def send_prospect_drop_notification(self, guild: discord.Guild, prospect: discord.Member, sponsor: discord.Member, reason: str, config: Dict):
        """Send notifications when a prospect is dropped"""
        try:
            # Send to leadership channel only (sensitive information)
            if config.get('leadership_channel_id'):
                leadership_channel = guild.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    embed = discord.Embed(
                        title="📢 Prospect Dropped",
                        description=f"**{prospect.display_name}** has been removed from prospect status.",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Prospect", value=prospect.mention, inline=True)
                    embed.add_field(name="Sponsor", value=sponsor.mention, inline=True)
                    embed.add_field(name="Reason", value=reason, inline=False)
                    embed.set_footer(text="Prospect Management System")
                    
                    await leadership_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending drop notifications: {e}")

    async def send_vote_started_notification(self, guild: discord.Guild, prospect: discord.Member, vote_type: str, started_by: discord.Member, config: Dict):
        """Send notification when a vote is started"""
        try:
            # Send to leadership channel
            if config.get('leadership_channel_id'):
                leadership_channel = guild.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    vote_colors = {
                        'patch': discord.Color.green(),
                        'drop': discord.Color.red()
                    }
                    
                    vote_emojis = {
                        'patch': '🎖️',
                        'drop': '❌'
                    }
                    
                    embed = discord.Embed(
                        title=f"{vote_emojis[vote_type]} {vote_type.title()} Vote Started",
                        description=f"A {vote_type} vote has been initiated for **{prospect.display_name}**",
                        color=vote_colors[vote_type],
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Prospect", value=prospect.mention, inline=True)
                    embed.add_field(name="Vote Type", value=vote_type.title(), inline=True)
                    embed.add_field(name="Started by", value=started_by.mention, inline=True)
                    
                    instructions = "**Voting Instructions:**\n"
                    instructions += "• Use `/vote-cast` to cast your vote\n"
                    instructions += "• Choose: Yes, No, or Abstain\n"
                    instructions += "• **Unanimous YES required to pass**\n"
                    instructions += "• Use `/vote-status` to check progress\n"
                    
                    embed.add_field(name="How to Vote", value=instructions, inline=False)
                    embed.set_footer(text="Prospect Management System • Anonymous Voting")
                    
                    await leadership_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending vote started notification: {e}")

    async def send_vote_concluded_notification(self, guild: discord.Guild, prospect: discord.Member, vote_type: str, result: str, vote_summary: Dict, config: Dict):
        """Send notification when a vote is concluded"""
        try:
            # Send to leadership channel
            if config.get('leadership_channel_id'):
                leadership_channel = guild.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    result_colors = {
                        'passed': discord.Color.green(),
                        'failed': discord.Color.red()
                    }
                    
                    result_emojis = {
                        'passed': '✅',
                        'failed': '❌'
                    }
                    
                    embed = discord.Embed(
                        title=f"{result_emojis[result]} Vote Concluded: {result.title()}",
                        description=f"The **{vote_type}** vote for **{prospect.display_name}** has ended with result: **{result.upper()}**",
                        color=result_colors[result],
                        timestamp=datetime.now()
                    )
                    
                    embed.add_field(name="Prospect", value=prospect.mention, inline=True)
                    embed.add_field(name="Vote Type", value=vote_type.title(), inline=True)
                    embed.add_field(name="Result", value=f"{result_emojis[result]} {result.title()}", inline=True)
                    
                    # Vote tally
                    results_text = f"✅ **Yes:** {vote_summary['yes']}\n"
                    results_text += f"❌ **No:** {vote_summary['no']}\n"
                    results_text += f"🤷 **Abstain:** {vote_summary['abstain']}\n"
                    results_text += f"📊 **Total:** {vote_summary['total']}"
                    
                    embed.add_field(name="Final Tally", value=results_text, inline=True)
                    
                    # Next steps
                    if result == 'passed':
                        if vote_type == 'patch':
                            next_steps = f"✅ Use `/prospect-patch` to promote {prospect.mention}"
                        else:  # drop
                            next_steps = f"❌ Use `/prospect-drop` to remove {prospect.mention}"
                    else:
                        next_steps = f"⏳ {prospect.mention} remains a prospect - continue trial period"
                    
                    embed.add_field(name="Next Steps", value=next_steps, inline=False)
                    embed.set_footer(text="Prospect Management System • Vote Results")
                    
                    await leadership_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending vote concluded notification: {e}")

    async def send_high_strikes_alert(self, guild: discord.Guild, prospect: discord.Member, strike_count: int, config: Dict):
        """Send alert when prospect reaches high strike count"""
        try:
            if strike_count < 3:  # Only alert for 3+ strikes
                return
                
            # Send to leadership channel
            if config.get('leadership_channel_id'):
                leadership_channel = guild.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    embed = discord.Embed(
                        title="🚨 High Strike Count Alert",
                        description=f"**{prospect.display_name}** now has **{strike_count} strikes** and may need review.",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Prospect", value=prospect.mention, inline=True)
                    embed.add_field(name="Strike Count", value=str(strike_count), inline=True)
                    embed.add_field(name="Risk Level", value="🚨 HIGH RISK", inline=True)
                    
                    recommendations = "**Recommended Actions:**\n"
                    recommendations += "• Review prospect's recent performance\n"
                    recommendations += "• Consider additional mentoring\n"
                    recommendations += "• Evaluate if a drop vote is needed\n"
                    recommendations += "• Contact sponsor for discussion\n"
                    
                    embed.add_field(name="Leadership Review", value=recommendations, inline=False)
                    embed.set_footer(text="Prospect Management System • High Risk Alert")
                    
                    await leadership_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending high strikes alert: {e}")

async def setup(bot):
    await bot.add_cog(ProspectNotifications(bot))

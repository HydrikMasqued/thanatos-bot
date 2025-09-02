import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional, List
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectTasks(commands.Cog):
    """Prospect task management commands for assigning and tracking tasks"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectTasks cog initialized")

    async def parse_time_duration(self, time_str: str) -> Optional[datetime]:
        """Parse time duration using the bot's smart time parser"""
        try:
            # Try to use the existing time parser from the bot if available
            if hasattr(self.bot, 'time_parser') and hasattr(self.bot.time_parser, 'parse_time'):
                return await self.bot.time_parser.parse_time(time_str)
            
            # Fallback to basic parsing
            time_str = time_str.lower().strip()
            
            # Common patterns
            if 'tomorrow' in time_str:
                return datetime.now() + timedelta(days=1)
            elif 'week' in time_str:
                if '2' in time_str or 'two' in time_str:
                    return datetime.now() + timedelta(weeks=2)
                return datetime.now() + timedelta(weeks=1)
            elif 'day' in time_str:
                days = 1
                if '2' in time_str or 'two' in time_str:
                    days = 2
                elif '3' in time_str or 'three' in time_str:
                    days = 3
                elif '7' in time_str:
                    days = 7
                return datetime.now() + timedelta(days=days)
            elif 'hour' in time_str:
                hours = 24
                if '12' in time_str:
                    hours = 12
                elif '6' in time_str:
                    hours = 6
                elif '4' in time_str:
                    hours = 4
                return datetime.now() + timedelta(hours=hours)
            
            # Try to extract numbers
            import re
            numbers = re.findall(r'\d+', time_str)
            if numbers:
                num = int(numbers[0])
                if 'day' in time_str:
                    return datetime.now() + timedelta(days=num)
                elif 'week' in time_str:
                    return datetime.now() + timedelta(weeks=num)
                elif 'hour' in time_str:
                    return datetime.now() + timedelta(hours=num)
                elif 'month' in time_str:
                    return datetime.now() + timedelta(days=num * 30)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing time duration '{time_str}': {e}")
            return None

    @app_commands.command(name="task-assign", description="Assign a task to a prospect")
    @app_commands.describe(
        prospect="The prospect to assign the task to",
        task_name="Brief name for the task",
        description="Detailed description of what needs to be done",
        due_in="When the task is due (e.g., '2 days', 'next week', 'tomorrow')"
    )
    async def task_assign(self, interaction: discord.Interaction, prospect: discord.Member, 
                         task_name: str, description: str, due_in: str = None):
        """Assign a task to a prospect"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Get prospect record
            prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if not prospect_record or prospect_record['status'] != 'active':
                await interaction.followup.send(
                    f"❌ {prospect.mention} is not an active prospect!",
                    ephemeral=True
                )
                return
            
            # Parse due date if provided
            due_date = None
            due_date_str = "No due date"
            if due_in:
                due_date = await self.parse_time_duration(due_in)
                if due_date:
                    due_date_str = f"<t:{int(due_date.timestamp())}:F>"
                else:
                    await interaction.followup.send(
                        f"❌ Could not parse due date '{due_in}'. Please use formats like '2 days', 'next week', 'tomorrow'.",
                        ephemeral=True
                    )
                    return
            
            # Create task
            task_id = await self.bot.db.create_prospect_task(
                interaction.guild.id,
                prospect_record['id'],
                interaction.user.id,
                task_name,
                description,
                due_date
            )
            
            # Create success embed
            embed = discord.Embed(
                title="📋 Task Assigned Successfully",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Assigned by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Due Date", value=due_date_str, inline=True)
            embed.add_field(name="Task", value=f"**{task_name}**", inline=False)
            embed.add_field(name="Description", value=description, inline=False)
            embed.set_footer(text=f"Task ID: {task_id}")
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect about new task
            try:
                dm_embed = discord.Embed(
                    title="📋 New Task Assigned",
                    description=f"You have been assigned a new task in **{interaction.guild.name}**",
                    color=discord.Color.blue()
                )
                dm_embed.add_field(name="Task", value=f"**{task_name}**", inline=False)
                dm_embed.add_field(name="Description", value=description, inline=False)
                dm_embed.add_field(name="Assigned by", value=interaction.user.display_name, inline=True)
                dm_embed.add_field(name="Due Date", value=due_date_str, inline=True)
                
                if due_date:
                    time_left = due_date - datetime.now()
                    if time_left.total_seconds() > 0:
                        dm_embed.add_field(name="Time Remaining", value=f"{time_left.days} days, {time_left.seconds // 3600} hours", inline=True)
                
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send task assignment DM to prospect {prospect.id}")
            
            # Send notification to sponsor
            try:
                sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
                if sponsor:
                    sponsor_embed = discord.Embed(
                        title="📋 Task Assigned to Your Prospect",
                        description=f"A new task has been assigned to {prospect.mention}",
                        color=discord.Color.blue()
                    )
                    sponsor_embed.add_field(name="Task", value=f"**{task_name}**", inline=False)
                    sponsor_embed.add_field(name="Description", value=description, inline=False)
                    sponsor_embed.add_field(name="Assigned by", value=interaction.user.mention, inline=True)
                    sponsor_embed.add_field(name="Due Date", value=due_date_str, inline=True)
                    
                    await sponsor.send(embed=sponsor_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send task notification DM to sponsor {prospect_record['sponsor_id']}")
            except Exception as e:
                logger.warning(f"Error sending sponsor notification: {e}")
            
        except Exception as e:
            logger.error(f"Error assigning task: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while assigning the task: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="task-complete", description="Mark a prospect task as completed")
    @app_commands.describe(
        prospect="The prospect whose task was completed",
        task_name="Name of the task that was completed",
        notes="Optional notes about the completion"
    )
    async def task_complete(self, interaction: discord.Interaction, prospect: discord.Member,
                           task_name: str, notes: str = None):
        """Mark a prospect task as completed"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Get prospect record
            prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if not prospect_record:
                await interaction.followup.send(
                    f"❌ {prospect.mention} is not a prospect!",
                    ephemeral=True
                )
                return
            
            # Get prospect tasks
            tasks = await self.bot.db.get_prospect_tasks(prospect_record['id'])
            
            # Find matching task
            matching_task = None
            for task in tasks:
                if task['status'] == 'assigned' and task_name.lower() in task['task_name'].lower():
                    matching_task = task
                    break
            
            if not matching_task:
                # Show available tasks
                active_tasks = [t for t in tasks if t['status'] == 'assigned']
                if active_tasks:
                    task_list = "\n".join([f"• {task['task_name']}" for task in active_tasks[:10]])
                    await interaction.followup.send(
                        f"❌ Could not find an active task matching '{task_name}' for {prospect.mention}.\n\n**Active tasks:**\n{task_list}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ {prospect.mention} has no active tasks to complete.",
                        ephemeral=True
                    )
                return
            
            # Complete the task
            success = await self.bot.db.complete_prospect_task(
                matching_task['id'],
                interaction.user.id,
                notes
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ Failed to complete the task. Please try again.",
                    ephemeral=True
                )
                return
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Task Completed Successfully",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Completed by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Task", value=f"**{matching_task['task_name']}**", inline=False)
            
            if matching_task.get('due_date'):
                due_date = datetime.fromisoformat(matching_task['due_date'])
                now = datetime.now()
                if now <= due_date:
                    time_diff = due_date - now
                    embed.add_field(name="Status", value=f"✅ Completed on time ({time_diff.days} days early)", inline=True)
                else:
                    time_diff = now - due_date
                    embed.add_field(name="Status", value=f"⏰ Completed late (by {time_diff.days} days)", inline=True)
            
            if notes:
                embed.add_field(name="Notes", value=notes, inline=False)
            
            embed.set_footer(text=f"Task ID: {matching_task['id']}")
            
            await interaction.followup.send(embed=embed)
            
            # Send congratulations DM to prospect
            try:
                dm_embed = discord.Embed(
                    title="🎉 Task Completed!",
                    description=f"Your task has been marked as completed in **{interaction.guild.name}**",
                    color=discord.Color.green()
                )
                dm_embed.add_field(name="Task", value=f"**{matching_task['task_name']}**", inline=False)
                dm_embed.add_field(name="Completed by", value=interaction.user.display_name, inline=True)
                
                if notes:
                    dm_embed.add_field(name="Notes", value=notes, inline=False)
                
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send task completion DM to prospect {prospect.id}")
            
            # Notify sponsor
            try:
                sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
                if sponsor:
                    sponsor_embed = discord.Embed(
                        title="✅ Prospect Task Completed",
                        description=f"{prospect.mention} has completed a task!",
                        color=discord.Color.green()
                    )
                    sponsor_embed.add_field(name="Task", value=f"**{matching_task['task_name']}**", inline=False)
                    sponsor_embed.add_field(name="Completed by", value=interaction.user.mention, inline=True)
                    
                    if notes:
                        sponsor_embed.add_field(name="Notes", value=notes, inline=False)
                    
                    await sponsor.send(embed=sponsor_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send task completion notification to sponsor {prospect_record['sponsor_id']}")
            except Exception as e:
                logger.warning(f"Error sending sponsor notification: {e}")
                
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while completing the task: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="task-fail", description="Mark a prospect task as failed")
    @app_commands.describe(
        prospect="The prospect whose task failed",
        task_name="Name of the task that failed",
        reason="Reason why the task failed"
    )
    async def task_fail(self, interaction: discord.Interaction, prospect: discord.Member,
                       task_name: str, reason: str):
        """Mark a prospect task as failed"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Get prospect record
            prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if not prospect_record:
                await interaction.followup.send(
                    f"❌ {prospect.mention} is not a prospect!",
                    ephemeral=True
                )
                return
            
            # Get prospect tasks
            tasks = await self.bot.db.get_prospect_tasks(prospect_record['id'])
            
            # Find matching task
            matching_task = None
            for task in tasks:
                if task['status'] == 'assigned' and task_name.lower() in task['task_name'].lower():
                    matching_task = task
                    break
            
            if not matching_task:
                # Show available tasks
                active_tasks = [t for t in tasks if t['status'] == 'assigned']
                if active_tasks:
                    task_list = "\n".join([f"• {task['task_name']}" for task in active_tasks[:10]])
                    await interaction.followup.send(
                        f"❌ Could not find an active task matching '{task_name}' for {prospect.mention}.\n\n**Active tasks:**\n{task_list}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ {prospect.mention} has no active tasks to mark as failed.",
                        ephemeral=True
                    )
                return
            
            # Fail the task
            success = await self.bot.db.fail_prospect_task(
                matching_task['id'],
                interaction.user.id,
                reason
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ Failed to update the task. Please try again.",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="❌ Task Failed",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Failed by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Task", value=f"**{matching_task['task_name']}**", inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            if matching_task.get('due_date'):
                due_date = datetime.fromisoformat(matching_task['due_date'])
                embed.add_field(name="Original Due Date", value=f"<t:{int(due_date.timestamp())}:F>", inline=True)
            
            embed.set_footer(text=f"Task ID: {matching_task['id']}")
            
            await interaction.followup.send(embed=embed)
            
            # Send notification DM to prospect
            try:
                dm_embed = discord.Embed(
                    title="❌ Task Failed",
                    description=f"One of your tasks has been marked as failed in **{interaction.guild.name}**",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Task", value=f"**{matching_task['task_name']}**", inline=False)
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Failed by", value=interaction.user.display_name, inline=True)
                dm_embed.add_field(name="Note", value="You may receive a new task or additional guidance from your sponsor.", inline=False)
                
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send task failure DM to prospect {prospect.id}")
            
            # Notify sponsor
            try:
                sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
                if sponsor:
                    sponsor_embed = discord.Embed(
                        title="❌ Prospect Task Failed",
                        description=f"{prospect.mention}'s task has been marked as failed.",
                        color=discord.Color.red()
                    )
                    sponsor_embed.add_field(name="Task", value=f"**{matching_task['task_name']}**", inline=False)
                    sponsor_embed.add_field(name="Reason", value=reason, inline=False)
                    sponsor_embed.add_field(name="Failed by", value=interaction.user.mention, inline=True)
                    sponsor_embed.add_field(name="Action Needed", value="Consider providing guidance or assigning a new task.", inline=False)
                    
                    await sponsor.send(embed=sponsor_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send task failure notification to sponsor {prospect_record['sponsor_id']}")
            except Exception as e:
                logger.warning(f"Error sending sponsor notification: {e}")
                
        except Exception as e:
            logger.error(f"Error failing task: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while updating the task: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="task-list", description="List tasks for a prospect")
    @app_commands.describe(
        prospect="The prospect to list tasks for",
        status="Filter tasks by status (all, assigned, completed, failed)"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Assigned", value="assigned"),
        app_commands.Choice(name="Completed", value="completed"),
        app_commands.Choice(name="Failed", value="failed")
    ])
    async def task_list(self, interaction: discord.Interaction, prospect: discord.Member, status: str = "all"):
        """List tasks for a prospect"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get prospect record
            prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if not prospect_record:
                await interaction.followup.send(
                    f"❌ {prospect.mention} is not a prospect!",
                    ephemeral=True
                )
                return
            
            # Get tasks
            all_tasks = await self.bot.db.get_prospect_tasks(prospect_record['id'])
            
            # Filter tasks by status
            if status != "all":
                tasks = [t for t in all_tasks if t['status'] == status]
            else:
                tasks = all_tasks
            
            # Create embed
            status_colors = {
                'all': discord.Color.blue(),
                'assigned': discord.Color.orange(),
                'completed': discord.Color.green(),
                'failed': discord.Color.red()
            }
            
            embed = discord.Embed(
                title=f"📋 Tasks for {prospect.display_name}",
                description=f"Status: {status.title()}",
                color=status_colors.get(status, discord.Color.blue()),
                timestamp=datetime.now()
            )
            
            if not tasks:
                embed.add_field(name="No Tasks Found", value=f"No {status} tasks found for this prospect.", inline=False)
            else:
                # Sort tasks by created_at
                tasks.sort(key=lambda x: x['created_at'], reverse=True)
                
                # Add task summary
                if status == "all":
                    completed = len([t for t in all_tasks if t['status'] == 'completed'])
                    failed = len([t for t in all_tasks if t['status'] == 'failed'])
                    assigned = len([t for t in all_tasks if t['status'] == 'assigned'])
                    overdue = len([t for t in all_tasks if t['status'] == 'assigned' and t['due_date'] and datetime.fromisoformat(t['due_date']) < datetime.now()])
                    
                    summary = f"**Total:** {len(all_tasks)}\n"
                    summary += f"✅ Completed: {completed}\n"
                    summary += f"❌ Failed: {failed}\n"
                    summary += f"⏳ Assigned: {assigned}\n"
                    if overdue > 0:
                        summary += f"🚨 Overdue: {overdue}"
                    
                    embed.add_field(name="Summary", value=summary, inline=True)
                
                # Add individual tasks
                for i, task in enumerate(tasks[:15]):  # Limit to 15 tasks
                    status_emoji = {
                        'assigned': '⏳',
                        'completed': '✅',
                        'failed': '❌'
                    }.get(task['status'], '❓')
                    
                    # Check if overdue
                    overdue_text = ""
                    if task['status'] == 'assigned' and task['due_date']:
                        due_date = datetime.fromisoformat(task['due_date'])
                        if datetime.now() > due_date:
                            overdue_text = " 🚨"
                    
                    field_name = f"{status_emoji} {task['task_name']}{overdue_text}"
                    
                    field_value = f"**Assigned by:** {task.get('assigned_by_name', 'Unknown')}\n"
                    
                    if task['due_date']:
                        due_date = datetime.fromisoformat(task['due_date'])
                        field_value += f"**Due:** <t:{int(due_date.timestamp())}:R>\n"
                    
                    if task['status'] == 'completed' and task['completed_by_name']:
                        completed_date = datetime.fromisoformat(task['completed_date'])
                        field_value += f"**Completed by:** {task['completed_by_name']} (<t:{int(completed_date.timestamp())}:R>)\n"
                    elif task['status'] == 'failed' and task['completed_by_name']:
                        failed_date = datetime.fromisoformat(task['completed_date'])
                        field_value += f"**Failed by:** {task['completed_by_name']} (<t:{int(failed_date.timestamp())}:R>)\n"
                    
                    if task['notes']:
                        notes = task['notes'][:100] + "..." if len(task['notes']) > 100 else task['notes']
                        field_value += f"**Notes:** {notes}\n"
                    
                    # Truncate description if too long
                    description = task['task_description'][:150] + "..." if len(task['task_description']) > 150 else task['task_description']
                    field_value += f"**Description:** {description}"
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                
                if len(tasks) > 15:
                    embed.add_field(
                        name="Note",
                        value=f"Showing first 15 of {len(tasks)} tasks.",
                        inline=False
                    )
            
            embed.set_footer(text=f"Prospect ID: {prospect_record['id']}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while retrieving tasks: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="task-overdue", description="List all overdue prospect tasks")
    async def task_overdue(self, interaction: discord.Interaction):
        """List all overdue prospect tasks"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get overdue tasks
            overdue_tasks = await self.bot.db.get_overdue_tasks(interaction.guild.id)
            
            embed = discord.Embed(
                title="🚨 Overdue Prospect Tasks",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            if not overdue_tasks:
                embed.description = "No overdue tasks found! 🎉"
                embed.color = discord.Color.green()
            else:
                embed.description = f"Found {len(overdue_tasks)} overdue tasks that need attention."
                
                # Sort by how overdue they are
                overdue_tasks.sort(key=lambda x: datetime.fromisoformat(x['due_date']))
                
                for i, task in enumerate(overdue_tasks[:10]):  # Limit to 10 most overdue
                    prospect_name = task.get('prospect_name', f"User {task['prospect_user_id']}")
                    sponsor_name = task.get('sponsor_name', f"User {task['sponsor_id']}")
                    assigned_by_name = task.get('assigned_by_name', f"User {task['assigned_by_id']}")
                    
                    due_date = datetime.fromisoformat(task['due_date'])
                    days_overdue = (datetime.now() - due_date).days
                    
                    field_name = f"🚨 {task['task_name']} ({days_overdue} days overdue)"
                    
                    field_value = f"**Prospect:** {prospect_name}\n"
                    field_value += f"**Sponsor:** {sponsor_name}\n"
                    field_value += f"**Assigned by:** {assigned_by_name}\n"
                    field_value += f"**Due Date:** <t:{int(due_date.timestamp())}:F>\n"
                    
                    # Truncate description if too long
                    description = task['task_description'][:100] + "..." if len(task['task_description']) > 100 else task['task_description']
                    field_value += f"**Description:** {description}"
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                
                if len(overdue_tasks) > 10:
                    embed.add_field(
                        name="Note",
                        value=f"Showing 10 most overdue of {len(overdue_tasks)} total overdue tasks.",
                        inline=False
                    )
                
                # Add action suggestions
                embed.add_field(
                    name="Recommended Actions",
                    value="• Use `/task-complete` or `/task-fail` to update task status\n• Contact prospects and sponsors about overdue tasks\n• Consider adjusting due dates for reasonable tasks",
                    inline=False
                )
            
            embed.set_footer(text="Use /task-complete or /task-fail to resolve overdue tasks")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error listing overdue tasks: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while retrieving overdue tasks: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProspectTasks(bot))

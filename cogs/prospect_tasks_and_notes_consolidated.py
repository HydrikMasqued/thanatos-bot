import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional, List
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectTasksAndNotesConsolidated(commands.Cog):
    """Consolidated prospect tasks and notes commands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectTasksAndNotesConsolidated cog initialized")

    @app_commands.command(name="prospect-task", description="Prospect task management commands")
    @app_commands.describe(
        action="The action to perform",
        prospect="The prospect user",
        description="Task description (required for assign action)",
        due_date="Due date in format YYYY-MM-DD (optional for assign action)",
        task_id="Task ID (required for complete/fail actions)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Assign new task", value="assign"),
        app_commands.Choice(name="Mark task complete", value="complete"),
        app_commands.Choice(name="Mark task failed", value="fail"),
        app_commands.Choice(name="List tasks", value="list"),
        app_commands.Choice(name="Show overdue tasks", value="overdue")
    ])
    async def prospect_task(
        self, 
        interaction: discord.Interaction, 
        action: str, 
        prospect: Optional[discord.Member] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        task_id: Optional[int] = None
    ):
        """Main prospect task management command with subcommands"""
        # Permission check
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        if action == "assign":
            await self._task_assign(interaction, prospect, description, due_date)
        elif action == "complete":
            await self._task_complete(interaction, task_id)
        elif action == "fail":
            await self._task_fail(interaction, task_id)
        elif action == "list":
            await self._task_list(interaction, prospect)
        elif action == "overdue":
            await self._task_overdue(interaction)

    async def _task_assign(self, interaction: discord.Interaction, prospect: discord.Member, description: str, due_date: str):
        """Assign a new task to a prospect"""
        if not prospect:
            await interaction.response.send_message("❌ Please specify a prospect to assign a task to.", ephemeral=True)
            return
        if not description:
            await interaction.response.send_message("❌ Please provide a task description.", ephemeral=True)
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
            parsed_due_date = None
            if due_date:
                try:
                    parsed_due_date = datetime.strptime(due_date, "%Y-%m-%d")
                    if parsed_due_date < datetime.now():
                        await interaction.followup.send(
                            "❌ Due date cannot be in the past!", 
                            ephemeral=True
                        )
                        return
                except ValueError:
                    await interaction.followup.send(
                        "❌ Invalid date format! Please use YYYY-MM-DD (e.g., 2024-12-25)", 
                        ephemeral=True
                    )
                    return
            
            # Create task
            task_id = await self.bot.db.create_prospect_task(
                prospect_record['id'],
                description,
                interaction.user.id,
                parsed_due_date
            )
            
            # Create embed
            embed = discord.Embed(
                title="📋 Task Assigned",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Assigned by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Task ID", value=f"`{task_id}`", inline=True)
            
            embed.add_field(name="Description", value=description, inline=False)
            
            if parsed_due_date:
                embed.add_field(
                    name="Due Date", 
                    value=f"<t:{int(parsed_due_date.timestamp())}:F>", 
                    inline=True
                )
                
                # Check if due soon (within 7 days)
                days_until_due = (parsed_due_date - datetime.now()).days
                if days_until_due <= 7:
                    embed.add_field(name="⚠️ Notice", value="Due within 7 days!", inline=True)
            else:
                embed.add_field(name="Due Date", value="No deadline", inline=True)
            
            embed.set_footer(text="Use /prospect-task complete <task_id> when finished")
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect
            try:
                dm_embed = discord.Embed(
                    title="📋 New Task Assigned",
                    description=f"You have been assigned a new task in **{interaction.guild.name}**",
                    color=discord.Color.blue()
                )
                dm_embed.add_field(name="Task", value=description, inline=False)
                dm_embed.add_field(name="Assigned by", value=interaction.user.display_name, inline=True)
                
                if parsed_due_date:
                    dm_embed.add_field(
                        name="Due Date", 
                        value=f"<t:{int(parsed_due_date.timestamp())}:F>", 
                        inline=True
                    )
                
                dm_embed.set_footer(text=f"Task ID: {task_id}")
                await prospect.send(embed=dm_embed)
            except:
                pass  # User has DMs disabled
            
            # Log to leadership channel if configured
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    log_embed = embed.copy()
                    await leadership_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Error assigning prospect task: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while assigning the task: {str(e)}", 
                ephemeral=True
            )

    async def _task_complete(self, interaction: discord.Interaction, task_id: int):
        """Mark a task as completed"""
        if not task_id:
            await interaction.response.send_message("❌ Please provide a task ID to mark complete.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Get task
            task = await self.bot.db.get_prospect_task(task_id)
            if not task:
                await interaction.followup.send("❌ Task not found!", ephemeral=True)
                return
            
            # Verify task belongs to this guild
            prospect = await self.bot.db.get_prospect_by_id(task['prospect_id'])
            if not prospect or prospect['guild_id'] != interaction.guild.id:
                await interaction.followup.send("❌ Task not found in this server!", ephemeral=True)
                return
            
            if task['status'] != 'assigned':
                await interaction.followup.send("❌ Task is not in assigned status!", ephemeral=True)
                return
            
            # Update task status
            await self.bot.db.update_prospect_task_status(task_id, 'completed')
            
            # Get prospect member
            prospect_member = interaction.guild.get_member(prospect['user_id'])
            
            # Create embed
            embed = discord.Embed(
                title="✅ Task Completed",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Task ID", value=f"`{task_id}`", inline=True)
            embed.add_field(name="Prospect", value=prospect_member.mention if prospect_member else f"User {prospect['user_id']}", inline=True)
            embed.add_field(name="Completed by", value=interaction.user.mention, inline=True)
            
            embed.add_field(name="Task", value=task['task_name'], inline=False)
            
            if task.get('due_date'):
                due_date = datetime.fromisoformat(task['due_date'])
                embed.add_field(name="Was Due", value=f"<t:{int(due_date.timestamp())}:R>", inline=True)
                
                # Check if completed on time
                if datetime.now() <= due_date:
                    embed.add_field(name="✅ Status", value="Completed on time!", inline=True)
                else:
                    embed.add_field(name="⚠️ Status", value="Completed late", inline=True)
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect
            if prospect_member:
                try:
                    dm_embed = discord.Embed(
                        title="✅ Task Completed",
                        description=f"Your task has been marked as completed in **{interaction.guild.name}**",
                        color=discord.Color.green()
                    )
                    dm_embed.add_field(name="Task", value=task['task_name'], inline=False)
                    dm_embed.add_field(name="Completed by", value=interaction.user.display_name, inline=True)
                    dm_embed.set_footer(text=f"Task ID: {task_id}")
                    await prospect_member.send(embed=dm_embed)
                except:
                    pass  # User has DMs disabled
            
        except Exception as e:
            logger.error(f"Error completing prospect task: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while completing the task: {str(e)}", 
                ephemeral=True
            )

    async def _task_fail(self, interaction: discord.Interaction, task_id: int):
        """Mark a task as failed"""
        if not task_id:
            await interaction.response.send_message("❌ Please provide a task ID to mark failed.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Get task
            task = await self.bot.db.get_prospect_task(task_id)
            if not task:
                await interaction.followup.send("❌ Task not found!", ephemeral=True)
                return
            
            # Verify task belongs to this guild
            prospect = await self.bot.db.get_prospect_by_id(task['prospect_id'])
            if not prospect or prospect['guild_id'] != interaction.guild.id:
                await interaction.followup.send("❌ Task not found in this server!", ephemeral=True)
                return
            
            if task['status'] != 'assigned':
                await interaction.followup.send("❌ Task is not in assigned status!", ephemeral=True)
                return
            
            # Update task status
            await self.bot.db.update_prospect_task_status(task_id, 'failed')
            
            # Get prospect member
            prospect_member = interaction.guild.get_member(prospect['user_id'])
            
            # Create embed
            embed = discord.Embed(
                title="❌ Task Failed",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Task ID", value=f"`{task_id}`", inline=True)
            embed.add_field(name="Prospect", value=prospect_member.mention if prospect_member else f"User {prospect['user_id']}", inline=True)
            embed.add_field(name="Marked by", value=interaction.user.mention, inline=True)
            
            embed.add_field(name="Task", value=task['task_name'], inline=False)
            
            if task.get('due_date'):
                due_date = datetime.fromisoformat(task['due_date'])
                embed.add_field(name="Was Due", value=f"<t:{int(due_date.timestamp())}:R>", inline=True)
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect
            if prospect_member:
                try:
                    dm_embed = discord.Embed(
                        title="❌ Task Failed",
                        description=f"Your task has been marked as failed in **{interaction.guild.name}**",
                        color=discord.Color.red()
                    )
                    dm_embed.add_field(name="Task", value=task['task_name'], inline=False)
                    dm_embed.add_field(name="Marked by", value=interaction.user.display_name, inline=True)
                    dm_embed.set_footer(text=f"Task ID: {task_id}")
                    await prospect_member.send(embed=dm_embed)
                except:
                    pass  # User has DMs disabled
            
        except Exception as e:
            logger.error(f"Error failing prospect task: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while failing the task: {str(e)}", 
                ephemeral=True
            )

    async def _task_list(self, interaction: discord.Interaction, prospect: discord.Member):
        """List tasks for a prospect or all prospect tasks"""
        try:
            await interaction.response.defer()
            
            if prospect:
                # Get tasks for specific prospect
                prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
                if not prospect_record:
                    await interaction.followup.send(
                        f"❌ {prospect.mention} is not a prospect!", 
                        ephemeral=True
                    )
                    return
                
                tasks = await self.bot.db.get_prospect_tasks(prospect_record['id'])
                
                embed = discord.Embed(
                    title=f"📋 Tasks for {prospect.display_name}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                if not tasks:
                    embed.description = "No tasks have been assigned to this prospect."
                    await interaction.followup.send(embed=embed)
                    return
                
                # Categorize tasks
                assigned_tasks = [t for t in tasks if t['status'] == 'assigned']
                completed_tasks = [t for t in tasks if t['status'] == 'completed']
                failed_tasks = [t for t in tasks if t['status'] == 'failed']
                
                # Add summary
                embed.add_field(
                    name="📊 Summary",
                    value=f"⏳ Assigned: {len(assigned_tasks)}\n✅ Completed: {len(completed_tasks)}\n❌ Failed: {len(failed_tasks)}\n📋 Total: {len(tasks)}",
                    inline=True
                )
                
                # Show assigned tasks first (most important)
                if assigned_tasks:
                    assigned_list = []
                    for task in assigned_tasks[:5]:  # Show up to 5 assigned tasks
                        due_text = ""
                        if task.get('due_date'):
                            due_date = datetime.fromisoformat(task['due_date'])
                            if datetime.now() > due_date:
                                due_text = " 🚨 OVERDUE"
                            else:
                                due_text = f" (Due <t:{int(due_date.timestamp())}:R>)"
                        
                        assigned_list.append(
                            f"`{task['id']}` {task['task_name']}{due_text}\n"
                            f"   └ Assigned by: {task.get('assigned_by_name', 'Unknown')}"
                        )
                    
                    if len(assigned_tasks) > 5:
                        assigned_list.append(f"\n*...and {len(assigned_tasks) - 5} more assigned tasks*")
                    
                    embed.add_field(
                        name="⏳ Assigned Tasks",
                        value="\n".join(assigned_list),
                        inline=False
                    )
            else:
                # Show overview of all prospect tasks
                active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
                
                embed = discord.Embed(
                    title="📋 All Prospect Tasks Overview",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                if not active_prospects:
                    embed.description = "No active prospects found."
                    await interaction.followup.send(embed=embed)
                    return
                
                total_assigned = 0
                total_completed = 0
                total_failed = 0
                overdue_count = 0
                prospect_summaries = []
                
                for prospect in active_prospects[:10]:  # Limit to 10 prospects
                    tasks = await self.bot.db.get_prospect_tasks(prospect['id'])
                    
                    if tasks:
                        assigned = len([t for t in tasks if t['status'] == 'assigned'])
                        completed = len([t for t in tasks if t['status'] == 'completed'])
                        failed = len([t for t in tasks if t['status'] == 'failed'])
                        
                        # Count overdue tasks
                        for task in tasks:
                            if task['status'] == 'assigned' and task.get('due_date'):
                                due_date = datetime.fromisoformat(task['due_date'])
                                if datetime.now() > due_date:
                                    overdue_count += 1
                        
                        total_assigned += assigned
                        total_completed += completed
                        total_failed += failed
                        
                        prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                        status_parts = []
                        
                        if assigned > 0:
                            status_parts.append(f"⏳{assigned}")
                        if completed > 0:
                            status_parts.append(f"✅{completed}")
                        if failed > 0:
                            status_parts.append(f"❌{failed}")
                        
                        if status_parts:
                            prospect_summaries.append(f"**{prospect_name}**: {' '.join(status_parts)}")
                
                # Summary stats
                embed.add_field(
                    name="📊 Quick Stats",
                    value=f"⏳ **Assigned:** {total_assigned}\n✅ **Completed:** {total_completed}\n❌ **Failed:** {total_failed}\n🚨 **Overdue:** {overdue_count}",
                    inline=True
                )
                
                # Prospect summaries
                if prospect_summaries:
                    embed.add_field(
                        name="👥 Prospects with Tasks",
                        value="\n".join(prospect_summaries[:10]),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="👥 Task Activity",
                        value="No prospects have tasks assigned",
                        inline=False
                    )
            
            embed.set_footer(text="Use /prospect-task overdue to see overdue tasks")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing prospect tasks: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while listing tasks: {str(e)}", 
                ephemeral=True
            )

    async def _task_overdue(self, interaction: discord.Interaction):
        """Show all overdue tasks across prospects"""
        try:
            await interaction.response.defer()
            
            # Get all overdue tasks
            overdue_tasks = await self.bot.db.get_overdue_prospect_tasks(interaction.guild.id)
            
            embed = discord.Embed(
                title="🚨 Overdue Prospect Tasks",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            if not overdue_tasks:
                embed.description = "🎉 No overdue tasks! All prospects are up to date."
                embed.color = discord.Color.green()
                await interaction.followup.send(embed=embed)
                return
            
            embed.add_field(
                name="📊 Summary",
                value=f"🚨 **Total Overdue:** {len(overdue_tasks)}",
                inline=True
            )
            
            # Group by prospect
            prospect_tasks = {}
            for task in overdue_tasks:
                prospect_id = task['prospect_id']
                if prospect_id not in prospect_tasks:
                    prospect_tasks[prospect_id] = []
                prospect_tasks[prospect_id].append(task)
            
            # Show overdue tasks by prospect
            overdue_list = []
            for prospect_id, tasks in list(prospect_tasks.items())[:10]:  # Limit to 10 prospects
                prospect_name = tasks[0].get('prospect_name', f"User {tasks[0].get('prospect_user_id', 'Unknown')}")
                
                prospect_overdue = []
                for task in tasks[:3]:  # Show up to 3 tasks per prospect
                    due_date = datetime.fromisoformat(task['due_date'])
                    days_overdue = (datetime.now() - due_date).days
                    
                    prospect_overdue.append(
                        f"   • `{task['id']}` {task['task_name']} ({days_overdue} days overdue)"
                    )
                
                if len(tasks) > 3:
                    prospect_overdue.append(f"   • *...and {len(tasks) - 3} more overdue tasks*")
                
                overdue_list.append(f"🚨 **{prospect_name}**\n" + "\n".join(prospect_overdue))
            
            if len(prospect_tasks) > 10:
                overdue_list.append(f"\n*...and {len(prospect_tasks) - 10} more prospects with overdue tasks*")
            
            embed.add_field(
                name="📋 Overdue Tasks by Prospect",
                value="\n\n".join(overdue_list) if overdue_list else "No overdue tasks",
                inline=False
            )
            
            embed.set_footer(text="Consider following up on these overdue tasks")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting overdue tasks: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while getting overdue tasks: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(name="prospect-note", description="Prospect notes and strikes management commands")
    @app_commands.describe(
        action="The action to perform",
        prospect="The prospect user",
        content="Note content or search query",
        is_strike="Whether this note is a strike (default: False)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add note", value="add"),
        app_commands.Choice(name="Add strike", value="strike"),
        app_commands.Choice(name="List notes", value="list"),
        app_commands.Choice(name="Search notes", value="search")
    ])
    async def prospect_note(
        self, 
        interaction: discord.Interaction, 
        action: str, 
        prospect: Optional[discord.Member] = None,
        content: Optional[str] = None,
        is_strike: Optional[bool] = False
    ):
        """Main prospect notes management command with subcommands"""
        # Permission check
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        if action == "add":
            await self._note_add(interaction, prospect, content, is_strike)
        elif action == "strike":
            await self._note_add(interaction, prospect, content, True)  # Force is_strike=True
        elif action == "list":
            await self._note_list(interaction, prospect)
        elif action == "search":
            await self._note_search(interaction, content, prospect)

    async def _note_add(self, interaction: discord.Interaction, prospect: discord.Member, content: str, is_strike: bool):
        """Add a note or strike to a prospect"""
        if not prospect:
            await interaction.response.send_message("❌ Please specify a prospect to add a note to.", ephemeral=True)
            return
        if not content:
            note_type = "strike" if is_strike else "note"
            await interaction.response.send_message(f"❌ Please provide content for the {note_type}.", ephemeral=True)
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
            
            # Create note
            note_id = await self.bot.db.create_prospect_note(
                prospect_record['id'],
                content,
                interaction.user.id,
                is_strike=is_strike
            )
            
            # Update strikes count if it's a strike
            current_strikes = prospect_record.get('strikes', 0)
            if is_strike:
                new_strikes = current_strikes + 1
                await self.bot.db.update_prospect_strikes(prospect_record['id'], new_strikes)
            
            # Determine note type for display
            note_type = "Strike" if is_strike else "Note"
            color = discord.Color.red() if is_strike else discord.Color.blue()
            
            # Create embed
            embed = discord.Embed(
                title=f"{'⚠️' if is_strike else '📝'} {note_type} Added",
                color=color,
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Note ID", value=f"`{note_id}`", inline=True)
            
            embed.add_field(name="Content", value=content, inline=False)
            
            if is_strike:
                new_total_strikes = current_strikes + 1
                embed.add_field(name="Total Strikes", value=f"{new_total_strikes}", inline=True)
                
                # Check if strikes are reaching a threshold
                if new_total_strikes >= 3:
                    embed.add_field(name="⚠️ Warning", value="This prospect has 3+ strikes!", inline=True)
                elif new_total_strikes >= 2:
                    embed.add_field(name="⚠️ Notice", value="This prospect has 2+ strikes", inline=True)
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect
            try:
                dm_embed = discord.Embed(
                    title=f"{'⚠️ Strike Added' if is_strike else '📝 Note Added'}",
                    description=f"A {'strike' if is_strike else 'note'} has been added to your record in **{interaction.guild.name}**",
                    color=color
                )
                dm_embed.add_field(name="Content", value=content, inline=False)
                dm_embed.add_field(name="Added by", value=interaction.user.display_name, inline=True)
                
                if is_strike:
                    new_total_strikes = current_strikes + 1
                    dm_embed.add_field(name="Total Strikes", value=f"{new_total_strikes}", inline=True)
                    
                    if new_total_strikes >= 3:
                        dm_embed.add_field(
                            name="⚠️ Important", 
                            value="You now have 3+ strikes. Please speak with leadership immediately.", 
                            inline=False
                        )
                
                dm_embed.set_footer(text=f"Note ID: {note_id}")
                await prospect.send(embed=dm_embed)
            except:
                pass  # User has DMs disabled
            
            # Log to leadership channel if configured
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    log_embed = embed.copy()
                    await leadership_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Error adding prospect note: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while adding the note: {str(e)}", 
                ephemeral=True
            )

    async def _note_list(self, interaction: discord.Interaction, prospect: discord.Member):
        """List notes for a prospect or all prospect notes"""
        try:
            await interaction.response.defer()
            
            if prospect:
                # Get notes for specific prospect
                prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
                if not prospect_record:
                    await interaction.followup.send(
                        f"❌ {prospect.mention} is not a prospect!", 
                        ephemeral=True
                    )
                    return
                
                notes = await self.bot.db.get_prospect_notes(prospect_record['id'])
                
                embed = discord.Embed(
                    title=f"📝 Notes for {prospect.display_name}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                if not notes:
                    embed.description = "No notes found for this prospect."
                    await interaction.followup.send(embed=embed)
                    return
                
                # Separate strikes and regular notes
                strikes = [n for n in notes if n.get('is_strike', False)]
                regular_notes = [n for n in notes if not n.get('is_strike', False)]
                
                # Add summary
                embed.add_field(
                    name="📊 Summary",
                    value=f"📝 Notes: {len(regular_notes)}\n⚠️ Strikes: {len(strikes)}\n📋 Total: {len(notes)}",
                    inline=True
                )
                
                # Show strikes first (most important)
                if strikes:
                    strikes_list = []
                    for i, note in enumerate(strikes[:5]):  # Show up to 5 strikes
                        created_date = datetime.fromisoformat(note['created_at'])
                        author_name = note.get('author_name', 'Unknown')
                        
                        content_preview = note['content'][:60] + ('...' if len(note['content']) > 60 else '')
                        
                        strikes_list.append(
                            f"`{note['id']}` **Strike {i+1}** - <t:{int(created_date.timestamp())}:d>\n"
                            f"   └ {content_preview}\n"
                            f"   └ *By: {author_name}*"
                        )
                    
                    if len(strikes) > 5:
                        strikes_list.append(f"\n*...and {len(strikes) - 5} more strikes*")
                    
                    embed.add_field(
                        name="⚠️ Strikes",
                        value="\n".join(strikes_list),
                        inline=False
                    )
                
                # Show recent regular notes
                if regular_notes:
                    notes_list = []
                    for note in regular_notes[-5:]:  # Show last 5 notes
                        created_date = datetime.fromisoformat(note['created_at'])
                        author_name = note.get('author_name', 'Unknown')
                        
                        content_preview = note['content'][:80] + ('...' if len(note['content']) > 80 else '')
                        
                        notes_list.append(
                            f"`{note['id']}` <t:{int(created_date.timestamp())}:d> - *{author_name}*\n"
                            f"   └ {content_preview}"
                        )
                    
                    if len(regular_notes) > 5:
                        notes_list.append(f"\n*...and {len(regular_notes) - 5} more notes*")
                    
                    embed.add_field(
                        name="📝 Recent Notes",
                        value="\n".join(notes_list),
                        inline=False
                    )
            else:
                # Show overview of all prospect notes
                active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
                
                embed = discord.Embed(
                    title="📝 All Prospect Notes Overview",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                if not active_prospects:
                    embed.description = "No active prospects found."
                    await interaction.followup.send(embed=embed)
                    return
                
                total_notes = 0
                total_strikes = 0
                prospect_summaries = []
                
                for prospect in active_prospects[:10]:  # Limit to 10 prospects
                    notes = await self.bot.db.get_prospect_notes(prospect['id'])
                    
                    if notes:
                        strikes_count = len([n for n in notes if n.get('is_strike', False)])
                        regular_notes_count = len(notes) - strikes_count
                        
                        total_notes += regular_notes_count
                        total_strikes += strikes_count
                        
                        prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                        status_parts = []
                        
                        if regular_notes_count > 0:
                            status_parts.append(f"📝{regular_notes_count}")
                        if strikes_count > 0:
                            status_parts.append(f"⚠️{strikes_count}")
                        
                        if status_parts:
                            prospect_summaries.append(f"**{prospect_name}**: {' '.join(status_parts)}")
                
                # Summary stats
                embed.add_field(
                    name="📊 Quick Stats",
                    value=f"📝 **Total Notes:** {total_notes}\n⚠️ **Total Strikes:** {total_strikes}\n👥 **Active Prospects:** {len(active_prospects)}",
                    inline=True
                )
                
                # Prospect summaries
                if prospect_summaries:
                    embed.add_field(
                        name="👥 Prospects with Notes/Strikes",
                        value="\n".join(prospect_summaries[:10]),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="👥 Prospects with Notes",
                        value="No prospects have notes or strikes",
                        inline=False
                    )
            
            embed.set_footer(text="Use /prospect-note search <query> to search notes")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing prospect notes: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while listing notes: {str(e)}", 
                ephemeral=True
            )

    async def _note_search(self, interaction: discord.Interaction, query: str, prospect: discord.Member):
        """Search prospect notes"""
        if not query:
            await interaction.response.send_message("❌ Please provide a search query.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Search notes
            if prospect:
                # Search within specific prospect's notes
                prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
                if not prospect_record:
                    await interaction.followup.send(
                        f"❌ {prospect.mention} is not a prospect!", 
                        ephemeral=True
                    )
                    return
                
                search_results = await self.bot.db.search_prospect_notes(
                    guild_id=interaction.guild.id,
                    query=query,
                    prospect_id=prospect_record['id']
                )
                
                embed_title = f"🔍 Search Results for '{query}' in {prospect.display_name}'s Notes"
            else:
                # Search across all prospect notes
                search_results = await self.bot.db.search_prospect_notes(
                    guild_id=interaction.guild.id,
                    query=query
                )
                
                embed_title = f"🔍 Search Results for '{query}'"
            
            embed = discord.Embed(
                title=embed_title,
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            if not search_results:
                embed.description = "No notes found matching your search query."
                await interaction.followup.send(embed=embed)
                return
            
            # Add summary
            strikes_found = len([n for n in search_results if n.get('is_strike', False)])
            notes_found = len(search_results) - strikes_found
            
            embed.add_field(
                name="📊 Found",
                value=f"📝 Notes: {notes_found}\n⚠️ Strikes: {strikes_found}\n📋 Total: {len(search_results)}",
                inline=True
            )
            
            # Display results (limit to 10)
            results_list = []
            for i, note in enumerate(search_results[:10]):
                prospect_name = note.get('prospect_name', f"User {note.get('prospect_user_id', 'Unknown')}")
                created_date = datetime.fromisoformat(note['created_at'])
                author_name = note.get('author_name', 'Unknown')
                note_type = "⚠️ Strike" if note.get('is_strike', False) else "📝 Note"
                
                # Highlight the search term in content preview
                content = note['content']
                content_preview = content[:100] + ('...' if len(content) > 100 else '')
                
                results_list.append(
                    f"`{note['id']}` {note_type} - **{prospect_name}**\n"
                    f"   └ <t:{int(created_date.timestamp())}:d> by *{author_name}*\n"
                    f"   └ {content_preview}"
                )
            
            if len(search_results) > 10:
                results_list.append(f"\n*...and {len(search_results) - 10} more results*")
            
            embed.add_field(
                name="📋 Results",
                value="\n".join(results_list),
                inline=False
            )
            
            embed.set_footer(text=f"Search query: '{query}' • Use more specific terms to narrow results")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error searching prospect notes: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while searching notes: {str(e)}", 
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(ProspectTasksAndNotesConsolidated(bot))

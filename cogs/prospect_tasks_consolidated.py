import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional, List
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectTasksConsolidated(commands.Cog):
    """Consolidated prospect task management commands with subcommands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectTasksConsolidated cog initialized")

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
            await self.bot.db.update_task_status(task_id, 'completed', interaction.user.id)
            
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
            
            embed.add_field(name="Description", value=task['description'], inline=False)
            
            if task.get('due_date'):
                due_date = datetime.fromisoformat(task['due_date'])
                embed.add_field(name="Was Due", value=f"<t:{int(due_date.timestamp())}:F>", inline=True)
                
                # Check if completed on time
                if datetime.now() <= due_date:
                    embed.add_field(name="Status", value="✅ Completed on time", inline=True)
                else:
                    embed.add_field(name="Status", value="⚠️ Completed late", inline=True)
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect
            if prospect_member:
                try:
                    dm_embed = discord.Embed(
                        title="✅ Task Completed",
                        description=f"Your task has been marked complete in **{interaction.guild.name}**",
                        color=discord.Color.green()
                    )
                    dm_embed.add_field(name="Task", value=task['description'], inline=False)
                    dm_embed.add_field(name="Completed by", value=interaction.user.display_name, inline=True)
                    dm_embed.set_footer(text=f"Task ID: {task_id}")
                    await prospect_member.send(embed=dm_embed)
                except:
                    pass
            
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
            await self.bot.db.update_task_status(task_id, 'failed', interaction.user.id)
            
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
            embed.add_field(name="Marked failed by", value=interaction.user.mention, inline=True)
            
            embed.add_field(name="Description", value=task['description'], inline=False)
            
            if task.get('due_date'):
                due_date = datetime.fromisoformat(task['due_date'])
                embed.add_field(name="Was Due", value=f"<t:{int(due_date.timestamp())}:F>", inline=True)
            
            embed.set_footer(text="Consider discussing this failure with the prospect")
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect
            if prospect_member:
                try:
                    dm_embed = discord.Embed(
                        title="❌ Task Failed",
                        description=f"Your task has been marked as failed in **{interaction.guild.name}**",
                        color=discord.Color.red()
                    )
                    dm_embed.add_field(name="Task", value=task['description'], inline=False)
                    dm_embed.add_field(name="Reason", value="Please speak with leadership for details", inline=False)
                    dm_embed.set_footer(text=f"Task ID: {task_id}")
                    await prospect_member.send(embed=dm_embed)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error failing prospect task: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while failing the task: {str(e)}", 
                ephemeral=True
            )

    async def _task_list(self, interaction: discord.Interaction, prospect: discord.Member):
        """List tasks for a prospect or all tasks"""
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
                    embed.description = "No tasks found for this prospect."
                    await interaction.followup.send(embed=embed)
                    return
                
                # Group tasks by status
                assigned_tasks = [t for t in tasks if t['status'] == 'assigned']
                completed_tasks = [t for t in tasks if t['status'] == 'completed']
                failed_tasks = [t for t in tasks if t['status'] == 'failed']
                
                # Add summary
                embed.add_field(
                    name="📊 Summary",
                    value=f"⏳ Assigned: {len(assigned_tasks)}\n✅ Completed: {len(completed_tasks)}\n❌ Failed: {len(failed_tasks)}",
                    inline=True
                )
                
                # Show assigned tasks (most important)
                if assigned_tasks:
                    assigned_list = []
                    for task in assigned_tasks[:5]:  # Limit to 5
                        due_info = ""
                        if task.get('due_date'):
                            due_date = datetime.fromisoformat(task['due_date'])
                            if due_date < datetime.now():
                                due_info = " ⚠️ OVERDUE"
                            elif (due_date - datetime.now()).days <= 3:
                                due_info = " 🔶 Due soon"
                        
                        assigned_list.append(f"`{task['id']}` {task['description'][:50]}{'...' if len(task['description']) > 50 else ''}{due_info}")
                    
                    if len(assigned_tasks) > 5:
                        assigned_list.append(f"*...and {len(assigned_tasks) - 5} more assigned tasks*")
                    
                    embed.add_field(
                        name="⏳ Assigned Tasks",
                        value="\n".join(assigned_list),
                        inline=False
                    )
                
                # Show recent completed tasks
                if completed_tasks:
                    completed_list = []
                    for task in completed_tasks[-3:]:  # Last 3 completed
                        completed_list.append(f"`{task['id']}` {task['description'][:50]}{'...' if len(task['description']) > 50 else ''}")
                    
                    embed.add_field(
                        name="✅ Recently Completed",
                        value="\n".join(completed_list),
                        inline=False
                    )
                
                # Show failed tasks
                if failed_tasks:
                    failed_list = []
                    for task in failed_tasks[-3:]:  # Last 3 failed
                        failed_list.append(f"`{task['id']}` {task['description'][:50]}{'...' if len(task['description']) > 50 else ''}")
                    
                    embed.add_field(
                        name="❌ Failed Tasks",
                        value="\n".join(failed_list),
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
                total_overdue = 0
                prospect_summaries = []
                
                for prospect in active_prospects[:10]:  # Limit to 10 prospects
                    tasks = await self.bot.db.get_prospect_tasks(prospect['id'])
                    assigned_tasks = [t for t in tasks if t['status'] == 'assigned']
                    
                    overdue_count = 0
                    for task in assigned_tasks:
                        if task.get('due_date'):
                            due_date = datetime.fromisoformat(task['due_date'])
                            if due_date < datetime.now():
                                overdue_count += 1
                    
                    total_assigned += len(assigned_tasks)
                    total_overdue += overdue_count
                    
                    if assigned_tasks:  # Only show prospects with assigned tasks
                        prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                        status_text = f"⏳{len(assigned_tasks)}"
                        if overdue_count > 0:
                            status_text += f" ⚠️{overdue_count}"
                        
                        prospect_summaries.append(f"**{prospect_name}**: {status_text}")
                
                # Summary stats
                embed.add_field(
                    name="📊 Quick Stats",
                    value=f"⏳ **Total Assigned:** {total_assigned}\n⚠️ **Overdue:** {total_overdue}\n👥 **Active Prospects:** {len(active_prospects)}",
                    inline=True
                )
                
                # Prospect summaries
                if prospect_summaries:
                    embed.add_field(
                        name="👥 Prospects with Assigned Tasks",
                        value="\n".join(prospect_summaries[:10]),
                        inline=False
                    )
                    
                    if len(prospect_summaries) > 10:
                        embed.add_field(
                            name="📄 Note",
                            value=f"Showing top 10 prospects. Use `/prospect-task list @prospect` for detailed view.",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="👥 Prospects with Tasks",
                        value="No prospects have assigned tasks",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing prospect tasks: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while listing tasks: {str(e)}", 
                ephemeral=True
            )

    async def _task_overdue(self, interaction: discord.Interaction):
        """Show all overdue tasks"""
        try:
            await interaction.response.defer()
            
            # Get all active prospects
            active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
            
            embed = discord.Embed(
                title="⚠️ Overdue Tasks",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            if not active_prospects:
                embed.description = "No active prospects found."
                await interaction.followup.send(embed=embed)
                return
            
            overdue_tasks = []
            
            for prospect in active_prospects:
                tasks = await self.bot.db.get_prospect_tasks(prospect['id'])
                
                for task in tasks:
                    if task['status'] == 'assigned' and task.get('due_date'):
                        due_date = datetime.fromisoformat(task['due_date'])
                        if due_date < datetime.now():
                            days_overdue = (datetime.now() - due_date).days
                            
                            prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                            overdue_tasks.append({
                                'task': task,
                                'prospect_name': prospect_name,
                                'days_overdue': days_overdue
                            })
            
            if not overdue_tasks:
                embed.add_field(
                    name="✅ Good News!",
                    value="No overdue tasks found. All prospects are keeping up with their assignments!",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Sort by days overdue (most overdue first)
            overdue_tasks.sort(key=lambda x: x['days_overdue'], reverse=True)
            
            # Add summary
            embed.add_field(
                name="📊 Summary",
                value=f"⚠️ **Total Overdue:** {len(overdue_tasks)}\n📅 **Most Overdue:** {overdue_tasks[0]['days_overdue']} days",
                inline=True
            )
            
            # List overdue tasks
            overdue_list = []
            for item in overdue_tasks[:10]:  # Limit to 10
                task = item['task']
                prospect_name = item['prospect_name']
                days_overdue = item['days_overdue']
                
                description = task['description'][:40] + ('...' if len(task['description']) > 40 else '')
                
                overdue_list.append(
                    f"**{prospect_name}** ({days_overdue} days overdue)\n"
                    f"└ `{task['id']}` {description}"
                )
            
            if len(overdue_tasks) > 10:
                overdue_list.append(f"\n*...and {len(overdue_tasks) - 10} more overdue tasks*")
            
            embed.add_field(
                name="⚠️ Overdue Tasks",
                value="\n".join(overdue_list),
                inline=False
            )
            
            embed.add_field(
                name="🔧 Actions",
                value="• Use `/prospect-task complete <id>` to mark complete\n• Use `/prospect-task fail <id>` to mark failed\n• Consider following up with prospects",
                inline=False
            )
            
            embed.set_footer(text="Tasks are considered overdue when past their due date")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing overdue tasks: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while showing overdue tasks: {str(e)}", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProspectTasksConsolidated(bot))

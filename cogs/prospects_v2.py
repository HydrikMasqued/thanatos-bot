"""
Thanatos Prospect Management System v2.0
Modern, comprehensive prospect management with streamlined workflow
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

class ProspectStatus:
    """Prospect status constants"""
    ACTIVE = "active"
    PATCHED = "patched"
    DROPPED = "dropped"
    INACTIVE = "inactive"

class ProspectActions:
    """Prospect action constants"""
    ADD_TASK = "add_task"
    ADD_NOTE = "add_note"
    ADD_STRIKE = "add_strike"
    PATCH = "patch"
    DROP = "drop"
    VIEW_DETAILS = "view_details"
    
class ProspectTaskStatus:
    """Task status constants"""
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    FAILED = "failed"
    OVERDUE = "overdue"

class ProspectView(discord.ui.View):
    """Interactive prospect management view"""
    
    def __init__(self, bot, prospect_data: Dict, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.prospect_data = prospect_data
        self.user_id = user_id
        self.prospect_id = prospect_data['id']
        self.guild_id = prospect_data['guild_id']

    @discord.ui.button(label="Add Task", style=discord.ButtonStyle.primary, emoji="📋")
    async def add_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a new task to the prospect"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        modal = AddTaskModal(self.bot, self.prospect_id, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Add Note", style=discord.ButtonStyle.secondary, emoji="📝")
    async def add_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a note to the prospect"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        modal = AddNoteModal(self.bot, self.prospect_id, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Add Strike", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def add_strike(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a strike to the prospect"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        modal = AddStrikeModal(self.bot, self.prospect_id, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Patch", style=discord.ButtonStyle.success, emoji="🎉")
    async def patch_prospect(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Patch the prospect"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        # Confirmation view
        view = ConfirmationView(self.bot, self.prospect_id, "patch")
        embed = discord.Embed(
            title="🎉 Confirm Patch",
            description=f"Are you sure you want to patch **{self.prospect_data.get('prospect_name', 'this prospect')}**?",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Drop", style=discord.ButtonStyle.danger, emoji="❌")
    async def drop_prospect(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Drop the prospect"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        # Confirmation view
        view = ConfirmationView(self.bot, self.prospect_id, "drop")
        embed = discord.Embed(
            title="❌ Confirm Drop",
            description=f"Are you sure you want to drop **{self.prospect_data.get('prospect_name', 'this prospect')}**?",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ConfirmationView(discord.ui.View):
    """Confirmation view for prospect actions"""
    
    def __init__(self, bot, prospect_id: int, action: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.prospect_id = prospect_id
        self.action = action

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the action"""
        if self.action == "patch":
            await self._patch_prospect(interaction)
        elif self.action == "drop":
            await self._drop_prospect(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the action"""
        await interaction.response.edit_message(
            content="❌ Action cancelled.", 
            embed=None, 
            view=None
        )

    async def _patch_prospect(self, interaction: discord.Interaction):
        """Patch the prospect"""
        try:
            success = await self.bot.db.update_prospect_status(
                self.prospect_id, 
                'patched'
            )
            
            if success:
                embed = discord.Embed(
                    title="🎉 Prospect Patched!",
                    description="The prospect has been successfully patched!",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.response.edit_message(
                    content="❌ Failed to patch prospect.",
                    embed=None,
                    view=None
                )
        except Exception as e:
            logger.error(f"Error patching prospect: {e}")
            await interaction.response.edit_message(
                content=f"❌ Error patching prospect: {e}",
                embed=None,
                view=None
            )

    async def _drop_prospect(self, interaction: discord.Interaction):
        """Drop the prospect"""
        try:
            success = await self.bot.db.update_prospect_status(
                self.prospect_id, 
                'dropped'
            )
            
            if success:
                embed = discord.Embed(
                    title="❌ Prospect Dropped",
                    description="The prospect has been dropped.",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.response.edit_message(
                    content="❌ Failed to drop prospect.",
                    embed=None,
                    view=None
                )
        except Exception as e:
            logger.error(f"Error dropping prospect: {e}")
            await interaction.response.edit_message(
                content=f"❌ Error dropping prospect: {e}",
                embed=None,
                view=None
            )

class AddTaskModal(discord.ui.Modal, title="Add Prospect Task"):
    """Modal for adding tasks to prospects"""
    
    def __init__(self, bot, prospect_id: int, guild_id: int):
        super().__init__()
        self.bot = bot
        self.prospect_id = prospect_id
        self.guild_id = guild_id

    task_name = discord.ui.TextInput(
        label="Task Name",
        placeholder="Enter the task name...",
        max_length=100,
        required=True
    )
    
    task_description = discord.ui.TextInput(
        label="Task Description",
        placeholder="Describe what the prospect needs to do...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )
    
    due_days = discord.ui.TextInput(
        label="Days to Complete",
        placeholder="Enter number of days (e.g., 7)",
        max_length=3,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle task submission"""
        try:
            # Calculate due date
            due_date = None
            if self.due_days.value:
                try:
                    days = int(self.due_days.value)
                    due_date = datetime.utcnow() + timedelta(days=days)
                except ValueError:
                    pass
            
            # Add task to database
            task_id = await self.bot.db.add_prospect_task(
                guild_id=self.guild_id,
                prospect_id=self.prospect_id,
                assigned_by_id=interaction.user.id,
                task_name=str(self.task_name.value),
                task_description=str(self.task_description.value),
                due_date=due_date
            )
            
            embed = discord.Embed(
                title="✅ Task Added",
                description=f"**{self.task_name.value}** has been assigned to the prospect.",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Description", value=self.task_description.value, inline=False)
            if due_date:
                embed.add_field(name="Due Date", value=f"<t:{int(due_date.timestamp())}:R>", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error adding prospect task: {e}")
            await interaction.response.send_message(f"❌ Error adding task: {e}", ephemeral=True)

class AddNoteModal(discord.ui.Modal, title="Add Prospect Note"):
    """Modal for adding notes to prospects"""
    
    def __init__(self, bot, prospect_id: int, guild_id: int):
        super().__init__()
        self.bot = bot
        self.prospect_id = prospect_id
        self.guild_id = guild_id

    note_text = discord.ui.TextInput(
        label="Note",
        placeholder="Enter your note about the prospect...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle note submission"""
        try:
            # Add note to database
            note_id = await self.bot.db.add_prospect_note(
                guild_id=self.guild_id,
                prospect_id=self.prospect_id,
                author_id=interaction.user.id,
                note_text=str(self.note_text.value),
                is_strike=False
            )
            
            embed = discord.Embed(
                title="📝 Note Added",
                description="Your note has been added to the prospect's record.",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Note", value=self.note_text.value, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error adding prospect note: {e}")
            await interaction.response.send_message(f"❌ Error adding note: {e}", ephemeral=True)

class AddStrikeModal(discord.ui.Modal, title="Add Strike"):
    """Modal for adding strikes to prospects"""
    
    def __init__(self, bot, prospect_id: int, guild_id: int):
        super().__init__()
        self.bot = bot
        self.prospect_id = prospect_id
        self.guild_id = guild_id

    strike_reason = discord.ui.TextInput(
        label="Strike Reason",
        placeholder="Explain why this strike is being given...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle strike submission"""
        try:
            # Add strike note to database
            note_id = await self.bot.db.add_prospect_note(
                guild_id=self.guild_id,
                prospect_id=self.prospect_id,
                author_id=interaction.user.id,
                note_text=str(self.strike_reason.value),
                is_strike=True
            )
            
            # Note: Strike count is automatically updated in the database method
            
            embed = discord.Embed(
                title="⚠️ Strike Added",
                description="A strike has been added to the prospect's record.",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Reason", value=self.strike_reason.value, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error adding prospect strike: {e}")
            await interaction.response.send_message(f"❌ Error adding strike: {e}", ephemeral=True)

class ProspectManagementV2(commands.Cog):
    """Modern Prospect Management System v2.0"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        logger.info("Prospect Management v2.0 initialized")

    async def _check_management_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has prospect management permissions"""
        config = await self.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            await interaction.response.send_message(
                "❌ Officer role not configured. Please configure the bot first.", 
                ephemeral=True
            )
            return False
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ This command is only available to officers.", 
                ephemeral=True
            )
            return False
        
        return True

    @app_commands.command(name="prospect", description="Manage prospects - add, view, patch, or drop")
    @app_commands.describe(
        action="What action to perform",
        prospect="The prospect member",
        sponsor="The sponsoring member (for adding prospects)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add Prospect", value="add"),
        app_commands.Choice(name="View Prospect", value="view"),
        app_commands.Choice(name="List All Prospects", value="list"),
        app_commands.Choice(name="Patch Prospect", value="patch"),
        app_commands.Choice(name="Drop Prospect", value="drop")
    ])
    async def prospect_command(
        self,
        interaction: discord.Interaction,
        action: str,
        prospect: Optional[discord.Member] = None,
        sponsor: Optional[discord.Member] = None
    ):
        """Main prospect management command"""
        if not await self._check_management_permissions(interaction):
            return
            
        if action == "add":
            await self._add_prospect(interaction, prospect, sponsor)
        elif action == "view":
            await self._view_prospect(interaction, prospect)
        elif action == "list":
            await self._list_prospects(interaction)
        elif action == "patch":
            await self._patch_prospect(interaction, prospect)
        elif action == "drop":
            await self._drop_prospect(interaction, prospect)

    async def _add_prospect(self, interaction: discord.Interaction, prospect: discord.Member, sponsor: discord.Member):
        """Add a new prospect"""
        if not prospect or not sponsor:
            await interaction.response.send_message(
                "❌ Both prospect and sponsor must be specified when adding a prospect.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer()
        
        try:
            # Check if already a prospect
            existing = await self.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if existing and existing['status'] == ProspectStatus.ACTIVE:
                await interaction.followup.send(
                    "❌ This member is already an active prospect.", 
                    ephemeral=True
                )
                return
            
            # Ensure member records exist for both prospect and sponsor
            await self.db.add_or_update_member(
                guild_id=interaction.guild.id,
                user_id=prospect.id,
                discord_name=prospect.display_name,
                discord_username=prospect.name
            )
            
            await self.db.add_or_update_member(
                guild_id=interaction.guild.id,
                user_id=sponsor.id,
                discord_name=sponsor.display_name,
                discord_username=sponsor.name
            )
            
            # Add to database
            prospect_id = await self.db.add_prospect(
                guild_id=interaction.guild.id,
                user_id=prospect.id,
                sponsor_id=sponsor.id
            )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Prospect Added",
                description=f"{prospect.mention} has been added as a prospect",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=sponsor.mention, inline=True)
            embed.add_field(name="Added By", value=interaction.user.mention, inline=True)
            embed.set_footer(text=f"Prospect ID: {prospect_id}")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Added prospect {prospect.id} sponsored by {sponsor.id} in guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error adding prospect: {e}")
            await interaction.followup.send(f"❌ Error adding prospect: {e}", ephemeral=True)

    async def _view_prospect(self, interaction: discord.Interaction, prospect: discord.Member):
        """View detailed prospect information"""
        if not prospect:
            await interaction.response.send_message(
                "❌ Please specify a prospect member to view.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer()
        
        try:
            # Get prospect info
            prospect_info = await self.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if not prospect_info:
                await interaction.followup.send(
                    "❌ This member is not a prospect.", 
                    ephemeral=True
                )
                return
            
            # Get tasks and notes
            tasks = await self.db.get_prospect_tasks(prospect_info['id'])
            notes = await self.db.get_prospect_notes(prospect_info['id'])
            
            # Create detailed embed
            embed = discord.Embed(
                title=f"👤 Prospect: {prospect.display_name}",
                color=self._get_status_color(prospect_info['status']),
                timestamp=datetime.utcnow()
            )
            
            # Basic info
            sponsor = interaction.guild.get_member(prospect_info['sponsor_id'])
            start_date = datetime.fromisoformat(prospect_info['start_date'].replace('Z', '+00:00'))
            days_active = (datetime.utcnow() - start_date).days
            
            embed.add_field(
                name="Basic Information",
                value=f"**Status:** {prospect_info['status'].title()}\n"
                      f"**Sponsor:** {sponsor.mention if sponsor else 'Unknown'}\n"
                      f"**Start Date:** <t:{int(start_date.timestamp())}:D>\n"
                      f"**Days Active:** {days_active}\n"
                      f"**Strikes:** {prospect_info['strikes']}/3",
                inline=False
            )
            
            # Tasks summary
            if tasks:
                task_summary = []
                for task in tasks[:5]:  # Show first 5 tasks
                    status_emoji = self._get_task_status_emoji(task['status'])
                    task_summary.append(f"{status_emoji} {task['task_name']}")
                
                if len(tasks) > 5:
                    task_summary.append(f"... and {len(tasks) - 5} more")
                
                embed.add_field(
                    name=f"Tasks ({len(tasks)})",
                    value="\n".join(task_summary) or "No tasks assigned",
                    inline=True
                )
            
            # Recent notes
            if notes:
                note_summary = []
                for note in notes[:3]:  # Show first 3 notes
                    note_type = "🔴" if note['is_strike'] else "📝"
                    note_summary.append(f"{note_type} {note['note_text'][:30]}...")
                
                if len(notes) > 3:
                    note_summary.append(f"... and {len(notes) - 3} more")
                
                embed.add_field(
                    name=f"Recent Notes ({len(notes)})",
                    value="\n".join(note_summary) or "No notes",
                    inline=True
                )
            
            # Create interactive view
            view = ProspectView(self.bot, prospect_info, interaction.user.id)
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error viewing prospect: {e}")
            await interaction.followup.send(f"❌ Error viewing prospect: {e}", ephemeral=True)

    async def _list_prospects(self, interaction: discord.Interaction):
        """List all prospects"""
        await interaction.response.defer()
        
        try:
            # Get both active and archived prospects
            active_prospects = await self.db.get_active_prospects(interaction.guild.id)
            archived_prospects = await self.db.get_archived_prospects(interaction.guild.id)
            prospects = active_prospects + archived_prospects
            
            if not prospects:
                embed = discord.Embed(
                    title="📋 Prospect List",
                    description="No prospects found.",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Group by status
            active_prospects = [p for p in prospects if p['status'] == ProspectStatus.ACTIVE]
            inactive_prospects = [p for p in prospects if p['status'] != ProspectStatus.ACTIVE]
            
            embed = discord.Embed(
                title="📋 Prospect List",
                description=f"Found {len(prospects)} total prospects",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            if active_prospects:
                active_list = []
                for prospect in active_prospects[:10]:  # Limit to 10
                    # Use database-provided names first, fall back to Discord lookup if needed
                    name = prospect.get('prospect_name')
                    sponsor_name = prospect.get('sponsor_name')
                    
                    # If database doesn't have names, try Discord lookup
                    if not name:
                        member = interaction.guild.get_member(prospect['user_id'])
                        name = member.display_name if member else f"Unknown User ({prospect['user_id']})"
                    
                    if not sponsor_name:
                        sponsor = interaction.guild.get_member(prospect['sponsor_id'])
                        sponsor_name = sponsor.display_name if sponsor else "Unknown Sponsor"
                    
                    days = (datetime.utcnow() - datetime.fromisoformat(prospect['start_date'].replace('Z', '+00:00'))).days
                    
                    active_list.append(f"• **{name}** (Sponsor: {sponsor_name}, {days}d, {prospect['strikes']}⚠️)")
                
                if len(active_prospects) > 10:
                    active_list.append(f"... and {len(active_prospects) - 10} more")
                
                embed.add_field(
                    name=f"Active Prospects ({len(active_prospects)})",
                    value="\n".join(active_list),
                    inline=False
                )
            
            if inactive_prospects:
                inactive_list = []
                for prospect in inactive_prospects[:10]:  # Limit to 10
                    # Use database-provided names first, fall back to Discord lookup if needed
                    name = prospect.get('prospect_name')
                    sponsor_name = prospect.get('sponsor_name')
                    
                    # If database doesn't have names, try Discord lookup
                    if not name:
                        member = interaction.guild.get_member(prospect['user_id'])
                        name = member.display_name if member else f"Unknown User ({prospect['user_id']})"
                    
                    if not sponsor_name:
                        sponsor = interaction.guild.get_member(prospect['sponsor_id'])
                        sponsor_name = sponsor.display_name if sponsor else "Unknown Sponsor"
                    
                    # Get end date if available
                    end_info = ""
                    if prospect.get('end_date'):
                        try:
                            end_date = datetime.fromisoformat(prospect['end_date'].replace('Z', '+00:00'))
                            end_info = f" (Ended: {end_date.strftime('%m/%d/%Y')})"
                        except:
                            pass
                    
                    status_emoji = "🎉" if prospect['status'] == 'patched' else "❌"
                    inactive_list.append(f"{status_emoji} **{name}** - {prospect['status'].title()}{end_info}")
                
                if len(inactive_prospects) > 10:
                    inactive_list.append(f"... and {len(inactive_prospects) - 10} more")
                
                embed.add_field(
                    name=f"Inactive Prospects ({len(inactive_prospects)})",
                    value="\n".join(inactive_list),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing prospects: {e}")
            await interaction.followup.send(f"❌ Error listing prospects: {e}", ephemeral=True)

    async def _patch_prospect(self, interaction: discord.Interaction, prospect: discord.Member):
        """Patch a prospect"""
        if not prospect:
            await interaction.response.send_message(
                "❌ Please specify a prospect member to patch.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer()
        
        try:
            # Get prospect info
            prospect_info = await self.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if not prospect_info or prospect_info['status'] != ProspectStatus.ACTIVE:
                await interaction.followup.send(
                    "❌ This member is not an active prospect.", 
                    ephemeral=True
                )
                return
            
            # Patch the prospect
            success = await self.db.update_prospect_status(
                prospect_info['id'], 
                'patched'
            )
            
            if success:
                embed = discord.Embed(
                    title="🎉 Prospect Patched!",
                    description=f"{prospect.mention} has been successfully patched!",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="Patched By", value=interaction.user.mention, inline=True)
                embed.set_footer(text="Welcome to full membership!")
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Patched prospect {prospect.id} in guild {interaction.guild.id}")
            else:
                await interaction.followup.send("❌ Failed to patch prospect.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error patching prospect: {e}")
            await interaction.followup.send(f"❌ Error patching prospect: {e}", ephemeral=True)

    async def _drop_prospect(self, interaction: discord.Interaction, prospect: discord.Member):
        """Drop a prospect"""
        if not prospect:
            await interaction.response.send_message(
                "❌ Please specify a prospect member to drop.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer()
        
        try:
            # Get prospect info
            prospect_info = await self.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if not prospect_info or prospect_info['status'] != ProspectStatus.ACTIVE:
                await interaction.followup.send(
                    "❌ This member is not an active prospect.", 
                    ephemeral=True
                )
                return
            
            # Drop the prospect
            success = await self.db.update_prospect_status(
                prospect_info['id'], 
                'dropped'
            )
            
            if success:
                embed = discord.Embed(
                    title="❌ Prospect Dropped",
                    description=f"{prospect.mention} has been dropped from the prospect program.",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                embed.add_field(name="Dropped By", value=interaction.user.mention, inline=True)
                
                await interaction.followup.send(embed=embed)
                logger.info(f"Dropped prospect {prospect.id} in guild {interaction.guild.id}")
            else:
                await interaction.followup.send("❌ Failed to drop prospect.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error dropping prospect: {e}")
            await interaction.followup.send(f"❌ Error dropping prospect: {e}", ephemeral=True)

    def _get_status_color(self, status: str) -> discord.Color:
        """Get color based on prospect status"""
        colors = {
            ProspectStatus.ACTIVE: discord.Color.blue(),
            ProspectStatus.PATCHED: discord.Color.green(),
            ProspectStatus.DROPPED: discord.Color.red(),
            ProspectStatus.INACTIVE: discord.Color.greyple()
        }
        return colors.get(status, discord.Color.greyple())

    def _get_task_status_emoji(self, status: str) -> str:
        """Get emoji for task status"""
        emojis = {
            ProspectTaskStatus.ASSIGNED: "📋",
            ProspectTaskStatus.COMPLETED: "✅",
            ProspectTaskStatus.FAILED: "❌",
            ProspectTaskStatus.OVERDUE: "🔴"
        }
        return emojis.get(status, "📋")

async def setup(bot):
    await bot.add_cog(ProspectManagementV2(bot))
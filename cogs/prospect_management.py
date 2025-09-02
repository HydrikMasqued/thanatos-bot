import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional, Dict, List
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectManagement(commands.Cog):
    """Core prospect management commands for adding, patching, and dropping prospects"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectManagement cog initialized")

    async def create_prospect_roles(self, guild: discord.Guild, prospect_name: str, sponsor_name: str) -> tuple[Optional[discord.Role], Optional[discord.Role]]:
        """Create 'Sponsored by X' and 'Sponsors' roles if they don't exist"""
        try:
            sponsored_by_role = None
            sponsors_role = None
            
            # Create "Sponsored by [Sponsor]" role
            sponsored_by_name = f"Sponsored by {sponsor_name}"
            sponsored_by_role = discord.utils.get(guild.roles, name=sponsored_by_name)
            if not sponsored_by_role:
                sponsored_by_role = await guild.create_role(
                    name=sponsored_by_name,
                    color=discord.Color.orange(),
                    mentionable=True,
                    reason=f"Auto-created for prospect {prospect_name}"
                )
                logger.info(f"Created role '{sponsored_by_name}' in guild {guild.id}")
            
            # Create or get "Sponsors" role
            sponsors_role = discord.utils.get(guild.roles, name="Sponsors")
            if not sponsors_role:
                sponsors_role = await guild.create_role(
                    name="Sponsors",
                    color=discord.Color.blue(),
                    mentionable=True,
                    reason="Auto-created for prospect management"
                )
                logger.info(f"Created role 'Sponsors' in guild {guild.id}")
            
            return sponsored_by_role, sponsors_role
            
        except Exception as e:
            logger.error(f"Failed to create prospect roles: {e}")
            return None, None

    async def cleanup_prospect_roles(self, guild: discord.Guild, sponsored_by_role_id: int):
        """Clean up 'Sponsored by X' role if no longer needed"""
        try:
            role = guild.get_role(sponsored_by_role_id)
            if role and len(role.members) == 0:
                await role.delete(reason="No longer needed - prospect completed/dropped")
                logger.info(f"Cleaned up role '{role.name}' in guild {guild.id}")
        except Exception as e:
            logger.error(f"Failed to cleanup prospect role: {e}")

    @app_commands.command(name="prospect-add", description="Add a new prospect with a sponsor")
    @app_commands.describe(
        prospect="The user to add as a prospect",
        sponsor="The member who will sponsor this prospect"
    )
    async def prospect_add(self, interaction: discord.Interaction, prospect: discord.Member, sponsor: discord.Member):
        """Add a new prospect"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Check if user is already a prospect
            existing_prospect = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            if existing_prospect and existing_prospect['status'] == 'active':
                await interaction.followup.send(
                    f"❌ {prospect.mention} is already an active prospect!", 
                    ephemeral=True
                )
                return
            
            # Check if prospect is already a full member
            member_record = await self.bot.db.get_member(interaction.guild.id, prospect.id)
            if member_record and member_record.get('rank') in ['Full Patch', 'President', 'Vice President', 'Sergeant At Arms', 'Secretary', 'Treasurer', 'Road Captain', 'Tailgunner', 'Enforcer']:
                await interaction.followup.send(
                    f"❌ {prospect.mention} is already a full member!", 
                    ephemeral=True
                )
                return
            
            # Add members to database if they don't exist
            await self.bot.db.add_or_update_member(
                interaction.guild.id, 
                prospect.id, 
                prospect.display_name, 
                discord_username=prospect.name
            )
            await self.bot.db.add_or_update_member(
                interaction.guild.id, 
                sponsor.id, 
                sponsor.display_name, 
                discord_username=sponsor.name
            )
            
            # Create prospect roles
            sponsored_by_role, sponsors_role = await self.create_prospect_roles(
                interaction.guild, 
                prospect.display_name, 
                sponsor.display_name
            )
            
            # Create prospect record
            prospect_id = await self.bot.db.create_prospect(
                interaction.guild.id,
                prospect.id,
                sponsor.id,
                sponsored_by_role.id if sponsored_by_role else None,
                sponsors_role.id if sponsors_role else None
            )
            
            # Assign roles
            roles_assigned = []
            if sponsored_by_role:
                await prospect.add_roles(sponsored_by_role, reason=f"Added as prospect sponsored by {sponsor.display_name}")
                roles_assigned.append(sponsored_by_role.mention)
            
            if sponsors_role:
                await sponsor.add_roles(sponsors_role, reason=f"Sponsoring prospect {prospect.display_name}")
                roles_assigned.append(f"{sponsors_role.mention} (to sponsor)")
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Prospect Added Successfully",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=sponsor.mention, inline=True)
            embed.add_field(name="Start Date", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=False)
            
            if roles_assigned:
                embed.add_field(name="Roles Assigned", value="\n".join(roles_assigned), inline=False)
            
            embed.set_footer(text=f"Prospect ID: {prospect_id} • Added by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
            # Log to leadership channel if configured
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    leadership_embed = embed.copy()
                    leadership_embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
                    await leadership_channel.send(embed=leadership_embed)
            
        except Exception as e:
            logger.error(f"Error adding prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while adding the prospect: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(name="prospect-patch", description="Patch a prospect (promote to full member)")
    @app_commands.describe(prospect="The prospect to patch")
    async def prospect_patch(self, interaction: discord.Interaction, prospect: discord.Member):
        """Patch a prospect to full member"""
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
            
            # Update prospect status
            await self.bot.db.update_prospect_status(prospect_record['id'], 'patched')
            
            # Update member rank
            await self.bot.db.add_or_update_member(
                interaction.guild.id,
                prospect.id,
                prospect.display_name,
                rank='Full Patch',
                discord_username=prospect.name
            )
            
            # Remove prospect role and add full patch role if it exists
            roles_changes = []
            if prospect_record.get('prospect_role_id'):
                prospect_role = interaction.guild.get_role(prospect_record['prospect_role_id'])
                if prospect_role and prospect_role in prospect.roles:
                    await prospect.remove_roles(prospect_role, reason="Patched to full member")
                    roles_changes.append(f"Removed {prospect_role.name}")
            
            # Add Full Patch role if it exists
            full_patch_role = discord.utils.get(interaction.guild.roles, name="Full Patch")
            if full_patch_role and full_patch_role not in prospect.roles:
                await prospect.add_roles(full_patch_role, reason="Patched to full member")
                roles_changes.append(f"Added {full_patch_role.mention}")
            
            # Clean up sponsored by role
            if prospect_record.get('prospect_role_id'):
                await self.cleanup_prospect_roles(interaction.guild, prospect_record['prospect_role_id'])
            
            # Create success embed
            embed = discord.Embed(
                title="🎉 Prospect Patched Successfully",
                description=f"{prospect.mention} has been promoted to **Full Patch**!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Sponsor", value=f"<@{prospect_record['sponsor_id']}>", inline=True)
            embed.add_field(name="Trial Period", value=f"Started: <t:{int(datetime.fromisoformat(prospect_record['start_date']).timestamp())}:R>", inline=True)
            
            if roles_changes:
                embed.add_field(name="Role Changes", value="\n".join(roles_changes), inline=False)
            
            embed.set_footer(text=f"Patched by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
            # Send congratulatory DM to the newly patched member
            try:
                dm_embed = discord.Embed(
                    title="🎉 Congratulations!",
                    description=f"You have been **patched** in **{interaction.guild.name}**!\n\nWelcome to the full membership!",
                    color=discord.Color.gold()
                )
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send patch congratulations DM to {prospect.id}")
            
            # Log to leadership channel
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    leadership_embed = embed.copy()
                    leadership_embed.add_field(name="Patched by", value=interaction.user.mention, inline=True)
                    await leadership_channel.send(embed=leadership_embed)
            
        except Exception as e:
            logger.error(f"Error patching prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while patching the prospect: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(name="prospect-drop", description="Drop a prospect from the club")
    @app_commands.describe(
        prospect="The prospect to drop",
        reason="Reason for dropping the prospect"
    )
    async def prospect_drop(self, interaction: discord.Interaction, prospect: discord.Member, reason: str):
        """Drop a prospect from the club"""
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
            
            # Update prospect status
            await self.bot.db.update_prospect_status(prospect_record['id'], 'dropped')
            
            # Add drop note
            await self.bot.db.add_prospect_note(
                interaction.guild.id,
                prospect_record['id'],
                interaction.user.id,
                f"**DROPPED:** {reason}",
                is_strike=False
            )
            
            # Remove roles
            roles_removed = []
            if prospect_record.get('prospect_role_id'):
                prospect_role = interaction.guild.get_role(prospect_record['prospect_role_id'])
                if prospect_role and prospect_role in prospect.roles:
                    await prospect.remove_roles(prospect_role, reason=f"Dropped: {reason}")
                    roles_removed.append(prospect_role.name)
            
            # Remove sponsor from Sponsors role if they have no other active prospects
            sponsor_id = prospect_record['sponsor_id']
            active_sponsored_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
            other_sponsored = [p for p in active_sponsored_prospects if p['sponsor_id'] == sponsor_id and p['id'] != prospect_record['id']]
            
            if not other_sponsored and prospect_record.get('sponsor_role_id'):
                sponsors_role = interaction.guild.get_role(prospect_record['sponsor_role_id'])
                sponsor_member = interaction.guild.get_member(sponsor_id)
                if sponsors_role and sponsor_member and sponsors_role in sponsor_member.roles:
                    await sponsor_member.remove_roles(sponsors_role, reason="No longer sponsoring any active prospects")
                    roles_removed.append(f"Sponsors (from <@{sponsor_id}>)")
            
            # Clean up sponsored by role
            if prospect_record.get('prospect_role_id'):
                await self.cleanup_prospect_roles(interaction.guild, prospect_record['prospect_role_id'])
            
            # Create embed
            embed = discord.Embed(
                title="❌ Prospect Dropped",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=f"<@{prospect_record['sponsor_id']}>", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Trial Period", value=f"Started: <t:{int(datetime.fromisoformat(prospect_record['start_date']).timestamp())}:R>", inline=True)
            
            if roles_removed:
                embed.add_field(name="Roles Removed", value="\n".join(roles_removed), inline=False)
            
            embed.set_footer(text=f"Dropped by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
            # Send notification DM to the dropped prospect
            try:
                dm_embed = discord.Embed(
                    title="📢 Prospect Status Update",
                    description=f"You have been **dropped** from prospect status in **{interaction.guild.name}**.",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Note", value="You are welcome to reapply in the future if circumstances change.", inline=False)
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send drop notification DM to {prospect.id}")
            
            # Log to leadership channel
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    leadership_embed = embed.copy()
                    leadership_embed.add_field(name="Dropped by", value=interaction.user.mention, inline=True)
                    await leadership_channel.send(embed=leadership_embed)
            
        except Exception as e:
            logger.error(f"Error dropping prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while dropping the prospect: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(name="prospect-view", description="View prospect information and status")
    @app_commands.describe(prospect="The prospect to view information for")
    async def prospect_view(self, interaction: discord.Interaction, prospect: discord.Member):
        """View detailed prospect information"""
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
            
            # Get tasks, notes, and votes
            tasks = await self.bot.db.get_prospect_tasks(prospect_record['id'])
            notes = await self.bot.db.get_prospect_notes(prospect_record['id'])
            votes = await self.bot.db.get_prospect_vote_history(prospect_record['id'])
            
            # Create embed
            status_colors = {
                'active': discord.Color.green(),
                'patched': discord.Color.gold(),
                'dropped': discord.Color.red(),
                'archived': discord.Color.grey()
            }
            
            embed = discord.Embed(
                title=f"📋 Prospect Profile: {prospect.display_name}",
                color=status_colors.get(prospect_record['status'], discord.Color.blue()),
                timestamp=datetime.now()
            )
            
            # Basic info
            embed.add_field(name="Status", value=prospect_record['status'].title(), inline=True)
            embed.add_field(name="Sponsor", value=f"<@{prospect_record['sponsor_id']}>", inline=True)
            embed.add_field(name="Strikes", value=str(prospect_record['strikes']), inline=True)
            
            # Dates
            start_date = datetime.fromisoformat(prospect_record['start_date'])
            embed.add_field(name="Start Date", value=f"<t:{int(start_date.timestamp())}:F>", inline=True)
            
            if prospect_record['end_date']:
                end_date = datetime.fromisoformat(prospect_record['end_date'])
                embed.add_field(name="End Date", value=f"<t:{int(end_date.timestamp())}:F>", inline=True)
                
                # Calculate duration
                duration = end_date - start_date
                embed.add_field(name="Duration", value=f"{duration.days} days", inline=True)
            else:
                # Calculate current duration
                duration = datetime.now() - start_date
                embed.add_field(name="Current Duration", value=f"{duration.days} days", inline=True)
            
            # Tasks summary
            if tasks:
                completed = len([t for t in tasks if t['status'] == 'completed'])
                failed = len([t for t in tasks if t['status'] == 'failed'])
                assigned = len([t for t in tasks if t['status'] == 'assigned'])
                overdue = len([t for t in tasks if t['status'] == 'assigned' and t['due_date'] and datetime.fromisoformat(t['due_date']) < datetime.now()])
                
                task_summary = f"**Total:** {len(tasks)}\n"
                task_summary += f"✅ Completed: {completed}\n"
                task_summary += f"❌ Failed: {failed}\n"
                task_summary += f"⏳ Pending: {assigned}\n"
                if overdue > 0:
                    task_summary += f"🚨 Overdue: {overdue}"
                
                embed.add_field(name="Tasks", value=task_summary, inline=True)
            else:
                embed.add_field(name="Tasks", value="No tasks assigned", inline=True)
            
            # Notes summary
            if notes:
                strikes = len([n for n in notes if n['is_strike']])
                regular_notes = len(notes) - strikes
                notes_summary = f"**Total:** {len(notes)}\n"
                notes_summary += f"📝 Notes: {regular_notes}\n"
                notes_summary += f"⚠️ Strikes: {strikes}"
                embed.add_field(name="Notes & Strikes", value=notes_summary, inline=True)
            else:
                embed.add_field(name="Notes & Strikes", value="No notes recorded", inline=True)
            
            # Recent activity
            recent_activity = []
            
            # Add recent tasks (last 3)
            recent_tasks = sorted(tasks, key=lambda x: x['updated_at'], reverse=True)[:3]
            for task in recent_tasks:
                status_emoji = {'completed': '✅', 'failed': '❌', 'assigned': '⏳'}.get(task['status'], '⏳')
                recent_activity.append(f"{status_emoji} {task['task_name']}")
            
            # Add recent notes (last 3)
            recent_notes = sorted(notes, key=lambda x: x['created_at'], reverse=True)[:3]
            for note in recent_notes:
                note_emoji = '⚠️' if note['is_strike'] else '📝'
                truncated_note = note['note_text'][:30] + '...' if len(note['note_text']) > 30 else note['note_text']
                recent_activity.append(f"{note_emoji} {truncated_note}")
            
            if recent_activity:
                embed.add_field(name="Recent Activity", value="\n".join(recent_activity[:5]), inline=False)
            
            # Voting history
            if votes:
                active_vote = [v for v in votes if v['status'] == 'active']
                if active_vote:
                    embed.add_field(name="Active Vote", value=f"🗳️ {active_vote[0]['vote_type'].title()} vote in progress", inline=True)
                
                completed_votes = [v for v in votes if v['status'] == 'completed']
                if completed_votes:
                    last_vote = completed_votes[0]  # Most recent
                    result_emoji = '✅' if last_vote['result'] == 'passed' else '❌'
                    embed.add_field(name="Last Vote", value=f"{result_emoji} {last_vote['vote_type'].title()}: {last_vote['result']}", inline=True)
            
            embed.set_thumbnail(url=prospect.display_avatar.url)
            embed.set_footer(text=f"Prospect ID: {prospect_record['id']}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error viewing prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while retrieving prospect information: {str(e)}", 
                ephemeral=True
            )

    @app_commands.command(name="prospect-list", description="List all active or archived prospects")
    @app_commands.describe(
        status="Which prospects to show (active, archived, or all)",
        show_details="Show detailed information for each prospect"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Active", value="active"),
        app_commands.Choice(name="Archived", value="archived"),
        app_commands.Choice(name="All", value="all")
    ])
    async def prospect_list(self, interaction: discord.Interaction, status: str = "active", show_details: bool = False):
        """List prospects with optional filtering"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
            
            if status == "active":
                prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
                title = "🔍 Active Prospects"
                color = discord.Color.green()
            elif status == "archived":
                prospects = await self.bot.db.get_archived_prospects(interaction.guild.id)
                title = "📁 Archived Prospects"
                color = discord.Color.grey()
            else:  # all
                active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
                archived_prospects = await self.bot.db.get_archived_prospects(interaction.guild.id)
                prospects = active_prospects + archived_prospects
                title = "📋 All Prospects"
                color = discord.Color.blue()
            
            if not prospects:
                embed = discord.Embed(
                    title=title,
                    description="No prospects found.",
                    color=color
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Create embed
            embed = discord.Embed(title=title, color=color, timestamp=datetime.now())
            embed.set_footer(text=f"Total: {len(prospects)} prospects")
            
            if show_details:
                # Detailed view - limit to 10 prospects to avoid embed limits
                for i, prospect in enumerate(prospects[:10]):
                    prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                    sponsor_name = prospect.get('sponsor_name', f"User {prospect['sponsor_id']}")
                    
                    start_date = datetime.fromisoformat(prospect['start_date'])
                    duration = (datetime.now() - start_date).days if prospect['status'] == 'active' else (datetime.fromisoformat(prospect['end_date']) - start_date).days
                    
                    status_emoji = {
                        'active': '🟢',
                        'patched': '🟡',
                        'dropped': '🔴',
                        'archived': '⚫'
                    }.get(prospect['status'], '🔵')
                    
                    field_value = f"{status_emoji} **{prospect['status'].title()}**\n"
                    field_value += f"📅 {duration} days\n"
                    field_value += f"👤 Sponsor: {sponsor_name}\n"
                    
                    if prospect.get('total_tasks', 0) > 0:
                        field_value += f"✅ Tasks: {prospect.get('completed_tasks', 0)}/{prospect.get('total_tasks', 0)}\n"
                    
                    if prospect.get('strike_count', 0) > 0:
                        field_value += f"⚠️ Strikes: {prospect['strike_count']}\n"
                    
                    embed.add_field(
                        name=f"{i+1}. {prospect_name}",
                        value=field_value,
                        inline=True
                    )
                
                if len(prospects) > 10:
                    embed.add_field(
                        name="Note",
                        value=f"Showing first 10 of {len(prospects)} prospects. Use `/prospect-view` for individual details.",
                        inline=False
                    )
            else:
                # Simple list view
                prospect_list = []
                for i, prospect in enumerate(prospects):
                    prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                    sponsor_name = prospect.get('sponsor_name', f"User {prospect['sponsor_id']}")
                    
                    start_date = datetime.fromisoformat(prospect['start_date'])
                    duration = (datetime.now() - start_date).days if prospect['status'] == 'active' else (datetime.fromisoformat(prospect['end_date']) - start_date).days
                    
                    status_emoji = {
                        'active': '🟢',
                        'patched': '🟡',
                        'dropped': '🔴',
                        'archived': '⚫'
                    }.get(prospect['status'], '🔵')
                    
                    line = f"{i+1}. {status_emoji} **{prospect_name}** (by {sponsor_name}) - {duration} days"
                    
                    if prospect.get('strike_count', 0) > 0:
                        line += f" ⚠️{prospect['strike_count']}"
                    
                    prospect_list.append(line)
                
                # Split into chunks to avoid embed field limits
                chunk_size = 20
                for i in range(0, len(prospect_list), chunk_size):
                    chunk = prospect_list[i:i + chunk_size]
                    field_name = f"Prospects {i+1}-{min(i+chunk_size, len(prospect_list))}" if len(prospect_list) > chunk_size else "Prospects"
                    embed.add_field(
                        name=field_name,
                        value="\n".join(chunk),
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error listing prospects: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while retrieving prospects: {str(e)}", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProspectManagement(bot))

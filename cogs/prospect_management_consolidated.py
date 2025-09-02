import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional, Dict, List
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectManagementConsolidated(commands.Cog):
    """Consolidated prospect management commands with subcommands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectManagementConsolidated cog initialized")

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

    @app_commands.command(name="prospect", description="Prospect management commands")
    @app_commands.describe(
        action="The action to perform",
        prospect="The prospect user (required for most actions)",
        sponsor="The sponsor user (required for add action)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add new prospect", value="add"),
        app_commands.Choice(name="Patch prospect (promote)", value="patch"),
        app_commands.Choice(name="Drop prospect", value="drop"),
        app_commands.Choice(name="View prospect details", value="view"),
        app_commands.Choice(name="List all prospects", value="list")
    ])
    async def prospect(
        self, 
        interaction: discord.Interaction, 
        action: str, 
        prospect: Optional[discord.Member] = None,
        sponsor: Optional[discord.Member] = None
    ):
        """Main prospect management command with subcommands"""
        # Permission check
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        if action == "add":
            await self._prospect_add(interaction, prospect, sponsor)
        elif action == "patch":
            await self._prospect_patch(interaction, prospect)
        elif action == "drop":
            await self._prospect_drop(interaction, prospect)
        elif action == "view":
            await self._prospect_view(interaction, prospect)
        elif action == "list":
            await self._prospect_list(interaction)

    async def _prospect_add(self, interaction: discord.Interaction, prospect: discord.Member, sponsor: discord.Member):
        """Add a new prospect"""
        if not prospect:
            await interaction.response.send_message("❌ Please specify a prospect to add.", ephemeral=True)
            return
        if not sponsor:
            await interaction.response.send_message("❌ Please specify a sponsor for the prospect.", ephemeral=True)
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

    async def _prospect_patch(self, interaction: discord.Interaction, prospect: discord.Member):
        """Patch a prospect (promote to full member)"""
        if not prospect:
            await interaction.response.send_message("❌ Please specify a prospect to patch.", ephemeral=True)
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
            
            # Assign promotion roles
            roles_assigned = []
            promotion_role_ids = [1250216224722391110, 894033083869843457]  # Specified role IDs
            
            for role_id in promotion_role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    try:
                        await prospect.add_roles(role, reason=f"Patched from prospect to full member")
                        roles_assigned.append(role.name)
                        logger.info(f"Assigned role '{role.name}' to {prospect.display_name} upon patching")
                    except Exception as e:
                        logger.error(f"Failed to assign role {role.name} to {prospect.display_name}: {e}")
                else:
                    logger.warning(f"Role with ID {role_id} not found in guild {interaction.guild.id}")
            
            # Get sponsor for notifications
            sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
            
            # Remove prospect role and cleanup
            if prospect_record.get('prospect_role_id'):
                await self.cleanup_prospect_roles(interaction.guild, prospect_record['prospect_role_id'])
            
            # Create success embed
            embed = discord.Embed(
                title="🎉 Prospect Patched Successfully",
                description=f"{prospect.mention} has been promoted to **Full Patch Member**!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            embed.add_field(name="New Member", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=sponsor.mention if sponsor else "Unknown", inline=True)
            embed.add_field(name="Patched by", value=interaction.user.mention, inline=True)
            
            if roles_assigned:
                embed.add_field(
                    name="🎖️ Roles Assigned",
                    value="\n".join([f"• {role}" for role in roles_assigned]),
                    inline=False
                )
            
            embed.set_thumbnail(url=prospect.display_avatar.url)
            
            await interaction.followup.send(embed=embed)
            
            # Send notifications
            config = await self.bot.db.get_server_config(interaction.guild.id)
            
            # Notify prospect
            try:
                dm_embed = discord.Embed(
                    title="🎉 Congratulations!",
                    description=f"You have been **patched** in **{interaction.guild.name}**!\n\nWelcome to the club as a full member!",
                    color=discord.Color.gold()
                )
                await prospect.send(embed=dm_embed)
            except:
                pass
            
            # Send to leadership/notification channels
            if hasattr(self.bot, 'get_cog') and self.bot.get_cog('ProspectNotificationsConsolidated'):
                notifications_cog = self.bot.get_cog('ProspectNotificationsConsolidated')
                if notifications_cog:
                    await notifications_cog.send_prospect_patch_notification(
                        interaction.guild, prospect, sponsor, config
                    )
            
        except Exception as e:
            logger.error(f"Error patching prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while patching the prospect: {str(e)}", 
                ephemeral=True
            )

    async def _prospect_drop(self, interaction: discord.Interaction, prospect: discord.Member):
        """Drop a prospect"""
        if not prospect:
            await interaction.response.send_message("❌ Please specify a prospect to drop.", ephemeral=True)
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
            
            # Get sponsor for notifications
            sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
            
            # Remove prospect role and cleanup
            if prospect_record.get('prospect_role_id'):
                await self.cleanup_prospect_roles(interaction.guild, prospect_record['prospect_role_id'])
            
            # Create embed
            embed = discord.Embed(
                title="📢 Prospect Dropped",
                description=f"{prospect.mention} has been removed from prospect status.",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Dropped Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=sponsor.mention if sponsor else "Unknown", inline=True)
            embed.add_field(name="Dropped by", value=interaction.user.mention, inline=True)
            
            await interaction.followup.send(embed=embed)
            
            # Send notifications
            config = await self.bot.db.get_server_config(interaction.guild.id)
            
            # Notify prospect
            try:
                dm_embed = discord.Embed(
                    title="📢 Prospect Status Update",
                    description=f"Your prospect status in **{interaction.guild.name}** has been ended.\n\nThank you for your interest in the club.",
                    color=discord.Color.red()
                )
                await prospect.send(embed=dm_embed)
            except:
                pass
            
            # Send to leadership channels  
            if hasattr(self.bot, 'get_cog') and self.bot.get_cog('ProspectNotificationsConsolidated'):
                notifications_cog = self.bot.get_cog('ProspectNotificationsConsolidated')
                if notifications_cog:
                    await notifications_cog.send_prospect_drop_notification(
                        interaction.guild, prospect, sponsor, "Manual drop by leadership", config
                    )
            
        except Exception as e:
            logger.error(f"Error dropping prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while dropping the prospect: {str(e)}", 
                ephemeral=True
            )

    async def _prospect_view(self, interaction: discord.Interaction, prospect: discord.Member):
        """View prospect details"""
        if not prospect:
            await interaction.response.send_message("❌ Please specify a prospect to view.", ephemeral=True)
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
            
            # Get sponsor details
            sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
            sponsor_name = sponsor.display_name if sponsor else f"User {prospect_record['sponsor_id']}"
            
            # Calculate duration
            start_date = datetime.fromisoformat(prospect_record['start_date'])
            if prospect_record.get('end_date'):
                end_date = datetime.fromisoformat(prospect_record['end_date'])
                duration = (end_date - start_date).days
            else:
                duration = (datetime.now() - start_date).days
            
            # Status colors
            status_colors = {
                'active': discord.Color.green(),
                'patched': discord.Color.gold(),
                'dropped': discord.Color.red()
            }
            
            embed = discord.Embed(
                title=f"👤 Prospect Profile: {prospect.display_name}",
                color=status_colors.get(prospect_record['status'], discord.Color.blue()),
                timestamp=datetime.now()
            )
            
            # Basic info
            embed.add_field(name="Status", value=prospect_record['status'].title(), inline=True)
            embed.add_field(name="Sponsor", value=sponsor_name, inline=True)
            embed.add_field(name="Duration", value=f"{duration} days", inline=True)
            
            embed.add_field(name="Start Date", value=f"<t:{int(start_date.timestamp())}:F>", inline=True)
            embed.add_field(name="Strikes", value=str(prospect_record.get('strikes', 0)), inline=True)
            
            if prospect_record.get('end_date'):
                end_date = datetime.fromisoformat(prospect_record['end_date'])
                embed.add_field(name="End Date", value=f"<t:{int(end_date.timestamp())}:F>", inline=True)
            else:
                embed.add_field(name="End Date", value="N/A (Active)", inline=True)
            
            # Get additional stats
            try:
                tasks = await self.bot.db.get_prospect_tasks(prospect_record['id'])
                notes = await self.bot.db.get_prospect_notes(prospect_record['id'])
                
                # Task summary
                if tasks:
                    completed = len([t for t in tasks if t['status'] == 'completed'])
                    failed = len([t for t in tasks if t['status'] == 'failed'])
                    pending = len([t for t in tasks if t['status'] == 'assigned'])
                    
                    task_summary = f"**Total:** {len(tasks)}\n"
                    task_summary += f"✅ Completed: {completed}\n"
                    task_summary += f"❌ Failed: {failed}\n"
                    task_summary += f"⏳ Pending: {pending}"
                else:
                    task_summary = "No tasks assigned"
                
                embed.add_field(name="📋 Tasks", value=task_summary, inline=True)
                
                # Notes summary
                if notes:
                    strikes = len([n for n in notes if n.get('is_strike', False)])
                    regular_notes = len(notes) - strikes
                    
                    notes_summary = f"**Total:** {len(notes)}\n"
                    notes_summary += f"📝 Notes: {regular_notes}\n"
                    notes_summary += f"⚠️ Strikes: {strikes}"
                else:
                    notes_summary = "No notes recorded"
                
                embed.add_field(name="📝 Notes & Strikes", value=notes_summary, inline=True)
                
            except Exception as e:
                logger.error(f"Error getting prospect stats: {e}")
            
            embed.set_thumbnail(url=prospect.display_avatar.url)
            embed.set_footer(text=f"Prospect ID: {prospect_record['id']}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error viewing prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while viewing the prospect: {str(e)}", 
                ephemeral=True
            )

    async def _prospect_list(self, interaction: discord.Interaction):
        """List all prospects"""
        try:
            await interaction.response.defer()
            
            # Get all prospects
            active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
            archived_prospects = await self.bot.db.get_archived_prospects(interaction.guild.id)
            
            embed = discord.Embed(
                title="📋 Prospect Management Overview",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Stats
            embed.add_field(
                name="📊 Quick Stats",
                value=f"🟢 **Active:** {len(active_prospects)}\n📁 **Archived:** {len(archived_prospects)}\n📈 **Total:** {len(active_prospects) + len(archived_prospects)}",
                inline=True
            )
            
            # Active prospects
            if active_prospects:
                active_list = []
                for i, prospect in enumerate(active_prospects[:10]):  # Limit to 10
                    prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                    sponsor_name = prospect.get('sponsor_name', 'Unknown')
                    
                    start_date = datetime.fromisoformat(prospect['start_date'])
                    duration = (datetime.now() - start_date).days
                    
                    strikes = prospect.get('strikes', 0)
                    strike_text = f" ⚠️{strikes}" if strikes > 0 else ""
                    
                    active_list.append(f"`{i+1}.` **{prospect_name}**{strike_text}\n   └ Sponsor: {sponsor_name} • {duration} days")
                
                if len(active_prospects) > 10:
                    active_list.append(f"\n*...and {len(active_prospects) - 10} more active prospects*")
                
                embed.add_field(
                    name="🟢 Active Prospects",
                    value="\n".join(active_list) if active_list else "No active prospects",
                    inline=False
                )
            else:
                embed.add_field(name="🟢 Active Prospects", value="No active prospects found", inline=False)
            
            # Recent activity
            recent_activity = "• Use `/prospect-dashboard` for detailed views\n"
            recent_activity += "• Use `/prospect add` to add new prospects\n"
            recent_activity += "• Use `/prospect-task` to manage tasks\n"
            recent_activity += "• Use `/prospect-note` for notes and strikes"
            
            embed.add_field(name="🔗 Quick Actions", value=recent_activity, inline=False)
            embed.set_footer(text="Use /prospect-dashboard for interactive management")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing prospects: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while listing prospects: {str(e)}", 
                ephemeral=True
            )
    
    @app_commands.command(name="prospect-dashboard", description="Open the prospect management dashboard")
    async def prospect_dashboard(self, interaction: discord.Interaction):
        """Open the interactive prospect management dashboard"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            # Import the view classes from prospect_dashboard
            from cogs.prospect_dashboard import ProspectDashboardView
            
            view = ProspectDashboardView(self.bot, interaction.user.id)
            embed = await view.create_main_embed()
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error opening prospect dashboard: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred while opening the dashboard: {str(e)}",
                ephemeral=True
            )

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
                
                # Show recent completed tasks
                if completed_tasks:
                    completed_list = []
                    for task in completed_tasks[-3:]:  # Show last 3 completed
                        completed_date = datetime.fromisoformat(task['updated_at']) if task.get('updated_at') else datetime.now()
                        completed_list.append(
                            f"`{task['id']}` {task['task_name']}\n"
                            f"   └ Completed <t:{int(completed_date.timestamp())}:R>"
                        )
                    
                    if len(completed_tasks) > 3:
                        completed_list.append(f"\n*...and {len(completed_tasks) - 3} more completed*")
                    
                    embed.add_field(
                        name="✅ Recent Completions",
                        value="\n".join(completed_list),
                        inline=False
                    )
                
                # Show failed tasks if any
                if failed_tasks:
                    failed_list = []
                    for task in failed_tasks[-3:]:  # Show last 3 failed
                        failed_date = datetime.fromisoformat(task['updated_at']) if task.get('updated_at') else datetime.now()
                        failed_list.append(
                            f"`{task['id']}` {task['task_name']}\n"
                            f"   └ Failed <t:{int(failed_date.timestamp())}:R>"
                        )
                    
                    if len(failed_tasks) > 3:
                        failed_list.append(f"\n*...and {len(failed_tasks) - 3} more failed*")
                    
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


async def setup(bot):
    await bot.add_cog(ProspectManagementConsolidated(bot))

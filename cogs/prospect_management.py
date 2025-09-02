import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectManagement(commands.Cog):
    """Core prospect lifecycle management commands with role cleanup"""

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

    async def cleanup_prospect_roles(self, guild: discord.Guild, prospect_role_id: int, sponsor_role_id: int):
        """Clean up prospect and sponsor roles when no longer needed"""
        try:
            # Clean up "Sponsored by X" role
            if prospect_role_id:
                prospect_role = guild.get_role(prospect_role_id)
                if prospect_role and len(prospect_role.members) == 0:
                    await prospect_role.delete(reason="No longer needed - prospect completed/dropped")
                    logger.info(f"Cleaned up prospect role '{prospect_role.name}' in guild {guild.id}")
            
            # Note: Don't delete the general "Sponsors" role as it might be used by other sponsors
            # Only remove it from the specific sponsor if they're not sponsoring anyone else
            if sponsor_role_id:
                sponsor_role = guild.get_role(sponsor_role_id)
                if sponsor_role and sponsor_role.name == "Sponsors":
                    # Check if the sponsor has other prospects
                    # This would require checking the database for other active prospects by this sponsor
                    # For now, we'll leave the Sponsors role as it's generic
                    pass
                    
        except Exception as e:
            logger.error(f"Failed to cleanup prospect roles: {e}")

    @app_commands.command(name="prospect-add", description="Add a new prospect with automatic role creation")
    @app_commands.describe(
        prospect="The Discord member to add as a prospect",
        sponsor="The Discord member who will sponsor this prospect"
    )
    async def prospect_add(self, interaction: discord.Interaction, prospect: discord.Member, sponsor: discord.Member):
        """Add a new prospect with automatic role assignment"""
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']):
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
            
            # Check if prospect is already a full member (basic check)
            if any(role.name in ['Full Patch', 'President', 'Vice President', 'Sergeant At Arms', 
                               'Secretary', 'Treasurer', 'Road Captain', 'Tailgunner', 'Enforcer'] 
                   for role in prospect.roles):
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
            
            # Send DM to prospect
            try:
                dm_embed = discord.Embed(
                    title="🎉 Welcome to the Prospect Program!",
                    description=f"You have been added as a prospect in **{interaction.guild.name}**",
                    color=discord.Color.green()
                )
                dm_embed.add_field(name="Your Sponsor", value=sponsor.display_name, inline=True)
                dm_embed.add_field(name="Added by", value=interaction.user.display_name, inline=True)
                dm_embed.add_field(
                    name="What's Next?",
                    value="Your sponsor will guide you through the prospect process. "
                          "You may receive tasks to complete and will be evaluated by the membership.",
                    inline=False
                )
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send prospect welcome DM to {prospect.id}")
            
            # Send DM to sponsor
            try:
                sponsor_embed = discord.Embed(
                    title="👤 New Prospect Assignment",
                    description=f"You are now sponsoring **{prospect.display_name}**",
                    color=discord.Color.blue()
                )
                sponsor_embed.add_field(name="Prospect", value=prospect.mention, inline=True)
                sponsor_embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
                sponsor_embed.add_field(
                    name="Your Responsibilities",
                    value="• Guide them through the prospect process\n"
                          "• Assign and monitor tasks\n"
                          "• Provide mentorship and support\n"
                          "• Report on their progress",
                    inline=False
                )
                await sponsor.send(embed=sponsor_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send sponsor notification to {sponsor.id}")
            
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

    @app_commands.command(name="prospect-patch", description="Promote a prospect to full member (patches them in)")
    @app_commands.describe(
        prospect="The prospect to promote to full member",
        notes="Optional notes about the promotion"
    )
    async def prospect_patch(self, interaction: discord.Interaction, prospect: discord.Member, notes: Optional[str] = None):
        """Promote a prospect to full member with automatic role cleanup"""
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']):
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
            
            # Get sponsor
            sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
            
            # Update prospect status in database
            await self.bot.db.update_prospect_status(prospect_record['id'], 'patched')
            
            # Remove prospect-specific roles and add full member role
            roles_to_remove = []
            
            # Remove "Sponsored by X" role
            if prospect_record.get('prospect_role_id'):
                prospect_role = interaction.guild.get_role(prospect_record['prospect_role_id'])
                if prospect_role and prospect_role in prospect.roles:
                    await prospect.remove_roles(prospect_role, reason="Prospect patched to full member")
                    roles_to_remove.append(prospect_role.name)
            
            # Add Full Patch role if it exists
            full_patch_role = discord.utils.get(interaction.guild.roles, name="Full Patch")
            if full_patch_role:
                await prospect.add_roles(full_patch_role, reason="Promoted from prospect to full member")
            
            # Clean up roles (delete "Sponsored by X" if no one else has it)
            await self.cleanup_prospect_roles(
                interaction.guild, 
                prospect_record.get('prospect_role_id'),
                prospect_record.get('sponsor_role_id')
            )
            
            # Create success embed
            embed = discord.Embed(
                title="🎉 Prospect Patched Successfully!",
                description=f"**{prospect.display_name}** has been promoted to Full Member!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            embed.add_field(name="New Member", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=sponsor.mention if sponsor else "Unknown", inline=True)
            embed.add_field(name="Promoted by", value=interaction.user.mention, inline=True)
            
            # Calculate prospect duration
            start_date = datetime.fromisoformat(prospect_record['start_date'])
            duration = (datetime.now() - start_date).days
            embed.add_field(name="Prospect Duration", value=f"{duration} days", inline=True)
            embed.add_field(name="Total Strikes", value=str(prospect_record.get('strikes', 0)), inline=True)
            
            if notes:
                embed.add_field(name="Notes", value=notes, inline=False)
            
            if roles_to_remove:
                embed.add_field(name="Roles Removed", value="\n".join(f"• {role}" for role in roles_to_remove), inline=False)
            
            if full_patch_role:
                embed.add_field(name="New Role", value=full_patch_role.mention, inline=False)
            
            embed.set_thumbnail(url=prospect.display_avatar.url)
            embed.set_footer(text=f"Prospect ID: {prospect_record['id']}")
            
            await interaction.followup.send(embed=embed)
            
            # Send congratulatory DM to new member
            try:
                dm_embed = discord.Embed(
                    title="🎉 Congratulations!",
                    description=f"You have been patched in as a Full Member of **{interaction.guild.name}**!",
                    color=discord.Color.gold()
                )
                dm_embed.add_field(name="Promoted by", value=interaction.user.display_name, inline=True)
                dm_embed.add_field(name="Sponsor", value=sponsor.display_name if sponsor else "Unknown", inline=True)
                dm_embed.add_field(name="Prospect Duration", value=f"{duration} days", inline=True)
                
                if notes:
                    dm_embed.add_field(name="Promotion Notes", value=notes, inline=False)
                
                dm_embed.add_field(
                    name="Welcome to the Brotherhood!",
                    value="You are now a full member with all the rights and responsibilities that come with it. "
                          "Congratulations on completing your prospect period!",
                    inline=False
                )
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send patch congratulations DM to {prospect.id}")
            
            # Thank the sponsor
            if sponsor:
                try:
                    sponsor_embed = discord.Embed(
                        title="🎉 Your Prospect Has Been Patched!",
                        description=f"**{prospect.display_name}** has successfully completed their prospect period!",
                        color=discord.Color.gold()
                    )
                    sponsor_embed.add_field(name="New Member", value=prospect.mention, inline=True)
                    sponsor_embed.add_field(name="Promoted by", value=interaction.user.mention, inline=True)
                    sponsor_embed.add_field(name="Duration", value=f"{duration} days", inline=True)
                    sponsor_embed.add_field(
                        name="Thank You!",
                        value="Thank you for your guidance and mentorship throughout their prospect period. "
                              "Your support helped them succeed!",
                        inline=False
                    )
                    await sponsor.send(embed=sponsor_embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send sponsor thank you to {sponsor.id}")
            
            # Send notification through prospect notifications system
            try:
                from cogs.prospect_notifications import ProspectNotifications
                prospect_notifications = self.bot.get_cog('ProspectNotifications')
                if prospect_notifications:
                    await prospect_notifications.send_prospect_patch_notification(
                        interaction.guild, prospect, sponsor, 
                        await self.bot.db.get_server_config(interaction.guild.id) or {}
                    )
            except Exception as e:
                logger.warning(f"Error sending patch notifications: {e}")
            
        except Exception as e:
            logger.error(f"Error patching prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while patching the prospect: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="prospect-drop", description="Remove a prospect from the program")
    @app_commands.describe(
        prospect="The prospect to remove from the program",
        reason="Reason for removing the prospect"
    )
    async def prospect_drop(self, interaction: discord.Interaction, prospect: discord.Member, reason: str):
        """Remove a prospect from the program with automatic role cleanup"""
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']):
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
            
            # Get sponsor
            sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
            
            # Update prospect status in database
            await self.bot.db.update_prospect_status(prospect_record['id'], 'dropped')
            
            # Remove prospect-specific roles
            roles_removed = []
            
            # Remove "Sponsored by X" role
            if prospect_record.get('prospect_role_id'):
                prospect_role = interaction.guild.get_role(prospect_record['prospect_role_id'])
                if prospect_role and prospect_role in prospect.roles:
                    await prospect.remove_roles(prospect_role, reason=f"Prospect dropped: {reason}")
                    roles_removed.append(prospect_role.name)
            
            # Clean up roles (delete "Sponsored by X" if no one else has it)
            await self.cleanup_prospect_roles(
                interaction.guild, 
                prospect_record.get('prospect_role_id'),
                prospect_record.get('sponsor_role_id')
            )
            
            # Calculate prospect duration
            start_date = datetime.fromisoformat(prospect_record['start_date'])
            duration = (datetime.now() - start_date).days
            
            # Create response embed
            embed = discord.Embed(
                title="📢 Prospect Dropped",
                description=f"**{prospect.display_name}** has been removed from the prospect program",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Former Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=sponsor.mention if sponsor else "Unknown", inline=True)
            embed.add_field(name="Dropped by", value=interaction.user.mention, inline=True)
            
            embed.add_field(name="Prospect Duration", value=f"{duration} days", inline=True)
            embed.add_field(name="Total Strikes", value=str(prospect_record.get('strikes', 0)), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            if roles_removed:
                embed.add_field(name="Roles Removed", value="\n".join(f"• {role}" for role in roles_removed), inline=False)
            
            embed.set_footer(text=f"Prospect ID: {prospect_record['id']}")
            
            await interaction.followup.send(embed=embed)
            
            # Send notification to dropped prospect
            try:
                dm_embed = discord.Embed(
                    title="📢 Prospect Status Update",
                    description=f"Your prospect status in **{interaction.guild.name}** has been concluded",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Duration", value=f"{duration} days", inline=True)
                dm_embed.add_field(name="Sponsor", value=sponsor.display_name if sponsor else "Unknown", inline=True)
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(
                    name="Thank You",
                    value="Thank you for your interest in our organization. "
                          "We wish you the best in your future endeavors.",
                    inline=False
                )
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send drop notification DM to {prospect.id}")
            
            # Notify sponsor
            if sponsor:
                try:
                    sponsor_embed = discord.Embed(
                        title="📢 Your Prospect Has Been Dropped",
                        description=f"**{prospect.display_name}** has been removed from the prospect program",
                        color=discord.Color.red()
                    )
                    sponsor_embed.add_field(name="Former Prospect", value=prospect.mention, inline=True)
                    sponsor_embed.add_field(name="Dropped by", value=interaction.user.mention, inline=True)
                    sponsor_embed.add_field(name="Duration", value=f"{duration} days", inline=True)
                    sponsor_embed.add_field(name="Reason", value=reason, inline=False)
                    await sponsor.send(embed=sponsor_embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send drop notification to sponsor {sponsor.id}")
            
            # Send notification through prospect notifications system
            try:
                from cogs.prospect_notifications import ProspectNotifications
                prospect_notifications = self.bot.get_cog('ProspectNotifications')
                if prospect_notifications:
                    await prospect_notifications.send_prospect_drop_notification(
                        interaction.guild, prospect, sponsor, reason,
                        await self.bot.db.get_server_config(interaction.guild.id) or {}
                    )
            except Exception as e:
                logger.warning(f"Error sending drop notifications: {e}")
            
        except Exception as e:
            logger.error(f"Error dropping prospect: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while dropping the prospect: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="prospect-view", description="View detailed information about a prospect")
    @app_commands.describe(prospect="The prospect to view information for")
    async def prospect_view(self, interaction: discord.Interaction, prospect: discord.Member):
        """View detailed prospect information"""
        if not await has_required_permissions(interaction, 
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator', 'Sponsor', 'Member']):
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

    @app_commands.command(name="prospect-list", description="List all prospects with their current status")
    async def prospect_list(self, interaction: discord.Interaction):
        """List all prospects in the guild"""
        if not await has_required_permissions(interaction, 
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator', 'Sponsor', 'Member']):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

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
            recent_activity += "• Use `/prospect-add` to add new prospects\n"
            recent_activity += "• Use `/prospect-task assign` to assign tasks\n"
            recent_activity += "• Use `/prospect-note add` for notes and strikes"
            
            embed.add_field(name="🔗 Quick Actions", value=recent_activity, inline=False)
            embed.set_footer(text="Use /prospect-dashboard for interactive management")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing prospects: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while listing prospects: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProspectManagement(bot))

"""
Consolidated Prospect Management Core
Combines essential prospect management, tasks, notes, and voting functionality
to stay within Discord's slash command limits.
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

class ProspectCore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        logger.info("ProspectCore cog initialized")

    # ==================== PROSPECT MANAGEMENT ====================
    
    @app_commands.command(name="prospect_add", description="Add a new prospect")
    @app_commands.describe(
        prospect="The prospect member to add",
        sponsor="The sponsoring member"
    )
    async def add_prospect(
        self,
        interaction: discord.Interaction,
        prospect: discord.Member,
        sponsor: discord.Member
    ):
        """Add a new prospect"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if user is authorized
            auth_result = await self.db.check_management_permissions(interaction.user.id, interaction.guild.id)
            if not auth_result['authorized']:
                await interaction.followup.send(f"❌ {auth_result['message']}", ephemeral=True)
                return
            
            # Check if already a prospect
            existing = await self.db.get_prospect(prospect.id, interaction.guild.id)
            if existing:
                await interaction.followup.send("❌ This member is already a prospect.", ephemeral=True)
                return
            
            # Create sponsor role name
            sponsor_role_name = f"Sponsor of {prospect.display_name}"
            prospect_role_name = f"Prospect of {sponsor.display_name}"
            
            # Create roles
            try:
                sponsor_role = await interaction.guild.create_role(
                    name=sponsor_role_name,
                    reason=f"Prospect sponsorship role for {prospect.display_name}"
                )
                prospect_role = await interaction.guild.create_role(
                    name=prospect_role_name,
                    reason=f"Prospect role for {prospect.display_name}"
                )
                
                # Assign roles
                await sponsor.add_roles(sponsor_role, reason="Added as sponsor")
                await prospect.add_roles(prospect_role, reason="Added as prospect")
                
            except discord.Forbidden:
                await interaction.followup.send("❌ I don't have permission to create/assign roles.", ephemeral=True)
                return
            except Exception as e:
                await interaction.followup.send(f"❌ Error creating roles: {e}", ephemeral=True)
                return
            
            # Add to database
            prospect_id = await self.db.add_prospect(
                prospect.id,
                sponsor.id,
                interaction.guild.id,
                prospect_role.id,
                sponsor_role.id
            )
            
            # Success embed
            embed = discord.Embed(
                title="✅ Prospect Added",
                description=f"{prospect.mention} has been added as a prospect sponsored by {sponsor.mention}",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=sponsor.mention, inline=True)
            embed.set_footer(text=f"Added by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Added prospect {prospect.id} sponsored by {sponsor.id} in guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error adding prospect: {e}")
            await interaction.followup.send(f"❌ Error adding prospect: {e}", ephemeral=True)

    @app_commands.command(name="prospect_patch", description="Patch (promote) a prospect")
    @app_commands.describe(prospect="The prospect to patch/promote")
    async def patch_prospect(self, interaction: discord.Interaction, prospect: discord.Member):
        """Patch (promote) a prospect"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check authorization
            auth_result = await self.db.check_management_permissions(interaction.user.id, interaction.guild.id)
            if not auth_result['authorized']:
                await interaction.followup.send(f"❌ {auth_result['message']}", ephemeral=True)
                return
            
            # Get prospect info
            prospect_info = await self.db.get_prospect(prospect.id, interaction.guild.id)
            if not prospect_info:
                await interaction.followup.send("❌ This member is not a prospect.", ephemeral=True)
                return
            
            if prospect_info['status'] != 'active':
                await interaction.followup.send("❌ This prospect is not active.", ephemeral=True)
                return
            
            # Get sponsor info
            sponsor = interaction.guild.get_member(prospect_info['sponsor_id'])
            
            # Remove and delete roles
            try:
                # Remove prospect role
                if prospect_info['prospect_role_id']:
                    prospect_role = interaction.guild.get_role(prospect_info['prospect_role_id'])
                    if prospect_role:
                        await prospect.remove_roles(prospect_role, reason="Prospect patched")
                        await prospect_role.delete(reason="Prospect patched")
                
                # Remove sponsor role
                if prospect_info['sponsor_role_id'] and sponsor:
                    sponsor_role = interaction.guild.get_role(prospect_info['sponsor_role_id'])
                    if sponsor_role:
                        await sponsor.remove_roles(sponsor_role, reason="Prospect patched")
                        await sponsor_role.delete(reason="Prospect patched")
                
            except Exception as e:
                logger.warning(f"Error cleaning up roles during patch: {e}")
            
            # Update database
            await self.db.patch_prospect(prospect.id, interaction.guild.id, interaction.user.id)
            
            # Success embed
            embed = discord.Embed(
                title="🎉 Prospect Patched!",
                description=f"{prospect.mention} has been successfully patched!",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Patched Member", value=prospect.mention, inline=True)
            if sponsor:
                embed.add_field(name="Former Sponsor", value=sponsor.mention, inline=True)
            embed.add_field(name="Patched By", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Welcome to full membership!")
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect
            try:
                dm_embed = discord.Embed(
                    title="🎉 Congratulations!",
                    description=f"You have been patched in **{interaction.guild.name}**!",
                    color=0x00ff00
                )
                await prospect.send(embed=dm_embed)
            except:
                pass  # DM failed, continue
            
            logger.info(f"Patched prospect {prospect.id} in guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error patching prospect: {e}")
            await interaction.followup.send(f"❌ Error patching prospect: {e}", ephemeral=True)

    @app_commands.command(name="prospect_list", description="List all prospects")
    async def list_prospects(self, interaction: discord.Interaction):
        """List all prospects"""
        await interaction.response.defer()
        
        try:
            prospects = await self.db.get_all_prospects(interaction.guild.id)
            
            if not prospects:
                embed = discord.Embed(
                    title="📋 Prospect List",
                    description="No prospects found.",
                    color=0x3498db
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Group by status
            active_prospects = [p for p in prospects if p['status'] == 'active']
            archived_prospects = [p for p in prospects if p['status'] != 'active']
            
            embed = discord.Embed(
                title="📋 Prospect List",
                color=0x3498db,
                timestamp=datetime.utcnow()
            )
            
            if active_prospects:
                active_list = []
                for prospect in active_prospects[:10]:  # Limit to 10
                    member = interaction.guild.get_member(prospect['prospect_id'])
                    sponsor = interaction.guild.get_member(prospect['sponsor_id'])
                    
                    member_name = member.display_name if member else f"Unknown ({prospect['prospect_id']})"
                    sponsor_name = sponsor.display_name if sponsor else f"Unknown ({prospect['sponsor_id']})"
                    
                    active_list.append(f"• {member_name} (sponsored by {sponsor_name})")
                
                embed.add_field(
                    name=f"Active Prospects ({len(active_prospects)})",
                    value="\n".join(active_list) if active_list else "None",
                    inline=False
                )
            
            if archived_prospects:
                embed.add_field(
                    name=f"Archived Prospects ({len(archived_prospects)})",
                    value=f"Use prospect dashboard to view details",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing prospects: {e}")
            await interaction.followup.send(f"❌ Error listing prospects: {e}", ephemeral=True)

    # ==================== PROSPECT TASKS ====================
    
    @app_commands.command(name="prospect_task_add", description="Add a task for a prospect")
    @app_commands.describe(
        prospect="The prospect to assign the task to",
        task_description="Description of the task"
    )
    async def add_prospect_task(
        self,
        interaction: discord.Interaction,
        prospect: discord.Member,
        task_description: str
    ):
        """Add a task for a prospect"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check authorization
            auth_result = await self.db.check_management_permissions(interaction.user.id, interaction.guild.id)
            if not auth_result['authorized']:
                await interaction.followup.send(f"❌ {auth_result['message']}", ephemeral=True)
                return
            
            # Verify prospect exists
            prospect_info = await self.db.get_prospect(prospect.id, interaction.guild.id)
            if not prospect_info or prospect_info['status'] != 'active':
                await interaction.followup.send("❌ This member is not an active prospect.", ephemeral=True)
                return
            
            # Add task
            task_id = await self.db.add_prospect_task(
                prospect.id,
                interaction.guild.id,
                task_description,
                interaction.user.id
            )
            
            embed = discord.Embed(
                title="📋 Task Added",
                description=f"Task added for {prospect.mention}",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Task", value=task_description, inline=False)
            embed.set_footer(text=f"Added by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect
            try:
                dm_embed = discord.Embed(
                    title="📋 New Task Assigned",
                    description=f"You have been assigned a new task in **{interaction.guild.name}**",
                    color=0x3498db
                )
                dm_embed.add_field(name="Task", value=task_description, inline=False)
                dm_embed.add_field(name="Assigned by", value=interaction.user.display_name, inline=True)
                await prospect.send(embed=dm_embed)
            except:
                pass
            
            logger.info(f"Added task for prospect {prospect.id} in guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error adding prospect task: {e}")
            await interaction.followup.send(f"❌ Error adding task: {e}", ephemeral=True)

    @app_commands.command(name="prospect_note_add", description="Add a note for a prospect")
    @app_commands.describe(
        prospect="The prospect to add a note for",
        note_content="Content of the note"
    )
    async def add_prospect_note(
        self,
        interaction: discord.Interaction,
        prospect: discord.Member,
        note_content: str
    ):
        """Add a note for a prospect"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check authorization
            auth_result = await self.db.check_management_permissions(interaction.user.id, interaction.guild.id)
            if not auth_result['authorized']:
                await interaction.followup.send(f"❌ {auth_result['message']}", ephemeral=True)
                return
            
            # Verify prospect exists
            prospect_info = await self.db.get_prospect(prospect.id, interaction.guild.id)
            if not prospect_info:
                await interaction.followup.send("❌ This member is not a prospect.", ephemeral=True)
                return
            
            # Add note
            note_id = await self.db.add_prospect_note(
                prospect.id,
                interaction.guild.id,
                note_content,
                interaction.user.id
            )
            
            embed = discord.Embed(
                title="📝 Note Added",
                description=f"Note added for {prospect.mention}",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Note", value=note_content, inline=False)
            embed.set_footer(text=f"Added by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Added note for prospect {prospect.id} in guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error adding prospect note: {e}")
            await interaction.followup.send(f"❌ Error adding note: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ProspectCore(bot))

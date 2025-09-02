import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional, List
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectNotesConsolidated(commands.Cog):
    """Consolidated prospect notes management commands with subcommands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectNotesConsolidated cog initialized")

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
            
            # Send special notification for strikes reaching thresholds
            if is_strike and config:
                new_total_strikes = current_strikes + 1
                
                if new_total_strikes >= 3 and config.get('alerts_channel_id'):
                    alerts_channel = self.bot.get_channel(config['alerts_channel_id'])
                    if alerts_channel:
                        alert_embed = discord.Embed(
                            title="🚨 Prospect Strike Alert",
                            description=f"{prospect.mention} now has **{new_total_strikes} strikes**!",
                            color=discord.Color.dark_red()
                        )
                        alert_embed.add_field(name="Latest Strike", value=content, inline=False)
                        alert_embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
                        alert_embed.set_footer(text="Consider reviewing this prospect's status")
                        await alerts_channel.send(embed=alert_embed)
            
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
                    
                    if len(prospect_summaries) > 10:
                        embed.add_field(
                            name="📄 Note",
                            value=f"Showing top 10 prospects. Use `/prospect-note list @prospect` for detailed view.",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="👥 Prospects with Notes",
                        value="No prospects have notes or strikes",
                        inline=False
                    )
                
                # Recent activity (last 5 notes across all prospects)
                try:
                    recent_notes = await self.bot.db.get_recent_prospect_notes(interaction.guild.id, limit=5)
                    if recent_notes:
                        recent_list = []
                        for note in recent_notes:
                            prospect_name = note.get('prospect_name', f"User {note.get('prospect_user_id', 'Unknown')}")
                            created_date = datetime.fromisoformat(note['created_at'])
                            author_name = note.get('author_name', 'Unknown')
                            note_type = "⚠️" if note.get('is_strike', False) else "📝"
                            
                            content_preview = note['content'][:50] + ('...' if len(note['content']) > 50 else '')
                            
                            recent_list.append(
                                f"{note_type} **{prospect_name}** - <t:{int(created_date.timestamp())}:R>\n"
                                f"   └ {content_preview} *({author_name})*"
                            )
                        
                        embed.add_field(
                            name="🕒 Recent Activity",
                            value="\n".join(recent_list),
                            inline=False
                        )
                except Exception as e:
                    logger.error(f"Error getting recent notes: {e}")
            
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
    await bot.add_cog(ProspectNotesConsolidated(bot))

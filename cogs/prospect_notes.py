import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectNotes(commands.Cog):
    """Prospect notes and strikes management commands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectNotes cog initialized")

    @app_commands.command(name="note-add", description="Add a note to a prospect's record")
    @app_commands.describe(
        prospect="The prospect to add a note for",
        note="The note to add to their record",
        is_strike="Whether this note is a strike (counts toward strikes total)"
    )
    async def note_add(self, interaction: discord.Interaction, prospect: discord.Member, 
                      note: str, is_strike: bool = False):
        """Add a note to a prospect's record"""
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
            
            # Add the note
            note_id = await self.bot.db.add_prospect_note(
                interaction.guild.id,
                prospect_record['id'],
                interaction.user.id,
                note,
                is_strike
            )
            
            # Get updated prospect record to show current strike count
            updated_prospect = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
            
            # Create success embed
            embed_color = discord.Color.orange() if is_strike else discord.Color.blue()
            embed_title = f"⚠️ Strike Added" if is_strike else f"📝 Note Added"
            
            embed = discord.Embed(
                title=embed_title,
                color=embed_color,
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
            
            if is_strike:
                embed.add_field(name="Total Strikes", value=str(updated_prospect['strikes']), inline=True)
            
            embed.add_field(name="Note", value=note, inline=False)
            embed.set_footer(text=f"Note ID: {note_id}")
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect about the note/strike
            try:
                dm_title = "⚠️ Strike Added" if is_strike else "📝 Note Added"
                dm_color = discord.Color.orange() if is_strike else discord.Color.blue()
                
                dm_embed = discord.Embed(
                    title=dm_title,
                    description=f"A {'strike' if is_strike else 'note'} has been added to your record in **{interaction.guild.name}**",
                    color=dm_color
                )
                dm_embed.add_field(name="Note", value=note, inline=False)
                dm_embed.add_field(name="Added by", value=interaction.user.display_name, inline=True)
                
                if is_strike:
                    dm_embed.add_field(name="Total Strikes", value=str(updated_prospect['strikes']), inline=True)
                    if updated_prospect['strikes'] >= 3:
                        dm_embed.add_field(
                            name="⚠️ Warning", 
                            value="You have reached 3 or more strikes. Your prospect status may be at risk.", 
                            inline=False
                        )
                
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send note/strike DM to prospect {prospect.id}")
            
            # Notify sponsor about the note/strike
            try:
                sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
                if sponsor:
                    sponsor_title = f"⚠️ Strike Added to Your Prospect" if is_strike else f"📝 Note Added to Your Prospect"
                    sponsor_color = discord.Color.orange() if is_strike else discord.Color.blue()
                    
                    sponsor_embed = discord.Embed(
                        title=sponsor_title,
                        description=f"A {'strike' if is_strike else 'note'} has been added to {prospect.mention}'s record",
                        color=sponsor_color
                    )
                    sponsor_embed.add_field(name="Note", value=note, inline=False)
                    sponsor_embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
                    
                    if is_strike:
                        sponsor_embed.add_field(name="Total Strikes", value=str(updated_prospect['strikes']), inline=True)
                        if updated_prospect['strikes'] >= 3:
                            sponsor_embed.add_field(
                                name="⚠️ Action Needed", 
                                value="Your prospect has 3+ strikes. Consider additional guidance or mentoring.", 
                                inline=False
                            )
                    
                    await sponsor.send(embed=sponsor_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send note/strike notification to sponsor {prospect_record['sponsor_id']}")
            except Exception as e:
                logger.warning(f"Error sending sponsor notification: {e}")
            
            # Log to leadership channel if it's a strike
            if is_strike:
                config = await self.bot.db.get_server_config(interaction.guild.id)
                if config and config.get('leadership_channel_id'):
                    leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                    if leadership_channel:
                        leadership_embed = embed.copy()
                        leadership_embed.add_field(name="Added by", value=interaction.user.mention, inline=True)
                        
                        # Add warning if prospect has too many strikes
                        if updated_prospect['strikes'] >= 3:
                            leadership_embed.add_field(
                                name="⚠️ High Strike Count",
                                value=f"This prospect now has {updated_prospect['strikes']} strikes and may need review.",
                                inline=False
                            )
                        
                        await leadership_channel.send(embed=leadership_embed)
                        
        except Exception as e:
            logger.error(f"Error adding note: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while adding the note: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="note-list", description="List all notes for a prospect")
    @app_commands.describe(
        prospect="The prospect to list notes for",
        note_type="Filter notes by type (all, notes, strikes)"
    )
    @app_commands.choices(note_type=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Notes Only", value="notes"),
        app_commands.Choice(name="Strikes Only", value="strikes")
    ])
    async def note_list(self, interaction: discord.Interaction, prospect: discord.Member, 
                       note_type: str = "all"):
        """List all notes for a prospect"""
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
            
            # Get all notes
            all_notes = await self.bot.db.get_prospect_notes(prospect_record['id'])
            
            # Filter notes by type
            if note_type == "strikes":
                notes = [n for n in all_notes if n['is_strike']]
            elif note_type == "notes":
                notes = [n for n in all_notes if not n['is_strike']]
            else:  # all
                notes = all_notes
            
            # Create embed
            type_colors = {
                'all': discord.Color.blue(),
                'notes': discord.Color.blue(),
                'strikes': discord.Color.orange()
            }
            
            embed = discord.Embed(
                title=f"{'📝📋' if note_type == 'all' else '📝' if note_type == 'notes' else '⚠️'} {note_type.title()} for {prospect.display_name}",
                color=type_colors.get(note_type, discord.Color.blue()),
                timestamp=datetime.now()
            )
            
            if not notes:
                embed.add_field(
                    name="No Notes Found", 
                    value=f"No {note_type} found for this prospect.", 
                    inline=False
                )
            else:
                # Add summary for "all" type
                if note_type == "all":
                    strikes_count = len([n for n in all_notes if n['is_strike']])
                    notes_count = len(all_notes) - strikes_count
                    
                    summary = f"**Total:** {len(all_notes)}\n"
                    summary += f"📝 Notes: {notes_count}\n"
                    summary += f"⚠️ Strikes: {strikes_count}"
                    
                    embed.add_field(name="Summary", value=summary, inline=True)
                
                # Add current strikes total
                embed.add_field(name="Current Strikes", value=str(prospect_record['strikes']), inline=True)
                
                # Sort notes by date (newest first)
                notes.sort(key=lambda x: x['created_at'], reverse=True)
                
                # Add individual notes
                for i, note in enumerate(notes[:15]):  # Limit to 15 notes
                    note_emoji = "⚠️" if note['is_strike'] else "📝"
                    author_name = note.get('author_name', f"User {note['author_id']}")
                    author_rank = note.get('author_rank', '')
                    
                    created_date = datetime.fromisoformat(note['created_at'])
                    
                    field_name = f"{note_emoji} {author_name}"
                    if author_rank:
                        field_name += f" ({author_rank})"
                    
                    field_value = f"**Date:** <t:{int(created_date.timestamp())}:F>\n"
                    field_value += f"**Note:** {note['note_text']}"
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                
                if len(notes) > 15:
                    embed.add_field(
                        name="Note",
                        value=f"Showing first 15 of {len(notes)} {note_type}.",
                        inline=False
                    )
            
            embed.set_footer(text=f"Prospect ID: {prospect_record['id']}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error listing notes: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while retrieving notes: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="strike-summary", description="Show a summary of all prospects with strikes")
    async def strike_summary(self, interaction: discord.Interaction):
        """Show a summary of all prospects with strikes"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get all active prospects
            active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
            
            # Filter prospects with strikes
            prospects_with_strikes = [p for p in active_prospects if p.get('strike_count', 0) > 0]
            
            embed = discord.Embed(
                title="⚠️ Strike Summary",
                description=f"Active prospects with strikes",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            if not prospects_with_strikes:
                embed.description = "No active prospects have strikes! 🎉"
                embed.color = discord.Color.green()
                embed.add_field(
                    name="Great News!",
                    value="All your active prospects are performing well without any strikes.",
                    inline=False
                )
            else:
                # Sort by strike count (highest first)
                prospects_with_strikes.sort(key=lambda x: x.get('strike_count', 0), reverse=True)
                
                # Add summary statistics
                total_with_strikes = len(prospects_with_strikes)
                high_risk_count = len([p for p in prospects_with_strikes if p.get('strike_count', 0) >= 3])
                moderate_risk_count = len([p for p in prospects_with_strikes if p.get('strike_count', 0) == 2])
                low_risk_count = len([p for p in prospects_with_strikes if p.get('strike_count', 0) == 1])
                
                summary = f"**Total with strikes:** {total_with_strikes}\n"
                if high_risk_count > 0:
                    summary += f"🚨 High risk (3+ strikes): {high_risk_count}\n"
                if moderate_risk_count > 0:
                    summary += f"⚠️ Moderate risk (2 strikes): {moderate_risk_count}\n"
                if low_risk_count > 0:
                    summary += f"⚡ Low risk (1 strike): {low_risk_count}"
                
                embed.add_field(name="Summary", value=summary, inline=True)
                
                # Add individual prospects
                for i, prospect in enumerate(prospects_with_strikes[:10]):  # Limit to 10
                    prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                    sponsor_name = prospect.get('sponsor_name', f"User {prospect['sponsor_id']}")
                    strike_count = prospect.get('strike_count', 0)
                    
                    # Calculate trial duration
                    start_date = datetime.fromisoformat(prospect['start_date'])
                    duration = (datetime.now() - start_date).days
                    
                    # Determine risk level emoji
                    if strike_count >= 3:
                        risk_emoji = "🚨"
                        risk_level = "HIGH RISK"
                    elif strike_count == 2:
                        risk_emoji = "⚠️"
                        risk_level = "MODERATE RISK"
                    else:
                        risk_emoji = "⚡"
                        risk_level = "LOW RISK"
                    
                    field_name = f"{risk_emoji} {prospect_name} ({strike_count} strikes)"
                    
                    field_value = f"**Status:** {risk_level}\n"
                    field_value += f"**Sponsor:** {sponsor_name}\n"
                    field_value += f"**Trial Duration:** {duration} days\n"
                    
                    # Add task performance if available
                    if prospect.get('total_tasks', 0) > 0:
                        completed_tasks = prospect.get('completed_tasks', 0)
                        failed_tasks = prospect.get('failed_tasks', 0)
                        total_tasks = prospect.get('total_tasks', 0)
                        
                        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
                        field_value += f"**Tasks:** {completed_tasks}/{total_tasks} completed ({completion_rate:.0f}%)"
                        
                        if failed_tasks > 0:
                            field_value += f", {failed_tasks} failed"
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                
                if len(prospects_with_strikes) > 10:
                    embed.add_field(
                        name="Note",
                        value=f"Showing top 10 of {len(prospects_with_strikes)} prospects with strikes.",
                        inline=False
                    )
                
                # Add recommendations
                recommendations = []
                if high_risk_count > 0:
                    recommendations.append("🚨 **High Risk:** Consider reviewing prospects with 3+ strikes")
                if moderate_risk_count > 0:
                    recommendations.append("⚠️ **Moderate Risk:** Provide additional guidance to prospects with 2 strikes")
                
                if recommendations:
                    embed.add_field(
                        name="Recommendations",
                        value="\n".join(recommendations),
                        inline=False
                    )
            
            embed.set_footer(text=f"Total active prospects: {len(active_prospects)}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting strike summary: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while retrieving strike summary: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="note-search", description="Search for notes containing specific text")
    @app_commands.describe(
        search_text="Text to search for in notes",
        prospect="Optional: specific prospect to search (leave blank to search all prospects)"
    )
    async def note_search(self, interaction: discord.Interaction, search_text: str, 
                         prospect: Optional[discord.Member] = None):
        """Search for notes containing specific text"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
            
            if len(search_text) < 3:
                await interaction.followup.send(
                    "❌ Search text must be at least 3 characters long.",
                    ephemeral=True
                )
                return
            
            search_results = []
            
            if prospect:
                # Search notes for specific prospect
                prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
                if not prospect_record:
                    await interaction.followup.send(
                        f"❌ {prospect.mention} is not a prospect!",
                        ephemeral=True
                    )
                    return
                
                notes = await self.bot.db.get_prospect_notes(prospect_record['id'])
                for note in notes:
                    if search_text.lower() in note['note_text'].lower():
                        search_results.append({
                            **note,
                            'prospect_name': prospect.display_name,
                            'prospect_user_id': prospect.id
                        })
            else:
                # Search notes for all prospects
                active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
                archived_prospects = await self.bot.db.get_archived_prospects(interaction.guild.id)
                all_prospects = active_prospects + archived_prospects
                
                for prospect_record in all_prospects:
                    notes = await self.bot.db.get_prospect_notes(prospect_record['id'])
                    for note in notes:
                        if search_text.lower() in note['note_text'].lower():
                            search_results.append({
                                **note,
                                'prospect_name': prospect_record.get('prospect_name', f"User {prospect_record['user_id']}"),
                                'prospect_user_id': prospect_record['user_id']
                            })
            
            embed = discord.Embed(
                title=f"🔍 Note Search Results",
                description=f"Searching for: **{search_text}**",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if not search_results:
                embed.add_field(
                    name="No Results Found",
                    value=f"No notes found containing '{search_text}'.",
                    inline=False
                )
            else:
                # Sort by date (newest first)
                search_results.sort(key=lambda x: x['created_at'], reverse=True)
                
                embed.add_field(
                    name="Results Found",
                    value=f"Found {len(search_results)} matching notes",
                    inline=True
                )
                
                if prospect:
                    embed.add_field(
                        name="Searched",
                        value=f"Notes for {prospect.mention}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="Searched",
                        value="All prospect notes",
                        inline=True
                    )
                
                # Add search results
                for i, result in enumerate(search_results[:10]):  # Limit to 10 results
                    note_emoji = "⚠️" if result['is_strike'] else "📝"
                    author_name = result.get('author_name', f"User {result['author_id']}")
                    prospect_name = result['prospect_name']
                    
                    created_date = datetime.fromisoformat(result['created_at'])
                    
                    field_name = f"{note_emoji} {prospect_name} - {author_name}"
                    
                    # Highlight search term in note text
                    note_text = result['note_text']
                    highlighted_text = note_text.replace(
                        search_text, 
                        f"**{search_text}**"
                    )
                    
                    # Truncate if too long
                    if len(highlighted_text) > 200:
                        highlighted_text = highlighted_text[:200] + "..."
                    
                    field_value = f"**Date:** <t:{int(created_date.timestamp())}:R>\n"
                    field_value += f"**Note:** {highlighted_text}"
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                
                if len(search_results) > 10:
                    embed.add_field(
                        name="Note",
                        value=f"Showing first 10 of {len(search_results)} results.",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error searching notes: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while searching notes: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProspectNotes(bot))

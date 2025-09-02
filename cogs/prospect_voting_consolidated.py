import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
from typing import Optional, List
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectVotingConsolidated(commands.Cog):
    """Consolidated prospect voting management commands with subcommands"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectVotingConsolidated cog initialized")

    @app_commands.command(name="prospect-vote", description="Prospect voting management commands")
    @app_commands.describe(
        action="The action to perform",
        prospect="The prospect user (required for start action)",
        vote="Your vote (required for cast action)",
        vote_id="Vote ID (required for status/end actions)",
        duration="Voting duration in hours (optional for start action, default: 24)"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Start new vote", value="start"),
            app_commands.Choice(name="Cast your vote", value="cast"),
            app_commands.Choice(name="Check vote status", value="status"),
            app_commands.Choice(name="End vote early", value="end"),
            app_commands.Choice(name="View vote history", value="history")
        ],
        vote=[
            app_commands.Choice(name="Yes", value="yes"),
            app_commands.Choice(name="No", value="no"),
            app_commands.Choice(name="Abstain", value="abstain")
        ]
    )
    async def prospect_vote(
        self, 
        interaction: discord.Interaction, 
        action: str, 
        prospect: Optional[discord.Member] = None,
        vote: Optional[str] = None,
        vote_id: Optional[int] = None,
        duration: Optional[int] = 24
    ):
        """Main prospect voting management command with subcommands"""
        # Permission check
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator', 'Full Patch']):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        if action == "start":
            await self._vote_start(interaction, prospect, duration)
        elif action == "cast":
            await self._vote_cast(interaction, vote, vote_id)
        elif action == "status":
            await self._vote_status(interaction, vote_id)
        elif action == "end":
            await self._vote_end(interaction, vote_id)
        elif action == "history":
            await self._vote_history(interaction, prospect)

    async def _vote_start(self, interaction: discord.Interaction, prospect: discord.Member, duration: int):
        """Start a new prospect vote"""
        if not prospect:
            await interaction.response.send_message("❌ Please specify a prospect to vote on.", ephemeral=True)
            return

        # Additional permission check for starting votes
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']):
            await interaction.response.send_message("❌ Only leadership can start prospect votes.", ephemeral=True)
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
            
            # Check if there's already an active vote for this prospect
            active_vote = await self.bot.db.get_active_prospect_vote(prospect_record['id'])
            if active_vote:
                await interaction.followup.send(
                    f"❌ There is already an active vote for {prospect.mention}! (Vote ID: {active_vote['id']})", 
                    ephemeral=True
                )
                return
            
            # Validate duration
            if duration < 1 or duration > 168:  # 1 hour to 1 week
                await interaction.followup.send(
                    "❌ Voting duration must be between 1 and 168 hours (1 week)!", 
                    ephemeral=True
                )
                return
            
            # Calculate end time
            end_time = datetime.now() + timedelta(hours=duration)
            
            # Create vote
            vote_id = await self.bot.db.create_prospect_vote(
                prospect_record['id'],
                interaction.user.id,
                end_time
            )
            
            # Create embed
            embed = discord.Embed(
                title="🗳️ Prospect Vote Started",
                description=f"A vote has been started for prospect **{prospect.display_name}**",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Started by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Vote ID", value=f"`{vote_id}`", inline=True)
            
            embed.add_field(name="Duration", value=f"{duration} hours", inline=True)
            embed.add_field(name="Ends", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
            embed.add_field(name="Status", value="🟢 Active", inline=True)
            
            # Get prospect stats for context
            try:
                tasks = await self.bot.db.get_prospect_tasks(prospect_record['id'])
                notes = await self.bot.db.get_prospect_notes(prospect_record['id'])
                
                completed_tasks = len([t for t in tasks if t['status'] == 'completed'])
                failed_tasks = len([t for t in tasks if t['status'] == 'failed'])
                strikes = len([n for n in notes if n.get('is_strike', False)])
                
                context_info = f"**Tasks:** {completed_tasks} completed, {failed_tasks} failed\n"
                context_info += f"**Strikes:** {strikes}\n"
                context_info += f"**Duration as prospect:** {(datetime.now() - datetime.fromisoformat(prospect_record['start_date'])).days} days"
                
                embed.add_field(name="📊 Prospect Summary", value=context_info, inline=False)
            except Exception as e:
                logger.error(f"Error getting prospect context: {e}")
            
            embed.add_field(
                name="🗳️ How to Vote", 
                value=f"Use `/prospect-vote cast {vote_id} <yes/no/abstain>` to cast your vote",
                inline=False
            )
            
            embed.set_footer(text="All full patch members and leadership can vote")
            
            await interaction.followup.send(embed=embed)
            
            # Send to leadership and voting channels
            config = await self.bot.db.get_server_config(interaction.guild.id)
            
            if config and config.get('voting_channel_id'):
                voting_channel = self.bot.get_channel(config['voting_channel_id'])
                if voting_channel:
                    voting_embed = embed.copy()
                    voting_embed.add_field(
                        name="🔔 Attention", 
                        value="All eligible members please cast your votes!", 
                        inline=False
                    )
                    await voting_channel.send(f"@everyone", embed=voting_embed)
            
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel and leadership_channel != voting_channel:
                    await leadership_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error starting prospect vote: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while starting the vote: {str(e)}", 
                ephemeral=True
            )

    async def _vote_cast(self, interaction: discord.Interaction, vote: str, vote_id: int):
        """Cast a vote"""
        if not vote:
            await interaction.response.send_message("❌ Please specify your vote (yes/no/abstain).", ephemeral=True)
            return
        if not vote_id:
            await interaction.response.send_message("❌ Please provide a vote ID to cast your vote on.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get vote record
            vote_record = await self.bot.db.get_prospect_vote(vote_id)
            if not vote_record:
                await interaction.followup.send("❌ Vote not found!", ephemeral=True)
                return
            
            # Verify vote belongs to this guild
            prospect = await self.bot.db.get_prospect_by_id(vote_record['prospect_id'])
            if not prospect or prospect['guild_id'] != interaction.guild.id:
                await interaction.followup.send("❌ Vote not found in this server!", ephemeral=True)
                return
            
            # Check if vote is still active
            end_time = datetime.fromisoformat(vote_record['end_time'])
            if datetime.now() > end_time:
                await interaction.followup.send("❌ This vote has already ended!", ephemeral=True)
                return
            
            if vote_record['status'] != 'active':
                await interaction.followup.send("❌ This vote is no longer active!", ephemeral=True)
                return
            
            # Check if user already voted
            existing_vote = await self.bot.db.get_user_vote(vote_id, interaction.user.id)
            if existing_vote:
                await interaction.followup.send(
                    f"❌ You have already voted on this proposal! (Your vote: {existing_vote['vote'].title()})", 
                    ephemeral=True
                )
                return
            
            # Cast vote
            await self.bot.db.cast_prospect_vote(vote_id, interaction.user.id, vote)
            
            # Get prospect member for display
            prospect_member = interaction.guild.get_member(prospect['user_id'])
            prospect_name = prospect_member.display_name if prospect_member else f"User {prospect['user_id']}"
            
            # Create confirmation embed
            vote_colors = {
                'yes': discord.Color.green(),
                'no': discord.Color.red(),
                'abstain': discord.Color.grey()
            }
            
            embed = discord.Embed(
                title="✅ Vote Cast Successfully",
                description=f"Your vote has been recorded for **{prospect_name}**",
                color=vote_colors.get(vote, discord.Color.blue()),
                timestamp=datetime.now()
            )
            embed.add_field(name="Vote ID", value=f"`{vote_id}`", inline=True)
            embed.add_field(name="Your Vote", value=vote.title(), inline=True)
            embed.add_field(name="Prospect", value=prospect_name, inline=True)
            
            embed.set_footer(text="Your vote is confidential and cannot be changed")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log vote cast (without revealing the vote)
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    log_embed = discord.Embed(
                        title="📊 Vote Cast",
                        description=f"{interaction.user.mention} has cast their vote on **{prospect_name}**",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    log_embed.add_field(name="Vote ID", value=f"`{vote_id}`", inline=True)
                    log_embed.set_footer(text="Vote content is confidential")
                    await leadership_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Error casting prospect vote: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while casting your vote: {str(e)}", 
                ephemeral=True
            )

    async def _vote_status(self, interaction: discord.Interaction, vote_id: int):
        """Check vote status"""
        if not vote_id:
            # Show all active votes
            try:
                await interaction.response.defer()
                
                active_votes = await self.bot.db.get_active_votes(interaction.guild.id)
                
                embed = discord.Embed(
                    title="🗳️ Active Prospect Votes",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                if not active_votes:
                    embed.description = "No active votes found."
                    await interaction.followup.send(embed=embed)
                    return
                
                votes_list = []
                for vote in active_votes:
                    prospect_name = vote.get('prospect_name', f"User {vote.get('prospect_user_id', 'Unknown')}")
                    end_time = datetime.fromisoformat(vote['end_time'])
                    
                    # Get vote counts
                    votes_cast = await self.bot.db.get_vote_counts(vote['id'])
                    total_votes = votes_cast['yes'] + votes_cast['no'] + votes_cast['abstain']
                    
                    time_left = end_time - datetime.now()
                    if time_left.total_seconds() > 0:
                        time_status = f"<t:{int(end_time.timestamp())}:R>"
                    else:
                        time_status = "⚠️ Ended"
                    
                    votes_list.append(
                        f"`{vote['id']}` **{prospect_name}**\n"
                        f"   └ Ends: {time_status}\n"
                        f"   └ Votes: {total_votes} cast"
                    )
                
                embed.add_field(
                    name="📋 Active Votes",
                    value="\n".join(votes_list),
                    inline=False
                )
                
                embed.set_footer(text="Use /prospect-vote status <vote_id> for detailed view")
                
                await interaction.followup.send(embed=embed)
                return
                
            except Exception as e:
                logger.error(f"Error showing active votes: {e}")
                await interaction.followup.send(
                    f"❌ An error occurred while showing active votes: {str(e)}", 
                    ephemeral=True
                )
                return

        # Show specific vote status
        try:
            await interaction.response.defer()
            
            # Get vote record
            vote_record = await self.bot.db.get_prospect_vote(vote_id)
            if not vote_record:
                await interaction.followup.send("❌ Vote not found!", ephemeral=True)
                return
            
            # Verify vote belongs to this guild
            prospect = await self.bot.db.get_prospect_by_id(vote_record['prospect_id'])
            if not prospect or prospect['guild_id'] != interaction.guild.id:
                await interaction.followup.send("❌ Vote not found in this server!", ephemeral=True)
                return
            
            # Get vote counts
            votes_cast = await self.bot.db.get_vote_counts(vote_id)
            total_votes = votes_cast['yes'] + votes_cast['no'] + votes_cast['abstain']
            
            # Get prospect member
            prospect_member = interaction.guild.get_member(prospect['user_id'])
            prospect_name = prospect_member.display_name if prospect_member else f"User {prospect['user_id']}"
            
            # Calculate percentages
            if total_votes > 0:
                yes_pct = (votes_cast['yes'] / total_votes) * 100
                no_pct = (votes_cast['no'] / total_votes) * 100
                abstain_pct = (votes_cast['abstain'] / total_votes) * 100
            else:
                yes_pct = no_pct = abstain_pct = 0
            
            # Determine status and color
            end_time = datetime.fromisoformat(vote_record['end_time'])
            if vote_record['status'] != 'active':
                status_text = vote_record['status'].title()
                color = discord.Color.grey()
            elif datetime.now() > end_time:
                status_text = "⚠️ Ended (not closed)"
                color = discord.Color.orange()
            else:
                status_text = "🟢 Active"
                color = discord.Color.green()
            
            embed = discord.Embed(
                title=f"🗳️ Vote Status: {prospect_name}",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Vote ID", value=f"`{vote_id}`", inline=True)
            embed.add_field(name="Status", value=status_text, inline=True)
            embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
            
            embed.add_field(name="Started", value=f"<t:{int(datetime.fromisoformat(vote_record['created_at']).timestamp())}:F>", inline=True)
            embed.add_field(name="Ends/Ended", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
            
            # Time remaining
            if vote_record['status'] == 'active' and datetime.now() < end_time:
                time_left = end_time - datetime.now()
                hours_left = int(time_left.total_seconds() / 3600)
                embed.add_field(name="Time Left", value=f"{hours_left} hours", inline=True)
            else:
                embed.add_field(name="Time Left", value="None", inline=True)
            
            # Vote breakdown
            vote_breakdown = f"✅ **Yes:** {votes_cast['yes']} ({yes_pct:.1f}%)\n"
            vote_breakdown += f"❌ **No:** {votes_cast['no']} ({no_pct:.1f}%)\n"
            vote_breakdown += f"⚪ **Abstain:** {votes_cast['abstain']} ({abstain_pct:.1f}%)"
            
            embed.add_field(name="📊 Vote Breakdown", value=vote_breakdown, inline=False)
            
            # Progress bar
            if total_votes > 0:
                bar_length = 20
                yes_bars = int((votes_cast['yes'] / total_votes) * bar_length)
                no_bars = int((votes_cast['no'] / total_votes) * bar_length)
                abstain_bars = bar_length - yes_bars - no_bars
                
                progress_bar = "🟢" * yes_bars + "🔴" * no_bars + "⚪" * abstain_bars
                embed.add_field(name="📈 Visual Progress", value=progress_bar, inline=False)
            
            # Check if user has voted (show only to the user)
            user_vote = await self.bot.db.get_user_vote(vote_id, interaction.user.id)
            if user_vote:
                embed.add_field(name="Your Vote", value=user_vote['vote'].title(), inline=True)
            else:
                embed.add_field(name="Your Vote", value="Not cast", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing vote status: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while showing vote status: {str(e)}", 
                ephemeral=True
            )

    async def _vote_end(self, interaction: discord.Interaction, vote_id: int):
        """End a vote early"""
        if not vote_id:
            await interaction.response.send_message("❌ Please provide a vote ID to end.", ephemeral=True)
            return

        # Additional permission check for ending votes
        if not await has_required_permissions(interaction, 
                                            required_permissions=['manage_guild'],
                                            allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']):
            await interaction.response.send_message("❌ Only leadership can end votes.", ephemeral=True)
            return

        try:
            await interaction.response.defer()
            
            # Get vote record
            vote_record = await self.bot.db.get_prospect_vote(vote_id)
            if not vote_record:
                await interaction.followup.send("❌ Vote not found!", ephemeral=True)
                return
            
            # Verify vote belongs to this guild
            prospect = await self.bot.db.get_prospect_by_id(vote_record['prospect_id'])
            if not prospect or prospect['guild_id'] != interaction.guild.id:
                await interaction.followup.send("❌ Vote not found in this server!", ephemeral=True)
                return
            
            if vote_record['status'] != 'active':
                await interaction.followup.send("❌ This vote is not active!", ephemeral=True)
                return
            
            # End the vote
            await self.bot.db.update_vote_status(vote_id, 'completed', interaction.user.id)
            
            # Get final vote counts
            votes_cast = await self.bot.db.get_vote_counts(vote_id)
            total_votes = votes_cast['yes'] + votes_cast['no'] + votes_cast['abstain']
            
            # Get prospect member
            prospect_member = interaction.guild.get_member(prospect['user_id'])
            prospect_name = prospect_member.display_name if prospect_member else f"User {prospect['user_id']}"
            
            # Determine result
            if votes_cast['yes'] > votes_cast['no']:
                result = "✅ PASSED"
                result_color = discord.Color.green()
            elif votes_cast['no'] > votes_cast['yes']:
                result = "❌ FAILED"
                result_color = discord.Color.red()
            else:
                result = "🤝 TIED"
                result_color = discord.Color.orange()
            
            # Create result embed
            embed = discord.Embed(
                title="🗳️ Vote Ended",
                description=f"Vote for **{prospect_name}** has been ended by {interaction.user.mention}",
                color=result_color,
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Vote ID", value=f"`{vote_id}`", inline=True)
            embed.add_field(name="Result", value=result, inline=True)
            embed.add_field(name="Total Votes", value=str(total_votes), inline=True)
            
            # Final vote breakdown
            if total_votes > 0:
                yes_pct = (votes_cast['yes'] / total_votes) * 100
                no_pct = (votes_cast['no'] / total_votes) * 100
                abstain_pct = (votes_cast['abstain'] / total_votes) * 100
            else:
                yes_pct = no_pct = abstain_pct = 0
            
            vote_breakdown = f"✅ **Yes:** {votes_cast['yes']} ({yes_pct:.1f}%)\n"
            vote_breakdown += f"❌ **No:** {votes_cast['no']} ({no_pct:.1f}%)\n"
            vote_breakdown += f"⚪ **Abstain:** {votes_cast['abstain']} ({abstain_pct:.1f}%)"
            
            embed.add_field(name="📊 Final Results", value=vote_breakdown, inline=False)
            
            embed.set_footer(text="Vote has been permanently closed")
            
            await interaction.followup.send(embed=embed)
            
            # Send to voting and leadership channels
            config = await self.bot.db.get_server_config(interaction.guild.id)
            
            if config and config.get('voting_channel_id'):
                voting_channel = self.bot.get_channel(config['voting_channel_id'])
                if voting_channel:
                    await voting_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error ending prospect vote: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while ending the vote: {str(e)}", 
                ephemeral=True
            )

    async def _vote_history(self, interaction: discord.Interaction, prospect: discord.Member):
        """View voting history"""
        try:
            await interaction.response.defer()
            
            if prospect:
                # Get voting history for specific prospect
                prospect_record = await self.bot.db.get_prospect_by_user(interaction.guild.id, prospect.id)
                if not prospect_record:
                    await interaction.followup.send(
                        f"❌ {prospect.mention} is not a prospect!", 
                        ephemeral=True
                    )
                    return
                
                vote_history = await self.bot.db.get_prospect_vote_history(prospect_record['id'])
                
                embed = discord.Embed(
                    title=f"🗳️ Voting History: {prospect.display_name}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                if not vote_history:
                    embed.description = "No voting history found for this prospect."
                    await interaction.followup.send(embed=embed)
                    return
                
                history_list = []
                for vote in vote_history:
                    created_date = datetime.fromisoformat(vote['created_at'])
                    end_date = datetime.fromisoformat(vote['end_time'])
                    
                    # Get vote counts
                    votes_cast = await self.bot.db.get_vote_counts(vote['id'])
                    total_votes = votes_cast['yes'] + votes_cast['no'] + votes_cast['abstain']
                    
                    # Determine result
                    if vote['status'] == 'completed':
                        if votes_cast['yes'] > votes_cast['no']:
                            result = "✅ Passed"
                        elif votes_cast['no'] > votes_cast['yes']:
                            result = "❌ Failed"
                        else:
                            result = "🤝 Tied"
                    else:
                        result = f"❓ {vote['status'].title()}"
                    
                    history_list.append(
                        f"`{vote['id']}` <t:{int(created_date.timestamp())}:d> - {result}\n"
                        f"   └ Votes: {votes_cast['yes']}✅ {votes_cast['no']}❌ {votes_cast['abstain']}⚪ (Total: {total_votes})"
                    )
                
                embed.add_field(
                    name="📋 Vote History",
                    value="\n".join(history_list),
                    inline=False
                )
                
            else:
                # Show recent voting activity across all prospects
                recent_votes = await self.bot.db.get_recent_votes(interaction.guild.id, limit=10)
                
                embed = discord.Embed(
                    title="🗳️ Recent Voting Activity",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                if not recent_votes:
                    embed.description = "No recent voting activity found."
                    await interaction.followup.send(embed=embed)
                    return
                
                activity_list = []
                for vote in recent_votes:
                    prospect_name = vote.get('prospect_name', f"User {vote.get('prospect_user_id', 'Unknown')}")
                    created_date = datetime.fromisoformat(vote['created_at'])
                    
                    # Get vote counts
                    votes_cast = await self.bot.db.get_vote_counts(vote['id'])
                    total_votes = votes_cast['yes'] + votes_cast['no'] + votes_cast['abstain']
                    
                    # Status
                    if vote['status'] == 'active':
                        status = "🟢 Active"
                    elif vote['status'] == 'completed':
                        if votes_cast['yes'] > votes_cast['no']:
                            status = "✅ Passed"
                        elif votes_cast['no'] > votes_cast['yes']:
                            status = "❌ Failed"
                        else:
                            status = "🤝 Tied"
                    else:
                        status = f"❓ {vote['status'].title()}"
                    
                    activity_list.append(
                        f"`{vote['id']}` **{prospect_name}** - <t:{int(created_date.timestamp())}:R>\n"
                        f"   └ {status} • {total_votes} votes cast"
                    )
                
                embed.add_field(
                    name="📋 Recent Activity",
                    value="\n".join(activity_list),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing vote history: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while showing vote history: {str(e)}", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProspectVotingConsolidated(bot))

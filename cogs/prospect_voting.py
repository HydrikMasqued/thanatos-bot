import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from typing import Optional
from utils.permissions import has_required_permissions

logger = logging.getLogger(__name__)

class ProspectVoting(commands.Cog):
    """Anonymous voting system for prospect patch/drop decisions"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectVoting cog initialized")

    @app_commands.command(name="vote-start", description="Start a patch or drop vote for a prospect")
    @app_commands.describe(
        prospect="The prospect to vote on",
        vote_type="Type of vote (patch or drop)"
    )
    @app_commands.choices(vote_type=[
        app_commands.Choice(name="Patch (Promote to Full Member)", value="patch"),
        app_commands.Choice(name="Drop (Remove from Prospects)", value="drop")
    ])
    async def vote_start(self, interaction: discord.Interaction, prospect: discord.Member, vote_type: str):
        """Start a new vote for a prospect"""
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
            
            # Check for existing active vote
            active_vote = await self.bot.db.get_active_prospect_vote(prospect_record['id'])
            if active_vote:
                await interaction.followup.send(
                    f"❌ There is already an active {active_vote['vote_type']} vote for {prospect.mention}!",
                    ephemeral=True
                )
                return
            
            # Create the vote
            vote_id = await self.bot.db.create_prospect_vote(
                interaction.guild.id,
                prospect_record['id'],
                interaction.user.id,
                vote_type
            )
            
            # Create vote embed
            vote_colors = {
                'patch': discord.Color.green(),
                'drop': discord.Color.red()
            }
            
            vote_emojis = {
                'patch': '🎖️',
                'drop': '❌'
            }
            
            embed = discord.Embed(
                title=f"{vote_emojis[vote_type]} {vote_type.title()} Vote Started",
                description=f"A vote has been started for **{prospect.display_name}**",
                color=vote_colors[vote_type],
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Sponsor", value=f"<@{prospect_record['sponsor_id']}>", inline=True)
            embed.add_field(name="Vote Type", value=vote_type.title(), inline=True)
            
            # Calculate trial duration
            start_date = datetime.fromisoformat(prospect_record['start_date'])
            duration = (datetime.now() - start_date).days
            embed.add_field(name="Trial Duration", value=f"{duration} days", inline=True)
            embed.add_field(name="Current Strikes", value=str(prospect_record['strikes']), inline=True)
            embed.add_field(name="Started by", value=interaction.user.mention, inline=True)
            
            # Add voting instructions
            instructions = "**How to Vote:**\n"
            instructions += "• Use `/vote-cast` to cast your vote\n"
            instructions += "• Choose: **Yes**, **No**, or **Abstain**\n"
            instructions += "• You can change your vote anytime before the vote ends\n"
            instructions += "• **Unanimous YES votes required to pass**\n"
            instructions += "• Use `/vote-status` to check current results (anonymous)\n"
            instructions += "• Leadership can use `/vote-end` to conclude voting"
            
            embed.add_field(name="Voting Instructions", value=instructions, inline=False)
            
            embed.set_footer(text=f"Vote ID: {vote_id} • Anonymous voting system")
            
            await interaction.followup.send(embed=embed)
            
            # Send DM to prospect about the vote
            try:
                dm_title = f"🎖️ Patch Vote Started" if vote_type == 'patch' else f"❌ Drop Vote Started"
                dm_color = vote_colors[vote_type]
                
                dm_embed = discord.Embed(
                    title=dm_title,
                    description=f"A {vote_type} vote has been started for you in **{interaction.guild.name}**",
                    color=dm_color
                )
                
                if vote_type == 'patch':
                    dm_embed.add_field(
                        name="Good News!",
                        value="The leadership is considering promoting you to full member status.",
                        inline=False
                    )
                else:
                    dm_embed.add_field(
                        name="Important Notice",
                        value="Your prospect status is being reviewed. You will be notified of the outcome.",
                        inline=False
                    )
                
                dm_embed.add_field(name="Trial Duration", value=f"{duration} days", inline=True)
                dm_embed.add_field(name="Started by", value=interaction.user.display_name, inline=True)
                
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send vote notification DM to prospect {prospect.id}")
            
            # Notify sponsor
            try:
                sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
                if sponsor:
                    sponsor_embed = discord.Embed(
                        title=f"{vote_emojis[vote_type]} Vote Started for Your Prospect",
                        description=f"A {vote_type} vote has been started for {prospect.mention}",
                        color=vote_colors[vote_type]
                    )
                    sponsor_embed.add_field(name="Vote Type", value=vote_type.title(), inline=True)
                    sponsor_embed.add_field(name="Started by", value=interaction.user.mention, inline=True)
                    sponsor_embed.add_field(name="Trial Duration", value=f"{duration} days", inline=True)
                    sponsor_embed.add_field(
                        name="What This Means",
                        value=f"The leadership is voting on whether to {vote_type} your prospect. You'll be notified of the results.",
                        inline=False
                    )
                    
                    await sponsor.send(embed=sponsor_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send vote notification to sponsor {prospect_record['sponsor_id']}")
            except Exception as e:
                logger.warning(f"Error sending sponsor notification: {e}")
            
            # Log to leadership channel
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    leadership_embed = embed.copy()
                    await leadership_channel.send(embed=leadership_embed)
                    
        except ValueError as e:
            # Handle specific database errors (like existing vote)
            await interaction.followup.send(
                f"❌ {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error starting vote: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while starting the vote: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="vote-cast", description="Cast your vote on an active prospect vote")
    @app_commands.describe(
        prospect="The prospect you're voting on",
        vote="Your vote decision"
    )
    @app_commands.choices(vote=[
        app_commands.Choice(name="Yes - Support the action", value="yes"),
        app_commands.Choice(name="No - Oppose the action", value="no"),
        app_commands.Choice(name="Abstain - No opinion", value="abstain")
    ])
    async def vote_cast(self, interaction: discord.Interaction, prospect: discord.Member, vote: str):
        """Cast a vote on an active prospect vote"""
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
            
            # Get active vote
            active_vote = await self.bot.db.get_active_prospect_vote(prospect_record['id'])
            if not active_vote:
                await interaction.followup.send(
                    f"❌ There is no active vote for {prospect.mention}!",
                    ephemeral=True
                )
                return
            
            # Cast the vote
            success = await self.bot.db.cast_prospect_vote(
                active_vote['id'],
                interaction.user.id,
                vote
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ Failed to cast your vote. Please try again.",
                    ephemeral=True
                )
                return
            
            # Create confirmation embed
            vote_emojis = {
                'yes': '✅',
                'no': '❌',
                'abstain': '🤷'
            }
            
            vote_colors = {
                'yes': discord.Color.green(),
                'no': discord.Color.red(),
                'abstain': discord.Color.yellow()
            }
            
            embed = discord.Embed(
                title=f"{vote_emojis[vote]} Vote Cast Successfully",
                description=f"Your vote has been recorded for the **{active_vote['vote_type']}** vote",
                color=vote_colors[vote],
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Vote Type", value=active_vote['vote_type'].title(), inline=True)
            embed.add_field(name="Your Vote", value=f"{vote_emojis[vote]} {vote.title()}", inline=True)
            
            embed.add_field(
                name="Note",
                value="Your vote is anonymous. You can change it anytime by voting again before the vote ends.",
                inline=False
            )
            
            embed.set_footer(text="Use /vote-status to see current anonymous results")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error casting vote: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while casting your vote: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="vote-status", description="Check the status of an active prospect vote")
    @app_commands.describe(prospect="The prospect to check vote status for")
    async def vote_status(self, interaction: discord.Interaction, prospect: discord.Member):
        """Check the status of an active vote (anonymous results)"""
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
            
            # Get active vote
            active_vote = await self.bot.db.get_active_prospect_vote(prospect_record['id'])
            if not active_vote:
                await interaction.followup.send(
                    f"❌ There is no active vote for {prospect.mention}!",
                    ephemeral=True
                )
                return
            
            # Check if user is bot owner (for detailed results)
            is_bot_owner = interaction.user.id == self.bot.owner_id if hasattr(self.bot, 'owner_id') else False
            
            # Get vote responses
            vote_summary = await self.bot.db.get_vote_responses(active_vote['id'], include_voter_ids=is_bot_owner)
            
            # Create status embed
            vote_colors = {
                'patch': discord.Color.green(),
                'drop': discord.Color.red()
            }
            
            vote_emojis = {
                'patch': '🎖️',
                'drop': '❌'
            }
            
            embed = discord.Embed(
                title=f"{vote_emojis[active_vote['vote_type']]} Vote Status: {prospect.display_name}",
                description=f"**{active_vote['vote_type'].title()}** vote in progress",
                color=vote_colors[active_vote['vote_type']],
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Started by", value=active_vote.get('started_by_name', 'Unknown'), inline=True)
            
            # Vote started time
            started_time = datetime.fromisoformat(active_vote['started_at'])
            embed.add_field(name="Started", value=f"<t:{int(started_time.timestamp())}:R>", inline=True)
            
            # Vote results (anonymous)
            results = f"✅ **Yes:** {vote_summary['yes']}\n"
            results += f"❌ **No:** {vote_summary['no']}\n"
            results += f"🤷 **Abstain:** {vote_summary['abstain']}\n"
            results += f"📊 **Total Votes:** {vote_summary['total']}"
            
            embed.add_field(name="Current Results (Anonymous)", value=results, inline=True)
            
            # Determine current outcome
            total_votes = vote_summary['total']
            yes_votes = vote_summary['yes']
            
            if total_votes == 0:
                outcome_text = "⏳ **No votes cast yet**"
                outcome_color = discord.Color.yellow()
            elif yes_votes == total_votes and total_votes > 0:
                outcome_text = f"🎉 **PASSING** (Unanimous: {yes_votes}/{total_votes})"
                outcome_color = discord.Color.green()
            else:
                no_and_abstain = vote_summary['no'] + vote_summary['abstain']
                outcome_text = f"❌ **FAILING** (Not unanimous: {yes_votes} yes, {no_and_abstain} no/abstain)"
                outcome_color = discord.Color.red()
            
            embed.add_field(name="Current Outcome", value=outcome_text, inline=True)
            
            # Requirements
            requirements = "**Passing Requirements:**\n"
            requirements += "• **Unanimous YES votes required**\n"
            requirements += "• Any NO or ABSTAIN vote = failure\n"
            requirements += "• Leadership can end vote at any time"
            
            embed.add_field(name="Voting Rules", value=requirements, inline=False)
            
            # Instructions
            instructions = "**Actions Available:**\n"
            instructions += "• Use `/vote-cast` to vote or change your vote\n"
            instructions += "• Use `/vote-end` (leadership) to conclude voting\n"
            instructions += "• Vote anonymously - individual votes are private"
            
            embed.add_field(name="Instructions", value=instructions, inline=False)
            
            # Add detailed voter info for bot owner
            if is_bot_owner and vote_summary['responses']:
                voter_details = []
                for response in vote_summary['responses']:
                    voter_name = response.get('voter_name', f"User {response['voter_id']}")
                    vote_emoji = {'yes': '✅', 'no': '❌', 'abstain': '🤷'}[response['vote_response']]
                    voter_details.append(f"{vote_emoji} {voter_name}")
                
                if voter_details:
                    embed.add_field(
                        name="🔒 Detailed Votes (Bot Owner Only)",
                        value="\n".join(voter_details[:10]),
                        inline=False
                    )
            
            embed.set_footer(text=f"Vote ID: {active_vote['id']} • Anonymous voting system")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error checking vote status: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while checking vote status: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="vote-end", description="End an active prospect vote and apply results")
    @app_commands.describe(prospect="The prospect whose vote to end")
    async def vote_end(self, interaction: discord.Interaction, prospect: discord.Member):
        """End an active vote and apply the results"""
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
            
            # Get active vote
            active_vote = await self.bot.db.get_active_prospect_vote(prospect_record['id'])
            if not active_vote:
                await interaction.followup.send(
                    f"❌ There is no active vote for {prospect.mention}!",
                    ephemeral=True
                )
                return
            
            # Get vote results
            vote_summary = await self.bot.db.get_vote_responses(active_vote['id'])
            
            # Determine result
            total_votes = vote_summary['total']
            yes_votes = vote_summary['yes']
            
            if total_votes > 0 and yes_votes == total_votes:
                result = 'passed'
            else:
                result = 'failed'
            
            # End the vote
            await self.bot.db.end_prospect_vote(active_vote['id'], interaction.user.id, result)
            
            # Create results embed
            vote_colors = {
                'patch': discord.Color.green() if result == 'passed' else discord.Color.red(),
                'drop': discord.Color.red() if result == 'passed' else discord.Color.green()
            }
            
            result_emojis = {
                'passed': '✅',
                'failed': '❌'
            }
            
            embed = discord.Embed(
                title=f"{result_emojis[result]} Vote Concluded: {result.upper()}",
                description=f"The **{active_vote['vote_type']}** vote for **{prospect.display_name}** has ended",
                color=vote_colors[active_vote['vote_type']],
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Prospect", value=prospect.mention, inline=True)
            embed.add_field(name="Vote Type", value=active_vote['vote_type'].title(), inline=True)
            embed.add_field(name="Result", value=f"{result_emojis[result]} {result.title()}", inline=True)
            
            # Final vote tally
            results_text = f"✅ **Yes:** {vote_summary['yes']}\n"
            results_text += f"❌ **No:** {vote_summary['no']}\n"
            results_text += f"🤷 **Abstain:** {vote_summary['abstain']}\n"
            results_text += f"📊 **Total:** {vote_summary['total']}"
            
            embed.add_field(name="Final Vote Tally", value=results_text, inline=True)
            
            # Add reasoning
            if result == 'passed':
                if total_votes > 0:
                    reason = f"Unanimous approval ({yes_votes}/{total_votes} yes votes)"
                else:
                    reason = "No votes cast - treating as passed by leadership decision"
            else:
                if total_votes == 0:
                    reason = "No votes cast - vote failed"
                else:
                    no_and_abstain = vote_summary['no'] + vote_summary['abstain']
                    reason = f"Not unanimous ({yes_votes} yes, {no_and_abstain} no/abstain)"
            
            embed.add_field(name="Reason", value=reason, inline=True)
            embed.add_field(name="Ended by", value=interaction.user.mention, inline=True)
            
            # Add next steps
            if result == 'passed':
                if active_vote['vote_type'] == 'patch':
                    next_steps = f"✅ {prospect.mention} should be promoted to Full Member using `/prospect-patch`"
                else:  # drop
                    next_steps = f"❌ {prospect.mention} should be removed using `/prospect-drop`"
            else:
                if active_vote['vote_type'] == 'patch':
                    next_steps = f"⏳ {prospect.mention} remains a prospect - continue trial period"
                else:  # drop
                    next_steps = f"⏳ {prospect.mention} remains a prospect - continue trial period"
            
            embed.add_field(name="Next Steps", value=next_steps, inline=False)
            embed.set_footer(text=f"Vote ID: {active_vote['id']} • Ended after {(datetime.now() - datetime.fromisoformat(active_vote['started_at'])).days} days")
            
            await interaction.followup.send(embed=embed)
            
            # Send notification DMs
            vote_outcome = "approved" if result == 'passed' else "rejected"
            
            # Notify prospect
            try:
                dm_color = discord.Color.green() if result == 'passed' else discord.Color.red()
                dm_title = f"🎉 Vote Results: {result.title()}" if result == 'passed' else f"📢 Vote Results: {result.title()}"
                
                dm_embed = discord.Embed(
                    title=dm_title,
                    description=f"The {active_vote['vote_type']} vote for you has concluded in **{interaction.guild.name}**",
                    color=dm_color
                )
                
                dm_embed.add_field(name="Result", value=f"{result_emojis[result]} {result.title()}", inline=True)
                dm_embed.add_field(name="Vote Type", value=active_vote['vote_type'].title(), inline=True)
                
                if result == 'passed':
                    if active_vote['vote_type'] == 'patch':
                        dm_embed.add_field(
                            name="🎉 Congratulations!",
                            value="You have been approved for promotion to Full Member! Leadership will complete the promotion process.",
                            inline=False
                        )
                    else:
                        dm_embed.add_field(
                            name="📢 Decision Made",
                            value="The vote to remove you has been approved. You will be contacted by leadership.",
                            inline=False
                        )
                else:
                    dm_embed.add_field(
                        name="⏳ Continue Trial",
                        value=f"The {active_vote['vote_type']} vote was not approved. You remain a prospect and should continue your trial period.",
                        inline=False
                    )
                
                dm_embed.add_field(name="Final Tally", value=results_text, inline=True)
                
                await prospect.send(embed=dm_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send vote result DM to prospect {prospect.id}")
            
            # Notify sponsor
            try:
                sponsor = interaction.guild.get_member(prospect_record['sponsor_id'])
                if sponsor:
                    sponsor_embed = discord.Embed(
                        title=f"📊 Vote Results for Your Prospect",
                        description=f"The {active_vote['vote_type']} vote for {prospect.mention} has concluded",
                        color=dm_color
                    )
                    sponsor_embed.add_field(name="Result", value=f"{result_emojis[result]} {result.title()}", inline=True)
                    sponsor_embed.add_field(name="Vote Type", value=active_vote['vote_type'].title(), inline=True)
                    sponsor_embed.add_field(name="Final Tally", value=results_text, inline=True)
                    
                    if result == 'passed':
                        if active_vote['vote_type'] == 'patch':
                            message = "Your prospect has been approved for promotion! Great job sponsoring them."
                        else:
                            message = "The decision has been made to remove your prospect."
                    else:
                        message = f"The {active_vote['vote_type']} vote was not approved. Continue mentoring your prospect."
                    
                    sponsor_embed.add_field(name="Message", value=message, inline=False)
                    
                    await sponsor.send(embed=sponsor_embed)
            except discord.Forbidden:
                logger.warning(f"Could not send vote result to sponsor {prospect_record['sponsor_id']}")
            except Exception as e:
                logger.warning(f"Error sending sponsor notification: {e}")
            
            # Log to leadership channel
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if config and config.get('leadership_channel_id'):
                leadership_channel = self.bot.get_channel(config['leadership_channel_id'])
                if leadership_channel:
                    leadership_embed = embed.copy()
                    await leadership_channel.send(embed=leadership_embed)
                    
        except Exception as e:
            logger.error(f"Error ending vote: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while ending the vote: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="vote-history", description="View voting history for a prospect")
    @app_commands.describe(prospect="The prospect to view vote history for")
    async def vote_history(self, interaction: discord.Interaction, prospect: discord.Member):
        """View the voting history for a prospect"""
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
            
            # Get vote history
            vote_history = await self.bot.db.get_prospect_vote_history(prospect_record['id'])
            
            embed = discord.Embed(
                title=f"🗳️ Vote History: {prospect.display_name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if not vote_history:
                embed.add_field(
                    name="No Votes Found",
                    value="No votes have been held for this prospect yet.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Prospect",
                    value=prospect.mention,
                    inline=True
                )
                embed.add_field(
                    name="Total Votes",
                    value=str(len(vote_history)),
                    inline=True
                )
                
                # Count vote types and outcomes
                patch_votes = len([v for v in vote_history if v['vote_type'] == 'patch'])
                drop_votes = len([v for v in vote_history if v['vote_type'] == 'drop'])
                passed_votes = len([v for v in vote_history if v['result'] == 'passed'])
                failed_votes = len([v for v in vote_history if v['result'] == 'failed'])
                active_votes = len([v for v in vote_history if v['status'] == 'active'])
                
                summary = f"🎖️ Patch: {patch_votes} | ❌ Drop: {drop_votes}\n"
                summary += f"✅ Passed: {passed_votes} | ❌ Failed: {failed_votes}\n"
                summary += f"⏳ Active: {active_votes}"
                
                embed.add_field(name="Summary", value=summary, inline=True)
                
                # Add individual vote details
                for i, vote in enumerate(vote_history[:10]):  # Limit to 10 votes
                    vote_emoji = '🎖️' if vote['vote_type'] == 'patch' else '❌'
                    status_emoji = {
                        'active': '⏳',
                        'completed': '✅' if vote['result'] == 'passed' else '❌',
                        'cancelled': '🚫'
                    }.get(vote['status'], '❓')
                    
                    started_time = datetime.fromisoformat(vote['started_at'])
                    starter_name = vote.get('started_by_name', 'Unknown')
                    
                    field_name = f"{vote_emoji} {vote['vote_type'].title()} Vote {status_emoji}"
                    
                    field_value = f"**Started:** <t:{int(started_time.timestamp())}:F>\n"
                    field_value += f"**Started by:** {starter_name}\n"
                    field_value += f"**Status:** {vote['status'].title()}"
                    
                    if vote['status'] == 'completed':
                        field_value += f" ({vote['result']})\n"
                        if vote['ended_at']:
                            ended_time = datetime.fromisoformat(vote['ended_at'])
                            field_value += f"**Ended:** <t:{int(ended_time.timestamp())}:F>\n"
                        if vote.get('ended_by_name'):
                            field_value += f"**Ended by:** {vote['ended_by_name']}"
                    elif vote['status'] == 'active':
                        field_value += " (In Progress)"
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                
                if len(vote_history) > 10:
                    embed.add_field(
                        name="Note",
                        value=f"Showing 10 most recent of {len(vote_history)} total votes.",
                        inline=False
                    )
            
            embed.set_footer(text=f"Prospect ID: {prospect_record['id']}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error getting vote history: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while retrieving vote history: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProspectVoting(bot))

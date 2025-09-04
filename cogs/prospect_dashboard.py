import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
import os
import sys
from typing import Optional, List, Dict

# Multiple approaches to ensure utils module can be imported
try:
    # First, try adding the project root to Python path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Also try current working directory
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    
    # Try /home/container if we're in that environment
    if '/home/container' not in sys.path:
        sys.path.insert(0, '/home/container')
        
except Exception:
    pass  # Continue even if path manipulation fails

# Set up logger first
logger = logging.getLogger(__name__)

# Try to import utils.permissions with error handling and fallback
try:
    from utils.permissions import has_required_permissions
    logger.info("✅ Successfully imported utils.permissions")
except ImportError as e:
    logger.error(f"❌ Failed to import utils.permissions: {e}")
    logger.error(f"Current working directory: {os.getcwd()}")
    logger.error(f"Python path: {sys.path[:5]}")
    logger.warning("⚠️ Using dummy permissions function - all permissions will be allowed!")
    
    # Define a dummy permission function that always returns True
    async def has_required_permissions(interaction, required_permissions=None, allowed_roles=None, bot_owner_override=True):
        """Dummy permissions function - ALLOWS ALL ACCESS"""
        return True

class ProspectSelectionView(discord.ui.View):
    """View for selecting prospects from dropdowns"""
    
    def __init__(self, bot, user_id: int, prospects: List[Dict], view_type: str = "active"):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.prospects = prospects
        self.view_type = view_type
        
        # Only add select menu if there are prospects
        if prospects:
            options = []
            for i, prospect in enumerate(prospects[:25]):
                prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                sponsor_name = prospect.get('sponsor_name', f"User {prospect['sponsor_id']}")
                
                # Calculate trial duration
                start_date = datetime.fromisoformat(prospect['start_date'])
                if prospect['status'] == 'active':
                    duration = (datetime.now() - start_date).days
                else:
                    end_date = datetime.fromisoformat(prospect['end_date']) if prospect.get('end_date') else datetime.now()
                    duration = (end_date - start_date).days
                
                # Create description with key info
                description = f"Sponsor: {sponsor_name} | {duration} days"
                if prospect.get('strike_count', 0) > 0:
                    description += f" | ⚠️ {prospect['strike_count']} strikes"
                
                options.append(discord.SelectOption(
                    label=prospect_name,
                    description=description[:100],  # Discord limit
                    value=str(prospect['id']),
                    emoji='🟢' if prospect['status'] == 'active' else '🟡' if prospect['status'] == 'patched' else '🔴'
                ))
            
            # Create the select menu with options
            select = discord.ui.Select(
                placeholder="Select a prospect to view details...",
                options=options,
                custom_id="prospect_select"
            )
            select.callback = self.prospect_select_callback
            self.add_item(select)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    async def prospect_select_callback(self, interaction: discord.Interaction):
        """Handle prospect selection"""
        prospect_id = int(interaction.data['values'][0])
        
        # Find the selected prospect
        selected_prospect = None
        for prospect in self.prospects:
            if prospect['id'] == prospect_id:
                selected_prospect = prospect
                break
        
        if not selected_prospect:
            await interaction.response.send_message("❌ Prospect not found.", ephemeral=True)
            return
        
        # Create detailed view for the selected prospect
        view = ProspectDetailView(self.bot, self.user_id, selected_prospect, self.view_type)
        embed = await view.create_prospect_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_prospects(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the prospect list"""
        # Get updated prospect list
        if self.view_type == "active":
            prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
            title = "🟢 Active Prospects"
            color = discord.Color.green()
        else:
            prospects = await self.bot.db.get_archived_prospects(interaction.guild.id)
            title = "📁 Archived Prospects"
            color = 0x808080
        
        # Create new view with updated prospects
        new_view = ProspectSelectionView(self.bot, self.user_id, prospects, self.view_type)
        
        embed = discord.Embed(
            title=title,
            description=f"Select a prospect from the dropdown below to view detailed information.\n\n**Total {self.view_type} prospects:** {len(prospects)}",
            color=color,
            timestamp=datetime.now()
        )
        
        if not prospects:
            embed.add_field(
                name="No Prospects Found",
                value=f"There are currently no {self.view_type} prospects.",
                inline=False
            )
        
        embed.set_footer(text="Use the dropdown to select a prospect for details")
        
        await interaction.response.edit_message(embed=embed, view=new_view)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to main prospect dashboard menu"""
        view = ProspectDashboardView(self.bot, self.user_id)
        embed = await view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class ProspectDetailView(discord.ui.View):
    """Detailed view for a specific prospect"""
    
    def __init__(self, bot, user_id: int, prospect: Dict, view_type: str = "active"):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.prospect = prospect
        self.view_type = view_type
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    async def create_prospect_embed(self) -> discord.Embed:
        """Create detailed prospect embed"""
        prospect_name = self.prospect.get('prospect_name', f"User {self.prospect['user_id']}")
        sponsor_name = self.prospect.get('sponsor_name', f"User {self.prospect['sponsor_id']}")
        
        # Status colors
        status_colors = {
            'active': discord.Color.green(),
            'patched': discord.Color.gold(),
            'dropped': discord.Color.red(),
            'archived': 0x808080
        }
        
        embed = discord.Embed(
            title=f"📋 Prospect Profile: {prospect_name}",
            color=status_colors.get(self.prospect['status'], discord.Color.blue()),
            timestamp=datetime.now()
        )
        
        # Basic Information
        embed.add_field(name="Status", value=self.prospect['status'].title(), inline=True)
        embed.add_field(name="Sponsor", value=sponsor_name, inline=True)
        embed.add_field(name="Strikes", value=str(self.prospect.get('strikes', 0)), inline=True)
        
        # Dates and Duration
        start_date = datetime.fromisoformat(self.prospect['start_date'])
        embed.add_field(name="Start Date", value=f"<t:{int(start_date.timestamp())}:F>", inline=True)
        
        if self.prospect.get('end_date'):
            end_date = datetime.fromisoformat(self.prospect['end_date'])
            embed.add_field(name="End Date", value=f"<t:{int(end_date.timestamp())}:F>", inline=True)
            duration = (end_date - start_date).days
            embed.add_field(name="Total Duration", value=f"{duration} days", inline=True)
        else:
            duration = (datetime.now() - start_date).days
            embed.add_field(name="Current Duration", value=f"{duration} days", inline=True)
            embed.add_field(name="End Date", value="N/A (Active)", inline=True)
        
        # Tasks Summary
        total_tasks = self.prospect.get('total_tasks', 0)
        completed_tasks = self.prospect.get('completed_tasks', 0)
        failed_tasks = self.prospect.get('failed_tasks', 0)
        
        if total_tasks > 0:
            task_summary = f"**Total:** {total_tasks}\n"
            task_summary += f"✅ Completed: {completed_tasks}\n"
            task_summary += f"❌ Failed: {failed_tasks}\n"
            task_summary += f"⏳ Pending: {total_tasks - completed_tasks - failed_tasks}"
            
            # Calculate completion rate
            completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
            task_summary += f"\n📊 Rate: {completion_rate:.0f}%"
        else:
            task_summary = "No tasks assigned"
        
        embed.add_field(name="Tasks", value=task_summary, inline=True)
        
        # Notes & Strikes Summary
        total_notes = self.prospect.get('total_notes', 0)
        strike_count = self.prospect.get('strike_count', 0)
        
        if total_notes > 0:
            notes_summary = f"**Total:** {total_notes}\n"
            notes_summary += f"📝 Notes: {total_notes - strike_count}\n"
            notes_summary += f"⚠️ Strikes: {strike_count}"
        else:
            notes_summary = "No notes recorded"
        
        embed.add_field(name="Notes & Strikes", value=notes_summary, inline=True)
        
        # Performance Assessment
        if self.prospect['status'] == 'active':
            if strike_count >= 3:
                performance = "🚨 High Risk"
                performance_color = "❌"
            elif strike_count == 2:
                performance = "⚠️ Moderate Risk"
                performance_color = "⚠️"
            elif strike_count == 1:
                performance = "⚡ Low Risk"
                performance_color = "⚠️"
            else:
                if completion_rate >= 80 and total_tasks > 0:
                    performance = "🌟 Excellent"
                    performance_color = "✅"
                elif completion_rate >= 60 and total_tasks > 0:
                    performance = "👍 Good"
                    performance_color = "✅"
                elif total_tasks == 0:
                    performance = "📋 No Tasks Yet"
                    performance_color = "ℹ️"
                else:
                    performance = "📈 Needs Improvement"
                    performance_color = "⚠️"
            
            embed.add_field(name="Performance", value=f"{performance_color} {performance}", inline=True)
        
        # Footer with prospect ID
        embed.set_footer(text=f"Prospect ID: {self.prospect['id']} • Use buttons below for actions")
        
        return embed
    
    @discord.ui.button(label="📋 View Tasks", style=discord.ButtonStyle.primary)
    async def view_tasks(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View prospect's tasks"""
        # Get tasks for this prospect
        tasks = await self.bot.db.get_prospect_tasks(self.prospect['id'])
        
        embed = discord.Embed(
            title=f"📋 Tasks for {self.prospect.get('prospect_name', f'User {self.prospect['user_id']}')}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not tasks:
            embed.description = "No tasks have been assigned to this prospect yet."
        else:
            # Sort tasks by status and date
            tasks.sort(key=lambda x: (x['status'] == 'completed', x['status'] == 'failed', x['created_at']), reverse=True)
            
            for i, task in enumerate(tasks[:10]):  # Limit to 10 most recent
                status_emoji = {
                    'assigned': '⏳',
                    'completed': '✅',
                    'failed': '❌'
                }.get(task['status'], '❓')
                
                # Check if overdue
                overdue_text = ""
                if task['status'] == 'assigned' and task['due_date']:
                    due_date = datetime.fromisoformat(task['due_date'])
                    if datetime.now() > due_date:
                        overdue_text = " 🚨"
                
                field_name = f"{status_emoji} {task['task_name']}{overdue_text}"
                
                field_value = f"**Assigned by:** {task.get('assigned_by_name', 'Unknown')}\n"
                if task['due_date']:
                    due_date = datetime.fromisoformat(task['due_date'])
                    field_value += f"**Due:** <t:{int(due_date.timestamp())}:R>\n"
                
                # Truncate description
                description = task['task_description'][:100] + "..." if len(task['task_description']) > 100 else task['task_description']
                field_value += f"**Description:** {description}"
                
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            if len(tasks) > 10:
                embed.add_field(name="Note", value=f"Showing 10 most recent of {len(tasks)} total tasks.", inline=False)
        
        embed.set_footer(text="Use the back button to return to prospect profile")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="📝 View Notes", style=discord.ButtonStyle.secondary)
    async def view_notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View prospect's notes and strikes"""
        # Get notes for this prospect
        notes = await self.bot.db.get_prospect_notes(self.prospect['id'])
        
        embed = discord.Embed(
            title=f"📝 Notes for {self.prospect.get('prospect_name', f'User {self.prospect['user_id']}')}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not notes:
            embed.description = "No notes or strikes have been recorded for this prospect."
        else:
            # Sort notes by date (newest first)
            notes.sort(key=lambda x: x['created_at'], reverse=True)
            
            for i, note in enumerate(notes[:10]):  # Limit to 10 most recent
                note_emoji = "⚠️" if note['is_strike'] else "📝"
                author_name = note.get('author_name', f"User {note['author_id']}")
                author_rank = note.get('author_rank', '')
                
                created_date = datetime.fromisoformat(note['created_at'])
                
                field_name = f"{note_emoji} {author_name}"
                if author_rank:
                    field_name += f" ({author_rank})"
                
                field_value = f"**Date:** <t:{int(created_date.timestamp())}:F>\n"
                field_value += f"**{'Strike' if note['is_strike'] else 'Note'}:** {note['note_text']}"
                
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            if len(notes) > 10:
                embed.add_field(name="Note", value=f"Showing 10 most recent of {len(notes)} total notes.", inline=False)
        
        embed.set_footer(text="Use the back button to return to prospect profile")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🗳️ Vote History", style=discord.ButtonStyle.secondary)
    async def view_vote_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View prospect's voting history"""
        # Get vote history for this prospect
        votes = await self.bot.db.get_prospect_vote_history(self.prospect['id'])
        
        embed = discord.Embed(
            title=f"🗳️ Vote History for {self.prospect.get('prospect_name', f'User {self.prospect['user_id']}')}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not votes:
            embed.description = "No votes have been held for this prospect yet."
        else:
            # Add summary
            patch_votes = len([v for v in votes if v['vote_type'] == 'patch'])
            drop_votes = len([v for v in votes if v['vote_type'] == 'drop'])
            passed_votes = len([v for v in votes if v['result'] == 'passed'])
            failed_votes = len([v for v in votes if v['result'] == 'failed'])
            active_votes = len([v for v in votes if v['status'] == 'active'])
            
            summary = f"**Total Votes:** {len(votes)}\n"
            summary += f"🎖️ Patch: {patch_votes} | ❌ Drop: {drop_votes}\n"
            summary += f"✅ Passed: {passed_votes} | ❌ Failed: {failed_votes}\n"
            summary += f"⏳ Active: {active_votes}"
            
            embed.add_field(name="Summary", value=summary, inline=True)
            
            # Show individual votes
            for i, vote in enumerate(votes[:5]):  # Limit to 5 most recent
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
                    field_value += f" ({vote['result']})"
                    if vote['ended_at']:
                        ended_time = datetime.fromisoformat(vote['ended_at'])
                        field_value += f"\n**Ended:** <t:{int(ended_time.timestamp())}:F>"
                
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            if len(votes) > 5:
                embed.add_field(name="Note", value=f"Showing 5 most recent of {len(votes)} total votes.", inline=False)
        
        embed.set_footer(text="Use the back button to return to prospect profile")
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="📊 Generate Report", style=discord.ButtonStyle.primary, row=1)
    async def generate_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Generate a comprehensive prospect report"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get all data for the prospect
            tasks = await self.bot.db.get_prospect_tasks(self.prospect['id'])
            notes = await self.bot.db.get_prospect_notes(self.prospect['id'])
            votes = await self.bot.db.get_prospect_vote_history(self.prospect['id'])
            
            prospect_name = self.prospect.get('prospect_name', f"User {self.prospect['user_id']}")
            sponsor_name = self.prospect.get('sponsor_name', f"User {self.prospect['sponsor_id']}")
            
            # Generate comprehensive report
            report_lines = []
            report_lines.append(f"PROSPECT REPORT: {prospect_name.upper()}")
            report_lines.append("=" * 50)
            report_lines.append("")
            
            # Basic Info
            report_lines.append("BASIC INFORMATION:")
            report_lines.append(f"Name: {prospect_name}")
            report_lines.append(f"Sponsor: {sponsor_name}")
            report_lines.append(f"Status: {self.prospect['status'].title()}")
            report_lines.append(f"Strikes: {self.prospect.get('strikes', 0)}")
            
            start_date = datetime.fromisoformat(self.prospect['start_date'])
            report_lines.append(f"Start Date: {start_date.strftime('%Y-%m-%d %H:%M UTC')}")
            
            if self.prospect.get('end_date'):
                end_date = datetime.fromisoformat(self.prospect['end_date'])
                report_lines.append(f"End Date: {end_date.strftime('%Y-%m-%d %H:%M UTC')}")
                duration = (end_date - start_date).days
            else:
                report_lines.append("End Date: N/A (Active)")
                duration = (datetime.now() - start_date).days
            
            report_lines.append(f"Duration: {duration} days")
            report_lines.append("")
            
            # Tasks Summary
            report_lines.append("TASKS SUMMARY:")
            if tasks:
                completed = len([t for t in tasks if t['status'] == 'completed'])
                failed = len([t for t in tasks if t['status'] == 'failed'])
                pending = len([t for t in tasks if t['status'] == 'assigned'])
                
                report_lines.append(f"Total Tasks: {len(tasks)}")
                report_lines.append(f"Completed: {completed}")
                report_lines.append(f"Failed: {failed}")
                report_lines.append(f"Pending: {pending}")
                
                if len(tasks) > 0:
                    completion_rate = (completed / len(tasks)) * 100
                    report_lines.append(f"Completion Rate: {completion_rate:.1f}%")
            else:
                report_lines.append("No tasks assigned")
            report_lines.append("")
            
            # Notes Summary
            report_lines.append("NOTES & STRIKES SUMMARY:")
            if notes:
                strikes = len([n for n in notes if n['is_strike']])
                regular_notes = len(notes) - strikes
                report_lines.append(f"Total Notes: {len(notes)}")
                report_lines.append(f"Regular Notes: {regular_notes}")
                report_lines.append(f"Strikes: {strikes}")
            else:
                report_lines.append("No notes recorded")
            report_lines.append("")
            
            # Voting Summary
            report_lines.append("VOTING HISTORY:")
            if votes:
                patch_votes = len([v for v in votes if v['vote_type'] == 'patch'])
                drop_votes = len([v for v in votes if v['vote_type'] == 'drop'])
                passed_votes = len([v for v in votes if v['result'] == 'passed'])
                failed_votes = len([v for v in votes if v['result'] == 'failed'])
                
                report_lines.append(f"Total Votes: {len(votes)}")
                report_lines.append(f"Patch Votes: {patch_votes}")
                report_lines.append(f"Drop Votes: {drop_votes}")
                report_lines.append(f"Passed: {passed_votes}")
                report_lines.append(f"Failed: {failed_votes}")
            else:
                report_lines.append("No votes held")
            report_lines.append("")
            
            report_lines.append("=" * 50)
            report_lines.append(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
            report_lines.append(f"Generated by: {interaction.user.display_name}")
            
            # Create file
            report_content = "\n".join(report_lines)
            
            # Send as file
            import io
            file = io.StringIO(report_content)
            discord_file = discord.File(fp=io.BytesIO(report_content.encode()), filename=f"prospect_report_{prospect_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
            
            await interaction.followup.send(
                f"📊 **Prospect Report Generated**\n\nComprehensive report for **{prospect_name}** has been generated.",
                file=discord_file,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error generating prospect report: {e}")
            await interaction.followup.send(
                "❌ An error occurred while generating the report. Please try again.",
                ephemeral=True
            )
    
    @discord.ui.button(label="🔙 Back to List", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to prospect list"""
        # Get updated prospect list
        if self.view_type == "active":
            prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
            title = "🟢 Active Prospects"
            color = discord.Color.green()
        else:
            prospects = await self.bot.db.get_archived_prospects(interaction.guild.id)
            title = "📁 Archived Prospects"
            color = 0x808080
        
        view = ProspectSelectionView(self.bot, self.user_id, prospects, self.view_type)
        
        embed = discord.Embed(
            title=title,
            description=f"Select a prospect from the dropdown below to view detailed information.\n\n**Total {self.view_type} prospects:** {len(prospects)}",
            color=color,
            timestamp=datetime.now()
        )
        
        if not prospects:
            embed.add_field(
                name="No Prospects Found",
                value=f"There are currently no {self.view_type} prospects.",
                inline=False
            )
        
        embed.set_footer(text="Use the dropdown to select a prospect for details")
        
        await interaction.response.edit_message(embed=embed, view=view)


class ProspectDashboardView(discord.ui.View):
    """Main prospect dashboard menu"""
    
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    async def create_main_embed(self) -> discord.Embed:
        """Create main prospect dashboard embed"""
        # Get prospect statistics
        active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id if hasattr(self, 'interaction') else 1)
        archived_prospects = await self.bot.db.get_archived_prospects(interaction.guild.id if hasattr(self, 'interaction') else 1)
        
        embed = discord.Embed(
            title="🎯 Prospect Management Dashboard",
            description="**Comprehensive prospect tracking and management**\n\n" +
                       "Monitor prospect progress, tasks, notes, strikes, and voting history. " +
                       "Use the buttons below to access different views and reports.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Statistics
        total_active = len(active_prospects)
        total_archived = len(archived_prospects)
        high_risk = len([p for p in active_prospects if p.get('strike_count', 0) >= 3])
        
        # Quick stats
        stats = f"📊 **Quick Statistics:**\n"
        stats += f"🟢 Active Prospects: {total_active}\n"
        stats += f"📁 Archived Prospects: {total_archived}\n"
        stats += f"🚨 High Risk (3+ strikes): {high_risk}\n"
        
        embed.add_field(name="Overview", value=stats, inline=True)
        
        # Recent activity (mock data - could be enhanced with actual recent activity tracking)
        recent = f"📈 **Recent Activity:**\n"
        recent += f"• Task completions today\n"
        recent += f"• New prospects this week\n"
        recent += f"• Votes concluded recently\n"
        recent += f"• Patches and drops\n"
        
        embed.add_field(name="Activity", value=recent, inline=True)
        
        embed.set_footer(text="Select an option below to get started")
        
        return embed
    
    @discord.ui.button(label="🟢 View Active Prospects", style=discord.ButtonStyle.success)
    async def view_active_prospects(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View active prospects"""
        prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
        
        view = ProspectSelectionView(self.bot, self.user_id, prospects, "active")
        
        embed = discord.Embed(
            title="🟢 Active Prospects",
            description=f"Select a prospect from the dropdown below to view detailed information.\n\n**Total active prospects:** {len(prospects)}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        if not prospects:
            embed.add_field(
                name="No Active Prospects",
                value="There are currently no active prospects.",
                inline=False
            )
        
        embed.set_footer(text="Use the dropdown to select a prospect for details")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="📁 View Archived Prospects", style=discord.ButtonStyle.secondary)
    async def view_archived_prospects(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View archived prospects"""
        prospects = await self.bot.db.get_archived_prospects(interaction.guild.id)
        
        view = ProspectSelectionView(self.bot, self.user_id, prospects, "archived")
        
        embed = discord.Embed(
            title="📁 Archived Prospects",
            description=f"Select a prospect from the dropdown below to view detailed information.\n\n**Total archived prospects:** {len(prospects)}",
            color=0x808080,
            timestamp=datetime.now()
        )
        
        if not prospects:
            embed.add_field(
                name="No Archived Prospects",
                value="There are currently no archived prospects.",
                inline=False
            )
        
        embed.set_footer(text="Use the dropdown to select a prospect for details")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="⚠️ High Risk Prospects", style=discord.ButtonStyle.danger)
    async def view_high_risk_prospects(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View high risk prospects (3+ strikes)"""
        all_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
        high_risk_prospects = [p for p in all_prospects if p.get('strike_count', 0) >= 3]
        
        embed = discord.Embed(
            title="🚨 High Risk Prospects",
            description=f"Prospects with 3 or more strikes requiring attention.\n\n**Total high risk prospects:** {len(high_risk_prospects)}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        if not high_risk_prospects:
            embed.add_field(
                name="🎉 Great News!",
                value="No prospects currently have 3 or more strikes.",
                inline=False
            )
        else:
            # Show high risk prospects with details
            for i, prospect in enumerate(high_risk_prospects[:10]):
                prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                sponsor_name = prospect.get('sponsor_name', f"User {prospect['sponsor_id']}")
                strike_count = prospect.get('strike_count', 0)
                
                start_date = datetime.fromisoformat(prospect['start_date'])
                duration = (datetime.now() - start_date).days
                
                field_value = f"**Sponsor:** {sponsor_name}\n"
                field_value += f"**Strikes:** {strike_count}\n"
                field_value += f"**Duration:** {duration} days\n"
                
                # Add task performance if available
                if prospect.get('total_tasks', 0) > 0:
                    completed = prospect.get('completed_tasks', 0)
                    total = prospect.get('total_tasks', 0)
                    completion_rate = (completed / total) * 100
                    field_value += f"**Task Rate:** {completion_rate:.0f}% ({completed}/{total})"
                
                embed.add_field(
                    name=f"🚨 {prospect_name}",
                    value=field_value,
                    inline=True
                )
        
        # Create view with high risk prospects for selection
        if high_risk_prospects:
            view = ProspectSelectionView(self.bot, self.user_id, high_risk_prospects, "active")
        else:
            view = self  # Return to main menu
        
        embed.set_footer(text="High risk prospects may need additional guidance or review")
        
        await interaction.response.edit_message(embed=embed, view=view)


class ProspectDashboard(commands.Cog):
    """Dashboard integration for prospect management system"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("ProspectDashboard cog initialized")

    @app_commands.command(name="prospect-dashboard", description="Open the prospect management dashboard")
    async def prospect_dashboard(self, interaction: discord.Interaction):
        """Open the interactive prospect management dashboard"""
        if not await has_required_permissions(interaction, self.bot.db):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        try:
            view = ProspectDashboardView(self.bot, interaction.user.id)
            embed = await view.create_main_embed()
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error opening prospect dashboard: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred while opening the dashboard: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ProspectDashboard(bot))

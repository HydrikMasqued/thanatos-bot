"""
Event Attendance Export Utilities
Generate detailed attendance reports and CSV files for historical analysis
"""

import csv
import json
import io
from datetime import datetime
from typing import Dict, List, Optional, Any
import discord
import logging

logger = logging.getLogger(__name__)

class EventExportUtils:
    """Utility class for exporting event attendance data"""
    
    @staticmethod
    def create_attendance_csv(events_data: List[Dict], filename: str = None) -> io.StringIO:
        """Create CSV file with attendance data"""
        if not filename:
            filename = f"event_attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Create CSV in memory
        csv_buffer = io.StringIO()
        
        # Define CSV headers
        headers = [
            'Event ID',
            'Event Name', 
            'Event Date',
            'Category',
            'Created By',
            'Location',
            'Total Invited',
            'Total Responses',
            'Yes Responses',
            'No Responses', 
            'Maybe Responses',
            'Response Rate (%)',
            'Attendance Rate (%)',
            'Status',
            'Created At'
        ]
        
        writer = csv.writer(csv_buffer)
        writer.writerow(headers)
        
        # Write event data
        for event in events_data:
            # Calculate rates
            total_responses = (event.get('yes_count', 0) or 0) + (event.get('no_count', 0) or 0) + (event.get('maybe_count', 0) or 0)
            total_invited = event.get('total_invited', total_responses) or total_responses
            
            response_rate = (total_responses / total_invited * 100) if total_invited > 0 else 0
            attendance_rate = ((event.get('yes_count', 0) or 0) / total_responses * 100) if total_responses > 0 else 0
            
            row = [
                event.get('id', ''),
                event.get('event_name', ''),
                event.get('event_date', ''),
                event.get('category', ''),
                event.get('created_by_name', ''),
                event.get('location', ''),
                total_invited,
                total_responses,
                event.get('yes_count', 0) or 0,
                event.get('no_count', 0) or 0,
                event.get('maybe_count', 0) or 0,
                f"{response_rate:.1f}",
                f"{attendance_rate:.1f}",
                'Active' if event.get('is_active', False) else 'Inactive',
                event.get('created_at', '')
            ]
            writer.writerow(row)
        
        csv_buffer.seek(0)
        return csv_buffer
    
    @staticmethod
    def create_detailed_rsvp_csv(event: Dict, rsvps: Dict[str, List[Dict]], filename: str = None) -> io.StringIO:
        """Create detailed CSV with individual RSVP responses"""
        if not filename:
            event_name_safe = event.get('event_name', 'Event').replace(' ', '_').replace('/', '_')
            filename = f"{event_name_safe}_rsvps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        csv_buffer = io.StringIO()
        
        headers = [
            'User ID',
            'Discord Name',
            'Display Name', 
            'Response',
            'Response Time',
            'Invited At',
            'Rank',
            'Notes',
            'Invitation Method'
        ]
        
        writer = csv.writer(csv_buffer)
        writer.writerow(headers)
        
        # Combine all RSVP responses
        all_rsvps = []
        for response_type, response_list in rsvps.items():
            for rsvp in response_list:
                rsvp['response_type'] = response_type
                all_rsvps.append(rsvp)
        
        # Sort by response time
        all_rsvps.sort(key=lambda x: x.get('response_time', ''))
        
        # Write RSVP data
        for rsvp in all_rsvps:
            row = [
                rsvp.get('user_id', ''),
                rsvp.get('discord_name', ''),
                rsvp.get('discord_name', ''),  # Using same for now, could get display name
                rsvp.get('response', '').title(),
                rsvp.get('response_time', ''),
                rsvp.get('invited_at', ''),
                rsvp.get('rank', ''),
                rsvp.get('notes', ''),
                rsvp.get('invitation_method', '')
            ]
            writer.writerow(row)
        
        csv_buffer.seek(0)
        return csv_buffer
    
    @staticmethod
    def create_analytics_json(analytics: Dict) -> io.StringIO:
        """Create JSON file with analytics data"""
        json_buffer = io.StringIO()
        
        # Add metadata
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_type': 'event_analytics',
            'data': analytics
        }
        
        json.dump(export_data, json_buffer, indent=2, default=str)
        json_buffer.seek(0)
        return json_buffer
    
    @staticmethod
    def create_summary_table_text(events_data: List[Dict]) -> str:
        """Create a formatted text table for discord message"""
        if not events_data:
            return "No events found."
        
        # Create table
        table_lines = []
        
        # Header
        table_lines.append("📊 **EVENT ATTENDANCE SUMMARY**")
        table_lines.append("=" * 50)
        table_lines.append("")
        
        # Stats summary
        total_events = len(events_data)
        total_responses = sum((e.get('yes_count', 0) or 0) + (e.get('no_count', 0) or 0) + (e.get('maybe_count', 0) or 0) for e in events_data)
        total_yes = sum(e.get('yes_count', 0) or 0 for e in events_data)
        
        avg_attendance = (total_yes / total_responses * 100) if total_responses > 0 else 0
        
        table_lines.extend([
            f"📅 **Total Events:** {total_events}",
            f"📋 **Total Responses:** {total_responses:,}",
            f"✅ **Total Yes Responses:** {total_yes:,}",
            f"🎯 **Average Attendance:** {avg_attendance:.1f}%",
            "",
            "**TOP PERFORMING EVENTS:**",
            "-" * 30
        ])
        
        # Sort by attendance rate
        sorted_events = sorted(events_data, key=lambda x: (
            (x.get('yes_count', 0) or 0) / max((x.get('yes_count', 0) or 0) + (x.get('no_count', 0) or 0) + (x.get('maybe_count', 0) or 0), 1) * 100
        ), reverse=True)
        
        # Top 10 events
        for i, event in enumerate(sorted_events[:10], 1):
            total_resp = (event.get('yes_count', 0) or 0) + (event.get('no_count', 0) or 0) + (event.get('maybe_count', 0) or 0)
            yes_count = event.get('yes_count', 0) or 0
            attendance_rate = (yes_count / total_resp * 100) if total_resp > 0 else 0
            
            event_name = event.get('event_name', 'Unknown Event')
            if len(event_name) > 25:
                event_name = event_name[:22] + "..."
            
            table_lines.append(f"{i:2d}. {event_name:<25} | {yes_count:3d}/{total_resp:3d} ({attendance_rate:5.1f}%)")
        
        return "\n".join(table_lines)
    
    @staticmethod
    async def send_csv_file(interaction: discord.Interaction, csv_buffer: io.StringIO, filename: str, description: str = "Event attendance data"):
        """Send CSV file as Discord attachment"""
        try:
            # Convert StringIO to bytes
            csv_bytes = csv_buffer.getvalue().encode('utf-8')
            file = discord.File(io.BytesIO(csv_bytes), filename=filename)
            
            embed = discord.Embed(
                title="📊 Attendance Data Export",
                description=f"**{description}**\n\nFile: `{filename}`\nGenerated: <t:{int(datetime.now().timestamp())}:F>",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📁 File Details",
                value=f"Format: CSV\nSize: {len(csv_bytes)} bytes\nCompatible with Excel, Google Sheets",
                inline=False
            )
            
            embed.set_footer(text="Event Attendance Export System")
            
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            logger.error(f"Error sending CSV file: {e}")
            await interaction.followup.send(
                "❌ Error generating export file. Please try again.",
                ephemeral=True
            )
    
    @staticmethod
    async def send_json_file(interaction: discord.Interaction, json_buffer: io.StringIO, filename: str, description: str = "Event analytics data"):
        """Send JSON file as Discord attachment"""
        try:
            # Convert StringIO to bytes  
            json_bytes = json_buffer.getvalue().encode('utf-8')
            file = discord.File(io.BytesIO(json_bytes), filename=filename)
            
            embed = discord.Embed(
                title="📈 Analytics Data Export", 
                description=f"**{description}**\n\nFile: `{filename}`\nGenerated: <t:{int(datetime.now().timestamp())}:F>",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📁 File Details",
                value=f"Format: JSON\nSize: {len(json_bytes)} bytes\nMachine-readable format for analysis",
                inline=False
            )
            
            embed.set_footer(text="Event Analytics Export System")
            
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            logger.error(f"Error sending JSON file: {e}")
            await interaction.followup.send(
                "❌ Error generating export file. Please try again.",
                ephemeral=True
            )
    
    @staticmethod
    def format_attendance_summary(analytics: Dict, days: int) -> discord.Embed:
        """Create a formatted embed with attendance summary"""
        embed = discord.Embed(
            title=f"📊 Attendance Summary ({days} days)",
            description="Quick overview of event attendance metrics",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        # Key metrics
        embed.add_field(
            name="📈 Overview",
            value=f"📅 Events: {analytics['total_events']}\n"
                  f"📬 Invitations: {analytics['total_invitations']:,}\n"
                  f"📋 Responses: {analytics['total_responses']:,}",
            inline=True
        )
        
        # Response breakdown
        breakdown = analytics['response_breakdown']
        embed.add_field(
            name="📊 Responses",
            value=f"✅ Yes: {breakdown['yes']}\n"
                  f"❌ No: {breakdown['no']}\n" 
                  f"🤔 Maybe: {breakdown['maybe']}",
            inline=True
        )
        
        # Rates
        embed.add_field(
            name="📈 Performance",
            value=f"📬 Response Rate: {analytics['response_rate']}%\n"
                  f"🎯 Attendance Rate: {analytics['attendance_rate']}%",
            inline=True
        )
        
        # Top category
        if analytics['category_stats']:
            top_category = max(analytics['category_stats'].items(), key=lambda x: x[1]['count'])
            embed.add_field(
                name="🏆 Top Category",
                value=f"**{top_category[0]}**\n{top_category[1]['count']} events",
                inline=True
            )
        
        # Trend analysis
        attendance_rate = analytics['attendance_rate']
        if attendance_rate >= 75:
            trend = "🟢 Excellent"
        elif attendance_rate >= 50:
            trend = "🟡 Good"
        else:
            trend = "🔴 Needs Improvement"
            
        embed.add_field(
            name="📈 Trend",
            value=f"{trend}\n{attendance_rate:.1f}% attendance",
            inline=True
        )
        
        embed.set_footer(text="Use export commands for detailed data")
        
        return embed

class EventNotificationUtils:
    """Utilities for event notifications and reminders"""
    
    @staticmethod
    async def notify_rsvp_change(bot, event_data: Dict, user: discord.User, old_response: str, new_response: str):
        """Notify event creator of RSVP changes"""
        try:
            creator_id = event_data.get('created_by_id')
            if not creator_id:
                return
            
            creator = bot.get_user(creator_id)
            if not creator:
                creator = await bot.fetch_user(creator_id)
            
            if creator and creator.id != user.id:  # Don't notify creator of their own changes
                embed = discord.Embed(
                    title="🔄 RSVP Changed",
                    description=f"**{user.display_name}** updated their response to your event!",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(name="📅 Event", value=event_data['event_name'], inline=True)
                embed.add_field(name="👤 User", value=user.display_name, inline=True)
                embed.add_field(name="🔄 Change", value=f"{old_response.title()} → {new_response.title()}", inline=True)
                
                embed.set_thumbnail(url=user.display_avatar.url)
                embed.set_footer(text=f"Event ID: {event_data['id']}")
                
                await creator.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error sending RSVP change notification: {e}")
    
    @staticmethod
    async def send_event_summary_to_creator(bot, event_data: Dict, rsvps: Dict[str, List[Dict]]):
        """Send event summary to creator after event ends"""
        try:
            creator_id = event_data.get('created_by_id')
            if not creator_id:
                return
            
            creator = bot.get_user(creator_id)
            if not creator:
                creator = await bot.fetch_user(creator_id)
            
            if creator:
                yes_count = len(rsvps.get('yes', []))
                no_count = len(rsvps.get('no', []))
                maybe_count = len(rsvps.get('maybe', []))
                total_responses = yes_count + no_count + maybe_count
                
                embed = discord.Embed(
                    title="📊 Event Summary",
                    description=f"Final attendance report for **{event_data['event_name']}**",
                    color=discord.Color.purple(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(name="📅 Event Date", value=event_data['event_date'], inline=True)
                embed.add_field(name="📋 Category", value=event_data['category'], inline=True)
                embed.add_field(name="🆔 Event ID", value=str(event_data['id']), inline=True)
                
                # Attendance summary
                if total_responses > 0:
                    attendance_rate = (yes_count / total_responses) * 100
                    embed.add_field(
                        name="📈 Final Attendance",
                        value=f"✅ Yes: {yes_count}\n❌ No: {no_count}\n🤔 Maybe: {maybe_count}\n🎯 Rate: {attendance_rate:.1f}%",
                        inline=False
                    )
                else:
                    embed.add_field(name="📈 Final Attendance", value="No responses received", inline=False)
                
                # Who attended
                if rsvps.get('yes'):
                    attendees = [rsvp.get('discord_name', f"User {rsvp['user_id']}") for rsvp in rsvps['yes'][:10]]
                    if len(rsvps['yes']) > 10:
                        attendees.append(f"... and {len(rsvps['yes']) - 10} more")
                    
                    embed.add_field(
                        name="👥 Attendees",
                        value="\n".join([f"• {name}" for name in attendees]),
                        inline=False
                    )
                
                embed.set_footer(text="Thank you for using the Event Management System!")
                
                await creator.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error sending event summary: {e}")

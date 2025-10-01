import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from utils.advanced_timestamp_parser import AdvancedTimestampParser
from utils.smart_time_formatter import SmartTimeFormatter

logger = logging.getLogger(__name__)

class TimeConverter(commands.Cog):
    """Simple time conversion utilities for Discord timestamps"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="time", description="Convert time to Discord timestamp (leave empty for current time)")
    @app_commands.describe(
        time_input="Time to convert (leave empty for current time)",
        format_type="Display format for the timestamp (optional)"
    )
    @app_commands.choices(format_type=[
        app_commands.Choice(name="Default (Date & Time)", value="F"),
        app_commands.Choice(name="Short Date & Time", value="f"),
        app_commands.Choice(name="Long Date", value="D"),
        app_commands.Choice(name="Short Date", value="d"),
        app_commands.Choice(name="Long Time", value="T"),
        app_commands.Choice(name="Short Time", value="t"),
        app_commands.Choice(name="Relative (in X minutes)", value="R"),
    ])
    async def convert_time(self, interaction: discord.Interaction, time_input: str = None, format_type: str = "F"):
        """Convert natural language time to Discord timestamp or show current time"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # If no time input provided, use current time
            if not time_input:
                parsed_datetime = datetime.now()
                timestamp_result = {'is_valid': True, 'datetime': parsed_datetime, 'confidence': 1.0, 'source_format': 'Current time'}
            else:
                # Parse the time input
                timestamp_result = AdvancedTimestampParser.parse_any_timestamp(time_input, context="general")
            
            if not timestamp_result or not timestamp_result['is_valid']:
                # Create helpful error message
                error_msg = f"❌ Could not parse time: **{time_input}**"
                if timestamp_result and timestamp_result.get('error'):
                    error_msg += f"\nError: {timestamp_result['error']}"
                
                error_msg += "\n\n🕐 **Supported formats:**\n"
                error_msg += "• **Natural:** 'tomorrow 8pm', 'next friday 7:30pm', 'january 15 at 8pm'\n"
                error_msg += "• **Relative:** 'in 2 hours', '3 days from now', 'today in 4 hours'\n"
                error_msg += "• **Standard:** '2024-01-15 20:00', '1/15/2024 8:00 PM'\n"
                error_msg += "• **Discord:** '<t:1704670800:F>' (from Discord message)"
                
                await interaction.followup.send(error_msg, ephemeral=True)
                return
            
            parsed_datetime = timestamp_result['datetime']
            
            # Generate Discord timestamp
            timestamp = int(parsed_datetime.timestamp())
            discord_timestamp = f"<t:{timestamp}:{format_type}>"
            
            # Create response embed
            title = "⏰ Current Timestamp" if not time_input else "⏰ Time Conversion Result"
            description = "**Current time**" if not time_input else f"**Input:** {time_input}"
            
            embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            # Show the parsed time in multiple formats
            embed.add_field(
                name="📅 Parsed Time",
                value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)",
                inline=False
            )
            
            # Show the Discord timestamp code
            embed.add_field(
                name="💬 Discord Timestamp Code",
                value=f"`{discord_timestamp}`\n**Copy this to use in Discord!**",
                inline=False
            )
            
            # Show preview of selected format
            embed.add_field(
                name=f"👁️ Preview ({self._get_format_name(format_type)})",
                value=discord_timestamp,
                inline=False
            )
            
            # Show parsing confidence if available
            if timestamp_result.get('confidence') and timestamp_result.get('source_format'):
                confidence_emoji = "🎯" if timestamp_result['confidence'] >= 0.9 else "✅" if timestamp_result['confidence'] >= 0.7 else "⚠️"
                embed.add_field(
                    name="📊 Parse Information",
                    value=f"{confidence_emoji} **Confidence:** {timestamp_result['confidence']:.0%}\n"
                          f"**Format:** {timestamp_result['source_format']}",
                    inline=True
                )
            
            # Show all format options
            all_formats = self._generate_all_formats(timestamp)
            embed.add_field(
                name="🎨 All Format Options",
                value=all_formats,
                inline=False
            )
            
            embed.set_footer(text="Copy any timestamp code above and paste in Discord to use it!")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"User {interaction.user.id} converted time: '{time_input}' -> {timestamp}")
            
        except Exception as e:
            logger.error(f"Error in time conversion command: {e}")
            await interaction.followup.send(
                "❌ An unexpected error occurred while converting the time. Please try again.",
                ephemeral=True
            )
    
    def _get_format_name(self, format_type: str) -> str:
        """Get human-readable format name"""
        format_names = {
            "F": "Full Date & Time",
            "f": "Short Date & Time", 
            "D": "Long Date",
            "d": "Short Date",
            "T": "Long Time",
            "t": "Short Time",
            "R": "Relative Time"
        }
        return format_names.get(format_type, "Default")
    
    def _generate_all_formats(self, timestamp: int) -> str:
        """Generate examples of all Discord timestamp formats"""
        formats = {
            "F": "Full Date & Time",
            "f": "Short Date & Time",
            "D": "Long Date", 
            "d": "Short Date",
            "T": "Long Time",
            "t": "Short Time",
            "R": "Relative Time"
        }
        
        result = []
        for format_code, name in formats.items():
            discord_code = f"`<t:{timestamp}:{format_code}>`"
            preview = f"<t:{timestamp}:{format_code}>"
            result.append(f"**{name}:** {discord_code} → {preview}")
        
        return "\n".join(result)
    

async def setup(bot):
    await bot.add_cog(TimeConverter(bot))
"""
Timestamp Demo Cog - Demonstrates universal timestamp parsing
Shows how any cog can easily use the natural language parsing system.
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional

# Import the universal timestamp utilities (multiple ways to import)
from utils.universal_timestamp import (
    UniversalTimestamp,
    BotTimeUtils,
    parse_time,
    format_discord, 
    is_valid,
    get_help,
    parse_event,
    parse_due,
    quick_parse,
    validate_time
)

class TimestampDemo(commands.Cog):
    """
    Demonstration cog showing how to use universal timestamp parsing
    throughout the bot with simple imports and method calls.
    """
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="parse-time", description="Demo: Parse any natural language time expression")
    @app_commands.describe(time_input="Natural language time (e.g., 'tomorrow 8pm', 'next week anytime', 'today')")
    async def parse_time_demo(self, interaction: discord.Interaction, time_input: str):
        """Demonstrate parsing any time expression."""
        
        # Multiple ways to parse - choose what works best for your use case
        
        # Method 1: Simple parsing (just get datetime)
        parsed_dt = parse_time(time_input)
        
        # Method 2: Full parsing with details
        full_result = UniversalTimestamp.parse(time_input)
        
        # Method 3: Context-specific parsing
        event_dt = parse_event(time_input)
        due_dt = parse_due(time_input)
        
        embed = discord.Embed(
            title="🕐 Universal Time Parser Demo",
            description=f"**Input:** `{time_input}`",
            color=0x00D4FF
        )
        
        if parsed_dt:
            # Show all the different timestamp formats
            formats = UniversalTimestamp.get_all_formats(parsed_dt)
            
            embed.add_field(
                name="✅ Parsing Success",
                value=f"**Datetime:** {parsed_dt.strftime('%B %d, %Y at %I:%M %p')}\n"
                      f"**Discord Timestamp:** {formats['full_long']}\n"
                      f"**Relative:** {formats['relative']}",
                inline=False
            )
            
            if full_result:
                confidence = full_result.get('confidence', 0)
                source_format = full_result.get('source_format', 'unknown')
                
                confidence_emoji = "🎯" if confidence >= 0.9 else "✅" if confidence >= 0.7 else "⚠️"
                
                embed.add_field(
                    name="📊 Parsing Details", 
                    value=f"{confidence_emoji} **Confidence:** {confidence:.0%}\n"
                          f"🔍 **Source Format:** {source_format}\n"
                          f"🎯 **Context Used:** General",
                    inline=True
                )
            
            # Show different format options
            embed.add_field(
                name="🎨 All Discord Formats",
                value=f"**Full:** {formats['full_long']}\n"
                      f"**Date:** {formats['date_long']}\n" 
                      f"**Time:** {formats['time_short']}\n"
                      f"**Relative:** {formats['relative']}",
                inline=True
            )
            
            # Show context-specific results if different
            context_results = []
            if event_dt and event_dt != parsed_dt:
                context_results.append(f"**Event context:** {format_discord(event_dt, 'F')}")
            if due_dt and due_dt != parsed_dt:
                context_results.append(f"**Dues context:** {format_discord(due_dt, 'F')}")
                
            if context_results:
                embed.add_field(
                    name="🎯 Context-Specific Results",
                    value="\n".join(context_results),
                    inline=False
                )
                
        else:
            embed.add_field(
                name="❌ Parsing Failed",
                value=f"Could not parse: `{time_input}`\n\n{get_help('general')[:500]}...",
                inline=False
            )
        
        embed.set_footer(text="Universal Timestamp Parser • Supports 60+ time formats")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="time-examples", description="Show examples of supported time formats")
    async def time_examples(self, interaction: discord.Interaction):
        """Show comprehensive examples of supported formats."""
        
        examples = UniversalTimestamp.get_examples()
        
        embed = discord.Embed(
            title="🕐 Supported Time Formats",
            description="The bot understands natural language time expressions!",
            color=0x00FF88
        )
        
        # Show examples by category
        embed.add_field(
            name="📅 Flexible Basic",
            value="• " + "\n• ".join(examples['flexible_basic'][:6]),
            inline=True
        )
        
        embed.add_field(
            name="📆 Weekday Flexible", 
            value="• " + "\n• ".join(examples['weekday_flexible']),
            inline=True
        )
        
        embed.add_field(
            name="⏰ Time of Day",
            value="• " + "\n• ".join(examples['time_of_day']),
            inline=True
        )
        
        embed.add_field(
            name="🚀 Relative Times",
            value="• " + "\n• ".join(examples['relative']),
            inline=True
        )
        
        embed.add_field(
            name="🎯 Specific Times",
            value="• " + "\n• ".join(examples['specific_with_time']),
            inline=True
        )
        
        embed.add_field(
            name="📋 Standard Formats",
            value="• " + "\n• ".join(examples['standard_formats']),
            inline=True
        )
        
        embed.add_field(
            name="✨ Live Examples",
            value=f"• `today` → {format_discord(parse_time('today'), 'F') if parse_time('today') else 'Error'}\n"
                  f"• `tomorrow 8pm` → {format_discord(parse_time('tomorrow 8pm'), 'F') if parse_time('tomorrow 8pm') else 'Error'}\n"
                  f"• `next week` → {format_discord(parse_time('next week'), 'F') if parse_time('next week') else 'Error'}\n"
                  f"• `friday anytime` → {format_discord(parse_time('friday anytime'), 'F') if parse_time('friday anytime') else 'Error'}",
            inline=False
        )
        
        embed.set_footer(text="Try `/parse-time` with any of these examples!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="validate-time", description="Check if a time string is valid")
    @app_commands.describe(time_input="Time string to validate")
    async def validate_time_demo(self, interaction: discord.Interaction, time_input: str):
        """Demonstrate time validation."""
        
        # Use the validation utility
        is_valid_result, parsed_dt, error_msg = validate_time(time_input)
        
        embed = discord.Embed(
            title="✅ Time Validation Demo",
            description=f"**Input:** `{time_input}`",
            color=0x00FF88 if is_valid_result else 0xFF4444
        )
        
        if is_valid_result:
            embed.add_field(
                name="✅ Valid Time",
                value=f"**Parsed as:** {format_discord(parsed_dt, 'F')}\n"
                      f"**Relative:** {format_discord(parsed_dt, 'R')}\n"
                      f"**Quick check:** {is_valid(time_input)} ✓",
                inline=False
            )
        else:
            embed.add_field(
                name="❌ Invalid Time",
                value=f"**Error:** {error_msg}\n"
                      f"**Quick check:** {is_valid(time_input)} ✗\n\n"
                      f"Try formats like:\n"
                      f"• `tomorrow 8pm`\n"
                      f"• `next friday anytime`\n"
                      f"• `today`\n"
                      f"• `in 2 hours`",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="quick-event", description="Demo: Quick event creation with natural time")
    @app_commands.describe(
        name="Event name",
        time_input="When (e.g., 'tomorrow 8pm', 'next friday anytime', 'today')"
    )
    async def quick_event_demo(self, interaction: discord.Interaction, name: str, time_input: str):
        """Demonstrate creating an event with natural language time."""
        
        # Parse the time for an event context
        event_time = parse_event(time_input)
        
        if not event_time:
            embed = discord.Embed(
                title="❌ Invalid Time",
                description=f"Could not parse: `{time_input}`\n\n{get_help('event')[:300]}...",
                color=0xFF4444
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎉 Quick Event Created (Demo)",
            description=f"**{name}** would be created successfully!",
            color=0x00FF88
        )
        
        # Show how it would display
        embed.add_field(
            name="📅 Event Time",
            value=BotTimeUtils.format_event_display(event_time),
            inline=False
        )
        
        embed.add_field(
            name="🔍 Parsing Info",
            value=f"**Input:** `{time_input}`\n"
                  f"**Parsed as:** {event_time.strftime('%B %d, %Y at %I:%M %p')}\n"
                  f"**Context:** Event",
            inline=False
        )
        
        embed.add_field(
            name="💡 Integration Example",
            value="```python\n"
                  "# How easy it is in your cogs:\n"
                  "from utils.universal_timestamp import parse_event\n\n"
                  f"event_time = parse_event('{time_input}')\n"
                  "if event_time:\n"
                  "    # Create event with parsed time\n"
                  "    await create_event(name, event_time)\n"
                  "```",
            inline=False
        )
        
        embed.set_footer(text="This is a demo - no actual event was created")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TimestampDemo(bot))

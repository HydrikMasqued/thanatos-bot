"""
Shared utilities for contribution and audit systems.
Contains common functions used across contribution and audit log cogs.
"""

import discord
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class ContributionAuditHelpers:
    """Shared utilities for contribution and audit logging systems"""
    
    @staticmethod
    def get_user_display_name(bot, user_id: int, max_length: int = 20) -> str:
        """
        Get a user's display name with fallback and optional truncation.
        
        Args:
            bot: The bot instance
            user_id: Discord user ID
            max_length: Maximum length for display name (0 for no truncation)
            
        Returns:
            User's display name or fallback identifier
        """
        if not user_id:
            return "Unknown"
            
        try:
            user_obj = bot.get_user(user_id)
            if user_obj:
                display_name = user_obj.display_name
                if max_length > 0:
                    display_name = display_name[:max_length]
                return display_name
            else:
                # Fallback to user ID
                fallback = f"User_{str(user_id)[-6:]}"
                return fallback[:max_length] if max_length > 0 else fallback
        except Exception:
            fallback = f"User_{str(user_id)[-6:]}"
            return fallback[:max_length] if max_length > 0 else fallback
    
    @staticmethod
    def format_datetime_safe(datetime_str: str, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """
        Safely format a datetime string with fallback.
        
        Args:
            datetime_str: ISO format datetime string
            format_str: Desired output format
            
        Returns:
            Formatted datetime string or "Unknown"
        """
        if not datetime_str:
            return "Unknown"
            
        try:
            # Handle various datetime formats
            cleaned_str = datetime_str.replace('T', ' ').replace('Z', '')
            dt = datetime.fromisoformat(cleaned_str)
            return dt.strftime(format_str)
        except Exception:
            return "Unknown"
    
    @staticmethod
    def get_date_str(datetime_str: str) -> str:
        """Get date portion of datetime string"""
        return ContributionAuditHelpers.format_datetime_safe(datetime_str, "%Y-%m-%d")
    
    @staticmethod
    def get_time_str(datetime_str: str) -> str:
        """Get time portion of datetime string"""
        return ContributionAuditHelpers.format_datetime_safe(datetime_str, "%H:%M:%S")
    
    @staticmethod
    async def check_officer_permissions(interaction: discord.Interaction, bot) -> bool:
        """
        Check if user has officer permissions.
        
        Args:
            interaction: Discord interaction
            bot: Bot instance with database access
            
        Returns:
            True if user has officer permissions
        """
        # Check bot owner permissions first (total control)
        if hasattr(bot, 'is_bot_owner') and bot.is_bot_owner(interaction.user.id):
            return True
            
        # Check admin permissions
        if interaction.user.guild_permissions.administrator:
            return True
            
        # Check officer role
        try:
            config = await bot.db.get_server_config(interaction.guild.id)
            if not config or not config.get('officer_role_id'):
                return False
            
            officer_role = interaction.guild.get_role(config['officer_role_id'])
            if not officer_role:
                return False
                
            return officer_role in interaction.user.roles
        except Exception as e:
            logger.error(f"Error checking officer permissions: {e}")
            return False
    
    @staticmethod
    async def send_permission_error(interaction: discord.Interaction, message: str = None):
        """Send a standard permission denied message"""
        default_message = "❌ You need administrator or officer permissions to use this command."
        await interaction.response.send_message(
            message or default_message, 
            ephemeral=True
        )
    
    @staticmethod
    def format_quantity_change_description(event: Dict[str, Any]) -> str:
        """
        Format a description for quantity changes.
        
        Args:
            event: Event dictionary with quantity data
            
        Returns:
            Formatted change description
        """
        if event.get('quantity_delta') is None:
            return "N/A"
            
        delta = event['quantity_delta']
        if delta > 0:
            return f"+{delta} Added"
        elif delta < 0:
            return f"{delta} Removed"
        else:
            return "No Change"
    
    @staticmethod
    def format_notes_reason(event: Dict[str, Any], max_length: int = 50) -> str:
        """
        Format notes/reason field for display.
        
        Args:
            event: Event dictionary
            max_length: Maximum length for output
            
        Returns:
            Formatted notes/reason string
        """
        if event.get('reason'):
            text = f"REASON: {event['reason']}"
        elif event.get('notes'):
            text = f"NOTES: {event['notes']}"
        else:
            text = "No additional details"
            
        return text[:max_length] if max_length > 0 else text
    
    @staticmethod
    def calculate_outstanding_quantities(events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calculate outstanding quantities for all items based on events.
        
        Args:
            events: List of audit events
            
        Returns:
            Dictionary mapping item keys to outstanding quantities
        """
        quantities = {}
        
        # Process events chronologically
        sorted_events = sorted(events, key=lambda x: x.get('occurred_at', ''))
        
        for event in sorted_events:
            item_name = event.get('item_name', 'Unknown')
            category = event.get('category', 'Misc Locker')
            item_key = f"{category}::{item_name}"
            
            if item_key not in quantities:
                quantities[item_key] = 0
            
            # Apply quantity changes
            if event.get('quantity_delta') is not None:
                quantities[item_key] += event['quantity_delta']
        
        return quantities
    
    @staticmethod 
    def calculate_contribution_totals(events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calculate total contributions by item, counting only contribution events.
        
        Args:
            events: List of audit events
            
        Returns:
            Dictionary mapping item keys to total contribution quantities
        """
        totals = {}
        
        for event in events:
            # Only count contribution events
            if event.get('event_type') != 'contribution':
                continue
                
            item_name = event.get('item_name', 'Unknown')
            category = event.get('category', 'Misc Locker')
            item_key = f"{category}::{item_name}"
            
            if item_key not in totals:
                totals[item_key] = 0
            
            # Add contribution quantity
            if event.get('quantity_delta') is not None:
                totals[item_key] += event['quantity_delta']
        
        return totals
    
    @staticmethod 
    def calculate_inventory_levels(events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calculate current inventory levels, using the most recent quantity_change events.
        
        Args:
            events: List of audit events
            
        Returns:
            Dictionary mapping item keys to current inventory quantities
        """
        inventory = {}
        
        # Process events chronologically to get the latest quantity for each item
        sorted_events = sorted(events, key=lambda x: x.get('occurred_at', ''))
        
        for event in sorted_events:
            if event.get('event_type') != 'quantity_change':
                continue
                
            item_name = event.get('item_name', 'Unknown')
            category = event.get('category', 'Misc Locker')
            item_key = f"{category}::{item_name}"
            
            # Use the new_quantity from the most recent quantity change
            if event.get('new_quantity') is not None:
                inventory[item_key] = event['new_quantity']
        
        return inventory
    
    @staticmethod
    async def get_leadership_notification_channel(bot, guild_id: int) -> Optional[discord.TextChannel]:
        """
        Get the leadership notification channel for a guild.
        
        Args:
            bot: Bot instance
            guild_id: Discord guild ID
            
        Returns:
            Leadership channel or None
        """
        try:
            config = await bot.db.get_server_config(guild_id)
            if not config:
                return None
                
            guild = bot.get_guild(guild_id)
            if not guild:
                return None
            
            # Try leadership channel first, then notification channel
            channel_id = config.get('leadership_channel_id') or config.get('notification_channel_id')
            if not channel_id:
                return None
                
            return guild.get_channel(channel_id)
        except Exception as e:
            logger.error(f"Error getting leadership channel for guild {guild_id}: {e}")
            return None
    
    @staticmethod
    async def get_tailgunner_role(guild: discord.Guild) -> Optional[discord.Role]:
        """Get the Tailgunner role for notifications"""
        try:
            for role in guild.roles:
                if role.name.lower() == "tailgunner":
                    return role
            return None
        except Exception:
            return None
    
    @staticmethod
    def create_contribution_embed(contributor: discord.Member, category: str, 
                                item_name: str, quantity: int, 
                                contribution_id: Optional[int] = None,
                                forum_thread: Optional[discord.Thread] = None) -> discord.Embed:
        """
        Create a standard contribution embed.
        
        Args:
            contributor: The user who made the contribution
            category: Contribution category
            item_name: Name of the contributed item
            quantity: Quantity contributed
            contribution_id: Database ID of contribution
            forum_thread: Associated forum thread if any
            
        Returns:
            Formatted Discord embed
        """
        embed = discord.Embed(
            title="✅ Contribution Recorded",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Category", value=category, inline=True)
        embed.add_field(name="Item", value=item_name, inline=True)
        embed.add_field(name="Quantity", value=str(quantity), inline=True)
        
        if forum_thread:
            embed.add_field(
                name="Forum Thread", 
                value=f"[View Thread]({forum_thread.jump_url})", 
                inline=False
            )
        
        footer_text = "Your contribution has been recorded and leadership has been notified."
        if forum_thread:
            footer_text += " Posted to forum thread."
        embed.set_footer(text=footer_text)
        
        return embed
    
    @staticmethod
    def create_quantity_change_embed(user: discord.Member, item_name: str, category: str,
                                   old_qty: int, new_qty: int, operation: str,
                                   reason: str, notes: str = None,
                                   change_id: Optional[int] = None) -> discord.Embed:
        """
        Create a standard quantity change embed.
        
        Args:
            user: User who made the change
            item_name: Name of the item
            category: Item category
            old_qty: Previous quantity
            new_qty: New quantity
            operation: Type of operation (set, add, remove)
            reason: Reason for change
            notes: Additional notes
            change_id: Database change ID
            
        Returns:
            Formatted Discord embed
        """
        difference = new_qty - old_qty
        operation_emoji = {"set": "🔄", "add": "➕", "remove": "➖"}
        
        embed = discord.Embed(
            title=f"{operation_emoji.get(operation, '✅')} Quantity {operation.title()} Successfully",
            color=discord.Color.green() if difference >= 0 else discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="Item Details",
            value=f"**Item:** {item_name}\n"
                  f"**Category:** {category}\n"
                  f"**Previous Quantity:** {old_qty}\n"
                  f"**New Quantity:** {new_qty}\n"
                  f"**Net Change:** {'+' if difference >= 0 else ''}{difference}",
            inline=False
        )
        
        embed.add_field(
            name="Operation Details",
            value=f"**Type:** {operation.title()}\n"
                  f"**Reason:** {reason}",
            inline=False
        )
        
        if notes:
            embed.add_field(
                name="Additional Notes",
                value=notes,
                inline=False
            )
        
        if change_id:
            embed.add_field(
                name="Change Log",
                value=f"**Change ID:** {change_id}\n"
                      f"**Modified by:** {user.mention}\n"
                      f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
                inline=False
            )
        
        return embed
    
    @staticmethod
    def group_events_by_category(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group events by category"""
        categories = {}
        for event in events:
            category = event.get('category', 'Misc Locker')
            if category not in categories:
                categories[category] = []
            categories[category].append(event)
        return categories
    
    @staticmethod
    def get_category_order() -> List[str]:
        """Get the standard category ordering"""
        return ['Weapons Locker', 'Drug Locker', 'Misc Locker']
    
    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """Safely truncate text with suffix"""
        if not text or len(text) <= max_length:
            return text or ""
        return text[:max_length - len(suffix)] + suffix

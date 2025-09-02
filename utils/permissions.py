import discord
from discord.ext import commands
import logging
from typing import List, Union, Optional

logger = logging.getLogger(__name__)

async def has_required_permissions(
    interaction: discord.Interaction,
    required_permissions: List[str] = None,
    allowed_roles: List[str] = None,
    bot_owner_override: bool = True
) -> bool:
    """
    Check if a user has required permissions for a command.
    
    Args:
        interaction: Discord interaction object
        required_permissions: List of required permission names (e.g., ['manage_guild', 'administrator'])
        allowed_roles: List of allowed role names
        bot_owner_override: Whether bot owners bypass all checks
    
    Returns:
        bool: True if user has permissions, False otherwise
    """
    try:
        # Bot owner check (if enabled and bot has owner check method)
        if bot_owner_override and hasattr(interaction.client, 'is_bot_owner'):
            if interaction.client.is_bot_owner(interaction.user.id):
                return True
        
        # Guild administrator check
        if interaction.user.guild_permissions.administrator:
            return True
        
        # Check specific permissions
        if required_permissions:
            user_permissions = interaction.user.guild_permissions
            for perm in required_permissions:
                if not getattr(user_permissions, perm, False):
                    return False
        
        # Check role-based permissions
        if allowed_roles:
            user_roles = [role.name.lower() for role in interaction.user.roles]
            allowed_roles_lower = [role.lower() for role in allowed_roles]
            
            if not any(role in allowed_roles_lower for role in user_roles):
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking permissions: {e}")
        return False

async def has_prospect_management_permissions(interaction: discord.Interaction) -> bool:
    """Check if user has prospect management permissions"""
    return await has_required_permissions(
        interaction,
        required_permissions=['manage_guild'],
        allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator']
    )

async def has_prospect_notes_permissions(interaction: discord.Interaction) -> bool:
    """Check if user has prospect notes permissions"""
    return await has_required_permissions(
        interaction,
        required_permissions=['manage_messages'],
        allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator', 'Sponsor']
    )

async def has_prospect_voting_permissions(interaction: discord.Interaction) -> bool:
    """Check if user has prospect voting permissions"""
    return await has_required_permissions(
        interaction,
        required_permissions=['manage_roles'],
        allowed_roles=['Officer', 'Leadership', 'Admin', 'Member']
    )

async def has_prospect_dashboard_permissions(interaction: discord.Interaction) -> bool:
    """Check if user has prospect dashboard permissions"""
    return await has_required_permissions(
        interaction,
        allowed_roles=['Officer', 'Leadership', 'Admin', 'Moderator', 'Sponsor', 'Member']
    )

class PermissionError(Exception):
    """Custom exception for permission errors"""
    pass

def require_permissions(
    required_permissions: List[str] = None,
    allowed_roles: List[str] = None,
    bot_owner_override: bool = True
):
    """
    Decorator to require specific permissions for a command.
    
    Args:
        required_permissions: List of required permission names
        allowed_roles: List of allowed role names
        bot_owner_override: Whether bot owners bypass all checks
    """
    def decorator(func):
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not await has_required_permissions(
                interaction, 
                required_permissions, 
                allowed_roles, 
                bot_owner_override
            ):
                await interaction.response.send_message(
                    "❌ You don't have the required permissions to use this command.",
                    ephemeral=True
                )
                return
            
            return await func(self, interaction, *args, **kwargs)
        
        return wrapper
    return decorator

async def is_prospect_sponsor(interaction: discord.Interaction, prospect_user_id: int) -> bool:
    """Check if the user is the sponsor of a specific prospect"""
    try:
        # Get prospect data from database
        if hasattr(interaction.client, 'db'):
            prospect = await interaction.client.db.get_prospect(interaction.guild.id, prospect_user_id)
            if prospect and prospect['sponsor_id'] == interaction.user.id:
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking sponsor permissions: {e}")
        return False

async def is_prospect_or_sponsor(interaction: discord.Interaction, prospect_user_id: int) -> bool:
    """Check if the user is either the prospect or their sponsor"""
    # Check if user is the prospect themselves
    if interaction.user.id == prospect_user_id:
        return True
    
    # Check if user is the sponsor
    return await is_prospect_sponsor(interaction, prospect_user_id)

async def get_server_config_permissions(interaction: discord.Interaction, config_key: str) -> bool:
    """Check permissions based on server configuration"""
    try:
        if hasattr(interaction.client, 'db'):
            config = await interaction.client.db.get_server_config(interaction.guild.id)
            if config and config.get(f'{config_key}_role_id'):
                role = interaction.guild.get_role(config[f'{config_key}_role_id'])
                if role and role in interaction.user.roles:
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking server config permissions: {e}")
        return False

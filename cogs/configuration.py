import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import List, Optional

class ConfigurationSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def _has_admin_permissions(self, member: discord.Member) -> bool:
        """Check if member has administrator permissions"""
        return member.guild_permissions.administrator
    
    @app_commands.command(name="set_officer_role", description="Set which role has officer permissions (Admin only)")
    async def set_officer_role(self, interaction: discord.Interaction, role: discord.Role):
        """Set which role has officer permissions for managing LOAs, memberships, and contributions"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            officer_role_id=role.id
        )
        
        embed = discord.Embed(
            title="✅ Officer Role Configured",
            description=f"**Officer role set to {role.mention}**\n\n"
                       f"Members with this role can now:\n"
                       f"• Manage LOA requests (approve/deny)\n"
                       f"• Sync membership rosters\n"
                       f"• View contribution reports\n"
                       f"• Access officer-only commands",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Role ID: {role.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="config_officer_role", description="Set the officer role for permissions (Admin only)")
    async def config_officer_role(self, interaction: discord.Interaction, role: discord.Role):
        """Configure the officer role (legacy command - use /set_officer_role instead)"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            officer_role_id=role.id
        )
        
        embed = discord.Embed(
            title="✅ Officer Role Configured",
            description=f"Officer role set to {role.mention}\n\n"
                       f"💡 **Tip:** Use `/set_officer_role` for the enhanced version of this command.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="clear_officer_role", description="Remove the current officer role (Admin only)")
    async def clear_officer_role(self, interaction: discord.Interaction):
        """Clear the current officer role configuration"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Get current configuration to show what we're clearing
        config = await self.bot.db.get_server_config(interaction.guild.id)
        current_role = None
        if config and config.get('officer_role_id'):
            current_role = interaction.guild.get_role(config['officer_role_id'])
        
        if not current_role:
            return await interaction.response.send_message(
                "❌ No officer role is currently configured.", ephemeral=True
            )
        
        # Clear the officer role
        await self.bot.db.update_server_config(
            interaction.guild.id,
            officer_role_id=None
        )
        
        embed = discord.Embed(
            title="✅ Officer Role Cleared",
            description=f"**Removed {current_role.mention} as officer role**\n\n"
                       f"⚠️ **Warning:** No role currently has officer permissions.\n"
                       f"Use `/set_officer_role` to assign a new officer role.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="config_notification_channel", description="Set the notification channel (Admin only)")
    async def config_notification_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Configure the notification channel for LOA alerts"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            notification_channel_id=channel.id
        )
        
        embed = discord.Embed(
            title="✅ Notification Channel Configured",
            description=f"Notification channel set to {channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="config_leadership_channel", description="Set the leadership channel for contribution alerts (Admin only)")
    async def config_leadership_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Configure the leadership channel for contribution notifications"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            leadership_channel_id=channel.id
        )
        
        embed = discord.Embed(
            title="✅ Leadership Channel Configured",
            description=f"Leadership channel set to {channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="config_dm_user", description="Set the user to receive DM notifications (Admin only)")
    async def config_dm_user(self, interaction: discord.Interaction, user: discord.Member):
        """Configure the user to receive DM notifications"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            dm_user_id=user.id
        )
        
        embed = discord.Embed(
            title="✅ DM User Configured",
            description=f"DM notifications will be sent to {user.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="config_membership_roles", description="Configure membership roles (Admin only)")
    async def config_membership_roles(self, interaction: discord.Interaction, roles: str):
        """Configure membership roles (comma-separated list)"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Parse roles
        role_names = [role.strip() for role in roles.split(',') if role.strip()]
        
        if not role_names:
            return await interaction.response.send_message(
                "❌ Please provide at least one role name.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            membership_roles=role_names
        )
        
        embed = discord.Embed(
            title="✅ Membership Roles Configured",
            description=f"Configured {len(role_names)} membership roles:\n• " + "\n• ".join(role_names),
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="config_contribution_categories", description="Configure contribution categories (Admin only)")
    async def config_contribution_categories(self, interaction: discord.Interaction, categories: str):
        """Configure contribution categories (comma-separated list)"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Parse categories
        category_names = [cat.strip() for cat in categories.split(',') if cat.strip()]
        
        if not category_names:
            return await interaction.response.send_message(
                "❌ Please provide at least one category name.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            contribution_categories=category_names
        )
        
        embed = discord.Embed(
            title="✅ Contribution Categories Configured",
            description=f"Configured {len(category_names)} categories:\n• " + "\n• ".join(category_names),
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="config_add_membership_role", description="Add a single membership role (Admin only)")
    async def config_add_membership_role(self, interaction: discord.Interaction, role_name: str):
        """Add a single membership role to the existing list"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Get current configuration
        config = await self.bot.db.get_server_config(interaction.guild.id)
        current_roles = config.get('membership_roles', []) if config else []
        
        if role_name in current_roles:
            return await interaction.response.send_message(
                f"❌ Role '{role_name}' is already in the membership roles list.", ephemeral=True
            )
        
        # Add the new role
        current_roles.append(role_name)
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            membership_roles=current_roles
        )
        
        embed = discord.Embed(
            title="✅ Membership Role Added",
            description=f"Added '{role_name}' to membership roles.\n\nCurrent roles:\n• " + "\n• ".join(current_roles),
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="config_remove_membership_role", description="Remove a membership role (Admin only)")
    async def config_remove_membership_role(self, interaction: discord.Interaction, role_name: str):
        """Remove a membership role from the list"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Get current configuration
        config = await self.bot.db.get_server_config(interaction.guild.id)
        current_roles = config.get('membership_roles', []) if config else []
        
        if role_name not in current_roles:
            return await interaction.response.send_message(
                f"❌ Role '{role_name}' is not in the membership roles list.", ephemeral=True
            )
        
        # Remove the role
        current_roles.remove(role_name)
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            membership_roles=current_roles
        )
        
        embed = discord.Embed(
            title="✅ Membership Role Removed",
            description=f"Removed '{role_name}' from membership roles.\n\nRemaining roles:\n• " + "\n• ".join(current_roles) if current_roles else "No roles configured",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="config_add_contribution_category", description="Add a contribution category (Admin only)")
    async def config_add_contribution_category(self, interaction: discord.Interaction, category_name: str):
        """Add a single contribution category to the existing list"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Get current configuration
        config = await self.bot.db.get_server_config(interaction.guild.id)
        current_categories = config.get('contribution_categories', []) if config else []
        
        if category_name in current_categories:
            return await interaction.response.send_message(
                f"❌ Category '{category_name}' is already in the contribution categories list.", ephemeral=True
            )
        
        # Add the new category
        current_categories.append(category_name)
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            contribution_categories=current_categories
        )
        
        embed = discord.Embed(
            title="✅ Contribution Category Added",
            description=f"Added '{category_name}' to contribution categories.\n\nCurrent categories:\n• " + "\n• ".join(current_categories),
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="config_remove_category", description="Remove a contribution category (Admin only)")
    async def config_remove_contribution_category(self, interaction: discord.Interaction, category_name: str):
        """Remove a contribution category from the list"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Get current configuration
        config = await self.bot.db.get_server_config(interaction.guild.id)
        current_categories = config.get('contribution_categories', []) if config else []
        
        if category_name not in current_categories:
            return await interaction.response.send_message(
                f"❌ Category '{category_name}' is not in the contribution categories list.", ephemeral=True
            )
        
        # Remove the category
        current_categories.remove(category_name)
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            contribution_categories=current_categories
        )
        
        embed = discord.Embed(
            title="✅ Contribution Category Removed",
            description=f"Removed '{category_name}' from contribution categories.\n\nRemaining categories:\n• " + "\n• ".join(current_categories) if current_categories else "No categories configured",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="set_notification_channel", description="Set the general notification channel (Admin only)")
    async def set_notification_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the notification channel for general bot alerts and notifications"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            notification_channel_id=channel.id
        )
        
        embed = discord.Embed(
            title="✅ Notification Channel Set",
            description=f"**General notification channel set to {channel.mention}**\n\n"
                       f"This channel will receive:\n"
                       f"• General bot notifications\n"
                       f"• Officer-related alerts\n"
                       f"• System status messages",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="set_leadership_channel", description="Set the leadership channel for contribution alerts (Admin only)")
    async def set_leadership_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the leadership channel for contribution alerts and leadership notifications"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            leadership_channel_id=channel.id
        )
        
        embed = discord.Embed(
            title="✅ Leadership Channel Set",
            description=f"**Leadership channel set to {channel.mention}**\n\n"
                       f"This channel will receive:\n"
                       f"• Contribution notifications\n"
                       f"• Leadership-specific alerts\n"
                       f"• Important administrative updates",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="set_forum_channel", description="Set a forum channel for category thread clearing (Admin only)")
    async def set_forum_channel(self, interaction: discord.Interaction, channel: discord.ForumChannel, category_type: str):
        """Set a forum channel for category thread clearing during archives"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Validate category type
        valid_types = ['weapons_locker', 'drug_locker', 'misc_locker']
        if category_type.lower() not in valid_types:
            return await interaction.response.send_message(
                f"❌ Invalid category type. Please use one of: {', '.join(valid_types)}", ephemeral=True
            )
        
        # Update server configuration
        config_key = f"{category_type.lower()}_forum_channel_id"
        await self.bot.db.update_server_config(
            interaction.guild.id,
            **{config_key: channel.id}
        )
        
        embed = discord.Embed(
            title="✅ Forum Channel Set",
            description=f"**{category_type.replace('_', ' ').title()} forum channel set to {channel.mention}**\n\n"
                       f"This forum's threads will be cleared when creating archives.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="add_dm_user", description="Add a user to receive DM notifications (Admin only)")
    async def add_dm_user(self, interaction: discord.Interaction, user: discord.Member):
        """Add a user to the list of users who receive direct message notifications"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Add the user to the DM users list
        success = await self.bot.db.add_dm_user(interaction.guild.id, user.id)
        
        if not success:
            return await interaction.response.send_message(
                f"❌ {user.mention} is already in the DM users list.", ephemeral=True
            )
        
        # Get current DM users count
        dm_users = await self.bot.db.get_dm_users(interaction.guild.id)
        
        embed = discord.Embed(
            title="✅ DM User Added",
            description=f"**Added {user.mention} to DM users list**\n\n"
                       f"Total DM users: {len(dm_users)}\n\n"
                       f"This user will receive:\n"
                       f"• Private bot notifications\n"
                       f"• Critical system alerts\n"
                       f"• Administrative updates via DM",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"User ID: {user.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="remove_dm_user", description="Remove a user from DM notifications (Admin only)")
    async def remove_dm_user(self, interaction: discord.Interaction, user: discord.Member):
        """Remove a user from the list of users who receive direct message notifications"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Remove the user from the DM users list
        success = await self.bot.db.remove_dm_user(interaction.guild.id, user.id)
        
        if not success:
            return await interaction.response.send_message(
                f"❌ {user.mention} is not in the DM users list.", ephemeral=True
            )
        
        # Get current DM users count
        dm_users = await self.bot.db.get_dm_users(interaction.guild.id)
        
        embed = discord.Embed(
            title="✅ DM User Removed",
            description=f"**Removed {user.mention} from DM users list**\n\n"
                       f"Remaining DM users: {len(dm_users)}",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"User ID: {user.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="list_dm_users", description="List all users configured to receive DM notifications")
    async def list_dm_users(self, interaction: discord.Interaction):
        """List all users configured to receive DM notifications"""
        # Get DM users
        dm_users = await self.bot.db.get_dm_users(interaction.guild.id)
        
        embed = discord.Embed(
            title="💬 DM Users Configuration",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not dm_users:
            embed.description = "No users are currently configured to receive DM notifications."
        else:
            user_list = []
            for user_id in dm_users:
                user = interaction.client.get_user(user_id)
                if user:
                    user_list.append(f"• {user.mention} (`{user.name}`)")
                else:
                    user_list.append(f"• User ID: {user_id} (User not found)")
            
            embed.description = f"**{len(dm_users)} user(s) configured to receive DM notifications:**\n\n" + "\n".join(user_list)
        
        embed.set_footer(text=f"Server ID: {interaction.guild.id}")
        
        # Only show to admins by default, but allow others to see if not sensitive
        is_admin = self._has_admin_permissions(interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=not is_admin)
    
    @app_commands.command(name="clear_dm_users", description="Remove all users from DM notifications (Admin only)")
    async def clear_dm_users(self, interaction: discord.Interaction):
        """Clear all users from the DM notifications list"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Get current DM users before clearing
        dm_users = await self.bot.db.get_dm_users(interaction.guild.id)
        
        if not dm_users:
            return await interaction.response.send_message(
                "❌ No DM users are currently configured.", ephemeral=True
            )
        
        # Clear all DM users
        await self.bot.db.clear_dm_users(interaction.guild.id)
        
        embed = discord.Embed(
            title="✅ DM Users Cleared",
            description=f"**Removed all {len(dm_users)} users from DM notifications list**\n\n"
                       f"No users will receive DM notifications until new ones are added.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="set_dm_user", description="Set the user to receive DM notifications (Admin only) - Legacy")
    async def set_dm_user(self, interaction: discord.Interaction, user: discord.Member):
        """Legacy command - use /add_dm_user instead for multiple user support"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Clear existing users and set this one user
        await self.bot.db.set_dm_users(interaction.guild.id, [user.id])
        
        embed = discord.Embed(
            title="✅ DM User Set (Legacy Mode)",
            description=f"**DM notifications will be sent to {user.mention}**\n\n"
                       f"💡 **Tip:** Use `/add_dm_user` to add multiple users, or `/remove_dm_user` to manage the list.\n\n"
                       f"This user will receive:\n"
                       f"• Private bot notifications\n"
                       f"• Critical system alerts\n"
                       f"• Administrative updates via DM",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"User ID: {user.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="set_loa_notification_role", description="Set which role gets pinged for LOA notifications (Admin only)")
    async def set_loa_notification_role(self, interaction: discord.Interaction, role: discord.Role):
        """Set which role gets pinged when members go on LOA"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            loa_notification_role_id=role.id
        )
        
        embed = discord.Embed(
            title="✅ LOA Notification Role Set",
            description=f"**LOA notification role set to {role.mention}**\n\n"
                       f"This role will be pinged whenever:\n"
                       f"• A member submits an LOA request\n"
                       f"• A member returns from LOA\n"
                       f"• An LOA expires automatically",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Role ID: {role.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="set_loa_notification_channel", description="Set the channel for LOA notifications (Admin only)")
    async def set_loa_notification_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the channel where LOA notifications will be sent"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            loa_notification_channel_id=channel.id
        )
        
        embed = discord.Embed(
            title="✅ LOA Notification Channel Set",
            description=f"**LOA notification channel set to {channel.mention}**\n\n"
                       f"LOA status changes and membership updates will be posted here.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="toggle_cross_server", description="Enable/disable cross-server LOA notifications (Admin only)")
    async def toggle_cross_server_notifications(self, interaction: discord.Interaction, enabled: bool):
        """Toggle whether LOA notifications should be sent to all configured servers"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            cross_server_notifications=enabled
        )
        
        status_text = "enabled" if enabled else "disabled"
        status_emoji = "✅" if enabled else "❌"
        
        embed = discord.Embed(
            title=f"{status_emoji} Cross-Server Notifications {status_text.title()}",
            description=f"**Cross-server LOA notifications are now {status_text}**\n\n"
                       f"When {'enabled' if enabled else 'disabled'}, LOA changes " +
                       ("will be sent to all servers where the bot has notification channels configured."
                        if enabled else "will only be sent to this server's configured channels."),
            color=discord.Color.green() if enabled else discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="config_view", description="View current server configuration")
    async def config_view(self, interaction: discord.Interaction):
        """View the current server configuration"""
        # Get server configuration
        config = await self.bot.db.get_server_config(interaction.guild.id)
        
        if not config:
            embed = discord.Embed(
                title="⚙️ Server Configuration",
                description="No configuration found. Server may not be initialized.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        embed = discord.Embed(
            title="⚙️ Server Configuration",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Officer role
        if config.get('officer_role_id'):
            role = interaction.guild.get_role(config['officer_role_id'])
            embed.add_field(
                name="👮 Officer Role",
                value=role.mention if role else f"Role ID: {config['officer_role_id']} (Not found)",
                inline=True
            )
        else:
            embed.add_field(name="👮 Officer Role", value="Not configured", inline=True)
        
        # Notification channel
        if config.get('notification_channel_id'):
            channel = interaction.guild.get_channel(config['notification_channel_id'])
            embed.add_field(
                name="📢 Notification Channel",
                value=channel.mention if channel else f"Channel ID: {config['notification_channel_id']} (Not found)",
                inline=True
            )
        else:
            embed.add_field(name="📢 Notification Channel", value="Not configured", inline=True)
        
        # Leadership channel
        if config.get('leadership_channel_id'):
            channel = interaction.guild.get_channel(config['leadership_channel_id'])
            embed.add_field(
                name="🏛️ Leadership Channel",
                value=channel.mention if channel else f"Channel ID: {config['leadership_channel_id']} (Not found)",
                inline=True
            )
        else:
            embed.add_field(name="🏛️ Leadership Channel", value="Not configured", inline=True)
        
        # DM users
        dm_users = await self.bot.db.get_dm_users(interaction.guild.id)
        if dm_users:
            user_mentions = []
            for user_id in dm_users:
                user = interaction.client.get_user(user_id)
                if user:
                    user_mentions.append(user.mention)
                else:
                    user_mentions.append(f"User ID: {user_id} (Not found)")
            
            embed.add_field(
                name=f"💬 DM Users ({len(dm_users)})",
                value="\n".join(user_mentions) if user_mentions else "None configured",
                inline=True
            )
        else:
            embed.add_field(name="💬 DM Users", value="Not configured", inline=True)
        
        # LOA Notification Role
        if config.get('loa_notification_role_id'):
            role = interaction.guild.get_role(config['loa_notification_role_id'])
            embed.add_field(
                name="🔔 LOA Notification Role",
                value=role.mention if role else f"Role ID: {config['loa_notification_role_id']} (Not found)",
                inline=True
            )
        else:
            embed.add_field(name="🔔 LOA Notification Role", value="Not configured", inline=True)
        
        # LOA Notification Channel
        if config.get('loa_notification_channel_id'):
            channel = interaction.guild.get_channel(config['loa_notification_channel_id'])
            embed.add_field(
                name="📨 LOA Notification Channel",
                value=channel.mention if channel else f"Channel ID: {config['loa_notification_channel_id']} (Not found)",
                inline=True
            )
        else:
            embed.add_field(name="📨 LOA Notification Channel", value="Not configured", inline=True)
        
        # Cross-server notifications
        cross_server_enabled = config.get('cross_server_notifications', False)
        embed.add_field(
            name="🌐 Cross-Server Notifications",
            value="✅ Enabled" if cross_server_enabled else "❌ Disabled",
            inline=True
        )
        
        # Membership roles
        membership_roles = config.get('membership_roles', [])
        if membership_roles:
            roles_text = "\n• ".join(membership_roles)
            if len(roles_text) > 1000:
                roles_text = roles_text[:950] + "..."
            embed.add_field(
                name=f"👥 Membership Roles ({len(membership_roles)})",
                value=f"• {roles_text}",
                inline=False
            )
        else:
            embed.add_field(name="👥 Membership Roles", value="Not configured", inline=False)
        
        # Contribution categories
        contribution_categories = config.get('contribution_categories', [])
        if contribution_categories:
            categories_text = "\n• ".join(contribution_categories)
            if len(categories_text) > 1000:
                categories_text = categories_text[:950] + "..."
            embed.add_field(
                name=f"📦 Contribution Categories ({len(contribution_categories)})",
                value=f"• {categories_text}",
                inline=False
            )
        else:
            embed.add_field(name="📦 Contribution Categories", value="Not configured", inline=False)
        
        embed.set_footer(text=f"Server ID: {interaction.guild.id}")
        
        # Check if user is admin to show sensitive info
        is_admin = self._has_admin_permissions(interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=not is_admin)
    
    @app_commands.command(name="setup", description="Interactive bot setup menu with dropdowns (Admin only)")
    async def setup_menu(self, interaction: discord.Interaction):
        """Interactive setup menu with dropdown selectors for all configuration options"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Create the setup view and populate dropdown options
        view = ConfigurationMenuView(self.bot, interaction.guild)
        await view._populate_all_options()
        embed = await view.create_main_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="config_reset", description="Reset all server configuration (Admin only)")
    async def config_reset(self, interaction: discord.Interaction):
        """Reset all server configuration to defaults"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        # Confirmation embed
        embed = discord.Embed(
            title="⚠️ Confirm Configuration Reset",
            description="This will reset ALL server configuration to defaults:\n\n"
                       "• Officer role will be cleared\n"
                       "• All channels will be cleared\n"
                       "• DM user will be cleared\n"
                       "• Membership roles will be reset to defaults\n"
                       "• Contribution categories will be reset to defaults\n\n"
                       "**This action cannot be undone!**",
            color=discord.Color.red()
        )
        
        # Create confirmation view
        view = discord.ui.View(timeout=60)
        
        async def confirm_callback(button_interaction):
            if button_interaction.user != interaction.user:
                return await button_interaction.response.send_message(
                    "❌ Only the command user can confirm this action.", ephemeral=True
                )
            
            # Reset configuration
            await self.bot.db.initialize_guild(interaction.guild.id)
            
            success_embed = discord.Embed(
                title="✅ Configuration Reset",
                description="Server configuration has been reset to defaults.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            await button_interaction.response.edit_message(embed=success_embed, view=None)
        
        async def cancel_callback(button_interaction):
            if button_interaction.user != interaction.user:
                return await button_interaction.response.send_message(
                    "❌ Only the command user can cancel this action.", ephemeral=True
                )
            
            cancel_embed = discord.Embed(
                title="❌ Configuration Reset Cancelled",
                description="No changes were made to the server configuration.",
                color=discord.Color.blue()
            )
            
            await button_interaction.response.edit_message(embed=cancel_embed, view=None)
        
        confirm_button = discord.ui.Button(label="Confirm Reset", style=discord.ButtonStyle.danger)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        
        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback
        
        view.add_item(confirm_button)
        view.add_item(cancel_button)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ConfigurationMenuView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.current_step = "main"  # Track current configuration step
        
        # Initialize dropdown selectors (only the most essential ones)
        self._init_dropdowns()
    
    def _init_dropdowns(self):
        """Initialize dropdown selectors with placeholder options"""
        # Simplified approach with fewer buttons to stay within Discord's limits
        
        # Row 0: Essential configuration buttons (max 4 to leave room)
        self.config_roles_button = discord.ui.Button(
            label="Roles & Notifications", 
            style=discord.ButtonStyle.primary, 
            emoji="👮",
            row=0
        )
        self.config_roles_button.callback = self.configure_roles
        self.add_item(self.config_roles_button)
        
        self.config_channels_button = discord.ui.Button(
            label="Channels", 
            style=discord.ButtonStyle.primary, 
            emoji="📢",
            row=0
        )
        self.config_channels_button.callback = self.configure_channels
        self.add_item(self.config_channels_button)
        
    async def create_main_embed(self):
        """Create the main configuration embed showing current settings"""
        config = await self.bot.db.get_server_config(self.guild.id)
        
        embed = discord.Embed(
            title="🛠️ Bot Configuration Setup",
            description="Use the buttons below to configure your bot settings.\n"
                       "**Click a button to access specific configuration options.**\n\n"
                       "**Current Configuration:**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if config:
            config_text = ""
            
            # Officer role
            if config.get('officer_role_id'):
                role = self.guild.get_role(config['officer_role_id'])
                config_text += f"👮 **Officer Role:** {role.mention if role else 'Not found'}\n"
            else:
                config_text += f"👮 **Officer Role:** Not set\n"
            
            # LOA Notification Role
            if config.get('loa_notification_role_id'):
                role = self.guild.get_role(config['loa_notification_role_id'])
                config_text += f"🔔 **LOA Notification Role:** {role.mention if role else 'Not found'}\n"
            else:
                config_text += f"🔔 **LOA Notification Role:** Not set\n"
                
            config_text += "\n"
            
            # Notification channel
            if config.get('notification_channel_id'):
                channel = self.guild.get_channel(config['notification_channel_id'])
                config_text += f"📢 **Notification Channel:** {channel.mention if channel else 'Not found'}\n"
            else:
                config_text += f"📢 **Notification Channel:** Not set\n"
            
            # Leadership channel
            if config.get('leadership_channel_id'):
                channel = self.guild.get_channel(config['leadership_channel_id'])
                config_text += f"🏛️ **Leadership Channel:** {channel.mention if channel else 'Not found'}\n"
            else:
                config_text += f"🏛️ **Leadership Channel:** Not set\n"
            
            # LOA Notification Channel
            if config.get('loa_notification_channel_id'):
                channel = self.guild.get_channel(config['loa_notification_channel_id'])
                config_text += f"📨 **LOA Notification Channel:** {channel.mention if channel else 'Not found'}\n"
            else:
                config_text += f"📨 **LOA Notification Channel:** Not set\n"
                
            config_text += "\n"
            
            # DM users
            dm_users = await self.bot.db.get_dm_users(self.guild.id)
            if dm_users:
                user_mentions = []
                for user_id in dm_users:
                    user = self.bot.get_user(user_id)
                    if user:
                        user_mentions.append(user.mention)
                    else:
                        user_mentions.append(f"ID:{user_id}")
                config_text += f"💬 **DM Users ({len(dm_users)}):** {', '.join(user_mentions)}\n"
            else:
                config_text += f"💬 **DM Users:** Not set\n"
            
            # Cross-server notifications
            cross_server_enabled = config.get('cross_server_notifications', False)
            config_text += f"🌐 **Cross-Server Notifications:** {'✅ Enabled' if cross_server_enabled else '❌ Disabled'}\n"
            
            embed.description += f"\n{config_text}"
        else:
            embed.description += "\n⚠️ **No Configuration Found** - Use the buttons below to set up your bot."
        
        return embed
    
    # Add button interaction callbacks
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to use configuration commands"""
        return interaction.user.guild_permissions.administrator
    
    # Dropdown callback methods
    async def officer_role_callback(self, interaction: discord.Interaction):
        """Handle officer role dropdown selection"""
        role_id = interaction.data["values"][0]
        if role_id == "loading":
            await interaction.response.defer()
            return
        
        if role_id == "none":
            await self.bot.db.update_server_config(self.guild.id, officer_role_id=None)
            role_text = "cleared"
        else:
            role = self.guild.get_role(int(role_id))
            if role:
                await self.bot.db.update_server_config(self.guild.id, officer_role_id=role.id)
                role_text = f"set to {role.mention}"
            else:
                await interaction.response.send_message("❌ Role not found.", ephemeral=True)
                return
        
        embed = await self.create_main_embed()
        embed.add_field(
            name="✅ Officer Role Updated",
            value=f"Officer role {role_text}",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def loa_role_callback(self, interaction: discord.Interaction):
        """Handle LOA notification role dropdown selection"""
        role_id = interaction.data["values"][0]
        if role_id == "loading":
            await interaction.response.defer()
            return
        
        if role_id == "none":
            await self.bot.db.update_server_config(self.guild.id, loa_notification_role_id=None)
            role_text = "cleared"
        else:
            role = self.guild.get_role(int(role_id))
            if role:
                await self.bot.db.update_server_config(self.guild.id, loa_notification_role_id=role.id)
                role_text = f"set to {role.mention}"
            else:
                await interaction.response.send_message("❌ Role not found.", ephemeral=True)
                return
        
        embed = await self.create_main_embed()
        embed.add_field(
            name="✅ LOA Notification Role Updated",
            value=f"LOA notification role {role_text}",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def notification_channel_callback(self, interaction: discord.Interaction):
        """Handle notification channel dropdown selection"""
        channel_id = interaction.data["values"][0]
        if channel_id == "loading":
            await interaction.response.defer()
            return
        
        if channel_id == "none":
            await self.bot.db.update_server_config(self.guild.id, notification_channel_id=None)
            channel_text = "cleared"
        else:
            channel = self.guild.get_channel(int(channel_id))
            if channel:
                await self.bot.db.update_server_config(self.guild.id, notification_channel_id=channel.id)
                channel_text = f"set to {channel.mention}"
            else:
                await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
                return
        
        embed = await self.create_main_embed()
        embed.add_field(
            name="✅ Notification Channel Updated",
            value=f"Notification channel {channel_text}",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def leadership_channel_callback(self, interaction: discord.Interaction):
        """Handle leadership channel dropdown selection"""
        channel_id = interaction.data["values"][0]
        if channel_id == "loading":
            await interaction.response.defer()
            return
        
        if channel_id == "none":
            await self.bot.db.update_server_config(self.guild.id, leadership_channel_id=None)
            channel_text = "cleared"
        else:
            channel = self.guild.get_channel(int(channel_id))
            if channel:
                await self.bot.db.update_server_config(self.guild.id, leadership_channel_id=channel.id)
                channel_text = f"set to {channel.mention}"
            else:
                await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
                return
        
        embed = await self.create_main_embed()
        embed.add_field(
            name="✅ Leadership Channel Updated",
            value=f"Leadership channel {channel_text}",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def loa_channel_callback(self, interaction: discord.Interaction):
        """Handle LOA notification channel dropdown selection"""
        channel_id = interaction.data["values"][0]
        if channel_id == "loading":
            await interaction.response.defer()
            return
        
        if channel_id == "none":
            await self.bot.db.update_server_config(self.guild.id, loa_notification_channel_id=None)
            channel_text = "cleared"
        else:
            channel = self.guild.get_channel(int(channel_id))
            if channel:
                await self.bot.db.update_server_config(self.guild.id, loa_notification_channel_id=channel.id)
                channel_text = f"set to {channel.mention}"
            else:
                await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
                return
        
        embed = await self.create_main_embed()
        embed.add_field(
            name="✅ LOA Notification Channel Updated",
            value=f"LOA notification channel {channel_text}",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=self)
    
    # Add button callback methods
    async def configure_roles(self, interaction: discord.Interaction):
        """Show role configuration options"""
        view = RoleConfigurationView(self.bot, self.guild, self)
        embed = discord.Embed(
            title="👮 Role Configuration",
            description="Choose how you'd like to configure roles:\n\n"
                       "🔍 **Search** - Type to find specific roles\n"
                       "📋 **Browse** - Select from dropdown lists",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def configure_notifications(self, interaction: discord.Interaction):
        """Show notification configuration options (roles)"""
        view = RoleConfigurationView(self.bot, self.guild, self)
        embed = discord.Embed(
            title="🔔 Notification Configuration",
            description="Configure notification roles:\n\n"
                       "🔍 **Search** - Type to find specific roles\n"
                       "📋 **Browse** - Select from dropdown lists",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def configure_channels(self, interaction: discord.Interaction):
        """Show channel configuration options"""
        view = ChannelConfigurationView(self.bot, self.guild, self)
        embed = discord.Embed(
            title="📢 Channel Configuration",
            description="Choose how you'd like to configure channels:\n\n"
                       "🔍 **Search** - Type to find specific channels\n"
                       "📋 **Browse** - Select from dropdown lists",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def on_timeout(self):
        """Called when the view times out"""
        # Disable all components
        for item in self.children:
            item.disabled = True
    
    async def _populate_all_options(self):
        """Populate all dropdown options with actual server data"""
        try:
            # Get current configuration - no dropdowns to populate since we use buttons now
            config = await self.bot.db.get_server_config(self.guild.id) or {}
            
            # Note: We now use buttons instead of dropdowns to avoid Discord component limits
            # All configuration options are accessed through button-based navigation
            pass
        
        except Exception as e:
            print(f"Error in populate options: {e}")
    
    @discord.ui.button(label="Configure DM User", style=discord.ButtonStyle.primary, emoji="💬", row=1)
    async def configure_dm_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show DM user configuration options"""
        view = UserConfigurationView(self.bot, self.guild, self)
        embed = discord.Embed(
            title="🛠️ DM User Configuration",
            description="Choose how you'd like to configure the DM user:\n\n"
                       "🔍 **Search** - Type to find specific users\n"
                       "📋 **Dropdown** - Browse from a list",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Toggle Cross-Server", style=discord.ButtonStyle.secondary, emoji="🌐", row=1)
    async def toggle_cross_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle cross-server notifications"""
        config = await self.bot.db.get_server_config(self.guild.id)
        current_state = config.get('cross_server_notifications', False) if config else False
        new_state = not current_state
        
        await self.bot.db.update_server_config(
            self.guild.id,
            cross_server_notifications=new_state
        )
        
        # Update the main embed
        await self._populate_all_options()
        embed = await self.create_main_embed()
        embed.add_field(
            name="🌐 Cross-Server Notifications Updated",
            value=f"Cross-server notifications are now {'✅ **Enabled**' if new_state else '❌ **Disabled**'}",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Refresh View", style=discord.ButtonStyle.success, emoji="🔄", row=1)
    async def refresh_view(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the configuration view"""
        await self._populate_all_options()
        embed = await self.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """Called when the view times out"""
        # Disable all components
        for item in self.children:
            item.disabled = True


class RoleSelectionView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, role_type: str, parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.role_type = role_type
        self.parent_view = parent_view
        
        # Get roles and create select options (limit to 25)
        roles = [role for role in guild.roles if not role.is_default() and not role.managed][:23]
        options = [
            discord.SelectOption(
                label=role.name,
                description=f"Members: {len(role.members)}",
                value=str(role.id)
            )
            for role in roles
        ]
        
        # Add "None" option
        options.append(discord.SelectOption(
            label="None (Clear Setting)",
            description="Remove the current role setting",
            value="none"
        ))
        
        if options:
            self.role_select.options = options
        else:
            self.role_select.disabled = True
    
    @discord.ui.select(placeholder="Choose a role...")
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle role selection"""
        role_id = select.values[0]
        
        if role_id == "none":
            # Clear the role setting
            field_name = "officer_role_id" if self.role_type == "officer_role" else "loa_notification_role_id"
            await self.bot.db.update_server_config(self.guild.id, **{field_name: None})
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ Role Cleared",
                value=f"{'Officer role' if self.role_type == 'officer_role' else 'LOA notification role'} has been cleared.",
                inline=False
            )
        else:
            role = self.guild.get_role(int(role_id))
            if role:
                field_name = "officer_role_id" if self.role_type == "officer_role" else "loa_notification_role_id"
                await self.bot.db.update_server_config(self.guild.id, **{field_name: role.id})
                
                embed = await self.parent_view.create_main_embed()
                embed.add_field(
                    name="✅ Role Set",
                    value=f"{'Officer role' if self.role_type == 'officer_role' else 'LOA notification role'} set to {role.mention}",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Role not found.",
                    color=discord.Color.red()
                )
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
    
    @discord.ui.button(label="Back to Main Menu", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ChannelSelectionView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, channel_type: str, parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.channel_type = channel_type
        self.parent_view = parent_view
        
        # Get text channels and create select options (limit to 25)
        channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages][:23]
        options = [
            discord.SelectOption(
                label=f"#{channel.name}",
                description=f"Category: {channel.category.name if channel.category else 'None'}",
                value=str(channel.id)
            )
            for channel in channels
        ]
        
        # Add "None" option
        options.append(discord.SelectOption(
            label="None (Clear Setting)",
            description="Remove the current channel setting",
            value="none"
        ))
        
        if options:
            self.channel_select.options = options
        else:
            self.channel_select.disabled = True
    
    @discord.ui.select(placeholder="Choose a channel...")
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle channel selection"""
        channel_id = select.values[0]
        
        field_mapping = {
            "notification_channel": "notification_channel_id",
            "leadership_channel": "leadership_channel_id",
            "loa_notification_channel": "loa_notification_channel_id"
        }
        
        field_name = field_mapping[self.channel_type]
        
        if channel_id == "none":
            # Clear the channel setting
            await self.bot.db.update_server_config(self.guild.id, **{field_name: None})
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ Channel Cleared",
                value=f"{self.channel_type.replace('_', ' ').title()} has been cleared.",
                inline=False
            )
        else:
            channel = self.guild.get_channel(int(channel_id))
            if channel:
                await self.bot.db.update_server_config(self.guild.id, **{field_name: channel.id})
                
                embed = await self.parent_view.create_main_embed()
                embed.add_field(
                    name="✅ Channel Set",
                    value=f"{self.channel_type.replace('_', ' ').title()} set to {channel.mention}",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Channel not found.",
                    color=discord.Color.red()
                )
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
    
    @discord.ui.button(label="Back to Main Menu", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class UserSelectionView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, user_type: str, parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.user_type = user_type
        self.parent_view = parent_view
        
        # Get members and create select options (limit to 25, exclude bots)
        members = [member for member in guild.members if not member.bot][:23]
        options = [
            discord.SelectOption(
                label=member.display_name,
                description=f"@{member.name}",
                value=str(member.id)
            )
            for member in members
        ]
        
        # Add "None" option
        options.append(discord.SelectOption(
            label="None (Clear Setting)",
            description="Remove the current user setting",
            value="none"
        ))
        
        if options:
            self.user_select.options = options
        else:
            self.user_select.disabled = True
    
    @discord.ui.select(placeholder="Choose a user...")
    async def user_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle user selection"""
        user_id = select.values[0]
        
        if user_id == "none":
            # Clear all DM users
            await self.bot.db.clear_dm_users(self.guild.id)
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ DM Users Cleared",
                value="All DM users have been cleared.",
                inline=False
            )
        else:
            user = self.guild.get_member(int(user_id))
            if user:
                # Use the new DM users system instead of dm_user_id
                await self.bot.db.add_dm_user(self.guild.id, user.id)
                
                embed = await self.parent_view.create_main_embed()
                embed.add_field(
                    name="✅ DM User Added",
                    value=f"DM user added: {user.mention}",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="User not found.",
                    color=discord.Color.red()
                )
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
    
    @discord.ui.button(label="Back to Main Menu", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class RoleSearchModal(discord.ui.Modal):
    def __init__(self, bot, guild: discord.Guild, parent_view: ConfigurationMenuView):
        super().__init__(title="Search for Role")
        self.bot = bot
        self.guild = guild
        self.parent_view = parent_view
        
        self.role_input = discord.ui.TextInput(
            label="Role Name or ID",
            placeholder="Type role name or ID to search...",
            required=True,
            max_length=100
        )
        self.add_item(self.role_input)
        
        self.role_type = discord.ui.TextInput(
            label="Role Type",
            placeholder="Type 'officer' or 'loa_notification'",
            required=True,
            max_length=50
        )
        self.add_item(self.role_type)
    
    async def on_submit(self, interaction: discord.Interaction):
        search_term = self.role_input.value.strip().lower()
        role_type_input = self.role_type.value.strip().lower()
        
        # Map shortcuts to full role types
        role_type_mapping = {
            'officer': 'officer',
            'loa_notification': 'loa_notification', 
            'loa': 'loa_notification',  # Shortcut for loa_notification
            'l': 'loa_notification',   # Even shorter shortcut
        }
        
        if role_type_input not in role_type_mapping:
            await interaction.response.send_message(
                "❌ Invalid role type. Please use 'officer', 'loa_notification', 'loa', or 'l'.", ephemeral=True
            )
            return
        
        # Get the actual role type from the mapping
        role_type = role_type_mapping[role_type_input]
        
        # Search for roles
        matching_roles = []
        
        # Try to find by ID first
        if search_term.isdigit():
            role = self.guild.get_role(int(search_term))
            if role:
                matching_roles.append(role)
        
        # Search by name (partial match)
        if not matching_roles:
            for role in self.guild.roles:
                if search_term in role.name.lower() and not role.is_default() and not role.managed:
                    matching_roles.append(role)
        
        if not matching_roles:
            await interaction.response.send_message(
                f"❌ No roles found matching '{self.role_input.value}'", ephemeral=True
            )
            return
        
        # If multiple matches, show selection view
        if len(matching_roles) > 1:
            view = RoleSelectionResultView(self.bot, self.guild, matching_roles, role_type, self.parent_view)
            embed = discord.Embed(
                title=f"🔍 Role Search Results ({len(matching_roles)} found)",
                description=f"Multiple roles found for '{self.role_input.value}'. Select one below:",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # Single match, apply directly
            role = matching_roles[0]
            field_name = "officer_role_id" if role_type == "officer" else "loa_notification_role_id"
            await self.bot.db.update_server_config(self.guild.id, **{field_name: role.id})
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ Role Set",
                value=f"{'Officer role' if role_type == 'officer' else 'LOA notification role'} set to {role.mention}",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ChannelSearchModal(discord.ui.Modal):
    def __init__(self, bot, guild: discord.Guild, parent_view: ConfigurationMenuView):
        super().__init__(title="Search for Channel")
        self.bot = bot
        self.guild = guild
        self.parent_view = parent_view
        
        self.channel_input = discord.ui.TextInput(
            label="Channel Name or ID",
            placeholder="Type channel name or ID to search...",
            required=True,
            max_length=100
        )
        self.add_item(self.channel_input)
        
        self.channel_type = discord.ui.TextInput(
            label="Channel Type",
            placeholder="Type 'notification', 'leadership', or 'loa_notification'",
            required=True,
            max_length=50
        )
        self.add_item(self.channel_type)
    
    async def on_submit(self, interaction: discord.Interaction):
        search_term = self.channel_input.value.strip().lower()
        channel_type_input = self.channel_type.value.strip().lower()
        
        # Map shortcuts to full channel types
        channel_type_mapping = {
            'notification': 'notification',
            'leadership': 'leadership',
            'loa_notification': 'loa_notification',
            'loa': 'loa_notification',  # Shortcut for loa_notification
            'l': 'loa_notification',   # Even shorter shortcut
        }
        
        if channel_type_input not in channel_type_mapping:
            await interaction.response.send_message(
                "❌ Invalid channel type. Please use 'notification', 'leadership', 'loa_notification', 'loa', or 'l'.", ephemeral=True
            )
            return
        
        # Get the actual channel type from the mapping
        channel_type = channel_type_mapping[channel_type_input]
        
        # Search for channels
        matching_channels = []
        
        # Try to find by ID first
        if search_term.isdigit():
            channel = self.guild.get_channel(int(search_term))
            if channel and isinstance(channel, discord.TextChannel):
                matching_channels.append(channel)
        
        # Search by name (partial match)
        if not matching_channels:
            for channel in self.guild.text_channels:
                if (search_term in channel.name.lower() and 
                    channel.permissions_for(self.guild.me).send_messages):
                    matching_channels.append(channel)
        
        if not matching_channels:
            await interaction.response.send_message(
                f"❌ No channels found matching '{self.channel_input.value}'", ephemeral=True
            )
            return
        
        # If multiple matches, show selection view
        if len(matching_channels) > 1:
            view = ChannelSelectionResultView(self.bot, self.guild, matching_channels, channel_type, self.parent_view)
            embed = discord.Embed(
                title=f"🔍 Channel Search Results ({len(matching_channels)} found)",
                description=f"Multiple channels found for '{self.channel_input.value}'. Select one below:",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # Single match, apply directly
            channel = matching_channels[0]
            field_mapping = {
                "notification": "notification_channel_id",
                "leadership": "leadership_channel_id",
                "loa_notification": "loa_notification_channel_id"
            }
            field_name = field_mapping[channel_type]
            await self.bot.db.update_server_config(self.guild.id, **{field_name: channel.id})
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ Channel Set",
                value=f"{channel_type.replace('_', ' ').title()} channel set to {channel.mention}",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=self.parent_view)


class UserSearchModal(discord.ui.Modal):
    def __init__(self, bot, guild: discord.Guild, parent_view: ConfigurationMenuView):
        super().__init__(title="Search for User")
        self.bot = bot
        self.guild = guild
        self.parent_view = parent_view
        
        self.user_input = discord.ui.TextInput(
            label="User Name or ID",
            placeholder="Type username, display name, or ID to search...",
            required=True,
            max_length=100
        )
        self.add_item(self.user_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        search_term = self.user_input.value.strip().lower()
        
        # Search for users
        matching_users = []
        
        # Try to find by ID first
        if search_term.isdigit():
            user = self.guild.get_member(int(search_term))
            if user and not user.bot:
                matching_users.append(user)
        
        # Search by username and display name (partial match)
        if not matching_users:
            for member in self.guild.members:
                if (not member.bot and 
                    (search_term in member.name.lower() or 
                     search_term in member.display_name.lower())):
                    matching_users.append(member)
        
        if not matching_users:
            await interaction.response.send_message(
                f"❌ No users found matching '{self.user_input.value}'", ephemeral=True
            )
            return
        
        # If multiple matches, show selection view
        if len(matching_users) > 1:
            view = UserSelectionResultView(self.bot, self.guild, matching_users, self.parent_view)
            embed = discord.Embed(
                title=f"🔍 User Search Results ({len(matching_users)} found)",
                description=f"Multiple users found for '{self.user_input.value}'. Select one below:",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # Single match, apply directly
            user = matching_users[0]
            # Use the new DM users system instead of dm_user_id
            await self.bot.db.add_dm_user(self.guild.id, user.id)
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ DM User Added",
                value=f"DM user added: {user.mention}",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=self.parent_view)


class RoleSelectionResultView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, roles: List[discord.Role], role_type: str, parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.roles = roles
        self.role_type = role_type
        self.parent_view = parent_view
        
        # Create select options for up to 25 roles
        options = [
            discord.SelectOption(
                label=role.name,
                description=f"Members: {len(role.members)}",
                value=str(role.id)
            )
            for role in roles[:25]
        ]
        
        if options:
            self.role_select.options = options
        else:
            self.role_select.disabled = True
    
    @discord.ui.select(placeholder="Choose a role from search results...")
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        role_id = int(select.values[0])
        role = self.guild.get_role(role_id)
        
        if role:
            field_name = "officer_role_id" if self.role_type == "officer" else "loa_notification_role_id"
            await self.bot.db.update_server_config(self.guild.id, **{field_name: role.id})
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ Role Set",
                value=f"{'Officer role' if self.role_type == 'officer' else 'LOA notification role'} set to {role.mention}",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Role not found.",
                color=discord.Color.red()
            )
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
    
    @discord.ui.button(label="Back to Main Menu", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ChannelSelectionResultView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, channels: List[discord.TextChannel], channel_type: str, parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.channels = channels
        self.channel_type = channel_type
        self.parent_view = parent_view
        
        # Create select options for up to 25 channels
        options = [
            discord.SelectOption(
                label=f"#{channel.name}",
                description=f"Category: {channel.category.name if channel.category else 'None'}",
                value=str(channel.id)
            )
            for channel in channels[:25]
        ]
        
        if options:
            self.channel_select.options = options
        else:
            self.channel_select.disabled = True
    
    @discord.ui.select(placeholder="Choose a channel from search results...")
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        channel_id = int(select.values[0])
        channel = self.guild.get_channel(channel_id)
        
        if channel:
            field_mapping = {
                "notification": "notification_channel_id",
                "leadership": "leadership_channel_id",
                "loa_notification": "loa_notification_channel_id"
            }
            field_name = field_mapping[self.channel_type]
            await self.bot.db.update_server_config(self.guild.id, **{field_name: channel.id})
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ Channel Set",
                value=f"{self.channel_type.replace('_', ' ').title()} channel set to {channel.mention}",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="Channel not found.",
                color=discord.Color.red()
            )
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
    
    @discord.ui.button(label="Back to Main Menu", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class UserSelectionResultView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, users: List[discord.Member], parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.users = users
        self.parent_view = parent_view
        
        # Create select options for up to 25 users
        options = [
            discord.SelectOption(
                label=user.display_name,
                description=f"@{user.name}",
                value=str(user.id)
            )
            for user in users[:25]
        ]
        
        if options:
            self.user_select.options = options
        else:
            self.user_select.disabled = True
    
    @discord.ui.select(placeholder="Choose a user from search results...")
    async def user_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        user_id = int(select.values[0])
        user = self.guild.get_member(user_id)
        
        if user:
            # Use the new DM users system instead of dm_user_id
            await self.bot.db.add_dm_user(self.guild.id, user.id)
            
            embed = await self.parent_view.create_main_embed()
            embed.add_field(
                name="✅ DM User Added",
                value=f"DM user added: {user.mention}",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="User not found.",
                color=discord.Color.red()
            )
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
    
    @discord.ui.button(label="Back to Main Menu", style=discord.ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class RoleConfigurationView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.parent_view = parent_view
    
    @discord.ui.button(label="🔍 Search for Role", style=discord.ButtonStyle.primary, emoji="🔍")
    async def search_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open role search modal"""
        modal = RoleSearchModal(self.bot, self.guild, self.parent_view)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 Browse Officer Roles", style=discord.ButtonStyle.secondary, emoji="👮")
    async def browse_officer_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show officer role dropdown"""
        view = RoleSelectionView(self.bot, self.guild, "officer_role", self.parent_view)
        embed = discord.Embed(
            title="👮 Select Officer Role",
            description="Choose from the roles in your server:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="📋 Browse LOA Notification Roles", style=discord.ButtonStyle.secondary, emoji="🔔")
    async def browse_loa_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show LOA notification role dropdown"""
        view = RoleSelectionView(self.bot, self.guild, "loa_notification_role", self.parent_view)
        embed = discord.Embed(
            title="🔔 Select LOA Notification Role",
            description="Choose from the roles in your server:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="⬅️ Back to Main Menu", style=discord.ButtonStyle.gray)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ChannelConfigurationView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.parent_view = parent_view
    
    @discord.ui.button(label="🔍 Search for Channel", style=discord.ButtonStyle.primary, emoji="🔍")
    async def search_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open channel search modal"""
        modal = ChannelSearchModal(self.bot, self.guild, self.parent_view)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 Browse Notification Channels", style=discord.ButtonStyle.secondary, emoji="📢")
    async def browse_notification_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show notification channel dropdown"""
        view = ChannelSelectionView(self.bot, self.guild, "notification_channel", self.parent_view)
        embed = discord.Embed(
            title="📢 Select Notification Channel",
            description="Choose from the channels in your server:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="📋 Browse Leadership Channels", style=discord.ButtonStyle.secondary, emoji="🏛️")
    async def browse_leadership_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show leadership channel dropdown"""
        view = ChannelSelectionView(self.bot, self.guild, "leadership_channel", self.parent_view)
        embed = discord.Embed(
            title="🏛️ Select Leadership Channel",
            description="Choose from the channels in your server:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="📋 Browse LOA Notification Channels", style=discord.ButtonStyle.secondary, emoji="📨")
    async def browse_loa_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show LOA notification channel dropdown"""
        view = ChannelSelectionView(self.bot, self.guild, "loa_notification_channel", self.parent_view)
        embed = discord.Embed(
            title="📨 Select LOA Notification Channel",
            description="Choose from the channels in your server:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="⬅️ Back to Main Menu", style=discord.ButtonStyle.gray)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class UserConfigurationView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild, parent_view: ConfigurationMenuView):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.parent_view = parent_view
    
    @discord.ui.button(label="🔍 Search for User", style=discord.ButtonStyle.primary, emoji="🔍")
    async def search_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open user search modal"""
        modal = UserSearchModal(self.bot, self.guild, self.parent_view)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 Browse Users", style=discord.ButtonStyle.secondary, emoji="👥")
    async def browse_users(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show user dropdown"""
        view = UserSelectionView(self.bot, self.guild, "dm_user", self.parent_view)
        embed = discord.Embed(
            title="💬 Select DM User",
            description="Choose from the members in your server:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="⬅️ Back to Main Menu", style=discord.ButtonStyle.gray)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.parent_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


async def setup(bot):
    await bot.add_cog(ConfigurationSystem(bot))

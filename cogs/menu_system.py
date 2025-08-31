import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import List, Optional, Dict, Any
import asyncio
from utils.contribution_audit_helpers import ContributionAuditHelpers

class MainMenuView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.bot = bot
        self.user_id = user_id
        self.is_officer = False
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the user who opened the menu can interact with it"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This menu belongs to someone else. Use `/menu` to open your own.", 
                ephemeral=True
            )
            return False
        return True
    
    async def check_officer_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has officer permissions"""
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return False
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        return officer_role and officer_role in interaction.user.roles
    
    @discord.ui.button(label="📦 Contributions", style=discord.ButtonStyle.primary, emoji="📦")
    async def contributions_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ContributionsMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="📦 Contributions Menu",
            description="**Manage member contributions to the organization**\n\n"
                       "• Record new contributions\n"
                       "• View contribution statistics\n"
                       "• Browse by categories\n"
                       "• Track member participation",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Select an option below")
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🗄️ Database", style=discord.ButtonStyle.secondary, emoji="🗄️")
    async def database_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_officer = await self.check_officer_permissions(interaction)
        if not is_officer:
            await interaction.response.send_message(
                "❌ Database management is only available to officers.", 
                ephemeral=True
            )
            return
        
        view = DatabaseMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🗄️ Database Management Menu",
            description="**Manage and analyze contribution data** (Officers Only)\n\n"
                       "• Generate comprehensive reports\n"
                       "• Create data archives\n"
                       "• Edit item quantities\n"
                       "• View change history\n"
                       "• Export data for analysis",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Select an option below")
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="👥 Membership", style=discord.ButtonStyle.secondary, emoji="👥")
    async def membership_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MembershipMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="👥 Membership Menu",
            description="**Manage organization membership**\n\n"
                       "• Add new members\n"
                       "• View member roster\n"
                       "• Update member information\n"
                       "• Track member status",
            color=discord.Color.green()
        )
        embed.set_footer(text="Select an option below")
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="📅 Leave of Absence", style=discord.ButtonStyle.secondary, emoji="📅")
    async def loa_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LOAMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="📅 Leave of Absence Menu",
            description="**Manage LOA requests and tracking**\n\n"
                       "• Submit LOA request\n"
                       "• View active LOAs\n"
                       "• End LOA early\n"
                       "• LOA status tracking",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Select an option below")
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="💬 Messaging", style=discord.ButtonStyle.secondary, emoji="💬")
    async def messaging_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_officer = await self.check_officer_permissions(interaction)
        if not is_officer:
            await interaction.response.send_message(
                "❌ Messaging features are only available to officers.", 
                ephemeral=True
            )
            return
        
        view = MessagingMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="💬 Messaging Menu",
            description="**Direct messaging and communication tools** (Officers Only)\n\n"
                       "• Send messages to members\n"
                       "• Message entire roles\n"
                       "• View message transcripts\n"
                       "• Search conversation history",
            color=discord.Color.red()
        )
        embed.set_footer(text="Select an option below")
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="⚙️ Configuration", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def config_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_officer = await self.check_officer_permissions(interaction)
        if not is_officer:
            await interaction.response.send_message(
                "❌ Configuration is only available to officers.", 
                ephemeral=True
            )
            return
        
        view = ConfigMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="⚙️ Configuration Menu",
            description="**Bot setup and configuration** (Officers Only)\n\n"
                       "• Set officer role\n"
                       "• Configure channels\n"
                       "• Manage categories\n"
                       "• Backup & export settings",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Select an option below")
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, emoji="🏠", row=2)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.create_main_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="👋 Menu Closed",
            description="The menu has been closed. Use `/menu` to open it again anytime.",
            color=discord.Color.greyple()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    async def create_main_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Create the main menu embed with status information"""
        is_officer = await self.check_officer_permissions(interaction)
        
        embed = discord.Embed(
            title="🏠 Thanatos Bot - Main Menu",
            description="**Welcome to the comprehensive bot management system!**\n\n"
                       "Use the buttons below to access different features:",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Add user status
        status = "👑 Officer" if is_officer else "👤 Member"
        embed.add_field(
            name="Your Status",
            value=status,
            inline=True
        )
        
        # Add quick stats
        try:
            contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
            total_contributions = len(contributions) if contributions else 0
            
            embed.add_field(
                name="Quick Stats",
                value=f"📦 Total Contributions: {total_contributions}",
                inline=True
            )
        except:
            pass
        
        # Add available features
        features = [
            "📦 **Contributions** - Record and manage contributions",
            "👥 **Membership** - Member management tools",
            "📅 **LOA System** - Leave of absence management",
        ]
        
        if is_officer:
            features.extend([
                "🗄️ **Database** - Data management & analysis",
                "💬 **Messaging** - Direct messaging tools",
                "⚙️ **Configuration** - Bot setup & settings"
            ])
        
        embed.add_field(
            name="Available Features",
            value="\n".join(features),
            inline=False
        )
        
        embed.set_footer(text=f"Thanatos Bot Menu • User: {interaction.user.display_name}")
        
        return embed

class ContributionsMenuView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="📝 Record Contribution", style=discord.ButtonStyle.primary)
    async def record_contribution(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get the contribute command from the contributions cog
        contribute_cog = self.bot.get_cog('ContributionSystem')
        if contribute_cog:
            await contribute_cog.contribute_command.callback(contribute_cog, interaction)
        else:
            await interaction.response.send_message("❌ Contributions system not available.", ephemeral=True)
    
    @discord.ui.button(label="📊 View Statistics", style=discord.ButtonStyle.secondary)
    async def view_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        contribute_cog = self.bot.get_cog('ContributionSystem')
        if contribute_cog:
            await contribute_cog.view_contributions.callback(contribute_cog, interaction)
        else:
            await interaction.response.send_message("❌ Contributions system not available.", ephemeral=True)
    
    @discord.ui.button(label="📋 List Categories", style=discord.ButtonStyle.secondary)
    async def list_categories(self, interaction: discord.Interaction, button: discord.ui.Button):
        contribute_cog = self.bot.get_cog('ContributionSystem')
        if contribute_cog:
            await contribute_cog.list_contribution_categories.callback(contribute_cog, interaction)
        else:
            await interaction.response.send_message("❌ Contributions system not available.", ephemeral=True)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        main_view = MainMenuView(self.bot, self.user_id)
        embed = await main_view.create_main_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=main_view)

class DatabaseMenuView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="📋 Generate Summary", style=discord.ButtonStyle.primary)
    async def database_summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.database_summary.callback(db_cog, interaction, format="embed")
        else:
            await interaction.response.send_message("❌ Database management system not available.", ephemeral=True)
    
    @discord.ui.button(label="📦 Create Archive", style=discord.ButtonStyle.secondary)
    async def create_archive(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.create_archive.callback(db_cog, interaction)
        else:
            await interaction.response.send_message("❌ Database management system not available.", ephemeral=True)
    
    @discord.ui.button(label="📚 View Archives", style=discord.ButtonStyle.secondary)
    async def view_archives(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.view_archives.callback(db_cog, interaction)
        else:
            await interaction.response.send_message("❌ Database management system not available.", ephemeral=True)
    
    @discord.ui.button(label="🔧 Edit Quantities", style=discord.ButtonStyle.secondary)
    async def edit_quantity(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.edit_quantity.callback(db_cog, interaction)
        else:
            await interaction.response.send_message("❌ Database management system not available.", ephemeral=True)
    
    @discord.ui.button(label="📊 Export Data", style=discord.ButtonStyle.secondary, row=1)
    async def export_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Create export options view
        view = ExportOptionsView(self.bot, self.user_id)
        embed = discord.Embed(
            title="📊 Data Export Options",
            description="Choose your preferred export format:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        main_view = MainMenuView(self.bot, self.user_id)
        embed = await main_view.create_main_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=main_view)

class ExportOptionsView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="📄 Text File", style=discord.ButtonStyle.primary)
    async def export_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.database_summary.callback(db_cog, interaction, format="text")
        else:
            await interaction.response.send_message("❌ Database management system not available.", ephemeral=True)
    
    @discord.ui.button(label="📊 JSON File", style=discord.ButtonStyle.primary)
    async def export_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.database_summary.callback(db_cog, interaction, format="json")
        else:
            await interaction.response.send_message("❌ Database management system not available.", ephemeral=True)
    
    @discord.ui.button(label="🔙 Back to Database", style=discord.ButtonStyle.secondary)
    async def back_to_database(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DatabaseMenuView(self.bot, self.user_id)
        embed = discord.Embed(
            title="🗄️ Database Management Menu",
            description="**Manage and analyze contribution data** (Officers Only)\n\n"
                       "• Generate comprehensive reports\n"
                       "• Create data archives\n"
                       "• Edit item quantities\n"
                       "• View change history\n"
                       "• Export data for analysis",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Select an option below")
        await interaction.response.edit_message(embed=embed, view=view)

class MembershipMenuView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="📋 Sync Membership", style=discord.ButtonStyle.primary)
    async def sync_membership(self, interaction: discord.Interaction, button: discord.ui.Button):
        member_cog = self.bot.get_cog('MembershipSystem')
        if member_cog:
            await member_cog.sync_membership.callback(member_cog, interaction)
        else:
            await interaction.response.send_message("❌ Membership system not available.", ephemeral=True)
    
    @discord.ui.button(label="🔍 Debug Roles", style=discord.ButtonStyle.secondary)
    async def debug_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        member_cog = self.bot.get_cog('MembershipSystem')
        if member_cog:
            await member_cog.debug_roles.callback(member_cog, interaction)
        else:
            await interaction.response.send_message("❌ Membership system not available.", ephemeral=True)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        main_view = MainMenuView(self.bot, self.user_id)
        embed = await main_view.create_main_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=main_view)

class LOAMenuView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="📝 Submit LOA", style=discord.ButtonStyle.primary)
    async def submit_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.loa_command.callback(loa_cog, interaction)
        else:
            await interaction.response.send_message("❌ LOA system not available.", ephemeral=True)
    
    @discord.ui.button(label="📋 View My LOA", style=discord.ButtonStyle.secondary)
    async def view_my_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.check_loa_status.callback(loa_cog, interaction, member=interaction.user)
        else:
            await interaction.response.send_message("❌ LOA system not available.", ephemeral=True)
    
    @discord.ui.button(label="⏹️ End LOA Early", style=discord.ButtonStyle.secondary)
    async def end_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.loa_cancel.callback(loa_cog, interaction)
        else:
            await interaction.response.send_message("❌ LOA system not available.", ephemeral=True)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        main_view = MainMenuView(self.bot, self.user_id)
        embed = await main_view.create_main_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=main_view)

class MessagingMenuView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="📜 DM Commands Help", style=discord.ButtonStyle.primary)
    async def dm_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💬 Direct Messaging Commands",
            description="Available DM commands for officers:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📤 Send Message",
            value="`/dm_user <user> <message>` - Send a DM to a user",
            inline=False
        )
        
        embed.add_field(
            name="📊 View Transcripts",
            value="`/view_transcript <user>` - View DM history with a user",
            inline=False
        )
        
        embed.add_field(
            name="🔍 Search Messages",
            value="`/search_transcript <query>` - Search DM transcripts",
            inline=False
        )
        
        embed.set_footer(text="Use the slash commands directly for full functionality")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="⚙️ DM Configuration", style=discord.ButtonStyle.secondary)
    async def dm_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚙️ DM System Configuration",
            description="Configure the direct messaging system:",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="📥 Add DM User",
            value="`/add_dm_user <user>` - Add user to receive DM notifications",
            inline=False
        )
        
        embed.add_field(
            name="📤 Remove DM User",
            value="`/remove_dm_user <user>` - Remove user from DM notifications",
            inline=False
        )
        
        embed.add_field(
            name="📋 List DM Users",
            value="`/list_dm_users` - Show all configured DM users",
            inline=False
        )
        
        embed.set_footer(text="Use the slash commands to configure DM settings")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        main_view = MainMenuView(self.bot, self.user_id)
        embed = await main_view.create_main_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=main_view)

class ConfigMenuView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="⚙️ Config Commands", style=discord.ButtonStyle.primary)
    async def config_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚙️ Configuration Commands",
            description="Available configuration commands for admins:",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="👑 Officer Role",
            value="`/set_officer_role <role>` - Set officer permissions role\n"
                  "`/clear_officer_role` - Remove officer role",
            inline=False
        )
        
        embed.add_field(
            name="📢 Channels",
            value="`/config_notification_channel <channel>` - Set notification channel\n"
                  "`/config_leadership_channel <channel>` - Set leadership channel",
            inline=False
        )
        
        embed.add_field(
            name="👥 Membership",
            value="`/config_membership_roles <roles>` - Set membership roles (comma-separated)",
            inline=False
        )
        
        embed.set_footer(text="Admin permissions required for configuration commands")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📤 Export Backup", style=discord.ButtonStyle.secondary)
    async def export_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        backup_cog = self.bot.get_cog('BackupSystem')
        if backup_cog:
            await backup_cog.export_data.callback(backup_cog, interaction, format_type="both")
        else:
            await interaction.response.send_message("❌ Backup system not available.", ephemeral=True)
    
    @discord.ui.button(label="🏠 Main Menu", style=discord.ButtonStyle.success, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        main_view = MainMenuView(self.bot, self.user_id)
        embed = await main_view.create_main_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=main_view)

class MenuSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="menu", description="Open the main bot menu interface")
    async def main_menu(self, interaction: discord.Interaction):
        """Open the main menu interface"""
        await interaction.response.defer(ephemeral=True)
        
        view = MainMenuView(self.bot, interaction.user.id)
        embed = await view.create_main_embed(interaction)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="quick_contribute", description="Quick access to contribution recording")
    async def quick_contribute(self, interaction: discord.Interaction):
        """Quick access to contribution recording"""
        contribute_cog = self.bot.get_cog('ContributionSystem')
        if contribute_cog:
            await contribute_cog.contribute_command.callback(contribute_cog, interaction)
        else:
            await interaction.response.send_message("❌ Contributions system not available.", ephemeral=True)
    
    @app_commands.command(name="quick_loa", description="Quick access to LOA submission")
    async def quick_loa(self, interaction: discord.Interaction):
        """Quick access to LOA submission"""
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.loa_command.callback(loa_cog, interaction)
        else:
            await interaction.response.send_message("❌ LOA system not available.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MenuSystem(bot))

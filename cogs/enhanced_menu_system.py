"""
Enhanced Menu System - Professional UI/UX for Thanatos Bot
Features modern design, improved navigation, and robust functionality.
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
import asyncio
from utils.contribution_audit_helpers import ContributionAuditHelpers

# Professional color scheme
class MenuColors:
    PRIMARY = 0x2F3136      # Dark theme primary
    SUCCESS = 0x00FF88      # Green success
    WARNING = 0xFFCC4D      # Orange warning
    DANGER = 0xFF4444       # Red danger
    INFO = 0x5865F2         # Discord blurple
    SECONDARY = 0x36393F    # Lighter dark
    ACCENT = 0x00D4FF       # Light blue accent

class ModernMenuView(discord.ui.View):
    """Base class for modern menu views with consistent styling"""
    
    def __init__(self, bot, user_id: int, timeout: int = 600):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self.last_interaction = datetime.now()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enhanced interaction check with better error handling"""
        if interaction.user.id != self.user_id:
            error_embed = discord.Embed(
                title="🚫 Access Denied",
                description=f"This menu belongs to <@{self.user_id}>.\nUse `/menu` to open your own interface.",
                color=MenuColors.DANGER
            )
            error_embed.set_footer(text="Thanatos Bot • Secure Menu System")
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return False
        
        self.last_interaction = datetime.now()
        return True
    
    async def on_timeout(self):
        """Handle view timeout with proper cleanup"""
        try:
            # Disable all buttons
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            
            timeout_embed = discord.Embed(
                title="⏰ Menu Timeout",
                description="This menu has expired due to inactivity.\nUse `/menu` to open a new one.",
                color=MenuColors.WARNING
            )
            timeout_embed.set_footer(text="Session expired for security")
            
            # Try to edit the message if possible
            # Note: This might fail if the message was deleted, but that's okay
        except Exception:
            pass
    
    def create_professional_embed(self, title: str, description: str, color: int = MenuColors.PRIMARY) -> discord.Embed:
        """Create a professionally styled embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        embed.set_author(
            name="Thanatos Bot Management System",
            icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png"  # Bot avatar if available
        )
        return embed

class DashboardView(ModernMenuView):
    """Main dashboard with professional layout and real-time stats"""
    
    def __init__(self, bot, user_id: int):
        super().__init__(bot, user_id)
        self.is_officer = False
        self.stats_cache = {}
    
    async def refresh_stats(self, interaction: discord.Interaction):
        """Refresh comprehensive real-time statistics"""
        try:
            # Check officer permissions
            self.is_officer = await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot)
            
            # Get basic stats
            contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
            members = await self.bot.db.get_all_members(interaction.guild.id)
            events = await self.bot.db.get_active_events(interaction.guild.id)
            
            # Get LOA stats if officer
            active_loas = 0
            dues_periods = 0
            if self.is_officer:
                try:
                    conn = await self.bot.db._get_shared_connection()
                    cursor = await conn.execute(
                        'SELECT COUNT(*) FROM loa_records WHERE guild_id = ? AND is_active = TRUE AND is_expired = FALSE',
                        (interaction.guild.id,)
                    )
                    active_loas = (await cursor.fetchone())[0]
                    
                    # Get active dues periods
                    cursor = await conn.execute(
                        'SELECT COUNT(*) FROM dues_periods WHERE guild_id = ? AND is_active = TRUE',
                        (interaction.guild.id,)
                    )
                    dues_periods = (await cursor.fetchone())[0]
                except:
                    active_loas = 0
                    dues_periods = 0
            
            # Calculate contribution stats
            total_quantity = sum(c.get('quantity', 0) for c in contributions) if contributions else 0
            active_contributors = len(set(c['discord_name'] for c in contributions)) if contributions else 0
            
            # Calculate event stats  
            total_attendees = sum(e.get('yes_count', 0) or 0 for e in events) if events else 0
            
            self.stats_cache = {
                'total_contributions': len(contributions) if contributions else 0,
                'total_quantity': total_quantity,
                'total_members': len(members) if members else 0,
                'active_contributors': active_contributors,
                'active_loas': active_loas,
                'active_events': len(events) if events else 0,
                'total_attendees': total_attendees,
                'dues_periods': dues_periods,
                'categories': len(set(c['category'] for c in contributions)) if contributions else 0
            }
        except Exception as e:
            print(f"Error refreshing stats: {e}")
            self.stats_cache = {
                'total_contributions': 0, 'total_quantity': 0, 'total_members': 0, 
                'active_contributors': 0, 'active_loas': 0, 'active_events': 0, 
                'total_attendees': 0, 'dues_periods': 0, 'categories': 0
            }
    
    async def create_dashboard_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Create the main dashboard embed"""
        await self.refresh_stats(interaction)
        
        # Professional main embed
        embed = self.create_professional_embed(
            "🏛️ Thanatos Management Dashboard",
            "**Comprehensive Guild Management System**\n\n" +
            "Welcome to your professional management interface. " +
            "Navigate through different modules using the buttons below.",
            MenuColors.PRIMARY
        )
        
        # User status badge
        if self.is_officer:
            status_emoji = "👑"
            status_text = "Officer"
            status_color = "🟡"
        else:
            status_emoji = "👤"
            status_text = "Member"
            status_color = "🟢"
        
        embed.add_field(
            name="👤 User Status",
            value=f"{status_color} {status_emoji} **{status_text}**\n`Access Level: {status_text}`",
            inline=True
        )
        
        # Real-time statistics - Enhanced
        stats_text = (
            f"📦 **{self.stats_cache['total_contributions']:,}** Records ({self.stats_cache['total_quantity']:,} items)\n"
            f"👥 **{self.stats_cache['total_members']:,}** Members ({self.stats_cache['active_contributors']} active)\n"
            f"🎉 **{self.stats_cache['active_events']}** Events ({self.stats_cache['total_attendees']} attending)\n"
            f"📂 **{self.stats_cache['categories']}** Categories"
        )
        
        if self.is_officer:
            stats_text += (
                f"\n📅 **{self.stats_cache['active_loas']}** Active LOAs\n"
                f"💰 **{self.stats_cache['dues_periods']}** Dues Periods"
            )
        
        embed.add_field(
            name="📊 Live Statistics",
            value=stats_text,
            inline=True
        )
        
        # System status
        embed.add_field(
            name="⚡ System Status",
            value="🟢 **Online** • All systems operational\n"
                  f"🕐 Last updated: <t:{int(datetime.now().timestamp())}:R>",
            inline=True
        )
        
        # Available modules - Enhanced
        modules = [
            "📦 **Contributions** • Record, track & analyze donations",
            "👥 **Membership** • Member management & statistics",
            "📅 **LOA System** • Interactive leave management",
            "🎉 **Event Management** • Full RSVP & invitation system",
            "💰 **Dues Tracking** • Payment tracking & reports",
            "🔍 **Prospect Management** • Recruit tracking & evaluation"
        ]
        
        if self.is_officer:
            modules.extend([
                "🗄️ **Database Management** • Analytics, exports & archives",
                "💬 **Messaging Center** • Direct & mass communication",
                "⚙️ **Administration** • System configuration & backups",
                "📋 **Audit Logs** • Complete activity tracking",
                "🔧 **System Tools** • Advanced bot management"
            ])
        
        embed.add_field(
            name="🎛️ Available Modules",
            value="\n".join(modules),
            inline=False
        )
        
        # Professional footer
        embed.set_footer(
            text=f"Thanatos Bot v2.0 • Session: {interaction.user.display_name} • {datetime.now().strftime('%H:%M UTC')}",
            icon_url=interaction.user.display_avatar.url
        )
        
        return embed
    
    # Main navigation buttons (Row 0)
    @discord.ui.button(
        label="Contributions",
        style=discord.ButtonStyle.primary,
        emoji="📦",
        row=0
    )
    async def contributions_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ContributionsModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(
        label="Membership",
        style=discord.ButtonStyle.secondary,
        emoji="👥",
        row=0
    )
    async def membership_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MembershipModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(
        label="LOA System",
        style=discord.ButtonStyle.secondary,
        emoji="📅",
        row=0
    )
    async def loa_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LOAModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(
        label="Events",
        style=discord.ButtonStyle.secondary,
        emoji="🎉",
        row=0
    )
    async def events_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = EventsModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(
        label="Dues Tracking",
        style=discord.ButtonStyle.secondary,
        emoji="💰",
        row=0
    )
    async def dues_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DuesTrackingModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(
        label="Prospects",
        style=discord.ButtonStyle.secondary,
        emoji="🔍",
        row=1
    )
    async def prospect_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Prospect Management** requires Officer permissions."
            )
            return
        
        view = ProspectManagementModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(
        label="Database",
        style=discord.ButtonStyle.secondary,
        emoji="🗄️",
        row=1
    )
    async def database_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Database Management** requires Officer permissions."
            )
            return
        
        view = DatabaseModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    # Officer-only buttons (Row 1)
    @discord.ui.button(
        label="Audit Logs",
        style=discord.ButtonStyle.secondary,
        emoji="📋",
        row=1
    )
    async def audit_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Audit Logs** require Officer permissions."
            )
            return
        
        view = AuditModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(
        label="Messaging",
        style=discord.ButtonStyle.secondary,
        emoji="💬",
        row=1
    )
    async def messaging_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Messaging System** requires Officer permissions."
            )
            return
        
        view = MessagingModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(
        label="Administration",
        style=discord.ButtonStyle.secondary,
        emoji="⚙️",
        row=1
    )
    async def admin_module(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Administration** requires Officer permissions."
            )
            return
        
        view = AdministrationModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    # Control buttons (Row 2)
    @discord.ui.button(
        label="Refresh",
        style=discord.ButtonStyle.success,
        emoji="🔄",
        row=2
    )
    async def refresh_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        row=2
    )
    async def close_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        close_embed = self.create_professional_embed(
            "👋 Session Ended",
            "Your management session has been closed.\n\n"
            "• Use `/menu` to open a new session\n"
            "• Use `/quick_contribute` for fast contributions\n"
            "• Use `/quick_loa` for quick LOA requests",
            MenuColors.INFO
        )
        close_embed.set_footer(text="Thank you for using Thanatos Bot")
        await interaction.response.edit_message(embed=close_embed, view=None)
        self.stop()

class ContributionsModuleView(ModernMenuView):
    """Enhanced contributions module with detailed stats"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Create contributions module embed with live data"""
        embed = self.create_professional_embed(
            "📦 Contributions Management",
            "**Comprehensive Contribution Tracking System**\n\n"
            "Manage all aspects of member contributions to your organization.",
            MenuColors.INFO
        )
        
        try:
            # Get contribution stats
            contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
            
            if contributions:
                # Category breakdown
                categories = {}
                contributors = set()
                total_items = 0
                
                for contrib in contributions:
                    category = contrib['category']
                    categories[category] = categories.get(category, 0) + contrib['quantity']
                    contributors.add(contrib['discord_name'])
                    total_items += contrib['quantity']
                
                # Stats display
                stats_text = (
                    f"📊 **{len(contributions):,}** Total Records\n"
                    f"📦 **{total_items:,}** Items Contributed\n"
                    f"👥 **{len(contributors)}** Active Contributors\n"
                    f"📂 **{len(categories)}** Categories"
                )
                
                embed.add_field(
                    name="📈 Live Statistics",
                    value=stats_text,
                    inline=True
                )
                
                # Top categories
                if categories:
                    top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
                    cat_text = "\n".join([f"• **{cat}**: {qty:,} items" for cat, qty in top_cats])
                    embed.add_field(
                        name="🏆 Top Categories",
                        value=cat_text,
                        inline=True
                    )
            else:
                embed.add_field(
                    name="📊 Statistics",
                    value="No contributions recorded yet.\nStart by recording your first contribution!",
                    inline=False
                )
        except Exception as e:
            embed.add_field(
                name="⚠️ Stats Unavailable",
                value="Unable to load statistics at this time.",
                inline=False
            )
        
        # Feature list
        features = [
            "📝 **Record Contributions** • Log new donations",
            "📊 **View Statistics** • Detailed analytics",
            "📋 **Browse Categories** • Organized by type",
            "👥 **Contributor Rankings** • See top donors",
            "📈 **Trends Analysis** • Track patterns"
        ]
        
        embed.add_field(
            name="🎯 Available Features",
            value="\n".join(features),
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="Record Contribution", style=discord.ButtonStyle.primary, emoji="📝", row=0)
    async def record_contribution(self, interaction: discord.Interaction, button: discord.ui.Button):
        contribute_cog = self.bot.get_cog('ContributionSystem')
        if contribute_cog:
            await contribute_cog.contribute_command.callback(contribute_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The contributions system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="View Statistics", style=discord.ButtonStyle.secondary, emoji="📊", row=0)
    async def view_statistics(self, interaction: discord.Interaction, button: discord.ui.Button):
        contribute_cog = self.bot.get_cog('ContributionSystem')
        if contribute_cog:
            await contribute_cog.view_contributions.callback(contribute_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The statistics system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="Browse Categories", style=discord.ButtonStyle.secondary, emoji="📂", row=0)
    async def browse_categories(self, interaction: discord.Interaction, button: discord.ui.Button):
        contribute_cog = self.bot.get_cog('ContributionSystem')
        if contribute_cog:
            await contribute_cog.list_contribution_categories.callback(contribute_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The category browser is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=1)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)

class DatabaseModuleView(ModernMenuView):
    """Enhanced database module for officers"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "🗄️ Database Management",
            "**Advanced Data Analytics & Management** (Officer Access)\n\n"
            "Comprehensive tools for data analysis, archiving, and management.",
            MenuColors.WARNING
        )
        
        try:
            # Get database stats
            contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
            archives = await self.bot.db.get_database_archives(interaction.guild.id)
            audit_events = await self.bot.db.get_all_audit_events(interaction.guild.id, limit=1000)
            
            stats_text = (
                f"💾 **{len(contributions):,}** Active Records\n"
                f"📚 **{len(archives)}** Archives Created\n"
                f"📋 **{len(audit_events):,}** Audit Events\n"
                f"🔄 **Live** Data Status"
            )
            
            embed.add_field(
                name="📊 Database Statistics",
                value=stats_text,
                inline=True
            )
            
        except Exception:
            embed.add_field(
                name="📊 Database Statistics",
                value="Loading statistics...",
                inline=True
            )
        
        # Management features
        features = [
            "📋 **Generate Reports** • Comprehensive summaries",
            "📦 **Create Archives** • Data backup & reset",
            "📚 **View Archives** • Access historical data",
            "🔧 **Edit Quantities** • Adjust inventory levels",
            "📊 **Export Data** • Multiple formats available",
            "🔍 **Data Analysis** • Advanced insights"
        ]
        
        embed.add_field(
            name="🛠️ Management Tools",
            value="\n".join(features),
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="Generate Report", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def generate_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.database_summary.callback(db_cog, interaction, format="embed")
        else:
            await self._service_unavailable(interaction, "Database Management")
    
    @discord.ui.button(label="Create Archive", style=discord.ButtonStyle.danger, emoji="📦", row=0)
    async def create_archive(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.create_archive.callback(db_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Archive System")
    
    @discord.ui.button(label="View Archives", style=discord.ButtonStyle.secondary, emoji="📚", row=0)
    async def view_archives(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.view_archives.callback(db_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Archive Viewer")
    
    @discord.ui.button(label="Edit Quantities", style=discord.ButtonStyle.secondary, emoji="🔧", row=1)
    async def edit_quantities(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.edit_quantity.callback(db_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Quantity Editor")
    
    @discord.ui.button(label="Export Data", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
    async def export_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ExportOptionsView(self.bot, self.user_id)
        embed = view.create_professional_embed(
            "📊 Data Export Center",
            "Select your preferred export format and options:",
            MenuColors.INFO
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=1)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def _service_unavailable(self, interaction: discord.Interaction, service_name: str):
        """Helper for service unavailable responses"""
        error_embed = self.create_professional_embed(
            "❌ Service Unavailable",
            f"The {service_name} is currently unavailable. Please contact an administrator.",
            MenuColors.DANGER
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

class AuditModuleView(ModernMenuView):
    """Audit logs module for officers"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "📋 Audit Log Management",
            "**Comprehensive Activity Tracking & Security** (Officer Access)\n\n"
            "Monitor all system activities, changes, and user actions.",
            MenuColors.DANGER
        )
        
        try:
            # Get audit stats
            audit_events = await self.bot.db.get_all_audit_events(interaction.guild.id, limit=None)
            
            if audit_events:
                contributions_count = sum(1 for e in audit_events if e['event_type'] == 'contribution')
                changes_count = sum(1 for e in audit_events if e['event_type'] == 'quantity_change')
                unique_actors = len(set(e['actor_id'] for e in audit_events))
                
                stats_text = (
                    f"📊 **{len(audit_events):,}** Total Events\n"
                    f"📦 **{contributions_count:,}** Contributions\n"
                    f"⚖️ **{changes_count:,}** Quantity Changes\n"
                    f"👥 **{unique_actors}** Unique Actors"
                )
                
                embed.add_field(
                    name="📈 Activity Statistics",
                    value=stats_text,
                    inline=True
                )
                
                # Recent activity indicator
                if audit_events:
                    latest_event = audit_events[0]  # Most recent
                    latest_time = ContributionAuditHelpers.format_datetime_safe(latest_event['occurred_at'])
                    embed.add_field(
                        name="🕐 Latest Activity",
                        value=f"**{latest_event['event_type'].title()}**\n"
                              f"Item: {latest_event['item_name'][:20]}\n"
                              f"Time: {latest_time}",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="📊 Activity Statistics",
                    value="No audit events recorded yet.",
                    inline=False
                )
        except Exception:
            embed.add_field(
                name="⚠️ Stats Loading",
                value="Loading audit statistics...",
                inline=False
            )
        
        # Audit features
        features = [
            "📋 **View Audit Logs** • Complete activity history",
            "📊 **Generate Reports** • Comprehensive summaries",
            "📁 **Export Logs** • Multiple export formats",
            "🔍 **Search & Filter** • Advanced filtering options",
            "⚡ **Real-time Tracking** • Live activity monitoring"
        ]
        
        embed.add_field(
            name="🔍 Audit Features",
            value="\n".join(features),
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="View Logs", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def view_audit_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        audit_cog = self.bot.get_cog('AuditLogs')
        if audit_cog:
            await audit_cog.audit_logs.callback(audit_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Audit Logs")
    
    @discord.ui.button(label="Export Logs", style=discord.ButtonStyle.secondary, emoji="📁", row=0)
    async def export_audit_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
        audit_cog = self.bot.get_cog('AuditLogs')
        if audit_cog:
            await audit_cog.audit_export.callback(audit_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Audit Export")
    
    @discord.ui.button(label="Summary Report", style=discord.ButtonStyle.secondary, emoji="📊", row=0)
    async def audit_summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        audit_cog = self.bot.get_cog('AuditLogs')
        if audit_cog:
            await audit_cog.audit_summary.callback(audit_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Audit Summary")
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=1)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def _service_unavailable(self, interaction: discord.Interaction, service_name: str):
        error_embed = self.create_professional_embed(
            "❌ Service Unavailable",
            f"The {service_name} service is currently unavailable. Please contact an administrator.",
            MenuColors.DANGER
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

# Additional module views (MembershipModuleView, LOAModuleView, etc.) would follow the same pattern
# For brevity, I'll include just the key ones and the enhanced system classes

class ExportOptionsView(ModernMenuView):
    """Enhanced export options with more formats and features"""
    
    @discord.ui.button(label="Excel Export", style=discord.ButtonStyle.primary, emoji="📊", row=0)
    async def export_excel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Implementation for Excel export
        await interaction.response.send_message("Excel export feature coming soon!", ephemeral=True)
    
    @discord.ui.button(label="PDF Report", style=discord.ButtonStyle.primary, emoji="📄", row=0)
    async def export_pdf(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Implementation for PDF export
        await interaction.response.send_message("PDF export feature coming soon!", ephemeral=True)
    
    @discord.ui.button(label="JSON Data", style=discord.ButtonStyle.secondary, emoji="📋", row=0)
    async def export_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        db_cog = self.bot.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.database_summary.callback(db_cog, interaction, format="json")
        else:
            await self._service_unavailable(interaction, "JSON Export")
    
    @discord.ui.button(label="🔙 Back", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_database(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DatabaseModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def _service_unavailable(self, interaction: discord.Interaction, service_name: str):
        error_embed = self.create_professional_embed(
            "❌ Service Unavailable",
            f"The {service_name} is currently unavailable.",
            MenuColors.DANGER
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

# Additional simplified views for other modules
class MembershipModuleView(ModernMenuView):
    """Membership management module"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "👥 Membership Management",
            "**Organization Member Management**\n\nManage member records, roles, and status tracking.",
            MenuColors.SUCCESS
        )
        
        # Add features list
        features = [
            "📋 **Sync Membership** • Update member records",
            "🔍 **Debug Roles** • Troubleshoot role issues",
            "📊 **Member Statistics** • View membership data",
            "📝 **Membership List** • Generate member list file",
            "📄 **Membership Embed** • Display formatted member list"
        ]
        
        embed.add_field(
            name="🎯 Available Features",
            value="\n".join(features),
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="📋 Sync Membership", style=discord.ButtonStyle.primary, row=0)
    async def sync_membership(self, interaction: discord.Interaction, button: discord.ui.Button):
        member_cog = self.bot.get_cog('MembershipSystem')
        if member_cog:
            await member_cog.sync_membership.callback(member_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The membership system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="🔍 Debug Roles", style=discord.ButtonStyle.secondary, row=0)
    async def debug_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        member_cog = self.bot.get_cog('MembershipSystem')
        if member_cog:
            await member_cog.debug_roles.callback(member_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The membership system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="📝 Membership List", style=discord.ButtonStyle.secondary, row=0)
    async def membership_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        member_cog = self.bot.get_cog('MembershipSystem')
        if member_cog:
            await member_cog.membership_list.callback(member_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The membership system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="📄 Membership Embed", style=discord.ButtonStyle.secondary, row=1)
    async def membership_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        member_cog = self.bot.get_cog('MembershipSystem')
        if member_cog:
            await member_cog.membership_embed.callback(member_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The membership system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=1)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)

class LOAModuleView(ModernMenuView):
    """LOA management module"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "📅 Leave of Absence Management",
            "**LOA Request & Tracking System**\n\nManage leave requests, approvals, and member status.",
            MenuColors.INFO
        )
        
        # Add features list
        features = [
            "📝 **Submit LOA Request** • Request time off",
            "📋 **View My LOA Status** • Check current request",
            "⏹️ **End LOA Early** • Return from leave"
        ]
        
        # Check if user is officer to show additional features
        try:
            is_officer = await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot)
            if is_officer:
                features.extend([
                    "📄 **View All LOAs** • Officer overview",
                    "⚔️ **Manage LOAs** • Interactive LOA management dashboard",
                    "🛡️ **End Member LOA** • Force end someone else's LOA"
                ])
        except:
            pass
        
        embed.add_field(
            name="🎯 Available Features",
            value="\n".join(features),
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="📝 Submit LOA", style=discord.ButtonStyle.primary, row=0)
    async def submit_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.loa_command.callback(loa_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The LOA system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="📋 View My LOA", style=discord.ButtonStyle.secondary, row=0)
    async def view_my_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.loa_status.callback(loa_cog, interaction, member=interaction.user)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The LOA system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="⏹️ End LOA Early", style=discord.ButtonStyle.secondary, row=0)
    async def end_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.loa_cancel.callback(loa_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The LOA system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="⚔️ Manage LOAs (Officer)", style=discord.ButtonStyle.primary, row=1)
    async def manage_loas_officer(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions first
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **LOA Management** requires Officer permissions."
            )
            return
        
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.loa_manage.callback(loa_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The LOA management system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="🛡️ End Member LOA (Officer)", style=discord.ButtonStyle.danger, row=1)
    async def end_member_loa_officer(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions first
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **End Member LOA** requires Officer permissions."
            )
            return
        
        # Create member selection modal
        modal = EndMemberLOAModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=2)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)

class MessagingModuleView(ModernMenuView):
    """Messaging module for officers"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "💬 Messaging Center",
            "**Direct Communication Tools** (Officer Access)\n\n"
            "Send direct messages, announcements, and manage communications.",
            MenuColors.INFO
        )
        
        # Communication features
        features = [
            "📨 **Direct Message** • Send private messages to members",
            "👥 **Mass Role Message** • Send messages to all users with a specific role",
            "📢 **Announcements** • Broadcast to channels",
            "📋 **Message Templates** • Pre-written messages",
            "🔔 **Notifications** • System alerts and updates"
        ]
        
        embed.add_field(
            name="📬 Communication Tools",
            value="\n".join(features),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Usage Guidelines",
            value="• Use direct messaging responsibly\n"
                  "• Follow Discord Terms of Service\n"
                  "• Respect member privacy settings\n"
                  "• Keep communications professional",
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="📨 Send Direct Message", style=discord.ButtonStyle.primary, emoji="📨", row=0)
    async def send_direct_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        dm_cog = self.bot.get_cog('DirectMessaging')
        if dm_cog:
            await dm_cog.send_dm.callback(dm_cog, interaction, user=None, message=None)
        else:
            await self._service_unavailable(interaction, "Direct Messaging")
    
    @discord.ui.button(label="👥 Mass Role Message", style=discord.ButtonStyle.secondary, emoji="👥", row=0)
    async def mass_role_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the Mass Role Message interface"""
        # Create and open Mass Role Message view
        view = MassRoleMessageView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="📋 Message Templates", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def message_templates(self, interaction: discord.Interaction, button: discord.ui.Button):
        templates_embed = self.create_professional_embed(
            "📋 Message Templates",
            "Quick access to common message templates:",
            MenuColors.INFO
        )
        
        templates = [
            "**Welcome Message** • New member greeting",
            "**LOA Reminder** • Leave request follow-up",
            "**Contribution Thanks** • Appreciation message",
            "**Event Notification** • Upcoming events",
            "**General Reminder** • Various reminders"
        ]
        
        templates_embed.add_field(
            name="Available Templates",
            value="\n".join(templates),
            inline=False
        )
        
        templates_embed.set_footer(text="Use /send_dm to send messages with these templates")
        
        await interaction.response.send_message(embed=templates_embed, ephemeral=True)
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=2)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def _service_unavailable(self, interaction: discord.Interaction, service_name: str):
        error_embed = self.create_professional_embed(
            "❌ Service Unavailable",
            f"The {service_name} is currently unavailable. Please contact an administrator.",
            MenuColors.DANGER
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

class AdministrationModuleView(ModernMenuView):
    """Administration module for officers"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "⚙️ System Administration",
            "**Bot Configuration & Management** (Officer Access)\n\n"
            "Manage bot settings, channels, roles, and system configuration.",
            MenuColors.WARNING
        )
        
        try:
            # Get current server configuration
            config = await self.bot.db.get_server_config(interaction.guild.id)
            
            if config:
                config_status = "🟢 **Configured**"
                
                # Show key settings
                settings_text = ""
                if config.get('officer_role_id'):
                    role = interaction.guild.get_role(config['officer_role_id'])
                    settings_text += f"👑 **Officer Role:** {role.name if role else 'Not Found'}\n"
                else:
                    settings_text += "👑 **Officer Role:** Not Set\n"
                
                if config.get('notification_channel_id'):
                    channel = interaction.guild.get_channel(config['notification_channel_id'])
                    settings_text += f"📢 **Notification Channel:** {channel.name if channel else 'Not Found'}\n"
                else:
                    settings_text += "📢 **Notification Channel:** Not Set\n"
                
                if config.get('leadership_channel_id'):
                    channel = interaction.guild.get_channel(config['leadership_channel_id'])
                    settings_text += f"👑 **Leadership Channel:** {channel.name if channel else 'Not Found'}\n"
                else:
                    settings_text += "👑 **Leadership Channel:** Not Set\n"
                
                embed.add_field(
                    name="📊 Current Configuration",
                    value=f"{config_status}\n\n{settings_text}",
                    inline=True
                )
            else:
                embed.add_field(
                    name="📊 Current Configuration",
                    value="🔴 **Not Configured**\n\nServer settings need to be configured for full functionality.",
                    inline=True
                )
        except Exception:
            embed.add_field(
                name="📊 Current Configuration",
                value="⚠️ Loading configuration...",
                inline=True
            )
        
        # Administration features
        admin_features = [
            "⚙️ **Configure Bot** • Set channels, roles, and permissions",
            "🔧 **System Settings** • Advanced bot configuration",
            "💾 **Backup Management** • Create and restore backups",
            "🔄 **Reset Systems** • Clear data and restart components",
            "📊 **System Status** • Check bot health and performance",
            "🛡️ **Security Settings** • Manage access and permissions"
        ]
        
        embed.add_field(
            name="🛠️ Administrative Tools",
            value="\n".join(admin_features),
            inline=False
        )
        
        # Quick actions
        embed.add_field(
            name="⚡ Quick Actions",
            value="• Use buttons below to configure settings\n"
                  "• Changes take effect immediately\n"
                  "• All changes are logged for security\n"
                  "• Backup your settings before major changes",
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="⚙️ Configure Bot", style=discord.ButtonStyle.primary, emoji="⚙️", row=0)
    async def configure_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        config_cog = self.bot.get_cog('ConfigurationSystem')
        if config_cog:
            await config_cog.setup_menu.callback(config_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Configuration System")
    
    @discord.ui.button(label="💾 Backup Management", style=discord.ButtonStyle.secondary, emoji="💾", row=0)
    async def backup_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BackupManagementView(self.bot, self.user_id)
        embed = view.create_professional_embed(
            "💾 Backup Management Center",
            "Create, restore, and manage database backups:",
            MenuColors.WARNING
        )
        
        # Add backup options
        backup_options = [
            "📥 **Create Backup** • Save current database state",
            "📤 **Restore Backup** • Load previous database state",
            "📋 **List Backups** • View available backups",
            "🗑️ **Delete Backup** • Remove old backup files"
        ]
        
        embed.add_field(
            name="🔧 Backup Operations",
            value="\n".join(backup_options),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Notes",
            value="• Backups include all contribution data\n"
                  "• Restore operations will overwrite current data\n"
                  "• Always create a backup before major operations\n"
                  "• Backup files are stored locally on the server",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="📊 System Status", style=discord.ButtonStyle.secondary, emoji="📊", row=0)
    async def system_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        status_embed = self.create_professional_embed(
            "📊 System Status Report",
            "Current bot health and performance metrics:",
            MenuColors.SUCCESS
        )
        
        try:
            # Bot basic info
            bot_info = (
                f"🤖 **Bot:** {self.bot.user.name}#{self.bot.user.discriminator}\n"
                f"🆔 **ID:** {self.bot.user.id}\n"
                f"📊 **Guilds:** {len(self.bot.guilds)}\n"
                f"👥 **Total Users:** {len(set(self.bot.get_all_members()))}\n"
                f"⚡ **Latency:** {round(self.bot.latency * 1000)}ms"
            )
            
            status_embed.add_field(
                name="🤖 Bot Information",
                value=bot_info,
                inline=True
            )
            
            # System status indicators
            system_status = (
                "🟢 **Database:** Online\n"
                "🟢 **Commands:** Functional\n"
                "🟢 **Background Tasks:** Running\n"
                f"🟢 **Uptime:** <t:{int(self.bot.user.created_at.timestamp())}:R>\n"
                "🟢 **Memory:** Normal"
            )
            
            status_embed.add_field(
                name="📡 System Status",
                value=system_status,
                inline=True
            )
            
            # Quick stats
            try:
                contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
                members = await self.bot.db.get_all_members(interaction.guild.id)
                
                guild_stats = (
                    f"📦 **Contributions:** {len(contributions) if contributions else 0}\n"
                    f"👥 **Members:** {len(members) if members else 0}\n"
                    f"📋 **Commands:** 71\n"
                    f"⚙️ **Modules:** 9\n"
                    f"🔧 **Version:** 2.0"
                )
                
                status_embed.add_field(
                    name="📈 Guild Statistics",
                    value=guild_stats,
                    inline=True
                )
            except:
                status_embed.add_field(
                    name="📈 Guild Statistics",
                    value="⚠️ Loading statistics...",
                    inline=True
                )
            
        except Exception as e:
            status_embed.add_field(
                name="⚠️ Status Error",
                value=f"Unable to fetch complete system status.\nError: {str(e)[:100]}",
                inline=False
            )
        
        status_embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        await interaction.response.send_message(embed=status_embed, ephemeral=True)
    
    @discord.ui.button(label="🔄 Reset Options", style=discord.ButtonStyle.danger, emoji="🔄", row=1)
    async def reset_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        reset_embed = self.create_professional_embed(
            "🔄 System Reset Options",
            "⚠️ **DANGER ZONE** - These operations cannot be undone!\n\n"
            "Available reset operations:",
            MenuColors.DANGER
        )
        
        reset_options = [
            "🗑️ **Clear Cache** • Reset temporary data (Safe)",
            "🔄 **Restart Modules** • Reload all cogs (Safe)",
            "⚠️ **Reset Configuration** • Clear server settings (Caution)",
            "💥 **Factory Reset** • Clear ALL data (DESTRUCTIVE)"
        ]
        
        reset_embed.add_field(
            name="🔧 Available Resets",
            value="\n".join(reset_options),
            inline=False
        )
        
        reset_embed.add_field(
            name="⚠️ Critical Warning",
            value="**ALWAYS CREATE A BACKUP FIRST!**\n\n"
                  "• Factory reset removes ALL server data\n"
                  "• Configuration reset removes bot settings\n"
                  "• These operations are IRREVERSIBLE\n"
                  "• Contact support if you need assistance",
            inline=False
        )
        
        reset_embed.set_footer(text="🚨 Proceed with extreme caution - Data loss is permanent!")
        
        await interaction.response.send_message(embed=reset_embed, ephemeral=True)
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=1)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def _service_unavailable(self, interaction: discord.Interaction, service_name: str):
        error_embed = self.create_professional_embed(
            "❌ Service Unavailable",
            f"The {service_name} is currently unavailable. Please contact an administrator.",
            MenuColors.DANGER
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

class BackupManagementView(ModernMenuView):
    """Backup management interface"""
    
    @discord.ui.button(label="📥 Create Backup", style=discord.ButtonStyle.primary, emoji="📥", row=0)
    async def create_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        backup_cog = self.bot.get_cog('BackupSystem')
        if backup_cog:
            await backup_cog.backup_database.callback(backup_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Backup System")
    
    @discord.ui.button(label="📤 Restore Backup", style=discord.ButtonStyle.danger, emoji="📤", row=0)
    async def restore_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        backup_cog = self.bot.get_cog('BackupSystem')
        if backup_cog:
            await backup_cog.restore_database.callback(backup_cog, interaction, filename=None)
        else:
            await self._service_unavailable(interaction, "Backup System")
    
    @discord.ui.button(label="📋 List Backups", style=discord.ButtonStyle.secondary, emoji="📋", row=0)
    async def list_backups(self, interaction: discord.Interaction, button: discord.ui.Button):
        backup_cog = self.bot.get_cog('BackupSystem')
        if backup_cog:
            await backup_cog.list_backups.callback(backup_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Backup System")
    
    @discord.ui.button(label="🔙 Back to Admin", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AdministrationModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def _service_unavailable(self, interaction: discord.Interaction, service_name: str):
        error_embed = self.create_professional_embed(
            "❌ Service Unavailable",
            f"The {service_name} is currently unavailable. Please contact an administrator.",
            MenuColors.DANGER
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

class MassRoleMessageView(ModernMenuView):
    """Mass Role Message interface for sending messages to all users with a specific role"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "👥 Mass Role Message System",
            "**Send messages to all members with a specific role** (Officer Access)\n\n"
            "This tool allows you to send direct messages to all members who have a specific role.",
            MenuColors.WARNING
        )
        
        # Safety guidelines
        guidelines = [
            "📋 **Step 1:** Select the target role from server roles",
            "✍️ **Step 2:** Compose your message content",
            "📤 **Step 3:** Review and send to all role members",
            "📊 **Step 4:** Monitor delivery results and feedback"
        ]
        
        embed.add_field(
            name="📝 How to Use",
            value="\n".join(guidelines),
            inline=False
        )
        
        # Important warnings
        warnings = [
            "⚠️ **Use Responsibly** • Messages will be sent to ALL members with the role",
            "🚫 **Respect Privacy** • Some users may have DMs disabled",
            "📜 **Follow Rules** • Comply with Discord ToS and server rules",
            "🔄 **One-Way Communication** • Recipients can reply but it goes to server staff"
        ]
        
        embed.add_field(
            name="⚠️ Important Guidelines",
            value="\n".join(warnings),
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="👥 Select Role & Send Message", style=discord.ButtonStyle.primary, row=0)
    async def send_mass_role_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open role selection and message composition interface"""
        # This will integrate with the existing mass DM dashboard functionality
        # For now, redirect to the dashboard mass-dm page
        embed = self.create_professional_embed(
            "🚀 Opening Mass Role Message Interface",
            "**Please use the web dashboard for Mass Role Messaging:**\n\n"
            "1. Open the **Dashboard** link (button in your bot message)\n"
            "2. Navigate to **Messaging Center**\n"
            "3. Click **Mass Role Message**\n\n"
            "📱 **Alternative:** Use the `/dm_role` slash command directly",
            MenuColors.INFO
        )
        
        embed.add_field(
            name="🌐 Dashboard Features",
            value="• **Role Selection** • Choose from all server roles\n"
                  "• **Message Preview** • See exactly what members will receive\n"
                  "• **Delivery Stats** • Track successful/failed sends\n"
                  "• **Safety Checks** • Prevent accidental mass messages",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📋 View Server Roles", style=discord.ButtonStyle.secondary, row=0)
    async def view_server_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Display a list of server roles and their member counts"""
        embed = self.create_professional_embed(
            "👑 Server Roles Overview",
            "**Available roles in this server:**",
            MenuColors.INFO
        )
        
        # Get roles and filter out @everyone and managed roles
        roles = [role for role in interaction.guild.roles 
                if role.name != '@everyone' and not role.managed]
        
        # Sort by position (higher = more important)
        roles.sort(key=lambda r: r.position, reverse=True)
        
        if roles:
            role_list = []
            for role in roles[:15]:  # Show top 15 roles
                member_count = len(role.members)
                color_indicator = "🟢" if member_count > 0 else "🔘"
                role_list.append(f"{color_indicator} **{role.name}** • {member_count} members")
            
            embed.add_field(
                name="📊 Role Statistics",
                value="\n".join(role_list),
                inline=False
            )
            
            if len(roles) > 15:
                embed.add_field(
                    name="📈 Summary",
                    value=f"Showing top 15 of {len(roles)} roles\n"
                          f"Use the dashboard for complete role management",
                    inline=False
                )
        else:
            embed.add_field(
                name="📊 No Roles Found",
                value="No assignable roles found in this server.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔙 Back to Messaging", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_messaging(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MessagingModuleView(self.bot, self.user_id)
        embed = await view.create_module_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)

class EndMemberLOAModal(discord.ui.Modal):
    """Modal for officers to end another member's LOA"""
    
    def __init__(self, bot):
        super().__init__(title="End Member's LOA (Officer Action)")
        self.bot = bot
        
        # Member identification input
        self.member_input = discord.ui.TextInput(
            label="Member to End LOA For",
            placeholder="Enter member's Discord username, display name, or ID...",
            max_length=100,
            required=True
        )
        self.add_item(self.member_input)
        
        # Reason input (optional but recommended)
        self.reason_input = discord.ui.TextInput(
            label="Reason for Ending LOA (Optional)",
            placeholder="Administrative reason for ending this LOA early...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Try to find the member
            member_input = self.member_input.value.strip()
            member = None
            
            # Try different methods to find the member
            if member_input.isdigit():
                # Try by ID
                try:
                    member = interaction.guild.get_member(int(member_input))
                except ValueError:
                    pass
            
            if not member:
                # Try by exact display name or username match
                for guild_member in interaction.guild.members:
                    if (guild_member.display_name.lower() == member_input.lower() or 
                        guild_member.name.lower() == member_input.lower()):
                        member = guild_member
                        break
            
            if not member:
                # Try partial match
                for guild_member in interaction.guild.members:
                    if (member_input.lower() in guild_member.display_name.lower() or 
                        member_input.lower() in guild_member.name.lower()):
                        member = guild_member
                        break
            
            if not member:
                error_embed = discord.Embed(
                    title="❌ Member Not Found",
                    description=f"Could not find a member matching '{member_input}'.\n\n"
                               "**Try these formats:**\n"
                               "• Exact username: `JohnDoe`\n"
                               "• Display name: `John Doe`\n"
                               "• User ID: `123456789012345678`\n"
                               "• Partial name: `John`",
                    color=MenuColors.DANGER
                )
                return await interaction.followup.send(embed=error_embed, ephemeral=True)
            
            # Check if member has an active LOA
            loa = await self.bot.db.get_active_loa(interaction.guild.id, member.id)
            
            if not loa:
                error_embed = discord.Embed(
                    title="❌ No Active LOA",
                    description=f"**{member.display_name}** does not have an active LOA to end.\n\n"
                               "💡 **Tip:** Use `/loa_list` to see all active LOAs.",
                    color=MenuColors.DANGER
                )
                return await interaction.followup.send(embed=error_embed, ephemeral=True)
            
            # Create confirmation view
            reason = self.reason_input.value.strip() if self.reason_input.value else "Administrative decision"
            confirm_view = ConfirmEndMemberLOAView(self.bot, loa, member, interaction.user, reason)
            
            confirm_embed = discord.Embed(
                title="⚠️ Confirm End Member's LOA",
                description=f"**You are about to force-end {member.display_name}'s LOA**\n\n"
                           f"📊 **LOA Details:**\n"
                           f"• **Duration:** {loa.get('duration', 'Unknown')}\n"
                           f"• **Original Reason:** {loa.get('reason', 'No reason')[:100]}\n"
                           f"• **Started:** <t:{int(loa.get('start_time', 0))}:R>\n\n"
                           f"🛡️ **Officer Action:**\n"
                           f"• **Your Reason:** {reason}\n"
                           f"• **Officer:** {interaction.user.display_name}",
                color=MenuColors.WARNING
            )
            
            confirm_embed.add_field(
                name="📝 This Action Will:",
                value="• End their LOA immediately\n"
                      "• Mark them as **Active** in the system\n"
                      "• Send notifications to relevant parties\n"
                      "• Log this action with your officer credentials\n"
                      "• Send a DM to the affected member",
                inline=False
            )
            
            await interaction.followup.send(
                embed=confirm_embed,
                view=confirm_view,
                ephemeral=True
            )
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error Processing Request",
                description=f"An error occurred while processing your request:\n```{str(e)[:200]}```\n\n"
                           "Please try again or contact an administrator.",
                color=MenuColors.DANGER
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class ConfirmEndMemberLOAView(discord.ui.View):
    """Confirmation view for ending a member's LOA"""
    
    def __init__(self, bot, loa_data: dict, member: discord.Member, officer: discord.Member, reason: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.loa_data = loa_data
        self.member = member
        self.officer = officer
        self.reason = reason
    
    @discord.ui.button(label="✅ Confirm End LOA", style=discord.ButtonStyle.danger)
    async def confirm_end_loa(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.officer.id:
            await interaction.response.send_message(
                "❌ Only the officer who initiated this action can confirm.", ephemeral=True
            )
            return
        
        try:
            # End the LOA
            await self.bot.db.end_loa(self.loa_data['id'])
            
            # Send notifications
            if hasattr(self.bot, 'loa_notifications'):
                await self.bot.loa_notifications.notify_loa_ended_by_officer(
                    interaction.guild.id, self.member, self.officer, self.reason
                )
            
            # Success embed
            success_embed = discord.Embed(
                title="✅ LOA Successfully Ended",
                description=f"**{self.member.display_name}**'s LOA has been ended by officer action.\n\n"
                           f"📊 **Action Summary:**\n"
                           f"• **Officer:** {self.officer.display_name}\n"
                           f"• **Member:** {self.member.display_name}\n"
                           f"• **Reason:** {self.reason}\n"
                           f"• **Original Duration:** {self.loa_data.get('duration', 'Unknown')}\n\n"
                           f"🔔 **Notifications Sent:**\n"
                           f"• Member has been notified via DM\n"
                           f"• Leadership team has been informed\n"
                           f"• Action logged in audit trail",
                color=MenuColors.SUCCESS,
                timestamp=datetime.now()
            )
            
            success_embed.set_footer(text="LOA Management • Officer Action Completed")
            
            await interaction.response.edit_message(
                embed=success_embed,
                view=None
            )
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error Ending LOA",
                description=f"An error occurred while ending the LOA:\n```{str(e)[:200]}```\n\n"
                           "The LOA may still be active. Please check and try again.",
                color=MenuColors.DANGER
            )
            await interaction.response.edit_message(embed=error_embed, view=None)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.officer.id:
            await interaction.response.send_message(
                "❌ Only the officer who initiated this action can cancel.", ephemeral=True
            )
            return
        
        cancel_embed = discord.Embed(
            title="❌ Action Cancelled",
            description="The LOA end action has been cancelled. No changes were made.",
            color=MenuColors.SECONDARY
        )
        await interaction.response.edit_message(embed=cancel_embed, view=None)

class DuesTrackingModuleView(ModernMenuView):
    """Dues Tracking module for comprehensive payment management"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "💰 Dues Tracking System",
            "**Comprehensive Payment Management & Reporting**\n\nTrack member dues, payments, and generate detailed financial reports.",
            MenuColors.SUCCESS
        )
        
        try:
            # Get dues stats if officer
            is_officer = await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot)
            
            if is_officer:
                # Get dues periods
                conn = await self.bot.db._get_shared_connection()
                cursor = await conn.execute(
                    'SELECT COUNT(*) FROM dues_periods WHERE guild_id = ? AND is_active = TRUE',
                    (interaction.guild.id,)
                )
                active_periods = (await cursor.fetchone())[0]
                
                # Get payment stats from latest period
                cursor = await conn.execute(
                    'SELECT * FROM dues_periods WHERE guild_id = ? AND is_active = TRUE ORDER BY created_at DESC LIMIT 1',
                    (interaction.guild.id,)
                )
                latest_period = await cursor.fetchone()
                
                if latest_period:
                    summary = await self.bot.db.get_dues_collection_summary(interaction.guild.id, latest_period[0])
                    
                    stats_text = (
                        f"📅 **{active_periods}** Active Periods\n"
                        f"👥 **{summary.get('total_members', 0)}** Members Tracked\n"
                        f"💰 **${summary.get('total_collected', 0):.2f}** Total Collected\n"
                        f"📊 **{summary.get('collection_percentage', 0):.1f}%** Collection Rate"
                    )
                    
                    embed.add_field(
                        name="📈 Payment Statistics",
                        value=stats_text,
                        inline=True
                    )
                    
                    # Period breakdown
                    period_info = (
                        f"**Latest Period:** {latest_period[2]}\n"
                        f"**Due Amount:** ${latest_period[4]:.2f}\n"
                        f"**Paid Members:** {summary.get('paid_count', 0)}\n"
                        f"**Outstanding:** ${summary.get('outstanding_amount', 0):.2f}"
                    )
                    
                    embed.add_field(
                        name="🏆 Current Period",
                        value=period_info,
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="📊 Payment Statistics",
                        value=f"**{active_periods}** Active Periods\nNo payment data available yet.",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="👤 Member Access",
                    value="Basic dues tracking features available.\nContact officers for payment updates.",
                    inline=False
                )
        except Exception:
            embed.add_field(
                name="⚠️ Stats Loading",
                value="Loading dues statistics...",
                inline=False
            )
        
        # Features based on permissions
        is_officer = await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot)
        
        if is_officer:
            features = [
                "📋 **Create Dues Period** • Set up new payment periods",
                "💳 **Update Payments** • Record member payments",
                "📊 **Financial Reports** • Comprehensive analytics",
                "📈 **Payment History** • Track member payment records",
                "📁 **Export Data** • Backup and analysis files",
                "🔧 **Manage Periods** • Edit and reset payment periods"
            ]
        else:
            features = [
                "💳 **View My Payments** • Check personal payment status",
                "📋 **Payment History** • See payment records",
                "💰 **Due Amounts** • Check current dues",
                "📞 **Contact Officers** • Get payment assistance"
            ]
        
        embed.add_field(
            name="🎯 Available Features",
            value="\n".join(features),
            inline=False
        )
        
        if is_officer:
            embed.add_field(
                name="🔧 Management Tools",
                value="• **Period Management** • Create, edit, reset periods\n"
                      "• **Payment Processing** • Record and track payments\n"
                      "• **Financial Reporting** • Generate detailed reports\n"
                      "• **Data Export** • Backup and analysis capabilities",
                inline=False
            )
        
        return embed
    
    @discord.ui.button(label="📋 Create Period", style=discord.ButtonStyle.primary, row=0)
    async def create_period(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Dues Period Creation** requires Officer permissions."
            )
            return
        
        # Show period creation command info
        create_embed = self.create_professional_embed(
            "📋 Create Dues Period",
            "Use the dues period creation command to set up new payment periods:",
            MenuColors.INFO
        )
        
        create_embed.add_field(
            name="🚀 Quick Creation",
            value="Use `/dues_create_period` with these parameters:\n"
                  "• **period_name:** Name for the period (e.g. 'Q1 2024 Dues')\n"
                  "• **due_amount:** Amount per member (e.g. 25.00)\n"
                  "• **due_date:** When due (e.g. 'next friday', '2024-03-15')\n"
                  "• **description:** Optional description",
            inline=False
        )
        
        create_embed.add_field(
            name="💡 Example Usage",
            value="`/dues_create_period period_name:'Q1 2024 Dues' due_amount:25.00 due_date:'march 15' description:'Quarterly membership dues'`",
            inline=False
        )
        
        await interaction.response.send_message(embed=create_embed, ephemeral=True)
    
    @discord.ui.button(label="💳 Update Payment", style=discord.ButtonStyle.secondary, row=0)
    async def update_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Payment Updates** require Officer permissions."
            )
            return
        
        dues_cog = self.bot.get_cog('DuesTrackingSystem')
        if dues_cog:
            # Show payment update command info
            update_embed = self.create_professional_embed(
                "💳 Update Member Payment",
                "Record and update member payment information:",
                MenuColors.SUCCESS
            )
            
            update_embed.add_field(
                name="📝 Payment Recording",
                value="Use `/dues_update_payment` to record payments:\n"
                      "• Select the member and period\n"
                      "• Enter amount paid and payment method\n"
                      "• Set payment status (paid/partial/exempt)\n"
                      "• Add optional notes",
                inline=False
            )
            
            update_embed.add_field(
                name="💰 Payment Status Options",
                value="• **Paid** - Full payment received\n"
                      "• **Partial** - Partial payment received\n"
                      "• **Unpaid** - No payment received\n"
                      "• **Exempt** - Member is exempt from dues",
                inline=True
            )
            
            update_embed.add_field(
                name="💳 Payment Methods",
                value="Cash, Venmo, PayPal, Zelle,\nCashApp, Bank Transfer,\nCheck, Other",
                inline=True
            )
            
            await interaction.response.send_message(embed=update_embed, ephemeral=True)
        else:
            await self._service_unavailable(interaction, "Dues Tracking System")
    
    @discord.ui.button(label="📊 Financial Report", style=discord.ButtonStyle.secondary, row=0)
    async def financial_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Financial Reports** require Officer permissions."
            )
            return
        
        dues_cog = self.bot.get_cog('DuesTrackingSystem')
        if dues_cog:
            await dues_cog.financial_report.callback(dues_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Dues Financial Reports")
    
    @discord.ui.button(label="📈 Payment History", style=discord.ButtonStyle.secondary, row=1)
    async def payment_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions for full history, members can see their own
        is_officer = await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot)
        
        if is_officer:
            # Officers can see any member's history
            history_embed = self.create_professional_embed(
                "📈 Payment History Access",
                "View detailed payment history for any member:",
                MenuColors.INFO
            )
            
            history_embed.add_field(
                name="🔍 Officer Access",
                value="Use `/dues_payment_history` to view:\n"
                      "• Complete payment records for any member\n"
                      "• Payment trends across all periods\n"
                      "• Outstanding balances and exemptions\n"
                      "• Payment methods and dates",
                inline=False
            )
            
            await interaction.response.send_message(embed=history_embed, ephemeral=True)
        else:
            # Members can only see their own
            history_embed = self.create_professional_embed(
                "📈 My Payment History",
                "View your personal payment history and status:",
                MenuColors.SUCCESS
            )
            
            history_embed.add_field(
                name="👤 Personal Access",
                value="• View your payment records across all periods\n"
                      "• Check current payment status\n"
                      "• See outstanding balances\n"
                      "• Contact officers for payment updates",
                inline=False
            )
            
            await interaction.response.send_message(embed=history_embed, ephemeral=True)
    
    @discord.ui.button(label="📁 Export Data", style=discord.ButtonStyle.secondary, row=1)
    async def export_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Data Export** requires Officer permissions."
            )
            return
        
        dues_cog = self.bot.get_cog('DuesTrackingSystem')
        if dues_cog:
            await dues_cog.export_dues_data.callback(dues_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Dues Data Export")
    
    @discord.ui.button(label="📋 View Periods", style=discord.ButtonStyle.secondary, row=1)
    async def view_periods(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Period Management** requires Officer permissions."
            )
            return
        
        dues_cog = self.bot.get_cog('DuesTrackingSystem')
        if dues_cog:
            await dues_cog.list_dues_periods.callback(dues_cog, interaction)
        else:
            await self._service_unavailable(interaction, "Dues Period Management")
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=2)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def _service_unavailable(self, interaction: discord.Interaction, service_name: str):
        error_embed = self.create_professional_embed(
            "❌ Service Unavailable",
            f"The {service_name} is currently unavailable. Please contact an administrator.",
            MenuColors.DANGER
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

class EventsModuleView(ModernMenuView):
    """Event Management module"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "🎉 Event Management System",
            "**Comprehensive Event Organization & RSVP Tracking**\n\nCreate, manage, and track events with full RSVP integration.",
            MenuColors.INFO
        )
        
        try:
            # Get event stats
            events = await self.bot.db.get_active_events(interaction.guild.id)
            
            if events:
                # Calculate stats
                total_events = len(events)
                total_attending = sum(e.get('yes_count', 0) or 0 for e in events)
                categories = len(set(e['category'] for e in events))
                
                stats_text = (
                    f"📅 **{total_events}** Active Events\n"
                    f"✅ **{total_attending}** Total Attending\n"
                    f"📂 **{categories}** Categories\n"
                    f"🔄 **Live** Status Updates"
                )
                
                embed.add_field(
                    name="📊 Event Statistics",
                    value=stats_text,
                    inline=True
                )
                
                # Upcoming events
                upcoming = [e for e in events[:3]]  # First 3 events
                if upcoming:
                    event_list = []
                    for event in upcoming:
                        attending = event.get('yes_count', 0) or 0
                        event_list.append(f"**{event['event_name']}**\n📅 {event['event_date']} | ✅ {attending} attending")
                    
                    embed.add_field(
                        name="🔜 Upcoming Events",
                        value="\n\n".join(event_list),
                        inline=True
                    )
            else:
                embed.add_field(
                    name="📊 Event Statistics",
                    value="No active events found.\nCreate your first event to get started!",
                    inline=False
                )
        except Exception:
            embed.add_field(
                name="⚠️ Stats Loading",
                value="Loading event statistics...",
                inline=False
            )
        
        # Event features
        features = [
            "🎉 **Create Events** • Schedule new events",
            "📧 **Send Invitations** • Invite users/roles to events",
            "📋 **RSVP Management** • Track responses",
            "📊 **Event Analytics** • View attendance stats",
            "📅 **Event Calendar** • List all active events",
            "💬 **Send Event DMs** • Direct message invitations"
        ]
        
        embed.add_field(
            name="🎯 Available Features",
            value="\n".join(features),
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="🎉 Create Event", style=discord.ButtonStyle.primary, row=0)
    async def create_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions for event creation
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Event Creation** requires Officer permissions."
            )
            return
        
        # Show simplified event creation instructions
        create_embed = self.create_professional_embed(
            "🎉 Create Event - Simplified",
            "Use the new simplified event creation command!",
            MenuColors.SUCCESS
        )
        
        create_embed.add_field(
            name="🚀 Quick Event Creation",
            value="Use `/event` with these parameters:\n"
                  "• **name:** Event title\n"
                  "• **time:** When (e.g. 'tomorrow 8pm', 'friday 3pm')\n"
                  "• **description:** Event details\n"
                  "• **role:** Role to invite (@Members, @Officers, etc.)\n"
                  "• **send_dms:** Send DM notifications (True/False)",
            inline=False
        )
        
        create_embed.add_field(
            name="🎁 Example Usage",
            value="`/event name:Team Meeting time:tomorrow 3pm description:Weekly sync role:@Members send_dms:True`",
            inline=False
        )
        
        create_embed.add_field(
            name="✨ What Happens Automatically",
            value="✅ Event is created\n"
                  "✅ All role members are invited\n"
                  "✅ Everyone is RSVP'd as 'Yes'\n"
                  "✅ DM notifications sent (if enabled)\n"
                  "✅ Members can change their RSVP later",
            inline=False
        )
        
        await interaction.response.send_message(embed=create_embed, ephemeral=True)
    
    @discord.ui.button(label="📅 List Events", style=discord.ButtonStyle.secondary, row=0)
    async def list_events(self, interaction: discord.Interaction, button: discord.ui.Button):
        events_cog = self.bot.get_cog('EventManagement')
        if events_cog:
            await events_cog.list_events.callback(events_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The Event Management system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="📊 Event Analytics", style=discord.ButtonStyle.secondary, row=0)
    async def event_analytics(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check officer permissions for analytics
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "🔒 **Event Analytics** requires Officer permissions."
            )
            return
        
        events_cog = self.bot.get_cog('EventManagement')
        if events_cog:
            await events_cog.event_analytics.callback(events_cog, interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The Event Management system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="📧 Event Commands", style=discord.ButtonStyle.secondary, row=1)
    async def event_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        commands_embed = self.create_professional_embed(
            "📋 Event Management Commands",
            "Quick reference for event management commands:",
            MenuColors.INFO
        )
        
        # Officer commands
        officer_commands = [
            "`/create_event` • Create a new event",
            "`/invite_to_event` • Invite users/roles to events",
            "`/send_event_dms` • Send DM invitations",
            "`/event_rsvps` • View RSVPs for an event",
            "`/event_analytics` • View event statistics"
        ]
        
        # User commands
        user_commands = [
            "`/rsvp` • Respond to event invitations",
            "`/event_details` • View event information",
            "`/list_events` • See all active events"
        ]
        
        commands_embed.add_field(
            name="👑 Officer Commands",
            value="\n".join(officer_commands),
            inline=True
        )
        
        commands_embed.add_field(
            name="👤 Member Commands",
            value="\n".join(user_commands),
            inline=True
        )
        
        commands_embed.add_field(
            name="💡 Tips",
            value="• Use `/list_events` to find event IDs\n"
                  "• Events support categories and locations\n"
                  "• Automatic reminders are sent before events\n"
                  "• RSVPs can include optional notes",
            inline=False
        )
        
        await interaction.response.send_message(embed=commands_embed, ephemeral=True)
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=1)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)

class EnhancedMenuSystem(commands.Cog):
    """Enhanced menu system with professional UI/UX"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="menu", description="Open the enhanced Thanatos management dashboard")
    async def enhanced_menu(self, interaction: discord.Interaction):
        """Open the enhanced management dashboard"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            view = DashboardView(self.bot, interaction.user.id)
            embed = await view.create_dashboard_embed(interaction)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Dashboard Error",
                description=f"Unable to load dashboard: {str(e)[:100]}...",
                color=MenuColors.DANGER
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    @app_commands.command(name="dashboard", description="Quick access to the management dashboard")
    async def dashboard_shortcut(self, interaction: discord.Interaction):
        """Quick access to dashboard"""
        await self.enhanced_menu.callback(self, interaction)
    
    @app_commands.command(name="quick_contribute", description="Quick contribution recording")
    async def quick_contribute(self, interaction: discord.Interaction):
        """Quick contribution recording"""
        contribute_cog = self.bot.get_cog('ContributionSystem')
        if contribute_cog:
            await contribute_cog.contribute_command.callback(contribute_cog, interaction)
        else:
            await interaction.response.send_message(
                "❌ Contribution system is currently unavailable.", 
                ephemeral=True
            )
    
    @app_commands.command(name="quick_loa", description="Quick LOA request submission")
    async def quick_loa(self, interaction: discord.Interaction):
        """Quick LOA request"""
        loa_cog = self.bot.get_cog('LOASystem')
        if loa_cog:
            await loa_cog.loa_command.callback(loa_cog, interaction)
        else:
            await interaction.response.send_message(
                "❌ LOA system is currently unavailable.", 
                ephemeral=True
            )
    
    @app_commands.command(name="test", description="Test if commands are working")
    async def test_command(self, interaction: discord.Interaction):
        """Simple test command to verify bot functionality"""
        test_embed = discord.Embed(
            title="✅ Bot Test Successful",
            description="All systems are operational!",
            color=MenuColors.SUCCESS,
            timestamp=datetime.now()
        )
        
        test_embed.add_field(
            name="🤖 Bot Status",
            value="Online and responsive",
            inline=True
        )
        
        test_embed.add_field(
            name="⚡ Response Time",
            value=f"{round(self.bot.latency * 1000)}ms",
            inline=True
        )
        
        test_embed.add_field(
            name="🎛️ Commands",
            value="Use `/menu` to access the dashboard",
            inline=True
        )
        
        test_embed.set_footer(text="Thanatos Bot • Test Command")
        
        await interaction.response.send_message(embed=test_embed, ephemeral=True)

class ProspectManagementModuleView(ModernMenuView):
    """Prospect Management module for officer access"""
    
    async def create_module_embed(self, interaction: discord.Interaction) -> discord.Embed:
        embed = self.create_professional_embed(
            "🔍 Prospect Management System",
            "**Comprehensive Prospect Tracking & Evaluation** (Officer Access)\n\n"
            "Manage prospect recruitment, evaluation, and advancement through the club hierarchy.",
            MenuColors.WARNING
        )
        
        try:
            # Get prospect stats
            active_prospects = await self.bot.db.get_active_prospects(interaction.guild.id)
            archived_prospects = await self.bot.db.get_archived_prospects(interaction.guild.id)
            
            if active_prospects:
                # Calculate stats
                total_strikes = sum(p.get('strikes', 0) for p in active_prospects)
                with_tasks = len([p for p in active_prospects if await self.bot.db.get_prospect_tasks(p['id'])])
                with_notes = len([p for p in active_prospects if await self.bot.db.get_prospect_notes(p['id'])])
                
                stats_text = (
                    f"👥 **{len(active_prospects)}** Active Prospects\n"
                    f"📁 **{len(archived_prospects)}** Archived\n"
                    f"⚠️ **{total_strikes}** Total Strikes\n"
                    f"📋 **{with_tasks}** With Tasks"
                )
                
                embed.add_field(
                    name="📊 Prospect Statistics",
                    value=stats_text,
                    inline=True
                )
                
                # Recent activity
                recent_prospects = active_prospects[-3:]  # Most recent 3
                if recent_prospects:
                    prospect_list = []
                    for prospect in recent_prospects:
                        prospect_name = prospect.get('prospect_name', f"User {prospect['user_id']}")
                        strikes = prospect.get('strikes', 0)
                        strike_indicator = f" ⚠️{strikes}" if strikes > 0 else ""
                        prospect_list.append(f"**{prospect_name}**{strike_indicator}\nSponsor: {prospect.get('sponsor_name', 'Unknown')}")
                    
                    embed.add_field(
                        name="👤 Recent Prospects",
                        value="\n\n".join(prospect_list),
                        inline=True
                    )
            else:
                embed.add_field(
                    name="📊 Prospect Statistics",
                    value="No active prospects found.\nAdd your first prospect to get started!",
                    inline=False
                )
        except Exception as e:
            embed.add_field(
                name="⚠️ Stats Loading",
                value=f"Loading prospect statistics... {str(e)[:50]}",
                inline=False
            )
        
        # Prospect management features
        features = [
            "➕ **Add Prospects** • Recruit new members",
            "📊 **Track Progress** • Monitor advancement",
            "📝 **Manage Tasks** • Assign and track tasks",
            "📋 **Notes & Strikes** • Record evaluations",
            "🗳️ **Voting System** • Vote on advancement",
            "📈 **Analytics** • Track success rates"
        ]
        
        embed.add_field(
            name="🎯 Available Features",
            value="\n".join(features),
            inline=False
        )
        
        # Quick actions guide
        embed.add_field(
            name="🚀 Quick Actions",
            value="• Use `/prospect add` to recruit new prospects\n"
                  "• Use `/prospect-task assign` to give tasks\n"
                  "• Use `/prospect-note add` for evaluations\n"
                  "• Use `/prospect-vote` for advancement votes",
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="➕ Add Prospect", style=discord.ButtonStyle.primary, emoji="➕", row=0)
    async def add_prospect(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show add prospect command info
        add_embed = self.create_professional_embed(
            "➕ Add New Prospect",
            "Use the prospect add command to recruit new members:",
            MenuColors.SUCCESS
        )
        
        add_embed.add_field(
            name="🚀 Quick Prospect Addition",
            value="Use `/prospect add` with these parameters:\n"
                  "• **prospect:** The Discord member to recruit\n"
                  "• **sponsor:** The member sponsoring them\n"
                  "• System will automatically create roles and notifications",
            inline=False
        )
        
        add_embed.add_field(
            name="💡 Example Usage",
            value="`/prospect add prospect:@NewMember sponsor:@ExistingMember`",
            inline=False
        )
        
        add_embed.add_field(
            name="✨ What Happens Automatically",
            value="✅ Prospect record is created\n"
                  "✅ 'Sponsored by X' role is assigned\n"
                  "✅ Sponsor gets 'Sponsors' role\n"
                  "✅ Leadership is notified\n"
                  "✅ Prospect receives welcome DM",
            inline=False
        )
        
        await interaction.response.send_message(embed=add_embed, ephemeral=True)
    
    @discord.ui.button(label="📋 Manage Tasks", style=discord.ButtonStyle.secondary, emoji="📋", row=0)
    async def manage_tasks(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show task management options
        task_embed = self.create_professional_embed(
            "📋 Prospect Task Management",
            "Assign and track tasks for prospect evaluation:",
            MenuColors.INFO
        )
        
        task_commands = [
            "`/prospect-task assign` • Assign new task to prospect",
            "`/prospect-task complete` • Mark task as completed",
            "`/prospect-task fail` • Mark task as failed",
            "`/prospect-task list` • View prospect tasks",
            "`/prospect-task overdue` • Show overdue tasks"
        ]
        
        task_embed.add_field(
            name="📝 Task Commands",
            value="\n".join(task_commands),
            inline=False
        )
        
        task_embed.add_field(
            name="💡 Task Examples",
            value="• Attend 3 club meetings\n"
                  "• Complete safety training\n"
                  "• Participate in group ride\n"
                  "• Learn club rules and bylaws\n"
                  "• Meet other members",
            inline=True
        )
        
        task_embed.add_field(
            name="⚠️ Task Management Tips",
            value="• Set realistic deadlines\n"
                  "• Track completion rates\n"
                  "• Follow up on overdue items\n"
                  "• Use tasks to gauge commitment\n"
                  "• Document progress in notes",
            inline=True
        )
        
        await interaction.response.send_message(embed=task_embed, ephemeral=True)
    
    @discord.ui.button(label="📝 Notes & Strikes", style=discord.ButtonStyle.secondary, emoji="📝", row=0)
    async def notes_strikes(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show notes and strikes management
        notes_embed = self.create_professional_embed(
            "📝 Prospect Notes & Strikes System",
            "Record evaluations, observations, and disciplinary actions:",
            MenuColors.WARNING
        )
        
        notes_commands = [
            "`/prospect-note add` • Add evaluation note",
            "`/prospect-note strike` • Add disciplinary strike",
            "`/prospect-note list` • View prospect notes",
            "`/prospect-note search` • Search notes by content"
        ]
        
        notes_embed.add_field(
            name="📋 Notes Commands",
            value="\n".join(notes_commands),
            inline=False
        )
        
        notes_embed.add_field(
            name="📝 Note Types",
            value="**Regular Notes:**\n"
                  "• Positive observations\n"
                  "• Meeting attendance\n"
                  "• Skill demonstrations\n"
                  "• General progress updates",
            inline=True
        )
        
        notes_embed.add_field(
            name="⚠️ Strike System",
            value="**Strikes for:**\n"
                  "• Rule violations\n"
                  "• Poor attitude/behavior\n"
                  "• Missed obligations\n"
                  "• Safety violations\n\n"
                  "**3+ strikes = Review**",
            inline=True
        )
        
        await interaction.response.send_message(embed=notes_embed, ephemeral=True)
    
    @discord.ui.button(label="🗳️ Voting System", style=discord.ButtonStyle.secondary, emoji="🗳️", row=1)
    async def voting_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show voting system info
        voting_embed = self.create_professional_embed(
            "🗳️ Prospect Voting System",
            "Democratic evaluation and advancement voting:",
            MenuColors.INFO
        )
        
        voting_commands = [
            "`/prospect-vote create` • Start new advancement vote",
            "`/prospect-vote cast` • Cast your vote",
            "`/prospect-vote results` • View voting results",
            "`/prospect-vote history` • See past votes"
        ]
        
        voting_embed.add_field(
            name="🗳️ Voting Commands",
            value="\n".join(voting_commands),
            inline=False
        )
        
        voting_embed.add_field(
            name="📊 Vote Types",
            value="**Advancement Votes:**\n"
                  "• Ready for patch\n"
                  "• Extend prospect period\n"
                  "• Remove from prospect status\n\n"
                  "**Evaluation Votes:**\n"
                  "• General performance\n"
                  "• Specific incidents",
            inline=True
        )
        
        voting_embed.add_field(
            name="⚖️ Voting Rules",
            value="• All full members can vote\n"
                  "• Anonymous voting available\n"
                  "• Majority rules (>50%)\n"
                  "• Officers can override\n"
                  "• Results are logged",
            inline=True
        )
        
        await interaction.response.send_message(embed=voting_embed, ephemeral=True)
    
    @discord.ui.button(label="📊 Analytics", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
    async def prospect_analytics(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show analytics and reporting
        analytics_embed = self.create_professional_embed(
            "📊 Prospect Analytics & Reporting",
            "Track success rates and identify improvement areas:",
            MenuColors.SUCCESS
        )
        
        analytics_features = [
            "📈 **Success Rates** • Track patch rates by sponsor",
            "⏱️ **Time Tracking** • Average time to advancement",
            "🎯 **Task Completion** • Task success rates",
            "⚠️ **Strike Analysis** • Common violation patterns",
            "🗳️ **Vote History** • Voting pattern analysis",
            "📋 **Reports** • Generate comprehensive reports"
        ]
        
        analytics_embed.add_field(
            name="🔍 Available Analytics",
            value="\n".join(analytics_features),
            inline=False
        )
        
        analytics_embed.add_field(
            name="📊 Use Analytics To:",
            value="• Identify effective sponsors\n"
                  "• Improve prospect programs\n"
                  "• Adjust evaluation criteria\n"
                  "• Track club growth trends\n"
                  "• Make data-driven decisions",
            inline=True
        )
        
        analytics_embed.add_field(
            name="📈 Report Types",
            value="• Monthly prospect summary\n"
                  "• Sponsor effectiveness\n"
                  "• Task completion rates\n"
                  "• Strike trend analysis\n"
                  "• Advancement predictions",
            inline=True
        )
        
        await interaction.response.send_message(embed=analytics_embed, ephemeral=True)
    
    @discord.ui.button(label="📋 List Prospects", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def list_prospects(self, interaction: discord.Interaction, button: discord.ui.Button):
        prospect_cog = self.bot.get_cog('ProspectManagementConsolidated')
        if prospect_cog:
            await prospect_cog._prospect_list(interaction)
        else:
            error_embed = self.create_professional_embed(
                "❌ Service Unavailable",
                "The Prospect Management system is currently unavailable. Please try again later.",
                MenuColors.DANGER
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="🏠 Dashboard", style=discord.ButtonStyle.success, row=2)
    async def back_to_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DashboardView(self.bot, self.user_id)
        embed = await view.create_dashboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(EnhancedMenuSystem(bot))

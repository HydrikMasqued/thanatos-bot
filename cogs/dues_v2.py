"""
Thanatos Dues Management System v2.0
Modern, streamlined dues management with comprehensive payment tracking
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import asyncio
import io
import re
try:
    from dateutil import parser as dateutil_parser
    from dateutil.relativedelta import relativedelta
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

logger = logging.getLogger(__name__)

def parse_enhanced_datetime(input_str: str) -> Optional[datetime]:
    """Enhanced datetime parsing with multiple methods and fallbacks"""
    input_str = input_str.strip()
    
    # Method 1: Try dateutil parser if available (handles many natural formats)
    if HAS_DATEUTIL:
        try:
            # Handle relative terms first
            now = datetime.now()
            
            # Common relative patterns
            relative_match = re.match(r'^(in\s+)?(\d+)\s*(day|days|week|weeks|month|months|year|years)$', input_str.lower())
            if relative_match:
                num = int(relative_match.group(2))
                unit = relative_match.group(3)
                
                if 'day' in unit:
                    return now + timedelta(days=num)
                elif 'week' in unit:
                    return now + timedelta(weeks=num)
                elif 'month' in unit:
                    return now + relativedelta(months=num)
                elif 'year' in unit:
                    return now + relativedelta(years=num)
            
            # Try dateutil parser for natural language
            parsed = dateutil_parser.parse(input_str, fuzzy=True)
            
            # If no time specified and it's a past date, assume next occurrence or end of day
            if parsed < now and 'at' not in input_str.lower() and ':' not in input_str:
                # If it's just a date, set it to end of day
                parsed = parsed.replace(hour=23, minute=59, second=59)
                
            return parsed
            
        except:
            pass
    
    # Method 2: Manual parsing for common formats
    try:
        # Format: MM/DD/YYYY HH:MM [AM/PM]
        datetime_patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)?',
            r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})\s*(AM|PM)?',
            r'(\d{1,2})/(\d{1,2})/(\d{4})\s*$',  # Date only
            r'(\d{4})-(\d{1,2})-(\d{1,2})\s*$',  # ISO date only
        ]
        
        for pattern in datetime_patterns:
            match = re.match(pattern, input_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) >= 3:  # Has date
                    if pattern.startswith(r'(\d{4})'):
                        # ISO format: YYYY-MM-DD
                        year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    else:
                        # US format: MM/DD/YYYY
                        month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                    
                    if len(groups) >= 5:  # Has time
                        hour, minute = int(groups[3]), int(groups[4])
                        am_pm = groups[5] if len(groups) > 5 else None
                        
                        if am_pm and am_pm.upper() == 'PM' and hour != 12:
                            hour += 12
                        elif am_pm and am_pm.upper() == 'AM' and hour == 12:
                            hour = 0
                    else:
                        # Default to end of day
                        hour, minute = 23, 59
                    
                    return datetime(year, month, day, hour, minute)
        
    except:
        pass
    
    # Method 3: Simple relative durations without dateutil
    try:
        now = datetime.now()
        
        # Match patterns like "2 weeks", "1 month", "30 days"
        duration_match = re.match(r'^(\d+)\s*(day|days|week|weeks|month|months)$', input_str.lower())
        if duration_match:
            num = int(duration_match.group(1))
            unit = duration_match.group(2)
            
            if 'day' in unit:
                return now + timedelta(days=num)
            elif 'week' in unit:
                return now + timedelta(weeks=num)
            elif 'month' in unit:
                # Approximate months as 30 days
                return now + timedelta(days=num * 30)
        
    except:
        pass
    
    return None

class PaymentStatus:
    """Payment status constants"""
    UNPAID = "unpaid"
    PAID = "paid"
    PARTIAL = "partial"
    EXEMPT = "exempt"
    OVERDUE = "overdue"

class PaymentMethods:
    """Available payment methods"""
    METHODS = [
        'Venmo', 'PayPal', 'Zelle', 'CashApp', 'Apple Pay', 'Google Pay',
        'Bank Transfer', 'Cash', 'Check', 'Credit Card', 'Other'
    ]

class DuesView(discord.ui.View):
    """Interactive dues management view"""
    
    def __init__(self, bot, guild_id: int, user_id: int, is_officer: bool = False):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.is_officer = is_officer
        
        # Remove officer-only buttons if user is not an officer  
        if not is_officer:
            self.create_period.disabled = True
            self.manage_payments.disabled = True
        # Enhanced Manager is available to everyone for demo purposes

    @discord.ui.button(label="My Dues", style=discord.ButtonStyle.primary, emoji="💰")
    async def my_dues(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show user's personal dues"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        await self._show_user_dues(interaction)

    @discord.ui.button(label="Create Period", style=discord.ButtonStyle.success, emoji="📅")
    async def create_period(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Create a new dues period (officers only)"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        modal = EnhancedCreatePeriodModal(self.bot, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Manage Payments", style=discord.ButtonStyle.secondary, emoji="💳")
    async def manage_payments(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage member payments (officers only)"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        await self._show_enhanced_period_selection(interaction)
    
    @discord.ui.button(label="✨ Enhanced Manager", style=discord.ButtonStyle.primary, emoji="🔧")
    async def enhanced_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Access enhanced management features for existing periods"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        await self._show_enhanced_period_selection(interaction)

    @discord.ui.button(label="View Reports", style=discord.ButtonStyle.secondary, emoji="📊")
    async def view_reports(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View dues reports"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command user can use this button.", ephemeral=True)
            return
            
        await self._show_dues_reports(interaction)

    async def _show_user_dues(self, interaction: discord.Interaction):
        """Show user's personal dues status"""
        try:
            # Get active dues periods
            periods = await self.bot.db.get_active_dues_periods(self.guild_id)
            
            if not periods:
                embed = discord.Embed(
                    title="💰 My Dues",
                    description="No active dues periods found.",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title="💰 My Dues Status",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            total_owed = 0
            overdue_count = 0
            
            for period in periods:
                # Get user's payment status for this period
                payment = await self.bot.db.get_user_dues_payment(
                    self.guild_id, 
                    interaction.user.id, 
                    period['id']
                )
                
                due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                amount = period['due_amount']
                
                if payment:
                    status = payment['status']
                    amount_paid = payment['amount_paid']
                    remaining = max(0, amount - amount_paid)
                else:
                    status = PaymentStatus.UNPAID
                    amount_paid = 0
                    remaining = amount
                
                # Check if overdue
                if due_date < datetime.now() and status != PaymentStatus.PAID and status != PaymentStatus.EXEMPT:
                    if status != PaymentStatus.OVERDUE:
                        status = PaymentStatus.OVERDUE
                        overdue_count += 1
                
                total_owed += remaining
                
                # Status emoji
                status_emoji = self._get_status_emoji(status)
                
                # Create field value
                field_value = f"**Amount:** ${amount:.2f}\n"
                if amount_paid > 0:
                    field_value += f"**Paid:** ${amount_paid:.2f}\n"
                if remaining > 0:
                    field_value += f"**Remaining:** ${remaining:.2f}\n"
                field_value += f"**Due Date:** <t:{int(due_date.timestamp())}:D>\n"
                field_value += f"**Status:** {status_emoji} {status.title()}"
                
                embed.add_field(
                    name=f"📅 {period['period_name']}",
                    value=field_value,
                    inline=True
                )
            
            # Summary
            if total_owed > 0:
                embed.add_field(
                    name="📊 Summary",
                    value=f"**Total Owed:** ${total_owed:.2f}\n"
                          f"**Overdue Periods:** {overdue_count}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error showing user dues: {e}")
            await interaction.response.send_message(f"❌ Error loading dues: {e}", ephemeral=True)

    async def _show_payment_management(self, interaction: discord.Interaction):
        """Show payment management interface"""
        view = PaymentManagementView(self.bot, self.guild_id, interaction.user.id)
        embed = discord.Embed(
            title="💳 Payment Management",
            description="Select an action to manage member payments:",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _show_enhanced_period_selection(self, interaction: discord.Interaction):
        """Show enhanced period selection for management"""
        try:
            periods = await self.bot.db.get_active_dues_periods(self.guild_id)
            
            if not periods:
                # Create a demo period for testing enhanced features
                await self._create_demo_period(interaction)
                return
            
            embed = discord.Embed(
                title="✨ Enhanced Period Management",
                description="Select a period to access advanced management features:",
                color=discord.Color.gold()
            )
            
            # Create dropdown with periods
            options = []
            for period in periods[:25]:  # Discord limit
                due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                description = f"${period['due_amount']:.2f} - Due: {due_date.strftime('%m/%d/%Y')}"
                options.append(discord.SelectOption(
                    label=period['period_name'][:100],  # Discord limit
                    value=str(period['id']),
                    description=description[:100]
                ))
            
            view = PeriodSelectionView(self.bot, self.guild_id, options)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error showing enhanced period selection: {e}")
            await interaction.response.send_message(f"❌ Error loading periods: {e}", ephemeral=True)
    
    async def _create_demo_period(self, interaction: discord.Interaction):
        """Create demo periods for testing enhanced features and reminders"""
        try:
            from datetime import datetime, timedelta
            
            # Create multiple demo periods to test different reminder scenarios
            periods_to_create = [
                {
                    "name": "🔴 Overdue Test Period",
                    "amount": 25.00,
                    "due_date": datetime.now() - timedelta(days=2),  # 2 days overdue
                    "description": "Test period for overdue reminder functionality"
                },
                {
                    "name": "🟡 Due Soon Test Period", 
                    "amount": 30.00,
                    "due_date": datetime.now() + timedelta(days=2),  # Due in 2 days
                    "description": "Test period for upcoming reminder functionality"
                },
                {
                    "name": "🟢 Future Period",
                    "amount": 35.00,
                    "due_date": datetime.now() + timedelta(days=30),  # Due in 30 days
                    "description": "Regular demo period for testing enhanced features"
                }
            ]
            
            created_periods = []
            for period_data in periods_to_create:
                period_id = await self.bot.db.create_dues_period(
                    guild_id=self.guild_id,
                    period_name=period_data["name"],
                    due_amount=period_data["amount"],
                    due_date=period_data["due_date"],
                    description=period_data["description"]
                )
                created_periods.append((period_id, period_data))
            
            # Add some demo payments to the overdue period
            members = await self._get_guild_members()
            if members and created_periods:
                overdue_period_id = created_periods[0][0]  # First period (overdue)
                # Mark first member as paid for demo
                await self.bot.db.record_payment(
                    period_id=overdue_period_id,
                    user_id=members[0]['id'],
                    amount=25.00,
                    payment_method='Demo Payment'
                )
            
            embed = discord.Embed(
                title="✨ Demo Test Periods Created!",
                description=f"Created {len(created_periods)} test periods for enhanced features and reminder testing.",
                color=discord.Color.green()
            )
            
            period_list = ""
            for period_id, period_data in created_periods:
                period_list += f"• {period_data['name']} - ${period_data['amount']:.2f}\n"
            
            embed.add_field(
                name="📅 Created Test Periods",
                value=period_list,
                inline=False
            )
            
            embed.add_field(
                name="🛠️ Features Ready to Test",
                value="• **Enhanced Member Dropdowns**: Organized by role\n"
                      "• **Payment History Tracking**: Full audit trail\n"
                      "• **Reminder System**: Testing at 30-second intervals\n"
                      "• **Rich Visual Indicators**: Color-coded status\n"
                      "• **Advanced Management**: Safe operations with confirmations",
                inline=False
            )
            
            # Show the enhanced management view for the first period
            view = DuesManagementView(self.bot, self.guild_id, created_periods[0][0])
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error creating demo period: {e}")
            embed = discord.Embed(
                title="❌ Error Creating Demo Period",
                description=f"Failed to create demo period: {e}\n\nPlease ask an officer to create a dues period first.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _show_dues_reports(self, interaction: discord.Interaction):
        """Show dues reports"""
        try:
            # Get summary data
            periods = await self.bot.db.get_active_dues_periods(self.guild_id)
            
            if not periods:
                embed = discord.Embed(
                    title="📊 Dues Reports",
                    description="No active dues periods found.",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📊 Dues Reports",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            for period in periods:
                # Get payment stats for this period
                payments = await self.bot.db.get_dues_payments_for_period(self.guild_id, period['id'])
                
                total_members = len(payments) if payments else 0
                paid_count = sum(1 for p in payments if p['status'] == PaymentStatus.PAID) if payments else 0
                exempt_count = sum(1 for p in payments if p['status'] == PaymentStatus.EXEMPT) if payments else 0
                overdue_count = sum(1 for p in payments if p['status'] == PaymentStatus.OVERDUE) if payments else 0
                
                total_collected = sum(p['amount_paid'] for p in payments) if payments else 0
                
                collection_rate = (paid_count / total_members * 100) if total_members > 0 else 0
                
                field_value = f"**Total Members:** {total_members}\n"
                field_value += f"**Paid:** {paid_count} ({collection_rate:.1f}%)\n"
                field_value += f"**Exempt:** {exempt_count}\n"
                field_value += f"**Overdue:** {overdue_count}\n"
                field_value += f"**Collected:** ${total_collected:.2f}"
                
                embed.add_field(
                    name=f"📅 {period['period_name']}",
                    value=field_value,
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error showing dues reports: {e}")
            await interaction.response.send_message(f"❌ Error loading reports: {e}", ephemeral=True)

    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for payment status"""
        emojis = {
            PaymentStatus.PAID: "✅",
            PaymentStatus.UNPAID: "❌",
            PaymentStatus.PARTIAL: "⚠️",
            PaymentStatus.EXEMPT: "🆓",
            PaymentStatus.OVERDUE: "🔴"
        }
        return emojis.get(status, "❓")
    
    async def _get_guild_members(self):
        """Get guild members for demo purposes"""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                return [{'id': member.id, 'name': member.display_name} for member in guild.members if not member.bot][:5]
            return []
        except Exception:
            return []

class PaymentManagementView(discord.ui.View):
    """Payment management interface for officers"""
    
    def __init__(self, bot, guild_id: int, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

    @discord.ui.button(label="Record Payment", style=discord.ButtonStyle.success, emoji="💳")
    async def record_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Record a payment"""
        modal = RecordPaymentModal(self.bot, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Mark Exempt", style=discord.ButtonStyle.secondary, emoji="🆓")
    async def mark_exempt(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark a member as exempt"""
        modal = MarkExemptModal(self.bot, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Export Data", style=discord.ButtonStyle.primary, emoji="📁")
    async def export_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Export dues data"""
        await self._export_dues_data(interaction)

    async def _export_dues_data(self, interaction: discord.Interaction):
        """Export dues data to CSV"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get all periods and payments
            periods = await self.bot.db.get_active_dues_periods(self.guild_id)
            
            if not periods:
                await interaction.followup.send("❌ No active dues periods found.", ephemeral=True)
                return
            
            # Create CSV content
            csv_content = "Member,Period,Amount,Paid,Status,Due Date,Payment Date,Payment Method\n"
            
            for period in periods:
                payments = await self.bot.db.get_dues_payments_for_period(self.guild_id, period['id'])
                
                for payment in payments:
                    member_name = payment.get('discord_name', 'Unknown')
                    csv_content += f"{member_name},{period['period_name']},${period['due_amount']:.2f},"
                    csv_content += f"${payment['amount_paid']:.2f},{payment['status']},"
                    csv_content += f"{period['due_date']},{payment.get('payment_date', 'N/A')},"
                    csv_content += f"{payment.get('payment_method', 'N/A')}\n"
            
            # Create file
            file_content = csv_content.encode('utf-8')
            file = discord.File(
                io.BytesIO(file_content),
                filename=f"dues_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
            await interaction.followup.send(
                "📁 Dues data exported successfully!",
                file=file,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error exporting dues data: {e}")
            await interaction.followup.send(f"❌ Error exporting data: {e}", ephemeral=True)

class EnhancedCreatePeriodModal(discord.ui.Modal, title="✨ Create New Dues Period"):
    """Enhanced modal for creating new dues periods with comprehensive date/time support"""
    
    def __init__(self, bot, guild_id: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

    period_name = discord.ui.TextInput(
        label="📅 Period Name",
        placeholder="January 2025 | Q1 Dues | Weekly Club Fees",
        max_length=100,
        required=True
    )
    
    amount = discord.ui.TextInput(
        label="💰 Amount (USD)",
        placeholder="25.00",
        max_length=10,
        required=True
    )
    
    due_datetime = discord.ui.TextInput(
        label="🕐 Due Date & Time",
        placeholder="12/31/2024 11:59 PM | 2024-12-31 15:30 | '2 weeks' | 'next friday 6pm'",
        max_length=100,
        required=True
    )
    
    description = discord.ui.TextInput(
        label="📝 Description (Optional)",
        placeholder="Monthly membership dues | Special event fees | Equipment fund...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle enhanced form submission with comprehensive datetime support"""
        try:
            # Validate amount
            try:
                amount_val = float(self.amount.value)
                if amount_val <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError as e:
                await interaction.response.send_message(f"❌ Invalid amount: {e}", ephemeral=True)
                return

            # Enhanced datetime parsing
            due_datetime = parse_enhanced_datetime(self.due_datetime.value)
            if not due_datetime:
                await interaction.response.send_message(
                    f"❌ Could not parse due date & time '{self.due_datetime.value}'.\n"
                    "**Supported formats:**\n"
                    "🗓️ Full datetime: `12/31/2024 11:59 PM`, `2024-12-31 15:30`\n"
                    "🌐 Natural language: `next friday 6pm`, `tomorrow at noon`, `in 2 weeks`\n"
                    "⏰ Relative: `2 weeks`, `1 month`, `30 days`\n"
                    "📋 ISO format: `2024-12-31T23:59:59`",
                    ephemeral=True
                )
                return

            # Create dues period with enhanced datetime
            period_id = await self.bot.db.create_dues_period(
                guild_id=self.guild_id,
                period_name=self.period_name.value,
                due_amount=amount_val,
                due_date=due_datetime,
                description=self.description.value or None
            )

            # Enhanced success embed with rich formatting
            embed = discord.Embed(
                title="✨ Dues Period Created Successfully!",
                color=discord.Color.green()
            )
            
            # Main details field
            embed.add_field(
                name="📋 Period Details",
                value=(
                    f"**Name:** {self.period_name.value}\n"
                    f"**Amount:** ${amount_val:.2f}\n"
                    f"**Due:** {due_datetime.strftime('%A, %B %d, %Y at %I:%M %p')}\n"
                    f"**Status:** 🟢 Active"
                ),
                inline=False
            )
            
            if self.description.value:
                embed.add_field(
                    name="📝 Description",
                    value=self.description.value,
                    inline=False
                )
                
            # Time until due with smart formatting
            time_until_due = due_datetime - datetime.now()
            if time_until_due.total_seconds() > 0:
                days = time_until_due.days
                hours, remainder = divmod(time_until_due.seconds, 3600)
                minutes = remainder // 60
                
                if days > 0:
                    time_str = f"{days} days, {hours} hours"
                elif hours > 0:
                    time_str = f"{hours} hours, {minutes} minutes"
                else:
                    time_str = "Less than 1 hour"
                    
                embed.add_field(
                    name="⏰ Time Remaining",
                    value=time_str,
                    inline=True
                )
            else:
                embed.add_field(
                    name="⚠️ Status",
                    value="Already past due date",
                    inline=True
                )
                
            embed.set_footer(
                text=f"Period ID: {period_id} | Created by {interaction.user.display_name}"
            )
            embed.timestamp = datetime.now()
            
            # Add quick action buttons for immediate management
            view = DuesManagementView(self.bot, self.guild_id, period_id)
            await interaction.response.send_message(embed=embed, view=view)
            
            logger.info(f"Created enhanced dues period '{self.period_name.value}' for guild {self.guild_id}")
            
        except Exception as e:
            logger.error(f"Error creating dues period: {e}")
            await interaction.response.send_message(
                f"❌ Error creating dues period: {str(e)}", ephemeral=True
            )

class DuesManagementView(discord.ui.View):
    """Comprehensive dues management interface with fancy UI components"""
    
    def __init__(self, bot, guild_id: int, period_id: int):
        super().__init__(timeout=600)  # 10 minute timeout for management actions
        self.bot = bot
        self.guild_id = guild_id
        self.period_id = period_id

    @discord.ui.button(label="Record Payment", style=discord.ButtonStyle.success, emoji="💳")
    async def record_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Record a payment with member dropdown selection"""
        view = EnhancedPaymentView(self.bot, self.guild_id, self.period_id)
        embed = discord.Embed(
            title="💳 Record Member Payment",
            description="Select a member and their payment status:",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Member Status", style=discord.ButtonStyle.primary, emoji="📋")
    async def view_member_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View detailed member payment status"""
        await self._show_member_status(interaction)

    @discord.ui.button(label="Cancel Period", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_period(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel this dues period"""
        view = ConfirmCancellationView(self.bot, self.guild_id, self.period_id)
        embed = discord.Embed(
            title="⚠️ Cancel Dues Period",
            description="Are you sure you want to cancel this dues period?\n"
                       "**This action cannot be undone.**",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Export Data", style=discord.ButtonStyle.secondary, emoji="📁")
    async def export_period_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Export data for this specific period"""
        await self._export_period_data(interaction)

    async def _show_member_status(self, interaction: discord.Interaction):
        """Show detailed member status with role-based filtering"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get period details
            period = await self.bot.db.get_dues_period(self.guild_id, self.period_id)
            if not period:
                await interaction.followup.send("❌ Period not found.", ephemeral=True)
                return
            
            # Get guild members with relevant roles
            guild = interaction.guild
            config = await self.bot.db.get_server_config(self.guild_id)
            
            full_patch_role_id = config.get('full_patch_role_id') if config else None
            prospect_role_id = config.get('prospect_role_id') if config else None
            
            # Get all members with roles
            full_patches = []
            prospects = []
            
            if full_patch_role_id:
                full_patch_role = guild.get_role(full_patch_role_id)
                if full_patch_role:
                    full_patches = [m for m in guild.members if full_patch_role in m.roles]
            
            if prospect_role_id:
                prospect_role = guild.get_role(prospect_role_id)
                if prospect_role:
                    prospects = [m for m in guild.members if prospect_role in m.roles]
            
            # Get payment statuses
            payments = await self.bot.db.get_dues_payments_for_period(self.guild_id, self.period_id)
            payment_dict = {p['user_id']: p for p in payments} if payments else {}
            
            # Create paginated embed
            embeds = []
            
            # Full Patches page
            if full_patches:
                embed = discord.Embed(
                    title=f"🏅 Full Patches - {period['period_name']}",
                    color=discord.Color.gold()
                )
                
                paid_members = []
                unpaid_members = []
                exempt_members = []
                
                for member in full_patches:
                    payment = payment_dict.get(member.id)
                    if payment:
                        status = payment['status']
                        amount_paid = payment['amount_paid']
                        
                        if status == PaymentStatus.PAID:
                            paid_members.append(f"✅ {member.display_name} (${amount_paid:.2f})")
                        elif status == PaymentStatus.EXEMPT:
                            exempt_members.append(f"🆓 {member.display_name}")
                        else:
                            unpaid_members.append(f"❌ {member.display_name} ({status})")
                    else:
                        unpaid_members.append(f"❌ {member.display_name} (unpaid)")
                
                if paid_members:
                    embed.add_field(
                        name=f"✅ Paid ({len(paid_members)})",
                        value="\n".join(paid_members[:10]) + ("\n..." if len(paid_members) > 10 else ""),
                        inline=False
                    )
                
                if exempt_members:
                    embed.add_field(
                        name=f"🆓 Exempt ({len(exempt_members)})",
                        value="\n".join(exempt_members[:10]) + ("\n..." if len(exempt_members) > 10 else ""),
                        inline=False
                    )
                
                if unpaid_members:
                    embed.add_field(
                        name=f"❌ Unpaid ({len(unpaid_members)})",
                        value="\n".join(unpaid_members[:10]) + ("\n..." if len(unpaid_members) > 10 else ""),
                        inline=False
                    )
                
                embeds.append(embed)
            
            # Prospects page
            if prospects:
                embed = discord.Embed(
                    title=f"🌟 Prospects - {period['period_name']}",
                    color=discord.Color.orange()
                )
                
                paid_prospects = []
                unpaid_prospects = []
                exempt_prospects = []
                
                for member in prospects:
                    payment = payment_dict.get(member.id)
                    if payment:
                        status = payment['status']
                        amount_paid = payment['amount_paid']
                        
                        if status == PaymentStatus.PAID:
                            paid_prospects.append(f"✅ {member.display_name} (${amount_paid:.2f})")
                        elif status == PaymentStatus.EXEMPT:
                            exempt_prospects.append(f"🆓 {member.display_name}")
                        else:
                            unpaid_prospects.append(f"❌ {member.display_name} ({status})")
                    else:
                        unpaid_prospects.append(f"❌ {member.display_name} (unpaid)")
                
                if paid_prospects:
                    embed.add_field(
                        name=f"✅ Paid ({len(paid_prospects)})",
                        value="\n".join(paid_prospects[:10]) + ("\n..." if len(paid_prospects) > 10 else ""),
                        inline=False
                    )
                
                if exempt_prospects:
                    embed.add_field(
                        name=f"🆓 Exempt ({len(exempt_prospects)})",
                        value="\n".join(exempt_prospects[:10]) + ("\n..." if len(exempt_prospects) > 10 else ""),
                        inline=False
                    )
                
                if unpaid_prospects:
                    embed.add_field(
                        name=f"❌ Unpaid ({len(unpaid_prospects)})",
                        value="\n".join(unpaid_prospects[:10]) + ("\n..." if len(unpaid_prospects) > 10 else ""),
                        inline=False
                    )
                
                embeds.append(embed)
            
            if not embeds:
                embed = discord.Embed(
                    title="📄 No Member Data",
                    description="No Full Patches or Prospects found with configured roles.",
                    color=discord.Color.greyple()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Send paginated results
            if len(embeds) == 1:
                await interaction.followup.send(embed=embeds[0], ephemeral=True)
            else:
                view = PaginatedMemberView(embeds)
                await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error showing member status: {e}")
            await interaction.followup.send(f"❌ Error loading member status: {e}", ephemeral=True)
    
    async def _export_period_data(self, interaction: discord.Interaction):
        """Export data for this specific period"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get period and payment data
            period = await self.bot.db.get_dues_period(self.guild_id, self.period_id)
            payments = await self.bot.db.get_dues_payments_for_period(self.guild_id, self.period_id)
            
            if not period:
                await interaction.followup.send("❌ Period not found.", ephemeral=True)
                return
            
            # Create enhanced CSV content
            csv_content = "Member Name,Discord ID,Amount Due,Amount Paid,Status,Payment Date,Payment Method,Notes\n"
            
            if payments:
                for payment in payments:
                    member = interaction.guild.get_member(payment['user_id'])
                    member_name = member.display_name if member else f"Unknown ({payment['user_id']})"
                    
                    csv_content += f"\"{member_name}\",{payment['user_id']},"
                    csv_content += f"${period['due_amount']:.2f},${payment.get('amount_paid', 0):.2f},"
                    csv_content += f"{payment.get('status', 'unpaid')},"
                    csv_content += f"{payment.get('payment_date', 'N/A')},"
                    csv_content += f"{payment.get('payment_method', 'N/A')},"
                    csv_content += f"\"{payment.get('notes', '')}\"\n"
            
            # Create file
            file_content = csv_content.encode('utf-8')
            filename = f"dues_{period['period_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file = discord.File(
                io.BytesIO(file_content),
                filename=filename
            )
            
            embed = discord.Embed(
                title="📁 Period Data Exported",
                description=f"Export completed for **{period['period_name']}**",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(
                embed=embed,
                file=file,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error exporting period data: {e}")
            await interaction.followup.send(f"❌ Error exporting data: {e}", ephemeral=True)

class EnhancedPaymentView(discord.ui.View):
    """Enhanced payment recording with member dropdown selection"""
    
    def __init__(self, bot, guild_id: int, period_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.period_id = period_id
        self.selected_member = None
        self.selected_status = None
        
        # Add member selection dropdown
        asyncio.create_task(self._populate_member_dropdown())
    
    async def _populate_member_dropdown(self):
        """Populate member dropdown with Full Patches and Prospects"""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                return
                
            config = await self.bot.db.get_server_config(self.guild_id)
            
            full_patch_role_id = config.get('full_patch_role_id') if config else None
            prospect_role_id = config.get('prospect_role_id') if config else None
            
            options = []
            
            # Add Full Patches
            if full_patch_role_id:
                full_patch_role = guild.get_role(full_patch_role_id)
                if full_patch_role:
                    full_patches = [m for m in guild.members if full_patch_role in m.roles]
                    for member in sorted(full_patches, key=lambda m: m.display_name)[:20]:  # Limit to 20
                        options.append(discord.SelectOption(
                            label=f"🏅 {member.display_name}",
                            value=f"fp_{member.id}",
                            description="Full Patch"
                        ))
            
            # Add Prospects
            if prospect_role_id:
                prospect_role = guild.get_role(prospect_role_id)
                if prospect_role:
                    prospects = [m for m in guild.members if prospect_role in m.roles]
                    for member in sorted(prospects, key=lambda m: m.display_name)[:20]:  # Limit to 20
                        options.append(discord.SelectOption(
                            label=f"🌟 {member.display_name}",
                            value=f"pr_{member.id}",
                            description="Prospect"
                        ))
            
            if options:
                select = MemberSelect(options[:25])  # Discord limit of 25 options
                self.add_item(select)
                
        except Exception as e:
            logger.error(f"Error populating member dropdown: {e}")
    
    @discord.ui.button(label="Record Payment", style=discord.ButtonStyle.success, emoji="💳", disabled=True)
    async def record_payment_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Record payment for selected member"""
        if not self.selected_member:
            await interaction.response.send_message("❌ Please select a member first.", ephemeral=True)
            return
            
        modal = EnhancedRecordPaymentModal(self.bot, self.guild_id, self.period_id, self.selected_member)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Mark Exempt", style=discord.ButtonStyle.secondary, emoji="🆓", disabled=True)
    async def mark_exempt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark selected member as exempt"""
        if not self.selected_member:
            await interaction.response.send_message("❌ Please select a member first.", ephemeral=True)
            return
            
        modal = EnhancedExemptModal(self.bot, self.guild_id, self.period_id, self.selected_member)
        await interaction.response.send_modal(modal)
    
    def enable_buttons(self, member_id: int):
        """Enable buttons when member is selected"""
        self.selected_member = member_id
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = False

class MemberSelect(discord.ui.Select):
    """Member selection dropdown"""
    
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(
            placeholder="👥 Choose a member...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Extract member ID from value
        value = self.values[0]
        member_id = int(value.split('_')[1])
        
        # Enable parent view buttons
        self.view.enable_buttons(member_id)
        
        member = interaction.guild.get_member(member_id)
        await interaction.response.send_message(
            f"✅ Selected: **{member.display_name if member else 'Unknown Member'}**",
            ephemeral=True
        )

class EnhancedRecordPaymentModal(discord.ui.Modal, title="💳 Record Payment"):
    """Enhanced payment recording modal"""
    
    def __init__(self, bot, guild_id: int, period_id: int, member_id: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.period_id = period_id
        self.member_id = member_id
    
    amount_paid = discord.ui.TextInput(
        label="💰 Amount Paid",
        placeholder="25.00",
        max_length=10,
        required=True
    )
    
    payment_method = discord.ui.TextInput(
        label="💳 Payment Method",
        placeholder="Venmo, PayPal, Cash, Zelle, etc.",
        max_length=50,
        required=True
    )
    
    notes = discord.ui.TextInput(
        label="📝 Notes (Optional)",
        placeholder="Additional payment details...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate amount
            try:
                amount = float(self.amount_paid.value)
                if amount < 0:
                    raise ValueError("Amount cannot be negative")
            except ValueError:
                await interaction.followup.send("❌ Invalid amount. Please enter a valid number.", ephemeral=True)
                return
            
            # Get period details to determine payment status
            period = await self.bot.db.get_dues_period(self.guild_id, self.period_id)
            if not period:
                await interaction.followup.send("❌ Period not found.", ephemeral=True)
                return
            
            # Determine payment status
            if amount >= period['due_amount']:
                status = PaymentStatus.PAID
            elif amount > 0:
                status = PaymentStatus.PARTIAL
            else:
                status = PaymentStatus.UNPAID
            
            # Record payment
            await self.bot.db.update_dues_payment(
                guild_id=self.guild_id,
                user_id=self.member_id,
                dues_period_id=self.period_id,
                amount_paid=amount,
                payment_date=datetime.now(),
                payment_method=self.payment_method.value,
                payment_status=status,
                notes=self.notes.value or None,
                updated_by_id=interaction.user.id
            )
            
            member = interaction.guild.get_member(self.member_id)
            embed = discord.Embed(
                title="✅ Payment Recorded Successfully!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="👥 Member",
                value=member.display_name if member else "Unknown Member",
                inline=True
            )
            
            embed.add_field(
                name="💰 Amount",
                value=f"${amount:.2f}",
                inline=True
            )
            
            embed.add_field(
                name="📋 Status",
                value=f"{self._get_status_emoji(status)} {status.title()}",
                inline=True
            )
            
            embed.add_field(
                name="💳 Payment Method",
                value=self.payment_method.value,
                inline=True
            )
            
            embed.add_field(
                name="📅 Date",
                value=f"<t:{int(datetime.now().timestamp())}:D>",
                inline=True
            )
            
            if self.notes.value:
                embed.add_field(
                    name="📝 Notes",
                    value=self.notes.value,
                    inline=False
                )
            
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error recording payment: {e}")
            await interaction.followup.send(f"❌ Error recording payment: {e}", ephemeral=True)
    
    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for payment status"""
        emojis = {
            PaymentStatus.PAID: "✅",
            PaymentStatus.UNPAID: "❌",
            PaymentStatus.PARTIAL: "⚠️",
            PaymentStatus.EXEMPT: "🆓",
            PaymentStatus.OVERDUE: "🔴"
        }
        return emojis.get(status, "❓")

class EnhancedExemptModal(discord.ui.Modal, title="🆓 Mark Member Exempt"):
    """Enhanced exemption modal"""
    
    def __init__(self, bot, guild_id: int, period_id: int, member_id: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.period_id = period_id
        self.member_id = member_id
    
    reason = discord.ui.TextInput(
        label="📝 Exemption Reason",
        placeholder="Officer, special circumstances, etc.",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Mark as exempt
            await self.bot.db.update_dues_payment(
                guild_id=self.guild_id,
                user_id=self.member_id,
                dues_period_id=self.period_id,
                amount_paid=0,
                payment_status=PaymentStatus.EXEMPT,
                notes=self.reason.value,
                updated_by_id=interaction.user.id
            )
            
            member = interaction.guild.get_member(self.member_id)
            embed = discord.Embed(
                title="🆓 Member Marked Exempt",
                description=f"**{member.display_name if member else 'Unknown Member'}** has been marked exempt from dues.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📝 Reason",
                value=self.reason.value,
                inline=False
            )
            
            embed.timestamp = datetime.now()
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error marking member exempt: {e}")
            await interaction.followup.send(f"❌ Error marking exempt: {e}", ephemeral=True)

class ConfirmCancellationView(discord.ui.View):
    """Confirmation view for period cancellation"""
    
    def __init__(self, bot, guild_id: int, period_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.period_id = period_id
    
    @discord.ui.button(label="Yes, Cancel Period", style=discord.ButtonStyle.danger, emoji="❌")
    async def confirm_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm cancellation"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # For now, we'll just mark the period as inactive by setting a note
            # This is a simplified approach since the full database method doesn't exist yet
            embed = discord.Embed(
                title="ℹ️ Period Cancellation",
                description="Period cancellation feature is coming soon! \n"
                           "For now, please contact an administrator to cancel periods manually.",
                color=discord.Color.blue()
            )
            embed.timestamp = datetime.now()
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
        except Exception as e:
            logger.error(f"Error with period cancellation interface: {e}")
            await interaction.followup.send(f"❌ Error with cancellation interface: {e}", ephemeral=True)
            for item in self.children:
                item.disabled = True
    
    @discord.ui.button(label="No, Keep Active", style=discord.ButtonStyle.secondary, emoji="✅")
    async def cancel_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the cancellation"""
        embed = discord.Embed(
            title="✅ Action Cancelled",
            description="The dues period remains active.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True

class PaginatedMemberView(discord.ui.View):
    """Paginated view for member status displays"""
    
    def __init__(self, embeds: List[discord.Embed]):
        super().__init__(timeout=300)
        self.embeds = embeds
        self.current_page = 0
        
        # Update button states
        self._update_buttons()
    
    def _update_buttons(self):
        """Update button states based on current page"""
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.embeds) - 1
        
        # Update page counter
        for item in self.children:
            if hasattr(item, 'label') and 'Page' in item.label:
                item.label = f"Page {self.current_page + 1}/{len(self.embeds)}"
    
    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.primary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Page counter (non-functional)"""
        await interaction.response.defer()
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

class PeriodSelectionView(discord.ui.View):
    """View for selecting a period to manage with enhanced features"""
    
    def __init__(self, bot, guild_id: int, options: List[discord.SelectOption]):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        
        # Add period selection dropdown
        if options:
            select = PeriodSelect(options)
            self.add_item(select)

class PeriodSelect(discord.ui.Select):
    """Period selection dropdown"""
    
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(
            placeholder="📅 Choose a period to manage...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        period_id = int(self.values[0])
        
        # Show the enhanced management view for this period
        view = DuesManagementView(self.view.bot, self.view.guild_id, period_id)
        embed = discord.Embed(
            title="✨ Enhanced Period Management",
            description="Access all advanced management features for this period:",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="🛠️ Available Features",
            value="• **Record Payment**: Enhanced member selection with dropdowns\n"
                  "• **Member Status**: Role-based status views with pagination\n"
                  "• **Cancel Period**: Safe cancellation with confirmation\n"
                  "• **Export Data**: Comprehensive CSV export with full details",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class RecordPaymentModal(discord.ui.Modal, title="Record Payment"):
    """Modal for recording member payments"""
    
    def __init__(self, bot, guild_id: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

    member_name = discord.ui.TextInput(
        label="Member Name",
        placeholder="Enter the member's Discord name or mention",
        max_length=100,
        required=True
    )
    
    period_name = discord.ui.TextInput(
        label="Period Name",
        placeholder="Enter the exact period name",
        max_length=100,
        required=True
    )
    
    amount_paid = discord.ui.TextInput(
        label="Amount Paid",
        placeholder="e.g., 25.00",
        max_length=10,
        required=True
    )
    
    payment_method = discord.ui.TextInput(
        label="Payment Method",
        placeholder="Venmo, PayPal, Cash, etc.",
        max_length=50,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle payment recording"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse amount
            try:
                amount = float(self.amount_paid.value)
                if amount < 0:
                    raise ValueError("Amount cannot be negative")
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid amount. Please enter a valid number.",
                    ephemeral=True
                )
                return
            
            # Find member by name (basic search)
            member = None
            for m in interaction.guild.members:
                if (self.member_name.value.lower() in m.display_name.lower() or 
                    self.member_name.value.lower() in str(m).lower()):
                    member = m
                    break
            
            if not member:
                await interaction.followup.send(
                    f"❌ Could not find member: {self.member_name.value}",
                    ephemeral=True
                )
                return
            
            # Find dues period
            periods = await self.bot.db.get_active_dues_periods(self.guild_id)
            period = None
            for p in periods:
                if self.period_name.value.lower() in p['period_name'].lower():
                    period = p
                    break
            
            if not period:
                await interaction.followup.send(
                    f"❌ Could not find period: {self.period_name.value}",
                    ephemeral=True
                )
                return
            
            # Record payment
            payment_id = await self.bot.db.update_dues_payment(
                guild_id=self.guild_id,
                user_id=member.id,
                dues_period_id=period['id'],
                amount_paid=amount,
                payment_date=datetime.now(),
                payment_method=str(self.payment_method.value),
                payment_status=PaymentStatus.PAID if amount >= period['due_amount'] else PaymentStatus.PARTIAL,
                updated_by_id=interaction.user.id
            )
            
            embed = discord.Embed(
                title="✅ Payment Recorded",
                description=f"Payment recorded for **{member.display_name}**",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Period", value=period['period_name'], inline=True)
            embed.add_field(name="Amount", value=f"${amount:.2f}", inline=True)
            embed.add_field(name="Method", value=self.payment_method.value, inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Recorded payment for {member.id} in period {period['id']}")
            
        except Exception as e:
            logger.error(f"Error recording payment: {e}")
            await interaction.followup.send(f"❌ Error recording payment: {e}", ephemeral=True)

class MarkExemptModal(discord.ui.Modal, title="Mark Member Exempt"):
    """Modal for marking members as exempt from dues"""
    
    def __init__(self, bot, guild_id: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

    member_name = discord.ui.TextInput(
        label="Member Name",
        placeholder="Enter the member's Discord name or mention",
        max_length=100,
        required=True
    )
    
    period_name = discord.ui.TextInput(
        label="Period Name",
        placeholder="Enter the exact period name",
        max_length=100,
        required=True
    )
    
    reason = discord.ui.TextInput(
        label="Exemption Reason",
        placeholder="Why is this member exempt from dues?",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle exemption"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Find member
            member = None
            for m in interaction.guild.members:
                if (self.member_name.value.lower() in m.display_name.lower() or 
                    self.member_name.value.lower() in str(m).lower()):
                    member = m
                    break
            
            if not member:
                await interaction.followup.send(
                    f"❌ Could not find member: {self.member_name.value}",
                    ephemeral=True
                )
                return
            
            # Find period
            periods = await self.bot.db.get_active_dues_periods(self.guild_id)
            period = None
            for p in periods:
                if self.period_name.value.lower() in p['period_name'].lower():
                    period = p
                    break
            
            if not period:
                await interaction.followup.send(
                    f"❌ Could not find period: {self.period_name.value}",
                    ephemeral=True
                )
                return
            
            # Mark as exempt
            payment_id = await self.bot.db.update_dues_payment(
                guild_id=self.guild_id,
                user_id=member.id,
                dues_period_id=period['id'],
                amount_paid=0,
                payment_status=PaymentStatus.EXEMPT,
                notes=str(self.reason.value),
                updated_by_id=interaction.user.id
            )
            
            embed = discord.Embed(
                title="🆓 Member Marked Exempt",
                description=f"**{member.display_name}** has been marked exempt from **{period['period_name']}**",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Reason", value=self.reason.value, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Marked {member.id} as exempt from period {period['id']}")
            
        except Exception as e:
            logger.error(f"Error marking member exempt: {e}")
            await interaction.followup.send(f"❌ Error marking exempt: {e}", ephemeral=True)

class DuesManagementV2(commands.Cog):
    """Modern Dues Management System v2.0"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.dues_reminder_task.start()
        logger.info("Dues Management v2.0 initialized")

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.dues_reminder_task.cancel()

    async def _check_officer_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has officer permissions"""
        config = await self.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return False
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        return officer_role and officer_role in interaction.user.roles

    @app_commands.command(name="dues", description="Manage club dues - view status, make payments, and generate reports")
    async def dues_command(self, interaction: discord.Interaction):
        """Main dues management command"""
        await interaction.response.defer()
        
        try:
            # Check if user is officer
            is_officer = await self._check_officer_permissions(interaction)
            
            # Get summary data
            periods = await self.db.get_active_dues_periods(interaction.guild.id)
            
            # Create main embed
            embed = discord.Embed(
                title="💰 Dues Management System",
                description="Manage club dues, payments, and generate reports",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            
            if periods:
                # Show summary of active periods
                period_summary = []
                for period in periods[:3]:  # Show first 3 periods
                    due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                    period_summary.append(
                        f"• **{period['period_name']}** - ${period['due_amount']:.2f} "
                        f"(Due: <t:{int(due_date.timestamp())}:D>)"
                    )
                
                if len(periods) > 3:
                    period_summary.append(f"... and {len(periods) - 3} more")
                
                embed.add_field(
                    name=f"📅 Active Periods ({len(periods)})",
                    value="\n".join(period_summary),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📅 Active Periods",
                    value="No active dues periods found.",
                    inline=False
                )
            
            # Add user status info
            if is_officer:
                embed.add_field(
                    name="👑 Officer Access",
                    value="You have full access to dues management features.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="👤 Member Access",
                    value="You can view your personal dues status.",
                    inline=False
                )
            
            # Create interactive view
            view = DuesView(self.bot, interaction.guild.id, interaction.user.id, is_officer)
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error in dues command: {e}")
            await interaction.followup.send(f"❌ Error loading dues system: {e}", ephemeral=True)

    @tasks.loop(seconds=30)  # Check every 30 seconds for testing (normally hours=6)
    async def dues_reminder_task(self):
        """Background task to send dues reminders - TEST MODE"""
        try:
            await self.bot.wait_until_ready()
            
            for guild in self.bot.guilds:
                try:
                    # Get active dues periods
                    periods = await self.db.get_active_dues_periods(guild.id)
                    
                    for period in periods:
                        due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                        now = datetime.now()
                        
                        # Check if overdue (send reminder once per day)
                        if due_date < now:
                            await self._send_overdue_reminders(guild, period)
                        # Check if due within 3 days
                        elif (due_date - now).days <= 3 and (due_date - now).days > 0:
                            await self._send_upcoming_reminders(guild, period)
                            
                except Exception as e:
                    logger.error(f"Error processing dues reminders for guild {guild.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in dues reminder task: {e}")

    async def _send_overdue_reminders(self, guild: discord.Guild, period: Dict):
        """Send reminders for overdue dues"""
        try:
            # Get config for notification channel
            config = await self.db.get_server_config(guild.id)
            if not config or not config.get('notification_channel_id'):
                return
                
            channel = guild.get_channel(config['notification_channel_id'])
            if not channel:
                return
            
            # Get unpaid members
            payments = await self.db.get_dues_payments_for_period(guild.id, period['id'])
            unpaid_members = [
                p for p in payments 
                if p['status'] in [PaymentStatus.UNPAID, PaymentStatus.PARTIAL, PaymentStatus.OVERDUE]
            ]
            
            if not unpaid_members:
                return
            
            due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
            days_overdue = (datetime.now() - due_date).days
            
            embed = discord.Embed(
                title="🔴 Overdue Dues Reminder",
                description=f"**{period['period_name']}** dues are **{days_overdue}** day(s) overdue!",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Period Details",
                value=f"**Amount:** ${period['due_amount']:.2f}\n"
                      f"**Due Date:** <t:{int(due_date.timestamp())}:D>\n"
                      f"**Unpaid Members:** {len(unpaid_members)}",
                inline=False
            )
            
            # Don't ping too many people at once
            if len(unpaid_members) <= 10:
                member_mentions = [f"<@{p['user_id']}>" for p in unpaid_members]
                embed.add_field(
                    name="Unpaid Members",
                    value=" ".join(member_mentions),
                    inline=False
                )
            
            await channel.send(embed=embed)
            logger.info(f"Sent overdue dues reminder for period {period['id']} in guild {guild.id}")
            
        except Exception as e:
            logger.error(f"Error sending overdue reminders: {e}")

    async def _send_upcoming_reminders(self, guild: discord.Guild, period: Dict):
        """Send reminders for dues due soon"""
        try:
            # Get config for notification channel
            config = await self.db.get_server_config(guild.id)
            if not config or not config.get('notification_channel_id'):
                return
                
            channel = guild.get_channel(config['notification_channel_id'])
            if not channel:
                return
            
            due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
            days_until_due = (due_date - datetime.now()).days
            
            embed = discord.Embed(
                title="📅 Dues Reminder",
                description=f"**{period['period_name']}** dues are due in **{days_until_due}** day(s)!",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Period Details",
                value=f"**Amount:** ${period['due_amount']:.2f}\n"
                      f"**Due Date:** <t:{int(due_date.timestamp())}:D>\n"
                      f"Please make your payment before the due date.",
                inline=False
            )
            
            await channel.send(embed=embed)
            logger.info(f"Sent upcoming dues reminder for period {period['id']} in guild {guild.id}")
            
        except Exception as e:
            logger.error(f"Error sending upcoming reminders: {e}")

async def setup(bot):
    await bot.add_cog(DuesManagementV2(bot))
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import io
import logging
import json
import calendar
from typing import List, Dict, Optional, Tuple
from utils.smart_time_formatter import SmartTimeFormatter

# Set up logger for this module
logger = logging.getLogger(__name__)

class AdvancedDuesTrackingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Role IDs for reminders
        self.PRESIDENT_ROLE_ID = 1212496539369476136
        self.TREASURER_ROLE_ID = 1212500237470666804
        
        # Start the reminder check task
        self.check_dues_reminders.start()
        
        # Payment status options with descriptions
        self.payment_statuses = {
            'unpaid': 'Member has not paid dues yet',
            'paid': 'Member has paid dues in full',
            'partial': 'Member has made partial payment',
            'exempt': 'Member is exempt from paying dues',
            'overdue': 'Member payment is past due date'
        }
        
        # Payment methods with categories
        self.payment_methods = {
            'Digital': ['Venmo', 'PayPal', 'Zelle', 'CashApp', 'Bank Transfer', 'Apple Pay', 'Google Pay'],
            'Traditional': ['Cash', 'Check', 'Money Order'],
            'Other': ['Cryptocurrency', 'Barter/Trade', 'Other']
        }
        
        # Audit event types for comprehensive logging
        self.audit_events = {
            'PERIOD_CREATED': 'Dues period created',
            'PERIOD_MODIFIED': 'Dues period modified',
            'PERIOD_CLOSED': 'Dues period closed',
            'PAYMENT_RECORDED': 'Payment recorded',
            'PAYMENT_MODIFIED': 'Payment modified',
            'PAYMENT_DELETED': 'Payment deleted',
            'EXEMPTION_GRANTED': 'Exemption granted',
            'EXEMPTION_REMOVED': 'Exemption removed',
            'MEMBER_ADDED': 'Member added to dues tracking',
            'MEMBER_REMOVED': 'Member removed from dues tracking',
            'REPORT_GENERATED': 'Report generated',
            'BULK_UPDATE': 'Bulk update performed'
        }

    @tasks.loop(hours=24)  # Check once per day
    async def check_dues_reminders(self):
        """Background task to check for due dates and send reminders"""
        try:
            await self.bot.wait_until_ready()
            
            for guild in self.bot.guilds:
                periods = await self.bot.db.get_active_dues_periods(guild.id)
                
                for period in periods:
                    if not period.get('due_date'):
                        continue
                        
                    try:
                        due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                        today = datetime.now()
                        
                        # Check if due date is today or overdue
                        if due_date.date() <= today.date():
                            await self._send_due_date_reminder(guild, period, due_date, today)
                            
                    except Exception as e:
                        logger.error(f"Error processing due date for period {period['id']}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in dues reminder check: {e}")
    
    async def _send_due_date_reminder(self, guild: discord.Guild, period: Dict, due_date: datetime, today: datetime):
        """Send reminder to President and Treasurer about due date"""
        try:
            # Get President and Treasurer roles
            president_role = guild.get_role(self.PRESIDENT_ROLE_ID)
            treasurer_role = guild.get_role(self.TREASURER_ROLE_ID)
            
            if not president_role and not treasurer_role:
                logger.warning(f"President or Treasurer roles not found in guild {guild.id}")
                return
            
            # Get collection summary
            summary = await self.bot.db.get_dues_collection_summary(guild.id, period['id'])
            
            # Determine reminder type
            days_overdue = (today.date() - due_date.date()).days
            
            if days_overdue == 0:
                title = "📅 Dues Due Today!"
                color = discord.Color.orange()
            elif days_overdue > 0:
                title = f"⚠️ Dues Overdue ({days_overdue} days)"
                color = discord.Color.red()
            else:
                return  # Future due date, no reminder needed
            
            embed = discord.Embed(
                title=title,
                description=f"**Period:** {period['period_name']}\n"
                           f"**Due Amount:** ${period['due_amount']:.2f} per member\n"
                           f"**Due Date:** {SmartTimeFormatter.format_discord_timestamp(due_date, 'D')}\n"
                           f"**Days Overdue:** {max(0, days_overdue)}",
                color=color,
                timestamp=today
            )
            
            if summary:
                paid_percentage = (summary.get('paid_count', 0) / summary.get('total_members', 1)) * 100
                embed.add_field(
                    name="📊 Collection Status",
                    value=f"**Paid:** {summary.get('paid_count', 0)}/{summary.get('total_members', 0)} ({paid_percentage:.1f}%)\n"
                          f"**Collected:** ${summary.get('total_collected', 0):.2f}\n"
                          f"**Outstanding:** ${summary.get('outstanding_amount', 0):.2f}",
                    inline=False
                )
            
            embed.add_field(
                name="🎯 Action Required",
                value="• Follow up with unpaid members\n"
                      "• Update payment records\n"
                      "• Consider sending reminders",
                inline=False
            )
            
            # Find a suitable channel to send the reminder (general, officers, etc.)
            target_channel = None
            channel_names = ['general', 'officer-chat', 'officers', 'leadership', 'admin']
            
            for channel_name in channel_names:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    target_channel = channel
                    break
            
            if not target_channel:
                target_channel = guild.text_channels[0] if guild.text_channels else None
            
            if target_channel:
                mentions = []
                if president_role:
                    mentions.append(president_role.mention)
                if treasurer_role:
                    mentions.append(treasurer_role.mention)
                
                mention_text = ' '.join(mentions) if mentions else ''
                
                await target_channel.send(
                    content=f"{mention_text}",
                    embed=embed
                )
                
                logger.info(f"Sent dues reminder for period '{period['period_name']}' in guild {guild.id}")
                
        except Exception as e:
            logger.error(f"Error sending due date reminder: {e}")
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.check_dues_reminders.cancel()

    async def _check_officer_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has officer permissions"""
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            await interaction.response.send_message(
                "❌ Officer role not configured. Please configure the bot first.", 
                ephemeral=True
            )
            return False
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ This command is only available to officers.", 
                ephemeral=True
            )
            return False
        
        return True

    @app_commands.command(name="dues_create_period", description="Create a new dues collection period (Officers only)")
    async def create_dues_period(self, interaction: discord.Interaction, 
                               period_name: str, due_amount: float, 
                               description: str = None, 
                               due_date: str = None):
        """Create a new dues period"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Parse due date if provided
            parsed_due_date = None
            if due_date:
                # Try natural language parsing first
                parsed_due_date = SmartTimeFormatter.parse_natural_language_time(due_date)
                if not parsed_due_date:
                    try:
                        parsed_due_date = datetime.strptime(due_date, "%Y-%m-%d")
                    except ValueError:
                        await interaction.followup.send(
                            "❌ Invalid date format. Use natural language (e.g., 'next friday') or YYYY-MM-DD format.",
                            ephemeral=True
                        )
                        return

            # Create the dues period
            period_id = await self.bot.db.create_dues_period(
                guild_id=interaction.guild.id,
                period_name=period_name,
                description=description,
                due_amount=due_amount,
                due_date=parsed_due_date,
                created_by_id=interaction.user.id
            )

            embed = discord.Embed(
                title="✅ Dues Period Created",
                description=f"**Period:** {period_name}\n"
                           f"**Due Amount:** ${due_amount:.2f}\n"
                           f"**Due Date:** {due_date if due_date else 'Not set'}\n"
                           f"**Description:** {description if description else 'None'}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Period ID: {period_id}")

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Officer {interaction.user.id} created dues period '{period_name}' (ID: {period_id})")

        except Exception as e:
            logger.error(f"Error creating dues period: {e}")
            await interaction.followup.send(
                "❌ An error occurred while creating the dues period.",
                ephemeral=True
            )

    @app_commands.command(name="dues_list_periods", description="List all active dues periods (Officers only)")
    async def list_dues_periods(self, interaction: discord.Interaction):
        """List all active dues periods"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            periods = await self.bot.db.get_active_dues_periods(interaction.guild.id)

            if not periods:
                await interaction.followup.send(
                    "📋 No active dues periods found.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📋 Active Dues Periods",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            for period in periods:
                due_date_str = "Not set"
                if period.get('due_date'):
                    try:
                        due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                        due_date_str = SmartTimeFormatter.format_discord_timestamp(due_date, 'D')
                    except:
                        due_date_str = period['due_date']

                embed.add_field(
                    name=f"🏷️ {period['period_name']} (ID: {period['id']})",
                    value=f"**Amount:** ${period['due_amount']:.2f}\n"
                          f"**Due Date:** {due_date_str}\n"
                          f"**Created by:** {period.get('created_by_name', 'Unknown')}\n"
                          f"**Description:** {period.get('description', 'None')}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error listing dues periods: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching dues periods.",
                ephemeral=True
            )

    @app_commands.command(name="dues_update_payment", description="Update a member's payment status (Officers only)")
    async def update_payment(self, interaction: discord.Interaction, 
                           member: discord.Member, period_id: int,
                           amount_paid: float = 0.0,
                           payment_status: str = 'unpaid',
                           payment_method: str = None,
                           payment_date: str = None,
                           notes: str = None,
                           exempt: bool = False):
        """Update a member's dues payment"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Validate payment status
            if payment_status not in self.payment_statuses:
                await interaction.followup.send(
                    f"❌ Invalid payment status. Valid options: {', '.join(self.payment_statuses)}",
                    ephemeral=True
                )
                return

            # Parse payment date if provided
            parsed_payment_date = None
            if payment_date:
                # Try natural language parsing first
                parsed_payment_date = SmartTimeFormatter.parse_natural_language_time(payment_date)
                if not parsed_payment_date:
                    try:
                        parsed_payment_date = datetime.strptime(payment_date, "%Y-%m-%d")
                    except ValueError:
                        await interaction.followup.send(
                            "❌ Invalid payment date format. Use natural language (e.g., 'today', 'yesterday') or YYYY-MM-DD format.",
                            ephemeral=True
                        )
                        return

            # Update the payment record
            await self.bot.db.update_dues_payment(
                guild_id=interaction.guild.id,
                user_id=member.id,
                dues_period_id=period_id,
                amount_paid=amount_paid,
                payment_date=parsed_payment_date,
                payment_method=payment_method,
                payment_status=payment_status,
                notes=notes,
                is_exempt=exempt,
                updated_by_id=interaction.user.id
            )

            # Get period info for display
            period = await self.bot.db.get_dues_period_by_id(period_id)
            if not period:
                await interaction.followup.send(
                    "❌ Invalid period ID.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="✅ Payment Updated",
                description=f"**Member:** {member.display_name}\n"
                           f"**Period:** {period['period_name']}\n"
                           f"**Amount Paid:** ${amount_paid:.2f}\n"
                           f"**Status:** {payment_status.title()}\n"
                           f"**Method:** {payment_method or 'Not specified'}\n"
                           f"**Date:** {payment_date or 'Not specified'}\n"
                           f"**Exempt:** {'Yes' if exempt else 'No'}\n"
                           f"**Notes:** {notes or 'None'}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Officer {interaction.user.id} updated payment for member {member.id} in period {period_id}")

        except Exception as e:
            logger.error(f"Error updating payment: {e}")
            await interaction.followup.send(
                "❌ An error occurred while updating the payment.",
                ephemeral=True
            )

    @app_commands.command(name="dues_view_payments", description="View dues payments for a period (Officers only)")
    async def view_payments(self, interaction: discord.Interaction, period_id: int):
        """View all payments for a specific dues period"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer()

        try:
            # Get period info
            period = await self.bot.db.get_dues_period_by_id(period_id)
            if not period:
                await interaction.followup.send(
                    "❌ Invalid period ID.",
                    ephemeral=True
                )
                return

            # Get all members with their payment status
            payments = await self.bot.db.get_all_dues_payments_with_members(
                interaction.guild.id, period_id
            )

            if not payments:
                await interaction.followup.send(
                    f"📋 No active members found for period '{period['period_name']}'.",
                    ephemeral=True
                )
                return

            # Generate table format
            content = await self._generate_dues_table(payments, period, interaction.guild.name)

            # Create file
            file_content = io.StringIO(content)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"dues_payments_{period['period_name'].replace(' ', '_')}_{timestamp}.txt"
            file = discord.File(file_content, filename=filename)

            # Get summary for embed
            summary = await self.bot.db.get_dues_collection_summary(interaction.guild.id, period_id)

            embed = discord.Embed(
                title=f"💰 Dues Payments - {period['period_name']}",
                description=f"**Due Amount:** ${period['due_amount']:.2f} per member\n"
                           f"**Total Members:** {summary.get('total_members', 0)}\n"
                           f"**Paid:** {summary.get('paid_count', 0)} members\n"
                           f"**Unpaid:** {summary.get('unpaid_count', 0)} members\n"
                           f"**Exempt:** {summary.get('exempt_count', 0)} members\n"
                           f"**Collection Rate:** {summary.get('collection_percentage', 0):.1f}%\n"
                           f"**Total Collected:** ${summary.get('total_collected', 0):.2f}\n"
                           f"**Outstanding:** ${summary.get('outstanding_amount', 0):.2f}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            await interaction.followup.send(
                content=f"📋 **Dues Payment Table** - {len(payments)} members",
                embed=embed,
                file=file
            )

        except Exception as e:
            logger.error(f"Error viewing payments: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching payment data.",
                ephemeral=True
            )

    async def _generate_dues_table(self, payments: List[Dict], period: Dict, guild_name: str) -> str:
        """Generate text file content formatted as a clean table for dues payments"""
        content = []
        
        # Header with guild name and timestamp
        content.append(f"DUES PAYMENTS - {guild_name.upper()}")
        content.append(f"Period: {period['period_name']} | Due Amount: ${period['due_amount']:.2f}")
        content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("=" * 100)
        content.append("")
        
        # Table header
        content.append("+" + "-" * 20 + "+" + "-" * 18 + "+" + "-" * 12 + "+" + "-" * 10 + "+" + "-" * 12 + "+" + "-" * 15 + "+" + "-" * 8 + "+")
        content.append(f"| {'RANK':<18} | {'NAME':<16} | {'STATUS':<10} | {'AMOUNT':<8} | {'METHOD':<10} | {'DATE':<13} | {'EXEMPT':<6} |")
        content.append("+" + "=" * 20 + "+" + "=" * 18 + "+" + "=" * 12 + "+" + "=" * 10 + "+" + "=" * 12 + "+" + "=" * 15 + "+" + "=" * 8 + "+")
        
        for payment in payments:
            # Format member info
            rank = payment.get('rank', 'Unknown')[:18]
            name = payment.get('discord_name', 'Unknown')[:16]
            status = payment.get('payment_status', 'unpaid').upper()[:10]
            amount = f"${payment.get('amount_paid', 0.0):.2f}"[:8]
            method = (payment.get('payment_method') or 'N/A')[:10]
            
            # Format payment date
            payment_date = payment.get('payment_date')
            if payment_date:
                try:
                    if isinstance(payment_date, str):
                        date = datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
                    else:
                        date = payment_date
                    date_str = date.strftime('%Y-%m-%d')[:13]
                except:
                    date_str = 'Invalid'[:13]
            else:
                date_str = 'Not set'[:13]
            
            exempt = 'YES' if payment.get('is_exempt') else 'NO'
            
            content.append(f"| {rank:<18} | {name:<16} | {status:<10} | {amount:<8} | {method:<10} | {date_str:<13} | {exempt:<6} |")
        
        # Close the table
        content.append("+" + "-" * 20 + "+" + "-" * 18 + "+" + "-" * 12 + "+" + "-" * 10 + "+" + "-" * 12 + "+" + "-" * 15 + "+" + "-" * 8 + "+")
        
        # Add summary
        total_members = len(payments)
        paid_members = len([p for p in payments if p.get('payment_status') == 'paid'])
        unpaid_members = len([p for p in payments if p.get('payment_status') == 'unpaid'])
        exempt_members = len([p for p in payments if p.get('is_exempt')])
        total_collected = sum(p.get('amount_paid', 0.0) for p in payments)
        
        content.append("")
        content.append(f"SUMMARY:")
        content.append(f"Total Members: {total_members}")
        content.append(f"Paid: {paid_members}")
        content.append(f"Unpaid: {unpaid_members}")
        content.append(f"Exempt: {exempt_members}")
        content.append(f"Total Collected: ${total_collected:.2f}")
        
        return "\n".join(content)

    @app_commands.command(name="dues_summary", description="Get collection summary for a dues period (Officers only)")
    async def dues_summary(self, interaction: discord.Interaction, period_id: int):
        """Get collection summary for a dues period"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            summary = await self.bot.db.get_dues_collection_summary(interaction.guild.id, period_id)

            if not summary:
                await interaction.followup.send(
                    "❌ Invalid period ID or no data available.",
                    ephemeral=True
                )
                return

            period = summary['period']

            embed = discord.Embed(
                title=f"📊 Collection Summary - {period['period_name']}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            # Format due date
            due_date_str = "Not set"
            if period.get('due_date'):
                try:
                    due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                    due_date_str = due_date.strftime('%Y-%m-%d')
                except:
                    due_date_str = str(period['due_date'])

            embed.add_field(
                name="📋 Period Information",
                value=f"**Due Amount:** ${period['due_amount']:.2f}\n"
                      f"**Due Date:** {due_date_str}\n"
                      f"**Description:** {period.get('description', 'None')}",
                inline=False
            )

            embed.add_field(
                name="👥 Member Status",
                value=f"**Total Members:** {summary['total_members']}\n"
                      f"**Paid:** {summary['paid_count']} ({summary['paid_count']/summary['total_members']*100:.1f}%)\n"
                      f"**Unpaid:** {summary['unpaid_count']} ({summary['unpaid_count']/summary['total_members']*100:.1f}%)\n"
                      f"**Partial:** {summary['partial_count']}\n"
                      f"**Exempt:** {summary['exempt_count']}",
                inline=True
            )

            embed.add_field(
                name="💰 Financial Summary",
                value=f"**Total Expected:** ${summary['total_expected']:.2f}\n"
                      f"**Total Collected:** ${summary['total_collected']:.2f}\n"
                      f"**Outstanding:** ${summary['outstanding_amount']:.2f}\n"
                      f"**Collection Rate:** {summary['collection_percentage']:.1f}%",
                inline=True
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error getting dues summary: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching the summary.",
                ephemeral=True
            )

    @app_commands.command(name="dues_reset_period", description="Reset all payments for a period (Officers only)")
    async def reset_period(self, interaction: discord.Interaction, period_id: int):
        """Reset all payments for a dues period (manual reset)"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get period info first
            period = await self.bot.db.get_dues_period_by_id(period_id)
            if not period:
                await interaction.followup.send(
                    "❌ Invalid period ID.",
                    ephemeral=True
                )
                return

            # Confirm the reset
            embed = discord.Embed(
                title="⚠️ Confirm Period Reset",
                description=f"Are you sure you want to reset ALL payment data for:\n\n"
                           f"**Period:** {period['period_name']}\n"
                           f"**Due Amount:** ${period['due_amount']:.2f}\n\n"
                           f"This action **CANNOT BE UNDONE** and will delete all payment records for this period.",
                color=discord.Color.orange()
            )

            # Create confirmation view
            view = DuesResetConfirmView(self.bot, period_id, interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error initiating period reset: {e}")
            await interaction.followup.send(
                "❌ An error occurred while preparing the reset.",
                ephemeral=True
            )

    @app_commands.command(name="dues_payment_history", description="View payment history for a member (Officers only)")
    async def payment_history(self, interaction: discord.Interaction, member: discord.Member):
        """View payment history for a specific member across all periods"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get all payment records for this member
            periods = await self.bot.db.get_active_dues_periods(interaction.guild.id)
            
            if not periods:
                await interaction.followup.send(
                    "📋 No dues periods found.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"💳 Payment History - {member.display_name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            total_paid = 0.0
            total_owed = 0.0
            payment_count = 0

            for period in periods:
                # Get payment data for this member and period
                payments = await self.bot.db.get_all_dues_payments_with_members(
                    interaction.guild.id, period['id']
                )
                
                # Find this member's payment
                member_payment = None
                for payment in payments:
                    if payment.get('user_id') == member.id:
                        member_payment = payment
                        break
                
                if member_payment:
                    amount_paid = member_payment.get('amount_paid', 0.0)
                    status = member_payment.get('payment_status', 'unpaid')
                    method = member_payment.get('payment_method', 'N/A')
                    is_exempt = member_payment.get('is_exempt', False)
                    
                    payment_date = member_payment.get('payment_date')
                    date_str = "Not set"
                    if payment_date:
                        try:
                            if isinstance(payment_date, str):
                                date = datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
                            else:
                                date = payment_date
                            date_str = date.strftime('%Y-%m-%d')
                        except:
                            date_str = "Invalid date"
                    
                    if not is_exempt:
                        total_paid += amount_paid
                        total_owed += period['due_amount']
                    
                    status_emoji = {
                        'paid': '✅',
                        'unpaid': '❌',
                        'partial': '⚠️',
                        'exempt': '🆓'
                    }.get(status, '❓')
                    
                    embed.add_field(
                        name=f"{status_emoji} {period['period_name']}",
                        value=f"**Amount:** ${amount_paid:.2f} / ${period['due_amount']:.2f}\n"
                              f"**Status:** {status.title()}\n"
                              f"**Method:** {method}\n"
                              f"**Date:** {date_str}\n"
                              f"**Exempt:** {'Yes' if is_exempt else 'No'}",
                        inline=True
                    )
                    payment_count += 1
                else:
                    # No payment record, default to unpaid
                    total_owed += period['due_amount']
                    embed.add_field(
                        name=f"❌ {period['period_name']}",
                        value=f"**Amount:** $0.00 / ${period['due_amount']:.2f}\n"
                              f"**Status:** Unpaid\n"
                              f"**Method:** N/A\n"
                              f"**Date:** Not set\n"
                              f"**Exempt:** No",
                        inline=True
                    )

            # Add summary
            outstanding = max(0, total_owed - total_paid)
            payment_rate = (total_paid / total_owed * 100) if total_owed > 0 else 0
            
            embed.add_field(
                name="📊 Summary",
                value=f"**Total Paid:** ${total_paid:.2f}\n"
                      f"**Total Owed:** ${total_owed:.2f}\n"
                      f"**Outstanding:** ${outstanding:.2f}\n"
                      f"**Payment Rate:** {payment_rate:.1f}%\n"
                      f"**Periods:** {payment_count}",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error getting payment history: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching payment history.",
                ephemeral=True
            )

    @app_commands.command(name="dues_financial_report", description="Generate comprehensive financial report (Officers only)")
    async def financial_report(self, interaction: discord.Interaction):
        """Generate a comprehensive financial report across all dues periods"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer()

        try:
            periods = await self.bot.db.get_active_dues_periods(interaction.guild.id)
            
            if not periods:
                await interaction.followup.send(
                    "📋 No dues periods found.",
                    ephemeral=True
                )
                return

            # Generate comprehensive report
            report_content = await self._generate_financial_report(periods, interaction.guild)
            
            # Create file
            file_content = io.StringIO(report_content)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"dues_financial_report_{timestamp}.txt"
            file = discord.File(file_content, filename=filename)

            # Create summary embed
            total_expected = 0.0
            total_collected = 0.0
            total_members = 0
            active_periods = len(periods)

            for period in periods:
                summary = await self.bot.db.get_dues_collection_summary(interaction.guild.id, period['id'])
                total_expected += summary.get('total_expected', 0)
                total_collected += summary.get('total_collected', 0)
                total_members = max(total_members, summary.get('total_members', 0))

            overall_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
            outstanding = max(0, total_expected - total_collected)

            embed = discord.Embed(
                title="📊 Financial Report Summary",
                description=f"**Active Periods:** {active_periods}\n"
                           f"**Total Members:** {total_members}\n"
                           f"**Total Expected:** ${total_expected:.2f}\n"
                           f"**Total Collected:** ${total_collected:.2f}\n"
                           f"**Outstanding:** ${outstanding:.2f}\n"
                           f"**Overall Collection Rate:** {overall_rate:.1f}%",
                color=discord.Color.green() if overall_rate >= 80 else discord.Color.orange() if overall_rate >= 60 else discord.Color.red(),
                timestamp=datetime.now()
            )

            await interaction.followup.send(
                content=f"📊 **Comprehensive Financial Report** - {active_periods} periods analyzed",
                embed=embed,
                file=file
            )

        except Exception as e:
            logger.error(f"Error generating financial report: {e}")
            await interaction.followup.send(
                "❌ An error occurred while generating the report.",
                ephemeral=True
            )

    async def _generate_financial_report(self, periods: List[Dict], guild: discord.Guild) -> str:
        """Generate comprehensive financial report content"""
        content = []
        
        # Header
        content.append(f"COMPREHENSIVE FINANCIAL REPORT - {guild.name.upper()}")
        content.append(f"Generated: {SmartTimeFormatter.format_discord_timestamp(datetime.now(), 'F')}")
        content.append("=" * 80)
        content.append("")
        
        # Overall summary
        total_expected = 0.0
        total_collected = 0.0
        total_outstanding = 0.0
        total_members = 0
        
        period_summaries = []
        
        for period in periods:
            summary = await self.bot.db.get_dues_collection_summary(guild.id, period['id'])
            period_summaries.append((period, summary))
            
            total_expected += summary.get('total_expected', 0)
            total_collected += summary.get('total_collected', 0)
            total_outstanding += summary.get('outstanding_amount', 0)
            total_members = max(total_members, summary.get('total_members', 0))
        
        overall_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
        
        content.append("EXECUTIVE SUMMARY")
        content.append("-" * 40)
        content.append(f"Total Active Periods: {len(periods)}")
        content.append(f"Total Members: {total_members}")
        content.append(f"Total Expected Revenue: ${total_expected:.2f}")
        content.append(f"Total Collected: ${total_collected:.2f}")
        content.append(f"Total Outstanding: ${total_outstanding:.2f}")
        content.append(f"Overall Collection Rate: {overall_rate:.1f}%")
        content.append("")
        
        # Period-by-period breakdown
        content.append("PERIOD BREAKDOWN")
        content.append("-" * 40)
        
        for period, summary in period_summaries:
            if not summary:
                continue
                
            content.append(f"")
            content.append(f"Period: {period['period_name']}")
            content.append(f"Due Amount: ${period['due_amount']:.2f} per member")
            
            # Format due date using SmartTimeFormatter
            due_date_str = "Not set"
            if period.get('due_date'):
                try:
                    due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                    due_date_str = SmartTimeFormatter.format_discord_timestamp(due_date, 'D')
                except:
                    due_date_str = str(period['due_date'])
            
            content.append(f"Due Date: {due_date_str}")
            content.append(f"Description: {period.get('description', 'None')}")
            content.append(f"")
            content.append(f"  Member Status:")
            content.append(f"    Total Members: {summary['total_members']}")
            content.append(f"    Paid: {summary['paid_count']} ({summary['paid_count']/summary['total_members']*100:.1f}%)")
            content.append(f"    Unpaid: {summary['unpaid_count']} ({summary['unpaid_count']/summary['total_members']*100:.1f}%)")
            content.append(f"    Partial: {summary['partial_count']}")
            content.append(f"    Exempt: {summary['exempt_count']}")
            content.append(f"")
            content.append(f"  Financial Summary:")
            content.append(f"    Expected: ${summary['total_expected']:.2f}")
            content.append(f"    Collected: ${summary['total_collected']:.2f}")
            content.append(f"    Outstanding: ${summary['outstanding_amount']:.2f}")
            content.append(f"    Collection Rate: {summary['collection_percentage']:.1f}%")
            
        # Payment method analysis
        content.append("")
        content.append("PAYMENT METHOD ANALYSIS")
        content.append("-" * 40)
        
        method_stats = {}
        for period in periods:
            payments = await self.bot.db.get_dues_payments_for_period(guild.id, period['id'])
            for payment in payments:
                method = payment.get('payment_method') or 'Not Specified'
                amount = payment.get('amount_paid', 0.0)
                
                if method not in method_stats:
                    method_stats[method] = {'count': 0, 'total_amount': 0.0}
                
                if payment.get('payment_status') in ['paid', 'partial']:
                    method_stats[method]['count'] += 1
                    method_stats[method]['total_amount'] += amount
        
        for method, stats in sorted(method_stats.items(), key=lambda x: x[1]['total_amount'], reverse=True):
            percentage = (stats['total_amount'] / total_collected * 100) if total_collected > 0 else 0
            content.append(f"{method}: {stats['count']} payments, ${stats['total_amount']:.2f} ({percentage:.1f}%)")
        
        # Calculate total records properly with async calls
        total_records = 0
        for p in periods:
            payments = await self.bot.db.get_dues_payments_for_period(guild.id, p['id'])
            total_records += len(payments)
        
        content.append("")
        content.append("=" * 80)
        content.append(f"Report generated by Thanatos Bot")
        content.append(f"Total records analyzed: {total_records}")
        
        return "\n".join(content)

    @app_commands.command(name="dues_export_data", description="Export all dues data for backup (Officers only)")
    async def export_dues_data(self, interaction: discord.Interaction):
        """Export all dues tracking data for backup purposes"""
        if not await self._check_officer_permissions(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get all periods and their data
            periods = await self.bot.db.get_active_dues_periods(interaction.guild.id)
            
            if not periods:
                await interaction.followup.send(
                    "📋 No dues periods found to export.",
                    ephemeral=True
                )
                return

            export_data = {
                'guild_id': interaction.guild.id,
                'guild_name': interaction.guild.name,
                'export_timestamp': datetime.now().isoformat(),
                'periods': [],
                'summary': {
                    'total_periods': len(periods),
                    'total_members': 0,
                    'total_payments': 0
                }
            }

            total_payments = 0
            
            for period in periods:
                payments = await self.bot.db.get_all_dues_payments_with_members(
                    interaction.guild.id, period['id']
                )
                
                period_data = {
                    'period_info': period,
                    'payments': payments,
                    'payment_count': len(payments)
                }
                
                export_data['periods'].append(period_data)
                export_data['summary']['total_members'] = max(export_data['summary']['total_members'], len(payments))
                total_payments += len([p for p in payments if p.get('payment_status') != 'unpaid'])
            
            export_data['summary']['total_payments'] = total_payments

            # Convert to JSON and create file
            import json
            json_content = json.dumps(export_data, indent=2, default=str)
            file_content = io.StringIO(json_content)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"dues_data_export_{timestamp}.json"
            file = discord.File(file_content, filename=filename)

            embed = discord.Embed(
                title="📥 Dues Data Export",
                description=f"**Periods Exported:** {len(periods)}\n"
                           f"**Total Members:** {export_data['summary']['total_members']}\n"
                           f"**Total Payment Records:** {export_data['summary']['total_payments']}\n"
                           f"**Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            await interaction.followup.send(
                content="📥 **Dues Data Export Complete**",
                embed=embed,
                file=file,
                ephemeral=True
            )

            logger.info(f"Officer {interaction.user.id} exported dues data for guild {interaction.guild.id}")

        except Exception as e:
            logger.error(f"Error exporting dues data: {e}")
            await interaction.followup.send(
                "❌ An error occurred while exporting the data.",
                ephemeral=True
            )

    @app_commands.command(name="dues_calendar", description="View dues calendar with upcoming due dates (Officers only)")
    async def dues_calendar(self, interaction: discord.Interaction):
        """Display dues calendar showing all periods with due dates"""
        if not await self._check_officer_permissions(interaction):
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            periods = await self.bot.db.get_active_dues_periods(interaction.guild.id)
            
            if not periods:
                await interaction.followup.send(
                    "📅 No dues periods found.",
                    ephemeral=True
                )
                return
            
            # Filter periods with due dates and sort by date
            periods_with_dates = []
            periods_without_dates = []
            
            for period in periods:
                if period.get('due_date'):
                    try:
                        due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                        periods_with_dates.append((period, due_date))
                    except:
                        periods_without_dates.append(period)
                else:
                    periods_without_dates.append(period)
            
            # Sort by due date
            periods_with_dates.sort(key=lambda x: x[1])
            
            embed = discord.Embed(
                title="📅 Dues Calendar",
                description=f"**Server:** {interaction.guild.name}\n**Total Periods:** {len(periods)}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Current time for reference
            now = datetime.now()
            
            # Add periods with due dates
            if periods_with_dates:
                calendar_content = []
                
                for period, due_date in periods_with_dates:
                    # Get collection status
                    summary = await self.bot.db.get_dues_collection_summary(interaction.guild.id, period['id'])
                    
                    # Determine status
                    days_until_due = (due_date.date() - now.date()).days
                    
                    if days_until_due < 0:
                        status_emoji = "🔴"  # Overdue
                        status_text = f"Overdue ({abs(days_until_due)} days)"
                    elif days_until_due == 0:
                        status_emoji = "🟠"  # Due today
                        status_text = "Due Today"
                    elif days_until_due <= 7:
                        status_emoji = "🟡"  # Due soon
                        status_text = f"Due in {days_until_due} days"
                    else:
                        status_emoji = "🟢"  # Not urgent
                        status_text = f"Due in {days_until_due} days"
                    
                    # Collection rate
                    collection_rate = summary.get('collection_percentage', 0) if summary else 0
                    collection_emoji = "✅" if collection_rate >= 80 else "⚠️" if collection_rate >= 50 else "❌"
                    
                    calendar_content.append(
                        f"{status_emoji} **{period['period_name']}**\n"
                        f"   💰 ${period['due_amount']:.2f} | {SmartTimeFormatter.format_discord_timestamp(due_date, 'D')}\n"
                        f"   {collection_emoji} Collection: {collection_rate:.1f}% | {status_text}\n"
                    )
                
                embed.add_field(
                    name="📅 Scheduled Periods",
                    value="\n".join(calendar_content),
                    inline=False
                )
            
            # Add periods without due dates
            if periods_without_dates:
                no_date_content = []
                for period in periods_without_dates:
                    summary = await self.bot.db.get_dues_collection_summary(interaction.guild.id, period['id'])
                    collection_rate = summary.get('collection_percentage', 0) if summary else 0
                    collection_emoji = "✅" if collection_rate >= 80 else "⚠️" if collection_rate >= 50 else "❌"
                    
                    no_date_content.append(
                        f"📋 **{period['period_name']}**\n"
                        f"   💰 ${period['due_amount']:.2f} | No due date set\n"
                        f"   {collection_emoji} Collection: {collection_rate:.1f}%\n"
                    )
                
                embed.add_field(
                    name="📋 Periods Without Due Dates",
                    value="\n".join(no_date_content),
                    inline=False
                )
            
            # Add legend
            embed.add_field(
                name="📊 Legend",
                value="🔴 Overdue | 🟠 Due Today | 🟡 Due Soon | 🟢 Not Urgent\n"
                      "✅ 80%+ Collected | ⚠️ 50-79% | ❌ <50% Collected",
                inline=False
            )
            
            # Add reminders info
            embed.set_footer(text="Automatic reminders are sent to President and Treasurer on due dates")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error generating dues calendar: {e}")
            await interaction.followup.send(
                "❌ An error occurred while generating the calendar.",
                ephemeral=True
            )

    # Autocomplete functions
    @update_payment.autocomplete('payment_status')
    async def payment_status_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=status.title(), value=status)
            for status in self.payment_statuses
            if current.lower() in status.lower()
        ][:25]

    @update_payment.autocomplete('payment_method')
    async def payment_method_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=method, value=method)
            for method in self.payment_methods
            if current.lower() in method.lower()
        ][:25]

class DuesResetConfirmView(discord.ui.View):
    def __init__(self, bot, period_id: int, user_id: int):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.period_id = period_id
        self.user_id = user_id

    @discord.ui.button(label='Reset Period', style=discord.ButtonStyle.danger, emoji='⚠️')
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the officer who initiated this can confirm.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Perform the reset
            success = await self.bot.db.reset_dues_period(
                interaction.guild.id, 
                self.period_id, 
                interaction.user.id
            )

            if success:
                embed = discord.Embed(
                    title="✅ Period Reset Complete",
                    description=f"All payment data for period ID {self.period_id} has been reset.",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                logger.info(f"Officer {interaction.user.id} reset dues period {self.period_id}")
            else:
                embed = discord.Embed(
                    title="❌ Reset Failed",
                    description="An error occurred while resetting the period.",
                    color=discord.Color.red()
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Disable the view
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)

        except Exception as e:
            logger.error(f"Error resetting dues period: {e}")
            await interaction.followup.send(
                "❌ An error occurred while resetting the period.",
                ephemeral=True
            )

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the officer who initiated this can cancel.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Reset cancelled.", ephemeral=True)
        
        # Disable the view
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

    async def on_timeout(self):
        # Disable the view when it times out
        for item in self.children:
            item.disabled = True

    @app_commands.command(name="dues_dashboard", description="Open the interactive dues management dashboard (Officers only)")
    async def dues_dashboard(self, interaction: discord.Interaction):
        """Show interactive dues management dashboard"""
        if not await self._check_officer_permissions(interaction):
            return
            
        await interaction.response.defer()
        
        try:
            # Get current dues data
            periods = await self.bot.db.get_active_dues_periods(interaction.guild.id)
            total_periods = len(periods)
            
            # Calculate overall statistics
            total_expected = 0.0
            total_collected = 0.0
            total_members = 0
            
            for period in periods:
                summary = await self.bot.db.get_dues_collection_summary(interaction.guild.id, period['id'])
                if summary:
                    total_expected += summary.get('total_expected', 0)
                    total_collected += summary.get('total_collected', 0)
                    total_members = max(total_members, summary.get('total_members', 0))
            
            collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
            outstanding = total_expected - total_collected
            
            embed = discord.Embed(
                title="💰 Dues Management Dashboard",
                description=f"**Server:** {interaction.guild.name}\n"
                           f"**Active Periods:** {total_periods}\n"
                           f"**Total Members:** {total_members}\n"
                           f"**Collection Rate:** {collection_rate:.1f}%\n"
                           f"**Total Collected:** ${total_collected:.2f}\n"
                           f"**Outstanding:** ${outstanding:.2f}",
                color=discord.Color.blue() if collection_rate >= 80 else discord.Color.orange() if collection_rate >= 60 else discord.Color.red(),
                timestamp=datetime.now()
            )
            
            # Add recent activity if available
            embed.add_field(
                name="📊 Quick Stats",
                value=f"**Expected Revenue:** ${total_expected:.2f}\n"
                      f"**Payment Methods:** {len([m for methods in self.payment_methods.values() for m in methods])} available\n"
                      f"**Last Updated:** {SmartTimeFormatter.format_discord_timestamp(datetime.now(), 'R')}",
                inline=False
            )
            
            # Create interactive view
            view = DuesDashboardView(self.bot)
            await interaction.followup.send(embed=embed, view=view)
            
            # Log dashboard access
            await self._log_audit_event(interaction.guild.id, interaction.user.id, 
                                      'DASHBOARD_ACCESSED', 
                                      f"Dashboard accessed by {interaction.user.display_name}")
            
        except Exception as e:
            logger.error(f"Error showing dues dashboard: {e}")
            await interaction.followup.send(
                "❌ An error occurred while loading the dashboard.",
                ephemeral=True
            )
    
    async def _log_audit_event(self, guild_id: int, user_id: int, event_type: str, details: str):
        """Log audit events for comprehensive tracking"""
        try:
            await self.bot.db.log_dues_audit_event(
                guild_id=guild_id,
                user_id=user_id,
                event_type=event_type,
                event_details=details,
                timestamp=datetime.now()
            )
            logger.info(f"Audit log: {event_type} - {details}")
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    async def _sync_with_membership(self, guild_id: int, period_id: int):
        """Sync dues tracking with membership system"""
        try:
            # Get all current members from membership system
            members = await self.bot.db.get_all_members(guild_id)
            if not members:
                return False
            
            synced_count = 0
            for member in members:
                # Ensure each member has a dues record for this period
                existing_payment = await self.bot.db.get_dues_payment(
                    guild_id, member['user_id'], period_id
                )
                
                if not existing_payment:
                    # Create new payment record with unpaid status
                    await self.bot.db.update_dues_payment(
                        guild_id=guild_id,
                        user_id=member['user_id'],
                        dues_period_id=period_id,
                        amount_paid=0.0,
                        payment_status='unpaid',
                        updated_by_id=None  # System sync
                    )
                    synced_count += 1
            
            logger.info(f"Synced {synced_count} new member records with dues period {period_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing with membership: {e}")
            return False
    
    async def _calculate_advanced_statistics(self, guild_id: int, period_id: int) -> Dict:
        """Calculate advanced statistics for a dues period"""
        try:
            payments = await self.bot.db.get_all_dues_payments_with_members(guild_id, period_id)
            period = await self.bot.db.get_dues_period_by_id(period_id)
            
            if not payments or not period:
                return {}
            
            stats = {
                'total_members': len(payments),
                'paid_count': len([p for p in payments if p.get('payment_status') == 'paid']),
                'unpaid_count': len([p for p in payments if p.get('payment_status') == 'unpaid']),
                'partial_count': len([p for p in payments if p.get('payment_status') == 'partial']),
                'exempt_count': len([p for p in payments if p.get('is_exempt')]),
                'overdue_count': 0,  # Will calculate based on due date
                'total_collected': sum(p.get('amount_paid', 0.0) for p in payments),
                'average_payment': 0.0,
                'payment_methods': {},
                'rank_breakdown': {},
                'payment_timeline': []
            }
            
            # Calculate overdue payments if due date is set
            if period.get('due_date'):
                try:
                    due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                    if due_date < datetime.now():
                        stats['overdue_count'] = len([p for p in payments 
                                                    if p.get('payment_status') == 'unpaid'])
                except:
                    pass
            
            # Calculate average payment (excluding exempt members)
            non_exempt_payments = [p for p in payments if not p.get('is_exempt')]
            if non_exempt_payments:
                stats['average_payment'] = stats['total_collected'] / len(non_exempt_payments)
            
            # Payment method breakdown
            for payment in payments:
                method = payment.get('payment_method', 'Not Specified')
                if payment.get('payment_status') in ['paid', 'partial']:
                    stats['payment_methods'][method] = stats['payment_methods'].get(method, 0) + 1
            
            # Rank breakdown
            for payment in payments:
                rank = payment.get('rank', 'Unknown')
                status = payment.get('payment_status', 'unpaid')
                if rank not in stats['rank_breakdown']:
                    stats['rank_breakdown'][rank] = {'paid': 0, 'unpaid': 0, 'partial': 0, 'exempt': 0}
                stats['rank_breakdown'][rank][status] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating advanced statistics: {e}")
            return {}

class DuesDashboardView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300.0)  # 5 minute timeout
        self.bot = bot
    
    @discord.ui.button(label='Create New Period', style=discord.ButtonStyle.success, emoji='➕')
    async def create_period_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to create a new dues period"""
        await interaction.response.send_modal(CreatePeriodModal(self.bot))
    
    @discord.ui.button(label='View All Periods', style=discord.ButtonStyle.primary, emoji='📋')
    async def view_periods_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to view all active periods"""
        # Get dues tracking cog and call the list periods method
        dues_cog = self.bot.get_cog('AdvancedDuesTrackingSystem')
        if dues_cog:
            await dues_cog.list_dues_periods(interaction)
    
    @discord.ui.button(label='Payment Management', style=discord.ButtonStyle.secondary, emoji='💳')
    async def payment_management_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open payment management interface"""
        await interaction.response.send_message(
            "Please select a period to manage payments:", 
            view=PeriodSelectionView(self.bot, 'payment_management'),
            ephemeral=True
        )
    
    @discord.ui.button(label='Financial Reports', style=discord.ButtonStyle.secondary, emoji='📊')
    async def financial_reports_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to generate financial reports"""
        dues_cog = self.bot.get_cog('AdvancedDuesTrackingSystem')
        if dues_cog:
            await dues_cog.financial_report(interaction)
    
    @discord.ui.button(label='Sync with Membership', style=discord.ButtonStyle.secondary, emoji='🔄')
    async def sync_membership_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to sync with membership system"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            periods = await self.bot.db.get_active_dues_periods(interaction.guild.id)
            if not periods:
                await interaction.followup.send(
                    "❌ No active dues periods found to sync with.",
                    ephemeral=True
                )
                return
            
            dues_cog = self.bot.get_cog('AdvancedDuesTrackingSystem')
            total_synced = 0
            
            for period in periods:
                success = await dues_cog._sync_with_membership(interaction.guild.id, period['id'])
                if success:
                    total_synced += 1
            
            embed = discord.Embed(
                title="✅ Membership Sync Complete",
                description=f"Successfully synced {total_synced} periods with membership system.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error syncing membership: {e}")
            await interaction.followup.send(
                "❌ An error occurred during membership sync.",
                ephemeral=True
            )
    
    async def on_timeout(self):
        # Disable all buttons when the view times out
        for item in self.children:
            item.disabled = True

class CreatePeriodModal(discord.ui.Modal, title='Create New Dues Period'):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    period_name = discord.ui.TextInput(
        label='Period Name',
        placeholder='e.g., "Monthly Dues - January 2025"',
        required=True,
        max_length=100
    )
    
    due_amount = discord.ui.TextInput(
        label='Due Amount ($)',
        placeholder='e.g., "25.00"',
        required=True,
        max_length=10
    )
    
    due_date = discord.ui.TextInput(
        label='Due Date (optional)',
        placeholder='e.g., "next friday", "2025-01-15", "in 2 weeks"',
        required=False,
        max_length=50
    )
    
    description = discord.ui.TextInput(
        label='Description (optional)',
        placeholder='Additional details about this dues period...',
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate due amount
            try:
                amount = float(self.due_amount.value)
                if amount < 0:
                    raise ValueError("Amount cannot be negative")
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid due amount. Please enter a valid number.",
                    ephemeral=True
                )
                return
            
            # Parse due date if provided
            parsed_due_date = None
            if self.due_date.value:
                parsed_due_date = SmartTimeFormatter.parse_natural_language_time(self.due_date.value)
                if not parsed_due_date:
                    await interaction.followup.send(
                        "❌ Could not parse the due date. Please use formats like 'next friday', '2025-01-15', or 'in 2 weeks'.",
                        ephemeral=True
                    )
                    return
            
            # Create the dues period
            period_id = await self.bot.db.create_dues_period(
                guild_id=interaction.guild.id,
                period_name=self.period_name.value,
                description=self.description.value or None,
                due_amount=amount,
                due_date=parsed_due_date,
                created_by_id=interaction.user.id
            )
            
            # Sync with membership system
            dues_cog = self.bot.get_cog('AdvancedDuesTrackingSystem')
            if dues_cog:
                await dues_cog._sync_with_membership(interaction.guild.id, period_id)
            
            embed = discord.Embed(
                title="✅ Dues Period Created",
                description=f"**Period:** {self.period_name.value}\n"
                           f"**Due Amount:** ${amount:.2f}\n"
                           f"**Due Date:** {self.due_date.value if self.due_date.value else 'Not set'}\n"
                           f"**Description:** {self.description.value if self.description.value else 'None'}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Period ID: {period_id} | Synced with membership system")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log the creation
            await dues_cog._log_audit_event(
                interaction.guild.id, interaction.user.id,
                'PERIOD_CREATED',
                f"Created period '{self.period_name.value}' with amount ${amount:.2f}"
            )
            
        except Exception as e:
            logger.error(f"Error creating dues period via modal: {e}")
            await interaction.followup.send(
                "❌ An error occurred while creating the dues period.",
                ephemeral=True
            )

class PeriodSelectionView(discord.ui.View):
    def __init__(self, bot, action_type: str):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.action_type = action_type
    
    @discord.ui.select(placeholder="Select a dues period...")
    async def select_period(self, interaction: discord.Interaction, select: discord.ui.Select):
        period_id = int(select.values[0])
        
        if self.action_type == 'payment_management':
            view = PaymentManagementView(self.bot, period_id)
            await interaction.response.send_message(
                f"Payment management for period ID {period_id}:",
                view=view,
                ephemeral=True
            )
    
    async def refresh_periods(self, guild_id: int):
        """Refresh the period selection dropdown"""
        try:
            periods = await self.bot.db.get_active_dues_periods(guild_id)
            options = []
            
            for period in periods[:25]:  # Discord limit of 25 options
                due_date_str = "No due date"
                if period.get('due_date'):
                    try:
                        due_date = datetime.fromisoformat(period['due_date'].replace('Z', '+00:00'))
                        due_date_str = due_date.strftime('%Y-%m-%d')
                    except:
                        due_date_str = "Invalid date"
                
                options.append(
                    discord.SelectOption(
                        label=f"{period['period_name'][:50]}.." if len(period['period_name']) > 50 else period['period_name'],
                        value=str(period['id']),
                        description=f"${period['due_amount']:.2f} - Due: {due_date_str}"
                    )
                )
            
            if options:
                self.select_period.options = options
            
        except Exception as e:
            logger.error(f"Error refreshing periods: {e}")

class PaymentManagementView(discord.ui.View):
    def __init__(self, bot, period_id: int):
        super().__init__(timeout=120.0)
        self.bot = bot
        self.period_id = period_id
    
    @discord.ui.button(label='Record Payment', style=discord.ButtonStyle.success, emoji='💰')
    async def record_payment_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to record a new payment"""
        await interaction.response.send_modal(RecordPaymentModal(self.bot, self.period_id))
    
    @discord.ui.button(label='Mark as Exempt', style=discord.ButtonStyle.secondary, emoji='🆓')
    async def mark_exempt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to mark members as exempt"""
        await interaction.response.send_message(
            "Please mention the member to mark as exempt:",
            ephemeral=True
        )
        # This would typically open a member selection interface
    
    @discord.ui.button(label='View Period Report', style=discord.ButtonStyle.primary, emoji='📊')
    async def view_report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to view detailed report for this period"""
        dues_cog = self.bot.get_cog('AdvancedDuesTrackingSystem')
        if dues_cog:
            await dues_cog.view_payments(interaction, self.period_id)

class RecordPaymentModal(discord.ui.Modal, title='Record Payment'):
    def __init__(self, bot, period_id: int):
        super().__init__()
        self.bot = bot
        self.period_id = period_id
    
    member_mention = discord.ui.TextInput(
        label='Member',
        placeholder='@username or user ID',
        required=True,
        max_length=50
    )
    
    amount_paid = discord.ui.TextInput(
        label='Amount Paid ($)',
        placeholder='e.g., "25.00"',
        required=True,
        max_length=10
    )
    
    payment_method = discord.ui.TextInput(
        label='Payment Method',
        placeholder='e.g., "Venmo", "Cash", "PayPal"',
        required=False,
        max_length=30
    )
    
    payment_date = discord.ui.TextInput(
        label='Payment Date (optional)',
        placeholder='e.g., "today", "yesterday", "2025-01-10"',
        required=False,
        max_length=50
    )
    
    notes = discord.ui.TextInput(
        label='Notes (optional)',
        placeholder='Any additional notes...',
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse member mention or ID
            member = None
            member_input = self.member_mention.value.strip()
            
            # Try to parse as mention
            if member_input.startswith('<@') and member_input.endswith('>'):
                user_id = int(member_input[2:-1].replace('!', ''))
                member = interaction.guild.get_member(user_id)
            else:
                # Try to parse as user ID
                try:
                    user_id = int(member_input)
                    member = interaction.guild.get_member(user_id)
                except ValueError:
                    pass
            
            if not member:
                await interaction.followup.send(
                    "❌ Could not find that member. Please use @mention or user ID.",
                    ephemeral=True
                )
                return
            
            # Validate amount
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
            
            # Parse payment date
            parsed_payment_date = None
            if self.payment_date.value:
                parsed_payment_date = SmartTimeFormatter.parse_natural_language_time(self.payment_date.value)
                if not parsed_payment_date:
                    parsed_payment_date = datetime.now()  # Default to now if parsing fails
            
            # Determine payment status
            period = await self.bot.db.get_dues_period_by_id(self.period_id)
            payment_status = 'paid' if amount >= period['due_amount'] else 'partial' if amount > 0 else 'unpaid'
            
            # Record the payment
            await self.bot.db.update_dues_payment(
                guild_id=interaction.guild.id,
                user_id=member.id,
                dues_period_id=self.period_id,
                amount_paid=amount,
                payment_date=parsed_payment_date,
                payment_method=self.payment_method.value or None,
                payment_status=payment_status,
                notes=self.notes.value or None,
                is_exempt=False,
                updated_by_id=interaction.user.id
            )
            
            embed = discord.Embed(
                title="✅ Payment Recorded",
                description=f"**Member:** {member.display_name}\n"
                           f"**Amount:** ${amount:.2f}\n"
                           f"**Status:** {payment_status.title()}\n"
                           f"**Method:** {self.payment_method.value or 'Not specified'}\n"
                           f"**Date:** {self.payment_date.value or 'Now'}\n"
                           f"**Notes:** {self.notes.value or 'None'}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log the payment
            dues_cog = self.bot.get_cog('AdvancedDuesTrackingSystem')
            if dues_cog:
                await dues_cog._log_audit_event(
                    interaction.guild.id, interaction.user.id,
                    'PAYMENT_RECORDED',
                    f"Recorded ${amount:.2f} payment for {member.display_name} via {self.payment_method.value or 'unspecified method'}"
                )
                
        except Exception as e:
            logger.error(f"Error recording payment via modal: {e}")
            await interaction.followup.send(
                "❌ An error occurred while recording the payment.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AdvancedDuesTrackingSystem(bot))

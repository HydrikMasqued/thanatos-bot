import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import io
import logging
from typing import List, Dict, Optional
from utils.smart_time_formatter import SmartTimeFormatter

# Set up logger for this module
logger = logging.getLogger(__name__)

class DuesTrackingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Payment status options
        self.payment_statuses = ['paid', 'unpaid', 'partial', 'exempt']
        
        # Common payment methods
        self.payment_methods = [
            'Cash', 'Venmo', 'PayPal', 'Zelle', 'CashApp', 'Bank Transfer', 'Check', 'Other'
        ]

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

async def setup(bot):
    await bot.add_cog(DuesTrackingSystem(bot))

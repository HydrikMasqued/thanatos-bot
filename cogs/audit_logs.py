import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import List, Optional, Dict, Literal
import io
import csv
import json
from utils.contribution_audit_helpers import ContributionAuditHelpers
from utils.smart_time_formatter import SmartTimeFormatter

class AuditLogsPaginator(discord.ui.View):
    def __init__(self, bot, guild_id: int, events: List[dict], per_page: int = 10):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.events = events
        self.per_page = per_page
        self.current_page = 0
        self.max_page = max(0, (len(events) - 1) // per_page)
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        self.first_page.disabled = (self.current_page == 0)
        self.prev_page.disabled = (self.current_page == 0)
        self.next_page.disabled = (self.current_page == self.max_page)
        self.last_page.disabled = (self.current_page == self.max_page)
    
    def get_page_events(self) -> List[dict]:
        """Get events for current page"""
        start = self.current_page * self.per_page
        end = start + self.per_page
        return self.events[start:end]
    
    async def create_embed(self) -> discord.Embed:
        """Create embed for current page"""
        page_events = self.get_page_events()
        
        embed = discord.Embed(
            title="📋 Audit Logs",
            description=f"Complete record of all item movements and changes\n"
                       f"**Total Events:** {len(self.events)} | **Page:** {self.current_page + 1}/{self.max_page + 1}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not page_events:
            embed.add_field(
                name="No Events",
                value="No audit events found for the specified criteria.",
                inline=False
            )
            return embed
        
        # Add events to embed
        for i, event in enumerate(page_events, 1):
            event_num = (self.current_page * self.per_page) + i
            
            # Format the event based on type
            if event['event_type'] == 'contribution':
                event_title = f"#{event_num} 📦 Contribution"
                event_desc = f"**Item:** {event['item_name']}\n"
                event_desc += f"**Category:** {event['category']}\n"
                event_desc += f"**Quantity:** +{event['quantity_delta']}\n"
            else:  # quantity_change
                event_title = f"#{event_num} ⚖️ Quantity Change"
                event_desc = f"**Item:** {event['item_name']}\n"
                event_desc += f"**Category:** {event['category']}\n"
                event_desc += f"**Change:** {event['old_quantity']} → {event['new_quantity']} "
                delta = event['quantity_delta']
                if delta > 0:
                    event_desc += f"(+{delta})"
                else:
                    event_desc += f"({delta})"
                
                if event['reason']:
                    event_desc += f"\n**Reason:** {event['reason']}"
                if event['notes']:
                    event_desc += f"\n**Notes:** {event['notes'][:100]}{'...' if len(event['notes']) > 100 else ''}"
            
            # Add timestamp and actor
            try:
                occurred_at = datetime.fromisoformat(event['occurred_at'].replace('T', ' ').replace('Z', ''))
                event_desc += f"\n**When:** {SmartTimeFormatter.format_discord_timestamp(occurred_at, 'f')}"
            except:
                event_desc += f"\n**When:** {event['occurred_at']}"
            event_desc += f"\n**Actor ID:** {event['actor_id']}"
            
            embed.add_field(
                name=event_title,
                value=event_desc,
                inline=True
            )
        
        return embed
    
    @discord.ui.button(label='⏪', style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='◀️', style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='▶️', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='⏩', style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.max_page
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='📁 Export CSV', style=discord.ButtonStyle.success)
    async def export_csv(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Generate CSV content
            csv_content = await self._generate_csv()
            
            # Create file
            file = discord.File(
                io.StringIO(csv_content),
                filename=f"audit_logs_{self.guild_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
            embed = discord.Embed(
                title="📁 Audit Logs Export",
                description=f"Complete audit trail exported to CSV file.\n"
                           f"**Total Records:** {len(self.events)}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Export Failed",
                description=f"Failed to export audit logs: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    async def _generate_csv(self) -> str:
        """Generate comprehensive detailed table content from events"""
        output = io.StringIO()
        
        # Write comprehensive table header
        output.write("=" * 150 + "\n")
        output.write("COMPREHENSIVE AUDIT LOG - DETAILED TRANSACTION RECORD\n")
        output.write("=" * 150 + "\n\n")
        
        # Write table headers with proper spacing
        header_format = "{:<8} {:<12} {:<15} {:<10} {:<12} {:<20} {:<15} {:<8} {:<15} {:<30} {:<50}\n"
        output.write(header_format.format(
            "REC#", "EVENT_TYPE", "USER", "DATE", "TIME", "ITEM_NAME", "CATEGORY", "OLD_QTY", "NEW_QTY", "CHANGE_DESC", "NOTES/REASON"
        ))
        output.write("-" * 150 + "\n")
        
        # Write table data for each event
        for i, event in enumerate(self.events, 1):
            # Get user information
            user_display_name = "Unknown"
            
            if event.get('actor_id'):
                try:
                    user_obj = self.bot.get_user(event['actor_id'])
                    if user_obj:
                        user_display_name = user_obj.display_name[:14]  # Truncate for table
                    else:
                        user_display_name = f"User_{str(event['actor_id'])[-6:]}"
                except:
                    user_display_name = f"User_{str(event['actor_id'])[-6:]}"
            
            # Parse timestamp details
            try:
                dt = datetime.fromisoformat(event['occurred_at'].replace('T', ' ').replace('Z', ''))
                date_str = SmartTimeFormatter.format_discord_timestamp(dt, 'd')
                time_str = SmartTimeFormatter.format_discord_timestamp(dt, 't')
            except:
                date_str = "Unknown"
                time_str = "Unknown"
            
            # Format event data
            event_type = event.get('event_type', 'unknown')[:11]  # Truncate for table
            item_name = event.get('item_name', 'Unknown')[:19]  # Truncate for table
            category = event.get('category', 'Unknown')[:14]  # Truncate for table
            old_qty = str(event.get('old_quantity', ''))
            new_qty = str(event.get('new_quantity', ''))
            
            # Create change description
            change_desc = ""
            if event.get('quantity_delta') is not None:
                delta = event['quantity_delta']
                if delta > 0:
                    change_desc = f"+{delta} Added"
                elif delta < 0:
                    change_desc = f"{delta} Removed"
                else:
                    change_desc = "No Change"
            else:
                change_desc = "N/A"
            
            # Format notes/reason
            notes_reason = ""
            if event.get('reason'):
                notes_reason = f"R: {event['reason'][:45]}"
            elif event.get('notes'):
                notes_reason = f"N: {event['notes'][:45]}"
            else:
                notes_reason = "None"
            
            # Write formatted row
            row_format = "{:<8} {:<12} {:<15} {:<10} {:<12} {:<20} {:<15} {:<8} {:<15} {:<30} {:<50}\n"
            output.write(row_format.format(
                f"{i:04d}",
                event_type,
                user_display_name,
                date_str,
                time_str,
                item_name,
                category,
                old_qty if old_qty else "-",
                new_qty if new_qty else "-",
                change_desc[:29],
                notes_reason[:49]
            ))
        
        # Write footer
        output.write("-" * 150 + "\n")
        output.write(f"Total Events: {len(self.events)}\n")
        output.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        output.write("=" * 150 + "\n")
        
        return output.getvalue()


class AuditLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def _has_officer_permissions(self, member: discord.Member) -> bool:
        """Check if member has officer permissions"""
        return member.guild_permissions.administrator
    
    @app_commands.command(name="audit_logs", description="View complete audit trail of all item movements and changes")
    @app_commands.describe(
        item_name="Filter by specific item name",
        category="Filter by specific category",
        limit="Maximum number of events to show (default: 100)"
    )
    async def audit_logs(
        self, 
        interaction: discord.Interaction, 
        item_name: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = 100
    ):
        """View comprehensive audit logs with all item movements and changes"""
        
        # Check permissions using shared utility
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            return await ContributionAuditHelpers.send_permission_error(interaction)
        
        await interaction.response.defer()
        
        try:
            # Fetch audit events
            events = await self.bot.db.get_all_audit_events(
                interaction.guild.id,
                item_name=item_name,
                category=category,
                limit=limit
            )
            
            if not events:
                embed = discord.Embed(
                    title="📋 Audit Logs",
                    description="No audit events found for the specified criteria.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                return await interaction.followup.send(embed=embed)
            
            # If there are many events, auto-export to file
            if len(events) > 50:
                # Show summary and provide file
                await self._send_audit_file(interaction, events, item_name, category)
            else:
                # Show paginated view
                view = AuditLogsPaginator(self.bot, interaction.guild.id, events)
                embed = await view.create_embed()
                await interaction.followup.send(embed=embed, view=view)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Retrieving Audit Logs",
                description=f"Failed to retrieve audit logs: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _send_audit_file(self, interaction: discord.Interaction, events: List[dict], 
                              item_name: Optional[str], category: Optional[str]):
        """Send audit logs as a file when there are many events"""
        try:
            # Generate readable table format
            output = io.StringIO()
            
            # Write table header
            output.write("=" * 180 + "\n")
            output.write(f"COMPREHENSIVE AUDIT LOG WITH TOTAL AMOUNTS - {interaction.guild.name.upper()}\n")
            output.write(f"GENERATED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            output.write("=" * 180 + "\n\n")
            
            # Add filter information if any
            if item_name or category:
                output.write("FILTERS APPLIED:\n")
                if item_name:
                    output.write(f"  - Item Name: {item_name}\n")
                if category:
                    output.write(f"  - Category: {category}\n")
                output.write("\n")
            
            # Write statistics summary
            contrib_count = sum(1 for e in events if e['event_type'] == 'contribution')
            change_count = sum(1 for e in events if e['event_type'] == 'quantity_change')
            
            output.write("SUMMARY STATISTICS:\n")
            output.write(f"  - Total Events: {len(events)}\n")
            output.write(f"  - Contributions: {contrib_count}\n")
            output.write(f"  - Quantity Changes: {change_count}\n")
            output.write("\n")
            
            # Calculate total amounts for all items
            total_amounts = self._calculate_total_amounts(events)
            
            # Group events by category
            categories = {}
            for event in events:
                cat = event.get('category', 'Misc Locker')
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(event)
            
            # Process each category separately
            category_order = ['Weapons Locker', 'Drug Locker', 'Misc Locker']
            processed_categories = set()
            
            # Process known categories in order
            for cat_name in category_order:
                if cat_name in categories:
                    self._write_category_section(output, cat_name, categories[cat_name], total_amounts)
                    processed_categories.add(cat_name)
            
            # Process any remaining categories
            for cat_name, cat_events in categories.items():
                if cat_name not in processed_categories:
                    self._write_category_section(output, cat_name, cat_events, total_amounts)
            
            # Write final report footer
            output.write("\n" + "=" * 180 + "\n")
            output.write("COMPREHENSIVE AUDIT REPORT SUMMARY\n")
            output.write("=" * 180 + "\n")
            output.write(f"TOTAL EVENTS PROCESSED: {len(events)}\n")
            output.write(f"CATEGORIES PROCESSED: {len(categories)}\n")
            output.write(f"REPORT COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            output.write(f"GUILD: {interaction.guild.name} (ID: {interaction.guild.id})\n")
            output.write("\nThis is an official audit trail record with total amounts generated by Thanatos Bot.\n")
            output.write("All timestamps are in UTC. Total amounts reflect cumulative transaction totals.\n")
            output.write("For questions, contact your guild administrators.\n")
            output.write("=" * 180 + "\n")
            
            # Create comprehensive export file
            table_content = output.getvalue()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            guild_name_safe = "".join(c for c in interaction.guild.name if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"COMPREHENSIVE_AUDIT_TABLE_{guild_name_safe}_{timestamp}.txt"
            
            file = discord.File(
                io.StringIO(table_content),
                filename=filename
            )
            
            # Create summary embed
            embed = discord.Embed(
                title="📋 Complete Audit Logs",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Add summary statistics
            contrib_count = sum(1 for e in events if e['event_type'] == 'contribution')
            change_count = sum(1 for e in events if e['event_type'] == 'quantity_change')
            
            embed.add_field(
                name="📊 Summary",
                value=f"**Total Events:** {len(events)}\n"
                     f"**Contributions:** {contrib_count}\n"
                     f"**Quantity Changes:** {change_count}",
                inline=True
            )
            
            # Add filter info if any
            filter_info = []
            if item_name:
                filter_info.append(f"Item: {item_name}")
            if category:
                filter_info.append(f"Category: {category}")
            
            if filter_info:
                embed.add_field(
                    name="🔍 Filters Applied",
                    value="\n".join(filter_info),
                    inline=True
                )
            
            # Add recent events preview
            if events:
                recent_events = []
                for event in events[:5]:  # Show first 5 events
                    occurred_at = datetime.fromisoformat(event['occurred_at'].replace('T', ' ').replace('Z', ''))
                    if event['event_type'] == 'contribution':
                        recent_events.append(f"📦 {event['item_name']} (+{event['quantity_delta']}) - {occurred_at.strftime('%m/%d %H:%M')}")
                    else:
                        delta = event['quantity_delta']
                        sign = '+' if delta >= 0 else ''
                        recent_events.append(f"⚖️ {event['item_name']} ({sign}{delta}) - {occurred_at.strftime('%m/%d %H:%M')}")
                
                embed.add_field(
                    name="🕐 Recent Events (Latest First)",
                    value="\n".join(recent_events),
                    inline=False
                )
            
            embed.set_footer(text="Complete audit trail exported to CSV file for detailed analysis")
            
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Export Failed",
                description=f"Failed to generate audit logs file: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="audit_export", description="Export complete audit trail as CSV file")
    @app_commands.describe(
        item_name="Filter by specific item name",
        category="Filter by specific category"
    )
    async def audit_export(
        self,
        interaction: discord.Interaction,
        item_name: Optional[str] = None,
        category: Optional[str] = None
    ):
        """Export complete audit trail as CSV file for external analysis"""
        
        # Check permissions using shared utility
        if not await ContributionAuditHelpers.check_officer_permissions(interaction, self.bot):
            return await ContributionAuditHelpers.send_permission_error(
                interaction, 
                "❌ You need administrator or officer permissions to export audit logs."
            )
        
        await interaction.response.defer()
        
        try:
            # Fetch ALL audit events (no limit)
            events = await self.bot.db.get_all_audit_events(
                interaction.guild.id,
                item_name=item_name,
                category=category,
                limit=None
            )
            
            if not events:
                embed = discord.Embed(
                    title="📋 Audit Export",
                    description="No audit events found for the specified criteria.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Always send as file for exports
            await self._send_audit_file(interaction, events, item_name, category)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Export Failed",
                description=f"Failed to export audit logs: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="audit_summary", description="Get summary statistics of all audit events")
    async def audit_summary(self, interaction: discord.Interaction):
        """Get high-level summary of audit trail statistics"""
        
        # Check permissions (officers and admins only)
        if not self._has_officer_permissions(interaction.user):
            config = await self.bot.db.get_server_config(interaction.guild.id)
            if not config or not config.get('officer_role_id'):
                return await interaction.response.send_message(
                    "❌ You need administrator or officer permissions to view audit summary.", 
                    ephemeral=True
                )
            
            officer_role = interaction.guild.get_role(config['officer_role_id'])
            if not officer_role or officer_role not in interaction.user.roles:
                return await interaction.response.send_message(
                    "❌ You need administrator or officer permissions to view audit summary.", 
                    ephemeral=True
                )
        
        await interaction.response.defer()
        
        try:
            # Get all events for analysis
            events = await self.bot.db.get_all_audit_events(interaction.guild.id, limit=None)
            
            if not events:
                embed = discord.Embed(
                    title="📊 Audit Summary",
                    description="No audit events found in the database.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                return await interaction.followup.send(embed=embed)
            
            # Analyze data
            contrib_events = [e for e in events if e['event_type'] == 'contribution']
            change_events = [e for e in events if e['event_type'] == 'quantity_change']
            
            # Calculate statistics - contributions and inventory are now completely separate systems
            total_contributions = sum(e['quantity_delta'] for e in contrib_events)
            
            # All quantity changes are now admin/system adjustments (no auto-contribution changes)
            total_admin_changes = sum(abs(e['quantity_delta']) for e in change_events)
            
            # Get unique items and categories
            unique_items = set(e['item_name'] for e in events)
            unique_categories = set(e['category'] for e in events)
            
            # Get unique actors
            unique_actors = set(e['actor_id'] for e in events)
            
            # Get date range
            if events:
                oldest = min(datetime.fromisoformat(e['occurred_at'].replace('T', ' ').replace('Z', '')) for e in events)
                newest = max(datetime.fromisoformat(e['occurred_at'].replace('T', ' ').replace('Z', '')) for e in events)
            
            # Create summary embed
            embed = discord.Embed(
                title="📊 Audit Trail Summary",
                description=f"Complete overview of all tracked item movements and changes",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Overall statistics
            embed.add_field(
                name="📈 Overall Statistics",
                value=f"**Total Events:** {len(events)}\n"
                     f"**Contributions:** {len(contrib_events)}\n"
                     f"**Quantity Changes:** {len(change_events)}\n"
                     f"**Unique Items:** {len(unique_items)}\n"
                     f"**Unique Categories:** {len(unique_categories)}\n"
                     f"**Unique Actors:** {len(unique_actors)}",
                inline=True
            )
            
            # Volume statistics - separated to avoid double-counting
            embed.add_field(
                name="📦 Volume Statistics",
                value=f"**Total Items Added (Contributions):** {total_contributions}\n"
                     f"**Total Admin Adjustments:** {total_admin_changes}\n"
                     f"**Inventory Changes:** {len(change_events)}",
                inline=True
            )
            
            # Time range
            if events:
                embed.add_field(
                    name="⏰ Time Range",
                    value=f"**Oldest Record:** {oldest.strftime('%Y-%m-%d')}\n"
                         f"**Newest Record:** {newest.strftime('%Y-%m-%d')}\n"
                         f"**Days Tracked:** {(newest - oldest).days + 1}",
                    inline=True
                )
            
            # Top categories by activity
            category_counts = {}
            for event in events:
                category_counts[event['category']] = category_counts.get(event['category'], 0) + 1
            
            top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            if top_categories:
                category_text = "\n".join([f"**{cat}:** {count} events" for cat, count in top_categories])
                embed.add_field(
                    name="🎯 Most Active Categories",
                    value=category_text,
                    inline=False
                )
            
            embed.set_footer(text="Use /audit_logs or /audit_export for detailed records")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Generating Summary",
                description=f"Failed to generate audit summary: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    def _calculate_total_amounts(self, events: List[dict]) -> dict:
        """Calculate current inventory levels by tracking all contributions and quantity changes"""
        amounts = {}
        
        # Process events chronologically to get accurate running totals
        sorted_events = sorted(events, key=lambda x: x.get('occurred_at', ''))
        
        for event in sorted_events:
            item_name = event.get('item_name', 'Unknown')
            category = event.get('category', 'Misc Locker')
            item_key = f"{category}::{item_name}"
            
            # Initialize item if not seen before
            if item_key not in amounts:
                amounts[item_key] = 0
            
            if event.get('event_type') == 'quantity_change':
                # For quantity changes, use the new_quantity directly as the current level
                # This represents an administrative override of the inventory level
                if event.get('new_quantity') is not None:
                    amounts[item_key] = event['new_quantity']
            elif event.get('event_type') == 'contribution':
                # For contributions, add the contribution amount to the current level
                contribution_amount = event.get('quantity_delta', 0)
                amounts[item_key] += contribution_amount
        
        return amounts
    
    def _write_category_section(self, output: io.StringIO, category_name: str, 
                               category_events: List[dict], total_amounts: dict):
        """Write a section for a specific category with total amounts"""
        # Category header
        output.write(f"\n{'=' * 180}\n")
        output.write(f"CATEGORY: {category_name.upper()}\n")
        output.write(f"{'=' * 180}\n")
        
        # Get unique items in this category and their total amounts
        category_items = {}
        for event in category_events:
            item_name = event.get('item_name', 'Unknown')
            item_key = f"{category_name}::{item_name}"
            if item_key not in category_items:
                total_amount = total_amounts.get(item_key, 0)
                category_items[item_name] = total_amount
        
        # Write current totals summary for this category
        output.write(f"\nCURRENT TOTALS SUMMARY - {category_name}:\n")
        output.write("-" * 80 + "\n")
        output.write(f"{'ITEM NAME':<40} {'TOTAL AMOUNT':<20} {'STATUS':<15}\n")
        output.write("-" * 80 + "\n")
        
        total_items = 0
        for item_name, qty in sorted(category_items.items()):
            status = "IN STOCK" if qty > 0 else "OUT OF STOCK" if qty == 0 else "NEGATIVE"
            output.write(f"{item_name[:39]:<40} {str(qty):<20} {status:<15}\n")
            total_items += qty
        
        output.write("-" * 80 + "\n")
        output.write(f"{'CATEGORY TOTAL:':<40} {str(total_items):<20} {'ITEMS':<15}\n")
        output.write("-" * 80 + "\n\n")
        
        # Write detailed transaction history for this category
        output.write(f"DETAILED TRANSACTION HISTORY - {category_name}:\n")
        output.write("-" * 180 + "\n")
        
        # Enhanced table headers with total amount column
        header_format = "{:<6} {:<12} {:<16} {:<12} {:<10} {:<25} {:<8} {:<8} {:<8} {:<20} {:<50}\n"
        output.write(header_format.format(
            "REC#", "EVENT_TYPE", "USER", "DATE", "TIME", "ITEM_NAME", "OLD_QTY", "NEW_QTY", "TOTAL", "CHANGE_DESC", "NOTES/REASON"
        ))
        output.write("-" * 180 + "\n")
        
        # Sort events chronologically for proper running balance calculation
        sorted_category_events = sorted(category_events, key=lambda x: x.get('occurred_at', ''))
        
        # Track running balances for each item in this category
        running_balances = {}
        
        # Write events for this category
        for i, event in enumerate(sorted_category_events, 1):
            # Get user information
            user_display_name = "Unknown"
            
            if event.get('actor_id'):
                try:
                    user_obj = self.bot.get_user(event['actor_id'])
                    if user_obj:
                        user_display_name = user_obj.display_name[:15]
                    else:
                        user_display_name = f"User_{str(event['actor_id'])[-6:]}"
                except:
                    user_display_name = f"User_{str(event['actor_id'])[-6:]}"
            
            # Parse timestamp details
            try:
                dt = datetime.fromisoformat(event['occurred_at'].replace('T', ' ').replace('Z', ''))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except:
                date_str = "Unknown"
                time_str = "Unknown"
            
            # Format event data
            event_type = event.get('event_type', 'unknown')[:11]
            item_name = event.get('item_name', 'Unknown')[:24]
            old_qty = str(event.get('old_quantity', ''))
            new_qty = str(event.get('new_quantity', ''))
            
            # Calculate current inventory level for the TOTAL column
            # The TOTAL column should show the running inventory balance after this transaction
            item_name_key = event.get('item_name', 'Unknown')
            
            # Initialize running balance for this item if not seen before
            if item_name_key not in running_balances:
                running_balances[item_name_key] = 0
            
            if event.get('event_type') == 'quantity_change':
                # For quantity changes, set the inventory level to new_quantity (admin override)
                if event.get('new_quantity') is not None:
                    running_balances[item_name_key] = event['new_quantity']
            elif event.get('event_type') == 'contribution':
                # For contributions, add the contribution amount to the current balance
                contribution_amount = event.get('quantity_delta', 0)
                running_balances[item_name_key] += contribution_amount
            
            total_amount_after_transaction = running_balances[item_name_key]
            
            # Create change description
            change_desc = ""
            if event.get('quantity_delta') is not None:
                delta = event['quantity_delta']
                if delta > 0:
                    change_desc = f"+{delta} Added"
                elif delta < 0:
                    change_desc = f"{delta} Removed"
                else:
                    change_desc = "No Change"
            else:
                change_desc = "N/A"
            
            # Format notes/reason
            notes_reason = ""
            if event.get('reason'):
                notes_reason = f"REASON: {event['reason'][:40]}"
            elif event.get('notes'):
                notes_reason = f"NOTES: {event['notes'][:40]}"
            else:
                notes_reason = "No additional details"
            
            # Write formatted row
            output.write(header_format.format(
                f"{i:04d}",
                event_type,
                user_display_name,
                date_str,
                time_str,
                item_name,
                old_qty[:7] if old_qty else "-",
                new_qty[:7] if new_qty else "-",
                str(total_amount_after_transaction)[:7],
                change_desc[:19],
                notes_reason[:49]
            ))
        
        output.write("-" * 180 + "\n")
        output.write(f"End of {category_name} - {len(category_events)} transactions processed\n")
        output.write("=" * 180 + "\n\n")


    @app_commands.command(name="audit_remove", description="Remove specific audit log entries (Admins only)")
    @app_commands.describe(
        entry_type="Type of entry to remove",
        entry_id="ID of the entry to remove"
    )
    async def audit_remove(
        self,
        interaction: discord.Interaction,
        entry_type: Literal["contribution", "quantity_change"],
        entry_id: int
    ):
        """Remove a specific audit log entry (Admin only)"""
        
        # Check permissions - only admins can remove audit entries
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Only administrators can remove audit log entries.",
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get entry details first for confirmation
            entry_details = await self.bot.db.get_audit_entry_details(
                interaction.guild.id, entry_type, entry_id
            )
            
            if not entry_details:
                return await interaction.followup.send(
                    f"❌ {entry_type.replace('_', ' ').title()} entry with ID {entry_id} not found.",
                    ephemeral=True
                )
            
            # Create confirmation view
            view = AuditRemovalConfirmView(
                entry_type, entry_id, entry_details, interaction.user
            )
            
            # Create confirmation embed
            embed = discord.Embed(
                title="⚠️ Confirm Audit Entry Removal",
                description=f"Are you sure you want to permanently remove this {entry_type.replace('_', ' ')} entry?",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            # Add entry details
            if entry_type == "contribution":
                embed.add_field(
                    name="📦 Contribution Details",
                    value=f"**Item:** {entry_details.get('item_name', 'Unknown')}\n"
                          f"**Category:** {entry_details.get('category', 'Unknown')}\n"
                          f"**Quantity:** {entry_details.get('quantity', 'Unknown')}\n"
                          f"**Contributor:** {entry_details.get('contributor_name', 'Unknown')}\n"
                          f"**Date:** <t:{int(datetime.fromisoformat(entry_details.get('created_at', '2000-01-01')).timestamp())}:F>",
                    inline=False
                )
            elif entry_type == "quantity_change":
                embed.add_field(
                    name="⚖️ Quantity Change Details",
                    value=f"**Item:** {entry_details.get('item_name', 'Unknown')}\n"
                          f"**Category:** {entry_details.get('category', 'Unknown')}\n"
                          f"**Change:** {entry_details.get('old_quantity', '?')} → {entry_details.get('new_quantity', '?')}\n"
                          f"**Reason:** {entry_details.get('reason', 'No reason')}\n"
                          f"**Changed By:** {entry_details.get('changed_by_name', 'Unknown')}\n"
                          f"**Date:** <t:{int(datetime.fromisoformat(entry_details.get('changed_at', '2000-01-01')).timestamp())}:F>",
                    inline=False
                )
            
            embed.add_field(
                name="⚠️ Warning",
                value="This action cannot be undone. The entry will be permanently deleted from the audit trail.",
                inline=False
            )
            
            embed.set_footer(text=f"Entry ID: {entry_id} | Requested by: {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to retrieve audit entry details: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="audit_manage", description="Interactive audit log management dashboard (Admins only)")
    async def audit_manage(self, interaction: discord.Interaction):
        """Interactive audit log management interface for admins"""
        
        # Check permissions - only admins can manage audit entries
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Only administrators can manage audit log entries.",
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get recent audit events for management
            events = await self.bot.db.get_all_audit_events(
                interaction.guild.id,
                limit=50  # Show last 50 events for management
            )
            
            if not events:
                embed = discord.Embed(
                    title="📋 Audit Management Dashboard",
                    description="No audit events found to manage.",
                    color=discord.Color.blue()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Create management view
            view = AuditManagementView(events, interaction.guild)
            embed = await view.create_dashboard_embed()
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to load audit management dashboard: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class AuditRemovalConfirmView(discord.ui.View):
    def __init__(self, entry_type: str, entry_id: int, entry_details: Dict, requesting_user: discord.Member):
        super().__init__(timeout=120)
        self.entry_type = entry_type
        self.entry_id = entry_id
        self.entry_details = entry_details
        self.requesting_user = requesting_user
    
    @discord.ui.button(label="✅ Confirm Removal", style=discord.ButtonStyle.danger)
    async def confirm_removal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requesting_user.id:
            return await interaction.response.send_message(
                "❌ Only the requesting admin can confirm this action.", ephemeral=True
            )
        
        try:
            success = await interaction.client.db.remove_audit_entry(
                interaction.guild.id, self.entry_type, self.entry_id, interaction.user.id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Audit Entry Removed",
                    description=f"Successfully removed {self.entry_type.replace('_', ' ')} entry (ID: {self.entry_id}).",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="Removed Entry",
                    value=f"**Item:** {self.entry_details.get('item_name', 'Unknown')}\n"
                          f"**Category:** {self.entry_details.get('category', 'Unknown')}\n"
                          f"**Action:** Permanently deleted from audit trail",
                    inline=False
                )
                embed.set_footer(text=f"Removed by: {interaction.user.display_name}")
            else:
                embed = discord.Embed(
                    title="❌ Removal Failed",
                    description=f"Failed to remove {self.entry_type.replace('_', ' ')} entry (ID: {self.entry_id}). Entry may have already been removed.",
                    color=discord.Color.red()
                )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while removing the audit entry: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_removal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requesting_user.id:
            return await interaction.response.send_message(
                "❌ Only the requesting admin can cancel this action.", ephemeral=True
            )
        
        embed = discord.Embed(
            title="❌ Removal Cancelled",
            description="Audit entry removal has been cancelled.",
            color=discord.Color.greyple()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class AuditManagementView(discord.ui.View):
    def __init__(self, events: List[Dict], guild: discord.Guild):
        super().__init__(timeout=300)
        self.events = events
        self.guild = guild
        self.current_page = 0
        self.items_per_page = 10
        
        # Add audit entry dropdown
        self.add_audit_dropdown()
        
        # Add navigation if needed
        total_pages = (len(events) - 1) // self.items_per_page + 1
        if total_pages > 1:
            self.add_navigation_buttons()
    
    def add_audit_dropdown(self):
        """Add dropdown for selecting audit entries to manage"""
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.events))
        
        options = []
        for i in range(start_idx, end_idx):
            event = self.events[i]
            
            # Format display
            event_type_display = "📦" if event['event_type'] == 'contribution' else "⚖️"
            item_name = event.get('item_name', 'Unknown')[:30]
            category = event.get('category', 'Unknown')[:15]
            
            try:
                occurred_at = datetime.fromisoformat(event['occurred_at'].replace('T', ' ').replace('Z', ''))
                date_str = occurred_at.strftime('%m/%d %H:%M')
            except:
                date_str = "Unknown"
            
            options.append(
                discord.SelectOption(
                    label=f"{event_type_display} {item_name} - {category}",
                    description=f"{date_str} | Click to remove this entry",
                    value=f"{event['event_type']}:{event.get('id', 0)}"
                )
            )
        
        if hasattr(self, 'audit_select'):
            self.remove_item(self.audit_select)
        
        self.audit_select = discord.ui.Select(
            placeholder="Select an audit entry to remove...",
            options=options
        )
        self.audit_select.callback = self.audit_selected
        self.add_item(self.audit_select)
    
    def add_navigation_buttons(self):
        """Add page navigation buttons"""
        total_pages = (len(self.events) - 1) // self.items_per_page + 1
        
        if self.current_page > 0:
            prev_btn = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary)
            prev_btn.callback = self.previous_page
            self.add_item(prev_btn)
        
        page_btn = discord.ui.Button(
            label=f"Page {self.current_page + 1}/{total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True
        )
        self.add_item(page_btn)
        
        if self.current_page < total_pages - 1:
            next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
            next_btn.callback = self.next_page
            self.add_item(next_btn)
    
    async def previous_page(self, interaction: discord.Interaction):
        self.current_page -= 1
        await self.update_view(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        self.current_page += 1
        await self.update_view(interaction)
    
    async def update_view(self, interaction: discord.Interaction):
        self.clear_items()
        self.add_audit_dropdown()
        
        total_pages = (len(self.events) - 1) // self.items_per_page + 1
        if total_pages > 1:
            self.add_navigation_buttons()
        
        embed = await self.create_dashboard_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def audit_selected(self, interaction: discord.Interaction):
        """Handle audit entry selection for removal"""
        selection = self.audit_select.values[0]
        event_type, entry_id_str = selection.split(':', 1)
        entry_id = int(entry_id_str)
        
        # Find the selected event
        selected_event = None
        for event in self.events:
            if event['event_type'] == event_type and event.get('id') == entry_id:
                selected_event = event
                break
        
        if not selected_event:
            await interaction.response.send_message(
                "❌ Selected audit entry not found.", ephemeral=True
            )
            return
        
        # Get detailed entry information
        try:
            entry_details = await interaction.client.db.get_audit_entry_details(
                interaction.guild.id, event_type, entry_id
            )
            
            if not entry_details:
                return await interaction.response.send_message(
                    "❌ Could not retrieve entry details.", ephemeral=True
                )
            
            # Create removal confirmation view
            confirm_view = AuditRemovalConfirmView(
                event_type, entry_id, entry_details, interaction.user
            )
            
            # Create confirmation embed
            embed = discord.Embed(
                title="⚠️ Confirm Audit Entry Removal",
                description=f"Are you sure you want to permanently remove this {event_type.replace('_', ' ')} entry?",
                color=discord.Color.orange()
            )
            
            # Add details based on event type
            if event_type == "contribution":
                embed.add_field(
                    name="📦 Contribution Details",
                    value=f"**Item:** {entry_details.get('item_name', 'Unknown')}\n"
                          f"**Category:** {entry_details.get('category', 'Unknown')}\n"
                          f"**Quantity:** {entry_details.get('quantity', 'Unknown')}\n"
                          f"**Contributor:** {entry_details.get('contributor_name', 'Unknown')}",
                    inline=False
                )
            elif event_type == "quantity_change":
                embed.add_field(
                    name="⚖️ Quantity Change Details",
                    value=f"**Item:** {entry_details.get('item_name', 'Unknown')}\n"
                          f"**Category:** {entry_details.get('category', 'Unknown')}\n"
                          f"**Change:** {entry_details.get('old_quantity', '?')} → {entry_details.get('new_quantity', '?')}\n"
                          f"**Reason:** {entry_details.get('reason', 'No reason')}\n"
                          f"**Changed By:** {entry_details.get('changed_by_name', 'Unknown')}",
                    inline=False
                )
            
            embed.add_field(
                name="⚠️ Warning",
                value="This action cannot be undone. The entry will be permanently deleted.",
                inline=False
            )
            
            await interaction.response.send_message(
                embed=embed, view=confirm_view, ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error retrieving entry details: {str(e)}", ephemeral=True
            )
    
    async def create_dashboard_embed(self) -> discord.Embed:
        """Create the audit management dashboard embed"""
        embed = discord.Embed(
            title="🛡️ Audit Log Management Dashboard",
            description=f"**Total Audit Entries:** {len(self.events)}\n\n"
                       f"Select entries from the dropdown below to remove them from the audit trail.\n"
                       f"⚠️ **Warning:** Removed entries cannot be recovered!",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        # Show current page entries
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.events))
        
        entries_text = ""
        for i in range(start_idx, end_idx):
            event = self.events[i]
            
            event_icon = "📦" if event['event_type'] == 'contribution' else "⚖️"
            item_name = event.get('item_name', 'Unknown')[:20]
            category = event.get('category', 'Unknown')[:15]
            
            try:
                occurred_at = datetime.fromisoformat(event['occurred_at'].replace('T', ' ').replace('Z', ''))
                date_str = occurred_at.strftime('%m/%d %H:%M')
            except:
                date_str = "Unknown"
            
            if event['event_type'] == 'contribution':
                detail = f"Qty: +{event.get('quantity_delta', 0)}"
            else:
                delta = event.get('quantity_delta', 0)
                detail = f"Change: {'+' if delta >= 0 else ''}{delta}"
            
            entries_text += f"• {event_icon} **{item_name}** ({category}) - {detail} - {date_str}\n"
        
        if entries_text:
            embed.add_field(
                name="📋 Recent Audit Entries",
                value=entries_text[:1024],
                inline=False
            )
        
        # Page info
        total_pages = (len(self.events) - 1) // self.items_per_page + 1
        if total_pages > 1:
            embed.set_footer(text=f"Page {self.current_page + 1} of {total_pages} | Admin Management Interface")
        else:
            embed.set_footer(text="Admin Management Interface - Select entries to remove")
        
        return embed


async def setup(bot):
    await bot.add_cog(AuditLogs(bot))

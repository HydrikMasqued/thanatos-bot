import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import aiosqlite
import json
import os
import logging
import io
import asyncio

class DatabaseArchiveModal(discord.ui.Modal):
    def __init__(self, current_summary: str):
        super().__init__(title="Create Database Archive")
        self.current_summary = current_summary
        
        # Archive name input
        self.archive_name = discord.ui.TextInput(
            label="Archive Name",
            placeholder=f"Archive_{datetime.now().strftime('%Y%m%d_%H%M')}",
            max_length=100,
            required=True,
            default=f"Archive_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )
        self.add_item(self.archive_name)
        
        # Description input
        self.description = discord.ui.TextInput(
            label="Archive Description",
            placeholder="Describe this archive (e.g., 'Pre-heist inventory', 'Monthly summary')",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True
        )
        self.add_item(self.description)
        
        # Notes input
        self.notes = discord.ui.TextInput(
            label="Additional Notes (Optional)",
            placeholder="Any additional context or notes about this archive...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the bot instance
            bot = interaction.client
            
            # Create archive
            archive_id = await bot.db.create_database_archive(
                interaction.guild.id,
                self.archive_name.value,
                self.description.value,
                self.notes.value,
                interaction.user.id
            )
            
            # Clear forum threads after successful archive creation
            db_cog = bot.get_cog('DatabaseManagement')
            if db_cog:
                cleared_threads = await db_cog._clear_forum_threads(bot, interaction.guild.id)
                if cleared_threads:
                    thread_names = [t['name'] for t in cleared_threads]
                    logging.getLogger(__name__).info(f"Archive creation: Cleared {len(cleared_threads)} threads: {', '.join(thread_names)}")
            
            embed = discord.Embed(
                title="✅ Database Archive Created",
                description=f"**Archive Name:** {self.archive_name.value}\n\n"
                           f"**Description:** {self.description.value}\n\n"
                           f"**Archive ID:** {archive_id}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            if self.notes.value:
                embed.add_field(
                    name="Notes",
                    value=self.notes.value,
                    inline=False
                )
            
            embed.add_field(
                name="Next Steps",
                value="• Current contributions have been archived\n"
                      "• Audit logs have been archived and cleared\n"
                      "• New contributions and audit tracking will start fresh\n"
                      "• Use `/view_archives` to see all archives\n"
                      "• Use `/restore_archive` to restore if needed",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Creating Archive",
                description=f"An error occurred while creating the archive: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    

class ArchiveSelectionView(discord.ui.View):
    """View for selecting archives from a dropdown menu"""
    
    def __init__(self, archives: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.archives = archives
        
        # Create dropdown options (limit to 25 due to Discord limit)
        options = []
        for archive in archives[-25:]:  # Show most recent 25
            created_date = datetime.fromisoformat(archive['created_at']).strftime('%Y-%m-%d %H:%M')
            archive_data = json.loads(archive['archived_data'])
            
            description = f"{created_date} • {archive_data.get('total_contributions', 0)} contributions"
            options.append(
                discord.SelectOption(
                    label=archive['archive_name'][:100],  # Discord limit
                    description=description[:100],  # Discord limit
                    value=str(archive['id'])
                )
            )
        
        # Reverse to show newest first
        options.reverse()
        
        self.archive_select = discord.ui.Select(
            placeholder="Select an archive to view...",
            options=options
        )
        self.archive_select.callback = self.archive_selected
        self.add_item(self.archive_select)
        
        if len(archives) > 25:
            # Add note about limitation
            note_button = discord.ui.Button(
                label=f"Showing newest 25 of {len(archives)} archives",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )
            self.add_item(note_button)
    
    async def archive_selected(self, interaction: discord.Interaction):
        """Handle archive selection from dropdown"""
        archive_id = int(self.archive_select.values[0])
        
        # Get the selected archive details
        bot = interaction.client
        archive = await bot.db.get_archive_by_id(archive_id)
        
        if not archive:
            await interaction.response.send_message("❌ Archive not found.", ephemeral=True)
            return
        
        # Create detailed archive view
        view = ArchiveDetailView(archive)
        embed = await view.create_archive_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

class ArchiveDetailView(discord.ui.View):
    """View for displaying detailed archive information"""
    
    def __init__(self, archive: Dict[str, Any]):
        super().__init__(timeout=300)
        self.archive = archive
        self.archived_data = archive['archived_data']  # Already parsed JSON
    
    async def create_archive_embed(self) -> discord.Embed:
        """Create detailed embed for archive contents"""
        created_date = datetime.fromisoformat(self.archive['created_at'])
        
        embed = discord.Embed(
            title=f"📦 Archive: {self.archive['archive_name']}",
            description=f"**{self.archive['description']}**\n\n"
                       f"📅 Created: {created_date.strftime('%Y-%m-%d %H:%M UTC')}\n"
                       f"👤 Created by: <@{self.archive['created_by_id']}>\n\n",
            color=discord.Color.blue(),
            timestamp=created_date
        )
        
        # Archive statistics
        total_contributions = self.archived_data.get('total_contributions', 0)
        total_audit_events = self.archived_data.get('total_audit_events', 0)
        
        embed.add_field(
            name="📊 Archive Statistics",
            value=f"📦 **{total_contributions:,}** Contributions\n"
                  f"📋 **{total_audit_events:,}** Audit Events\n"
                  f"📚 **Archive ID:** {self.archive['id']}",
            inline=True
        )
        
        # Top categories from archived data
        contributions = self.archived_data.get('contributions', [])
        if contributions:
            categories = {}
            for contrib in contributions:
                category = contrib.get('category', 'Unknown')
                categories[category] = categories.get(category, 0) + contrib.get('quantity', 1)
            
            top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
            cat_text = "\n".join([f"• **{cat}**: {qty:,}" for cat, qty in top_categories])
            
            embed.add_field(
                name="🏆 Top Categories",
                value=cat_text[:1024] if cat_text else "No categories",
                inline=True
            )
        
        # Top contributors from archived data
        if contributions:
            contributors = {}
            for contrib in contributions:
                name = contrib.get('discord_name', 'Unknown')
                contributors[name] = contributors.get(name, 0) + contrib.get('quantity', 1)
            
            top_contributors = sorted(contributors.items(), key=lambda x: x[1], reverse=True)[:5]
            contrib_text = "\n".join([f"• **{name}**: {qty:,}" for name, qty in top_contributors])
            
            embed.add_field(
                name="👥 Top Contributors",
                value=contrib_text[:1024] if contrib_text else "No contributors",
                inline=True
            )
        
        # Notes if available
        if self.archive.get('notes'):
            embed.add_field(
                name="📝 Notes",
                value=self.archive['notes'][:1024],
                inline=False
            )
        
        embed.set_footer(
            text=f"Archive #{self.archive['id']} • {total_contributions + total_audit_events:,} total records"
        )
        
        return embed
    
    @discord.ui.button(label="📊 Export Archive Data", style=discord.ButtonStyle.primary, emoji="📊")
    async def export_archive(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Export archive data in comprehensive audit format"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Generate comprehensive audit-style export
            output = io.StringIO()
            
            # Write comprehensive header
            output.write("=" * 180 + "\n")
            output.write(f"COMPREHENSIVE ARCHIVE EXPORT - {self.archive['archive_name'].upper()}\n")
            output.write(f"GENERATED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            output.write("=" * 180 + "\n\n")
            
            # Write archive metadata
            created_date = datetime.fromisoformat(self.archive['created_at'])
            output.write("ARCHIVE INFORMATION:\n")
            output.write(f"  - Archive Name: {self.archive['archive_name']}\n")
            output.write(f"  - Description: {self.archive['description']}\n")
            output.write(f"  - Created: {created_date.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            output.write(f"  - Created by ID: {self.archive['created_by_id']}\n")
            output.write(f"  - Archive ID: {self.archive['id']}\n")
            if self.archive.get('notes'):
                output.write(f"  - Notes: {self.archive['notes']}\n")
            output.write("\n")
            
            # Get archived contributions and audit events
            contributions = self.archived_data.get('contributions', [])
            audit_events = self.archived_data.get('audit_events', [])
            
            # Write statistics summary
            output.write("ARCHIVE STATISTICS:\n")
            output.write(f"  - Total Contributions: {len(contributions)}\n")
            output.write(f"  - Total Audit Events: {len(audit_events)}\n")
            output.write(f"  - Total Records: {len(contributions) + len(audit_events)}\n")
            output.write("\n")
            
            # Calculate final quantities from contributions
            final_quantities = self._calculate_final_quantities(contributions)
            
            # Group contributions by category
            categories = {}
            for contrib in contributions:
                cat = contrib.get('category', 'Misc Locker')
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(contrib)
            
            # Process each category
            category_order = ['Weapons Locker', 'Drug Locker', 'Misc Locker']
            processed_categories = set()
            
            # Process known categories in order
            for cat_name in category_order:
                if cat_name in categories:
                    self._write_archive_category_section(output, cat_name, categories[cat_name], final_quantities)
                    processed_categories.add(cat_name)
            
            # Process any remaining categories
            for cat_name, cat_contributions in categories.items():
                if cat_name not in processed_categories:
                    self._write_archive_category_section(output, cat_name, cat_contributions, final_quantities)
            
            # Write audit events section if any
            if audit_events:
                output.write("\n" + "=" * 180 + "\n")
                output.write("ARCHIVED AUDIT EVENTS\n")
                output.write("=" * 180 + "\n")
                output.write(f"Total Audit Events: {len(audit_events)}\n\n")
                
                # Write audit events table
                header_format = "{:<6} {:<12} {:<16} {:<12} {:<10} {:<25} {:<8} {:<8} {:<20} {:<50}\n"
                output.write(header_format.format(
                    "REC#", "EVENT_TYPE", "USER", "DATE", "TIME", "ITEM_NAME", "OLD_QTY", "NEW_QTY", "CHANGE_DESC", "NOTES/REASON"
                ))
                output.write("-" * 180 + "\n")
                
                for i, event in enumerate(audit_events, 1):
                    # Format timestamp
                    try:
                        dt = datetime.fromisoformat(event['occurred_at'].replace('T', ' ').replace('Z', ''))
                        date_str = dt.strftime("%Y-%m-%d")
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        date_str = "Unknown"
                        time_str = "Unknown"
                    
                    # Format event data
                    event_type = event.get('event_type', 'unknown')[:11]
                    user_name = event.get('actor_name', 'Unknown')[:15]
                    item_name = event.get('item_name', 'Unknown')[:24]
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
                        notes_reason = f"REASON: {event['reason'][:40]}"
                    elif event.get('notes'):
                        notes_reason = f"NOTES: {event['notes'][:40]}"
                    else:
                        notes_reason = "No additional details"
                    
                    # Write formatted row
                    output.write(header_format.format(
                        f"{i:04d}",
                        event_type,
                        user_name,
                        date_str,
                        time_str,
                        item_name,
                        old_qty[:7] if old_qty else "-",
                        new_qty[:7] if new_qty else "-",
                        change_desc[:19],
                        notes_reason[:49]
                    ))
                
                output.write("-" * 180 + "\n")
                output.write(f"End of Audit Events - {len(audit_events)} events processed\n")
            
            # Write final report footer
            output.write("\n" + "=" * 180 + "\n")
            output.write("COMPREHENSIVE ARCHIVE EXPORT SUMMARY\n")
            output.write("=" * 180 + "\n")
            output.write(f"TOTAL CONTRIBUTIONS PROCESSED: {len(contributions)}\n")
            output.write(f"TOTAL AUDIT EVENTS PROCESSED: {len(audit_events)}\n")
            output.write(f"CATEGORIES PROCESSED: {len(categories)}\n")
            output.write(f"EXPORT COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            output.write(f"ARCHIVE: {self.archive['archive_name']} (ID: {self.archive['id']})\n")
            output.write("\nThis is an official archive export generated by Thanatos Bot.\n")
            output.write("All timestamps are in UTC. Quantities reflect archived inventory levels.\n")
            output.write("=" * 180 + "\n")
            
            # Create file
            table_content = output.getvalue()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name_safe = "".join(c for c in self.archive['archive_name'] if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"ARCHIVE_EXPORT_{archive_name_safe}_{timestamp}.txt"
            
            file = discord.File(
                io.StringIO(table_content),
                filename=filename
            )
            
            # Create summary embed
            embed = discord.Embed(
                title="📊 Archive Export Complete",
                description=f"**Archive:** {self.archive['archive_name']}\n"
                           f"*Complete archive data in comprehensive audit format.*",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📋 Export Summary",
                value=f"**Contributions:** {len(contributions)}\n"
                     f"**Audit Events:** {len(audit_events)}\n"
                     f"**Categories:** {len(categories)}\n"
                     f"**Total Records:** {len(contributions) + len(audit_events)}",
                inline=True
            )
            
            embed.add_field(
                name="📅 Archive Details",
                value=f"**Created:** {created_date.strftime('%Y-%m-%d')}\n"
                     f"**Archive ID:** {self.archive['id']}\n"
                     f"**Format:** Comprehensive Audit Table",
                inline=True
            )
            
            embed.set_footer(text="Export format matches audit trail structure for consistency")
            
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Export Error",
                description=f"Failed to export archive data: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔙 Back to Archives", style=discord.ButtonStyle.secondary)
    async def back_to_archives(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go back to archive list"""
        # Get all archives again
        archives = await interaction.client.db.get_database_archives(interaction.guild.id)
        view = ArchiveSelectionView(archives)
        
        embed = discord.Embed(
            title="📚 Database Archives",
            description=f"**Found {len(archives)} archive(s)**\n\n"
                       f"Select an archive from the dropdown below to view its detailed contents.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Show overview of recent archives
        recent_archives = archives[-5:] if len(archives) > 5 else archives
        archive_list = []
        for archive in recent_archives:
            created_date = datetime.fromisoformat(archive['created_at']).strftime('%Y-%m-%d %H:%M')
            archive_data = json.loads(archive['archived_data'])
            archive_list.append(
                f"• **{archive['archive_name']}** ({created_date})\n"
                f"  └ {archive_data.get('total_contributions', 0)} contributions"
            )
        
        embed.add_field(
            name="🔍 Recent Archives",
            value="\n".join(archive_list) if archive_list else "No recent archives",
            inline=False
        )
        
        if len(archives) > 5:
            embed.set_footer(text=f"Showing 5 most recent • Use dropdown to view all {len(archives)} archives")
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    def _calculate_final_quantities(self, contributions: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate final quantities for all items from contributions"""
        quantities = {}
        
        for contrib in contributions:
            item_name = contrib.get('item_name', 'Unknown')
            category = contrib.get('category', 'Misc Locker')
            quantity = contrib.get('quantity', 0)
            
            item_key = f"{category}::{item_name}"
            if item_key not in quantities:
                quantities[item_key] = 0
            quantities[item_key] += quantity
        
        return quantities
    
    def _write_archive_category_section(self, output: io.StringIO, category_name: str, 
                                       contributions: List[Dict[str, Any]], final_quantities: Dict[str, int]):
        """Write a section for a specific category with contributions and final quantities"""
        # Category header
        output.write(f"\n{'=' * 180}\n")
        output.write(f"CATEGORY: {category_name.upper()}\n")
        output.write(f"{'=' * 180}\n")
        
        # Get unique items in this category and their final quantities
        category_items = {}
        for contrib in contributions:
            item_name = contrib.get('item_name', 'Unknown')
            item_key = f"{category_name}::{item_name}"
            if item_key not in category_items:
                final_qty = final_quantities.get(item_key, 0)
                category_items[item_name] = final_qty
        
        # Write current inventory summary for this category
        output.write(f"\nARCHIVED INVENTORY SUMMARY - {category_name}:\n")
        output.write("-" * 80 + "\n")
        output.write(f"{'ITEM NAME':<40} {'ARCHIVED QTY':<20} {'STATUS':<15}\n")
        output.write("-" * 80 + "\n")
        
        total_items = 0
        for item_name, qty in sorted(category_items.items()):
            status = "IN STOCK" if qty > 0 else "OUT OF STOCK" if qty == 0 else "NEGATIVE"
            output.write(f"{item_name[:39]:<40} {str(qty):<20} {status:<15}\n")
            total_items += qty
        
        output.write("-" * 80 + "\n")
        output.write(f"{'CATEGORY TOTAL:':<40} {str(total_items):<20} {'ITEMS':<15}\n")
        output.write("-" * 80 + "\n\n")
        
        # Write detailed contribution history for this category
        output.write(f"CONTRIBUTION HISTORY - {category_name}:\n")
        output.write("-" * 180 + "\n")
        
        # Enhanced table headers
        header_format = "{:<6} {:<16} {:<12} {:<10} {:<25} {:<8} {:<8} {:<20} {:<50}\n"
        output.write(header_format.format(
            "REC#", "CONTRIBUTOR", "DATE", "TIME", "ITEM_NAME", "QUANTITY", "TOTAL", "CONTRIBUTION_TYPE", "NOTES"
        ))
        output.write("-" * 180 + "\n")
        
        # Sort contributions chronologically
        sorted_contributions = sorted(contributions, key=lambda x: x.get('created_at', ''))
        
        # Track running balances for each item in this category
        running_balances = {}
        
        # Write contributions for this category
        for i, contrib in enumerate(sorted_contributions, 1):
            # Get contributor name
            contributor_name = contrib.get('discord_name', 'Unknown')[:15]
            
            # Parse timestamp details
            try:
                dt = datetime.fromisoformat(contrib['created_at'].replace('T', ' ').replace('Z', ''))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except:
                date_str = "Unknown"
                time_str = "Unknown"
            
            # Format contribution data
            item_name = contrib.get('item_name', 'Unknown')[:24]
            quantity = contrib.get('quantity', 0)
            
            # Calculate running balance for this specific item after this contribution
            item_name_key = contrib.get('item_name', 'Unknown')
            if item_name_key not in running_balances:
                running_balances[item_name_key] = 0
            running_balances[item_name_key] += quantity
            
            # Format contribution type
            contrib_type = "Contribution"
            
            # Format notes
            notes = contrib.get('notes', 'No additional notes')[:49]
            
            # Write formatted row
            output.write(header_format.format(
                f"{i:04d}",
                contributor_name,
                date_str,
                time_str,
                item_name,
                str(quantity),
                str(running_balances[item_name_key]),
                contrib_type[:19],
                notes
            ))
        
        output.write("-" * 180 + "\n")
        output.write(f"End of {category_name} - {len(contributions)} contributions processed\n")
        output.write("=" * 180 + "\n\n")

class QuantityOperationModal(discord.ui.Modal):
    def __init__(self, item_name: str, current_quantity: int, category: str, contribution_ids: List[int], operation: str = "set"):
        self.operation = operation  # 'set', 'add', or 'remove'
        
        operation_titles = {
            "set": f"Set Quantity: {item_name}",
            "add": f"Add to Quantity: {item_name}",
            "remove": f"Remove from Quantity: {item_name}"
        }
        
        super().__init__(title=operation_titles.get(operation, f"Edit Quantity: {item_name}"))
        self.item_name = item_name
        self.current_quantity = current_quantity
        self.category = category
        self.contribution_ids = contribution_ids
        
        # Operation-specific input field
        if operation == "set":
            self.quantity_input = discord.ui.TextInput(
                label="New Total Quantity",
                placeholder=f"Current: {current_quantity}. Enter new total.",
                max_length=10,
                required=True,
                default=str(current_quantity)
            )
        elif operation == "add":
            self.quantity_input = discord.ui.TextInput(
                label="Quantity to Add",
                placeholder=f"Current: {current_quantity}. Enter amount to add.",
                max_length=10,
                required=True
            )
        elif operation == "remove":
            self.quantity_input = discord.ui.TextInput(
                label="Quantity to Remove",
                placeholder=f"Current: {current_quantity}. Enter amount to remove.",
                max_length=10,
                required=True
            )
        
        self.add_item(self.quantity_input)
        
        # Operation-specific reason placeholders
        reason_placeholders = {
            "set": "e.g., 'Inventory correction', 'Manual adjustment', 'Audit findings'",
            "add": "e.g., 'New contributions', 'Found additional items', 'Restocked'",
            "remove": "e.g., 'Used in operation', 'Lost equipment', 'Damaged items', 'Distributed'"
        }
        
        # Reason input
        self.reason = discord.ui.TextInput(
            label="Reason for Change",
            placeholder=reason_placeholders.get(operation, "Reason for this change..."),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True
        )
        self.add_item(self.reason)
        
        # Notes input
        self.notes = discord.ui.TextInput(
            label="Additional Notes (Optional)",
            placeholder="Any additional context about this quantity change...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate and calculate new quantity based on operation
            input_qty = int(self.quantity_input.value)
            
            if self.operation == "set":
                if input_qty < 0:
                    raise ValueError("Quantity cannot be negative")
                new_qty = input_qty
            elif self.operation == "add":
                if input_qty <= 0:
                    raise ValueError("Amount to add must be positive")
                new_qty = self.current_quantity + input_qty
            elif self.operation == "remove":
                if input_qty <= 0:
                    raise ValueError("Amount to remove must be positive")
                new_qty = max(0, self.current_quantity - input_qty)
                if self.current_quantity - input_qty < 0:
                    # If removing more than available, warn user
                    embed = discord.Embed(
                        title="⚠️ Warning: Removing More Than Available",
                        description=f"You're trying to remove {input_qty} items, but only {self.current_quantity} are available.\n"
                                   f"The quantity will be set to 0 instead.\n\n"
                                   f"**Original Quantity:** {self.current_quantity}\n"
                                   f"**Requested Removal:** {input_qty}\n"
                                   f"**Final Quantity:** 0",
                        color=discord.Color.orange()
            )
                    view = ConfirmOperationView(self, interaction, new_qty, input_qty)
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                    return
            
            # Get the bot instance
            bot = interaction.client
            
            # Calculate the actual difference
            difference = new_qty - self.current_quantity
            
            # Create detailed operation description for logging
            if self.operation == "set":
                operation_desc = f"Set to {new_qty}"
            elif self.operation == "add":
                operation_desc = f"Added {input_qty} (from {self.current_quantity})"
            elif self.operation == "remove":
                actual_removed = min(input_qty, self.current_quantity)
                operation_desc = f"Removed {actual_removed} (from {self.current_quantity})"
            
            # Log the quantity change with operation details
            change_id = await bot.db.log_quantity_change(
                interaction.guild.id,
                self.item_name,
                self.category,
                self.current_quantity,
                new_qty,
                f"[{self.operation.upper()}] {self.reason.value}",
                f"Operation: {operation_desc}\nNotes: {self.notes.value}" if self.notes.value else f"Operation: {operation_desc}",
                interaction.user.id
            )
            
            # Update the actual quantities in contributions
            await bot.db.update_item_quantities(
                interaction.guild.id,
                self.item_name,
                self.category,
                new_qty
            )
            
            # Log to officer channel if configured
            await self._log_quantity_change_to_channel(
                bot, interaction, operation_desc, new_qty, difference
            )
            
            # Create response embed
            operation_emoji = {"set": "🔄", "add": "➕", "remove": "➖"}
            embed = discord.Embed(
                title=f"{operation_emoji.get(self.operation, '✅')} Quantity {self.operation.title()} Successfully",
                color=discord.Color.green() if difference >= 0 else discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Item Details",
                value=f"**Item:** {self.item_name}\n"
                      f"**Category:** {self.category}\n"
                      f"**Previous Quantity:** {self.current_quantity}\n"
                      f"**New Quantity:** {new_qty}\n"
                      f"**Net Change:** {'+' if difference >= 0 else ''}{difference}",
                inline=False
            )
            
            embed.add_field(
                name="Operation Details",
                value=f"**Type:** {self.operation.title()}\n"
                      f"**Operation:** {operation_desc}\n"
                      f"**Reason:** {self.reason.value}",
                inline=False
            )
            
            if self.notes.value:
                embed.add_field(
                    name="Additional Notes",
                    value=self.notes.value,
                    inline=False
                )
            
            embed.add_field(
                name="Change Log",
                value=f"**Change ID:** {change_id}\n"
                      f"**Modified by:** {interaction.user.mention}\n"
                      f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Input",
                description=f"Please check your input: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Updating Quantity",
                description=f"An error occurred while updating the quantity: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _log_quantity_change_to_channel(self, bot, interaction, operation_desc, new_qty, difference):
        """Log quantity changes to the configured officer or notification channel"""
        try:
            config = await bot.db.get_server_config(interaction.guild.id)
            if not config:
                return
            
            # Try officer channel first, then notification channel
            channel_id = config.get('leadership_channel_id') or config.get('notification_channel_id')
            if not channel_id:
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                return
            
            # Create log embed
            operation_emoji = {"set": "🔄", "add": "➕", "remove": "➖"}
            embed = discord.Embed(
                title=f"{operation_emoji.get(self.operation, '📝')} Inventory {self.operation.title()}",
                description=f"**{interaction.user.mention}** modified inventory quantities",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Item Information",
                value=f"**Item:** {self.item_name}\n"
                      f"**Category:** {self.category}\n"
                      f"**Operation:** {operation_desc}\n"
                      f"**Final Quantity:** {new_qty}\n"
                      f"**Net Change:** {'+' if difference >= 0 else ''}{difference}",
                inline=True
            )
            
            embed.add_field(
                name="Change Details",
                value=f"**Reason:** {self.reason.value}\n"
                      f"**Modified by:** {interaction.user.display_name}\n"
                      f"**Channel:** {interaction.channel.mention if hasattr(interaction, 'channel') else 'Menu System'}",
                inline=True
            )
            
            if self.notes.value:
                embed.add_field(
                    name="Notes",
                    value=self.notes.value,
                    inline=False
                )
            
            await channel.send(embed=embed)
            
        except Exception as e:
            # Don't fail the operation if logging fails
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log quantity change to channel: {e}")

class ConfirmOperationView(discord.ui.View):
    def __init__(self, modal, interaction, new_qty, input_qty):
        super().__init__(timeout=60)
        self.modal = modal
        self.original_interaction = interaction
        self.new_qty = new_qty
        self.input_qty = input_qty
    
    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm_operation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the original user can confirm this operation.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get the bot instance
            bot = interaction.client
            
            # Calculate the actual difference
            difference = self.new_qty - self.modal.current_quantity
            
            # Create operation description
            actual_removed = min(self.input_qty, self.modal.current_quantity)
            operation_desc = f"Removed {actual_removed} (from {self.modal.current_quantity}) - exceeded available quantity"
            
            # Log the quantity change
            change_id = await bot.db.log_quantity_change(
                interaction.guild.id,
                self.modal.item_name,
                self.modal.category,
                self.modal.current_quantity,
                self.new_qty,
                f"[{self.modal.operation.upper()}] {self.modal.reason.value}",
                f"Operation: {operation_desc}\nNotes: {self.modal.notes.value}" if self.modal.notes.value else f"Operation: {operation_desc}",
                interaction.user.id
            )
            
            # Update the actual quantities in contributions
            await bot.db.update_item_quantities(
                interaction.guild.id,
                self.modal.item_name,
                self.modal.category,
                self.new_qty
            )
            
            # Log to officer channel if configured
            await self.modal._log_quantity_change_to_channel(
                bot, interaction, operation_desc, self.new_qty, difference
            )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Quantity Remove Confirmed",
                description=f"Successfully processed the remove operation.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Item Details",
                value=f"**Item:** {self.modal.item_name}\n"
                      f"**Category:** {self.modal.category}\n"
                      f"**Previous Quantity:** {self.modal.current_quantity}\n"
                      f"**Requested Removal:** {self.input_qty}\n"
                      f"**Actual Removal:** {actual_removed}\n"
                      f"**Final Quantity:** {self.new_qty}",
                inline=False
            )
            
            embed.add_field(
                name="Operation Details",
                value=f"**Reason:** {self.modal.reason.value}\n"
                      f"**Change ID:** {change_id}\n"
                      f"**Modified by:** {interaction.user.mention}",
                inline=False
            )
            
            if self.modal.notes.value:
                embed.add_field(
                    name="Additional Notes",
                    value=self.modal.notes.value,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Confirming Operation",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_operation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the original user can cancel this operation.", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="❌ Operation Cancelled",
            description="The quantity change operation has been cancelled.",
            color=discord.Color.greyple()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class QuantityOperationSelectView(discord.ui.View):
    def __init__(self, item_name: str, current_quantity: int, category: str, contribution_ids: List[int]):
        super().__init__(timeout=300)
        self.item_name = item_name
        self.current_quantity = current_quantity
        self.category = category
        self.contribution_ids = contribution_ids
    
    @discord.ui.button(label="🔄 Set Quantity", style=discord.ButtonStyle.primary, emoji="🔄")
    async def set_quantity(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = QuantityOperationModal(
            self.item_name, self.current_quantity, self.category, 
            self.contribution_ids, "set"
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➕ Add Quantity", style=discord.ButtonStyle.success, emoji="➕")
    async def add_quantity(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = QuantityOperationModal(
            self.item_name, self.current_quantity, self.category, 
            self.contribution_ids, "add"
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Remove Quantity", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_quantity(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = QuantityOperationModal(
            self.item_name, self.current_quantity, self.category, 
            self.contribution_ids, "remove"
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📊 View History", style=discord.ButtonStyle.secondary, emoji="📊")
    async def view_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get the database management cog to use its history method
        db_cog = interaction.client.get_cog('DatabaseManagement')
        if db_cog:
            await db_cog.quantity_history.callback(db_cog, interaction, self.item_name)
        else:
            await interaction.response.send_message(
                "❌ Database management system not available.", 
                ephemeral=True
            )

class ItemSelectView(discord.ui.View):
    def __init__(self, items: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.items = items
        
        # Create select options (limit to 25 items due to Discord limit)
        options = []
        for item in items[:25]:
            description = f"{item['category']} - Qty: {item['total_quantity']}"
            options.append(
                discord.SelectOption(
                    label=item['item_name'][:100],  # Discord limit
                    description=description[:100],  # Discord limit
                    value=f"{item['item_name']}|{item['category']}"
                )
            )
        
        self.item_select = discord.ui.Select(
            placeholder="Select an item to edit...",
            options=options
        )
        self.item_select.callback = self.item_selected
        self.add_item(self.item_select)
        
        if len(items) > 25:
            # Add note about limitation
            self.add_item(discord.ui.Button(
                label=f"Showing first 25 of {len(items)} items",
                style=discord.ButtonStyle.secondary,
                disabled=True
            ))
    
    async def item_selected(self, interaction: discord.Interaction):
        selected_value = self.item_select.values[0]
        item_name, category = selected_value.split('|', 1)
        
        # Find the selected item
        selected_item = None
        for item in self.items:
            if item['item_name'] == item_name and item['category'] == category:
                selected_item = item
                break
        
        if not selected_item:
            await interaction.response.send_message("❌ Item not found.", ephemeral=True)
            return
        
        # Open operation selection view
        view = QuantityOperationSelectView(
            item_name=selected_item['item_name'],
            current_quantity=selected_item['total_quantity'],
            category=selected_item['category'],
            contribution_ids=selected_item.get('contribution_ids', [])
        )
        
        embed = discord.Embed(
            title=f"🔧 Edit {selected_item['item_name']}",
            description=f"**Category:** {selected_item['category']}\n"
                       f"**Current Quantity:** {selected_item['total_quantity']}\n\n"
                       f"Choose the operation you want to perform:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Available Operations",
            value="🔄 **Set Quantity** - Set exact total amount\n"
                  "➕ **Add Quantity** - Add to existing amount\n"
                  "➖ **Remove Quantity** - Remove from existing amount\n"
                  "📊 **View History** - See quantity change log",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)

class DatabaseManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def _clear_forum_threads(self, bot, guild_id: int):
        """Clear the contents of forum threads while preserving the threads themselves"""
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                logging.getLogger(__name__).warning(f"Guild {guild_id} not found for thread clearing")
                return []
            
            # Get server configuration to find forum channels
            config = await bot.db.get_server_config(guild_id)
            if not config:
                logging.getLogger(__name__).warning(f"No server config found for guild {guild_id}")
                return []
            
            # Target forum channel IDs for thread clearing
            forum_channel_ids = []
            
            # Add configured forum channels
            if config.get('weapons_locker_forum_channel_id'):
                forum_channel_ids.append(config['weapons_locker_forum_channel_id'])
            if config.get('drug_locker_forum_channel_id'):
                forum_channel_ids.append(config['drug_locker_forum_channel_id'])
            if config.get('misc_locker_forum_channel_id'):
                forum_channel_ids.append(config['misc_locker_forum_channel_id'])
            
            # If no forum channels configured, use all known forum channels as fallback
            if not forum_channel_ids:
                forum_channel_ids = [
                    1366605626662322236,  # Misc-Locker forum
                    1366601638130880582,  # Drug-Locker forum  
                    1355399894227091517   # Weapons-Locker forum
                ]
                logging.getLogger(__name__).info(f"Using fallback forum channels for guild {guild_id}")
            
            # Collect all threads from all forum channels
            thread_ids_to_clear = {}
            logger = logging.getLogger(__name__)
            
            for forum_channel_id in forum_channel_ids:
                try:
                    # Get the target channel
                    target_channel = guild.get_channel(forum_channel_id)
                    if not target_channel:
                        try:
                            target_channel = await guild.fetch_channel(forum_channel_id)
                        except discord.NotFound:
                            logger.warning(f"Forum channel {forum_channel_id} not found")
                            continue
                        except Exception as e:
                            logger.error(f"Error fetching forum channel {forum_channel_id}: {e}")
                            continue
                    
                    if not isinstance(target_channel, discord.ForumChannel):
                        logger.warning(f"Channel {forum_channel_id} is not a forum channel, skipping")
                        continue
                    
                    logger.info(f"Processing forum channel: {target_channel.name} (ID: {forum_channel_id})")
                    
                    # Get active threads from this forum channel
                    for thread in target_channel.threads:
                        thread_ids_to_clear[thread.id] = f"{target_channel.name}::{thread.name}"
                    
                    # Get archived threads from this forum channel
                    try:
                        async for thread in target_channel.archived_threads(limit=100):
                            thread_ids_to_clear[thread.id] = f"{target_channel.name}::{thread.name}"
                    except Exception as e:
                        logger.warning(f"Error fetching archived threads from forum channel {forum_channel_id}: {e}")
                        
                except Exception as e:
                    logger.error(f"Error processing forum channel {forum_channel_id}: {e}")
                    continue
            
            cleared_threads = []
            logger = logging.getLogger(__name__)
            
            for thread_id, category_name in thread_ids_to_clear.items():
                try:
                    # Try to get the thread from the guild
                    thread = guild.get_thread(thread_id)
                    if not thread:
                        # Try fetching it if not in cache
                        try:
                            thread = await guild.fetch_channel(thread_id)
                        except discord.NotFound:
                            logger.warning(f"Thread {thread_id} ({category_name}) not found")
                            continue
                        except Exception as e:
                            logger.error(f"Error fetching thread {thread_id} ({category_name}): {e}")
                            continue
                    
                    if not isinstance(thread, discord.Thread):
                        logger.warning(f"Channel {thread_id} is not a thread, skipping")
                        continue
                    
                    # If thread is archived, unarchive it temporarily to delete messages
                    was_archived = thread.archived
                    if was_archived:
                        try:
                            await thread.edit(archived=False)
                            logger.info(f"Temporarily unarchived thread '{thread.name}' for clearing")
                            # Small delay to ensure unarchiving takes effect
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.error(f"Could not unarchive thread '{thread.name}': {e}")
                            continue
                    
                    # Count messages before clearing
                    messages_cleared = 0
                    messages_to_delete = []
                    
                    # Collect ALL messages for deletion - we want to completely clear the threads
                    try:
                        async for message in thread.history(limit=None, oldest_first=True):
                            # Delete ALL messages - including pinned messages and original posts
                            messages_to_delete.append(message)
                    
                    except Exception as e:
                        logger.error(f"Error collecting messages from thread '{thread.name}': {e}")
                        continue
                    
                    # Delete messages in batches to handle rate limits better
                    logger.info(f"Found {len(messages_to_delete)} messages to delete in thread '{thread.name}'")
                    
                    for message in messages_to_delete:
                        try:
                            await message.delete()
                            messages_cleared += 1
                            
                            # Add a delay to respect rate limits
                            await asyncio.sleep(0.2)
                            
                        except discord.NotFound:
                            # Message already deleted
                            messages_cleared += 1
                            continue
                        except discord.Forbidden:
                            logger.error(f"No permission to delete message {message.id} in thread {thread.name}")
                            continue
                        except Exception as e:
                            logger.error(f"Error deleting message {message.id} in thread {thread.name}: {e}")
                            continue
                    
                    # Re-archive the thread if it was originally archived
                    if was_archived:
                        try:
                            await thread.edit(archived=True)
                            logger.info(f"Re-archived thread '{thread.name}'")
                        except Exception as e:
                            logger.error(f"Could not re-archive thread '{thread.name}': {e}")
                    
                    cleared_threads.append({
                        'name': category_name,
                        'thread_name': thread.name,
                        'thread_id': thread_id,
                        'messages_cleared': messages_cleared,
                        'was_archived': was_archived
                    })
                    
                    # Post an archive notification message to the now-cleared thread
                    # Always post if thread is not archived, regardless of messages cleared
                    if not thread.archived:
                        try:
                            # Check if the last message is already an archive notification
                            # to avoid double posting
                            last_message = None
                            try:
                                async for msg in thread.history(limit=1):
                                    last_message = msg
                                    break
                            except:
                                pass
                            
                            # Only post if the last message isn't already an archive notification
                            should_post = True
                            if (last_message and 
                                last_message.author.id == bot.user.id and 
                                "Thread Contents Archived" in last_message.content):
                                should_post = False
                                logger.debug(f"Skipping duplicate archive message in thread '{thread.name}'")
                            
                            if should_post:
                                archive_message = (
                                    f"🗃️ **Thread Contents Archived**\n\n"
                                    f"The previous contents of this thread have been archived and cleared as part of a database archive.\n"
                                    f"This thread is now ready for fresh contributions.\n\n"
                                    f"*Cleared: {messages_cleared} messages | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*"
                                )
                                await thread.send(archive_message)
                                logger.info(f"Posted archive notification to thread '{thread.name}'")
                        except Exception as e:
                            logger.error(f"Error posting archive notification to thread {thread.name}: {e}")
                    
                    logger.info(f"Successfully cleared {messages_cleared} messages from thread '{thread.name}' ({category_name})")
                    
                except Exception as e:
                    logger.error(f"Error processing thread {thread_id} ({category_name}): {e}")
                    continue
            
            logger.info(f"Cleared {len(cleared_threads)} forum threads for guild {guild_id}")
            return cleared_threads
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to clear forum threads for guild {guild_id}: {e}")
            return []
    
    async def _get_contribution_summary(self, guild_id: int) -> Dict[str, Any]:
        """Get a complete summary of all contributions"""
        contributions = await self.bot.db.get_all_contributions(guild_id)
        
        if not contributions:
            return {"total_contributions": 0, "categories": {}, "contributors": {}, "items": {}}
        
        # Aggregate data
        categories = {}
        contributors = {}
        items = {}
        
        for contrib in contributions:
            category = contrib['category']
            contributor = contrib['discord_name']
            item_name = contrib['item_name']
            quantity = contrib['quantity']
            
            # Category totals
            if category not in categories:
                categories[category] = {"total_quantity": 0, "contributions": 0, "unique_contributors": set(), "items": {}}
            categories[category]["total_quantity"] += quantity
            categories[category]["contributions"] += 1
            categories[category]["unique_contributors"].add(contributor)
            
            if item_name not in categories[category]["items"]:
                categories[category]["items"][item_name] = 0
            categories[category]["items"][item_name] += quantity
            
            # Contributor totals
            if contributor not in contributors:
                contributors[contributor] = {"total_quantity": 0, "contributions": 0, "categories": set()}
            contributors[contributor]["total_quantity"] += quantity
            contributors[contributor]["contributions"] += 1
            contributors[contributor]["categories"].add(category)
            
            # Item totals (cross-category)
            if item_name not in items:
                items[item_name] = {"total_quantity": 0, "contributions": 0, "categories": set()}
            items[item_name]["total_quantity"] += quantity
            items[item_name]["contributions"] += 1
            items[item_name]["categories"].add(category)
        
        # Convert sets to lists for JSON serialization
        for cat_data in categories.values():
            cat_data["unique_contributors"] = list(cat_data["unique_contributors"])
        
        for contrib_data in contributors.values():
            contrib_data["categories"] = list(contrib_data["categories"])
        
        for item_data in items.values():
            item_data["categories"] = list(item_data["categories"])
        
        return {
            "total_contributions": len(contributions),
            "categories": categories,
            "contributors": contributors,
            "items": items,
            "generated_at": datetime.now().isoformat()
        }
    
    @app_commands.command(name="database_summary", description="Generate a comprehensive database summary")
    @app_commands.describe(format="Choose the output format for the summary")
    @app_commands.choices(format=[
        app_commands.Choice(name="Discord Embed", value="embed"),
        app_commands.Choice(name="Text File", value="text"),
        app_commands.Choice(name="JSON Export", value="json")
    ])
    async def database_summary(self, interaction: discord.Interaction, format: str = "embed"):
        """Generate a comprehensive summary of the contribution database"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return await interaction.response.send_message(
                "❌ Officer role not configured.", ephemeral=True
            )
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ This command is only available to officers.", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            summary = await self._get_contribution_summary(interaction.guild.id)
            
            if summary["total_contributions"] == 0:
                embed = discord.Embed(
                    title="📋 Database Summary",
                    description="No contributions found in the database.",
                    color=discord.Color.blue()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            if format == "embed":
                await self._send_embed_summary(interaction, summary)
            elif format == "text":
                await self._send_text_summary(interaction, summary)
            elif format == "json":
                await self._send_json_summary(interaction, summary)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Generating Summary",
                description=f"An error occurred while generating the summary: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _send_embed_summary(self, interaction: discord.Interaction, summary: Dict[str, Any]):
        """Send summary as Discord embeds"""
        embeds = []
        
        # Main summary embed
        main_embed = discord.Embed(
            title="📋 Database Summary Report",
            description=f"**Total Contributions:** {summary['total_contributions']}\n"
                       f"**Categories:** {len(summary['categories'])}\n"
                       f"**Contributors:** {len(summary['contributors'])}\n"
                       f"**Unique Items:** {len(summary['items'])}",
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(summary['generated_at'])
        )
        embeds.append(main_embed)
        
        # Category breakdown embed
        if summary['categories']:
            cat_embed = discord.Embed(
                title="📦 Category Breakdown",
                color=discord.Color.green()
            )
            
            for category, data in sorted(summary['categories'].items(), 
                                       key=lambda x: x[1]['total_quantity'], reverse=True):
                top_items = sorted(data['items'].items(), key=lambda x: x[1], reverse=True)[:5]
                items_text = "\n".join([f"• {item}: {qty}" for item, qty in top_items])
                
                field_value = f"**Total Quantity:** {data['total_quantity']}\n"
                field_value += f"**Contributions:** {data['contributions']}\n"
                field_value += f"**Contributors:** {len(data['unique_contributors'])}\n\n"
                field_value += f"**Top Items:**\n{items_text}"
                
                if len(data['items']) > 5:
                    field_value += f"\n... and {len(data['items']) - 5} more"
                
                cat_embed.add_field(
                    name=f"🔸 {category}",
                    value=field_value[:1000],  # Discord limit
                    inline=True
                )
            
            embeds.append(cat_embed)
        
        # Top contributors embed
        if summary['contributors']:
            contrib_embed = discord.Embed(
                title="👥 Top Contributors",
                color=discord.Color.purple()
            )
            
            top_contributors = sorted(summary['contributors'].items(), 
                                    key=lambda x: x[1]['contributions'], reverse=True)[:15]
            
            contrib_text = ""
            for i, (name, data) in enumerate(top_contributors, 1):
                contrib_text += f"{i:2d}. **{name}**\n"
                contrib_text += f"    Contributions: {data['contributions']} | Total Items: {data['total_quantity']}\n"
                contrib_text += f"    Categories: {', '.join(data['categories'])}\n\n"
            
            contrib_embed.description = contrib_text[:2000]  # Discord limit
            embeds.append(contrib_embed)
        
        # Send all embeds
        for i, embed in enumerate(embeds):
            if i == 0:
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _send_text_summary(self, interaction: discord.Interaction, summary: Dict[str, Any]):
        """Send summary as a text file"""
        text_content = f"DATABASE SUMMARY REPORT\n"
        text_content += f"Generated: {summary['generated_at']}\n"
        text_content += f"Guild: {interaction.guild.name}\n"
        text_content += "=" * 50 + "\n\n"
        
        text_content += f"OVERVIEW\n"
        text_content += f"Total Contributions: {summary['total_contributions']}\n"
        text_content += f"Categories: {len(summary['categories'])}\n"
        text_content += f"Contributors: {len(summary['contributors'])}\n"
        text_content += f"Unique Items: {len(summary['items'])}\n\n"
        
        # Categories section
        text_content += "CATEGORIES\n" + "-" * 20 + "\n"
        for category, data in sorted(summary['categories'].items(), 
                                   key=lambda x: x[1]['total_quantity'], reverse=True):
            text_content += f"\n{category}:\n"
            text_content += f"  Total Quantity: {data['total_quantity']}\n"
            text_content += f"  Contributions: {data['contributions']}\n"
            text_content += f"  Contributors: {len(data['unique_contributors'])}\n"
            text_content += f"  Items:\n"
            
            for item, qty in sorted(data['items'].items(), key=lambda x: x[1], reverse=True):
                text_content += f"    • {item}: {qty}\n"
        
        # Contributors section
        text_content += f"\n\nCONTRIBUTORS\n" + "-" * 20 + "\n"
        for name, data in sorted(summary['contributors'].items(), 
                               key=lambda x: x[1]['contributions'], reverse=True):
            text_content += f"\n{name}:\n"
            text_content += f"  Contributions: {data['contributions']}\n"
            text_content += f"  Total Items: {data['total_quantity']}\n"
            text_content += f"  Categories: {', '.join(data['categories'])}\n"
        
        # Save to temporary file
        filename = f"database_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join("temp", filename)
        
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        # Send file
        file = discord.File(filepath, filename=filename)
        await interaction.followup.send(
            content="📄 **Database Summary Report** (Text Format)",
            file=file,
            ephemeral=True
        )
        
        # Clean up temp file
        try:
            os.remove(filepath)
        except:
            pass
    
    async def _send_json_summary(self, interaction: discord.Interaction, summary: Dict[str, Any]):
        """Send summary as a JSON file"""
        filename = f"database_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join("temp", filename)
        
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Add guild information to summary
        summary['guild_name'] = interaction.guild.name
        summary['guild_id'] = interaction.guild.id
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Send file
        file = discord.File(filepath, filename=filename)
        await interaction.followup.send(
            content="📊 **Database Summary Report** (JSON Format)\n"
                   "*This format can be imported into spreadsheets or other analysis tools.*",
            file=file,
            ephemeral=True
        )
        
        # Clean up temp file
        try:
            os.remove(filepath)
        except:
            pass
    
    @app_commands.command(name="create_archive", description="Create a new database archive and reset current data")
    async def create_archive(self, interaction: discord.Interaction):
        """Create a new database archive"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return await interaction.response.send_message(
                "❌ Officer role not configured.", ephemeral=True
            )
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ This command is only available to officers.", ephemeral=True
            )
        
        # Get current summary for preview
        try:
            summary = await self._get_contribution_summary(interaction.guild.id)
            
            if summary["total_contributions"] == 0:
                embed = discord.Embed(
                    title="❌ No Data to Archive",
                    description="There are no contributions to archive. The database is empty.",
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Show modal to get archive details
            modal = DatabaseArchiveModal(summary)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Creating Archive",
                description=f"An error occurred while preparing the archive: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="view_archives", description="View all database archives")
    async def view_archives(self, interaction: discord.Interaction):
        """View all available archives with dropdown selection"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return await interaction.response.send_message(
                "❌ Officer role not configured.", ephemeral=True
            )
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ This command is only available to officers.", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            archives = await self.bot.db.get_database_archives(interaction.guild.id)
            
            if not archives:
                embed = discord.Embed(
                    title="📚 Database Archives",
                    description="No archives found. Use `/create_archive` to create your first archive.",
                    color=discord.Color.blue()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Create dropdown view
            view = ArchiveSelectionView(archives)
            
            embed = discord.Embed(
                title="📚 Database Archives",
                description=f"**Found {len(archives)} archive(s)**\n\n"
                           f"Select an archive from the dropdown below to view its detailed contents.",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Show overview of recent archives
            recent_archives = archives[-5:]  # Show last 5 archives
            archive_list = []
            for archive in recent_archives:
                created_date = datetime.fromisoformat(archive['created_at']).strftime('%Y-%m-%d %H:%M')
                archive_data = json.loads(archive['archived_data'])
                archive_list.append(
                    f"• **{archive['archive_name']}** ({created_date})\n"
                    f"  └ {archive_data.get('total_contributions', 0)} contributions"
                )
            
            embed.add_field(
                name="🔍 Recent Archives",
                value="\n".join(archive_list) if archive_list else "No recent archives",
                inline=False
            )
            
            if len(archives) > 5:
                embed.set_footer(text=f"Showing 5 most recent • Use dropdown to view all {len(archives)} archives")
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Loading Archives",
                description=f"An error occurred while loading archives: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="edit_quantity", description="Edit the quantity of items in the database")
    async def edit_quantity(self, interaction: discord.Interaction, search_term: str = None):
        """Edit item quantities in the database"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return await interaction.response.send_message(
                "❌ Officer role not configured.", ephemeral=True
            )
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ This command is only available to officers.", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get current item quantities using unified calculation (contributions + quantity changes)
            items = await self.bot.db.get_all_current_item_quantities(interaction.guild.id)
            
            if not items:
                embed = discord.Embed(
                    title="❌ No Items Found",
                    description="No items with positive quantities found in the database.",
                    color=discord.Color.red()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Filter by search term if provided
            if search_term:
                filtered_items = []
                search_lower = search_term.lower()
                for item in items.values():
                    if (search_lower in item['item_name'].lower() or 
                        search_lower in item['category'].lower()):
                        filtered_items.append(item)
            else:
                filtered_items = list(items.values())
            
            if not filtered_items:
                embed = discord.Embed(
                    title="❌ No Items Found",
                    description=f"No items found matching '{search_term}'." if search_term else "No items found.",
                    color=discord.Color.red()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Sort by total quantity (descending)
            filtered_items.sort(key=lambda x: x['total_quantity'], reverse=True)
            
            # Create selection view
            view = ItemSelectView(filtered_items)
            
            embed = discord.Embed(
                title="🔧 Edit Item Quantities",
                description=f"**Found {len(filtered_items)} items**\n\n"
                           f"Select an item below to edit its quantity.\n"
                           f"This is useful for tracking usage, loss, or damage.",
                color=discord.Color.blue()
            )
            
            if search_term:
                embed.add_field(
                    name="Search Filter",
                    value=f"Showing items matching: **{search_term}**",
                    inline=False
                )
            
            # Show top items in embed
            top_items = filtered_items[:10]
            items_text = ""
            for item in top_items:
                items_text += f"• **{item['item_name']}** ({item['category']}) - Qty: {item['total_quantity']}\n"
            
            embed.add_field(
                name=f"📦 Items Available for Editing",
                value=items_text,
                inline=False
            )
            
            if len(filtered_items) > 10:
                embed.set_footer(text=f"Use the dropdown to select from all {len(filtered_items)} items")
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Loading Items",
                description=f"An error occurred while loading items: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="quantity_history", description="View the quantity change history for an item")
    async def quantity_history(self, interaction: discord.Interaction, item_name: str):
        """View quantity change history for a specific item"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return await interaction.response.send_message(
                "❌ Officer role not configured.", ephemeral=True
            )
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ This command is only available to officers.", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            history = await self.bot.db.get_quantity_change_history(interaction.guild.id, item_name)
            
            if not history:
                embed = discord.Embed(
                    title="❌ No History Found",
                    description=f"No quantity changes found for item: **{item_name}**",
                    color=discord.Color.red()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            embed = discord.Embed(
                title=f"📊 Quantity History: {item_name}",
                description=f"Found {len(history)} quantity changes",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            for i, change in enumerate(history[-10:], 1):  # Show last 10 changes
                change_date = datetime.fromisoformat(change['changed_at']).strftime('%Y-%m-%d %H:%M')
                difference = change['new_quantity'] - change['old_quantity']
                
                field_value = f"**From:** {change['old_quantity']} → **To:** {change['new_quantity']}\n"
                field_value += f"**Change:** {'+' if difference >= 0 else ''}{difference}\n"
                field_value += f"**Reason:** {change['reason']}\n"
                field_value += f"**Date:** {change_date}\n"
                field_value += f"**Modified by:** {change.get('changed_by_name', 'Unknown')}\n"
                
                if change['notes']:
                    field_value += f"**Notes:** {change['notes']}\n"
                
                embed.add_field(
                    name=f"📝 Change #{len(history) - len(history) + i}",
                    value=field_value,
                    inline=False
                )
            
            if len(history) > 10:
                embed.set_footer(text=f"Showing 10 most recent changes out of {len(history)} total")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Loading History",
                description=f"An error occurred while loading quantity history: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="find_threads", description="List all threads in the server to help identify missing IDs")
    async def find_threads(self, interaction: discord.Interaction):
        """List all threads in the server to help identify missing thread IDs for archive clearing"""
        # Check permissions
        config = await self.bot.db.get_server_config(interaction.guild.id)
        if not config or not config.get('officer_role_id'):
            return await interaction.response.send_message(
                "❌ Officer role not configured.", ephemeral=True
            )
        
        officer_role = interaction.guild.get_role(config['officer_role_id'])
        if not officer_role or officer_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ This command is only available to officers.", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild = interaction.guild
            thread_info = []
            
            # Get active threads
            active_threads = guild.threads
            for thread in active_threads:
                thread_info.append({
                    'name': thread.name,
                    'id': thread.id,
                    'parent': thread.parent.name if thread.parent else 'Unknown',
                    'archived': thread.archived,
                    'type': 'Active'
                })
            
            # Get archived threads from each channel
            for channel in guild.channels:
                if hasattr(channel, 'archived_threads'):
                    try:
                        async for thread in channel.archived_threads(limit=50):
                            thread_info.append({
                                'name': thread.name,
                                'id': thread.id,
                                'parent': channel.name,
                                'archived': True,
                                'type': 'Archived'
                            })
                    except:
                        # Skip channels we can't access
                        pass
            
            if not thread_info:
                embed = discord.Embed(
                    title="📋 Thread Finder",
                    description="No threads found in this server.",
                    color=discord.Color.blue()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Create text file with thread information
            output = []
            output.append(f"THREAD IDs FOR {guild.name}")
            output.append("=" * 60)
            output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
            output.append(f"Total threads found: {len(thread_info)}\n")
            
            # Group by parent channel
            channels = {}
            for thread in thread_info:
                parent = thread['parent']
                if parent not in channels:
                    channels[parent] = []
                channels[parent].append(thread)
            
            for channel_name, threads in sorted(channels.items()):
                output.append(f"📁 Channel: {channel_name}")
                output.append("-" * 40)
                
                for thread in threads:
                    status = "[ARCHIVED]" if thread['archived'] else "[ACTIVE]  "
                    output.append(f"  {status} {thread['name']}")
                    output.append(f"           ID: {thread['id']}")
                    output.append("")
                
                output.append("")
            
            # Current configured threads
            output.append("CURRENTLY CONFIGURED THREADS IN BOT:")
            output.append("=" * 60)
            configured_threads = {
                # Weapons Locker threads
                1355399943967211609: "Pistols",
                1355400063685234838: "Rifles", 
                1355400006504284252: "SMGs",
                1355400270024015973: "Body Armour & Medical",
                
                # Drug Locker threads  
                1366601843240603648: "Meth",
                1389788322976497734: "Weed",
                
                # Misc Locker threads
                1368632475986694224: "Heist Items",
                1380363715983048826: "Dirty Cash",
                1389785875789119521: "Drug Items",
                1389787215042842714: "Mech Shop",
                1366606110315778118: "Crafting Items",
            }
            
            for thread_id, name in configured_threads.items():
                # Check if this thread still exists
                found = False
                for thread in thread_info:
                    if thread['id'] == thread_id:
                        found = True
                        break
                
                status = "✅ FOUND" if found else "❌ MISSING"
                output.append(f"  {status} {name} (ID: {thread_id})")
            
            output.append("")
            output.append("Instructions:")
            output.append("1. Look for threads that should be cleared during archiving")
            output.append("2. Find their IDs in the list above")
            output.append("3. Add missing thread IDs to the bot configuration")
            output.append("4. Remove any ❌ MISSING threads from the configuration")
            
            # Create text file
            file_content = "\n".join(output)
            filename = f"thread_ids_{guild.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
            
            # Create Discord file object
            file = discord.File(
                io.StringIO(file_content),
                filename=filename
            )
            
            # Create summary embed
            embed = discord.Embed(
                title="📋 Thread Finder Results",
                description=f"Found **{len(thread_info)}** threads in {guild.name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 Summary",
                value=f"Active: {len([t for t in thread_info if not t['archived']])}\n"
                     f"Archived: {len([t for t in thread_info if t['archived']])}\n"
                     f"Channels: {len(channels)}",
                inline=True
            )
            
            embed.add_field(
                name="🔧 Purpose",
                value="Use this file to:\n"
                     "• Find missing thread IDs\n"
                     "• Update archive clearing config\n"
                     "• Verify thread existence",
                inline=True
            )
            
            embed.set_footer(text="Check the attached file for detailed thread information")
            
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Finding Threads",
                description=f"An error occurred while finding threads: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

# Fixes for archive and wipe commands for misc locker
async def get_misc_locker_forum_channel(bot, guild_id):
    """Get the misc locker forum channel for the guild"""
    config = await bot.db.get_server_config(guild_id)
    forum_channel_id = config.get('misc_locker_forum_channel_id') if config else None
    if forum_channel_id:
        guild = bot.get_guild(guild_id)
        if guild:
            return guild.get_channel(forum_channel_id)
    return None

async def create_misc_archive(bot, guild_id):
    """Create archive for misc locker categories"""
    # Use misc locker forum channel
    forum_channel = await get_misc_locker_forum_channel(bot, guild_id)
    if not forum_channel:
        raise ValueError('Misc Locker forum channel not configured.')
    
    # Archive contributions and logs related to misc locker
    # Assuming contributions table has a category field to filter misc categories
    misc_categories = ["Heist Items", "Dirty Cash", "Drug Items", "Mech Shop", "Crafting Items"]
    conn = await bot.db._get_shared_connection()
    await conn.execute('BEGIN')
    try:
        # Delete audit log entries linked to misc categories
        await conn.execute(
            'DELETE FROM audit_logs WHERE guild_id = ? AND category IN ({seq})'.format(
                seq=','.join(['?']*len(misc_categories))
            ), 
            [guild_id] + misc_categories
        )
        # Delete contributions linked to misc categories
        await conn.execute(
            'DELETE FROM contributions WHERE guild_id = ? AND category IN ({seq})'.format(
                seq=','.join(['?']*len(misc_categories))
            ), 
            [guild_id] + misc_categories
        )
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise e

async def wipe_misc_locker(bot, guild_id):
    """Wipe all contributions and audit logs related to misc locker"""
    # Delete all contributions and audit logs related to misc locker
    forum_channel = await get_misc_locker_forum_channel(bot, guild_id)
    if not forum_channel:
        raise ValueError('Misc Locker forum channel not configured.')
    
    misc_categories = ["Heist Items", "Dirty Cash", "Drug Items", "Mech Shop", "Crafting Items"]
    conn = await bot.db._get_shared_connection()
    await conn.execute('BEGIN')
    try:
        # Remove audit logs
        await conn.execute(
            'DELETE FROM audit_logs WHERE guild_id = ? AND category IN ({seq})'.format(
                seq=','.join(['?']*len(misc_categories))
            ), 
            [guild_id] + misc_categories
        )
        # Remove contributions
        await conn.execute(
            'DELETE FROM contributions WHERE guild_id = ? AND category IN ({seq})'.format(
                seq=','.join(['?']*len(misc_categories))
            ), 
            [guild_id] + misc_categories
        )
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise e

async def setup(bot):
    await bot.add_cog(DatabaseManagement(bot))

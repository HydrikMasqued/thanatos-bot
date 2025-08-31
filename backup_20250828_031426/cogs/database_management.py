import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import aiosqlite
import json
import os

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
                      "• New contributions will start fresh\n"
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

class EditQuantityModal(discord.ui.Modal):
    def __init__(self, item_name: str, current_quantity: int, category: str, contribution_ids: List[int]):
        super().__init__(title=f"Edit Quantity: {item_name}")
        self.item_name = item_name
        self.current_quantity = current_quantity
        self.category = category
        self.contribution_ids = contribution_ids
        
        # New quantity input
        self.new_quantity = discord.ui.TextInput(
            label="New Total Quantity",
            placeholder=f"Current: {current_quantity}",
            max_length=10,
            required=True,
            default=str(current_quantity)
        )
        self.add_item(self.new_quantity)
        
        # Reason input
        self.reason = discord.ui.TextInput(
            label="Reason for Change",
            placeholder="e.g., 'Equipment lost in operation', 'Used in heist', 'Damaged'",
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
            # Validate new quantity
            new_qty = int(self.new_quantity.value)
            if new_qty < 0:
                raise ValueError("Quantity cannot be negative")
            
            # Get the bot instance
            bot = interaction.client
            
            # Calculate the difference
            difference = new_qty - self.current_quantity
            
            # Log the quantity change
            change_id = await bot.db.log_quantity_change(
                interaction.guild.id,
                self.item_name,
                self.category,
                self.current_quantity,
                new_qty,
                self.reason.value,
                self.notes.value,
                interaction.user.id
            )
            
            # Update the actual quantities in contributions
            await bot.db.update_item_quantities(
                interaction.guild.id,
                self.item_name,
                self.category,
                new_qty
            )
            
            # Create response embed
            embed = discord.Embed(
                title="✅ Quantity Updated Successfully",
                color=discord.Color.green() if difference >= 0 else discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Item Details",
                value=f"**Item:** {self.item_name}\n"
                      f"**Category:** {self.category}\n"
                      f"**Previous Quantity:** {self.current_quantity}\n"
                      f"**New Quantity:** {new_qty}\n"
                      f"**Change:** {'+' if difference >= 0 else ''}{difference}",
                inline=False
            )
            
            embed.add_field(
                name="Change Reason",
                value=self.reason.value,
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
                value=f"Change ID: {change_id}\n"
                      f"Modified by: {interaction.user.mention}\n"
                      f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Invalid Quantity",
                description="Please enter a valid positive number for quantity.",
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
        
        # Open edit modal
        modal = EditQuantityModal(
            item_name=selected_item['item_name'],
            current_quantity=selected_item['total_quantity'],
            category=selected_item['category'],
            contribution_ids=selected_item.get('contribution_ids', [])
        )
        await interaction.response.send_modal(modal)

class DatabaseManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
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
        """View all available archives"""
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
            
            embed = discord.Embed(
                title="📚 Database Archives",
                description=f"Found {len(archives)} archive(s)",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            for archive in archives[-10:]:  # Show last 10 archives
                created_date = datetime.fromisoformat(archive['created_at']).strftime('%Y-%m-%d %H:%M')
                
                field_value = f"**ID:** {archive['id']}\n"
                field_value += f"**Created:** {created_date}\n"
                field_value += f"**Description:** {archive['description']}\n"
                
                if archive['notes']:
                    field_value += f"**Notes:** {archive['notes'][:100]}...\n"
                
                # Get archive stats
                archive_data = json.loads(archive['archived_data'])
                field_value += f"**Stats:** {archive_data.get('total_contributions', 0)} contributions"
                
                embed.add_field(
                    name=f"📦 {archive['archive_name']}",
                    value=field_value,
                    inline=False
                )
            
            if len(archives) > 10:
                embed.set_footer(text=f"Showing 10 most recent archives out of {len(archives)} total")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
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
            # Get all contributions and aggregate by item
            contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
            
            if not contributions:
                embed = discord.Embed(
                    title="❌ No Items Found",
                    description="No contributions found in the database.",
                    color=discord.Color.red()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Aggregate items
            items = {}
            for contrib in contributions:
                key = f"{contrib['item_name']}|{contrib['category']}"
                if key not in items:
                    items[key] = {
                        'item_name': contrib['item_name'],
                        'category': contrib['category'],
                        'total_quantity': 0,
                        'contribution_ids': []
                    }
                items[key]['total_quantity'] += contrib['quantity']
                items[key]['contribution_ids'].append(contrib['id'])
            
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

async def setup(bot):
    await bot.add_cog(DatabaseManagement(bot))

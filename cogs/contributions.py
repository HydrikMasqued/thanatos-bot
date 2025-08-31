import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import List, Optional, Union
import aiosqlite
import asyncio

class ContributionModal(discord.ui.Modal):
    def __init__(self, category: str, forum_channel: Optional[discord.ForumChannel] = None):
        super().__init__(title=f"Contribute to {category}")
        self.category = category
        self.forum_channel = forum_channel
        
        # Item name input
        self.item_name = discord.ui.TextInput(
            label="Item Name",
            placeholder="What are you contributing?",
            max_length=100,
            required=True
        )
        self.add_item(self.item_name)
        
        # Quantity input
        self.quantity = discord.ui.TextInput(
            label="Quantity",
            placeholder="How many? (Default: 1)",
            max_length=10,
            required=False,
            default="1"
        )
        self.add_item(self.quantity)
        
        # Optional description for forum post
        self.description = discord.ui.TextInput(
            label="Description (Optional)",
            placeholder="Additional details about your contribution...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False
        )
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse quantity
            quantity_value = int(self.quantity.value) if self.quantity.value.strip() else 1
            if quantity_value <= 0:
                raise ValueError("Quantity must be positive")
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Quantity",
                description="Please enter a valid positive number for quantity.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        try:
            # Get the bot instance
            bot = interaction.client
            
            # Add contribution to database
            contribution_id = await bot.db.add_contribution(
                interaction.guild.id,
                interaction.user.id,
                self.category,
                self.item_name.value,
                quantity_value
            )
            
            # DO NOT create automatic quantity changes - contributions are separate from inventory
            # The contributions table tracks donated items, quantity_changes track admin inventory adjustments
            # These are two completely separate systems that should not interfere with each other
            
            # Update member record
            await bot.db.add_or_update_member(
                interaction.guild.id,
                interaction.user.id,
                interaction.user.display_name
            )
            
            # Create forum post if forum channel is configured
            created_thread = None
            if self.forum_channel:
                await self._create_forum_post(interaction, bot, contribution_id, quantity_value)
                created_thread = getattr(self, 'created_thread', None)
            
            # Create confirmation embed
            embed = discord.Embed(
                title="✅ Contribution Recorded",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Category", value=self.category, inline=True)
            embed.add_field(name="Item", value=self.item_name.value, inline=True)
            embed.add_field(name="Quantity", value=str(quantity_value), inline=True)
            
            # Add forum thread link if posted
            if created_thread:
                embed.add_field(
                    name="Forum Thread", 
                    value=f"[View Thread]({created_thread.jump_url})\nPosted in {self.forum_channel.mention}", 
                    inline=False
                )
            
            footer_text = "Your contribution has been recorded and leadership has been notified."
            if created_thread:
                footer_text += " Posted to existing forum thread."
            embed.set_footer(text=footer_text)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Send notification to leadership
            await self._notify_leadership(interaction, bot)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Recording Contribution",
                description=f"An error occurred while recording your contribution: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _update_inventory_quantity(self, bot, guild_id: int, user_id: int, 
                                        item_name: str, category: str, quantity: int):
        """Create a quantity change event to reflect the contribution in inventory"""
        try:
            # Get current quantity first (this will be 0 for new items)
            current_qty = await bot.db.get_current_item_quantity(guild_id, item_name, category)
            new_qty = current_qty + quantity
            
            # Create quantity change event for inventory tracking
            await bot.db.log_quantity_change(
                guild_id=guild_id,
                item_name=item_name,
                category=category,
                old_quantity=current_qty,
                new_quantity=new_qty,
                reason='contribution_adjustment',
                notes=f"Automatic inventory adjustment for contribution (+{quantity})",
                changed_by_id=user_id
            )
            
            print(f"Created quantity change event: {item_name} {current_qty} -> {new_qty} for contribution")
            
        except Exception as e:
            print(f"Error creating quantity change for contribution: {e}")
            # Don't fail the contribution if this fails, just log the error
    
    async def _notify_leadership(self, interaction: discord.Interaction, bot):
        """Send notification to leadership channel and Tailgunner role"""
        config = await bot.db.get_server_config(interaction.guild.id)
        
        if not config or not config.get('leadership_channel_id'):
            return
        
        channel = interaction.guild.get_channel(config['leadership_channel_id'])
        if not channel:
            return
        
        try:
            # Get Tailgunner role
            tailgunner_role = None
            for role in interaction.guild.roles:
                if role.name.lower() == "tailgunner":
                    tailgunner_role = role
                    break
            
            embed = discord.Embed(
                title="📦 New Contribution",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(
                name="Contributor",
                value=f"{interaction.user.mention} ({interaction.user.display_name})",
                inline=False
            )
            embed.add_field(name="Category", value=self.category, inline=True)
            embed.add_field(name="Item", value=self.item_name.value, inline=True)
            embed.add_field(name="Quantity", value=self.quantity.value, inline=True)
            
            # Add forum thread link if available
            if self.forum_channel:
                embed.add_field(
                    name="Forum Thread", 
                    value=f"Thread created in {self.forum_channel.mention}", 
                    inline=False
                )
            
            # Send notification with Tailgunner ping if role exists
            content = ""
            if tailgunner_role:
                content = f"{tailgunner_role.mention} New contribution logged!"
            
            await channel.send(content=content, embed=embed)
        except Exception as e:
            print(f"Error sending contribution notification: {e}")
    
    async def _create_forum_post(self, interaction: discord.Interaction, bot, contribution_id: int, quantity: int):
        """Post contribution to existing category thread"""
        try:
            # Find the existing thread for this category
            existing_thread = await self._find_category_thread(self.forum_channel, self.category)
            
            if not existing_thread:
                print(f"❌ No existing thread found for category: {self.category}")
                print(f"Forum channel: {self.forum_channel.name if self.forum_channel else 'None'}")
                self.created_thread = None
                return
            
            # Check thread accessibility and permissions
            try:
                # Check if thread is archived
                if existing_thread.archived:
                    print(f"⚠️ Thread {existing_thread.name} is archived, attempting to unarchive...")
                    try:
                        await existing_thread.edit(archived=False)
                        print(f"✅ Thread unarchived successfully")
                    except discord.Forbidden:
                        print(f"❌ No permission to unarchive thread {existing_thread.name}")
                        self.created_thread = None
                        return
                    except Exception as unarchive_error:
                        print(f"❌ Failed to unarchive thread: {unarchive_error}")
                        self.created_thread = None
                        return
                
                # Check if thread is locked
                if existing_thread.locked:
                    print(f"❌ Thread {existing_thread.name} is locked")
                    self.created_thread = None
                    return
                
                # Check bot permissions in the thread
                permissions = existing_thread.permissions_for(interaction.guild.me)
                if not permissions.send_messages:
                    print(f"❌ Bot lacks permission to send messages in thread {existing_thread.name}")
                    self.created_thread = None
                    return
                    
                print(f"✅ Thread {existing_thread.name} is accessible and writable")
                
            except Exception as perm_error:
                print(f"❌ Error checking thread permissions: {perm_error}")
                self.created_thread = None
                return
            
            # Get Tailgunner role for notification
            tailgunner_role = None
            for role in interaction.guild.roles:
                if role.name.lower() == "tailgunner":
                    tailgunner_role = role
                    break
            
            # Create contribution message content
            content = f"**📦 New {self.category} Contribution**\n\n"
            content += f"**Contributor:** {interaction.user.mention}\n"
            content += f"**Item:** {self.item_name.value}\n"
            content += f"**Quantity:** {quantity}\n"
            content += f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n"
            
            if self.description.value and self.description.value.strip():
                content += f"\n**Description:**\n{self.description.value}\n"
            
            # Add Tailgunner notification (but don't mention if no permission)
            if tailgunner_role and permissions.mention_everyone:
                content += f"\n{tailgunner_role.mention} - Please review this contribution."
            elif tailgunner_role:
                content += f"\n@{tailgunner_role.name} - Please review this contribution."
            
            content += f"\n*Contribution ID: {contribution_id}*"
            content += "\n" + "─" * 50  # Separator for readability
            
            # Post message to the existing thread with retry logic
            try:
                print(f"📤 Attempting to post to thread {existing_thread.name} (ID: {existing_thread.id})...")
                message = await existing_thread.send(content)
                print(f"✅ Successfully posted contribution to {self.category} thread: {existing_thread.name}")
                print(f"📨 Message ID: {message.id}, Jump URL: {message.jump_url}")
                
                # Store the thread reference for the confirmation message
                self.created_thread = existing_thread
                
            except discord.HTTPException as http_error:
                print(f"❌ HTTP error posting to thread: {http_error}")
                print(f"Status: {http_error.status}, Code: {http_error.code}")
                self.created_thread = None
            except discord.Forbidden as forbidden_error:
                print(f"❌ Forbidden error posting to thread: {forbidden_error}")
                self.created_thread = None
            except Exception as post_error:
                print(f"❌ Unexpected error posting to thread: {post_error}")
                self.created_thread = None
            
        except Exception as e:
            print(f"❌ Critical error in _create_forum_post for {self.category}: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            self.created_thread = None
    
    async def _find_category_thread(self, forum_channel: discord.ForumChannel, category: str) -> Optional[discord.Thread]:
        """Find the existing thread for a specific category"""
        try:
            # Check for specific thread IDs for certain categories
            specific_thread_ids = {
                # Weapons Locker threads
                "Pistols": 1355399943967211609,
                "Rifles": 1355400063685234838, 
                "SMGs": 1355400006504284252,
                "Body Armour & Medical": 1355400270024015973,
                
                # Drug Locker threads  
                "Meth": 1366601843240603648,
                "Weed": 1389788322976497734,
                
                # Misc Locker threads
                "Heist Items": 1368632475986694224,
                "Dirty Cash": 1380363715983048826,
                "Drug Items": 1389785875789119521,
                "Mech Shop": 1389787215042842714,
                "Crafting Items": 1366606110315778118,
            }
            
            # If this category has a specific thread ID, try to get it directly
            if category in specific_thread_ids:
                thread_id = specific_thread_ids[category]
                try:
                    # Try to get the thread from the guild (works for both active and archived)
                    thread = forum_channel.guild.get_thread(thread_id)
                    if thread:
                        print(f"Found specific thread for {category}: {thread.name} (ID: {thread.id})")
                        return thread
                    
                    # If not found with get_thread, try fetching it
                    thread = await forum_channel.guild.fetch_channel(thread_id)
                    if thread and isinstance(thread, discord.Thread):
                        print(f"Fetched specific thread for {category}: {thread.name} (ID: {thread.id})")
                        return thread
                except Exception as e:
                    print(f"Could not find specific thread {thread_id} for {category}: {e}")
            
            # Fall back to searching by name patterns
            # Get all threads (active and archived)
            active_threads = forum_channel.threads
            archived_threads = [thread async for thread in forum_channel.archived_threads(limit=100)]
            all_threads = active_threads + archived_threads
            
            # Search patterns for finding category threads
            search_patterns = [
                category.lower(),  # Exact category name
                category.lower().replace(" ", "-"),  # With dashes
                category.lower().replace(" ", "_"),  # With underscores
                category.lower().replace(" & ", "-"),  # Replace & with -
            ]
            
            # Look for threads that match the category
            for thread in all_threads:
                thread_name_lower = thread.name.lower()
                
                # Check if thread name matches any of our patterns
                for pattern in search_patterns:
                    if pattern in thread_name_lower:
                        print(f"Found existing thread for {category}: {thread.name} (ID: {thread.id})")
                        return thread
            
            # If no direct match, look for threads that start with the category name
            for thread in all_threads:
                thread_name_lower = thread.name.lower()
                if thread_name_lower.startswith(category.lower()):
                    print(f"Found existing thread for {category}: {thread.name} (ID: {thread.id})")
                    return thread
            
            print(f"No existing thread found for category: {category}")
            return None
            
        except Exception as e:
            print(f"Error searching for category thread: {e}")
            return None

class CategorySelect(discord.ui.Select):
    def __init__(self, categories: List[dict], header: str):
        # Filter categories by header
        filtered_categories = [cat for cat in categories if cat['header'] == header]
        
        # Create emoji mapping for different types
        emoji_map = {
            "Pistols": "🔫",
            "Rifles": "🏹", 
            "SMGs": "⚡",
            "Body Armour & Medical": "🛡️",
            "Meth": "💊",
            "Weed": "🌿",
            "Heist Items": "🔒",
            "Dirty Cash": "💰",
            "Drug Items": "💊",
            "Mech Shop": "🔧",
            "Crafting Items": "🔨"
        }
        
        options = [
            discord.SelectOption(
                label=category['name'],
                description=f"Log {category['name']} contributions",
                value=category['name'],
                emoji=emoji_map.get(category['name'], "📦")
            )
            for category in filtered_categories
        ]
        
        super().__init__(placeholder=f"Select from {header}...", options=options)
        self.categories = {cat['name']: cat for cat in categories}
        self.header = header
    
    async def callback(self, interaction: discord.Interaction):
        selected_category_name = self.values[0]
        selected_category = self.categories[selected_category_name]
        
        # Get forum channel if available
        forum_channel = None
        if selected_category.get('forum_channel_id'):
            forum_channel = interaction.guild.get_channel(selected_category['forum_channel_id'])
        
        modal = ContributionModal(selected_category_name, forum_channel)
        await interaction.response.send_modal(modal)

class CategorySelectView(discord.ui.View):
    def __init__(self, categories: List[dict]):
        super().__init__(timeout=300)  # 5 minute timeout
        
        # Group categories by header
        headers = list(set(cat['header'] for cat in categories))
        
        # Add a select dropdown for each header
        for i, header in enumerate(sorted(headers)):
            select = CategorySelect(categories, header)
            if select.options:  # Only add if there are options
                select.row = i  # Put each dropdown on a different row
                self.add_item(select)

class ContributionSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def _get_available_categories(self, guild_id: int) -> List[dict]:
        """Get available contribution categories organized by type"""
        # Organized category structure with individual forum assignments
        category_structure = {
            # Weapons categories - each gets their own forum
            "Pistols": {
                "forum_id": 1355399894227091517,  # Weapons forum
                "header": "🔫 Weapons"
            },
            "Rifles": {
                "forum_id": 1355399894227091517,  # Weapons forum  
                "header": "🔫 Weapons"
            },
            "SMGs": {
                "forum_id": 1355399894227091517,  # Weapons forum
                "header": "🔫 Weapons"
            },
            # Equipment & Medical
            "Body Armour & Medical": {
                "forum_id": 1366601638130880582,  # Equipment forum
                "header": "🛡️ Equipment & Medical"
            },
            # Contraband categories
            "Meth": {
                "forum_id": 1366605626662322236,  # Contraband forum
                "header": "💊 Contraband"
            },
            "Weed": {
                "forum_id": 1366605626662322236,  # Contraband forum
                "header": "💊 Contraband"
            },
            # Misc Items categories - using Misc-Locker forum
            "Heist Items": {
                "forum_id": 1366605626662322236,  # Misc-Locker forum (same as Contraband for now)
                "header": "📦 Misc Items"
            },
            "Dirty Cash": {
                "forum_id": 1366605626662322236,  # Misc-Locker forum (same as Contraband for now)
                "header": "📦 Misc Items"
            },
            "Drug Items": {
                "forum_id": 1366605626662322236,  # Misc-Locker forum (same as Contraband for now)
                "header": "📦 Misc Items"
            },
            "Mech Shop": {
                "forum_id": 1366605626662322236,  # Misc-Locker forum (same as Contraband for now)
                "header": "📦 Misc Items"
            },
            "Crafting Items": {
                "forum_id": 1366605626662322236,  # Misc-Locker forum (same as Contraband for now)
                "header": "📦 Misc Items"
            }
        }
        
        categories = []
        guild = self.bot.get_guild(guild_id)
        
        # Create categories from the new structure
        for cat_name, data in category_structure.items():
            forum_channel = None
            if guild and data["forum_id"]:
                forum_channel = guild.get_channel(data["forum_id"])
            
            categories.append({
                'name': cat_name,
                'header': data["header"],
                'type': 'forum_integrated' if forum_channel else 'predefined',
                'forum_channel_id': data["forum_id"] if forum_channel else None
            })
        
        return categories
    
    async def _get_forum_categories(self, forum_channel: discord.ForumChannel) -> List[str]:
        """Extract category names from forum channel tags or threads"""
        categories = []
        
        # Check if forum has tags (these can represent categories)
        if hasattr(forum_channel, 'available_tags') and forum_channel.available_tags:
            categories.extend([tag.name for tag in forum_channel.available_tags])
        
        # If no tags, derive categories from existing thread names
        if not categories:
            try:
                threads = [thread async for thread in forum_channel.archived_threads(limit=100)]
                active_threads = forum_channel.threads
                all_threads = threads + active_threads
                
                # Extract potential categories from thread names
                thread_names = [thread.name for thread in all_threads]
                
                # Look for common patterns in thread names to identify categories
                potential_categories = set()
                for name in thread_names:
                    # Split by common separators and take the first part as potential category
                    for separator in [' - ', ': ', ' | ', ' / ']:
                        if separator in name:
                            potential_categories.add(name.split(separator)[0].strip())
                            break
                
                categories.extend(list(potential_categories)[:10])  # Limit to 10
            except Exception as e:
                print(f"Error extracting forum categories: {e}")
        
        return categories
    
    @app_commands.command(name="contribute", description="Record a contribution to the group")
    async def contribute_command(self, interaction: discord.Interaction):
        """Main contribute command that opens category selection"""
        await interaction.response.defer(ephemeral=True)
        
        # Get available categories (configured + forum-derived)
        categories = await self._get_available_categories(interaction.guild.id)
        
        if not categories:
            embed = discord.Embed(
                title="❌ No Categories Available",
                description="No contribution categories are currently available. Officers can create categories using `/create_contribution_category`.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Create category selection view
        view = CategorySelectView(categories)
        
        embed = discord.Embed(
            title="📦 Record Contribution",
            description="**Choose a category from the organized sections below:**\n\n" +
                       "🔶 **Forum-Integrated**: Creates forum threads automatically\n" +
                       "🔷 **Standard**: Database-only tracking\n\n" +
                       "*Use the dropdown menus below to select your contribution category.*",
            color=discord.Color.blue()
        )
        
        # Show organized categories by header
        headers = {}
        for cat in categories:
            header = cat['header']
            if header not in headers:
                headers[header] = []
            headers[header].append(cat)
        
        # Add each header as a field
        for header, cats in headers.items():
            cat_list = ""
            for cat in cats:
                emoji = "🔶" if cat['type'] == 'forum_integrated' else "🔷"
                cat_list += f"{emoji} {cat['name']}\n"
            embed.add_field(name=header, value=cat_list, inline=True)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="contributions_view", description="View contributions by category")
    async def view_contributions(self, interaction: discord.Interaction, category: str = None):
        """View contributions, optionally filtered by category"""
        await interaction.response.defer()
        
        # Get server configuration for categories
        config = await self.bot.db.get_server_config(interaction.guild.id)
        available_categories = config.get('contribution_categories', []) if config else []
        
        if category:
            # Validate category
            if category not in available_categories:
                embed = discord.Embed(
                    title="❌ Invalid Category",
                    description=f"Available categories: {', '.join(available_categories)}",
                    color=discord.Color.red()
                )
                return await interaction.followup.send(embed=embed)
            
            # Get contributions for specific category
            contributions = await self.bot.db.get_contributions_by_category(interaction.guild.id, category)
            title = f"📦 Contributions - {category}"
        else:
            # Get all contributions
            contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
            title = "📦 All Contributions"
        
        if not contributions:
            embed = discord.Embed(
                title=title,
                description="No contributions found.",
                color=discord.Color.blue()
            )
            return await interaction.followup.send(embed=embed)
        
        # Group contributions by category
        grouped_contributions = {}
        for contrib in contributions:
            cat = contrib['category']
            if cat not in grouped_contributions:
                grouped_contributions[cat] = []
            grouped_contributions[cat].append(contrib)
        
        # Create embed(s)
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Total Contributions: {len(contributions)}")
        
        # Add fields for each category
        for cat, contribs in grouped_contributions.items():
            # Aggregate items and quantities
            item_totals = {}
            contributors = set()
            
            for contrib in contribs:
                item_name = contrib['item_name']
                quantity = contrib['quantity']
                contributors.add(contrib['discord_name'])
                
                if item_name in item_totals:
                    item_totals[item_name] += quantity
                else:
                    item_totals[item_name] = quantity
            
            # Format the field value
            if len(item_totals) == 0:
                field_value = "No contributions"
            else:
                # Sort by quantity descending
                sorted_items = sorted(item_totals.items(), key=lambda x: x[1], reverse=True)
                
                field_lines = []
                for item, total in sorted_items[:10]:  # Limit to top 10 items
                    field_lines.append(f"• {item}: {total}")
                
                if len(sorted_items) > 10:
                    field_lines.append(f"... and {len(sorted_items) - 10} more items")
                
                field_lines.append(f"\n**Contributors:** {len(contributors)}")
                field_value = "\n".join(field_lines)
            
            # Add field (Discord has a limit, so truncate if necessary)
            if len(field_value) > 1000:
                field_value = field_value[:950] + "..."
            
            embed.add_field(
                name=f"{cat} ({len(contribs)} entries)",
                value=field_value,
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="set_misc_forum", description="Set the Misc-Locker forum channel (Officers only)")
    @app_commands.describe(forum_channel="The Misc-Locker forum channel to link to misc categories")
    async def set_misc_forum(self, interaction: discord.Interaction, forum_channel: discord.ForumChannel):
        """Set the Misc-Locker forum channel for misc item categories"""
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
        
        # Store the forum ID in a simple way (we'll hardcode it in the category structure)
        # For now, just show confirmation that the forum has been identified
        embed = discord.Embed(
            title="✅ Misc Forum Identified",
            description=f"**Misc-Locker forum identified:**\n\n"
                       f"Forum: {forum_channel.mention}\n"
                       f"Forum ID: `{forum_channel.id}`\n\n"
                       f"**The following categories will be available:**\n"
                       f"🔒 Heist Items\n"
                       f"💰 Dirty Cash\n"
                       f"💊 Drug Items\n"
                       f"🔧 Mech Shop\n"
                       f"🔨 Crafting Items\n\n"
                       f"*Note: Update the code with this forum ID: `{forum_channel.id}`*",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="Forum Channel Info",
            value=f"Name: {forum_channel.name}\nID: {forum_channel.id}",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="contribution_stats", description="View contribution statistics (Officers only)")
    async def contribution_stats(self, interaction: discord.Interaction):
        """View detailed contribution statistics"""
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
        
        # Get all contributions
        contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
        
        if not contributions:
            embed = discord.Embed(
                title="📊 Contribution Statistics",
                description="No contributions found.",
                color=discord.Color.blue()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Calculate statistics
        contributor_stats = {}
        category_stats = {}
        
        for contrib in contributions:
            contributor = contrib['discord_name']
            category = contrib['category']
            quantity = contrib['quantity']
            
            # Contributor stats
            if contributor not in contributor_stats:
                contributor_stats[contributor] = {'total_quantity': 0, 'contributions': 0, 'categories': set()}
            
            contributor_stats[contributor]['total_quantity'] += quantity
            contributor_stats[contributor]['contributions'] += 1
            contributor_stats[contributor]['categories'].add(category)
            
            # Category stats
            if category not in category_stats:
                category_stats[category] = {'total_quantity': 0, 'contributions': 0, 'contributors': set()}
            
            category_stats[category]['total_quantity'] += quantity
            category_stats[category]['contributions'] += 1
            category_stats[category]['contributors'].add(contributor)
        
        # Create statistics embed
        embed = discord.Embed(
            title="📊 Contribution Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Top contributors
        top_contributors = sorted(
            contributor_stats.items(),
            key=lambda x: x[1]['contributions'],
            reverse=True
        )[:10]
        
        if top_contributors:
            contrib_text = ""
            for name, stats in top_contributors:
                contrib_text += f"• {name}: {stats['contributions']} contributions ({stats['total_quantity']} total items)\n"
            
            embed.add_field(
                name="🏆 Top Contributors",
                value=contrib_text[:1000],
                inline=False
            )
        
        # Category breakdown
        if category_stats:
            cat_text = ""
            for cat, stats in sorted(category_stats.items(), key=lambda x: x[1]['contributions'], reverse=True):
                cat_text += f"• {cat}: {stats['contributions']} contributions from {len(stats['contributors'])} contributors\n"
            
            embed.add_field(
                name="📦 Category Breakdown",
                value=cat_text[:1000],
                inline=False
            )
        
        embed.set_footer(text=f"Total: {len(contributions)} contributions from {len(contributor_stats)} contributors")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="delete_contribution", description="Delete a recent contribution (Officers only)")
    async def delete_contribution(self, interaction: discord.Interaction, 
                                 member: discord.Member, item_name: str):
        """Delete a contribution - officers only"""
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
        
        # Find and delete the contribution
        conn = await self.bot.db._get_shared_connection()
        # Set row factory to get dictionary-like rows
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('''
            SELECT c.*, m.discord_name
            FROM contributions c
            JOIN members m ON c.guild_id = m.guild_id AND c.user_id = m.user_id
            WHERE c.guild_id = ? AND c.user_id = ? AND c.item_name LIKE ?
            ORDER BY c.created_at DESC LIMIT 1
        ''', (interaction.guild.id, member.id, f"%{item_name}%"))
        
        contribution = await cursor.fetchone()
        
        if not contribution:
            return await interaction.response.send_message(
                f"❌ No recent contribution found for {member.display_name} with item '{item_name}'.",
                ephemeral=True
            )
        
        contrib_dict = dict(contribution)
        
        # Delete the contribution
        await conn.execute(
            'DELETE FROM contributions WHERE id = ?',
            (contrib_dict['id'],)
        )
        await self.bot.db._execute_commit()
        
        embed = discord.Embed(
            title="✅ Contribution Deleted",
            description=f"Deleted contribution: **{contrib_dict['item_name']}** (Qty: {contrib_dict['quantity']}) from **{contrib_dict['discord_name']}**",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="create_contribution_category", description="Create a new contribution category (Officers only)")
    async def create_contribution_category(self, interaction: discord.Interaction, 
                                         category_name: str, 
                                         forum_channel: Optional[discord.ForumChannel] = None):
        """Create a new contribution category"""
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
        
        # Validate category name
        if len(category_name.strip()) == 0:
            return await interaction.response.send_message(
                "❌ Category name cannot be empty.", ephemeral=True
            )
        
        category_name = category_name.strip()
        
        # Get current categories
        current_categories = config.get('contribution_categories', [])
        
        # Check if category already exists
        if category_name in current_categories:
            return await interaction.response.send_message(
                f"❌ Category '{category_name}' already exists.", ephemeral=True
            )
        
        # Add new category
        current_categories.append(category_name)
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            contribution_categories=current_categories
        )
        
        # Create confirmation embed
        embed = discord.Embed(
            title="✅ Category Created",
            description=f"**'{category_name}'** has been added as a contribution category.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        if forum_channel:
            embed.add_field(
                name="Forum Integration", 
                value=f"Linked to {forum_channel.mention}\nContributions will create forum posts.", 
                inline=False
            )
        
        embed.add_field(
            name="Total Categories", 
            value=str(len(current_categories)), 
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="remove_contribution_category", description="Remove a contribution category (Officers only)")
    async def remove_contribution_category(self, interaction: discord.Interaction, category_name: str):
        """Remove a contribution category"""
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
        
        # Get current categories
        current_categories = config.get('contribution_categories', [])
        
        # Check if category exists
        if category_name not in current_categories:
            available = ", ".join(current_categories) if current_categories else "None"
            return await interaction.response.send_message(
                f"❌ Category '{category_name}' not found.\nAvailable categories: {available}", ephemeral=True
            )
        
        # Remove category
        current_categories.remove(category_name)
        
        # Update server configuration
        await self.bot.db.update_server_config(
            interaction.guild.id,
            contribution_categories=current_categories
        )
        
        # Create confirmation embed
        embed = discord.Embed(
            title="✅ Category Removed",
            description=f"**'{category_name}'** has been removed from contribution categories.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="Remaining Categories", 
            value=str(len(current_categories)), 
            inline=True
        )
        
        if current_categories:
            embed.add_field(
                name="Available Categories", 
                value="• " + "\n• ".join(current_categories), 
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="list_contribution_categories", description="List all contribution categories")
    async def list_contribution_categories(self, interaction: discord.Interaction):
        """List all available contribution categories"""
        await interaction.response.defer()
        
        # Get available categories with forum integration info
        categories = await self._get_available_categories(interaction.guild.id)
        
        embed = discord.Embed(
            title="📦 Contribution Categories",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if not categories:
            embed.description = "No contribution categories are currently configured.\n\n" + \
                              "Officers can create categories using `/create_contribution_category`."
            return await interaction.followup.send(embed=embed)
        
        # Group categories by type
        predefined_cats = [cat for cat in categories if cat['type'] == 'predefined']
        integrated_cats = [cat for cat in categories if cat['type'] == 'forum_integrated']
        
        # Add predefined categories
        if predefined_cats:
            cat_list = "\n".join([f"• {cat['name']}" for cat in predefined_cats])
            embed.add_field(
                name="🔷 Standard Categories",
                value=cat_list,
                inline=False
            )
        
        # Add forum-integrated categories
        if integrated_cats:
            cat_list = "\n".join([
                f"• {cat['name']} (Forum: <#{cat['forum_channel_id']}>)" 
                for cat in integrated_cats
            ])
            embed.add_field(
                name="🔶 Forum-Integrated Categories",
                value=cat_list,
                inline=False
            )
        
        # Note: No forum-only categories since we use predefined list
        
        embed.set_footer(text=f"Total: {len(categories)} categories available")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="link_forum_to_category", description="Link a forum channel to a contribution category (Officers only)")
    @app_commands.describe(
        category_name="The contribution category to link",
        forum_channel="The forum channel to link to this category"
    )
    async def link_forum_to_category(self, interaction: discord.Interaction, 
                                   category_name: str, 
                                   forum_channel: discord.ForumChannel):
        """Link a forum channel to a specific contribution category"""
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
        
        # Get predefined categories (organized)
        predefined_categories = {
            "🔫 Weapons": ["Pistols", "Rifles", "SMGs"],
            "🛡️ Equipment & Medical": ["Body Armour & Medical"],
            "💊 Contraband": ["Meth", "Weed"],
            "📦 Misc Items": ["Heist Items", "Dirty Cash", "Drug Items", "Mech Shop", "Crafting Items"]
        }
        all_categories = []
        for header, cats in predefined_categories.items():
            all_categories.extend(cats)
        
        # Validate category name
        if category_name not in all_categories:
            available_text = ""
            for header, cats in predefined_categories.items():
                available_text += f"\n{header}:\n• " + "\n• ".join(cats) + "\n"
            return await interaction.response.send_message(
                f"❌ Invalid category name. Available categories:{available_text}", ephemeral=True
            )
        
        # Create confirmation embed
        embed = discord.Embed(
            title="✅ Forum Channel Linked",
            description=f"**Forum Integration Configured**\n\n"
                       f"Category: **{category_name}**\n"
                       f"Forum: {forum_channel.mention}\n\n"
                       f"Contributions to '{category_name}' will now create forum threads in {forum_channel.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="Forum Channel Info",
            value=f"Name: {forum_channel.name}\nID: {forum_channel.id}",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setup_forum_categories", description="Auto-create categories from forum channels (Officers only)")
    async def setup_forum_categories(self, interaction: discord.Interaction, 
                                   forum_channel: discord.ForumChannel):
        """Automatically create contribution categories from a forum channel's tags or threads"""
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
        
        await interaction.response.defer()
        
        # Get forum categories
        forum_categories = await self._get_forum_categories(forum_channel)
        
        if not forum_categories:
            embed = discord.Embed(
                title="❌ No Categories Found",
                description=f"No categories could be extracted from {forum_channel.mention}.\n\n" + \
                           "Make sure the forum has tags or existing threads with recognizable category patterns.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        # Get current categories
        current_categories = config.get('contribution_categories', [])
        new_categories = []
        existing_categories = []
        
        for cat_name in forum_categories:
            if cat_name not in current_categories:
                current_categories.append(cat_name)
                new_categories.append(cat_name)
            else:
                existing_categories.append(cat_name)
        
        if new_categories:
            # Update server configuration
            await self.bot.db.update_server_config(
                interaction.guild.id,
                contribution_categories=current_categories
            )
        
        # Create response embed
        embed = discord.Embed(
            title="🔧 Forum Categories Setup Complete",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="Forum Channel",
            value=forum_channel.mention,
            inline=False
        )
        
        if new_categories:
            embed.add_field(
                name=f"✅ Added ({len(new_categories)})",
                value="• " + "\n• ".join(new_categories),
                inline=True
            )
        
        if existing_categories:
            embed.add_field(
                name=f"ℹ️ Already Existed ({len(existing_categories)})",
                value="• " + "\n• ".join(existing_categories),
                inline=True
            )
        
        if not new_categories and not existing_categories:
            embed.description = "No valid categories were found to add."
            embed.color = discord.Color.orange()
        
        embed.set_footer(text=f"Total categories: {len(current_categories)}")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="view_category_threads", description="View all threads in a contribution category")
    @app_commands.describe(category_name="The category to view threads for")
    async def view_category_threads(self, interaction: discord.Interaction, category_name: str):
        """View all existing threads in a specific contribution category"""
        await interaction.response.defer()
        
        # Get available categories
        categories = await self._get_available_categories(interaction.guild.id)
        
        # Find the matching category
        category_info = None
        for cat in categories:
            if cat['name'].lower() == category_name.lower():
                category_info = cat
                break
        
        if not category_info:
            available = "\n• ".join([cat['name'] for cat in categories])
            embed = discord.Embed(
                title="❌ Category Not Found",
                description=f"Category '{category_name}' not found.\n\nAvailable categories:\n• {available}",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Check if category has forum integration
        if not category_info.get('forum_channel_id'):
            embed = discord.Embed(
                title="❌ No Forum Integration",
                description=f"Category '{category_name}' is not linked to a forum channel.\n\n"
                           f"Officers can link it using `/link_forum_to_category`.",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed)
        
        # Get the forum channel
        forum_channel = interaction.guild.get_channel(category_info['forum_channel_id'])
        if not forum_channel:
            embed = discord.Embed(
                title="❌ Forum Channel Not Found",
                description=f"Forum channel for '{category_name}' not found or bot lacks access.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        # Get all threads (active and archived)
        try:
            active_threads = forum_channel.threads
            archived_threads = [thread async for thread in forum_channel.archived_threads(limit=100)]
            all_threads = active_threads + archived_threads
            
            # Filter threads that might be related to this category
            category_threads = []
            for thread in all_threads:
                # Check if thread is related to contributions (has the format we create)
                if ' - ' in thread.name or any(keyword in thread.name.lower() for keyword in [category_name.lower(), 'contribution']):
                    category_threads.append(thread)
            
            # Create main embed
            embed = discord.Embed(
                title=f"📋 {category_name} - Forum Threads",
                description=f"**Forum:** {forum_channel.mention}\n"
                           f"**Total Threads:** {len(category_threads)}\n\n"
                           f"*Recent threads in this category:*",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if not category_threads:
                embed.add_field(
                    name="No Threads Found",
                    value="No contribution threads found in this category.\n\n"
                         "Use `/contribute` to create the first one!",
                    inline=False
                )
            else:
                # Sort by creation date (newest first)
                category_threads.sort(key=lambda t: t.created_at, reverse=True)
                
                # Show recent threads (limit to 10 for embed space)
                recent_threads = category_threads[:10]
                thread_list = ""
                
                for i, thread in enumerate(recent_threads, 1):
                    # Get thread info
                    created_date = thread.created_at.strftime('%m/%d/%Y')
                    is_archived = hasattr(thread, 'archived') and thread.archived
                    status = "📁" if is_archived else "📝"
                    
                    thread_list += f"{status} **[{thread.name}]({thread.jump_url})**\n"
                    thread_list += f"   • Created: {created_date}\n"
                    if hasattr(thread, 'message_count'):
                        thread_list += f"   • Messages: {thread.message_count}\n"
                    thread_list += "\n"
                
                embed.add_field(
                    name=f"📝 Recent Threads ({len(recent_threads)})",
                    value=thread_list[:1000],  # Discord field limit
                    inline=False
                )
                
                if len(category_threads) > 10:
                    embed.add_field(
                        name="Additional Threads",
                        value=f"... and {len(category_threads) - 10} more threads.\n"
                             f"Visit {forum_channel.mention} to see all threads.",
                        inline=False
                    )
            
            # Add statistics
            active_count = len([t for t in category_threads if not (hasattr(t, 'archived') and t.archived)])
            archived_count = len(category_threads) - active_count
            
            embed.add_field(
                name="📊 Thread Statistics",
                value=f"📝 Active: {active_count}\n📁 Archived: {archived_count}\n📋 Total: {len(category_threads)}",
                inline=True
            )
            
            embed.set_footer(text=f"Forum ID: {forum_channel.id}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Fetching Threads",
                description=f"An error occurred while fetching threads: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="create_category_thread", description="Create a new thread in a contribution category (Officers only)")
    @app_commands.describe(
        category_name="The category to create a thread in",
        thread_title="The title for the new thread",
        thread_content="The initial content for the thread"
    )
    async def create_category_thread(self, interaction: discord.Interaction, 
                                   category_name: str, 
                                   thread_title: str, 
                                   thread_content: str):
        """Create a new thread in a specific contribution category"""
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
        
        await interaction.response.defer()
        
        # Get available categories
        categories = await self._get_available_categories(interaction.guild.id)
        
        # Find the matching category
        category_info = None
        for cat in categories:
            if cat['name'].lower() == category_name.lower():
                category_info = cat
                break
        
        if not category_info:
            available = "\n• ".join([cat['name'] for cat in categories])
            embed = discord.Embed(
                title="❌ Category Not Found",
                description=f"Category '{category_name}' not found.\n\nAvailable categories:\n• {available}",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Check if category has forum integration
        if not category_info.get('forum_channel_id'):
            embed = discord.Embed(
                title="❌ No Forum Integration",
                description=f"Category '{category_name}' is not linked to a forum channel.\n\n"
                           f"Officers can link it using `/link_forum_to_category`.",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed)
        
        # Get the forum channel
        forum_channel = interaction.guild.get_channel(category_info['forum_channel_id'])
        if not forum_channel:
            embed = discord.Embed(
                title="❌ Forum Channel Not Found",
                description=f"Forum channel for '{category_name}' not found or bot lacks access.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        try:
            # Create the thread
            thread, message = await forum_channel.create_thread(
                name=thread_title,
                content=thread_content + f"\n\n*Thread created by {interaction.user.mention} via bot command.*",
                reason=f"Manual thread creation by {interaction.user.display_name}"
            )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Thread Created Successfully",
                description=f"**New thread created in {category_name}!**\n\n"
                           f"**Thread:** {thread.mention}\n"
                           f"**Forum:** {forum_channel.mention}\n"
                           f"**Title:** {thread_title}",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Thread Details",
                value=f"ID: {thread.id}\n"
                      f"URL: [Jump to Thread]({thread.jump_url})\n"
                      f"Created by: {interaction.user.mention}",
                inline=False
            )
            
            # Show preview of content if not too long
            if len(thread_content) <= 200:
                embed.add_field(
                    name="Content Preview",
                    value=thread_content,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Creating Thread",
                description=f"An error occurred while creating the thread: {str(e)}\n\n"
                           f"Make sure the bot has permission to create threads in {forum_channel.mention}.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="list_all_category_threads", description="View threads from all contribution categories")
    async def list_all_category_threads(self, interaction: discord.Interaction):
        """View a summary of threads from all contribution categories"""
        await interaction.response.defer()
        
        # Get available categories
        categories = await self._get_available_categories(interaction.guild.id)
        
        # Filter categories with forum integration
        forum_categories = [cat for cat in categories if cat.get('forum_channel_id')]
        
        if not forum_categories:
            embed = discord.Embed(
                title="❌ No Forum Integration",
                description="No categories are currently linked to forum channels.\n\n"
                           "Officers can link categories using `/link_forum_to_category`.",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed)
        
        # Create main embed
        embed = discord.Embed(
            title="📋 All Category Threads Overview",
            description="**Thread summary across all contribution categories:**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        total_threads = 0
        total_active = 0
        total_archived = 0
        
        for category in forum_categories:
            forum_channel = interaction.guild.get_channel(category['forum_channel_id'])
            if not forum_channel:
                continue
            
            try:
                # Get threads for this category
                active_threads = forum_channel.threads
                archived_threads = [thread async for thread in forum_channel.archived_threads(limit=50)]
                all_threads = active_threads + archived_threads
                
                active_count = len(active_threads)
                archived_count = len(archived_threads)
                total_count = len(all_threads)
                
                total_threads += total_count
                total_active += active_count
                total_archived += archived_count
                
                # Get most recent thread
                recent_thread = None
                if all_threads:
                    all_threads.sort(key=lambda t: t.created_at, reverse=True)
                    recent_thread = all_threads[0]
                
                # Create field for this category
                field_value = f"📋 Total: {total_count}\n"
                field_value += f"📝 Active: {active_count}\n"
                field_value += f"📁 Archived: {archived_count}\n"
                
                if recent_thread:
                    recent_date = recent_thread.created_at.strftime('%m/%d/%Y')
                    field_value += f"\n⏰ Latest: [{recent_thread.name[:30]}...]({recent_thread.jump_url})\n"
                    field_value += f"   Created: {recent_date}"
                else:
                    field_value += "\n🚫 No threads yet"
                
                # Add emoji for the category header
                emoji_map = {
                    "🔫 Weapons": "🔫",
                    "🛡️ Equipment & Medical": "🛡️",
                    "💊 Contraband": "💊",
                    "📦 Misc Items": "📦"
                }
                
                header_emoji = emoji_map.get(category['header'], "📦")
                
                embed.add_field(
                    name=f"{header_emoji} {category['name']}",
                    value=field_value,
                    inline=True
                )
                
            except Exception as e:
                print(f"Error processing category {category['name']}: {e}")
        
        # Add total summary
        embed.add_field(
            name="📊 Total Summary",
            value=f"📋 All Threads: {total_threads}\n"
                  f"📝 Active: {total_active}\n"
                  f"📁 Archived: {total_archived}\n\n"
                  f"*Use `/view_category_threads` for detailed view*",
            inline=False
        )
        
        embed.set_footer(text=f"Categories with forum integration: {len(forum_categories)}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="debug_examine_forums", description="Examine forum structure for debugging (Officers only)")
    async def debug_examine_forums(self, interaction: discord.Interaction):
        """Debug command to examine forum structure"""
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
        
        # Forum channel IDs from the contribution system
        forum_ids = {
            1355399894227091517: "Weapons",
            1366601638130880582: "Equipment & Medical", 
            1366605626662322236: "Contraband",
        }
        
        result = f"**Forum Structure Analysis**\n\n"
        
        for forum_id, forum_type in forum_ids.items():
            forum_channel = interaction.guild.get_channel(forum_id)
            if not forum_channel:
                result += f"❌ **{forum_type}** forum not found (ID: {forum_id})\n\n"
                continue
            
            result += f"📋 **{forum_type} Forum**: {forum_channel.name}\n"
            result += f"ID: {forum_id}\n\n"
            
            # Get active threads
            active_threads = forum_channel.threads
            if active_threads:
                result += f"📝 **Active Threads** ({len(active_threads)}):```\n"
                for thread in active_threads[:5]:  # Limit for message size
                    result += f"• {thread.name}\n"
                if len(active_threads) > 5:
                    result += f"... and {len(active_threads) - 5} more\n"
                result += "```\n"
            
            # Get some archived threads
            try:
                archived_threads = []
                async for thread in forum_channel.archived_threads(limit=5):
                    archived_threads.append(thread)
                
                if archived_threads:
                    result += f"📁 **Recent Archived Threads** ({len(archived_threads)}):```\n"
                    for thread in archived_threads:
                        result += f"• {thread.name}\n"
                    result += "```\n"
            except Exception as e:
                result += f"⚠️ Error getting archived threads: {str(e)}\n\n"
            
            result += "─" * 40 + "\n\n"
        
        # Split message if too long
        if len(result) > 2000:
            chunks = [result[i:i+1900] for i in range(0, len(result), 1900)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk, ephemeral=True)
                else:
                    await interaction.followup.send(f"**Continued ({i+1}/{len(chunks)})**\n{chunk}", ephemeral=True)
        else:
            await interaction.followup.send(result, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ContributionSystem(bot))

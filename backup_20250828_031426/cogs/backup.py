import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import io
import zipfile
import os

class BackupSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def _has_admin_permissions(self, member: discord.Member) -> bool:
        """Check if member has administrator permissions"""
        return member.guild_permissions.administrator
    
    @app_commands.command(name="export_data", description="Export all server data (Admin only)")
    async def export_data(self, interaction: discord.Interaction, format_type: str = "json"):
        """Export all server data to JSON or text format"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Export guild data
            guild_data = await self.bot.db.export_guild_data(interaction.guild.id)
            
            if format_type.lower() == "json":
                # Create JSON file
                json_content = json.dumps(guild_data, indent=2, default=str)
                file_content = io.StringIO(json_content)
                filename = f"thanatos_export_{interaction.guild.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                file = discord.File(file_content, filename=filename)
                
                await interaction.followup.send(
                    content="📥 **Data Export Complete** (JSON Format)",
                    file=file,
                    ephemeral=True
                )
            
            elif format_type.lower() == "text":
                # Create human-readable text format
                text_content = await self._format_data_as_text(guild_data)
                file_content = io.StringIO(text_content)
                filename = f"thanatos_export_{interaction.guild.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                file = discord.File(file_content, filename=filename)
                
                await interaction.followup.send(
                    content="📥 **Data Export Complete** (Text Format)",
                    file=file,
                    ephemeral=True
                )
            
            elif format_type.lower() == "both":
                # Create both formats in a ZIP file
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    # Add JSON file
                    json_content = json.dumps(guild_data, indent=2, default=str)
                    zip_file.writestr(f"thanatos_data.json", json_content)
                    
                    # Add text file
                    text_content = await self._format_data_as_text(guild_data)
                    zip_file.writestr(f"thanatos_data.txt", text_content)
                    
                    # Add membership list
                    members = guild_data.get('members', [])
                    if members:
                        # Group members by rank for membership list
                        grouped_members = {}
                        for member in members:
                            rank = member.get('rank', 'Unknown')
                            if rank not in grouped_members:
                                grouped_members[rank] = []
                            grouped_members[rank].append(member)
                        
                        # Generate membership list
                        membership_content = await self._generate_membership_text(grouped_members)
                        zip_file.writestr(f"membership_list.txt", membership_content)
                
                zip_buffer.seek(0)
                filename = f"thanatos_backup_{interaction.guild.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                file = discord.File(zip_buffer, filename=filename)
                
                await interaction.followup.send(
                    content="📥 **Complete Data Backup** (ZIP Archive with JSON, Text, and Membership List)",
                    file=file,
                    ephemeral=True
                )
            
            else:
                await interaction.followup.send(
                    "❌ Invalid format. Use 'json', 'text', or 'both'.",
                    ephemeral=True
                )
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Export Error",
                description=f"An error occurred while exporting data: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _format_data_as_text(self, guild_data: dict) -> str:
        """Format guild data as human-readable text"""
        lines = []
        lines.append("=" * 80)
        lines.append("THANATOS BOT - DATA EXPORT")
        lines.append(f"Export Date: {guild_data.get('export_timestamp', 'Unknown')}")
        lines.append(f"Guild ID: {guild_data.get('guild_id', 'Unknown')}")
        lines.append("=" * 80)
        lines.append("")
        
        # Server Configuration
        lines.append("SERVER CONFIGURATION")
        lines.append("-" * 30)
        config = guild_data.get('server_config', {})
        
        if config:
            lines.append(f"Officer Role ID: {config.get('officer_role_id', 'Not set')}")
            lines.append(f"Notification Channel ID: {config.get('notification_channel_id', 'Not set')}")
            lines.append(f"Leadership Channel ID: {config.get('leadership_channel_id', 'Not set')}")
            # Get DM users (handle both old and new format)
            dm_users = config.get('dm_users')
            if dm_users:
                try:
                    import json
                    dm_user_list = json.loads(dm_users) if isinstance(dm_users, str) else dm_users
                    lines.append(f"DM Users ({len(dm_user_list)}): {', '.join(map(str, dm_user_list))}")
                except:
                    lines.append(f"DM Users: {dm_users}")
            elif config.get('dm_user_id'):
                lines.append(f"DM User ID (legacy): {config.get('dm_user_id')}")
            else:
                lines.append("DM Users: Not set")
            
            membership_roles = config.get('membership_roles', [])
            lines.append(f"Membership Roles ({len(membership_roles)}):")
            for role in membership_roles:
                lines.append(f"  - {role}")
            
            contribution_categories = config.get('contribution_categories', [])
            lines.append(f"Contribution Categories ({len(contribution_categories)}):")
            for category in contribution_categories:
                lines.append(f"  - {category}")
        else:
            lines.append("No configuration found")
        
        lines.append("")
        
        # Members
        lines.append("MEMBERS")
        lines.append("-" * 30)
        members = guild_data.get('members', [])
        
        if members:
            lines.append(f"Total Members: {len(members)}")
            lines.append("")
            lines.append(f"{'Name':<25} {'Rank':<20} {'LOA Status':<15} {'Last Updated'}")
            lines.append("-" * 80)
            
            for member in sorted(members, key=lambda x: (x.get('rank', ''), x.get('discord_name', ''))):
                name = member.get('discord_name', 'Unknown')
                rank = member.get('rank', 'Unknown')
                loa_status = "On LOA" if member.get('is_on_loa') else "Active"
                updated = member.get('updated_at', 'Unknown')
                
                lines.append(f"{name:<25} {rank:<20} {loa_status:<15} {updated}")
        else:
            lines.append("No members found")
        
        lines.append("")
        
        # LOA Records
        lines.append("LOA RECORDS")
        lines.append("-" * 30)
        loa_records = guild_data.get('loa_records', [])
        
        if loa_records:
            lines.append(f"Total LOA Records: {len(loa_records)}")
            lines.append("")
            
            active_loas = [loa for loa in loa_records if loa.get('is_active')]
            expired_loas = [loa for loa in loa_records if loa.get('is_expired')]
            inactive_loas = [loa for loa in loa_records if not loa.get('is_active')]
            
            lines.append(f"Active LOAs: {len(active_loas)}")
            lines.append(f"Expired LOAs: {len(expired_loas)}")
            lines.append(f"Completed LOAs: {len(inactive_loas)}")
            lines.append("")
            
            # Show recent LOAs
            recent_loas = sorted(loa_records, key=lambda x: x.get('created_at', ''), reverse=True)[:10]
            lines.append("Recent LOA Records (Last 10):")
            lines.append(f"{'User ID':<15} {'Duration':<15} {'Status':<10} {'Start Date':<20} {'End Date'}")
            lines.append("-" * 80)
            
            for loa in recent_loas:
                user_id = str(loa.get('user_id', 'Unknown'))
                duration = loa.get('duration', 'Unknown')
                status = 'Active' if loa.get('is_active') else ('Expired' if loa.get('is_expired') else 'Completed')
                start_date = loa.get('start_time', 'Unknown')[:10] if loa.get('start_time') else 'Unknown'
                end_date = loa.get('end_time', 'Unknown')[:10] if loa.get('end_time') else 'Unknown'
                
                lines.append(f"{user_id:<15} {duration:<15} {status:<10} {start_date:<20} {end_date}")
        else:
            lines.append("No LOA records found")
        
        lines.append("")
        
        # Contributions
        lines.append("CONTRIBUTIONS")
        lines.append("-" * 30)
        contributions = guild_data.get('contributions', [])
        
        if contributions:
            lines.append(f"Total Contributions: {len(contributions)}")
            lines.append("")
            
            # Group by category
            categories = {}
            for contrib in contributions:
                category = contrib.get('category', 'Unknown')
                if category not in categories:
                    categories[category] = []
                categories[category].append(contrib)
            
            for category, contribs in categories.items():
                lines.append(f"{category} ({len(contribs)} contributions):")
                
                # Aggregate items
                items = {}
                contributors = set()
                for contrib in contribs:
                    item_name = contrib.get('item_name', 'Unknown')
                    quantity = contrib.get('quantity', 1)
                    contributor = contrib.get('discord_name', 'Unknown')
                    
                    contributors.add(contributor)
                    if item_name in items:
                        items[item_name] += quantity
                    else:
                        items[item_name] = quantity
                
                # Show top items
                sorted_items = sorted(items.items(), key=lambda x: x[1], reverse=True)
                for item, total in sorted_items[:5]:  # Top 5 items per category
                    lines.append(f"  - {item}: {total}")
                
                if len(sorted_items) > 5:
                    lines.append(f"  ... and {len(sorted_items) - 5} more items")
                
                lines.append(f"  Contributors: {len(contributors)}")
                lines.append("")
        else:
            lines.append("No contributions found")
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF EXPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    async def _generate_membership_text(self, grouped_members: dict) -> str:
        """Generate membership list text (similar to membership.py)"""
        content = []
        content.append("=" * 80)
        content.append("THANATOS MC - MEMBERSHIP LIST")
        content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("=" * 80)
        content.append("")
        
        # Header
        content.append(f"{'Rank':<20} {'Name':<25} {'Discord':<20} {'LOA':<10}")
        content.append("-" * 80)
        
        # Three Heads section
        content.append("")
        content.append("THREE HEADS")
        content.append("-" * 20)
        
        for rank in ["President", "Vice President", "Sergeant At Arms"]:
            if rank in grouped_members:
                for member in grouped_members[rank]:
                    loa_status = "X" if member.get('is_on_loa') else "O"
                    content.append(f"{rank:<20} {member['discord_name']:<25} {'N/A':<20} {loa_status:<10}")
        
        # Chapter Council section
        content.append("")
        content.append("CHAPTER COUNCIL")
        content.append("-" * 20)
        
        for rank in ["Secretary", "Treasurer", "Road Captain", "Tailgunner", "Enforcer"]:
            if rank in grouped_members:
                for member in grouped_members[rank]:
                    loa_status = "X" if member.get('is_on_loa') else "O"
                    content.append(f"{rank:<20} {member['discord_name']:<25} {'N/A':<20} {loa_status:<10}")
        
        # Full Patch/Nomad section
        content.append("")
        content.append("FULL PATCH/NOMAD")
        content.append("-" * 20)
        
        for rank in ["Full Patch", "Full Patch/Nomad"]:
            if rank in grouped_members:
                for member in grouped_members[rank]:
                    loa_status = "X" if member.get('is_on_loa') else "O"
                    content.append(f"{rank:<20} {member['discord_name']:<25} {'N/A':<20} {loa_status:<10}")
        
        # Any other ranks
        other_ranks = [rank for rank in grouped_members.keys() 
                      if rank not in ["President", "Vice President", "Sergeant At Arms", 
                                     "Secretary", "Treasurer", "Road Captain", "Tailgunner", 
                                     "Enforcer", "Full Patch", "Full Patch/Nomad"]]
        
        if other_ranks:
            content.append("")
            content.append("OTHER RANKS")
            content.append("-" * 20)
            
            for rank in other_ranks:
                for member in grouped_members[rank]:
                    loa_status = "X" if member.get('is_on_loa') else "O"
                    content.append(f"{rank:<20} {member['discord_name']:<25} {'N/A':<20} {loa_status:<10}")
        
        content.append("")
        content.append("=" * 80)
        content.append("LEGEND: X = On LOA, O = Active")
        content.append("=" * 80)
        
        return "\n".join(content)
    
    @app_commands.command(name="backup_database", description="Create a complete database backup (Admin only)")
    async def backup_database(self, interaction: discord.Interaction):
        """Create a complete backup of the bot's database file"""
        if not self._has_admin_permissions(interaction.user):
            return await interaction.response.send_message(
                "❌ This command requires administrator permissions.", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if database file exists
            db_path = self.bot.db.db_path
            if not os.path.exists(db_path):
                await interaction.followup.send(
                    "❌ Database file not found.", ephemeral=True
                )
                return
            
            # Read and send database file
            with open(db_path, 'rb') as db_file:
                file_content = io.BytesIO(db_file.read())
            
            filename = f"thanatos_database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            file = discord.File(file_content, filename=filename)
            
            embed = discord.Embed(
                title="💾 Database Backup Complete",
                description=f"Complete SQLite database backup created.\n\n"
                           f"**File:** {filename}\n"
                           f"**Size:** {len(file_content.getvalue())} bytes\n\n"
                           f"⚠️ **Warning:** This file contains all bot data. Keep it secure!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            await interaction.followup.send(
                embed=embed,
                file=file,
                ephemeral=True
            )
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Backup Error",
                description=f"An error occurred while creating database backup: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="data_summary", description="View a summary of server data")
    async def data_summary(self, interaction: discord.Interaction):
        """Display a summary of server data"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get data counts
            members = await self.bot.db.get_all_members(interaction.guild.id)
            contributions = await self.bot.db.get_all_contributions(interaction.guild.id)
            
            # Get LOA counts
            conn = await self.bot.db._get_shared_connection()
            # Active LOAs
            cursor = await conn.execute(
                'SELECT COUNT(*) FROM loa_records WHERE guild_id = ? AND is_active = TRUE AND is_expired = FALSE',
                (interaction.guild.id,)
            )
            active_loas = (await cursor.fetchone())[0]
            
            # Total LOA records
            cursor = await conn.execute(
                'SELECT COUNT(*) FROM loa_records WHERE guild_id = ?',
                (interaction.guild.id,)
            )
            total_loa_records = (await cursor.fetchone())[0]
            
            # Create summary embed
            embed = discord.Embed(
                title="📊 Data Summary",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Basic stats
            embed.add_field(name="👥 Total Members", value=str(len(members)), inline=True)
            embed.add_field(name="📋 Active LOAs", value=str(active_loas), inline=True)
            embed.add_field(name="📦 Total Contributions", value=str(len(contributions)), inline=True)
            
            # More detailed stats
            embed.add_field(name="📜 Total LOA Records", value=str(total_loa_records), inline=True)
            
            # Member breakdown by LOA status
            active_members = len([m for m in members if not m.get('is_on_loa')])
            loa_members = len([m for m in members if m.get('is_on_loa')])
            embed.add_field(name="🟢 Active Members", value=str(active_members), inline=True)
            embed.add_field(name="🔴 Members on LOA", value=str(loa_members), inline=True)
            
            # Contribution breakdown
            if contributions:
                categories = {}
                contributors = set()
                
                for contrib in contributions:
                    category = contrib.get('category', 'Unknown')
                    categories[category] = categories.get(category, 0) + 1
                    contributors.add(contrib.get('discord_name', 'Unknown'))
                
                embed.add_field(name="📦 Contribution Categories", value=str(len(categories)), inline=True)
                embed.add_field(name="👤 Unique Contributors", value=str(len(contributors)), inline=True)
                
                # Top category
                if categories:
                    top_category = max(categories.items(), key=lambda x: x[1])
                    embed.add_field(name="🏆 Top Category", value=f"{top_category[0]} ({top_category[1]})", inline=True)
            else:
                embed.add_field(name="📦 Contribution Categories", value="0", inline=True)
                embed.add_field(name="👤 Unique Contributors", value="0", inline=True)
                embed.add_field(name="🏆 Top Category", value="None", inline=True)
            
            embed.set_footer(text=f"Server ID: {interaction.guild.id}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while generating data summary: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BackupSystem(bot))

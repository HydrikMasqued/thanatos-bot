import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import io
import logging
from typing import List, Dict

# Set up logger for this module
logger = logging.getLogger(__name__)

class MembershipSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Default motorcycle club hierarchy (can be customized per server)
        self.default_rank_order = {
            "President": 1,
            "Vice President": 2, 
            "Sergeant At Arms": 3,
            "Secretary": 4,
            "Treasurer": 5,
            "Road Captain": 6,
            "Tailgunner": 7,
            "Enforcer": 8,
            "Full Patch": 9,
            "Nomad": 10
        }
        
        # Role name variations for flexible matching
        self.role_variations = {
            "President": ["President", "PRESIDENT", "president"],
            "Vice President": ["Vice President", "VICE PRESIDENT", "vice president", "VP", "V.P."],
            "Sergeant At Arms": ["Sergeant At Arms", "Sergeant at Arms", "SERGEANT AT ARMS", "sergeant at arms", "SGT At Arms", "Sgt at Arms"],
            "Secretary": ["Secretary", "SECRETARY", "secretary"],
            "Treasurer": ["Treasurer", "TREASURER", "treasurer"],
            "Road Captain": ["Road Captain", "ROAD CAPTAIN", "road captain"],
            "Tailgunner": ["Tailgunner", "TAILGUNNER", "tailgunner", "Tail Gunner"],
            "Enforcer": ["Enforcer", "ENFORCER", "enforcer"],
            "Full Patch": ["Full Patch", "FULL PATCH", "full patch"],
            "Nomad": ["Nomad", "NOMAD", "nomad"]
        }
        
    def _find_role_match(self, discord_role_name: str) -> str:
        """Find matching canonical role name from Discord role name variations"""
        for canonical_name, variations in self.role_variations.items():
            if discord_role_name in variations:
                return canonical_name
        return None
        
    def _get_all_role_variations(self) -> list:
        """Get all possible role name variations for configuration"""
        all_variations = []
        for variations in self.role_variations.values():
            all_variations.extend(variations)
        return all_variations
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Update member database when roles change"""
        if before.roles != after.roles:
            await self._update_member_from_roles(after)
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Add new member to database"""
        await self._update_member_from_roles(member)
    
    async def _update_member_from_roles(self, member: discord.Member):
        """Update member record based on their Discord roles"""
        if member.bot:  # Skip bots
            return
            
        try:
            config = await self.bot.db.get_server_config(member.guild.id)
            if not config or not config.get('membership_roles'):
                return
            
            # Find the highest ranking role
            member_rank = None
            highest_rank_order = float('inf')
            
            for role in member.roles:
                if role.name in config['membership_roles']:
                    rank_order = self.default_rank_order.get(role.name, 999)
                    if rank_order < highest_rank_order:
                        highest_rank_order = rank_order
                        member_rank = role.name
            
            # Determine member status
            status = 'Active'
            if member_rank:
                # Check if member has LOA status
                existing_member = await self.bot.db.get_member(member.guild.id, member.id)
                if existing_member and existing_member.get('is_on_loa'):
                    status = 'LOA'
                
                # Update member in database with username
                discord_username = member.name  # This is the actual username (e.g., user123)
                await self.bot.db.add_or_update_member(
                    member.guild.id,
                    member.id,
                    member.display_name,  # Display name (e.g., "John Doe")
                    member_rank,
                    discord_username,  # Actual username (e.g., "johndoe123")
                    status
                )
        except Exception as e:
            logger.error(f"Error updating member from roles for {member.display_name} (ID: {member.id}): {e}")
    
    @app_commands.command(name="membership_sync", description="Sync all members with their Discord roles (Officers only)")
    async def sync_membership(self, interaction: discord.Interaction):
        """Manually sync all server members with their roles"""
        await interaction.response.defer(ephemeral=True)
        
        # Get server configuration
        config = await self.bot.db.get_server_config(interaction.guild.id)
        
        # Auto-initialize membership roles if not configured
        membership_roles = []
        if config and config.get('membership_roles'):
            membership_roles = config['membership_roles']
        else:
            # Use default membership roles and auto-configure
            membership_roles = list(self.default_rank_order.keys())
            await self.bot.db.update_server_config(
                interaction.guild.id,
                membership_roles=membership_roles
            )
            await interaction.followup.send(
                f"✅ Auto-configured membership roles: {', '.join(membership_roles)}",
                ephemeral=True
            )
            # Wait a moment then continue
            import asyncio
            await asyncio.sleep(0.5)
        
        synced_count = 0
        
        # Sync all guild members
        for member in interaction.guild.members:
            if member.bot:  # Skip bots
                continue
            
            # Find member's highest ranking role
            member_rank = None
            highest_rank_order = float('inf')
            
            for role in member.roles:
                # Try exact match first, then flexible match
                canonical_role = None
                if role.name in membership_roles:
                    canonical_role = role.name
                else:
                    # Try flexible matching for role variations
                    canonical_role = self._find_role_match(role.name)
                    
                if canonical_role:
                    rank_order = self.default_rank_order.get(canonical_role, 999)
                    if rank_order < highest_rank_order:
                        highest_rank_order = rank_order
                        member_rank = canonical_role
            
            if member_rank:
                # Determine member status
                status = 'Active'
                existing_member = await self.bot.db.get_member(member.guild.id, member.id)
                if existing_member and existing_member.get('is_on_loa'):
                    status = 'LOA'
                
                # Update member with username
                discord_username = member.name
                await self.bot.db.add_or_update_member(
                    member.guild.id,
                    member.id,
                    member.display_name,
                    member_rank,
                    discord_username,
                    status
                )
                synced_count += 1
        
        embed = discord.Embed(
            title="✅ Membership Sync Complete",
            description=f"Successfully synced {synced_count} members with their Discord roles.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="debug_roles", description="Show all Discord roles and members (for troubleshooting)")
    async def debug_roles(self, interaction: discord.Interaction):
        """Debug command to see all Discord roles and their members"""
        await interaction.response.defer(ephemeral=True)
        
        # Get all members and their roles
        debug_info = []
        debug_info.append(f"**🔍 Debug Info for {interaction.guild.name}**")
        debug_info.append(f"Guild ID: {interaction.guild.id}")
        debug_info.append("")
        
        # Show all Discord roles that match our expected names or variations
        debug_info.append("**📋 Expected Membership Roles:**")
        for canonical_name in self.default_rank_order.keys():
            found_match = False
            # Check all variations for this role
            for variation in self.role_variations[canonical_name]:
                discord_role = discord.utils.get(interaction.guild.roles, name=variation)
                if discord_role:
                    members_with_role = [m.display_name for m in discord_role.members if not m.bot]
                    if members_with_role:
                        debug_info.append(f"✅ **{canonical_name}** (as '{variation}'): {', '.join(members_with_role)}")
                        found_match = True
                        break  # Found one, no need to check other variations
                    else:
                        debug_info.append(f"⚠️ **{canonical_name}** (as '{variation}'): Role exists but no members")
                        found_match = True
                        break
            
            if not found_match:
                debug_info.append(f"❌ **{canonical_name}**: No matching role found (checked: {', '.join(self.role_variations[canonical_name])})")
        
        debug_info.append("")
        debug_info.append("**🤖 Current Database Members:**")
        
        # Show current database state
        members = await self.bot.db.get_all_members(interaction.guild.id)
        if members:
            for member in members[:10]:  # Limit to 10 for readability
                debug_info.append(f"• {member.get('discord_name', 'Unknown')} - {member.get('rank', 'No rank')}")
            if len(members) > 10:
                debug_info.append(f"... and {len(members) - 10} more")
        else:
            debug_info.append("No members in database yet")
        
        # Send debug info
        debug_text = "\n".join(debug_info)
        if len(debug_text) > 2000:
            # Split into multiple messages if too long
            debug_text = debug_text[:1900] + "\n... (truncated)"
        
        await interaction.followup.send(debug_text, ephemeral=True)
    
    @app_commands.command(name="membership_list", description="Generate membership list table file")
    async def membership_list(self, interaction: discord.Interaction):
        """Generate membership list as a formatted table file for Notepad"""
        await interaction.response.defer()
        
        # Get all members
        members = await self.bot.db.get_all_members(interaction.guild.id)
        
        if not members:
            embed = discord.Embed(
                title="📋 Membership List",
                description="No members found in database. Try running `/membership_sync` first.",
                color=discord.Color.blue()
            )
            return await interaction.followup.send(embed=embed)
        
        # Group members by rank
        grouped_members = {}
        config = await self.bot.db.get_server_config(interaction.guild.id)
        membership_roles = config.get('membership_roles', []) if config else []
        
        for member in members:
            rank = member.get('rank', 'Unknown')
            if rank not in grouped_members:
                grouped_members[rank] = []
            grouped_members[rank].append(member)
        
        # Generate text file format
        content = await self._generate_membership_table(grouped_members, interaction.guild.name)
        
        # Create file
        file_content = io.StringIO(content)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file = discord.File(file_content, filename=f"membership_list_{timestamp}.txt")
        
        await interaction.followup.send(
            content=f"📋 **Membership List Table** - {len(members)} total members",
            file=file
        )
    
    async def _generate_membership_table(self, grouped_members: Dict, guild_name: str) -> str:
        """Generate text file content formatted as a clean table for Notepad"""
        content = []
        
        # Header with guild name and timestamp
        content.append(f"MEMBERSHIP LIST - {guild_name.upper()}")
        content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append("=" * 70)
        content.append("")
        
        # Table header with better spacing for readability
        content.append("+" + "-" * 22 + "+" + "-" * 20 + "+" + "-" * 16 + "+" + "-" * 8 + "+")
        content.append(f"| {'POSITION':<20} | {'NAME':<18} | {'USERNAME':<14} | {'STATUS':<6} |")
        content.append("+" + "=" * 22 + "+" + "=" * 20 + "+" + "=" * 16 + "+" + "=" * 8 + "+")
        
        # Three Heads section
        self._add_table_section(content, "THREE HEADS", [
            ("President", grouped_members),
            ("Vice President", grouped_members),
            ("Sergeant At Arms", grouped_members)
        ])
        
        # Chapter Council section
        content.append("+" + "-" * 22 + "+" + "-" * 20 + "+" + "-" * 16 + "+" + "-" * 8 + "+")
        self._add_table_section(content, "CHAPTER COUNCIL", [
            ("Secretary", grouped_members),
            ("Treasurer", grouped_members),
            ("Road Captain", grouped_members),
            ("Tailgunner", grouped_members),
            ("Enforcer", grouped_members)
        ])
        
        # Full Patch section
        content.append("+" + "-" * 22 + "+" + "-" * 20 + "+" + "-" * 16 + "+" + "-" * 8 + "+")
        self._add_table_section(content, "FULL PATCH", [
            ("Full Patch", grouped_members)
        ])
        
        # Nomad section  
        content.append("+" + "-" * 22 + "+" + "-" * 20 + "+" + "-" * 16 + "+" + "-" * 8 + "+")
        self._add_table_section(content, "NOMAD", [
            ("Nomad", grouped_members)
        ])
        
        # Add any other ranks not covered above
        three_heads = ["President", "Vice President", "Sergeant At Arms"]
        chapter_council = ["Secretary", "Treasurer", "Road Captain", "Tailgunner", "Enforcer"]
        full_patch = ["Full Patch"]
        nomad_ranks = ["Nomad"]
        other_ranks = [rank for rank in grouped_members.keys() 
                      if rank not in three_heads + chapter_council + full_patch + nomad_ranks]
        
        if other_ranks:
            content.append("+" + "-" * 22 + "+" + "-" * 20 + "+" + "-" * 16 + "+" + "-" * 8 + "+")
            other_section = [(rank, grouped_members) for rank in other_ranks]
            self._add_table_section(content, "OTHER RANKS", other_section)
        
        # Close the table
        content.append("+" + "-" * 22 + "+" + "-" * 20 + "+" + "-" * 16 + "+" + "-" * 8 + "+")
        
        # Add summary
        total_members = sum(len(members) for members in grouped_members.values())
        content.append("")
        content.append(f"TOTAL MEMBERS: {total_members}")
        
        return "\n".join(content)
    
    def _add_table_section(self, content: list, section_name: str, rank_data: list):
        """Add a section to the membership table with improved formatting"""
        section_added = False
        
        for rank_name, grouped_members in rank_data:
            if rank_name in grouped_members:
                members_in_rank = grouped_members[rank_name]
                for i, member in enumerate(members_in_rank):
                    # Get member info with proper truncation
                    name = member.get('discord_name', 'Unknown')
                    if len(name) > 18:
                        name = name[:15] + "..."
                    
                    username = member.get('discord_username') or 'N/A'
                    if len(username) > 14:
                        username = username[:11] + "..."
                    
                    # Determine status with clear indicators
                    status = member.get('status', 'Active')
                    if member.get('is_on_loa') or status == 'LOA':
                        status_display = 'LOA'
                    else:
                        status_display = 'ACTIVE'
                    
                    # FIXED: Always show the actual rank name, not the section name
                    if i == 0:
                        # First member of this rank gets the rank name
                        content.append(f"| {rank_name:<20} | {name:<18} | {username:<14} | {status_display:<6} |")
                    else:
                        # Subsequent members get empty rank field
                        content.append(f"| {'':<20} | {name:<18} | {username:<14} | {status_display:<6} |")
                    section_added = True
        
        # If no members were found for this section, still add the section header
        if not section_added:
            content.append(f"| {section_name:<20} | {'No members':<18} | {'':<14} | {'':<6} |")
    
    def _add_embed_section(self, embed: discord.Embed, section_title: str, ranks: list, grouped_members: dict):
        """Add a section to the embed with proper formatting"""
        section_text = ""
        
        for rank_name in ranks:
            if rank_name in grouped_members:
                members_list = grouped_members[rank_name]
                if members_list:
                    section_text += f"**{rank_name}:**\n"
                    for member in members_list:
                        # Get status emoji
                        if member.get('is_on_loa') or member.get('status') == 'LOA':
                            status_emoji = "🚫"  # LOA status
                        else:
                            status_emoji = "✅"  # Active status
                        
                        # Format member entry
                        member_name = member.get('discord_name', 'Unknown')[:25]  # Truncate if too long
                        section_text += f"  {status_emoji} {member_name}\n"
                else:
                    # No members in this rank
                    section_text += f"**{rank_name}:** *No members*\n"
        
        if section_text:
            # Only add if there's content
            embed.add_field(name=section_title, value=section_text[:1024], inline=False)
    
    @app_commands.command(name="membership_embed", description="Show membership list in Discord embed format")
    async def membership_embed(self, interaction: discord.Interaction):
        """Generate membership list as Discord embeds"""
        await interaction.response.defer()
        
        # Get all members
        members = await self.bot.db.get_all_members(interaction.guild.id)
        
        if not members:
            embed = discord.Embed(
                title="📋 Membership List",
                description="No members found in database. Try running `/membership_sync` first.",
                color=discord.Color.blue()
            )
            return await interaction.followup.send(embed=embed)
        
        # Group members by rank
        grouped_members = {}
        for member in members:
            rank = member.get('rank', 'Unknown')
            if rank not in grouped_members:
                grouped_members[rank] = []
            grouped_members[rank].append(member)
        
        # Create main embed
        main_embed = discord.Embed(
            title=f"📋 {interaction.guild.name} Membership List",
            description=f"**Total Members:** {len(members)}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Add sections to embed
        self._add_embed_section(main_embed, "🏛️ Three Heads", 
                               ["President", "Vice President", "Sergeant At Arms"], grouped_members)
        
        self._add_embed_section(main_embed, "⚖️ Chapter Council", 
                               ["Secretary", "Treasurer", "Road Captain", "Tailgunner", "Enforcer"], grouped_members)
        
        self._add_embed_section(main_embed, "🏍️ Full Patch", 
                               ["Full Patch"], grouped_members)
        
        self._add_embed_section(main_embed, "🗺️ Nomad", 
                               ["Nomad"], grouped_members)
        
        # Add other ranks if any
        covered_ranks = ["President", "Vice President", "Sergeant At Arms", "Secretary", 
                        "Treasurer", "Road Captain", "Tailgunner", "Enforcer", "Full Patch", "Nomad"]
        other_ranks = [rank for rank in grouped_members.keys() if rank not in covered_ranks]
        
        if other_ranks:
            self._add_embed_section(main_embed, "📝 Other Ranks", other_ranks, grouped_members)
        
        # Add legend
        main_embed.add_field(
            name="📊 Status Legend",
            value="✅ Active Member\n🚫 On Leave of Absence (LOA)",
            inline=False
        )
        
        await interaction.followup.send(embed=main_embed)
    
    @app_commands.command(name="update_member_rank", description="Update a member's rank (Officers only)")
    async def update_member_rank(self, interaction: discord.Interaction, 
                                member: discord.Member, new_rank: str):
        """Manually update a member's rank"""
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
        
        # Validate rank
        membership_roles = config.get('membership_roles', [])
        if new_rank not in membership_roles:
            available_ranks = ", ".join(membership_roles)
            return await interaction.response.send_message(
                f"❌ Invalid rank. Available ranks: {available_ranks}", ephemeral=True
            )
        
        # Update member
        await self.bot.db.add_or_update_member(
            interaction.guild.id,
            member.id,
            member.display_name,
            new_rank
        )
        
        embed = discord.Embed(
            title="✅ Member Rank Updated",
            description=f"Updated {member.display_name}'s rank to **{new_rank}**",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="remove_member", description="Remove a member from the database (Officers only)")
    async def remove_member(self, interaction: discord.Interaction, member: discord.Member):
        """Remove a member from the database"""
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
        
        # Remove member
        conn = await self.bot.db._get_shared_connection()
        await conn.execute(
            'DELETE FROM members WHERE guild_id = ? AND user_id = ?',
            (interaction.guild.id, member.id)
        )
        await self.bot.db._execute_commit()
        
        embed = discord.Embed(
            title="✅ Member Removed",
            description=f"Removed {member.display_name} from the membership database.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(MembershipSystem(bot))

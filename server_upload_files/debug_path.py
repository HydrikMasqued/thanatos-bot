import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
import logging

logger = logging.getLogger(__name__)

class DebugPath(commands.Cog):
    """Debug cog to check Python paths and imports"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("DebugPath cog initialized - checking Python paths...")
        
        # Log current working directory
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Log Python path
        logger.info(f"Python path entries:")
        for i, path in enumerate(sys.path[:10]):  # Log first 10 entries
            logger.info(f"  [{i}] {path}")
        
        # Check if utils directory exists
        utils_path = os.path.join(os.getcwd(), 'utils')
        logger.info(f"Utils directory exists at {utils_path}: {os.path.exists(utils_path)}")
        
        if os.path.exists(utils_path):
            utils_files = os.listdir(utils_path)
            logger.info(f"Files in utils directory: {utils_files}")
            
            permissions_path = os.path.join(utils_path, 'permissions.py')
            logger.info(f"permissions.py exists: {os.path.exists(permissions_path)}")
        
        # Try to import utils.permissions
        try:
            import utils.permissions
            logger.info("✅ Successfully imported utils.permissions")
        except Exception as e:
            logger.error(f"❌ Failed to import utils.permissions: {e}")
            
            # Try alternative imports
            try:
                sys.path.insert(0, '/home/container')
                import utils.permissions
                logger.info("✅ Successfully imported utils.permissions after adding /home/container to path")
            except Exception as e2:
                logger.error(f"❌ Still failed after adding /home/container: {e2}")

    @app_commands.command(name="debug-paths", description="Debug Python paths and imports")
    async def debug_paths(self, interaction: discord.Interaction):
        """Debug command to show Python paths"""
        embed = discord.Embed(
            title="🔍 Python Path Debug Info",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Working Directory",
            value=f"`{os.getcwd()}`",
            inline=False
        )
        
        paths_text = "\n".join([f"`{path}`" for path in sys.path[:5]])
        embed.add_field(
            name="Python Paths (first 5)",
            value=paths_text,
            inline=False
        )
        
        # Check utils directory
        utils_exists = os.path.exists(os.path.join(os.getcwd(), 'utils'))
        permissions_exists = os.path.exists(os.path.join(os.getcwd(), 'utils', 'permissions.py'))
        
        embed.add_field(
            name="File Status",
            value=f"Utils directory: {'✅' if utils_exists else '❌'}\n"
                  f"permissions.py: {'✅' if permissions_exists else '❌'}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(DebugPath(bot))

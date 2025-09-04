import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import discord
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_session import Session
import aiosqlite
from functools import wraps
import requests

# Import bot's database utilities
import sys
import os
# Add parent directory to sys.path to access utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.database import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'thanatos-admin-dashboard-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Discord OAuth2 Configuration
DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', 'YOUR_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', 'YOUR_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.environ.get('DISCORD_REDIRECT_URI', 'http://localhost:5000/callback')
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', 'YOUR_BOT_TOKEN')

# Target Guild ID for the dashboard (Thanatos Project)
TARGET_GUILD_ID = 1336076303098450003

# Initialize session
Session(app)

class DashboardManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.discord_client = None
        self._guild_cache = {}
        self._channel_cache = {}
        self._mass_dm_jobs = {}  # Track ongoing mass DM operations
        self.executor = ThreadPoolExecutor(max_workers=2)  # For background tasks
        
    async def initialize(self):
        """Initialize database and Discord client"""
        await self.db.initialize_database()
        
        # Initialize Discord client for API calls
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True
        
        self.discord_client = discord.Client(intents=intents)
        
    async def get_guild_info(self, guild_id: int) -> Optional[Dict]:
        """Get guild information from Discord API"""
        if guild_id in self._guild_cache:
            return self._guild_cache[guild_id]
            
        try:
            headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
            response = requests.get(f'https://discord.com/api/v10/guilds/{guild_id}', headers=headers)
            
            if response.status_code == 200:
                guild_data = response.json()
                self._guild_cache[guild_id] = guild_data
                return guild_data
        except Exception as e:
            logger.error(f"Error fetching guild info: {e}")
            
        return None
        
    async def get_forum_channels(self, guild_id: int) -> List[Dict]:
        """Get all forum channels from the guild"""
        try:
            headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
            response = requests.get(f'https://discord.com/api/v10/guilds/{guild_id}/channels', headers=headers)
            
            if response.status_code == 200:
                channels = response.json()
                # Filter for forum channels (type 15)
                forum_channels = [
                    {
                        'id': channel['id'],
                        'name': channel['name'],
                        'position': channel.get('position', 0),
                        'parent_id': channel.get('parent_id'),
                        'thread_count': len(channel.get('available_tags', []))
                    }
                    for channel in channels 
                    if channel.get('type') == 15  # GUILD_FORUM
                ]
                
                return sorted(forum_channels, key=lambda x: (x.get('parent_id') or 0, x['position']))
        except Exception as e:
            logger.error(f"Error fetching forum channels: {e}")
            
        return []
        
    async def get_forum_threads(self, channel_id: int, limit: int = 50) -> List[Dict]:
        """Get threads from a forum channel"""
        try:
            headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
            
            # Get active threads
            response = requests.get(
                f'https://discord.com/api/v10/channels/{channel_id}/threads/active',
                headers=headers
            )
            
            threads = []
            if response.status_code == 200:
                active_data = response.json()
                threads.extend([
                    {
                        'id': thread['id'],
                        'name': thread['name'],
                        'created_at': thread['created_at'],
                        'message_count': thread.get('message_count', 0),
                        'archived': False,
                        'locked': thread.get('locked', False)
                    }
                    for thread in active_data.get('threads', [])
                ])
                
            # Get archived threads
            response = requests.get(
                f'https://discord.com/api/v10/channels/{channel_id}/threads/archived/public?limit={limit}',
                headers=headers
            )
            
            if response.status_code == 200:
                archived_data = response.json()
                threads.extend([
                    {
                        'id': thread['id'],
                        'name': thread['name'],
                        'created_at': thread['created_at'],
                        'message_count': thread.get('message_count', 0),
                        'archived': True,
                        'locked': thread.get('locked', False)
                    }
                    for thread in archived_data.get('threads', [])
                ])
                
            # Sort by creation date (newest first)
            threads.sort(key=lambda x: x['created_at'], reverse=True)
            return threads[:limit]
            
        except Exception as e:
            logger.error(f"Error fetching forum threads: {e}")
            
        return []
        
    async def get_contribution_categories(self) -> Dict[str, Dict]:
        """Get all contribution categories with their current forum mappings"""
        # This matches the category structure from contributions.py
        categories = {
            "Pistols": {
                "forum_id": 1355399894227091517,  # Weapons forum
                "header": "🔫 Weapons",
                "thread_id": 1355399943967211609
            },
            "Rifles": {
                "forum_id": 1355399894227091517,  # Weapons forum  
                "header": "🔫 Weapons",
                "thread_id": 1355400063685234838
            },
            "SMGs": {
                "forum_id": 1355399894227091517,  # Weapons forum
                "header": "🔫 Weapons",
                "thread_id": 1355400006504284252
            },
            "Body Armour & Medical": {
                "forum_id": 1366601638130880582,  # Equipment forum
                "header": "🛡️ Equipment & Medical",
                "thread_id": 1355400270024015973
            },
            "Meth": {
                "forum_id": 1366605626662322236,  # Contraband forum
                "header": "💊 Contraband",
                "thread_id": 1366601843240603648
            },
            "Weed": {
                "forum_id": 1366605626662322236,  # Contraband forum
                "header": "💊 Contraband",
                "thread_id": 1389788322976497734
            },
            "Heist Items": {
                "forum_id": None,  # Misc forum - to be set
                "header": "📦 Misc Items",
                "thread_id": 1368632475986694224
            },
            "Dirty Cash": {
                "forum_id": None,  # Misc forum - to be set
                "header": "📦 Misc Items",
                "thread_id": 1380363715983048826
            },
            "Drug Items": {
                "forum_id": None,  # Misc forum - to be set
                "header": "📦 Misc Items",
                "thread_id": 1389785875789119521
            },
            "Mech Shop": {
                "forum_id": None,  # Misc forum - to be set
                "header": "📦 Misc Items",
                "thread_id": 1389787215042842714
            },
            "Crafting Items": {
                "forum_id": None,  # Misc forum - to be set
                "header": "📦 Misc Items",
                "thread_id": 1366606110315778118
            }
        }
        
        return categories
        
    async def update_category_mapping(self, category: str, forum_id: Optional[int], thread_id: Optional[int]) -> bool:
        """Update the forum/thread mapping for a category"""
        try:
            # This would update the bot's configuration
            # For now, we'll store it in a separate config file
            config_path = '../config/forum_mappings.json'
            
            # Load existing config
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = {}
                
            # Update the mapping
            config[category] = {
                'forum_id': forum_id,
                'thread_id': thread_id,
                'updated_at': datetime.now().isoformat(),
                'updated_by': session.get('user', {}).get('username', 'Unknown')
            }
            
            # Ensure config directory exists
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # Save config
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"Updated forum mapping for {category}: forum={forum_id}, thread={thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating category mapping: {e}")
            return False

# Initialize dashboard manager
dashboard = DashboardManager()

def requires_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def requires_admin(f):
    """Decorator to require admin permissions"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
            
        user = session['user']
        
        # Check if user has admin permissions (customize this logic)
        if not user.get('is_admin', False):
            flash('Access denied. Admin permissions required.', 'error')
            return redirect(url_for('index'))
            
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Main dashboard page"""
    if 'user' not in session:
        return redirect(url_for('login'))
        
    return render_template('index.html', user=session['user'])

@app.route('/api/treasury')
@requires_auth
def api_treasury():
    """API endpoint to get treasury summary"""
    try:
        # Get the guild ID from the user session (assuming it's stored there)
        # If not, you may need to adjust this to get the target guild ID
        guild_id = TARGET_GUILD_ID  # Use your target guild ID
        
        # Get treasury summary using the database manager
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            treasury_data = loop.run_until_complete(
                dashboard.db.get_treasury_summary(guild_id)
            )
        finally:
            loop.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_collected': treasury_data.get('total_collected', 0.0),
                'outstanding_amount': treasury_data.get('outstanding_amount', 0.0),
                'collection_percentage': treasury_data.get('collection_percentage', 0.0),
                'active_periods': treasury_data.get('active_periods_count', 0),
                'recent_period': treasury_data.get('recent_period_name', 'N/A')
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting treasury data: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'total_collected': 0.0,
                'outstanding_amount': 0.0,
                'collection_percentage': 0.0,
                'active_periods': 0,
                'recent_period': 'N/A'
            }
        })

@app.route('/login')
def login():
    """Discord OAuth2 login"""
    discord_login_url = (
        f"https://discord.com/api/oauth2/authorize?"
        f"client_id={DISCORD_CLIENT_ID}&"
        f"redirect_uri={DISCORD_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=identify guilds"
    )
    return redirect(discord_login_url)

@app.route('/callback')
def callback():
    """Handle Discord OAuth2 callback"""
    code = request.args.get('code')
    if not code:
        flash('Authorization failed.', 'error')
        return redirect(url_for('login'))
        
    try:
        # Exchange code for token
        token_data = {
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DISCORD_REDIRECT_URI
        }
        
        response = requests.post('https://discord.com/api/oauth2/token', data=token_data)
        tokens = response.json()
        
        if 'access_token' not in tokens:
            flash('Failed to get access token.', 'error')
            return redirect(url_for('login'))
            
        # Get user info
        headers = {'Authorization': f"Bearer {tokens['access_token']}"}
        user_response = requests.get('https://discord.com/api/users/@me', headers=headers)
        user_data = user_response.json()
        
        # Get user's guilds
        guilds_response = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
        guilds_data = guilds_response.json()
        
        # Check if user is in target guild and has admin permissions
        is_admin = False
        target_guild = None
        
        for guild in guilds_data:
            if int(guild['id']) == TARGET_GUILD_ID:
                target_guild = guild
                # Check if user has admin permissions (0x8 = ADMINISTRATOR)
                if int(guild['permissions']) & 0x8:
                    is_admin = True
                break
                
        if not target_guild:
            flash('Access denied. You must be a member of the Thanatos Discord server.', 'error')
            return redirect(url_for('login'))
            
        # Store user info in session
        session['user'] = {
            'id': user_data['id'],
            'username': user_data['username'],
            'discriminator': user_data.get('discriminator', '0000'),
            'avatar': user_data.get('avatar'),
            'is_admin': is_admin,
            'access_token': tokens['access_token']
        }
        
        session.permanent = True
        flash(f'Welcome, {user_data["username"]}!', 'success')
        
        return redirect(url_for('forum_management'))
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        flash('Login failed. Please try again.', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """Logout user"""
    session.pop('user', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/forum_management')
@requires_admin  
def forum_management():
    """Forum thread management interface"""
    return render_template('forum_management.html', user=session['user'])

@app.route('/api/categories')
@requires_admin
def api_categories():
    """API endpoint to get all contribution categories"""
    try:
        # Return list of category names for the forum management UI
        categories = [
            "Pistols", "SMGs", "Rifles", "Shotguns", "Grenades",
            "Body Armour & Medical", "Meth", "Weed", "Coke", "Heroin", 
            "Drug Items", "Heist Items", "Dirty Cash", "Mech Shop", 
            "Crafting Items"
        ]
        
        return jsonify(categories)
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/forum_threads')
@requires_admin
def api_forum_threads():
    """API endpoint to get threads from the target forum channel"""
    try:
        headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
        
        # Get the forum channel info first
        channel_response = requests.get(
            f'https://discord.com/api/v10/channels/{TARGET_GUILD_ID}',
            headers=headers
        )
        
        if channel_response.status_code != 200:
            return jsonify({'error': 'Failed to get forum channel'}), 400
            
        # Get active threads from the target forum
        threads_response = requests.get(
            f'https://discord.com/api/v10/channels/{TARGET_GUILD_ID}/threads/active',
            headers=headers
        )
        
        threads = []
        if threads_response.status_code == 200:
            threads_data = threads_response.json()
            threads.extend([
                {
                    'id': thread['id'],
                    'name': thread['name'],
                    'parent_id': thread.get('parent_id'),
                    'parent_name': 'Contribution Threads',
                    'archived': False
                }
                for thread in threads_data.get('threads', [])
            ])
        
        # Get archived threads too
        archived_response = requests.get(
            f'https://discord.com/api/v10/channels/{TARGET_GUILD_ID}/threads/archived/public',
            headers=headers
        )
        
        if archived_response.status_code == 200:
            archived_data = archived_response.json()
            threads.extend([
                {
                    'id': thread['id'], 
                    'name': thread['name'],
                    'parent_id': thread.get('parent_id'),
                    'parent_name': 'Contribution Threads',
                    'archived': True
                }
                for thread in archived_data.get('threads', [])
            ])
            
        return jsonify(threads)
        
    except Exception as e:
        logger.error(f"Error getting forum threads: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/thread_mappings', methods=['GET', 'POST'])
@requires_admin  
def api_thread_mappings():
    """API endpoint to get/update thread mappings"""
    if request.method == 'GET':
        try:
            # Load mappings from the config file
            config_path = '../config/thread_mappings.json'
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    mappings = json.load(f)
            else:
                # Return default mappings from contributions.py
                mappings = {
                    "Pistols": "1355399943967211609",
                    "SMGs": "1355400006504284252", 
                    "Rifles": "1355400063685234838",
                    "Body Armour & Medical": "1355400270024015973",
                    "Meth": "1366601843240603648",
                    "Weed": "1389788322976497734",
                    "Heist Items": "1368632475986694224",
                    "Dirty Cash": "1380363715983048826",
                    "Drug Items": "1389785875789119521",
                    "Mech Shop": "1389787215042842714",
                    "Crafting Items": "1366606110315778118"
                }
                
            return jsonify(mappings)
            
        except Exception as e:
            logger.error(f"Error getting thread mappings: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            # Update thread mappings
            new_mappings = request.get_json()
            
            if not isinstance(new_mappings, dict):
                return jsonify({'error': 'Invalid data format'}), 400
            
            # Save to config file  
            config_path = '../config/thread_mappings.json'
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(new_mappings, f, indent=2)
            
            logger.info(f"Updated thread mappings: {len(new_mappings)} categories")
            
            return jsonify({
                'success': True,
                'message': f'Successfully updated {len(new_mappings)} thread mappings',
                'updated_by': session.get('user', {}).get('username', 'Unknown'),
                'updated_at': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error updating thread mappings: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/update-mapping', methods=['POST'])
@requires_admin
def api_update_mapping():
    """API endpoint to update category-forum-thread mappings"""
    try:
        data = request.get_json()
        category = data.get('category')
        forum_id = data.get('forum_id')
        thread_id = data.get('thread_id')
        
        if not category:
            return jsonify({'success': False, 'error': 'Category is required'})
            
        # Convert to int or None
        forum_id = int(forum_id) if forum_id else None
        thread_id = int(thread_id) if thread_id else None
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(dashboard.update_category_mapping(category, forum_id, thread_id))
        loop.close()
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'Successfully updated {category} mapping',
                'updated_by': session['user']['username'],
                'updated_at': datetime.now().isoformat()
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update mapping'})
            
    except Exception as e:
        logger.error(f"Error updating mapping: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bulk-update', methods=['POST'])
@requires_admin
def api_bulk_update():
    """API endpoint for bulk updating multiple category mappings"""
    try:
        data = request.get_json()
        mappings = data.get('mappings', [])
        
        if not mappings:
            return jsonify({'success': False, 'error': 'No mappings provided'})
            
        results = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for mapping in mappings:
            category = mapping.get('category')
            forum_id = int(mapping.get('forum_id')) if mapping.get('forum_id') else None
            thread_id = int(mapping.get('thread_id')) if mapping.get('thread_id') else None
            
            success = loop.run_until_complete(dashboard.update_category_mapping(category, forum_id, thread_id))
            results.append({
                'category': category,
                'success': success
            })
            
        loop.close()
        
        successful_updates = len([r for r in results if r['success']])
        
        return jsonify({
            'success': True,
            'message': f'Updated {successful_updates} out of {len(mappings)} categories',
            'results': results,
            'updated_by': session['user']['username'],
            'updated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in bulk update: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/validate-thread/<int:thread_id>')
@requires_admin
def api_validate_thread(thread_id):
    """API endpoint to validate that a thread exists and get its info"""
    try:
        headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
        response = requests.get(f'https://discord.com/api/v10/channels/{thread_id}', headers=headers)
        
        if response.status_code == 200:
            thread_data = response.json()
            return jsonify({
                'success': True,
                'valid': True,
                'thread': {
                    'id': thread_data['id'],
                    'name': thread_data['name'],
                    'parent_id': thread_data.get('parent_id'),
                    'archived': thread_data.get('thread_metadata', {}).get('archived', False),
                    'locked': thread_data.get('thread_metadata', {}).get('locked', False)
                }
            })
        else:
            return jsonify({'success': True, 'valid': False, 'error': 'Thread not found'})
            
    except Exception as e:
        logger.error(f"Error validating thread {thread_id}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/loa-management')
@requires_admin
def loa_management():
    """LOA management interface"""
    return render_template('loa_management.html', user=session['user'])

@app.route('/api/loa/active')
@requires_admin
def api_get_active_loas():
    """Get all active LOAs for the target guild"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get active LOAs from the database
        db = DatabaseManager()
        active_loas = loop.run_until_complete(db.get_active_loas_for_guild(TARGET_GUILD_ID))
        
        loop.close()
        
        return jsonify({
            'success': True,
            'loas': active_loas
        })
        
    except Exception as e:
        logger.error(f"Error getting active LOAs: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/loa/<int:loa_id>/end', methods=['POST'])
@requires_admin
def api_end_loa(loa_id):
    """Force end an active LOA"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get LOA details first
        db = DatabaseManager()
        loa_details = loop.run_until_complete(db.get_loa_by_id(loa_id))
        
        if not loa_details:
            return jsonify({'success': False, 'error': 'LOA not found'})
        
        # End the LOA
        success = loop.run_until_complete(db.end_loa(loa_id))
        
        if success:
            # Send notifications to Discord
            loop.run_until_complete(send_loa_end_notification(
                TARGET_GUILD_ID, loa_details, session['user']['username']
            ))
            
        loop.close()
        
        if success:
            logger.info(f"Admin {session['user']['username']} force-ended LOA {loa_id}")
            return jsonify({
                'success': True,
                'message': f"Successfully ended LOA for {loa_details.get('discord_name', 'Unknown User')}"
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to end LOA'})
            
    except Exception as e:
        logger.error(f"Error ending LOA {loa_id}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/audit-management')
@requires_admin
def audit_management():
    """Audit log management interface"""
    return render_template('audit_management.html', user=session['user'])

@app.route('/api/audit/events')
@requires_admin
def api_get_audit_events():
    """Get recent audit events for management"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        db = DatabaseManager()
        events = loop.run_until_complete(db.get_all_audit_events(
            TARGET_GUILD_ID, 
            limit=limit
        ))
        
        loop.close()
        
        return jsonify({
            'success': True,
            'events': events
        })
        
    except Exception as e:
        logger.error(f"Error getting audit events: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/audit/remove', methods=['POST'])
@requires_admin
def api_remove_audit_entry():
    """Remove a specific audit entry"""
    try:
        data = request.get_json()
        event_type = data.get('event_type')
        entry_id = data.get('entry_id')
        
        if not event_type or not entry_id:
            return jsonify({'success': False, 'error': 'Missing event_type or entry_id'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        db = DatabaseManager()
        
        # Get entry details first for logging
        entry_details = loop.run_until_complete(db.get_audit_entry_details(
            TARGET_GUILD_ID, event_type, entry_id
        ))
        
        # Remove the entry
        success = loop.run_until_complete(db.remove_audit_entry(
            TARGET_GUILD_ID, event_type, entry_id, 
            int(session['user']['id'])
        ))
        
        loop.close()
        
        if success:
            item_name = entry_details.get('item_name', 'Unknown') if entry_details else 'Unknown'
            logger.info(f"Admin {session['user']['username']} removed {event_type} entry {entry_id} ({item_name})")
            return jsonify({
                'success': True,
                'message': f"Successfully removed {event_type.replace('_', ' ')} entry"
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to remove entry or entry not found'})
            
    except Exception as e:
        logger.error(f"Error removing audit entry: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/audit/bulk-remove', methods=['POST'])
@requires_admin
def api_bulk_remove_audit_entries():
    """Bulk remove multiple audit entries"""
    try:
        data = request.get_json()
        entries = data.get('entries', [])
        
        if not entries:
            return jsonify({'success': False, 'error': 'No entries provided'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        db = DatabaseManager()
        result = loop.run_until_complete(db.bulk_remove_audit_entries(
            TARGET_GUILD_ID, entries, int(session['user']['id'])
        ))
        
        loop.close()
        
        logger.info(f"Admin {session['user']['username']} bulk removed {result['total_removed']} audit entries")
        
        return jsonify({
            'success': result['success'],
            'message': f"Removed {result['total_removed']} entries",
            'details': result
        })
        
    except Exception as e:
        logger.error(f"Error bulk removing audit entries: {e}")
        return jsonify({'success': False, 'error': str(e)})

# LOA force-end notification function
async def send_loa_end_notification(guild_id: int, loa_details: dict, admin_username: str):
    """Send Discord notifications when an LOA is force-ended from dashboard"""
    try:
        headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
        
        # Get server config for notification channels
        db = DatabaseManager()
        config = await db.get_server_config(guild_id)
        if not config:
            return
        
        # Get user info
        user_id = loa_details.get('user_id')
        user_name = loa_details.get('discord_name', 'Unknown User')
        user_username = loa_details.get('discord_username', 'unknown')
        
        # Create notification embed
        embed_data = {
            "title": "🛡️ LOA Force Ended by Dashboard Admin",
            "description": f"**{user_name}**'s LOA has been ended by a dashboard administrator",
            "color": 0xFFD700,  # Gold color
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {
                    "name": "Member",
                    "value": f"{user_name} (@{user_username})",
                    "inline": True
                },
                {
                    "name": "Action by Admin",
                    "value": admin_username,
                    "inline": True
                },
                {
                    "name": "Original Duration",
                    "value": loa_details.get('duration', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "Reason",
                    "value": loa_details.get('reason', 'No reason provided')[:200] + ('...' if len(loa_details.get('reason', '')) > 200 else ''),
                    "inline": False
                },
                {
                    "name": "📊 Membership Impact",
                    "value": "Member status updated to **Active** in membership database",
                    "inline": False
                }
            ],
            "footer": {
                "text": f"User ID: {user_id} | Force-ended via Dashboard"
            }
        }
        
        # Send to officer notification channel
        officer_channel_id = config.get('loa_notification_channel_id') or config.get('notification_channel_id')
        if officer_channel_id:
            # Prepare mention for officer role
            mention_text = ""
            if config.get('loa_notification_role_id'):
                mention_text = f"<@&{config['loa_notification_role_id']}> "
            
            # Send message to channel
            payload = {
                "content": mention_text,
                "embeds": [embed_data]
            }
            
            requests.post(
                f'https://discord.com/api/v10/channels/{officer_channel_id}/messages',
                headers=headers,
                json=payload
            )
        
        # Send DM to the user whose LOA was ended
        try:
            dm_embed_data = {
                "title": "📨 Your LOA has been ended",
                "description": f"Your Leave of Absence has been ended by an administrator.",
                "color": 0xFFA500,  # Orange color
                "timestamp": datetime.now().isoformat(),
                "fields": [
                    {
                        "name": "Original Duration",
                        "value": loa_details.get('duration', 'Unknown'),
                        "inline": True
                    },
                    {
                        "name": "Status",
                        "value": "You are now marked as **Active** in the server",
                        "inline": True
                    },
                    {
                        "name": "Server",
                        "value": "Thanatos Project",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "If you have questions, please contact server staff"
                }
            }
            
            # Create DM channel and send message
            dm_channel_response = requests.post(
                'https://discord.com/api/v10/users/@me/channels',
                headers=headers,
                json={'recipient_id': str(user_id)}
            )
            
            if dm_channel_response.status_code == 200:
                dm_channel = dm_channel_response.json()
                requests.post(
                    f'https://discord.com/api/v10/channels/{dm_channel["id"]}/messages',
                    headers=headers,
                    json={'embeds': [dm_embed_data]}
                )
                
        except Exception as e:
            logger.error(f"Error sending DM notification to user {user_id}: {e}")
            # Don't fail the whole operation if DM fails
            pass
            
    except Exception as e:
        logger.error(f"Error sending LOA end notification: {e}")

@app.route('/mass-dm')
@requires_admin
def mass_dm():
    """Mass DM management interface"""
    return render_template('mass_dm.html', user=session['user'])

@app.route('/api/roles')
@requires_admin
def api_get_roles():
    """Get all roles from the target guild"""
    try:
        headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
        response = requests.get(f'https://discord.com/api/v10/guilds/{TARGET_GUILD_ID}/roles', headers=headers)
        
        if response.status_code == 200:
            roles_data = response.json()
            # Filter out @everyone and bot roles, sort by position
            roles = [
                {
                    'id': role['id'],
                    'name': role['name'],
                    'color': role['color'],
                    'position': role['position'],
                    'member_count': 0  # We'll populate this if needed
                }
                for role in roles_data
                if role['name'] != '@everyone' and not role.get('managed', False)
            ]
            
            # Sort by position (higher position = higher in hierarchy)
            roles.sort(key=lambda x: x['position'], reverse=True)
            
            return jsonify({
                'success': True,
                'roles': roles
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to fetch roles'})
            
    except Exception as e:
        logger.error(f"Error getting roles: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/role/<int:role_id>/members')
@requires_admin
def api_get_role_members(role_id):
    """Get all members with a specific role"""
    try:
        headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
        
        # Get guild members
        response = requests.get(
            f'https://discord.com/api/v10/guilds/{TARGET_GUILD_ID}/members?limit=1000',
            headers=headers
        )
        
        if response.status_code == 200:
            members_data = response.json()
            
            # Filter members who have the specified role and aren't bots
            role_members = [
                {
                    'id': member['user']['id'],
                    'username': member['user']['username'],
                    'display_name': member.get('nick') or member['user'].get('global_name') or member['user']['username'],
                    'avatar': member['user'].get('avatar')
                }
                for member in members_data
                if str(role_id) in member.get('roles', []) and not member['user'].get('bot', False)
            ]
            
            return jsonify({
                'success': True,
                'members': role_members,
                'count': len(role_members)
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to fetch guild members'})
            
    except Exception as e:
        logger.error(f"Error getting role members: {e}")
        return jsonify({'success': False, 'error': str(e)})

def send_mass_dm_background(job_id: str, role_id: int, message: str, sender_username: str, sender_id: int):
    """Background function to send mass DMs without blocking the main Flask thread"""
    try:
        # Update job status to running
        dashboard._mass_dm_jobs[job_id]['status'] = 'running'
        dashboard._mass_dm_jobs[job_id]['started_at'] = datetime.now().isoformat()
        
        headers = {'Authorization': f'Bot {DISCORD_BOT_TOKEN}'}
        
        # Get role info
        role_response = requests.get(f'https://discord.com/api/v10/guilds/{TARGET_GUILD_ID}/roles', headers=headers)
        if role_response.status_code != 200:
            raise Exception('Failed to fetch role information')
        
        roles_data = role_response.json()
        target_role = next((role for role in roles_data if role['id'] == str(role_id)), None)
        
        if not target_role:
            raise Exception('Role not found')
        
        # Get members with this role
        members_response = requests.get(
            f'https://discord.com/api/v10/guilds/{TARGET_GUILD_ID}/members?limit=1000',
            headers=headers
        )
        
        if members_response.status_code != 200:
            raise Exception('Failed to fetch guild members')
        
        members_data = members_response.json()
        target_members = [
            member for member in members_data
            if str(role_id) in member.get('roles', []) and not member['user'].get('bot', False)
        ]
        
        if not target_members:
            raise Exception('No users found with this role')
        
        # Update job with total count
        dashboard._mass_dm_jobs[job_id]['total_members'] = len(target_members)
        dashboard._mass_dm_jobs[job_id]['role_name'] = target_role['name']
        
        successful_sends = 0
        failed_sends = 0
        
        # Create DM embed
        embed_data = {
            "title": "📨 Message from Thanatos Project",
            "description": message,
            "color": 0x0099FF,  # Blue color
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"Sent to role: {target_role['name']} | You can reply to this message and it will be sent back to the server."
            },
            "author": {
                "name": f"Sent by: {sender_username}"
            }
        }
        
        # Send DM to each member with proper rate limiting
        for i, member in enumerate(target_members):
            try:
                user_id = member['user']['id']
                
                # Create DM channel
                dm_channel_response = requests.post(
                    'https://discord.com/api/v10/users/@me/channels',
                    headers=headers,
                    json={'recipient_id': user_id},
                    timeout=10  # Add timeout
                )
                
                if dm_channel_response.status_code == 200:
                    dm_channel = dm_channel_response.json()
                    
                    # Send message
                    message_response = requests.post(
                        f'https://discord.com/api/v10/channels/{dm_channel["id"]}/messages',
                        headers=headers,
                        json={'embeds': [embed_data]},
                        timeout=10  # Add timeout
                    )
                    
                    if message_response.status_code == 200:
                        successful_sends += 1
                        
                        # Log to database in a separate thread to avoid blocking
                        try:
                            def log_dm():
                                log_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(log_loop)
                                db = DatabaseManager()
                                
                                log_loop.run_until_complete(db.log_dm_transcript(
                                    guild_id=TARGET_GUILD_ID,
                                    sender_id=sender_id,
                                    recipient_id=int(user_id),
                                    role_id=role_id,
                                    message=message,
                                    message_type="outbound",
                                    recipient_type="role",
                                    attachments=None
                                ))
                                log_loop.close()
                            
                            # Run logging in a separate thread to avoid blocking
                            log_thread = threading.Thread(target=log_dm)
                            log_thread.daemon = True
                            log_thread.start()
                            
                        except Exception as log_error:
                            logger.error(f"Error logging DM transcript: {log_error}")
                    elif message_response.status_code == 429:  # Rate limit
                        # Handle rate limit properly
                        rate_limit_data = message_response.json()
                        retry_after = rate_limit_data.get('retry_after', 1)
                        logger.warning(f"Rate limited, waiting {retry_after} seconds")
                        time.sleep(retry_after + 0.5)  # Add small buffer
                        failed_sends += 1
                    else:
                        failed_sends += 1
                elif dm_channel_response.status_code == 429:  # Rate limit
                    rate_limit_data = dm_channel_response.json()
                    retry_after = rate_limit_data.get('retry_after', 1)
                    logger.warning(f"Rate limited on DM creation, waiting {retry_after} seconds")
                    time.sleep(retry_after + 0.5)
                    failed_sends += 1
                else:
                    failed_sends += 1
                    
                # Update progress
                dashboard._mass_dm_jobs[job_id]['processed'] = i + 1
                dashboard._mass_dm_jobs[job_id]['successful'] = successful_sends
                dashboard._mass_dm_jobs[job_id]['failed'] = failed_sends
                    
                # Smart rate limiting - wait longer after every 10 messages
                if (i + 1) % 10 == 0:
                    time.sleep(2)  # 2 second pause every 10 messages
                else:
                    time.sleep(0.5)  # 0.5 second pause between messages
                
                # Check if job was cancelled
                if dashboard._mass_dm_jobs[job_id].get('cancelled', False):
                    logger.info(f"Mass DM job {job_id} was cancelled")
                    break
                    
            except Exception as e:
                logger.error(f"Error sending DM to user {member['user']['id']}: {e}")
                failed_sends += 1
                dashboard._mass_dm_jobs[job_id]['failed'] = failed_sends
        
        # Update final job status
        dashboard._mass_dm_jobs[job_id]['status'] = 'completed'
        dashboard._mass_dm_jobs[job_id]['completed_at'] = datetime.now().isoformat()
        dashboard._mass_dm_jobs[job_id]['successful'] = successful_sends
        dashboard._mass_dm_jobs[job_id]['failed'] = failed_sends
        
        # Log the mass DM action
        logger.info(f"Admin {sender_username} completed mass DM to role {target_role['name']}: {successful_sends} successful, {failed_sends} failed")
        
        # Clean up job after 1 hour
        def cleanup_job():
            time.sleep(3600)  # 1 hour
            if job_id in dashboard._mass_dm_jobs:
                del dashboard._mass_dm_jobs[job_id]
                logger.info(f"Cleaned up completed mass DM job {job_id}")
        
        cleanup_thread = threading.Thread(target=cleanup_job)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
    except Exception as e:
        logger.error(f"Error in mass DM background job {job_id}: {e}")
        dashboard._mass_dm_jobs[job_id]['status'] = 'failed'
        dashboard._mass_dm_jobs[job_id]['error'] = str(e)
        dashboard._mass_dm_jobs[job_id]['completed_at'] = datetime.now().isoformat()

@app.route('/api/mass-dm/send', methods=['POST'])
@requires_admin
def api_send_mass_dm():
    """Start a mass DM job in the background"""
    try:
        data = request.get_json()
        role_id = data.get('role_id')
        message = data.get('message')
        
        if not role_id or not message:
            return jsonify({'success': False, 'error': 'Role ID and message are required'})
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create job tracking entry
        dashboard._mass_dm_jobs[job_id] = {
            'id': job_id,
            'status': 'queued',
            'role_id': role_id,
            'message': message,
            'sender_username': session['user']['username'],
            'sender_id': int(session['user']['id']),
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'total_members': 0,
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'role_name': None,
            'error': None,
            'cancelled': False
        }
        
        # Submit job to background thread
        dashboard.executor.submit(
            send_mass_dm_background,
            job_id,
            int(role_id),
            message,
            session['user']['username'],
            int(session['user']['id'])
        )
        
        logger.info(f"Started mass DM job {job_id} for role {role_id} by {session['user']['username']}")
        
        return jsonify({
            'success': True,
            'message': 'Mass DM job started successfully',
            'job_id': job_id
        })
        
    except Exception as e:
        logger.error(f"Error starting mass DM job: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mass-dm/status/<job_id>')
@requires_admin
def api_mass_dm_status(job_id):
    """Get the status of a mass DM job"""
    try:
        if job_id not in dashboard._mass_dm_jobs:
            return jsonify({'success': False, 'error': 'Job not found'})
        
        job_data = dashboard._mass_dm_jobs[job_id].copy()
        
        # Calculate progress percentage
        if job_data['total_members'] > 0:
            job_data['progress_percentage'] = (job_data['processed'] / job_data['total_members']) * 100
        else:
            job_data['progress_percentage'] = 0
        
        return jsonify({
            'success': True,
            'job': job_data
        })
        
    except Exception as e:
        logger.error(f"Error getting mass DM job status: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mass-dm/cancel/<job_id>', methods=['POST'])
@requires_admin
def api_cancel_mass_dm(job_id):
    """Cancel a running mass DM job"""
    try:
        if job_id not in dashboard._mass_dm_jobs:
            return jsonify({'success': False, 'error': 'Job not found'})
        
        job = dashboard._mass_dm_jobs[job_id]
        
        if job['status'] in ['completed', 'failed']:
            return jsonify({'success': False, 'error': 'Job already finished'})
        
        # Mark job as cancelled
        dashboard._mass_dm_jobs[job_id]['cancelled'] = True
        dashboard._mass_dm_jobs[job_id]['status'] = 'cancelled'
        dashboard._mass_dm_jobs[job_id]['completed_at'] = datetime.now().isoformat()
        
        logger.info(f"Mass DM job {job_id} cancelled by {session['user']['username']}")
        
        return jsonify({
            'success': True,
            'message': 'Mass DM job cancelled successfully'
        })
        
    except Exception as e:
        logger.error(f"Error cancelling mass DM job: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mass-dm/jobs')
@requires_admin
def api_list_mass_dm_jobs():
    """List all recent mass DM jobs"""
    try:
        # Get jobs from last 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        recent_jobs = []
        for job in dashboard._mass_dm_jobs.values():
            job_created = datetime.fromisoformat(job['created_at'])
            if job_created > cutoff_time:
                job_copy = job.copy()
                # Calculate progress percentage
                if job_copy['total_members'] > 0:
                    job_copy['progress_percentage'] = (job_copy['processed'] / job_copy['total_members']) * 100
                else:
                    job_copy['progress_percentage'] = 0
                recent_jobs.append(job_copy)
        
        # Sort by created time (newest first)
        recent_jobs.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({
            'success': True,
            'jobs': recent_jobs
        })
        
    except Exception as e:
        logger.error(f"Error listing mass DM jobs: {e}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Initialize dashboard on startup
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(dashboard.initialize())
        loop.close()
        logger.info("Dashboard initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize dashboard: {e}")
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)

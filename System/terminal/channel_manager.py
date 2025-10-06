import aiosqlite
import json

class ChannelManager:
    """Manages trusted channels for terminal commands"""

    def __init__(self):
        self.db_path = "Data/terminal_channels.db"
        self.admin_config_path = "Data/terminal_admins.json"

    def load_admin_config(self):
        """Load admin configuration from JSON"""
        try:
            with open(self.admin_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('admins', [])
        except FileNotFoundError:
            return []

    def is_admin(self, discord_id: int) -> bool:
        """Check if user is admin from JSON config"""
        admins = self.load_admin_config()
        return any(admin['discord_id'] == discord_id for admin in admins)

    async def setup_database(self):
        """Initialize channel database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS trusted_channels (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    channel_name TEXT,
                    added_by INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            print("✅ Channel database initialized")

    async def add_trusted_channel(self, channel_id: int, guild_id: int, channel_name: str, added_by: int) -> tuple[bool, str]:
        """Add channel to trusted list"""
        async with aiosqlite.connect(self.db_path) as db:
            
            cursor = await db.execute("SELECT channel_id FROM trusted_channels WHERE channel_id = ?", (channel_id,))
            if await cursor.fetchone():
                return False, f"Channel <#{channel_id}> is already trusted"

            
            await db.execute("""
                INSERT INTO trusted_channels (channel_id, guild_id, channel_name, added_by)
                VALUES (?, ?, ?, ?)
            """, (channel_id, guild_id, channel_name, added_by))
            await db.commit()

            return True, f"Channel <#{channel_id}> added to trusted list"

    async def remove_trusted_channel(self, channel_id: int) -> tuple[bool, str]:
        """Remove channel from trusted list"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT channel_id FROM trusted_channels WHERE channel_id = ?", (channel_id,))
            if not await cursor.fetchone():
                return False, f"Channel <#{channel_id}> is not in trusted list"

            await db.execute("DELETE FROM trusted_channels WHERE channel_id = ?", (channel_id,))
            await db.commit()

            return True, f"Channel <#{channel_id}> removed from trusted list"

    async def is_trusted_channel(self, channel_id: int) -> bool:
        """Check if channel is trusted"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT channel_id FROM trusted_channels WHERE channel_id = ?", (channel_id,))
            return bool(await cursor.fetchone())

    async def get_trusted_channels(self, guild_id: int = None) -> list:
        """Get all trusted channels (optionally filtered by guild)"""
        async with aiosqlite.connect(self.db_path) as db:
            if guild_id:
                cursor = await db.execute("""
                    SELECT channel_id, channel_name, added_at
                    FROM trusted_channels
                    WHERE guild_id = ?
                    ORDER BY added_at DESC
                """, (guild_id,))
            else:
                cursor = await db.execute("""
                    SELECT channel_id, channel_name, added_at
                    FROM trusted_channels
                    ORDER BY added_at DESC
                """)

            return await cursor.fetchall()

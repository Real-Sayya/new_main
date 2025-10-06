import aiosqlite
import discord
from datetime import datetime, timedelta
import json

class ModerationManager:
    """Handles moderation database and logic"""

    def __init__(self, bot):
        self.bot = bot
        self.db_path = "Data/moderation.db"

    async def setup_database(self):
        """Initialize moderation database"""
        async with aiosqlite.connect(self.db_path) as db:
            # Cases table - stores all moderation actions
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cases (
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    reason TEXT,
                    duration TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    active INTEGER DEFAULT 1
                )
            """)

            # Warnings table - tracks user warnings count
            await db.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    warn_count INTEGER DEFAULT 0,
                    last_warn_at DATETIME
                )
            """)

            # Mod logs table - detailed action logs
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mod_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER,
                    guild_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(case_id) REFERENCES cases(case_id)
                )
            """)

            await db.commit()
            print("✅ Moderation database initialized")

    async def create_case(self, guild_id: int, user_id: int, moderator_id: int,
                         action_type: str, reason: str = None, duration: str = None) -> int:
        """Create a new moderation case"""
        async with aiosqlite.connect(self.db_path) as db:
            expires_at = None
            if duration:
                expires_at = self._parse_duration(duration)

            cursor = await db.execute("""
                INSERT INTO cases (guild_id, user_id, moderator_id, action_type, reason, duration, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, moderator_id, action_type, reason, duration, expires_at))

            await db.commit()
            case_id = cursor.lastrowid

            # Log the action
            await self._log_action(case_id, guild_id, action_type,
                                  f"User: {user_id}, Mod: {moderator_id}, Reason: {reason}")

            return case_id

    async def add_warning(self, guild_id: int, user_id: int) -> int:
        """Add a warning to a user and return new warn count"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if user exists
            cursor = await db.execute("""
                SELECT warn_count FROM warnings WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))

            result = await cursor.fetchone()

            if result:
                new_count = result[0] + 1
                await db.execute("""
                    UPDATE warnings
                    SET warn_count = ?, last_warn_at = ?
                    WHERE user_id = ? AND guild_id = ?
                """, (new_count, datetime.now(), user_id, guild_id))
            else:
                new_count = 1
                await db.execute("""
                    INSERT INTO warnings (user_id, guild_id, warn_count, last_warn_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, guild_id, new_count, datetime.now()))

            await db.commit()
            return new_count

    async def remove_warning(self, guild_id: int, user_id: int) -> tuple[bool, int]:
        """Remove a warning from a user, returns (success, new_count)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT warn_count FROM warnings WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))

            result = await cursor.fetchone()

            if not result or result[0] <= 0:
                return False, 0

            new_count = result[0] - 1
            await db.execute("""
                UPDATE warnings
                SET warn_count = ?, last_warn_at = ?
                WHERE user_id = ? AND guild_id = ?
            """, (new_count, datetime.now(), user_id, guild_id))

            await db.commit()
            return True, new_count

    async def get_warning_count(self, guild_id: int, user_id: int) -> int:
        """Get warning count for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT warn_count FROM warnings WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))

            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_user_cases(self, guild_id: int, user_id: int, limit: int = 10) -> list:
        """Get moderation history for a user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT case_id, action_type, reason, moderator_id, timestamp, duration, active
                FROM cases
                WHERE guild_id = ? AND user_id = ?
                ORDER BY case_id DESC
                LIMIT ?
            """, (guild_id, user_id, limit))

            return await cursor.fetchall()

    async def get_all_logs(self, guild_id: int, limit: int = 50) -> list:
        """Get all moderation logs for terminal logging"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT log_id, case_id, action, details, timestamp
                FROM mod_logs
                WHERE guild_id = ?
                ORDER BY log_id DESC
                LIMIT ?
            """, (guild_id, limit))

            return await cursor.fetchall()

    async def deactivate_case(self, case_id: int):
        """Deactivate a case (for unbans, unmutes, etc.)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE cases SET active = 0 WHERE case_id = ?
            """, (case_id,))
            await db.commit()

    async def _log_action(self, case_id: int, guild_id: int, action: str, details: str):
        """Internal: Log an action to mod_logs"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO mod_logs (case_id, guild_id, action, details)
                VALUES (?, ?, ?, ?)
            """, (case_id, guild_id, action, details))
            await db.commit()

    def _parse_duration(self, duration_str: str) -> str:
        """Parse duration string (e.g., '1d', '2h', '30m') to ISO datetime"""
        try:
            amount = int(duration_str[:-1])
            unit = duration_str[-1].lower()

            if unit == 'd':
                delta = timedelta(days=amount)
            elif unit == 'h':
                delta = timedelta(hours=amount)
            elif unit == 'm':
                delta = timedelta(minutes=amount)
            elif unit == 'w':
                delta = timedelta(weeks=amount)
            else:
                return None

            return (datetime.now() + delta).isoformat()
        except:
            return None

    def format_duration(self, duration_str: str) -> str:
        """Format duration for display"""
        if not duration_str:
            return "Permanent"

        try:
            amount = duration_str[:-1]
            unit = duration_str[-1].lower()
            unit_names = {'d': 'day(s)', 'h': 'hour(s)', 'm': 'minute(s)', 'w': 'week(s)'}
            return f"{amount} {unit_names.get(unit, unit)}"
        except:
            return duration_str

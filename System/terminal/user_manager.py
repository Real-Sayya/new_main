import aiosqlite
import bcrypt
import json
import discord
from datetime import datetime, timedelta
from pathlib import Path

class UserManager:
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "Data/terminal_users.db"
        self.config_path = "Data/terminal_config.json"
        self.admin_config_path = "Data/terminal_admins.json"
        self.config = self.load_config()
        self.sessions = {}  # {discord_id: {'username': str, 'role': str, 'login_time': datetime, 'current_dir': str}}

    def load_config(self):
        """Load configuration from JSON"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_config(self):
        """Save configuration to JSON"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)

    def load_admin_config(self):
        """Load admin configuration from JSON"""
        try:
            with open(self.admin_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('admins', [])
        except FileNotFoundError:
            return []

    def is_admin_by_discord_id(self, discord_id: int) -> bool:
        """Check if user is admin from JSON config"""
        admins = self.load_admin_config()
        return any(admin['discord_id'] == discord_id for admin in admins)

    async def setup_database(self):
        """Initialize user database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    discord_id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    failed_login_attempts INTEGER DEFAULT 0,
                    locked_until TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS login_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER,
                    username TEXT,
                    action TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success INTEGER DEFAULT 1
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    discord_id INTEGER PRIMARY KEY,
                    reset_code TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    attempts INTEGER DEFAULT 0
                )
            """)

            await db.commit()
            print("✅ User database initialized")

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    async def register_user(self, discord_id: int, username: str, password: str, role: str = 'user') -> tuple[bool, str]:
        """
        Register a new user
        Returns: (success: bool, message: str)
        """
        # Validate username
        if len(username) < 3:
            return False, "Username must be at least 3 characters long"

        if not username.isalnum():
            return False, "Username must be alphanumeric"

        # Validate password
        min_length = self.config['settings']['password_min_length']
        if len(password) < min_length:
            return False, f"Password must be at least {min_length} characters long"

        # Hash password
        password_hash = self.hash_password(password)

        async with aiosqlite.connect(self.db_path) as db:
            # Check if user already exists
            cursor = await db.execute("SELECT discord_id FROM users WHERE discord_id = ?", (discord_id,))
            if await cursor.fetchone():
                return False, "You already have an account. Use 'login' instead."

            # Check if username is taken
            cursor = await db.execute("SELECT username FROM users WHERE username = ?", (username,))
            if await cursor.fetchone():
                return False, f"Username '{username}' is already taken"

            # Check if user is admin from JSON config
            if self.is_admin_by_discord_id(discord_id):
                role = 'admin'

            # Insert new user
            try:
                await db.execute("""
                    INSERT INTO users (discord_id, username, password_hash, role)
                    VALUES (?, ?, ?, ?)
                """, (discord_id, username, password_hash, role))
                await db.commit()

                # Log registration
                await db.execute("""
                    INSERT INTO login_history (discord_id, username, action)
                    VALUES (?, ?, 'register')
                """, (discord_id, username))
                await db.commit()

                return True, f"Account created successfully! Username: {username}\nUse 'login' to access the terminal."

            except Exception as e:
                return False, f"Registration failed: {str(e)}"

    async def login_user_with_username(self, discord_id: int, username: str, password: str, guild: discord.Guild) -> tuple[bool, str]:
        """
        Login user with username and password validation
        Returns: (success: bool, message: str)
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Get user data by discord_id
            cursor = await db.execute("""
                SELECT username, password_hash, role, failed_login_attempts, locked_until
                FROM users WHERE discord_id = ?
            """, (discord_id,))
            user_data = await cursor.fetchone()

            if not user_data:
                return False, "No account found. Use 'register' to create one."

            db_username, password_hash, role, failed_attempts, locked_until = user_data

            # Verify username matches
            if db_username != username:
                return False, f"Incorrect username. Your account is registered as '{db_username}'"

            # Check if account is locked
            if locked_until:
                lock_time = datetime.fromisoformat(locked_until)
                if datetime.now() < lock_time:
                    remaining = (lock_time - datetime.now()).seconds // 60
                    return False, f"Account locked. Try again in {remaining} minutes."
                else:
                    # Unlock account
                    await db.execute("UPDATE users SET locked_until = NULL, failed_login_attempts = 0 WHERE discord_id = ?", (discord_id,))
                    await db.commit()

            # Verify password
            if not self.verify_password(password, password_hash):
                failed_attempts += 1
                await db.execute("UPDATE users SET failed_login_attempts = ? WHERE discord_id = ?", (failed_attempts, discord_id))

                max_attempts = self.config['settings']['max_failed_login_attempts']
                if failed_attempts >= max_attempts:
                    # Lock account for 15 minutes
                    lock_until = datetime.now() + timedelta(minutes=15)
                    await db.execute("UPDATE users SET locked_until = ? WHERE discord_id = ?", (lock_until, discord_id))
                    await db.commit()
                    return False, f"Account locked due to {max_attempts} failed login attempts. Try again in 15 minutes."

                await db.commit()
                await db.execute("INSERT INTO login_history (discord_id, username, action, success) VALUES (?, ?, 'login', 0)", (discord_id, username))
                await db.commit()

                remaining = max_attempts - failed_attempts
                return False, f"Incorrect password. {remaining} attempts remaining."

            # Reset failed attempts
            await db.execute("UPDATE users SET failed_login_attempts = 0, last_login = ? WHERE discord_id = ?", (datetime.now(), discord_id))
            await db.commit()

            # Log successful login
            await db.execute("INSERT INTO login_history (discord_id, username, action) VALUES (?, ?, 'login')", (discord_id, username))
            await db.commit()

        # Create session
        self.sessions[discord_id] = {
            'username': username,
            'role': role,
            'login_time': datetime.now(),
            'current_dir': f'/home/{username}'
        }

        # Assign Discord role
        member = guild.get_member(discord_id)
        if member:
            await self.assign_discord_role(member, role)

        return True, f"Welcome back, {username}! You are now logged in.\nCurrent directory: /home/{username}"

    async def login_user(self, discord_id: int, password: str, guild: discord.Guild) -> tuple[bool, str]:
        """
        Login user and create session (legacy method for backwards compatibility)
        Returns: (success: bool, message: str)
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Get user data
            cursor = await db.execute("""
                SELECT username, password_hash, role, failed_login_attempts, locked_until
                FROM users WHERE discord_id = ?
            """, (discord_id,))
            user_data = await cursor.fetchone()

            if not user_data:
                return False, "No account found. Use 'register' to create one."

            username, password_hash, role, failed_attempts, locked_until = user_data

            # Check if account is locked
            if locked_until:
                lock_time = datetime.fromisoformat(locked_until)
                if datetime.now() < lock_time:
                    remaining = (lock_time - datetime.now()).seconds // 60
                    return False, f"Account locked. Try again in {remaining} minutes."
                else:
                    # Unlock account
                    await db.execute("UPDATE users SET locked_until = NULL, failed_login_attempts = 0 WHERE discord_id = ?", (discord_id,))
                    await db.commit()

            # Verify password
            if not self.verify_password(password, password_hash):
                failed_attempts += 1
                await db.execute("UPDATE users SET failed_login_attempts = ? WHERE discord_id = ?", (failed_attempts, discord_id))

                max_attempts = self.config['settings']['max_failed_login_attempts']
                if failed_attempts >= max_attempts:
                    # Lock account for 15 minutes
                    lock_until = datetime.now() + timedelta(minutes=15)
                    await db.execute("UPDATE users SET locked_until = ? WHERE discord_id = ?", (lock_until, discord_id))
                    await db.commit()
                    return False, f"Account locked due to {max_attempts} failed login attempts. Try again in 15 minutes."

                await db.commit()
                await db.execute("INSERT INTO login_history (discord_id, username, action, success) VALUES (?, ?, 'login', 0)", (discord_id, username))
                await db.commit()

                remaining = max_attempts - failed_attempts
                return False, f"Incorrect password. {remaining} attempts remaining."

            # Reset failed attempts
            await db.execute("UPDATE users SET failed_login_attempts = 0, last_login = ? WHERE discord_id = ?", (datetime.now(), discord_id))
            await db.commit()

            # Log successful login
            await db.execute("INSERT INTO login_history (discord_id, username, action) VALUES (?, ?, 'login')", (discord_id, username))
            await db.commit()

        # Create session
        self.sessions[discord_id] = {
            'username': username,
            'role': role,
            'login_time': datetime.now(),
            'current_dir': f'/home/{username}'
        }

        # Assign Discord role
        member = guild.get_member(discord_id)
        if member:
            await self.assign_discord_role(member, role)

        return True, f"Welcome back, {username}! You are now logged in.\nCurrent directory: /home/{username}"

    async def logout_user(self, discord_id: int, guild: discord.Guild) -> tuple[bool, str]:
        """
        Logout user and remove session
        Returns: (success: bool, message: str)
        """
        if discord_id not in self.sessions:
            return False, "You are not logged in."

        username = self.sessions[discord_id]['username']
        role = self.sessions[discord_id]['role']

        # Remove session
        del self.sessions[discord_id]

        # Remove Discord role
        member = guild.get_member(discord_id)
        if member:
            await self.remove_discord_role(member, role)

        # Log logout
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO login_history (discord_id, username, action) VALUES (?, ?, 'logout')", (discord_id, username))
            await db.commit()

        return True, f"Goodbye, {username}! You have been logged out."

    async def assign_discord_role(self, member: discord.Member, role_type: str):
        """Assign Discord role based on user role"""
        role_id = self.config['discord_roles'].get(f'terminal_{role_type}')
        if not role_id:
            print(f"⚠️ No Discord role configured for 'terminal_{role_type}'")
            return

        role = member.guild.get_role(role_id)
        if role:
            await member.add_roles(role)
            print(f"✅ Assigned role '{role.name}' to {member.name}")

    async def remove_discord_role(self, member: discord.Member, role_type: str):
        """Remove Discord role"""
        role_id = self.config['discord_roles'].get(f'terminal_{role_type}')
        if not role_id:
            return

        role = member.guild.get_role(role_id)
        if role:
            await member.remove_roles(role)
            print(f"✅ Removed role '{role.name}' from {member.name}")

    def is_logged_in(self, discord_id: int) -> bool:
        """Check if user is logged in"""
        return discord_id in self.sessions

    def get_session(self, discord_id: int) -> dict:
        """Get user session data"""
        return self.sessions.get(discord_id)

    async def get_user_role(self, discord_id: int) -> str:
        """Get user role from database"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT role FROM users WHERE discord_id = ?", (discord_id,))
            result = await cursor.fetchone()
            return result[0] if result else None

    async def change_password(self, discord_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
        """Change user password"""
        min_length = self.config['settings']['password_min_length']
        if len(new_password) < min_length:
            return False, f"New password must be at least {min_length} characters long"

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT password_hash FROM users WHERE discord_id = ?", (discord_id,))
            result = await cursor.fetchone()

            if not result:
                return False, "User not found"

            password_hash = result[0]

            # Verify old password
            if not self.verify_password(old_password, password_hash):
                return False, "Incorrect current password"

            # Update password
            new_hash = self.hash_password(new_password)
            await db.execute("UPDATE users SET password_hash = ? WHERE discord_id = ?", (new_hash, discord_id))
            await db.commit()

            return True, "Password changed successfully"

    async def check_session_timeout(self):
        """Check and remove expired sessions"""
        timeout_minutes = self.config['settings']['session_timeout_minutes']
        timeout_duration = timedelta(minutes=timeout_minutes)

        expired_sessions = []
        for discord_id, session in self.sessions.items():
            if datetime.now() - session['login_time'] > timeout_duration:
                expired_sessions.append(discord_id)

        for discord_id in expired_sessions:
            del self.sessions[discord_id]
            print(f"⏱️ Session expired for user {discord_id}")

    def update_current_directory(self, discord_id: int, new_dir: str):
        """Update user's current directory in session"""
        if discord_id in self.sessions:
            self.sessions[discord_id]['current_dir'] = new_dir

    def get_current_directory(self, discord_id: int) -> str:
        """Get user's current directory"""
        session = self.sessions.get(discord_id)
        return session['current_dir'] if session else None

    async def generate_reset_code(self, discord_id: int) -> tuple[bool, str]:
        """
        Generate a password reset code for user
        Returns: (success: bool, message/code: str)
        """
        import random
        import string

        # Check if user exists
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT username FROM users WHERE discord_id = ?", (discord_id,))
            user = await cursor.fetchone()

            if not user:
                return False, "No account found. Use 'register' to create one."

            # Generate 6-digit code
            reset_code = ''.join(random.choices(string.digits, k=6))
            expires_at = datetime.now() + timedelta(minutes=10)

            # Store reset code (replace existing if any)
            await db.execute("""
                INSERT OR REPLACE INTO password_reset_tokens (discord_id, reset_code, expires_at, attempts)
                VALUES (?, ?, ?, 0)
            """, (discord_id, reset_code, expires_at))
            await db.commit()

            return True, reset_code

    async def reset_password_with_code(self, discord_id: int, code: str, new_password: str) -> tuple[bool, str]:
        """
        Reset password using verification code
        Returns: (success: bool, message: str)
        """
        # Validate new password
        min_length = self.config['settings']['password_min_length']
        if len(new_password) < min_length:
            return False, f"New password must be at least {min_length} characters long"

        async with aiosqlite.connect(self.db_path) as db:
            # Get reset token
            cursor = await db.execute("""
                SELECT reset_code, expires_at, attempts FROM password_reset_tokens
                WHERE discord_id = ?
            """, (discord_id,))
            token_data = await cursor.fetchone()

            if not token_data:
                return False, "No reset request found. Use 'resetpw' to request a reset."

            stored_code, expires_at, attempts = token_data

            # Check expiry
            expiry_time = datetime.fromisoformat(expires_at)
            if datetime.now() > expiry_time:
                await db.execute("DELETE FROM password_reset_tokens WHERE discord_id = ?", (discord_id,))
                await db.commit()
                return False, "Reset code expired. Use 'resetpw' to request a new one."

            # Check attempts (max 3)
            if attempts >= 3:
                await db.execute("DELETE FROM password_reset_tokens WHERE discord_id = ?", (discord_id,))
                await db.commit()
                return False, "Too many failed attempts. Use 'resetpw' to request a new code."

            # Verify code
            if code != stored_code:
                attempts += 1
                await db.execute("UPDATE password_reset_tokens SET attempts = ? WHERE discord_id = ?", (attempts, discord_id))
                await db.commit()
                remaining = 3 - attempts
                return False, f"Incorrect reset code. {remaining} attempts remaining."

            # Reset password
            new_hash = self.hash_password(new_password)
            await db.execute("""
                UPDATE users
                SET password_hash = ?, failed_login_attempts = 0, locked_until = NULL
                WHERE discord_id = ?
            """, (new_hash, discord_id))

            # Delete reset token
            await db.execute("DELETE FROM password_reset_tokens WHERE discord_id = ?", (discord_id,))
            await db.commit()

            # Log password reset
            cursor = await db.execute("SELECT username FROM users WHERE discord_id = ?", (discord_id,))
            username = (await cursor.fetchone())[0]
            await db.execute("""
                INSERT INTO login_history (discord_id, username, action)
                VALUES (?, ?, 'password_reset')
            """, (discord_id, username))
            await db.commit()

            return True, "Password reset successfully! You can now login with your new password."

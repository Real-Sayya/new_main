import discord
from functools import wraps

class PermissionManager:
    """Manages command permissions and role checks"""

    def __init__(self, user_manager):
        self.user_manager = user_manager

    def require_login(self, func):
        """Decorator: Require user to be logged in"""
        @wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            if not self.user_manager.is_logged_in(ctx.author.id):
                await ctx.send("❌ You must be logged in to use this command. Use 'login' first.")
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper

    def require_admin(self, func):
        """Decorator: Require admin role"""
        @wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            session = self.user_manager.get_session(ctx.author.id)
            if not session:
                await ctx.send("❌ You must be logged in.")
                return

            if session['role'] != 'admin':
                await ctx.send("❌ This command requires admin privileges. Use 'sudo' if you have permissions.")
                return

            return await func(self, ctx, *args, **kwargs)
        return wrapper

    async def check_command_permission(self, discord_id: int, command: str) -> tuple[bool, str]:
        """
        Check if user has permission to execute command
        Returns: (allowed: bool, message: str)
        """
        
        if not self.user_manager.is_logged_in(discord_id):
            return False, "You must be logged in to use commands"

        session = self.user_manager.get_session(discord_id)
        role = session['role']

        
        admin_commands = [
            'useradd', 'userdel', 'usermod', 'chown', 'chmod',
            'shutdown', 'reboot', 'systemctl'
        ]

        if command in admin_commands and role != 'admin':
            return False, f"Command '{command}' requires admin privileges"

        return True, "OK"

    def is_admin(self, discord_id: int) -> bool:
        """Check if user has admin role"""
        session = self.user_manager.get_session(discord_id)
        return session and session['role'] == 'admin'

    def is_user(self, discord_id: int) -> bool:
        """Check if user has user role"""
        session = self.user_manager.get_session(discord_id)
        return session and session['role'] == 'user'


class SudoManager:
    """Manages sudo command execution with password verification"""

    def __init__(self, user_manager):
        self.user_manager = user_manager
        self.pending_sudo = {}  

    async def request_sudo_password(self, discord_id: int, command: str, args: list):
        """Request password for sudo command"""
        from datetime import datetime

        
        self.pending_sudo[discord_id] = {
            'command': command,
            'args': args,
            'timestamp': datetime.now()
        }

    def get_pending_sudo(self, discord_id: int) -> dict:
        """Get pending sudo request"""
        return self.pending_sudo.get(discord_id)

    def clear_pending_sudo(self, discord_id: int):
        """Clear pending sudo request"""
        if discord_id in self.pending_sudo:
            del self.pending_sudo[discord_id]

    async def verify_sudo_password(self, discord_id: int, password: str) -> tuple[bool, str]:
        """
        Verify password for sudo command (available to ALL users)
        Returns: (success: bool, message: str)
        """
        import aiosqlite

        async with aiosqlite.connect(self.user_manager.db_path) as db:
            cursor = await db.execute("""
                SELECT password_hash FROM users WHERE discord_id = ?
            """, (discord_id,))
            result = await cursor.fetchone()

            if not result:
                return False, "User not found"

            password_hash = result[0]

            
            if not self.user_manager.verify_password(password, password_hash):
                return False, "Incorrect password"

            return True, "Password verified"

    async def verify_root_password(self, discord_id: int, password: str) -> tuple[bool, str]:
        """
        Verify password for root command (only for terminal admins)
        Returns: (success: bool, message: str)
        """
        import aiosqlite

        async with aiosqlite.connect(self.user_manager.db_path) as db:
            cursor = await db.execute("""
                SELECT password_hash, role FROM users WHERE discord_id = ?
            """, (discord_id,))
            result = await cursor.fetchone()

            if not result:
                return False, "User not found"

            password_hash, role = result

            
            if not self.user_manager.verify_password(password, password_hash):
                return False, "Incorrect password"

            
            if role != 'admin':
                return False, "Your account does not have root privileges (terminal admin required)"

            return True, "Root access granted"


def format_output(text: str, success: bool = True) -> str:
    """Format terminal output"""
    from datetime import datetime
    emoji = "✅" if success else "❌"
    timestamp = datetime.now().strftime("%H:%M:%S")
    return f"```\n[{timestamp}] {emoji} {text}\n```"


def format_error(text: str) -> str:
    """Format error message"""
    return format_output(f"Error: {text}", success=False)


def format_code_block(text: str, language: str = "") -> str:
    """Format text in code block"""
    return f"```{language}\n{text}\n```"

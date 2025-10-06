from .permissions import format_output, format_error, format_code_block
import aiosqlite

class AdminCommands:
    """Admin-only commands"""

    def __init__(self, user_manager, filesystem, permission_manager, bot):
        self.um = user_manager
        self.fs = filesystem
        self.pm = permission_manager
        self.bot = bot

    async def cmd_useradd(self, discord_id: int, args: list) -> str:
        """Promote existing user to admin/change role (does NOT create new users)"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if session['role'] != 'admin':
            return format_error("Permission denied. Admin privileges required.")

        if not args:
            return format_error("Usage: root useradd <discord_id> [role]\nExample: root useradd 123456789 admin")

        try:
            target_discord_id = int(args[0])
            role = args[1] if len(args) > 1 else 'admin'

            if role not in ['user', 'admin']:
                return format_error("Role must be 'user' or 'admin'")

            # Check if user exists in database
            async with aiosqlite.connect(self.um.db_path) as db:
                cursor = await db.execute("SELECT username, role FROM users WHERE discord_id = ?", (target_discord_id,))
                result = await cursor.fetchone()

                if not result:
                    # Fetch Discord username for better error message
                    try:
                        discord_user = await self.bot.fetch_user(target_discord_id)
                        discord_name = discord_user.name
                    except:
                        discord_name = "Unknown"

                    return format_error(
                        f"User with Discord ID {target_discord_id} (Discord: {discord_name}) is not registered in the terminal.\n"
                        f"User must register first with 'register' command."
                    )

                username, current_role = result

                # Check if role is already set
                if current_role == role:
                    return format_error(f"User '{username}' already has role '{role}'")

                # Update role
                await db.execute("UPDATE users SET role = ? WHERE discord_id = ?", (role, target_discord_id))
                await db.commit()

                # Update session if user is logged in
                if target_discord_id in self.um.sessions:
                    self.um.sessions[target_discord_id]['role'] = role

                return format_output(
                    f"✅ User role updated successfully\n"
                    f"Discord ID: {target_discord_id}\n"
                    f"Username: {username}\n"
                    f"Old Role: {current_role}\n"
                    f"New Role: {role}"
                )

        except ValueError:
            return format_error("Invalid Discord ID - must be a number")
        except Exception as e:
            return format_error(f"Failed to update user role: {str(e)}")

    async def cmd_userdel(self, discord_id: int, args: list) -> str:
        """Remove root/admin rights from user (does NOT delete the user account)"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if session['role'] != 'admin':
            return format_error("Permission denied. Admin privileges required.")

        if not args:
            return format_error("Usage: root userdel <discord_id>\nExample: root userdel 123456789")

        try:
            target_discord_id = int(args[0])
        except ValueError:
            return format_error("Invalid Discord ID - must be a number")

        # Prevent self-demotion
        if target_discord_id == discord_id:
            return format_error("Cannot remove your own admin rights")

        async with aiosqlite.connect(self.um.db_path) as db:
            # Check if user exists and get current role
            cursor = await db.execute("SELECT username, role FROM users WHERE discord_id = ?", (target_discord_id,))
            result = await cursor.fetchone()

            if not result:
                # Fetch Discord username for better error message
                try:
                    discord_user = await self.bot.fetch_user(target_discord_id)
                    discord_name = discord_user.name
                except:
                    discord_name = "Unknown"

                return format_error(
                    f"User with Discord ID {target_discord_id} (Discord: {discord_name}) is not registered in the terminal.\n"
                    f"User must be registered first."
                )

            username, current_role = result

            # Check if user is already a regular user
            if current_role == 'user':
                return format_error(f"User '{username}' already has role 'user' (no admin rights)")

            # Remove admin rights (set to user)
            await db.execute("UPDATE users SET role = 'user' WHERE discord_id = ?", (target_discord_id,))
            await db.commit()

            # Update session if user is logged in
            if target_discord_id in self.um.sessions:
                self.um.sessions[target_discord_id]['role'] = 'user'

            return format_output(
                f"✅ Admin rights removed successfully\n"
                f"Discord ID: {target_discord_id}\n"
                f"Username: {username}\n"
                f"Old Role: {current_role}\n"
                f"New Role: user"
            )

    async def cmd_usermod(self, discord_id: int, args: list) -> str:
        """Modify user account (admin only)"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if session['role'] != 'admin':
            return format_error("Permission denied. Admin privileges required.")

        if len(args) < 3:
            return format_error("Usage: usermod <username> <field> <value>\nFields: role")

        username = args[0]
        field = args[1]
        value = args[2]

        if field == 'role':
            if value not in ['user', 'admin']:
                return format_error("Role must be 'user' or 'admin'")

            async with aiosqlite.connect(self.um.db_path) as db:
                cursor = await db.execute("SELECT discord_id FROM users WHERE username = ?", (username,))
                result = await cursor.fetchone()

                if not result:
                    return format_error(f"User '{username}' not found")

                await db.execute("UPDATE users SET role = ? WHERE username = ?", (value, username))
                await db.commit()

                # Update session if user is logged in
                target_discord_id = result[0]
                if target_discord_id in self.um.sessions:
                    self.um.sessions[target_discord_id]['role'] = value

                return format_output(f"User '{username}' role changed to '{value}'")
        else:
            return format_error(f"Unknown field: {field}")

    async def cmd_passwd_admin(self, discord_id: int, args: list) -> str:
        """Change user password (admin only)"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if session['role'] != 'admin':
            return format_error("Permission denied. Admin privileges required.")

        if len(args) < 2:
            return format_error("Usage: passwd <username> <new_password>")

        username = args[0]
        new_password = args[1]

        min_length = self.um.config['settings']['password_min_length']
        if len(new_password) < min_length:
            return format_error(f"Password must be at least {min_length} characters long")

        async with aiosqlite.connect(self.um.db_path) as db:
            cursor = await db.execute("SELECT discord_id FROM users WHERE username = ?", (username,))
            result = await cursor.fetchone()

            if not result:
                return format_error(f"User '{username}' not found")

            new_hash = self.um.hash_password(new_password)
            await db.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, username))
            await db.commit()

            return format_output(f"Password for '{username}' changed successfully")

    async def cmd_users(self, discord_id: int, args: list) -> str:
        """List all users (admin only)"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if session['role'] != 'admin':
            return format_error("Permission denied. Admin privileges required.")

        async with aiosqlite.connect(self.um.db_path) as db:
            cursor = await db.execute("""
                SELECT username, role, created_at, last_login
                FROM users
                ORDER BY created_at DESC
            """)
            users = await cursor.fetchall()

            if not users:
                return format_code_block("No users found")

            output = []
            output.append(f"{'USERNAME':<20} {'ROLE':<10} {'CREATED':<20} {'LAST LOGIN':<20}")
            output.append("─" * 75)

            for username, role, created, last_login in users:
                created_str = created[:16] if created else 'N/A'
                login_str = last_login[:16] if last_login else 'Never'
                output.append(f"{username:<20} {role:<10} {created_str:<20} {login_str:<20}")

            return format_code_block('\n'.join(output))

    async def cmd_logs(self, discord_id: int, args: list) -> str:
        """View login history (admin only)"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if session['role'] != 'admin':
            return format_error("Permission denied. Admin privileges required.")

        limit = 20
        if args and args[0].isdigit():
            limit = int(args[0])

        async with aiosqlite.connect(self.um.db_path) as db:
            cursor = await db.execute("""
                SELECT username, action, timestamp, success
                FROM login_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            logs = await cursor.fetchall()

            if not logs:
                return format_code_block("No logs found")

            output = []
            output.append(f"{'USERNAME':<20} {'ACTION':<12} {'TIMESTAMP':<20} {'STATUS':<10}")
            output.append("─" * 70)

            for username, action, timestamp, success in logs:
                status = "✓" if success else "✗"
                time_str = timestamp[:19] if timestamp else 'N/A'
                output.append(f"{username:<20} {action:<12} {time_str:<20} {status:<10}")

            return format_code_block('\n'.join(output))

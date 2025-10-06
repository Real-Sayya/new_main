import discord
from discord.ext import commands
from .terminal.user_manager import UserManager
from .terminal.filesystem import VirtualFilesystem
from .terminal.permissions import PermissionManager, SudoManager, format_output, format_error, format_code_block
from .terminal.basic_commands import BasicCommands
from .terminal.admin_commands import AdminCommands
from .terminal.channel_manager import ChannelManager
from .terminal.modals import RegisterModal, LoginModal, SudoModal, RootModal, PasswdModal, ResetPasswordModal
from .terminal.logger_manager import TerminalLogger
import asyncio

class TerminalCore(commands.Cog):
    """Virtual Terminal System - Main Cog"""

    def __init__(self, bot):
        self.bot = bot

        # Initialize managers
        self.user_manager = UserManager(bot)
        self.filesystem = VirtualFilesystem(bot)
        self.permission_manager = PermissionManager(self.user_manager)
        self.sudo_manager = SudoManager(self.user_manager)
        self.channel_manager = ChannelManager()

        # Initialize command handlers
        self.basic_commands = BasicCommands(self.filesystem, self.user_manager)
        self.admin_commands = AdminCommands(self.user_manager, self.filesystem, self.permission_manager, bot)

        # Valid terminal commands
        self.valid_commands = {
            'register', 'login', 'logout', 'passwd', 'resetpw', 'help',
            'ls', 'cd', 'pwd', 'mkdir', 'touch', 'cat', 'rm', 'echo', 'clear', 'cls', 'whoami', 'tree',
            'mv', 'cp', 'chmod', 'find', 'grep', 'du',
            'sudo', 'root', 'useradd', 'userdel', 'usermod', 'users', 'logs', 'channel',
            'warn', 'kick', 'ban', 'unban', 'timeout', 'untimeout', 'delwarn', 'modlog',
            'role', 'apt'
        }

        print("🖥️  Terminal Core initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize databases when bot is ready"""
        await self.user_manager.setup_database()
        await self.filesystem.setup_database()
        await self.channel_manager.setup_database()
        print("✅ Terminal System ready!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle terminal commands"""
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore DMs (all password inputs now use Modals)
        if isinstance(message.channel, discord.DMChannel):
            return

        # Only process if not a command (! or /)
        if message.content.startswith('!') or message.content.startswith('/'):
            return

        # Parse command
        content = message.content.strip()
        if not content:
            return

        # Check for command aliases
        config = self.user_manager.config
        for alias, actual_command in config.get('command_aliases', {}).items():
            if content.startswith(alias):
                content = content.replace(alias, actual_command, 1)

        parts = content.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # Only process valid terminal commands - ignore normal chat
        if command not in self.valid_commands:
            return

        # Extract context for logging
        server, channel_name, user, guild_id, channel_id, user_id = TerminalLogger.get_context_info(message)

        # Check if channel is trusted (unless it's a channel management command)
        content_preview = content.lower()
        is_channel_command = content_preview.startswith('channel ') or content_preview.startswith('root channel ')

        if not is_channel_command:
            if not await self.channel_manager.is_trusted_channel(message.channel.id):
                # Send error message instead of silent return
                error_msg = format_error(f"This channel is not trusted for terminal commands.\n"
                                f"Ask an admin to run: `root channel trust` in this channel first.")
                await message.channel.send(error_msg)

                # Log the rejected command
                TerminalLogger.log_input(server, channel_name, user, content, guild_id, channel_id, user_id)
                TerminalLogger.log_output(server, channel_name, user, "Channel not trusted - command rejected", success=False)
                return

        # Log the input command
        TerminalLogger.log_input(server, channel_name, user, content, guild_id, channel_id, user_id)

        # Route command
        try:
            response = await self.route_command(message, command, args)
            if response:
                # Log the output
                TerminalLogger.log_output(server, channel_name, user, response, success=True)

                # Split long messages
                if len(response) > 2000:
                    chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await message.channel.send(response)
        except Exception as e:
            error_response = format_error(f"Command failed: {str(e)}")

            # Log the error
            TerminalLogger.log_output(server, channel_name, user, str(e), success=False)

            await message.channel.send(error_response)
            print(f"Error executing command '{command}': {e}")

    async def route_command(self, message: discord.Message, command: str, args: list) -> str:
        """Route command to appropriate handler"""
        discord_id = message.author.id

        # Authentication commands (don't require login)
        if command == 'register':
            return await self.cmd_register(message, args)

        elif command == 'login':
            return await self.cmd_login(message, args)

        elif command == 'help':
            return await self.basic_commands.cmd_help(discord_id, args)

        # Check if user is logged in for all other commands
        if not self.user_manager.is_logged_in(discord_id):
            return format_error("You must be logged in. Use 'register' or 'login'")

        # User commands
        if command == 'logout':
            return await self.cmd_logout(message, args)

        elif command == 'passwd':
            return await self.cmd_passwd(message, args)

        elif command == 'resetpw':
            return await self.cmd_resetpw(message, args)

        # Filesystem commands
        elif command == 'ls':
            return await self.basic_commands.cmd_ls(discord_id, args)

        elif command == 'cd':
            return await self.basic_commands.cmd_cd(discord_id, args)

        elif command == 'pwd':
            return await self.basic_commands.cmd_pwd(discord_id, args)

        elif command == 'mkdir':
            return await self.basic_commands.cmd_mkdir(discord_id, args)

        elif command == 'touch':
            return await self.basic_commands.cmd_touch(discord_id, args)

        elif command == 'cat':
            return await self.basic_commands.cmd_cat(discord_id, args)

        elif command == 'rm':
            return await self.basic_commands.cmd_rm(discord_id, args)

        elif command == 'echo':
            return await self.basic_commands.cmd_echo(discord_id, args)

        elif command == 'clear' or command == 'cls':
            return format_error(f"Permission denied. Use 'sudo {command}' to execute this command.")

        elif command == 'whoami':
            return await self.basic_commands.cmd_whoami(discord_id, args)

        elif command == 'tree':
            return await self.basic_commands.cmd_tree(discord_id, args)

        elif command == 'mv':
            return await self.basic_commands.cmd_mv(discord_id, args)

        elif command == 'cp':
            return await self.basic_commands.cmd_cp(discord_id, args)

        elif command == 'chmod':
            return await self.basic_commands.cmd_chmod(discord_id, args)

        elif command == 'find':
            return await self.basic_commands.cmd_find(discord_id, args)

        elif command == 'grep':
            return await self.basic_commands.cmd_grep(discord_id, args)

        elif command == 'du':
            return await self.basic_commands.cmd_du(discord_id, args)

        # APT Package Manager (requires sudo)
        elif command == 'apt':
            return format_error("Permission denied. Use 'sudo apt' to execute APT commands.")

        # Sudo command (available to all users)
        elif command == 'sudo':
            return await self.cmd_sudo(message, args)

        # Root command (only for terminal admins)
        elif command == 'root':
            return await self.cmd_root(message, args)

        # Admin commands (require root)
        elif command in ['useradd', 'userdel', 'usermod', 'users', 'logs']:
            return format_error(f"Permission denied. Use 'root {command}' if you have terminal admin rights.")

        # Moderation commands (require root)
        elif command in ['warn', 'kick', 'ban', 'unban', 'timeout', 'untimeout', 'delwarn', 'modlog']:
            return format_error(f"Permission denied. Use 'root {command}' if you have terminal admin rights.")

        # Role management commands (require root)
        elif command == 'role':
            return format_error("Permission denied. Use 'root role' if you have terminal admin rights.")

        else:
            return format_error(f"Unknown command: {command}\nType 'help' for available commands")

    async def cmd_register(self, message: discord.Message, args: list) -> str:
        """Register new user"""
        # Create button that opens modal
        class RegisterButton(discord.ui.View):
            def __init__(self, user_manager, filesystem):
                super().__init__(timeout=120)
                self.user_manager = user_manager
                self.filesystem = filesystem

            @discord.ui.button(label="Create Account", style=discord.ButtonStyle.primary, emoji="📝")
            async def create_account(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = RegisterModal(self.user_manager, self.filesystem)
                await interaction.response.send_modal(modal)

        view = RegisterButton(self.user_manager, self.filesystem)
        await message.channel.send(
            "📝 **Register New Account**\nClick the button below to create your account:",
            view=view
        )
        return None  # Don't send additional message

    async def cmd_login(self, message: discord.Message, args: list) -> str:
        """Login user"""
        discord_id = message.author.id

        # Check if already logged in
        if self.user_manager.is_logged_in(discord_id):
            session = self.user_manager.get_session(discord_id)
            return format_error(f"Already logged in as {session['username']}")

        # Create button that opens modal
        class LoginButton(discord.ui.View):
            def __init__(self, user_manager):
                super().__init__(timeout=120)
                self.user_manager = user_manager

            @discord.ui.button(label="Enter Password", style=discord.ButtonStyle.primary, emoji="🔐")
            async def enter_password(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = LoginModal(self.user_manager)
                await interaction.response.send_modal(modal)

        view = LoginButton(self.user_manager)
        await message.channel.send(
            "🔐 **Terminal Login**\nClick the button below to enter your password:",
            view=view
        )
        return None  # Don't send additional message

    async def cmd_logout(self, message: discord.Message, args: list) -> str:
        """Logout user"""
        discord_id = message.author.id
        success, msg = await self.user_manager.logout_user(discord_id, message.guild)
        return format_output(msg) if success else format_error(msg)

    async def cmd_passwd(self, message: discord.Message, args: list) -> str:
        """Change password"""
        if not args:
            return format_error("Usage: passwd <new_password>")

        new_password = args[0]

        # Delete original message with new password
        try:
            await message.delete()
        except:
            pass

        # Create button that opens modal
        class PasswdButton(discord.ui.View):
            def __init__(self, user_manager, new_password):
                super().__init__(timeout=120)
                self.user_manager = user_manager
                self.new_password = new_password

            @discord.ui.button(label="Confirm with Current Password", style=discord.ButtonStyle.primary, emoji="🔐")
            async def confirm_passwd(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = PasswdModal(self.user_manager, self.new_password)
                await interaction.response.send_modal(modal)

        view = PasswdButton(self.user_manager, new_password)
        await message.channel.send(
            "🔐 **Change Password**\nClick the button to confirm with your current password:",
            view=view
        )
        return None  # Don't send additional message

    async def cmd_resetpw(self, message: discord.Message, args: list) -> str:
        """Reset password (for forgotten passwords)"""
        discord_id = message.author.id

        # Generate reset code
        success, code = await self.user_manager.generate_reset_code(discord_id)

        if not success:
            return format_error(code)

        # Send code via DM
        try:
            user = message.author
            await user.send(
                f"🔐 **Password Reset Code**\n\n"
                f"Your reset code is: `{code}`\n\n"
                f"This code expires in 10 minutes and can be used up to 3 times.\n"
                f"Click the button in the channel to reset your password."
            )
        except discord.Forbidden:
            return format_error("Cannot send DM. Please enable DMs from server members.")

        # Create button that opens modal
        class ResetPasswordButton(discord.ui.View):
            def __init__(self, user_manager):
                super().__init__(timeout=600)  # 10 minutes
                self.user_manager = user_manager

            @discord.ui.button(label="Reset Password", style=discord.ButtonStyle.danger, emoji="🔐")
            async def reset_password(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = ResetPasswordModal(self.user_manager)
                await interaction.response.send_modal(modal)

        view = ResetPasswordButton(self.user_manager)
        await message.channel.send(
            "🔐 **Password Reset**\nA reset code has been sent to your DMs.\nClick the button below to reset your password:",
            view=view
        )
        return None  # Don't send additional message

    async def cmd_sudo(self, message: discord.Message, args: list) -> str:
        """Execute command with sudo (available to all users)"""
        if not args:
            return format_error("Usage: sudo <command> [args...]\nAvailable: clear, apt")

        discord_id = message.author.id
        command = args[0]
        cmd_args = args[1:] if len(args) > 1 else []

        # Check if user is logged in
        session = self.user_manager.get_session(discord_id)
        if not session:
            return format_error("You must be logged in to use sudo")

        # Validate sudo command
        valid_sudo_commands = ['clear', 'cls', 'apt']
        if command not in valid_sudo_commands:
            return format_error(f"'{command}' is not a sudo command.\nAvailable sudo commands: clear, apt\nFor admin commands, use 'root' instead.")

        # Create button that opens modal
        class SudoButton(discord.ui.View):
            def __init__(self, user_manager, sudo_manager, execute_callback, command, cmd_args, channel_id, guild):
                super().__init__(timeout=120)
                self.user_manager = user_manager
                self.sudo_manager = sudo_manager
                self.execute_callback = execute_callback
                self.command = command
                self.cmd_args = cmd_args
                self.channel_id = channel_id
                self.guild = guild

            @discord.ui.button(label="Confirm with Password", style=discord.ButtonStyle.primary, emoji="🔐")
            async def confirm_sudo(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = SudoModal(
                    self.user_manager,
                    self.sudo_manager,
                    self.execute_callback,
                    self.command,
                    self.cmd_args,
                    self.channel_id,
                    self.guild
                )
                await interaction.response.send_modal(modal)

        view = SudoButton(
            self.user_manager,
            self.sudo_manager,
            self.execute_sudo_command,
            command,
            cmd_args,
            message.channel.id,
            message.guild
        )

        cmd_display = f"{command} {' '.join(cmd_args)}" if cmd_args else command
        await message.channel.send(
            f"🔐 **Sudo Authentication Required**\nCommand: `{cmd_display}`\nClick the button to confirm with your password:",
            view=view
        )
        return None  # Don't send additional message

    async def cmd_root(self, message: discord.Message, args: list) -> str:
        """Execute command with root (only for terminal admins)"""
        if not args:
            return format_error("Usage: root <command> [args...]\nAvailable: warn, kick, ban, role, useradd, etc.")

        discord_id = message.author.id
        command = args[0]
        cmd_args = args[1:] if len(args) > 1 else []

        # Check if user is terminal admin
        role = await self.user_manager.get_user_role(discord_id)
        if role != 'admin':
            return format_error("You do not have root privileges (terminal admin required)")

        # Create button that opens modal
        class RootButton(discord.ui.View):
            def __init__(self, user_manager, sudo_manager, execute_callback, command, cmd_args, channel_id, guild):
                super().__init__(timeout=120)
                self.user_manager = user_manager
                self.sudo_manager = sudo_manager
                self.execute_callback = execute_callback
                self.command = command
                self.cmd_args = cmd_args
                self.channel_id = channel_id
                self.guild = guild

            @discord.ui.button(label="Confirm with Admin Password", style=discord.ButtonStyle.danger, emoji="⚠️")
            async def confirm_root(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = RootModal(
                    self.user_manager,
                    self.sudo_manager,
                    self.execute_callback,
                    self.command,
                    self.cmd_args,
                    self.channel_id,
                    self.guild
                )
                await interaction.response.send_modal(modal)

        view = RootButton(
            self.user_manager,
            self.sudo_manager,
            self.execute_admin_command,
            command,
            cmd_args,
            message.channel.id,
            message.guild
        )

        cmd_display = f"{command} {' '.join(cmd_args)}" if cmd_args else command
        await message.channel.send(
            f"⚠️ **ROOT Authentication Required**\nCommand: `{cmd_display}`\nClick the button to confirm with your admin password:",
            view=view
        )
        return None  # Don't send additional message

    async def execute_admin_command(self, discord_id: int, command: str, args: list, channel_id: int = None, guild: discord.Guild = None) -> str:
        """Execute admin command"""
        if command == 'useradd':
            return await self.admin_commands.cmd_useradd(discord_id, args)
        elif command == 'userdel':
            return await self.admin_commands.cmd_userdel(discord_id, args)
        elif command == 'usermod':
            return await self.admin_commands.cmd_usermod(discord_id, args)
        elif command == 'users':
            return await self.admin_commands.cmd_users(discord_id, args)
        elif command == 'logs':
            return await self.admin_commands.cmd_logs(discord_id, args)
        elif command == 'passwd' and args:  # admin passwd command
            return await self.admin_commands.cmd_passwd_admin(discord_id, args)
        elif command == 'channel':
            return await self.cmd_channel(discord_id, args, channel_id)
        # Moderation commands
        elif command in ['warn', 'kick', 'ban', 'unban', 'timeout', 'untimeout', 'delwarn', 'modlog']:
            return await self.execute_mod_command(discord_id, command, args, guild)
        # Role management commands
        elif command == 'role':
            return await self.execute_role_command(discord_id, command, args, guild, channel_id)
        else:
            return format_error(f"Unknown admin command: {command}")

    async def execute_mod_command(self, discord_id: int, command: str, args: list, guild: discord.Guild) -> str:
        """Execute moderation command"""
        if not guild:
            return format_error("Moderation commands can only be used in a server")

        # Get moderation cog
        mod_cog = self.bot.get_cog("Moderation")
        if not mod_cog:
            return format_error("Moderation system not loaded")

        # Route to appropriate command
        if command == 'warn':
            return await mod_cog.cmd_warn(discord_id, args, guild)
        elif command == 'kick':
            return await mod_cog.cmd_kick(discord_id, args, guild)
        elif command == 'ban':
            return await mod_cog.cmd_ban(discord_id, args, guild)
        elif command == 'unban':
            return await mod_cog.cmd_unban(discord_id, args, guild)
        elif command == 'timeout':
            return await mod_cog.cmd_timeout(discord_id, args, guild)
        elif command == 'untimeout':
            return await mod_cog.cmd_untimeout(discord_id, args, guild)
        elif command == 'delwarn':
            return await mod_cog.cmd_delwarn(discord_id, args, guild)
        elif command == 'modlog':
            return await mod_cog.cmd_modlog(discord_id, args, guild)
        else:
            return format_error(f"Unknown moderation command: {command}")

    async def execute_role_command(self, discord_id: int, command: str, args: list, guild: discord.Guild, channel_id: int = None) -> str:
        """Execute role management command"""
        if not guild:
            return format_error("Role commands can only be used in a server")

        # Get role cog
        role_cog = self.bot.get_cog("Roles")
        if not role_cog:
            return format_error("Role management system not loaded")

        # Get channel object
        channel = None
        if channel_id:
            channel = self.bot.get_channel(channel_id)

        return await role_cog.cmd_role(discord_id, args, guild, channel)

    async def execute_sudo_command(self, discord_id: int, command: str, args: list, channel_id: int = None, guild: discord.Guild = None) -> str:
        """Execute sudo command (available to all users)"""
        # Clear command
        if command == 'clear' or command == 'cls':
            channel = self.bot.get_channel(channel_id) if channel_id else None
            if not channel:
                return format_error("Channel not found")
            return await self.basic_commands.cmd_clear(discord_id, args, channel)

        # APT commands
        elif command == 'apt':
            return await self.execute_apt_command(discord_id, args, guild)

        else:
            return format_error(f"Unknown sudo command: {command}")

    async def execute_apt_command(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Execute APT package manager command"""
        if not guild:
            return format_error("APT commands can only be used in a server")

        # Get APT cog
        apt_cog = self.bot.get_cog("APT")
        if not apt_cog:
            return format_error("APT system not loaded")

        return await apt_cog.cmd_apt(discord_id, args, guild)

    async def cmd_channel(self, discord_id: int, args: list, channel_id: int = None) -> str:
        """Channel management commands (admin only)"""

        # Check if user is admin from JSON
        if not self.channel_manager.is_admin(discord_id):
            return format_error("Permission denied. Only admins can manage channels.")

        if not args:
            return format_error("Usage: root channel <trust|untrust|list>")

        action = args[0].lower()

        # Get channel object
        if not channel_id:
            return format_error("Channel context not available")

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return format_error("Channel not found")

        if action == 'trust':
            # Trust the channel where command was issued
            success, msg = await self.channel_manager.add_trusted_channel(
                channel.id,
                channel.guild.id,
                channel.name,
                discord_id
            )
            return format_output(msg) if success else format_error(msg)

        elif action == 'untrust':
            # Untrust the channel where command was issued
            success, msg = await self.channel_manager.remove_trusted_channel(channel.id)
            return format_output(msg) if success else format_error(msg)

        elif action == 'list':
            # List all trusted channels for this guild
            channels = await self.channel_manager.get_trusted_channels(channel.guild.id)

            if not channels:
                return format_code_block("No trusted channels configured.")

            output = []
            output.append("TRUSTED CHANNELS:")
            output.append("─" * 50)
            for ch_id, ch_name, added_at in channels:
                added_date = added_at[:10] if added_at else 'Unknown'
                output.append(f"<#{ch_id}> ({ch_name}) - Added: {added_date}")

            return format_code_block('\n'.join(output))

        else:
            return format_error(f"Unknown channel action: {action}\nAvailable: trust, untrust, list")


def setup(bot):
    bot.add_cog(TerminalCore(bot))
    print("✅ Terminal Core cog loaded")

import discord
from .permissions import format_output, format_error
from .logger_manager import TerminalLogger

class RegisterModal(discord.ui.Modal):
    """Modal for user registration"""
    def __init__(self, user_manager, filesystem):
        super().__init__(title="Register - Create Account")
        self.user_manager = user_manager
        self.filesystem = filesystem

        self.username = discord.ui.InputText(
            label="Username",
            placeholder="Enter your username",
            min_length=3,
            max_length=20,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.username)

        self.password = discord.ui.InputText(
            label="Password",
            placeholder="Enter your password",
            min_length=6,
            max_length=100,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.password)

    async def callback(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        username = self.username.value
        password = self.password.value

        
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        
        TerminalLogger.log_modal(server, channel, user, "RegisterModal", "SUBMIT", f"Username: {username}")

        
        success, msg = await self.user_manager.register_user(discord_id, username, password, 'user')

        if success:
            
            await self.filesystem.initialize_user_filesystem(discord_id, username)

            
            TerminalLogger.log_auth(server, channel, user, "REGISTER", True, f"Username: {username}")

            await interaction.response.send_message(format_output(msg))
        else:
            
            TerminalLogger.log_auth(server, channel, user, "REGISTER", False, msg)

            await interaction.response.send_message(format_error(msg))


class LoginModal(discord.ui.Modal):
    """Modal for user login"""
    def __init__(self, user_manager):
        super().__init__(title="Login - Terminal Access")
        self.user_manager = user_manager

        self.username = discord.ui.InputText(
            label="Username",
            placeholder="Enter your username",
            min_length=1,
            max_length=20,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.username)

        self.password = discord.ui.InputText(
            label="Password",
            placeholder="Enter your password",
            min_length=1,
            max_length=100,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.password)

    async def callback(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        username = self.username.value
        password = self.password.value

        
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        
        TerminalLogger.log_modal(server, channel, user, "LoginModal", "SUBMIT", f"Username: {username}")

        
        success, msg = await self.user_manager.login_user_with_username(discord_id, username, password, interaction.guild)

        if success:
            
            TerminalLogger.log_auth(server, channel, user, "LOGIN", True, f"Username: {username}")

            await interaction.response.send_message(format_output(msg))
        else:
            
            TerminalLogger.log_auth(server, channel, user, "LOGIN", False, msg)

            await interaction.response.send_message(format_error(msg))


class SudoModal(discord.ui.Modal):
    """Modal for sudo password confirmation (available to all users)"""
    def __init__(self, user_manager, sudo_manager, execute_callback, command, args, channel_id, guild=None):
        super().__init__(title=f"Sudo - Execute '{command}'")
        self.user_manager = user_manager
        self.sudo_manager = sudo_manager
        self.execute_callback = execute_callback
        self.command = command
        self.args = args
        self.channel_id = channel_id
        self.guild = guild

        self.password = discord.ui.InputText(
            label="Enter your password to confirm",
            placeholder="Password",
            min_length=1,
            max_length=100,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.password)

    async def callback(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        password = self.password.value

        
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        
        cmd_string = f"{self.command} {' '.join(self.args)}" if self.args else self.command

        
        TerminalLogger.log_modal(server, channel, user, "SudoModal", "SUBMIT", f"Command: {cmd_string}")

        
        success, msg = await self.sudo_manager.verify_sudo_password(discord_id, password)

        if success:
            
            TerminalLogger.log_sudo(server, channel, user, cmd_string, True)

            
            response = await self.execute_callback(discord_id, self.command, self.args, self.channel_id, self.guild)

            
            TerminalLogger.log_output(server, channel, user, response, success=True)

            await interaction.response.send_message(
                f"✅ Sudo command executed\n{response}"
            )
        else:
            
            TerminalLogger.log_sudo(server, channel, user, cmd_string, False)

            await interaction.response.send_message(format_error(msg))


class RootModal(discord.ui.Modal):
    """Modal for root password confirmation (only for terminal admins)"""
    def __init__(self, user_manager, sudo_manager, execute_callback, command, args, channel_id, guild=None):
        super().__init__(title=f"Root - Execute '{command}'")
        self.user_manager = user_manager
        self.sudo_manager = sudo_manager
        self.execute_callback = execute_callback
        self.command = command
        self.args = args
        self.channel_id = channel_id
        self.guild = guild

        self.password = discord.ui.InputText(
            label="Enter your admin password to confirm",
            placeholder="Password (Terminal Admin Required)",
            min_length=1,
            max_length=100,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.password)

    async def callback(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        password = self.password.value

        
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        
        cmd_string = f"{self.command} {' '.join(self.args)}" if self.args else self.command

        
        TerminalLogger.log_modal(server, channel, user, "RootModal", "SUBMIT", f"Command: {cmd_string}")

        
        success, msg = await self.sudo_manager.verify_root_password(discord_id, password)

        if success:
            
            TerminalLogger.log_sudo(server, channel, user, f"ROOT: {cmd_string}", True)

            
            response = await self.execute_callback(discord_id, self.command, self.args, self.channel_id, self.guild)

            
            TerminalLogger.log_output(server, channel, user, response, success=True)

            await interaction.response.send_message(
                f"✅ Root command executed\n{response}"
            )
        else:
            
            TerminalLogger.log_sudo(server, channel, user, f"ROOT: {cmd_string}", False)

            await interaction.response.send_message(format_error(msg))


class PasswdModal(discord.ui.Modal):
    """Modal for password change"""
    def __init__(self, user_manager, new_password):
        super().__init__(title="Change Password - Confirm")
        self.user_manager = user_manager
        self.new_password = new_password

        self.current_password = discord.ui.InputText(
            label="Current Password",
            placeholder="Enter your current password",
            min_length=1,
            max_length=100,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.current_password)

    async def callback(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        old_password = self.current_password.value

        
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        
        TerminalLogger.log_modal(server, channel, user, "PasswdModal", "SUBMIT", "Password change request")

        
        success, msg = await self.user_manager.change_password(discord_id, old_password, self.new_password)

        if success:
            
            TerminalLogger.log_auth(server, channel, user, "PASSWD", True, "Password changed")

            await interaction.response.send_message(format_output(msg))
        else:
            
            TerminalLogger.log_auth(server, channel, user, "PASSWD", False, msg)

            await interaction.response.send_message(format_error(msg))


class ResetPasswordModal(discord.ui.Modal):
    """Modal for password reset with verification code"""
    def __init__(self, user_manager):
        super().__init__(title="Reset Password")
        self.user_manager = user_manager

        self.reset_code = discord.ui.InputText(
            label="Reset Code (check your DMs)",
            placeholder="Enter the 6-digit code",
            min_length=6,
            max_length=6,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.reset_code)

        self.new_password = discord.ui.InputText(
            label="New Password",
            placeholder="Enter your new password",
            min_length=6,
            max_length=100,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.new_password)

    async def callback(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        code = self.reset_code.value
        new_password = self.new_password.value

        
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        
        TerminalLogger.log_modal(server, channel, user, "ResetPasswordModal", "SUBMIT", "Password reset with code")

        
        success, msg = await self.user_manager.reset_password_with_code(discord_id, code, new_password)

        if success:
            
            TerminalLogger.log_auth(server, channel, user, "RESETPW", True, "Password reset successful")

            await interaction.response.send_message(format_output(msg))
        else:
            
            TerminalLogger.log_auth(server, channel, user, "RESETPW", False, msg)

            await interaction.response.send_message(format_error(msg))

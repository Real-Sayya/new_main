import datetime
from typing import Optional
import discord

class TerminalLogger:
    """Centralized logging system for all terminal activities"""

    
    COLORS = {
        'RESET': '\033[0m',
        'BOLD': '\033[1m',
        'RED': '\033[91m',
        'GREEN': '\033[92m',
        'YELLOW': '\033[93m',
        'BLUE': '\033[94m',
        'MAGENTA': '\033[95m',
        'CYAN': '\033[96m',
        'WHITE': '\033[97m',
        'GRAY': '\033[90m',
    }

    @staticmethod
    def _get_timestamp() -> str:
        """Get formatted timestamp"""
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _format_log(
        log_type: str,
        server: str,
        channel: str,
        user: str,
        message: str,
        color: str = 'WHITE'
    ) -> str:
        """Format a log message"""
        timestamp = TerminalLogger._get_timestamp()
        c = TerminalLogger.COLORS

        formatted = (
            f"{c['GRAY']}[{timestamp}]{c['RESET']} "
            f"{c['BOLD']}{c[color]}[{log_type}]{c['RESET']} "
            f"{c['CYAN']}Server:{c['RESET']} {server} | "
            f"{c['BLUE']}Channel:{c['RESET']} {channel} | "
            f"{c['MAGENTA']}User:{c['RESET']} {user}\n"
            f"    {c['WHITE']}→ {message}{c['RESET']}"
        )

        return formatted

    @classmethod
    def log_input(
        cls,
        server: str,
        channel: str,
        user: str,
        command: str,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> None:
        """Log user input/command"""
        log_msg = cls._format_log(
            log_type="INPUT",
            server=server,
            channel=channel,
            user=user,
            message=command,
            color='YELLOW'
        )

        print(log_msg)

        
        if guild_id or channel_id or user_id:
            c = cls.COLORS
            id_info = f"{c['GRAY']}    IDs: "
            if guild_id:
                id_info += f"Guild={guild_id} "
            if channel_id:
                id_info += f"Channel={channel_id} "
            if user_id:
                id_info += f"User={user_id}"
            id_info += f"{c['RESET']}"
            print(id_info)

    @classmethod
    def log_output(
        cls,
        server: str,
        channel: str,
        user: str,
        response: str,
        success: bool = True
    ) -> None:
        """Log bot output/response"""
        
        display_response = response
        if len(response) > 200:
            display_response = response[:200] + "... [truncated]"

        
        display_response = display_response.replace('```', '').strip()

        color = 'GREEN' if success else 'RED'
        log_type = "OUTPUT" if success else "ERROR"

        log_msg = cls._format_log(
            log_type=log_type,
            server=server,
            channel=channel,
            user=user,
            message=display_response,
            color=color
        )

        print(log_msg)

    @classmethod
    def log_command(
        cls,
        server: str,
        channel: str,
        user: str,
        command_type: str,
        details: str
    ) -> None:
        """Log specific command execution (mod, role, etc.)"""
        log_msg = cls._format_log(
            log_type=f"CMD:{command_type.upper()}",
            server=server,
            channel=channel,
            user=user,
            message=details,
            color='CYAN'
        )

        print(log_msg)

    @classmethod
    def log_modal(
        cls,
        server: str,
        channel: str,
        user: str,
        modal_name: str,
        action: str,
        details: str = ""
    ) -> None:
        """Log modal interactions"""
        message = f"Modal: {modal_name} | Action: {action}"
        if details:
            message += f" | {details}"

        log_msg = cls._format_log(
            log_type="MODAL",
            server=server,
            channel=channel,
            user=user,
            message=message,
            color='MAGENTA'
        )

        print(log_msg)

    @classmethod
    def log_sudo(
        cls,
        server: str,
        channel: str,
        user: str,
        command: str,
        success: bool
    ) -> None:
        """Log sudo command attempts"""
        status = "SUCCESS" if success else "FAILED"
        color = 'GREEN' if success else 'RED'

        log_msg = cls._format_log(
            log_type=f"SUDO:{status}",
            server=server,
            channel=channel,
            user=user,
            message=f"Command: {command}",
            color=color
        )

        print(log_msg)

    @classmethod
    def log_auth(
        cls,
        server: str,
        channel: str,
        user: str,
        action: str,
        success: bool,
        details: str = ""
    ) -> None:
        """Log authentication events (login, register, etc.)"""
        status = "SUCCESS" if success else "FAILED"
        color = 'GREEN' if success else 'RED'

        message = f"Auth: {action} - {status}"
        if details:
            message += f" | {details}"

        log_msg = cls._format_log(
            log_type="AUTH",
            server=server,
            channel=channel,
            user=user,
            message=message,
            color=color
        )

        print(log_msg)

    @classmethod
    def log_moderation(
        cls,
        server: str,
        moderator: str,
        action: str,
        target_user: str,
        reason: str = "",
        case_id: Optional[int] = None
    ) -> None:
        """Log moderation actions"""
        message = f"Action: {action.upper()} | Target: {target_user}"
        if reason:
            message += f" | Reason: {reason}"
        if case_id:
            message += f" | Case: #{case_id}"

        c = cls.COLORS
        timestamp = cls._get_timestamp()

        formatted = (
            f"{c['GRAY']}[{timestamp}]{c['RESET']} "
            f"{c['BOLD']}{c['RED']}[MODERATION]{c['RESET']} "
            f"{c['CYAN']}Server:{c['RESET']} {server} | "
            f"{c['MAGENTA']}Moderator:{c['RESET']} {moderator}\n"
            f"    {c['WHITE']}→ {message}{c['RESET']}"
        )

        print(formatted)

    @classmethod
    def log_role_action(
        cls,
        server: str,
        admin: str,
        action: str,
        role_name: str,
        target_user: Optional[str] = None,
        details: str = ""
    ) -> None:
        """Log role management actions"""
        message = f"Action: {action.upper()} | Role: {role_name}"
        if target_user:
            message += f" | Target: {target_user}"
        if details:
            message += f" | {details}"

        c = cls.COLORS
        timestamp = cls._get_timestamp()

        formatted = (
            f"{c['GRAY']}[{timestamp}]{c['RESET']} "
            f"{c['BOLD']}{c['BLUE']}[ROLE]{c['RESET']} "
            f"{c['CYAN']}Server:{c['RESET']} {server} | "
            f"{c['MAGENTA']}Admin:{c['RESET']} {admin}\n"
            f"    {c['WHITE']}→ {message}{c['RESET']}"
        )

        print(formatted)

    @classmethod
    def log_system(
        cls,
        message: str,
        level: str = "INFO"
    ) -> None:
        """Log system-level events"""
        c = cls.COLORS
        timestamp = cls._get_timestamp()

        color_map = {
            'INFO': 'WHITE',
            'WARNING': 'YELLOW',
            'ERROR': 'RED',
            'SUCCESS': 'GREEN'
        }

        color = color_map.get(level, 'WHITE')

        formatted = (
            f"{c['GRAY']}[{timestamp}]{c['RESET']} "
            f"{c['BOLD']}{c[color]}[SYSTEM:{level}]{c['RESET']} "
            f"{c['WHITE']}{message}{c['RESET']}"
        )

        print(formatted)

    @classmethod
    def log_separator(cls) -> None:
        """Print a separator line"""
        c = cls.COLORS
        print(f"{c['GRAY']}{'─' * 100}{c['RESET']}")

    @classmethod
    def get_context_info(cls, message: discord.Message) -> tuple:
        """Extract context information from a Discord message"""
        server = message.guild.name if message.guild else "DM"
        channel = message.channel.name if hasattr(message.channel, 'name') else "DM"
        user = f"{message.author.name}#{message.author.discriminator}"

        guild_id = message.guild.id if message.guild else None
        channel_id = message.channel.id
        user_id = message.author.id

        return server, channel, user, guild_id, channel_id, user_id

    @classmethod
    def get_interaction_context(cls, interaction: discord.Interaction) -> tuple:
        """Extract context information from a Discord interaction"""
        server = interaction.guild.name if interaction.guild else "DM"
        channel = interaction.channel.name if hasattr(interaction.channel, 'name') else "DM"
        user = f"{interaction.user.name}#{interaction.user.discriminator}"

        return server, channel, user

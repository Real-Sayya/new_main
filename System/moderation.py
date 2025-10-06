import discord
from discord.ext import commands
from .terminal.mod_manager import ModerationManager
from .terminal.permissions import format_output, format_error, format_code_block
from .terminal.logger_manager import TerminalLogger
from datetime import datetime, timedelta

class Moderation(commands.Cog):
    """Moderation System - Terminal Integration"""

    def __init__(self, bot):
        self.bot = bot
        self.mod_manager = ModerationManager(bot)
        print("🛡️  Moderation System initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize database when bot is ready"""
        await self.mod_manager.setup_database()
        print("✅ Moderation System ready!")

    async def cmd_warn(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Warn a user - Auto-actions at 3, 5, 10 warns"""
        if len(args) < 2:
            return format_error("Usage: sudo warn <user_id|@mention> <reason>")

        
        user_id = self._parse_user_id(args[0])
        if not user_id:
            return format_error("Invalid user ID or mention")

        reason = " ".join(args[1:])

        try:
            member = await guild.fetch_member(user_id)
        except:
            return format_error("User not found in this guild")

        
        if member.bot:
            return format_error("Cannot warn bots")
        if member.id == discord_id:
            return format_error("Cannot warn yourself")

        
        case_id = await self.mod_manager.create_case(
            guild.id, user_id, discord_id, "WARN", reason
        )

        
        warn_count = await self.mod_manager.add_warning(guild.id, user_id)

        
        moderator = await guild.fetch_member(discord_id)
        mod_name = f"{moderator.name}#{moderator.discriminator}" if moderator else str(discord_id)
        TerminalLogger.log_moderation(
            server=guild.name,
            moderator=mod_name,
            action="WARN",
            target_user=member.name,
            reason=reason,
            case_id=case_id
        )

        
        output = [
            f"✅ Warning issued to {member.name} (ID: {user_id})",
            f"Case ID: #{case_id}",
            f"Reason: {reason}",
            f"Total Warnings: {warn_count}"
        ]

        
        auto_action = None
        if warn_count == 3:
            auto_action = await self._auto_kick(guild, member, discord_id, "3 warnings reached")
            output.append(f"\n⚠️  AUTO-ACTION: User kicked (3 warnings)")
        elif warn_count == 5:
            auto_action = await self._auto_tempban(guild, member, discord_id, "5 warnings reached", "1d")
            output.append(f"\n⚠️  AUTO-ACTION: User temp-banned for 1 day (5 warnings)")
        elif warn_count == 10:
            auto_action = await self._auto_ban(guild, member, discord_id, "10 warnings reached")
            output.append(f"\n⚠️  AUTO-ACTION: User permanently banned (10 warnings)")

        if auto_action:
            output.append(f"Auto-action Case ID: #{auto_action}")

        return format_code_block("\n".join(output))

    async def cmd_kick(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Kick a user from the guild"""
        if len(args) < 1:
            return format_error("Usage: sudo kick <user_id|@mention> [reason]")

        user_id = self._parse_user_id(args[0])
        if not user_id:
            return format_error("Invalid user ID or mention")

        reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided"

        try:
            member = await guild.fetch_member(user_id)
        except:
            return format_error("User not found in this guild")

        if member.bot:
            return format_error("Cannot kick bots")
        if member.id == discord_id:
            return format_error("Cannot kick yourself")

        
        if member.top_role >= guild.me.top_role:
            return format_error("Cannot kick this user (role hierarchy)")

        
        case_id = await self.mod_manager.create_case(
            guild.id, user_id, discord_id, "KICK", reason
        )

        
        try:
            await member.send(f"You have been kicked from {guild.name}.\nReason: {reason}")
        except:
            pass  

        await member.kick(reason=f"[Case #{case_id}] {reason}")

        
        moderator = await guild.fetch_member(discord_id)
        mod_name = f"{moderator.name}#{moderator.discriminator}" if moderator else str(discord_id)
        TerminalLogger.log_moderation(
            server=guild.name,
            moderator=mod_name,
            action="KICK",
            target_user=member.name,
            reason=reason,
            case_id=case_id
        )

        return format_code_block(
            f"✅ User kicked\n"
            f"Case ID: #{case_id}\n"
            f"User: {member.name} (ID: {user_id})\n"
            f"Reason: {reason}"
        )

    async def cmd_ban(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Ban a user from the guild (permanent or temporary)"""
        if len(args) < 1:
            return format_error("Usage: sudo ban <user_id|@mention> [duration] [reason]")

        user_id = self._parse_user_id(args[0])
        if not user_id:
            return format_error("Invalid user ID or mention")

        
        duration = None
        reason_start_idx = 1

        if len(args) > 1 and self._is_duration(args[1]):
            duration = args[1]
            reason_start_idx = 2

        reason = " ".join(args[reason_start_idx:]) if len(args) > reason_start_idx else "No reason provided"

        try:
            member = await guild.fetch_member(user_id)
        except:
            
            try:
                user = await self.bot.fetch_user(user_id)
                member = None
            except:
                return format_error("User not found")

        if member:
            if member.bot:
                return format_error("Cannot ban bots")
            if member.id == discord_id:
                return format_error("Cannot ban yourself")
            if member.top_role >= guild.me.top_role:
                return format_error("Cannot ban this user (role hierarchy)")

        
        case_id = await self.mod_manager.create_case(
            guild.id, user_id, discord_id, "BAN", reason, duration
        )

        
        try:
            if member:
                duration_text = self.mod_manager.format_duration(duration) if duration else "Permanent"
                await member.send(
                    f"You have been banned from {guild.name}.\n"
                    f"Duration: {duration_text}\n"
                    f"Reason: {reason}"
                )
        except:
            pass

        await guild.ban(discord.Object(id=user_id), reason=f"[Case #{case_id}] {reason}")

        
        if duration:
            self.bot.loop.create_task(self._schedule_unban(guild.id, user_id, case_id, duration))

        
        moderator = await guild.fetch_member(discord_id)
        mod_name = f"{moderator.name}#{moderator.discriminator}" if moderator else str(discord_id)
        ban_type = f"TEMPBAN ({self.mod_manager.format_duration(duration)})" if duration else "BAN"
        TerminalLogger.log_moderation(
            server=guild.name,
            moderator=mod_name,
            action=ban_type,
            target_user=str(user_id),
            reason=reason,
            case_id=case_id
        )

        duration_display = f" ({self.mod_manager.format_duration(duration)})" if duration else " (Permanent)"
        return format_code_block(
            f"✅ User banned{duration_display}\n"
            f"Case ID: #{case_id}\n"
            f"User ID: {user_id}\n"
            f"Reason: {reason}"
        )

    async def cmd_unban(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Unban a user from the guild"""
        if len(args) < 1:
            return format_error("Usage: sudo unban <user_id>")

        user_id = self._parse_user_id(args[0])
        if not user_id:
            return format_error("Invalid user ID")

        reason = " ".join(args[1:]) if len(args) > 1 else "Unbanned by admin"

        
        try:
            await guild.fetch_ban(discord.Object(id=user_id))
        except discord.NotFound:
            return format_error("User is not banned")

        
        case_id = await self.mod_manager.create_case(
            guild.id, user_id, discord_id, "UNBAN", reason
        )

        
        await guild.unban(discord.Object(id=user_id), reason=f"[Case #{case_id}] {reason}")

        
        moderator = await guild.fetch_member(discord_id)
        mod_name = f"{moderator.name}#{moderator.discriminator}" if moderator else str(discord_id)
        TerminalLogger.log_moderation(
            server=guild.name,
            moderator=mod_name,
            action="UNBAN",
            target_user=str(user_id),
            reason=reason,
            case_id=case_id
        )

        return format_code_block(
            f"✅ User unbanned\n"
            f"Case ID: #{case_id}\n"
            f"User ID: {user_id}\n"
            f"Reason: {reason}"
        )

    async def cmd_timeout(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Timeout a user (Discord native timeout)"""
        if len(args) < 2:
            return format_error("Usage: sudo timeout <user_id|@mention> <duration> [reason]")

        user_id = self._parse_user_id(args[0])
        if not user_id:
            return format_error("Invalid user ID or mention")

        duration_str = args[1]
        if not self._is_duration(duration_str):
            return format_error("Invalid duration format. Use: 1m, 1h, 1d, etc.")

        reason = " ".join(args[2:]) if len(args) > 2 else "No reason provided"

        try:
            member = await guild.fetch_member(user_id)
        except:
            return format_error("User not found in this guild")

        if member.bot:
            return format_error("Cannot timeout bots")
        if member.id == discord_id:
            return format_error("Cannot timeout yourself")

        
        delta = self._parse_timedelta(duration_str)
        if not delta or delta > timedelta(days=28):
            return format_error("Timeout duration must be between 1 minute and 28 days")

        
        case_id = await self.mod_manager.create_case(
            guild.id, user_id, discord_id, "TIMEOUT", reason, duration_str
        )

        
        try:
            await member.timeout_for(delta, reason=f"[Case #{case_id}] {reason}")
        except discord.Forbidden:
            return format_error("Cannot timeout this user (insufficient permissions)")

        try:
            await member.send(
                f"You have been timed out in {guild.name}.\n"
                f"Duration: {self.mod_manager.format_duration(duration_str)}\n"
                f"Reason: {reason}"
            )
        except:
            pass

        
        moderator = await guild.fetch_member(discord_id)
        mod_name = f"{moderator.name}#{moderator.discriminator}" if moderator else str(discord_id)
        TerminalLogger.log_moderation(
            server=guild.name,
            moderator=mod_name,
            action=f"TIMEOUT ({self.mod_manager.format_duration(duration_str)})",
            target_user=member.name,
            reason=reason,
            case_id=case_id
        )

        return format_code_block(
            f"✅ User timed out\n"
            f"Case ID: #{case_id}\n"
            f"User: {member.name} (ID: {user_id})\n"
            f"Duration: {self.mod_manager.format_duration(duration_str)}\n"
            f"Reason: {reason}"
        )

    async def cmd_untimeout(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Remove timeout from a user"""
        if len(args) < 1:
            return format_error("Usage: sudo untimeout <user_id|@mention> [reason]")

        user_id = self._parse_user_id(args[0])
        if not user_id:
            return format_error("Invalid user ID or mention")

        reason = " ".join(args[1:]) if len(args) > 1 else "Timeout removed by admin"

        try:
            member = await guild.fetch_member(user_id)
        except:
            return format_error("User not found in this guild")

        if not member.is_timed_out():
            return format_error("User is not timed out")

        
        case_id = await self.mod_manager.create_case(
            guild.id, user_id, discord_id, "UNTIMEOUT", reason
        )

        
        await member.remove_timeout(reason=f"[Case #{case_id}] {reason}")

        return format_code_block(
            f"✅ Timeout removed\n"
            f"Case ID: #{case_id}\n"
            f"User: {member.name} (ID: {user_id})\n"
            f"Reason: {reason}"
        )

    async def cmd_delwarn(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Delete/remove a warning from a user"""
        if len(args) < 1:
            return format_error("Usage: sudo delwarn <user_id|@mention>")

        user_id = self._parse_user_id(args[0])
        if not user_id:
            return format_error("Invalid user ID or mention")

        
        success, new_count = await self.mod_manager.remove_warning(guild.id, user_id)

        if not success:
            return format_error("User has no warnings to remove")

        
        case_id = await self.mod_manager.create_case(
            guild.id, user_id, discord_id, "DELWARN", "Warning removed by admin"
        )

        return format_code_block(
            f"✅ Warning removed\n"
            f"Case ID: #{case_id}\n"
            f"User ID: {user_id}\n"
            f"Remaining Warnings: {new_count}"
        )

    async def cmd_modlog(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """View moderation history for a user"""
        if len(args) < 1:
            return format_error("Usage: sudo modlog <user_id|@mention>")

        user_id = self._parse_user_id(args[0])
        if not user_id:
            return format_error("Invalid user ID or mention")

        
        warn_count = await self.mod_manager.get_warning_count(guild.id, user_id)

        
        cases = await self.mod_manager.get_user_cases(guild.id, user_id, limit=15)

        if not cases:
            return format_code_block(f"No moderation history found for user {user_id}")

        output = [
            f"MODERATION LOG - User ID: {user_id}",
            f"Current Warnings: {warn_count}",
            "=" * 60
        ]

        for case in cases:
            case_id, action, reason, mod_id, timestamp, duration, active = case
            status = "✅ Active" if active else "⏸️  Inactive"
            duration_str = f" ({self.mod_manager.format_duration(duration)})" if duration else ""

            output.append(
                f"\nCase #{case_id} - {action}{duration_str} {status}\n"
                f"  Moderator: {mod_id}\n"
                f"  Reason: {reason or 'No reason'}\n"
                f"  Time: {timestamp[:19]}"
            )

        return format_code_block("\n".join(output))

    

    def _parse_user_id(self, user_input: str) -> int:
        """Parse user ID from mention or raw ID"""
        
        user_input = user_input.strip('<@!>')
        try:
            return int(user_input)
        except:
            return None

    def _is_duration(self, text: str) -> bool:
        """Check if text is a valid duration format"""
        if len(text) < 2:
            return False
        return text[-1].lower() in ['m', 'h', 'd', 'w'] and text[:-1].isdigit()

    def _parse_timedelta(self, duration_str: str) -> timedelta:
        """Parse duration string to timedelta"""
        try:
            amount = int(duration_str[:-1])
            unit = duration_str[-1].lower()

            if unit == 'd':
                return timedelta(days=amount)
            elif unit == 'h':
                return timedelta(hours=amount)
            elif unit == 'm':
                return timedelta(minutes=amount)
            elif unit == 'w':
                return timedelta(weeks=amount)
        except:
            return None

    

    async def _auto_kick(self, guild: discord.Guild, member: discord.Member,
                         moderator_id: int, reason: str) -> int:
        """Auto-kick user (3 warns)"""
        case_id = await self.mod_manager.create_case(
            guild.id, member.id, moderator_id, "AUTO-KICK", reason
        )

        try:
            await member.send(f"You have been auto-kicked from {guild.name}.\nReason: {reason}")
        except:
            pass

        await member.kick(reason=f"[Case #{case_id}] Auto-kick: {reason}")

        
        TerminalLogger.log_moderation(
            server=guild.name,
            moderator="SYSTEM",
            action="AUTO-KICK",
            target_user=member.name,
            reason=reason,
            case_id=case_id
        )

        return case_id

    async def _auto_tempban(self, guild: discord.Guild, member: discord.Member,
                           moderator_id: int, reason: str, duration: str) -> int:
        """Auto-tempban user (5 warns)"""
        case_id = await self.mod_manager.create_case(
            guild.id, member.id, moderator_id, "AUTO-TEMPBAN", reason, duration
        )

        try:
            await member.send(
                f"You have been auto-banned from {guild.name} for {self.mod_manager.format_duration(duration)}.\n"
                f"Reason: {reason}"
            )
        except:
            pass

        await guild.ban(member, reason=f"[Case #{case_id}] Auto-tempban: {reason}")

        
        self.bot.loop.create_task(self._schedule_unban(guild.id, member.id, case_id, duration))

        
        TerminalLogger.log_moderation(
            server=guild.name,
            moderator="SYSTEM",
            action=f"AUTO-TEMPBAN ({self.mod_manager.format_duration(duration)})",
            target_user=member.name,
            reason=reason,
            case_id=case_id
        )

        return case_id

    async def _auto_ban(self, guild: discord.Guild, member: discord.Member,
                       moderator_id: int, reason: str) -> int:
        """Auto-ban user permanently (10 warns)"""
        case_id = await self.mod_manager.create_case(
            guild.id, member.id, moderator_id, "AUTO-BAN", reason
        )

        try:
            await member.send(
                f"You have been permanently banned from {guild.name}.\n"
                f"Reason: {reason}"
            )
        except:
            pass

        await guild.ban(member, reason=f"[Case #{case_id}] Auto-ban: {reason}")

        
        TerminalLogger.log_moderation(
            server=guild.name,
            moderator="SYSTEM",
            action="AUTO-BAN",
            target_user=member.name,
            reason=reason,
            case_id=case_id
        )

        return case_id

    async def _schedule_unban(self, guild_id: int, user_id: int, case_id: int, duration: str):
        """Schedule automatic unban after duration"""
        import asyncio
        delta = self._parse_timedelta(duration)
        if not delta:
            return

        await asyncio.sleep(delta.total_seconds())

        
        guild = self.bot.get_guild(guild_id)
        if guild:
            try:
                await guild.unban(discord.Object(id=user_id), reason=f"[Case #{case_id}] Temporary ban expired")
                await self.mod_manager.deactivate_case(case_id)
            except:
                pass  


def setup(bot):
    bot.add_cog(Moderation(bot))
    print("✅ Moderation cog loaded")

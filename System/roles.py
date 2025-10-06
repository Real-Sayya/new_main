import discord
from discord.ext import commands
from .terminal.role_manager import RoleManager
from .terminal.permissions import format_output, format_error, format_code_block
from .terminal.role_modals import RoleCreateModal, RoleEditModal, RoleGiveModal, RoleRemoveModal
from .terminal.logger_manager import TerminalLogger

class Roles(commands.Cog):
    """Role Management System - Terminal Integration"""

    def __init__(self, bot):
        self.bot = bot
        self.role_manager = RoleManager(bot)
        print("👑 Role Management System initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        print("✅ Role Management System ready!")

    async def cmd_role(self, discord_id: int, args: list, guild: discord.Guild, channel=None) -> str:
        """Main role command router"""
        if not guild:
            return format_error("Role commands can only be used in a server")

        if not args:
            return format_error(
                "Usage: sudo role <create|delete|give|remove|list|info|edit>\n"
                "Type 'help' for detailed role command information"
            )

        subcommand = args[0].lower()
        subargs = args[1:] if len(args) > 1 else []

        if subcommand == 'create':
            return await self.cmd_role_create(discord_id, subargs, guild, channel)
        elif subcommand == 'delete' or subcommand == 'del':
            return await self.cmd_role_delete(discord_id, subargs, guild)
        elif subcommand == 'give' or subcommand == 'add':
            return await self.cmd_role_give(discord_id, subargs, guild, channel)
        elif subcommand == 'remove' or subcommand == 'rem':
            return await self.cmd_role_remove(discord_id, subargs, guild, channel)
        elif subcommand == 'list' or subcommand == 'ls':
            return await self.cmd_role_list(discord_id, subargs, guild)
        elif subcommand == 'info':
            return await self.cmd_role_info(discord_id, subargs, guild)
        elif subcommand == 'edit':
            return await self.cmd_role_edit(discord_id, subargs, guild, channel)
        else:
            return format_error(f"Unknown role subcommand: {subcommand}")

    async def cmd_role_create(self, discord_id: int, args: list, guild: discord.Guild, channel=None) -> str:
        """Create a new role"""
        if not channel:
            return format_error("Channel context required")

        
        class RoleCreateButton(discord.ui.View):
            def __init__(self, role_manager, guild):
                super().__init__(timeout=120)
                self.role_manager = role_manager
                self.guild = guild

            @discord.ui.button(label="Create Role", style=discord.ButtonStyle.primary, emoji="👑")
            async def create_role(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = RoleCreateModal(self.role_manager, self.guild)
                await interaction.response.send_modal(modal)

        view = RoleCreateButton(self.role_manager, guild)
        await channel.send(
            "👑 **Create New Role**\nClick the button below to fill in role details:",
            view=view
        )
        return None  

    async def cmd_role_delete(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Delete a role"""
        if not args:
            return format_error(
                "Usage: sudo role delete <@role|role_id>\n"
                "Example: sudo role delete @Moderator"
            )

        role_id = self.role_manager.parse_role_id(args[0])
        if not role_id:
            return format_error("Invalid role ID or mention")

        role = guild.get_role(role_id)
        if not role:
            return format_error(f"Role not found (ID: {role_id})")

        role_name = role.name  

        
        success, message = await self.role_manager.delete_role(guild, role)

        if success:
            
            TerminalLogger.log_role_action(
                server=guild.name,
                admin="TERMINAL",
                action="DELETE",
                role_name=role_name
            )

            return format_code_block(f"✅ {message}")
        else:
            return format_error(message)

    async def cmd_role_give(self, discord_id: int, args: list, guild: discord.Guild, channel=None) -> str:
        """Give a role to a user"""
        if not channel:
            return format_error("Channel context required")

        
        class RoleGiveButton(discord.ui.View):
            def __init__(self, role_manager, guild):
                super().__init__(timeout=120)
                self.role_manager = role_manager
                self.guild = guild

            @discord.ui.button(label="Give Role", style=discord.ButtonStyle.success, emoji="➕")
            async def give_role(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = RoleGiveModal(self.role_manager, self.guild)
                await interaction.response.send_modal(modal)

        view = RoleGiveButton(self.role_manager, guild)
        await channel.send(
            "➕ **Give Role to User**\nClick the button below to specify user and role:",
            view=view
        )
        return None  

    async def cmd_role_remove(self, discord_id: int, args: list, guild: discord.Guild, channel=None) -> str:
        """Remove a role from a user"""
        if not channel:
            return format_error("Channel context required")

        
        class RoleRemoveButton(discord.ui.View):
            def __init__(self, role_manager, guild):
                super().__init__(timeout=120)
                self.role_manager = role_manager
                self.guild = guild

            @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.danger, emoji="➖")
            async def remove_role(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = RoleRemoveModal(self.role_manager, self.guild)
                await interaction.response.send_modal(modal)

        view = RoleRemoveButton(self.role_manager, guild)
        await channel.send(
            "➖ **Remove Role from User**\nClick the button below to specify user and role:",
            view=view
        )
        return None  

    async def cmd_role_list(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """List all roles in the guild"""
        show_managed = '-a' in args or '--all' in args

        roles = self.role_manager.list_roles(guild, show_managed)

        if not roles:
            return format_code_block("No roles found")

        output = [
            f"ROLES IN {guild.name.upper()}",
            "=" * 70
        ]

        for role_info in roles:
            managed_tag = " [MANAGED]" if role_info['managed'] else ""
            hoist_tag = " [HOISTED]" if role_info['hoist'] else ""
            mention_tag = " [MENTIONABLE]" if role_info['mentionable'] else ""

            output.append(
                f"\n{role_info['name']}{managed_tag}{hoist_tag}{mention_tag}\n"
                f"  ID: {role_info['id']} | Position: {role_info['position']} | "
                f"Members: {role_info['members']} | Color: {role_info['color']}"
            )

        output.append("\n" + "=" * 70)
        output.append(f"Total roles: {len(roles)}")

        if not show_managed:
            output.append("Tip: Use 'sudo role list -a' to show managed roles")

        return format_code_block("\n".join(output))

    async def cmd_role_info(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Show detailed information about a role"""
        if not args:
            return format_error(
                "Usage: sudo role info <@role|role_id>\n"
                "Example: sudo role info @Moderator"
            )

        role_id = self.role_manager.parse_role_id(args[0])
        if not role_id:
            return format_error("Invalid role ID or mention")

        role = guild.get_role(role_id)
        if not role:
            return format_error(f"Role not found (ID: {role_id})")

        info = self.role_manager.get_role_info(role)
        return format_code_block(info)

    async def cmd_role_edit(self, discord_id: int, args: list, guild: discord.Guild, channel=None) -> str:
        """Edit an existing role"""
        if not channel:
            return format_error("Channel context required")

        if not args:
            return format_error(
                "Usage: sudo role edit <@role|role_id>\n"
                "Example: sudo role edit @Moderator"
            )

        
        role_id = self.role_manager.parse_role_id(args[0])
        if not role_id:
            return format_error("Invalid role ID or mention")

        role = guild.get_role(role_id)
        if not role:
            return format_error(f"Role not found (ID: {role_id})")

        
        class RoleEditButton(discord.ui.View):
            def __init__(self, role_manager, guild, role):
                super().__init__(timeout=120)
                self.role_manager = role_manager
                self.guild = guild
                self.role = role

            @discord.ui.button(label="Edit Role", style=discord.ButtonStyle.primary, emoji="✏️")
            async def edit_role(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = RoleEditModal(self.role_manager, self.guild, self.role)
                await interaction.response.send_modal(modal)

        view = RoleEditButton(self.role_manager, guild, role)
        await channel.send(
            f"✏️ **Edit Role: {role.name}**\nClick the button below to edit role properties:",
            view=view
        )
        return None  


def setup(bot):
    bot.add_cog(Roles(bot))
    print("✅ Role Management cog loaded")

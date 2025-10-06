import discord
from .permissions import format_output, format_error, format_code_block
from .logger_manager import TerminalLogger

class RoleCreateModal(discord.ui.Modal):
    """Modal for creating a new role"""
    def __init__(self, role_manager, guild):
        super().__init__(title="Create Role")
        self.role_manager = role_manager
        self.guild = guild

        self.role_name = discord.ui.InputText(
            label="Role Name",
            placeholder="Enter the role name",
            min_length=1,
            max_length=100,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.role_name)

        self.color = discord.ui.InputText(
            label="Color (optional)",
            placeholder="red, blue, #FF0000, or leave empty",
            min_length=0,
            max_length=20,
            required=False,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.color)

        self.hoist = discord.ui.InputText(
            label="Display separately? (optional)",
            placeholder="yes or no (default: no)",
            min_length=0,
            max_length=3,
            required=False,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.hoist)

        self.mentionable = discord.ui.InputText(
            label="Mentionable? (optional)",
            placeholder="yes or no (default: no)",
            min_length=0,
            max_length=3,
            required=False,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.mentionable)

    async def callback(self, interaction: discord.Interaction):
        name = self.role_name.value
        color_str = self.color.value.strip()
        hoist_str = self.hoist.value.strip().lower()
        mention_str = self.mentionable.value.strip().lower()

        # Parse color
        color = None
        if color_str:
            color = self.role_manager.parse_color(color_str)
            if not color:
                await interaction.response.send_message(
                    format_error(f"Invalid color: {color_str}")
                )
                return

        # Parse hoist
        hoist = hoist_str in ['yes', 'y', 'true', '1']

        # Parse mentionable
        mentionable = mention_str in ['yes', 'y', 'true', '1']

        # Get context for logging
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        # Log modal interaction
        TerminalLogger.log_modal(server, channel, user, "RoleCreateModal", "SUBMIT", f"Creating role: {name}")

        # Create role
        success, message, role = await self.role_manager.create_role(
            self.guild, name, color, hoist, mentionable
        )

        if not success:
            await interaction.response.send_message(format_error(message))
            return

        # Log role action
        color_hex = f"#{role.color.value:06x}"
        details = f"Color: {color_hex}, Hoist: {hoist}, Mentionable: {mentionable}"
        TerminalLogger.log_role_action(
            server=server,
            admin=user,
            action="CREATE",
            role_name=role.name,
            details=details
        )

        output = [
            f"✅ Role created successfully",
            f"Name: {role.name}",
            f"ID: {role.id}",
            f"Color: #{role.color.value:06x}",
            f"Hoisted: {'Yes' if hoist else 'No'}",
            f"Mentionable: {'Yes' if mentionable else 'No'}"
        ]

        await interaction.response.send_message(format_code_block("\n".join(output)))


class RoleEditModal(discord.ui.Modal):
    """Modal for editing an existing role"""
    def __init__(self, role_manager, guild, role):
        super().__init__(title=f"Edit Role: {role.name}")
        self.role_manager = role_manager
        self.guild = guild
        self.role = role

        self.new_name = discord.ui.InputText(
            label="New Name (optional)",
            placeholder=f"Current: {role.name}",
            min_length=0,
            max_length=100,
            required=False,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.new_name)

        self.color = discord.ui.InputText(
            label="Color (optional)",
            placeholder=f"Current: #{role.color.value:06x}",
            min_length=0,
            max_length=20,
            required=False,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.color)

        self.hoist = discord.ui.InputText(
            label="Display separately? (optional)",
            placeholder=f"Current: {'yes' if role.hoist else 'no'}",
            min_length=0,
            max_length=3,
            required=False,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.hoist)

        self.mentionable = discord.ui.InputText(
            label="Mentionable? (optional)",
            placeholder=f"Current: {'yes' if role.mentionable else 'no'}",
            min_length=0,
            max_length=3,
            required=False,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.mentionable)

    async def callback(self, interaction: discord.Interaction):
        new_name = self.new_name.value.strip() if self.new_name.value.strip() else None
        color_str = self.color.value.strip()
        hoist_str = self.hoist.value.strip().lower()
        mention_str = self.mentionable.value.strip().lower()

        # Parse color
        new_color = None
        if color_str:
            new_color = self.role_manager.parse_color(color_str)
            if not new_color:
                await interaction.response.send_message(
                    format_error(f"Invalid color: {color_str}")
                )
                return

        # Parse hoist
        new_hoist = None
        if hoist_str:
            new_hoist = hoist_str in ['yes', 'y', 'true', '1']

        # Parse mentionable
        new_mentionable = None
        if mention_str:
            new_mentionable = mention_str in ['yes', 'y', 'true', '1']

        # Get context for logging
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        # Log modal interaction
        TerminalLogger.log_modal(server, channel, user, "RoleEditModal", "SUBMIT", f"Editing role: {self.role.name}")

        # Edit role
        success, message = await self.role_manager.edit_role(
            self.guild, self.role, new_name, new_color, new_hoist, new_mentionable
        )

        if success:
            # Build details for logging
            changes = []
            if new_name:
                changes.append(f"Name: {new_name}")
            if new_color:
                changes.append(f"Color: #{new_color.value:06x}")
            if new_hoist is not None:
                changes.append(f"Hoist: {new_hoist}")
            if new_mentionable is not None:
                changes.append(f"Mentionable: {new_mentionable}")

            details = ", ".join(changes) if changes else "No changes"
            TerminalLogger.log_role_action(
                server=server,
                admin=user,
                action="EDIT",
                role_name=self.role.name,
                details=details
            )

            await interaction.response.send_message(format_code_block(f"✅ {message}"))
        else:
            await interaction.response.send_message(format_error(message))


class RoleGiveModal(discord.ui.Modal):
    """Modal for giving a role to a user"""
    def __init__(self, role_manager, guild):
        super().__init__(title="Give Role to User")
        self.role_manager = role_manager
        self.guild = guild

        self.user_input = discord.ui.InputText(
            label="User",
            placeholder="@mention or user ID",
            min_length=1,
            max_length=50,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.user_input)

        self.role_input = discord.ui.InputText(
            label="Role",
            placeholder="@role mention or role ID",
            min_length=1,
            max_length=50,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.role_input)

    async def callback(self, interaction: discord.Interaction):
        # Parse user
        user_id = self.role_manager.parse_user_id(self.user_input.value)
        if not user_id:
            await interaction.response.send_message(
                format_error("Invalid user ID or mention")
            )
            return

        # Parse role
        role_id = self.role_manager.parse_role_id(self.role_input.value)
        if not role_id:
            await interaction.response.send_message(
                format_error("Invalid role ID or mention")
            )
            return

        # Get member and role
        try:
            member = await self.guild.fetch_member(user_id)
        except:
            await interaction.response.send_message(
                format_error(f"User not found in this guild (ID: {user_id})")
            )
            return

        role = self.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                format_error(f"Role not found (ID: {role_id})")
            )
            return

        # Get context for logging
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        # Log modal interaction
        TerminalLogger.log_modal(server, channel, user, "RoleGiveModal", "SUBMIT", f"Giving {role.name} to {member.name}")

        # Give role
        success, message = await self.role_manager.give_role(self.guild, member, role)

        if success:
            # Log role action
            TerminalLogger.log_role_action(
                server=server,
                admin=user,
                action="GIVE",
                role_name=role.name,
                target_user=member.name
            )

            await interaction.response.send_message(format_code_block(f"✅ {message}"))
        else:
            await interaction.response.send_message(format_error(message))


class RoleRemoveModal(discord.ui.Modal):
    """Modal for removing a role from a user"""
    def __init__(self, role_manager, guild):
        super().__init__(title="Remove Role from User")
        self.role_manager = role_manager
        self.guild = guild

        self.user_input = discord.ui.InputText(
            label="User",
            placeholder="@mention or user ID",
            min_length=1,
            max_length=50,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.user_input)

        self.role_input = discord.ui.InputText(
            label="Role",
            placeholder="@role mention or role ID",
            min_length=1,
            max_length=50,
            required=True,
            style=discord.InputTextStyle.short
        )
        self.add_item(self.role_input)

    async def callback(self, interaction: discord.Interaction):
        # Parse user
        user_id = self.role_manager.parse_user_id(self.user_input.value)
        if not user_id:
            await interaction.response.send_message(
                format_error("Invalid user ID or mention")
            )
            return

        # Parse role
        role_id = self.role_manager.parse_role_id(self.role_input.value)
        if not role_id:
            await interaction.response.send_message(
                format_error("Invalid role ID or mention")
            )
            return

        # Get member and role
        try:
            member = await self.guild.fetch_member(user_id)
        except:
            await interaction.response.send_message(
                format_error(f"User not found in this guild (ID: {user_id})")
            )
            return

        role = self.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                format_error(f"Role not found (ID: {role_id})")
            )
            return

        # Get context for logging
        server, channel, user = TerminalLogger.get_interaction_context(interaction)

        # Log modal interaction
        TerminalLogger.log_modal(server, channel, user, "RoleRemoveModal", "SUBMIT", f"Removing {role.name} from {member.name}")

        # Remove role
        success, message = await self.role_manager.remove_role(self.guild, member, role)

        if success:
            # Log role action
            TerminalLogger.log_role_action(
                server=server,
                admin=user,
                action="REMOVE",
                role_name=role.name,
                target_user=member.name
            )

            await interaction.response.send_message(format_code_block(f"✅ {message}"))
        else:
            await interaction.response.send_message(format_error(message))

import discord
from typing import Optional, Tuple

class RoleManager:
    """Handles Discord role management"""

    def __init__(self, bot):
        self.bot = bot

    def parse_color(self, color_str: str) -> Optional[discord.Color]:
        """Parse color from hex string or color name"""
        if not color_str:
            return discord.Color.default()

        # Remove # if present
        color_str = color_str.strip('#').lower()

        # Predefined colors
        color_map = {
            'red': discord.Color.red(),
            'blue': discord.Color.blue(),
            'green': discord.Color.green(),
            'yellow': discord.Color.yellow(),
            'orange': discord.Color.orange(),
            'purple': discord.Color.purple(),
            'pink': discord.Color.pink(),
            'teal': discord.Color.teal(),
            'gold': discord.Color.gold(),
            'dark_blue': discord.Color.dark_blue(),
            'dark_green': discord.Color.dark_green(),
            'dark_red': discord.Color.dark_red(),
            'dark_purple': discord.Color.dark_purple(),
            'dark_gold': discord.Color.dark_gold(),
            'white': discord.Color.from_rgb(255, 255, 255),
            'black': discord.Color.from_rgb(0, 0, 0),
            'grey': discord.Color.from_rgb(128, 128, 128),
            'gray': discord.Color.from_rgb(128, 128, 128),
        }

        if color_str in color_map:
            return color_map[color_str]

        # Try hex color
        try:
            if len(color_str) == 6:
                return discord.Color(int(color_str, 16))
            else:
                return None
        except:
            return None

    def parse_role_id(self, role_input: str) -> Optional[int]:
        """Parse role ID from mention or raw ID"""
        # Remove role mention formatting <@&ID>
        role_input = role_input.strip('<@&>')
        try:
            return int(role_input)
        except:
            return None

    def parse_user_id(self, user_input: str) -> Optional[int]:
        """Parse user ID from mention or raw ID"""
        # Remove user mention formatting
        user_input = user_input.strip('<@!>')
        try:
            return int(user_input)
        except:
            return None

    async def create_role(self, guild: discord.Guild, name: str,
                         color: Optional[discord.Color] = None,
                         hoist: bool = False,
                         mentionable: bool = False) -> Tuple[bool, str, Optional[discord.Role]]:
        """Create a new role"""
        try:
            if not color:
                color = discord.Color.default()

            role = await guild.create_role(
                name=name,
                color=color,
                hoist=hoist,
                mentionable=mentionable,
                reason="Created via Terminal System"
            )

            return True, f"Role '{role.name}' created successfully (ID: {role.id})", role

        except discord.Forbidden:
            return False, "Permission denied: Bot lacks 'Manage Roles' permission", None
        except discord.HTTPException as e:
            return False, f"Failed to create role: {str(e)}", None

    async def delete_role(self, guild: discord.Guild, role: discord.Role) -> Tuple[bool, str]:
        """Delete a role"""
        try:
            role_name = role.name
            role_id = role.id

            # Check if role is managed (bot roles, boosters, etc.)
            if role.managed:
                return False, "Cannot delete managed role (bot/integration role)"

            # Check if role is @everyone
            if role.is_default():
                return False, "Cannot delete @everyone role"

            # Check hierarchy
            if role >= guild.me.top_role:
                return False, "Cannot delete role (role hierarchy)"

            await role.delete(reason="Deleted via Terminal System")
            return True, f"Role '{role_name}' (ID: {role_id}) deleted successfully"

        except discord.Forbidden:
            return False, "Permission denied: Bot lacks 'Manage Roles' permission"
        except discord.HTTPException as e:
            return False, f"Failed to delete role: {str(e)}"

    async def give_role(self, guild: discord.Guild, member: discord.Member,
                       role: discord.Role) -> Tuple[bool, str]:
        """Give a role to a member"""
        try:
            # Check if member already has role
            if role in member.roles:
                return False, f"{member.name} already has role '{role.name}'"

            # Check hierarchy
            if role >= guild.me.top_role:
                return False, "Cannot assign role (role hierarchy)"

            await member.add_roles(role, reason="Assigned via Terminal System")
            return True, f"Role '{role.name}' given to {member.name}"

        except discord.Forbidden:
            return False, "Permission denied: Bot lacks 'Manage Roles' permission"
        except discord.HTTPException as e:
            return False, f"Failed to give role: {str(e)}"

    async def remove_role(self, guild: discord.Guild, member: discord.Member,
                         role: discord.Role) -> Tuple[bool, str]:
        """Remove a role from a member"""
        try:
            # Check if member has the role
            if role not in member.roles:
                return False, f"{member.name} doesn't have role '{role.name}'"

            # Check hierarchy
            if role >= guild.me.top_role:
                return False, "Cannot remove role (role hierarchy)"

            await member.remove_roles(role, reason="Removed via Terminal System")
            return True, f"Role '{role.name}' removed from {member.name}"

        except discord.Forbidden:
            return False, "Permission denied: Bot lacks 'Manage Roles' permission"
        except discord.HTTPException as e:
            return False, f"Failed to remove role: {str(e)}"

    async def edit_role(self, guild: discord.Guild, role: discord.Role,
                       name: Optional[str] = None,
                       color: Optional[discord.Color] = None,
                       hoist: Optional[bool] = None,
                       mentionable: Optional[bool] = None) -> Tuple[bool, str]:
        """Edit an existing role"""
        try:
            # Check if role is @everyone
            if role.is_default():
                return False, "Cannot edit @everyone role properties via this command"

            # Check hierarchy
            if role >= guild.me.top_role:
                return False, "Cannot edit role (role hierarchy)"

            # Build kwargs for what to update
            kwargs = {}
            changes = []

            if name is not None:
                kwargs['name'] = name
                changes.append(f"name: '{name}'")

            if color is not None:
                kwargs['color'] = color
                changes.append(f"color: {color}")

            if hoist is not None:
                kwargs['hoist'] = hoist
                changes.append(f"hoist: {hoist}")

            if mentionable is not None:
                kwargs['mentionable'] = mentionable
                changes.append(f"mentionable: {mentionable}")

            if not kwargs:
                return False, "No changes specified"

            kwargs['reason'] = "Edited via Terminal System"
            await role.edit(**kwargs)

            changes_str = ", ".join(changes)
            return True, f"Role '{role.name}' updated: {changes_str}"

        except discord.Forbidden:
            return False, "Permission denied: Bot lacks 'Manage Roles' permission"
        except discord.HTTPException as e:
            return False, f"Failed to edit role: {str(e)}"

    def get_role_info(self, role: discord.Role) -> str:
        """Get detailed information about a role"""
        info = []
        info.append(f"Role: {role.name}")
        info.append(f"ID: {role.id}")
        info.append(f"Color: #{role.color.value:06x} (RGB: {role.color.r}, {role.color.g}, {role.color.b})")
        info.append(f"Position: {role.position}")
        info.append(f"Hoisted: {'Yes' if role.hoist else 'No'}")
        info.append(f"Mentionable: {'Yes' if role.mentionable else 'No'}")
        info.append(f"Managed: {'Yes (Bot/Integration)' if role.managed else 'No'}")
        info.append(f"Members: {len(role.members)}")
        info.append(f"Created: {role.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        # Permissions summary
        perms = role.permissions
        admin_perms = []
        if perms.administrator:
            admin_perms.append("Administrator")
        if perms.manage_guild:
            admin_perms.append("Manage Server")
        if perms.manage_roles:
            admin_perms.append("Manage Roles")
        if perms.manage_channels:
            admin_perms.append("Manage Channels")
        if perms.kick_members:
            admin_perms.append("Kick Members")
        if perms.ban_members:
            admin_perms.append("Ban Members")

        if admin_perms:
            info.append(f"Key Permissions: {', '.join(admin_perms)}")

        return "\n".join(info)

    def list_roles(self, guild: discord.Guild, show_managed: bool = True) -> list:
        """List all roles in the guild"""
        roles = []
        for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
            if not show_managed and role.managed:
                continue

            role_info = {
                'name': role.name,
                'id': role.id,
                'position': role.position,
                'members': len(role.members),
                'color': f"#{role.color.value:06x}",
                'hoist': role.hoist,
                'mentionable': role.mentionable,
                'managed': role.managed
            }
            roles.append(role_info)

        return roles

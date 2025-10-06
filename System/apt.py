import discord
from discord.ext import commands
import json
import aiosqlite
from .terminal.permissions import format_output, format_error, format_code_block
from .terminal.logger_manager import TerminalLogger

class APT(commands.Cog):
    """APT Package Manager - Terminal Integration"""

    def __init__(self, bot):
        self.bot = bot
        self.config_path = "Data/apt_packages.json"
        self.db_path = "Data/apt.db"
        self.config = self.load_config()
        print("📦 APT Package Manager initialized")

    def load_config(self):
        """Load APT package configuration"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize APT database"""
        await self.setup_database()
        print("✅ APT System ready!")

    async def setup_database(self):
        """Initialize APT database"""
        async with aiosqlite.connect(self.db_path) as db:
            # Installed packages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS installed_packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    package_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    installed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, guild_id, package_name)
                )
            """)

            # Package usage statistics
            await db.execute("""
                CREATE TABLE IF NOT EXISTS package_stats (
                    package_name TEXT PRIMARY KEY,
                    install_count INTEGER DEFAULT 0,
                    last_installed DATETIME
                )
            """)

            await db.commit()
            print("✅ APT database initialized")

    async def cmd_apt(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Main APT command router"""
        if not guild:
            return format_error("APT commands can only be used in a server")

        if not args:
            return format_error(
                "Usage: apt <install|remove|list|search|update|show>\n"
                "Type 'apt help' for more information"
            )

        subcommand = args[0].lower()
        subargs = args[1:] if len(args) > 1 else []

        if subcommand == 'install':
            return await self.cmd_install(discord_id, subargs, guild)
        elif subcommand == 'remove' or subcommand == 'uninstall':
            return await self.cmd_remove(discord_id, subargs, guild)
        elif subcommand == 'list':
            return await self.cmd_list(discord_id, subargs, guild)
        elif subcommand == 'search':
            return await self.cmd_search(discord_id, subargs, guild)
        elif subcommand == 'update':
            return await self.cmd_update(discord_id, subargs, guild)
        elif subcommand == 'show':
            return await self.cmd_show(discord_id, subargs, guild)
        elif subcommand == 'help':
            return await self.cmd_help(discord_id, subargs, guild)
        else:
            return format_error(f"Unknown APT command: {subcommand}")

    async def cmd_install(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Install a package"""
        if not args:
            return format_error("Usage: apt install <package_name>")

        package_name = args[0].lower()

        # Check if package exists
        if package_name not in self.config['packages']:
            return format_error(f"Package '{package_name}' not found. Use 'apt search' to find packages.")

        package = self.config['packages'][package_name]

        # Check if already installed
        if await self.is_installed(discord_id, guild.id, package_name):
            return format_error(f"Package '{package_name}' is already installed")

        # Check disk quota
        if self.config['settings']['disk_quota_enabled']:
            user_usage = await self.get_user_disk_usage(discord_id, guild.id)
            max_quota = self.config['settings']['max_disk_usage_bytes']

            if user_usage + package['size'] > max_quota:
                return format_error(
                    f"Disk quota exceeded. "
                    f"Current usage: {user_usage / 1024:.2f} KB, "
                    f"Package size: {package['size'] / 1024:.2f} KB, "
                    f"Quota: {max_quota / 1024:.2f} KB"
                )

        # Check max packages limit
        installed_count = await self.get_installed_count(discord_id, guild.id)
        max_packages = self.config['settings']['max_packages_per_user']

        if installed_count >= max_packages:
            return format_error(f"Maximum package limit reached ({max_packages} packages)")

        # Install package (grant roles and channel access)
        member = await guild.fetch_member(discord_id)

        # Grant roles
        for role_id in package.get('role_ids', []):
            role = guild.get_role(role_id)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"APT: Installed package '{package_name}'")
                except:
                    pass

        # Add to database
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO installed_packages (user_id, guild_id, package_name, version)
                VALUES (?, ?, ?, ?)
            """, (discord_id, guild.id, package_name, package['version']))

            # Update stats
            await db.execute("""
                INSERT INTO package_stats (package_name, install_count, last_installed)
                VALUES (?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(package_name) DO UPDATE SET
                    install_count = install_count + 1,
                    last_installed = CURRENT_TIMESTAMP
            """, (package_name,))

            await db.commit()

        # Log installation
        TerminalLogger.log_system(
            f"APT: {member.name} installed package '{package_name}' v{package['version']}",
            level="INFO"
        )

        # Build response
        output = [
            f"✅ Package '{package_name}' installed successfully",
            f"Version: {package['version']}",
            f"Description: {package['description']}",
            f"Size: {package['size']} bytes",
            ""
        ]

        if package.get('role_ids'):
            output.append(f"Roles granted: {len(package['role_ids'])}")

        if package.get('channel_ids'):
            output.append(f"Channels unlocked: {len(package['channel_ids'])}")

        return format_code_block("\n".join(output))

    async def cmd_remove(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Remove/uninstall a package"""
        if not args:
            return format_error("Usage: apt remove <package_name>")

        if not self.config['settings']['allow_uninstall']:
            return format_error("Package uninstallation is disabled by server settings")

        package_name = args[0].lower()

        # Check if installed
        if not await self.is_installed(discord_id, guild.id, package_name):
            return format_error(f"Package '{package_name}' is not installed")

        package = self.config['packages'].get(package_name)
        if not package:
            return format_error(f"Package '{package_name}' not found in repository")

        # Remove roles
        member = await guild.fetch_member(discord_id)

        for role_id in package.get('role_ids', []):
            role = guild.get_role(role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason=f"APT: Removed package '{package_name}'")
                except:
                    pass

        # Remove from database
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                DELETE FROM installed_packages
                WHERE user_id = ? AND guild_id = ? AND package_name = ?
            """, (discord_id, guild.id, package_name))
            await db.commit()

        # Log removal
        TerminalLogger.log_system(
            f"APT: {member.name} removed package '{package_name}'",
            level="INFO"
        )

        return format_code_block(f"✅ Package '{package_name}' removed successfully")

    async def cmd_list(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """List installed packages"""
        installed = '--installed' in args or len(args) == 0

        if installed:
            # List user's installed packages
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT package_name, version, installed_at FROM installed_packages
                    WHERE user_id = ? AND guild_id = ?
                    ORDER BY installed_at DESC
                """, (discord_id, guild.id))
                packages = await cursor.fetchall()

            if not packages:
                return format_code_block("No packages installed")

            output = [
                "INSTALLED PACKAGES",
                "=" * 60
            ]

            for pkg_name, version, installed_at in packages:
                pkg_info = self.config['packages'].get(pkg_name, {})
                description = pkg_info.get('description', 'No description')
                output.append(f"\n{pkg_name} ({version})")
                output.append(f"  {description}")
                output.append(f"  Installed: {installed_at[:19]}")

            disk_usage = await self.get_user_disk_usage(discord_id, guild.id)
            max_quota = self.config['settings']['max_disk_usage_bytes']

            output.append("\n" + "=" * 60)
            output.append(f"Total packages: {len(packages)}")
            output.append(f"Disk usage: {disk_usage / 1024:.2f} KB / {max_quota / 1024:.2f} KB")

            return format_code_block("\n".join(output))

        else:
            # List all available packages
            return await self.cmd_search(discord_id, [], guild)

    async def cmd_search(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Search for packages"""
        search_term = args[0].lower() if args else None

        output = [
            "AVAILABLE PACKAGES",
            "=" * 60
        ]

        packages = self.config['packages']

        # Filter by search term
        if search_term:
            filtered = {k: v for k, v in packages.items()
                       if search_term in k.lower() or search_term in v.get('description', '').lower()}
        else:
            filtered = packages

        if not filtered:
            return format_code_block(f"No packages found matching '{search_term}'")

        # Group by category
        by_category = {}
        for pkg_name, pkg_info in filtered.items():
            category = pkg_info.get('category', 'other')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((pkg_name, pkg_info))

        for category, cat_packages in sorted(by_category.items()):
            category_name = self.config['categories'].get(category, category.title())
            output.append(f"\n📦 {category_name}:")

            for pkg_name, pkg_info in sorted(cat_packages):
                installed = await self.is_installed(discord_id, guild.id, pkg_name)
                status = "[INSTALLED]" if installed else ""

                output.append(f"  • {pkg_name} {status}")
                output.append(f"    {pkg_info['description']}")
                output.append(f"    Version: {pkg_info['version']} | Size: {pkg_info['size']} bytes")

        output.append("\n" + "=" * 60)
        output.append(f"Total packages: {len(filtered)}")
        output.append("\nUse 'apt install <package>' to install a package")

        return format_code_block("\n".join(output))

    async def cmd_show(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Show detailed package information"""
        if not args:
            return format_error("Usage: apt show <package_name>")

        package_name = args[0].lower()

        if package_name not in self.config['packages']:
            return format_error(f"Package '{package_name}' not found")

        package = self.config['packages'][package_name]
        installed = await self.is_installed(discord_id, guild.id, package_name)

        # Get install stats
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT install_count, last_installed FROM package_stats
                WHERE package_name = ?
            """, (package_name,))
            stats = await cursor.fetchone()

        install_count = stats[0] if stats else 0

        output = [
            f"Package: {package_name}",
            f"Version: {package['version']}",
            f"Category: {self.config['categories'].get(package.get('category', 'other'), 'Other')}",
            f"Size: {package['size']} bytes ({package['size'] / 1024:.2f} KB)",
            "",
            f"Description:",
            f"  {package['description']}",
            "",
            f"Status: {'INSTALLED' if installed else 'Not installed'}",
            f"Total installs (server-wide): {install_count}",
            ""
        ]

        if package.get('channel_ids'):
            output.append(f"Unlocks {len(package['channel_ids'])} channel(s)")

        if package.get('role_ids'):
            output.append(f"Grants {len(package['role_ids'])} role(s)")

        if package.get('dependencies'):
            output.append(f"Dependencies: {', '.join(package['dependencies'])}")

        return format_code_block("\n".join(output))

    async def cmd_update(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Update package list (reload config)"""
        try:
            self.config = self.load_config()

            return format_code_block(
                "✅ Package list updated\n"
                f"Available packages: {len(self.config['packages'])}"
            )
        except Exception as e:
            return format_error(f"Failed to update package list: {str(e)}")

    async def cmd_help(self, discord_id: int, args: list, guild: discord.Guild) -> str:
        """Show APT help"""
        help_text = """
APT PACKAGE MANAGER - HELP

COMMANDS:
  apt install <package>    Install a package
  apt remove <package>     Remove an installed package
  apt list                 List installed packages
  apt list --all           List all available packages
  apt search <term>        Search for packages
  apt show <package>       Show package details
  apt update               Update package list
  apt help                 Show this help

EXAMPLES:
  apt search temp          Search for packages matching 'temp'
  apt install tempchannel  Install the tempchannel package
  apt show vip             Show details about the vip package
  apt remove gaming        Uninstall the gaming package

NOTES:
  - Packages grant access to channels and roles
  - Disk quota limits apply to installations
  - Some packages may require admin approval
  - Use 'apt list' to see your installed packages
"""
        return format_code_block(help_text)

    # === Helper Functions ===

    async def is_installed(self, user_id: int, guild_id: int, package_name: str) -> bool:
        """Check if package is installed for user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id FROM installed_packages
                WHERE user_id = ? AND guild_id = ? AND package_name = ?
            """, (user_id, guild_id, package_name))
            return bool(await cursor.fetchone())

    async def get_user_disk_usage(self, user_id: int, guild_id: int) -> int:
        """Calculate total disk usage for user's installed packages"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT package_name FROM installed_packages
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            packages = await cursor.fetchall()

        total_size = 0
        for (pkg_name,) in packages:
            pkg_info = self.config['packages'].get(pkg_name, {})
            total_size += pkg_info.get('size', 0)

        return total_size

    async def get_installed_count(self, user_id: int, guild_id: int) -> int:
        """Get count of installed packages for user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM installed_packages
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            result = await cursor.fetchone()
            return result[0] if result else 0


def setup(bot):
    bot.add_cog(APT(bot))
    print("✅ APT Package Manager cog loaded")

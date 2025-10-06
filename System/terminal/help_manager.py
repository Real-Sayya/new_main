import json
from typing import Optional
from .permissions import format_code_block, format_error

class HelpManager:
    """Dynamic help system for terminal commands"""

    def __init__(self):
        self.help_path = "Data/help_content.json"
        self.help_data = self.load_help_data()

    def load_help_data(self) -> dict:
        """Load help content from JSON"""
        try:
            with open(self.help_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Failed to load help data: {e}")
            return {"categories": {}, "aliases": {}, "notes": []}

    def get_help(self, category: Optional[str] = None, command: Optional[str] = None) -> str:
        """Get help text for category or specific command"""

        # If no category specified, show category list
        if not category:
            return self._show_categories()

        # Normalize category name
        category = category.lower()

        # Check if category exists
        if category not in self.help_data['categories']:
            return self._search_command(category)

        # If command specified, show command help
        if command:
            return self._show_command_help(category, command)

        # Otherwise show all commands in category
        return self._show_category_help(category)

    def _show_categories(self) -> str:
        """Show all available help categories"""
        categories = self.help_data['categories']

        output = [
            "╔════════════════════════════════════════════╗",
            "║      VIRTUAL TERMINAL - HELP SYSTEM       ║",
            "╚════════════════════════════════════════════╝",
            "",
            "AVAILABLE CATEGORIES:",
            ""
        ]

        for cat_key, cat_data in categories.items():
            icon = cat_data.get('icon', '📋')
            name = cat_data.get('name', cat_key.title())
            description = cat_data.get('description', '')
            cmd_count = len(cat_data.get('commands', {}))

            output.append(f"{icon} {name.upper()} ({cmd_count} commands)")
            output.append(f"   {description}")
            output.append(f"   → help {cat_key}")
            output.append("")

        output.append("=" * 48)
        output.append("USAGE:")
        output.append("  help <category>         Show commands in category")
        output.append("  help <command>          Search for a command")
        output.append("")
        output.append("EXAMPLES:")
        output.append("  help filesystem         Show file system commands")
        output.append("  help apt                Show package manager help")
        output.append("  help moderation         Show moderation commands")
        output.append("")

        # Show aliases
        if self.help_data.get('aliases'):
            output.append("ALIASES:")
            for alias, command in self.help_data['aliases'].items():
                output.append(f"  {alias:<10} = {command}")
            output.append("")

        # Show notes
        if self.help_data.get('notes'):
            output.append("NOTES:")
            for note in self.help_data['notes']:
                output.append(f"  • {note}")

        return format_code_block('\n'.join(output))

    def _show_category_help(self, category: str) -> str:
        """Show all commands in a category"""
        cat_data = self.help_data['categories'][category]
        commands = cat_data.get('commands', {})

        icon = cat_data.get('icon', '📋')
        name = cat_data.get('name', category.title())
        description = cat_data.get('description', '')

        output = [
            f"{icon} {name.upper()}",
            "=" * 48,
            description,
            "",
            "COMMANDS:",
            ""
        ]

        for cmd_name, cmd_data in commands.items():
            usage = cmd_data.get('usage', cmd_name)
            desc = cmd_data.get('description', 'No description')

            output.append(f"• {cmd_name}")
            output.append(f"  Usage: {usage}")
            output.append(f"  {desc}")
            output.append("")

        output.append("=" * 48)
        output.append(f"Type 'help {category} <command>' for detailed help")
        output.append(f"Example: help {category} {list(commands.keys())[0]}")

        return format_code_block('\n'.join(output))

    def _show_command_help(self, category: str, command: str) -> str:
        """Show detailed help for a specific command"""
        cat_data = self.help_data['categories'][category]
        commands = cat_data.get('commands', {})

        if command not in commands:
            return format_error(f"Command '{command}' not found in category '{category}'")

        cmd_data = commands[command]

        output = [
            f"COMMAND: {command}",
            "=" * 48,
            "",
            "USAGE:",
            f"  {cmd_data.get('usage', command)}",
            "",
            "DESCRIPTION:",
            f"  {cmd_data.get('description', 'No description')}",
            ""
        ]

        # Show options if available
        if cmd_data.get('options'):
            output.append("OPTIONS:")
            for option in cmd_data['options']:
                output.append(f"  {option}")
            output.append("")

        # Show examples
        if cmd_data.get('examples'):
            output.append("EXAMPLES:")
            for example in cmd_data['examples']:
                output.append(f"  $ {example}")
            output.append("")

        # Show notes
        if cmd_data.get('notes'):
            output.append("NOTES:")
            for note in cmd_data['notes']:
                output.append(f"  • {note}")
            output.append("")

        return format_code_block('\n'.join(output))

    def _search_command(self, search_term: str) -> str:
        """Search for a command across all categories"""
        search_term = search_term.lower()
        results = []

        # Search in all categories
        for cat_key, cat_data in self.help_data['categories'].items():
            commands = cat_data.get('commands', {})

            for cmd_name, cmd_data in commands.items():
                # Check if search term matches command name
                if search_term in cmd_name.lower():
                    results.append({
                        'category': cat_key,
                        'command': cmd_name,
                        'usage': cmd_data.get('usage', cmd_name),
                        'description': cmd_data.get('description', '')
                    })

        if not results:
            return format_error(
                f"No command or category found matching '{search_term}'\n"
                f"Type 'help' to see all categories"
            )

        # If only one result, show detailed help
        if len(results) == 1:
            result = results[0]
            return self._show_command_help(result['category'], result['command'])

        # Otherwise show search results
        output = [
            f"SEARCH RESULTS FOR '{search_term}':",
            "=" * 48,
            ""
        ]

        for result in results:
            cat_name = self.help_data['categories'][result['category']].get('name', result['category'])
            output.append(f"• {result['command']} ({cat_name})")
            output.append(f"  {result['usage']}")
            output.append(f"  {result['description']}")
            output.append("")

        output.append("=" * 48)
        output.append("Type 'help <category> <command>' for detailed help")

        return format_code_block('\n'.join(output))

    def get_command_usage(self, command: str) -> Optional[str]:
        """Get quick usage string for a command"""
        for cat_data in self.help_data['categories'].values():
            commands = cat_data.get('commands', {})
            if command in commands:
                return commands[command].get('usage', command)
        return None

    def reload_help_data(self) -> bool:
        """Reload help data from JSON file"""
        try:
            self.help_data = self.load_help_data()
            return True
        except:
            return False

from datetime import datetime
from .permissions import format_output, format_error, format_code_block
from .help_manager import HelpManager

class BasicCommands:
    """Basic filesystem commands"""

    def __init__(self, filesystem, user_manager):
        self.fs = filesystem
        self.um = user_manager
        self.help_manager = HelpManager()

    async def cmd_ls(self, discord_id: int, args: list) -> str:
        """List directory contents"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        
        show_all = '-a' in args or '--all' in args
        long_format = '-l' in args
        target_path = None

        for arg in args:
            if not arg.startswith('-'):
                target_path = arg
                break

        
        current_dir = session['current_dir']
        if target_path:
            path = self.fs.resolve_path(current_dir, target_path)
        else:
            path = current_dir

        
        success, result = await self.fs.list_directory(discord_id, path, show_all)

        if not success:
            return format_error(result)

        if not result:
            return format_code_block("(empty directory)")

        
        if long_format:
            output = []
            for name, ftype, size, perms, modified, executable in result:
                type_char = 'd' if ftype == 'directory' else '-'
                size_str = f"{size:>8}" if ftype == 'file' else "    <DIR>"
                mod_time = datetime.fromisoformat(modified).strftime("%Y-%m-%d %H:%M")
                output.append(f"{type_char}{perms}  {size_str}  {mod_time}  {name}")
            return format_code_block('\n'.join(output))
        else:
            
            output = []
            for name, ftype, size, perms, modified, executable in result:
                if ftype == 'directory':
                    output.append(f"{name}/")
                elif executable:
                    output.append(f"{name}*")
                else:
                    output.append(name)
            return format_code_block('  '.join(output))

    async def cmd_cd(self, discord_id: int, args: list) -> str:
        """Change directory"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if not args:
            
            username = session['username']
            target_path = f"/home/{username}"
        else:
            target_path = args[0]

        
        current_dir = session['current_dir']
        new_path = self.fs.resolve_path(current_dir, target_path)

        
        if not await self.fs.path_exists(discord_id, new_path):
            return format_error(f"No such directory: {new_path}")

        if not await self.fs.is_directory(discord_id, new_path):
            return format_error(f"Not a directory: {new_path}")

        
        self.um.update_current_directory(discord_id, new_path)

        return format_output(f"Changed directory to: {new_path}")

    async def cmd_pwd(self, discord_id: int, args: list) -> str:
        """Print working directory"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        current_dir = session['current_dir']
        return format_code_block(current_dir)

    async def cmd_mkdir(self, discord_id: int, args: list) -> str:
        """Create directory"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if not args:
            return format_error("Usage: mkdir <directory>")

        current_dir = session['current_dir']
        target_path = self.fs.resolve_path(current_dir, args[0])

        success, message = await self.fs.create_directory(discord_id, target_path)

        if success:
            return format_output(message)
        else:
            return format_error(message)

    async def cmd_touch(self, discord_id: int, args: list) -> str:
        """Create empty file"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if not args:
            return format_error("Usage: touch <filename>")

        current_dir = session['current_dir']
        target_path = self.fs.resolve_path(current_dir, args[0])

        success, message = await self.fs.create_file(discord_id, target_path, '')

        if success:
            return format_output(message)
        else:
            return format_error(message)

    async def cmd_cat(self, discord_id: int, args: list) -> str:
        """Display file contents"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if not args:
            return format_error("Usage: cat <filename>")

        current_dir = session['current_dir']
        target_path = self.fs.resolve_path(current_dir, args[0])

        success, content = await self.fs.read_file(discord_id, target_path)

        if not success:
            return format_error(content)

        if not content:
            return format_code_block("(empty file)")

        return format_code_block(content)

    async def cmd_rm(self, discord_id: int, args: list) -> str:
        """Remove file or directory"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if not args:
            return format_error("Usage: rm [-r] <file/directory>")

        recursive = '-r' in args or '-rf' in args
        target = None

        for arg in args:
            if not arg.startswith('-'):
                target = arg
                break

        if not target:
            return format_error("No file/directory specified")

        current_dir = session['current_dir']
        target_path = self.fs.resolve_path(current_dir, target)

        
        protected_dirs = ['/', '/home', '/var', '/apps']
        if target_path in protected_dirs:
            return format_error(f"Cannot remove protected directory: {target_path}")

        success, message = await self.fs.remove_item(discord_id, target_path, recursive)

        if success:
            return format_output(message)
        else:
            return format_error(message)

    async def cmd_echo(self, discord_id: int, args: list) -> str:
        """Echo text or write to file"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if not args:
            return format_code_block("")

        
        if '>' in args:
            redirect_index = args.index('>')
            text = ' '.join(args[:redirect_index])

            if redirect_index + 1 < len(args):
                filename = args[redirect_index + 1]
                current_dir = session['current_dir']
                target_path = self.fs.resolve_path(current_dir, filename)

                
                if await self.fs.path_exists(discord_id, target_path):
                    
                    success, message = await self.fs.write_file(discord_id, target_path, text)
                else:
                    
                    success, message = await self.fs.create_file(discord_id, target_path, text)

                if success:
                    return format_output(f"Content written to {filename}")
                else:
                    return format_error(message)
            else:
                return format_error("No filename specified after '>'")
        else:
            
            text = ' '.join(args)
            return format_code_block(text)

    async def cmd_clear(self, discord_id: int, args: list, channel = None) -> str:
        """Clear channel messages (purge)"""
        if not channel:
            return format_error("Clear command requires channel context")

        
        limit = 100  
        if args and args[0].isdigit():
            limit = int(args[0])
            limit = min(limit, 1000)  

        
        try:
            
            permissions = channel.permissions_for(channel.guild.me)
            if not permissions.manage_messages:
                return format_error("Bot lacks 'Manage Messages' permission")

            
            session = self.um.get_session(discord_id)
            username = session['username'] if session else str(discord_id)

            
            deleted = await channel.purge(limit=limit + 1)  

            
            from .logger_manager import TerminalLogger
            TerminalLogger.log_system(
                f"Channel purged by {username}: {len(deleted)} messages deleted in #{channel.name}",
                level="WARNING"
            )

            
            import asyncio
            confirmation = await channel.send(
                format_output(f"✅ Cleared {len(deleted)} message(s) from this channel")
            )
            await asyncio.sleep(5)
            try:
                await confirmation.delete()
            except:
                pass  

            return None  

        except Exception as e:
            return format_error(f"Failed to clear channel: {str(e)}")

    async def cmd_whoami(self, discord_id: int, args: list) -> str:
        """Display current user info"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        username = session['username']
        role = session['role']
        login_time = session['login_time'].strftime("%Y-%m-%d %H:%M:%S")
        current_dir = session['current_dir']

        output = f"""Username: {username}
Role: {role}
Login Time: {login_time}
Current Directory: {current_dir}
Discord ID: {discord_id}"""

        return format_code_block(output)

    async def cmd_help(self, discord_id: int, args: list) -> str:
        """Display dynamic help menu"""
        
        category = args[0] if len(args) > 0 else None
        command = args[1] if len(args) > 1 else None

        
        return self.help_manager.get_help(category, command)

    async def cmd_tree(self, discord_id: int, args: list) -> str:
        """Display directory tree"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        current_dir = session['current_dir']
        target_path = args[0] if args else current_dir
        path = self.fs.resolve_path(current_dir, target_path)

        async def build_tree(path, prefix="", is_last=True):
            success, entries = await self.fs.list_directory(discord_id, path, show_all=False)
            if not success:
                return ""

            output = []
            for i, (name, ftype, *_) in enumerate(entries):
                is_last_item = (i == len(entries) - 1)
                connector = "└── " if is_last_item else "├── "

                if ftype == 'directory':
                    output.append(f"{prefix}{connector}{name}/")
                    extension = "    " if is_last_item else "│   "
                    subtree = await build_tree(f"{path}/{name}", prefix + extension, is_last_item)
                    if subtree:
                        output.append(subtree)
                else:
                    output.append(f"{prefix}{connector}{name}")

            return '\n'.join(output)

        tree_output = f"{path}/\n" + await build_tree(path)
        return format_code_block(tree_output)

    async def cmd_mv(self, discord_id: int, args: list) -> str:
        """Move or rename file/directory"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if len(args) < 2:
            return format_error("Usage: mv <source> <destination>")

        current_dir = session['current_dir']
        source = self.fs.resolve_path(current_dir, args[0])
        destination = self.fs.resolve_path(current_dir, args[1])

        success, message = await self.fs.move_item(discord_id, source, destination)

        if success:
            return format_output(message)
        else:
            return format_error(message)

    async def cmd_cp(self, discord_id: int, args: list) -> str:
        """Copy file or directory"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if len(args) < 2:
            return format_error("Usage: cp [-r] <source> <destination>")

        recursive = '-r' in args or '-R' in args
        filtered_args = [arg for arg in args if not arg.startswith('-')]

        if len(filtered_args) < 2:
            return format_error("Usage: cp [-r] <source> <destination>")

        current_dir = session['current_dir']
        source = self.fs.resolve_path(current_dir, filtered_args[0])
        destination = self.fs.resolve_path(current_dir, filtered_args[1])

        success, message = await self.fs.copy_item(discord_id, source, destination, recursive)

        if success:
            return format_output(message)
        else:
            return format_error(message)

    async def cmd_chmod(self, discord_id: int, args: list) -> str:
        """Change file permissions"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if len(args) < 2:
            return format_error("Usage: chmod <mode> <file>\nExamples: chmod 755 file.txt OR chmod rwxr-xr-x file.txt")

        mode = args[0]
        current_dir = session['current_dir']
        target_path = self.fs.resolve_path(current_dir, args[1])

        success, message = await self.fs.change_permissions(discord_id, target_path, mode)

        if success:
            return format_output(message)
        else:
            return format_error(message)

    async def cmd_find(self, discord_id: int, args: list) -> str:
        """Find files by name pattern"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        current_dir = session['current_dir']
        search_path = current_dir

        
        pattern = None
        file_type = None

        for i, arg in enumerate(args):
            if arg == '-name' and i + 1 < len(args):
                pattern = args[i + 1]
            elif arg == '-type' and i + 1 < len(args):
                type_char = args[i + 1]
                file_type = 'directory' if type_char == 'd' else 'file' if type_char == 'f' else None
            elif not arg.startswith('-') and arg != pattern:
                search_path = self.fs.resolve_path(current_dir, arg)

        results = await self.fs.find_files(discord_id, search_path, pattern, file_type)

        if not results:
            return format_code_block("No files found")

        output = []
        for path, name, ftype in results:
            type_indicator = '/' if ftype == 'directory' else ''
            output.append(f"{path}{type_indicator}")

        return format_code_block('\n'.join(output))

    async def cmd_grep(self, discord_id: int, args: list) -> str:
        """Search for pattern in file contents"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        if not args:
            return format_error("Usage: grep <pattern> [path]")

        pattern = args[0]
        search_path = None

        if len(args) > 1:
            current_dir = session['current_dir']
            search_path = self.fs.resolve_path(current_dir, args[1])

        results = await self.fs.grep_content(discord_id, pattern, search_path)

        if not results:
            return format_code_block(f"No matches found for '{pattern}'")

        output = []
        for path, matches in results:
            output.append(f"\n{path}:")
            for line_num, line in matches:
                output.append(f"  {line_num}: {line.strip()}")

        return format_code_block('\n'.join(output))

    async def cmd_du(self, discord_id: int, args: list) -> str:
        """Display disk usage statistics"""
        session = self.um.get_session(discord_id)
        if not session:
            return format_error("Not logged in")

        stats = await self.fs.get_disk_usage(discord_id)

        output = [
            "DISK USAGE STATISTICS",
            "=" * 40,
            f"Files:        {stats['total_files']}",
            f"Directories:  {stats['total_directories']}",
            f"Total Size:   {stats['total_size']:,} bytes ({stats['total_size'] / 1024:.2f} KB)",
            f"Files Size:   {stats['files_size']:,} bytes",
            "=" * 40
        ]

        return format_code_block('\n'.join(output))

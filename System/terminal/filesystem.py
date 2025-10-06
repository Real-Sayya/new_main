import aiosqlite
import json
from datetime import datetime
from pathlib import Path
import os

class VirtualFilesystem:
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "Data/terminal_fs.db"
        self.config_path = "Data/terminal_config.json"
        self.config = self.load_config()

    def load_config(self):
        """Load configuration from JSON"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def setup_database(self):
        """Initialize filesystem database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS filesystem (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT,
                    permissions TEXT DEFAULT 'rwxr-xr-x',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    size INTEGER DEFAULT 0,
                    executable INTEGER DEFAULT 0,
                    UNIQUE(owner_id, path)
                )
            """)
            await db.commit()
            print("✅ Filesystem database initialized")

    async def initialize_user_filesystem(self, discord_id: int, username: str):
        """Create default filesystem structure for new user"""
        default_dirs = self.config['default_filesystem']['directories']
        default_files = self.config['default_filesystem']['files']

        async with aiosqlite.connect(self.db_path) as db:
            # Create user's home directory
            user_home = f"/home/{username}"
            await self.create_directory(discord_id, user_home, db)

            # Create subdirectories in user home
            for subdir in ['documents', 'downloads', '.config']:
                await self.create_directory(discord_id, f"{user_home}/{subdir}", db)

            # Create default directories (if not exist)
            for directory in default_dirs:
                # Skip creating /home since we create user-specific ones
                if directory != "/home":
                    await self.create_directory(discord_id, directory, db)

            # Create default files
            for filepath, filedata in default_files.items():
                content = filedata.get('content', '')
                # Replace {username} placeholder
                content = content.replace('{username}', username)

                file_type = filedata.get('type', 'file')
                executable = 1 if filedata.get('executable', False) else 0

                await self.create_file(
                    discord_id,
                    filepath,
                    content,
                    file_type=file_type,
                    executable=executable,
                    db=db
                )

            await db.commit()
            print(f"✅ Initialized filesystem for user {username}")

    async def create_directory(self, owner_id: int, path: str, db=None):
        """Create a directory"""
        should_close = db is None
        if db is None:
            db = await aiosqlite.connect(self.db_path)

        try:
            # Normalize path
            path = self.normalize_path(path)
            name = Path(path).name or '/'

            # Check if already exists
            cursor = await db.execute(
                "SELECT id FROM filesystem WHERE owner_id = ? AND path = ?",
                (owner_id, path)
            )
            if await cursor.fetchone():
                return False, "Directory already exists"

            # Insert directory
            await db.execute("""
                INSERT INTO filesystem (owner_id, path, name, type, permissions)
                VALUES (?, ?, ?, 'directory', 'rwxr-xr-x')
            """, (owner_id, path, name))

            if should_close:
                await db.commit()

            return True, f"Directory created: {path}"

        finally:
            if should_close:
                await db.close()

    async def create_file(self, owner_id: int, path: str, content: str = '', file_type: str = 'file', executable: int = 0, db=None):
        """Create a file"""
        should_close = db is None
        if db is None:
            db = await aiosqlite.connect(self.db_path)

        try:
            path = self.normalize_path(path)
            name = Path(path).name
            size = len(content)

            # Check if already exists
            cursor = await db.execute(
                "SELECT id FROM filesystem WHERE owner_id = ? AND path = ?",
                (owner_id, path)
            )
            if await cursor.fetchone():
                return False, "File already exists"

            permissions = 'rwxr-xr-x' if executable else 'rw-r--r--'

            await db.execute("""
                INSERT INTO filesystem (owner_id, path, name, type, content, size, permissions, executable)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (owner_id, path, name, file_type, content, size, permissions, executable))

            if should_close:
                await db.commit()

            return True, f"File created: {path}"

        finally:
            if should_close:
                await db.close()

    async def read_file(self, owner_id: int, path: str) -> tuple[bool, str]:
        """Read file content"""
        path = self.normalize_path(path)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT type, content, executable FROM filesystem
                WHERE owner_id = ? AND path = ?
            """, (owner_id, path))
            result = await cursor.fetchone()

            if not result:
                return False, f"File not found: {path}"

            file_type, content, executable = result

            if file_type == 'directory':
                return False, f"{path} is a directory"

            return True, content or ''

    async def write_file(self, owner_id: int, path: str, content: str) -> tuple[bool, str]:
        """Write content to file"""
        path = self.normalize_path(path)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT type FROM filesystem
                WHERE owner_id = ? AND path = ?
            """, (owner_id, path))
            result = await cursor.fetchone()

            if not result:
                return False, f"File not found: {path}"

            if result[0] == 'directory':
                return False, f"{path} is a directory"

            size = len(content)
            await db.execute("""
                UPDATE filesystem
                SET content = ?, size = ?, modified_at = ?
                WHERE owner_id = ? AND path = ?
            """, (content, size, datetime.now(), owner_id, path))
            await db.commit()

            return True, f"File updated: {path}"

    async def list_directory(self, owner_id: int, path: str, show_all: bool = False) -> tuple[bool, list]:
        """List directory contents"""
        path = self.normalize_path(path)

        async with aiosqlite.connect(self.db_path) as db:
            # Check if path exists and is a directory
            cursor = await db.execute("""
                SELECT type FROM filesystem
                WHERE owner_id = ? AND path = ?
            """, (owner_id, path))
            result = await cursor.fetchone()

            if not result:
                return False, f"Directory not found: {path}"

            if result[0] != 'directory':
                return False, f"{path} is not a directory"

            # List contents
            search_pattern = f"{path}/%"
            if path == '/':
                search_pattern = '/%'

            cursor = await db.execute("""
                SELECT name, type, size, permissions, modified_at, executable
                FROM filesystem
                WHERE owner_id = ? AND path LIKE ? AND path NOT LIKE ?
                ORDER BY type DESC, name ASC
            """, (owner_id, search_pattern, search_pattern.replace('%', '%/%')))

            entries = await cursor.fetchall()

            # Filter hidden files if not show_all
            if not show_all:
                entries = [e for e in entries if not e[0].startswith('.')]

            return True, entries

    async def remove_item(self, owner_id: int, path: str, recursive: bool = False) -> tuple[bool, str]:
        """Remove file or directory"""
        path = self.normalize_path(path)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT type FROM filesystem
                WHERE owner_id = ? AND path = ?
            """, (owner_id, path))
            result = await cursor.fetchone()

            if not result:
                return False, f"No such file or directory: {path}"

            item_type = result[0]

            # If directory, check if empty or recursive
            if item_type == 'directory':
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM filesystem
                    WHERE owner_id = ? AND path LIKE ?
                """, (owner_id, f"{path}/%"))
                count = (await cursor.fetchone())[0]

                if count > 0 and not recursive:
                    return False, f"Directory not empty. Use 'rm -r' to remove recursively"

                # Remove directory and all contents
                if recursive:
                    await db.execute("""
                        DELETE FROM filesystem
                        WHERE owner_id = ? AND (path = ? OR path LIKE ?)
                    """, (owner_id, path, f"{path}/%"))
                else:
                    await db.execute("""
                        DELETE FROM filesystem
                        WHERE owner_id = ? AND path = ?
                    """, (owner_id, path))
            else:
                # Remove file
                await db.execute("""
                    DELETE FROM filesystem
                    WHERE owner_id = ? AND path = ?
                """, (owner_id, path))

            await db.commit()
            return True, f"Removed: {path}"

    async def path_exists(self, owner_id: int, path: str) -> bool:
        """Check if path exists"""
        path = self.normalize_path(path)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id FROM filesystem
                WHERE owner_id = ? AND path = ?
            """, (owner_id, path))
            return bool(await cursor.fetchone())

    async def is_directory(self, owner_id: int, path: str) -> bool:
        """Check if path is a directory"""
        path = self.normalize_path(path)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT type FROM filesystem
                WHERE owner_id = ? AND path = ?
            """, (owner_id, path))
            result = await cursor.fetchone()
            return result and result[0] == 'directory'

    def normalize_path(self, path: str) -> str:
        """Normalize filesystem path"""
        if not path.startswith('/'):
            path = '/' + path

        # Remove trailing slash except for root
        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')

        # Resolve . and ..
        parts = []
        for part in path.split('/'):
            if part == '' or part == '.':
                continue
            elif part == '..':
                if parts:
                    parts.pop()
            else:
                parts.append(part)

        return '/' + '/'.join(parts) if parts else '/'

    def resolve_path(self, current_dir: str, target_path: str) -> str:
        """Resolve relative or absolute path"""
        if target_path.startswith('/'):
            # Absolute path
            return self.normalize_path(target_path)
        else:
            # Relative path
            combined = f"{current_dir}/{target_path}"
            return self.normalize_path(combined)

    async def get_file_info(self, owner_id: int, path: str) -> dict:
        """Get detailed file information"""
        path = self.normalize_path(path)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT name, type, size, permissions, created_at, modified_at, executable
                FROM filesystem
                WHERE owner_id = ? AND path = ?
            """, (owner_id, path))
            result = await cursor.fetchone()

            if not result:
                return None

            return {
                'name': result[0],
                'type': result[1],
                'size': result[2],
                'permissions': result[3],
                'created_at': result[4],
                'modified_at': result[5],
                'executable': bool(result[6])
            }

    async def move_item(self, owner_id: int, source: str, destination: str) -> tuple[bool, str]:
        """Move or rename file/directory"""
        source = self.normalize_path(source)
        destination = self.normalize_path(destination)

        async with aiosqlite.connect(self.db_path) as db:
            # Check if source exists
            cursor = await db.execute("""
                SELECT type FROM filesystem WHERE owner_id = ? AND path = ?
            """, (owner_id, source))
            source_data = await cursor.fetchone()

            if not source_data:
                return False, f"Source not found: {source}"

            # Check if destination already exists
            cursor = await db.execute("""
                SELECT type FROM filesystem WHERE owner_id = ? AND path = ?
            """, (owner_id, destination))
            if await cursor.fetchone():
                return False, f"Destination already exists: {destination}"

            source_type = source_data[0]

            # Update path for the item
            await db.execute("""
                UPDATE filesystem SET path = ?, name = ?, modified_at = ?
                WHERE owner_id = ? AND path = ?
            """, (destination, Path(destination).name, datetime.now(), owner_id, source))

            # If directory, update all children paths
            if source_type == 'directory':
                cursor = await db.execute("""
                    SELECT path FROM filesystem
                    WHERE owner_id = ? AND path LIKE ?
                """, (owner_id, f"{source}/%"))

                children = await cursor.fetchall()
                for (old_path,) in children:
                    new_path = old_path.replace(source, destination, 1)
                    await db.execute("""
                        UPDATE filesystem SET path = ?
                        WHERE owner_id = ? AND path = ?
                    """, (new_path, owner_id, old_path))

            await db.commit()
            return True, f"Moved: {source} → {destination}"

    async def copy_item(self, owner_id: int, source: str, destination: str, recursive: bool = False) -> tuple[bool, str]:
        """Copy file or directory"""
        source = self.normalize_path(source)
        destination = self.normalize_path(destination)

        async with aiosqlite.connect(self.db_path) as db:
            # Check if source exists
            cursor = await db.execute("""
                SELECT type, content, permissions, executable FROM filesystem
                WHERE owner_id = ? AND path = ?
            """, (owner_id, source))
            source_data = await cursor.fetchone()

            if not source_data:
                return False, f"Source not found: {source}"

            source_type, content, permissions, executable = source_data

            # Check if destination exists
            cursor = await db.execute("""
                SELECT type FROM filesystem WHERE owner_id = ? AND path = ?
            """, (owner_id, destination))
            if await cursor.fetchone():
                return False, f"Destination already exists: {destination}"

            # Copy based on type
            if source_type == 'file':
                size = len(content) if content else 0
                await db.execute("""
                    INSERT INTO filesystem (owner_id, path, name, type, content, size, permissions, executable)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (owner_id, destination, Path(destination).name, source_type, content, size, permissions, executable))

            elif source_type == 'directory':
                if not recursive:
                    return False, "Cannot copy directory without -r flag"

                # Create destination directory
                await db.execute("""
                    INSERT INTO filesystem (owner_id, path, name, type, permissions)
                    VALUES (?, ?, ?, 'directory', ?)
                """, (owner_id, destination, Path(destination).name, permissions))

                # Copy all children
                cursor = await db.execute("""
                    SELECT path, name, type, content, size, permissions, executable FROM filesystem
                    WHERE owner_id = ? AND path LIKE ?
                """, (owner_id, f"{source}/%"))

                children = await cursor.fetchall()
                for child in children:
                    old_path, name, c_type, c_content, c_size, c_perms, c_exec = child
                    new_path = old_path.replace(source, destination, 1)

                    await db.execute("""
                        INSERT INTO filesystem (owner_id, path, name, type, content, size, permissions, executable)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (owner_id, new_path, name, c_type, c_content, c_size, c_perms, c_exec))

            await db.commit()
            return True, f"Copied: {source} → {destination}"

    async def change_permissions(self, owner_id: int, path: str, mode: str) -> tuple[bool, str]:
        """Change file permissions (chmod)"""
        path = self.normalize_path(path)

        # Validate mode (simple rwx format or octal)
        if not self._is_valid_mode(mode):
            return False, f"Invalid permissions mode: {mode}"

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id FROM filesystem WHERE owner_id = ? AND path = ?
            """, (owner_id, path))

            if not await cursor.fetchone():
                return False, f"File not found: {path}"

            # Convert mode to rwx format if octal
            permissions = self._mode_to_permissions(mode)

            # Update executable flag based on permissions
            executable = 1 if 'x' in permissions[:3] else 0

            await db.execute("""
                UPDATE filesystem SET permissions = ?, executable = ?, modified_at = ?
                WHERE owner_id = ? AND path = ?
            """, (permissions, executable, datetime.now(), owner_id, path))

            await db.commit()
            return True, f"Changed permissions of '{path}' to {permissions}"

    async def find_files(self, owner_id: int, search_path: str, pattern: str = None, file_type: str = None) -> list:
        """Find files matching pattern"""
        search_path = self.normalize_path(search_path)

        async with aiosqlite.connect(self.db_path) as db:
            query = """
                SELECT path, name, type FROM filesystem
                WHERE owner_id = ? AND (path = ? OR path LIKE ?)
            """
            params = [owner_id, search_path, f"{search_path}/%"]

            if file_type:
                query += " AND type = ?"
                params.append(file_type)

            cursor = await db.execute(query, params)
            results = await cursor.fetchall()

            # Filter by pattern if provided
            if pattern:
                results = [r for r in results if pattern.lower() in r[1].lower()]

            return results

    async def grep_content(self, owner_id: int, pattern: str, search_path: str = None) -> list:
        """Search for pattern in file contents"""
        async with aiosqlite.connect(self.db_path) as db:
            query = """
                SELECT path, name, content FROM filesystem
                WHERE owner_id = ? AND type = 'file' AND content LIKE ?
            """
            params = [owner_id, f"%{pattern}%"]

            if search_path:
                search_path = self.normalize_path(search_path)
                query += " AND (path = ? OR path LIKE ?)"
                params.extend([search_path, f"{search_path}/%"])

            cursor = await db.execute(query, params)
            results = await cursor.fetchall()

            # Format results with line numbers
            formatted_results = []
            for path, name, content in results:
                if content:
                    lines = content.split('\n')
                    matches = []
                    for i, line in enumerate(lines, 1):
                        if pattern.lower() in line.lower():
                            matches.append((i, line))
                    if matches:
                        formatted_results.append((path, matches))

            return formatted_results

    async def get_disk_usage(self, owner_id: int) -> dict:
        """Get disk usage statistics for user"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT COUNT(*), SUM(size), type FROM filesystem
                WHERE owner_id = ?
                GROUP BY type
            """, (owner_id,))
            results = await cursor.fetchall()

            stats = {
                'total_files': 0,
                'total_directories': 0,
                'total_size': 0,
                'files_size': 0
            }

            for count, size, file_type in results:
                if file_type == 'file':
                    stats['total_files'] = count
                    stats['files_size'] = size or 0
                elif file_type == 'directory':
                    stats['total_directories'] = count

                stats['total_size'] += size or 0

            return stats

    def _is_valid_mode(self, mode: str) -> bool:
        """Validate chmod mode string"""
        # Check if octal (e.g., 755)
        if mode.isdigit() and len(mode) == 3:
            return all(0 <= int(d) <= 7 for d in mode)

        # Check if symbolic (e.g., rwxr-xr-x)
        if len(mode) == 9:
            valid_chars = set('rwx-')
            return all(c in valid_chars for c in mode)

        return False

    def _mode_to_permissions(self, mode: str) -> str:
        """Convert mode to permission string"""
        if mode.isdigit():
            # Octal to rwx
            perms = ''
            for digit in mode:
                d = int(digit)
                perms += 'r' if d & 4 else '-'
                perms += 'w' if d & 2 else '-'
                perms += 'x' if d & 1 else '-'
            return perms
        else:
            return mode

    def check_permission(self, permissions: str, action: str) -> bool:
        """Check if action is allowed based on permissions"""
        # Simple owner permissions check (first 3 chars)
        owner_perms = permissions[:3]

        permission_map = {
            'read': 'r',
            'write': 'w',
            'execute': 'x'
        }

        required = permission_map.get(action)
        if not required:
            return False

        return required in owner_perms

import asyncio
import datetime

import discord
from discord.ext import commands
import aiosqlite
from discord.commands import slash_command, Option
import pyfiglet
import re
from Team.blacklist import db as blacklist_db
import os
import chat_exporter
import io
from Data.permissons import admin

pyfiglet.print_figlet('GSv2.0')
TOKEN = 'MTM3ODEwNDU5Mjg4MDg5ODA0OQ.GK1gPH.wr4TYuwUOOpt4oNneCmOgtydrigZ37noW3dy88'
bot = commands.Bot(command_prefix='!', debug_guilds=None, intents=discord.Intents.all())
conn: aiosqlite.Connection = None

TICKET_CATEGORIES = {
    "allgemein": {
        "role_ids": [1331410805786279998],  # Mehrere Rollen-IDs als Liste
        "keywords": [
            "frage", "hilfe", "support", "problem", "info", "anfrage", "allgemein", "chat",
            "ich habe eine frage", "wie funktioniert das?", "wer kann mir helfen?",
            "wo finde ich das?", "kann mir jemand erklären?", "brauche unterstützung"
        ],
        "channel_prefix": "📋-allgemein"
    },
    "technisch": {
        "role_ids": [1331410875835219968],  # Mehrere Rollen-IDs als Liste
        "keywords": [
            "bug", "fehler", "funktioniert nicht", "error", "problem", "bot", "discord",
            "crash", "technisch", "update", "es gibt ein problem",
            "der server hat einen fehler", "hilfe bei einem fehler",
        ],
        "channel_prefix": "🔧-technisch"
    },
    "moderation": {
        "role_ids": [1331409215096488016, 1331408653193838592],  # Zwei Rollen-IDs als Beispiel
        "keywords": [
            "warnung", "bann", "kick", "mute", "report", "melden", "user", "spam",
            "regel", "admin", "verstoß", "jemand spammt", "ein user benimmt sich schlecht",
            "bitte überprüfen", "kann ein moderator helfen?", "regelverstoß melden",
            "dieser user hat gespammt", "unangebrachtes verhalten"
        ],
        "channel_prefix": "🛡️-admin"
    },
    "partner": {
        "role_ids": [1331409215096488016],  # Mehrere Rollen-IDs als Liste
        "keywords": [
            "partner", "werbung", "kollaboration", "zusammenarbeit", "kooperation", "promo",
            "wir möchten zusammenarbeiten", "können wir partner werden?", "partneranfrage",
            "werbepartnerschaft", "wir suchen eine kooperation", "idee für eine partnerschaft"
        ],
        "channel_prefix": "🤝-partner"
    }
}


category_id = 1378366027586600960
guild_id = 1356278624411713676
log_channel_id = 1378360358602801182

if __name__ == '__main__':
    for filename in os.listdir('System'):
        if filename.endswith('.py'):
            bot.load_extension(f'System.{filename[:-3]}')
            print(f'Load System_command: {filename[:-3]}')
    for filename in os.listdir('Team'):
        if filename.endswith('.py'):
            bot.load_extension(f'Team.{filename[:-3]}')
            print(f'Load Team_command: {filename[:-3]}')
    for filename in os.listdir('Community'):
        if filename.endswith('.py'):
            bot.load_extension(f'Community.{filename[:-3]}')
            print(f'Load Community_command: {filename[:-3]}')

@bot.event
async def on_ready():
    await setup_database()
    print("Database connection established!")
    bot.add_view(menu())
    bot.add_view(TutorialView())
    bot.add_view(Ticketweiterleitung())
    bot.add_view(Ticketmenu())
    bot.add_view(DMMenu())
    await bot.change_presence(activity=discord.Game(name='GSv2.0 Mainsystem'), status=discord.Status.dnd)
    print(f"Logged in as {bot.user}")

async def setup_hook():
    chat_exporter.init_exporter(bot)

async def setup_database():
    global conn
    conn = await aiosqlite.connect("Data/tickets.db")

    # Create tickets table
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS tickets (
            channel_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            blocked INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0,
            claimed_by INTEGER,
            claimed_at TIMESTAMP
        )""")
    table_info = await conn.execute_fetchall("PRAGMA table_info(tickets)")
    if not any(column[1] == "category" for column in table_info):  # column[1] is the name
        await conn.execute("""
            ALTER TABLE tickets 
            ADD COLUMN category TEXT DEFAULT 'allgemein'
        """)

    # Add category stats table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS category_stats (
            category TEXT PRIMARY KEY,
            total_tickets INTEGER DEFAULT 0,
            avg_resolution_time INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create ticket queue table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ticket_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create pending tickets table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_tickets (
            user_id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create ticket stats table
    table_info = await conn.execute("PRAGMA table_info(tickets)")
    table_info = await table_info.fetchall()
    if not any(column[1] == "category" for column in table_info):
        await conn.execute("""
               ALTER TABLE tickets 
               ADD COLUMN category TEXT DEFAULT 'allgemein'
           """)

    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ticket_stats'")
    table_exists = await cursor.fetchone()

    if not table_exists:
        await conn.execute(
            """CREATE TABLE ticket_stats (
                team_member_id INTEGER PRIMARY KEY,
                tickets_handled INTEGER DEFAULT 0,
                tickets_closed INTEGER DEFAULT 0,
                avg_response_time REAL DEFAULT 0,
                total_response_time REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
    else:
        # Check if total_response_time column exists
        cursor = await conn.execute("PRAGMA table_info(ticket_stats)")
        columns = await cursor.fetchall()
        if not any(column[1] == "total_response_time" for column in columns):
            # Add the missing column
            await conn.execute(
                "ALTER TABLE ticket_stats ADD COLUMN total_response_time REAL DEFAULT 0")
            print("Added total_response_time column to ticket_stats table")

    cursor = await conn.execute("PRAGMA table_info(ticket_stats)")
    columns = await cursor.fetchall()

    await conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                team_member_id INTEGER,
                rating INTEGER,
                feedback_text TEXT,
                created_at DATETIME
            )
        """)

    if not any(column[1] == "avg_rating" for column in columns):
        await conn.execute("ALTER TABLE ticket_stats ADD COLUMN avg_rating REAL DEFAULT 0")
        await conn.execute("ALTER TABLE ticket_stats ADD COLUMN total_ratings INTEGER DEFAULT 0")

    await conn.commit()
    print("Database setup completed successfully!")



async def categorize_ticket(message_content: str) -> str:
    message_content = message_content.lower()
    category_scores = {category: 0 for category in TICKET_CATEGORIES}

    for category, data in TICKET_CATEGORIES.items():
        for keyword in data["keywords"]:
            if keyword in message_content:
                category_scores[category] += 1

    # Wenn keine Kategorie gefunden wurde, verwende "allgemein"
    best_category = max(category_scores.items(), key=lambda x: x[1])[0]
    return best_category if category_scores[best_category] > 0 else "allgemein"


async def send_feedback_request(channel, ticket_id: str, team_member_id: int):
    embed = discord.Embed(
        title="📝 Feedback",
        description="Wie zufrieden warst du mit der Bearbeitung deines Tickets?\nBitte bewerte mit 1-5 Sternen:",
        color=discord.Color.blue())

    view = FeedbackView(ticket_id, team_member_id)
    await channel.send(embed=embed, view=view)

async def update_team_member_stats(self, rating: int):
    async with conn as db:
        cursor = await db.execute("""
                SELECT avg_rating, total_ratings 
                FROM ticket_stats 
                WHERE team_member_id = ?
            """, (self.team_member_id,))
        stats = await cursor.fetchone()

        if stats is None:
            current_avg = 0
            total_ratings = 0
        else:
            current_avg = stats[0] or 0
            total_ratings = stats[1] or 0

        new_total = total_ratings + 1
        new_avg = ((current_avg * total_ratings) + rating) / new_total

        await db.execute("""
                UPDATE ticket_stats 
                SET avg_rating = ?, total_ratings = ?
                WHERE team_member_id = ?
            """, (round(new_avg, 2), new_total, self.team_member_id))
        await db.commit()

async def update_ticket_stats(team_member_id: int, action_type: str = None, response_time: float = None):
    global conn

    if conn is None:
        print("No database connection! Attempting to reconnect...")
        await setup_database()

    try:
        cursor = await conn.execute(
            """SELECT tickets_handled, tickets_closed, avg_response_time, 
                    COALESCE(total_response_time, 0) as total_response_time 
               FROM ticket_stats WHERE team_member_id = ?""",
            (team_member_id,))
        stats = await cursor.fetchone()

        print(f"Current stats for team member {team_member_id}: {stats}")

        if stats is None:
            print(f"Creating new stats entry for team member {team_member_id}")
            await conn.execute(
                """INSERT INTO ticket_stats 
                   (team_member_id, tickets_handled, tickets_closed, avg_response_time, total_response_time) 
                   VALUES (?, 0, 0, 0, 0)""",
                (team_member_id,))
            stats = (0, 0, 0, 0)

        if action_type == "handle":
            print(f"Updating handled tickets for {team_member_id}")
            await conn.execute(
                "UPDATE ticket_stats SET tickets_handled = tickets_handled + 1 WHERE team_member_id = ?",
                (team_member_id,))
        elif action_type == "close":
            print(f"Updating closed tickets for {team_member_id}")
            await conn.execute(
                "UPDATE ticket_stats SET tickets_closed = tickets_closed + 1 WHERE team_member_id = ?",
                (team_member_id,))

        if response_time is not None:
            new_total_time = stats[3] + response_time
            new_handled = stats[0] + 1
            new_avg = new_total_time / new_handled if new_handled > 0 else 0

            print(f"Updating response time stats for {team_member_id}")
            print(f"New average: {new_avg}, New total time: {new_total_time}")

            await conn.execute(
                """UPDATE ticket_stats 
                   SET avg_response_time = ?, total_response_time = ? 
                   WHERE team_member_id = ?""",
                (round(new_avg, 2), new_total_time, team_member_id))
        await conn.commit()

        cursor = await conn.execute("SELECT * FROM ticket_stats WHERE team_member_id = ?", (team_member_id,))
        result = await cursor.fetchone()
        print(f"Updated stats: {result}")

    except Exception as e:
        print(f"Error updating ticket stats: {e}")
        print(f"Team member ID: {team_member_id}")
        print(f"Action type: {action_type}")
        print(f"Response time: {response_time}")

async def has_ticket(user_id):
    cursor = await conn.execute("SELECT * FROM tickets WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return bool(row)

async def create_or_queue_ticket(user_id, message):
    cursor = await conn.execute("SELECT COUNT(*) FROM tickets")
    ticket_count = await cursor.fetchone()

    if ticket_count[0] >= 5:
        await conn.execute("INSERT INTO ticket_queue (user_id) VALUES (?)", (user_id,))
        await conn.commit()
        await message.channel.send(
            "Es sind momentan zu viele Tickets offen. Dein Ticket wurde in die Warteschlange gestellt und wird erstellt, sobald ein Platz frei wird.")
    else:
        await create_ticket(user_id, message)



async def get_open_ticket_count():
    cursor = await conn.execute("SELECT COUNT(*) FROM tickets")
    count = await cursor.fetchone()
    return count[0]


async def close_database():
    global conn
    if conn:
        await conn.close()
        print("Database connection closed!")


async def close_ticket(channel_id):
    cursor = await conn.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (channel_id,))
    row = await cursor.fetchone()
    if row is None:
        return
    user_id = row[0]

    await conn.execute("DELETE FROM tickets WHERE channel_id = ?", (channel_id,))
    await conn.commit()

    cursor = await conn.execute("SELECT id, user_id FROM ticket_queue ORDER BY id ASC LIMIT 1")
    row = await cursor.fetchone()

    if row:
        queued_ticket_id, queued_user_id = row
        await create_ticket(queued_user_id, None)
        await conn.execute("DELETE FROM ticket_queue WHERE id = ?", (queued_ticket_id,))
        await conn.commit()

    print(f"Ticket {channel_id} wurde geschlossen und ein Ticket aus der Warteschlange erstellt.")


async def create_ticket(user_id, message):
    guild = bot.get_guild(guild_id)
    category = guild.get_channel(category_id)

    # Kategorisiere das Ticket basierend auf der ersten Nachricht
    ticket_category = await categorize_ticket(message.content)
    category_data = TICKET_CATEGORIES[ticket_category]

    # Create the channel with category prefix
    channel_name = f"{category_data['channel_prefix']}-{message.author.name}"
    channel = await category.create_text_channel(channel_name)

    # Insert ticket into database with category
    await conn.execute("""
        INSERT INTO tickets (user_id, channel_id, category) 
        VALUES (?, ?, ?)
    """, (user_id, channel.id, ticket_category))
    await conn.commit()

    # Send confirmation to user
    user_embed = discord.Embed(
        title="Ticket erstellt",
        description=f"Dein Ticket wurde erfolgreich in der Kategorie '{ticket_category}' erstellt. "
                    f"Ein Teammitglied wird sich in Kürze bei dir melden.",
        color=discord.Color.green())
    await message.channel.send(embed=user_embed)

    team_embed = discord.Embed(
        title=f"📩 Neues {ticket_category.title()}-Ticket",
        description=(
            f"**User:** {message.author.mention} (`{message.author.id}`)\n"
            f"**Ticket ID:** `{channel.id}`\n"
            f"**Kategorie:** `{ticket_category}`\n\n"
            "**Erste Nachricht:**\n"
            f"`{message.content}`\n\n"
            "**Wichtige Hinweise:**\n"
            "• Bitte das Ticket mit dem Button unten beanspruchen\n"
            "• Bei Bedarf an passenden Teambereich weiterleiten\n"
            "• Ticket erst schließen, wenn das Problem gelöst ist"),
        color=0x2b2d31)

    team_embed.set_thumbnail(url=message.author.display_avatar.url)
    team_embed.add_field(name="Username", value=message.author.name, inline=True)
    team_embed.add_field(name="User ID", value=message.author.id, inline=True)
    team_embed.add_field(name="Account erstellt am",
                         value=message.author.created_at.strftime("%d.%m.%Y"),
                         inline=True)

    if isinstance(message.author, discord.Member):
        team_embed.add_field(name="Server beigetreten am",
                             value=message.author.joined_at.strftime("%d.%m.%Y"),
                             inline=True)
        team_embed.add_field(name="Höchste Rolle",
                             value=message.author.top_role.mention,
                             inline=True)

    team_embed.set_footer(text=f"Ticket erstellt",
                          icon_url=guild.icon.url if guild.icon else None)
    team_embed.timestamp = datetime.datetime.now()

    team_roles = [f"<@&{role_id}>" for role_id in category_data['role_ids']]
    team_ping = " ".join(team_roles)
    await channel.send(team_ping)
    await channel.send(embed=team_embed, view=TutorialView())

    return channel


def remove_emojis(string):
    emoji_pattern = re.compile("["
                               u"\U0001F451-\U0001F4BB"
                               u"\U0001F334"
                               u"\U0001F4DA"
                               u"\U0001F4DD"
                               "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', string)


#emoji = ("📝")
#unicode_codepoint = hex(ord(emoji))
#print(unicode_codepoint)


@slash_command(description="Zeige Ticket-Statistiken")
async def ticket_stats(
        self,
        ctx: discord.ApplicationContext,
        user: discord.User = None):
    async with aiosqlite.connect(self.db_path) as db:
        if user:
            cursor = await db.execute("""
                SELECT 
                    team_member_id,
                    tickets_handled,
                    tickets_closed,
                    COALESCE(avg_response_time, 0) AS avg_response_time,
                    total_response_time,
                    COALESCE(avg_rating, 0) AS avg_rating,
                    COALESCE(total_ratings, 0) AS total_ratings,
                    created_at
                FROM ticket_stats
                WHERE team_member_id = ?
            """, (user.id,))
            stats = await cursor.fetchone()

            if not stats:
                await ctx.respond(f"Keine Statistiken für {user.mention} verfügbar.")
                return

            embed = discord.Embed(
                title=f"📊 Ticket-Statistiken für {user.name}",
                color=user.color or discord.Color.blue(),
                timestamp=datetime.datetime.now())
            embed.set_thumbnail(url=user.display_avatar.url)

            # Include rating information in stats
            avg_rating = stats[5]
            total_ratings = stats[6]
            stars = "⭐" * round(avg_rating)

            embed.description = (
                f"📝 Bearbeitet: **{stats[1]}**\n"
                f"✅ Geschlossen: **{stats[2]}**\n"
                f"⏱️ Ø Reaktionszeit: **{stats[3]:.1f}** Min\n"
                f"⭐ Bewertung: **{avg_rating:.1f}** ({total_ratings} {'Bewertung' if total_ratings == 1 else 'Bewertungen'})\n"
                f"{stars}\n"
                f"⏰ Gesamtzeit: **{stats[4]:.1f}** Min")


@ticket_stats.error
async def ticket_stats_error(self, ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.respond("Du hast nicht die erforderlichen Rechte für diesen Befehl.", ephemeral=True)
    else:
        await ctx.respond(f"Ein Fehler ist aufgetreten: {str(error)}", ephemeral=True)
        print(f"Error in ticket_stats: {error}")


@slash_command(description="DB info command")
async def dbinfo(ctx):
    if admin(ctx.author):
        return

    """Show database structure"""
    try:
        cursor = await conn.execute("PRAGMA table_info(ticket_stats)")
        columns = await cursor.fetchall()
        column_info = "\n".join([f"Column: {col[1]}, Type: {col[2]}" for col in columns])
        await ctx.send(f"Ticket Stats Table Structure:\n{column_info}")
    except Exception as e:
        await ctx.send(f"Error getting database info: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Handle DM messages
    if isinstance(message.channel, discord.DMChannel):
        # Check if user is in ticket creation process
        cursor = await conn.execute("SELECT * FROM pending_tickets WHERE user_id = ?", (message.author.id,))
        pending_ticket = await cursor.fetchone()

        if pending_ticket:
            # Remove pending ticket status
            await conn.execute("DELETE FROM pending_tickets WHERE user_id = ?", (message.author.id,))
            await conn.commit()

            # Create the ticket
            await create_or_queue_ticket(message.author.id, message)
            return
        cursor = await conn.execute("SELECT channel_id FROM tickets WHERE user_id = ?", (message.author.id,))
        ticket = await cursor.fetchone()

        if not ticket:
            if message.content.lower() != "ticket":
                welcome_embed = discord.Embed(
                    title="👋 Willkommen im Support!",
                    description="Wie kann ich dir helfen? Wähle eine Option aus dem Menü unten.",
                    color=discord.Color.blue())
                await message.channel.send(embed=welcome_embed, view=DMMenu())
                return

        # Wenn der User bereits ein Ticket hat
        if ticket:
            channel_id = ticket[0]
            channel = await bot.fetch_channel(channel_id)

            # Nachricht an den Ticket-Channel senden
            embed = discord.Embed(description=f"{message.content}", color=discord.Color.green())
            embed.set_author(name=message.author, icon_url=message.author.avatar.url)
            if message.attachments:
                embed.set_image(url=message.attachments[0].url)
            await channel.send(embed=embed)

            await message.add_reaction("✅")

    # Nachrichten im Ticket-Channel
    elif message.channel.category_id == category_id and not isinstance(message.channel, discord.DMChannel):
        cursor = await conn.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (message.channel.id,))
        row = await cursor.fetchone()

        if row:
            user_id = row[0]
            user = bot.get_user(user_id)
            if user is None:
                user = await bot.fetch_user(user_id)

            member = message.guild.get_member(message.author.id)
            ignore_roles = ["Blau", "Rot", "pink", "Grün", "Lila", "Gelb", "⠀⠀⠀⠀⠀⠀⠀⠀⠀Team⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"]
            highest_role = next((role for role in sorted(member.roles, key=lambda role: role.position, reverse=True)
                                 if role.name not in ignore_roles), None)

            embedt = discord.Embed(description=f"{message.content}\n", color=discord.Color.dark_gold())
            embedt.set_author(name=f"{message.author} | {highest_role.name if highest_role else 'Unbekannt'}",
                              icon_url=message.author.avatar.url)
            if message.attachments:
                embedt.set_image(url=message.attachments[0].url)
            await user.send(embed=embedt)

        await message.add_reaction("✅")

    # Integration des gewünschten Codes
    elif isinstance(message.channel, discord.DMChannel):
        # Überprüfen, ob der Benutzer ein Ticket erstellt
        if message.content.lower() == "ticket":
            cursor = await conn.execute("SELECT channel_id FROM tickets WHERE user_id = ?", (message.author.id,))
            ticket = await cursor.fetchone()

            if not ticket:
                # Ticket erstellen
                guild = bot.get_guild(guild_id)  # Ersetze GUILD_ID mit deiner Server-ID
                category = discord.utils.get(guild.categories, id=category_id)  # Ersetze CATEGORY_ID
                channel = await category.create_text_channel(name=f"ticket-{message.author.name}")
                teamping = "<@&ROLE_ID>"  # Rolle ersetzen

                embed = discord.Embed(
                    title="WILLKOMMEN IM TICKET-SUPPORT!",
                    description="Ich habe deine Support-Anfrage erstellt und das Server-Team über dein Anliegen informiert.",
                    color=discord.Color.green()
                )
                team_embed = discord.Embed(
                    title="Neues Ticket!",
                    description=f"Neues Ticket von: {message.author.mention}.",
                    color=discord.Color.green()
                )

                # Nachricht an den User senden
                await message.channel.send(embed=embed)

                # Nachrichten im Ticket-Kanal senden
                await channel.send(teamping)
                await asyncio.sleep(0.5)  # Kurze Pause zwischen den Nachrichten
                await channel.send(embed=team_embed, view=TutorialView())

                # Datenbank aktualisieren
                await conn.execute("INSERT INTO tickets (user_id, channel_id) VALUES (?, ?)",
                                   (message.author.id, channel.id))
                await conn.commit()
                return
            else:
                await message.channel.send("Du hast bereits ein offenes Ticket!")
    await bot.process_commands(message)


class Ticketweiterleitung(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    options = [
        discord.SelectOption(
            label="Admin Weiterleitung",
            description="Leite das Ticket an einen Admin weiter",
            value="admin"
        ),
        discord.SelectOption(
            label="Developer Weiterleitung",
            description="Leite das Ticket an einen Developer weiter",
            value="developer"
        ),
        discord.SelectOption(
            label="Moderator Weiterleitung",
            description="Leite das Ticket an einen Moderator weiter",
            value="moderator"
        ),
        discord.SelectOption(
            label="management Weiterleitung",
            description="Leite das Ticket an das Management weiter",
            value="management"
        ),

    ]

    @discord.ui.select(
        min_values=1,
        max_values=1,
        placeholder="Was möchtest du tun?",
        options=options,
        custom_id="select",
    )
    async def select_callback(self, select, interaction):
        if select.values[0] == "admin":
            cursor = await conn.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            user_id_tuple = await cursor.fetchone()
            user_id = user_id_tuple[0]
            user = bot.get_user(user_id)
            admin = '<@&1234626364737585244>'  # hier teamping definieren !!!
            if user is None:
                user = await bot.fetch_user(user_id)
            embed = discord.Embed(
                title="Ticket wurde an Admin weitergeleitet!",
                description=f"Ich habe dein Ticket an einen Admin weitergeleitet. Bitte habe etwas Geduld.",
            )

            await user.send(embed=embed)
            await interaction.message.channel.send(admin)
            await interaction.response.send_message("Das Ticket wurde an einen Admin weitergeleitet!")


        if select.values[0] == "moderator":
            cursor = await conn.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            user_id_tuple = await cursor.fetchone()
            user_id = user_id_tuple[0]
            user = bot.get_user(user_id)
            moderator = '<@&1234626368160006265>'
            if user is None:
                user = await bot.fetch_user(user_id)
            embed = discord.Embed(
                title="Ticket wurde an Moderator weitergeleitet!",
                description=f"Ich habe dein Ticket an einen Moderator weitergeleitet. Bitte habe etwas Geduld.",
            )
            await user.send(embed=embed)
            await interaction.message.channel.send(moderator)
            await interaction.response.send_message("Das Ticket wurde an einen Moderator weitergeleitet!")

        if select.values[0] == "developer":
            cursor = await conn.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            user_id_tuple = await cursor.fetchone()
            user_id = user_id_tuple[0]
            user = bot.get_user(user_id)
            developer = '<@&1234626366079635557>'
            if user is None:
                user = await bot.fetch_user(user_id)
            embed = discord.Embed(
                title="Ticket wurde an Developer weitergeleitet!",
                description=f"Ich habe dein Ticket an einen Developer weitergeleitet. Bitte habe etwas Geduld.",
            )
            await user.send(embed=embed)
            await interaction.message.channel.send(developer)
            await interaction.response.send_message("Das Ticket wurde an einen Developer weitergeleitet!")

        if select.values[0] == "management":
            cursor = await conn.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            user_id_tuple = await cursor.fetchone()
            user_id = user_id_tuple[0]
            user = bot.get_user(user_id)
            management = '<@&1234626372249587794>'
            if user is None:
                user = await bot.fetch_user(user_id)
            embed = discord.Embed(
                title="Ticket wurde an das Management weitergeleitet!",
                description=f"Ich habe dein Ticket an das Management weitergeleitet. Bitte habe etwas Geduld.",
            )
            await user.send(embed=embed)
            await interaction.message.channel.send(management)
            await interaction.response.send_message("Das Ticket wurde an das Management weitergeleitet!")



class menu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    options = [
        discord.SelectOption(
            label="Ticket Regeln",
            description="Bitte lesen Sie die Ticket Regeln bevor Sie ein Ticket erstellen.",
            value="sonstiges")]

    @discord.ui.select(
        min_values=1,
        max_values=1,
        placeholder="Schau dir Nützliche Informationen an!",
        options=options,
        custom_id="select",)
    async def select_callback(self, select, interaction):
        auswahl = select.values[0]

        if auswahl == "sonstiges":
            embed = discord.Embed(
                title="Ticket Regeln",
                description="1. Bitte benutze das Ticket System nur für wichtige Anliegen.\n"
                            "2. Bitte sei respektvoll gegenüber dem Team und anderen Usern.\n"
                            "3. Bitte warte geduldig auf eine Antwort.\n"
                            "4. Bitte schreibe dein Anliegen möglichst genau.\n"
                            "5. Bitte beachte, dass das Team auch mal offline sein kann.\n"
                            "6. Bitte beachte, dass das Team auch mal offline sein kann.\n"
                            "7. Bitte beachte, dass das Team auch mal offline sein kann.\n",
                color=discord.Color.blue())
            await interaction.user.send(embed=embed)


class Ticketmenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    options = [
        discord.SelectOption(
            label="Ticket Schließen",
            description="Schließe das Ticket (Nur für Admins)",
            value="close"
        ),
        discord.SelectOption(
            label="Schließungsanfrage",
            description="Frage den User, ob das Ticket geschlossen werden kann",
            value="close_request"
        ),
        discord.SelectOption(
            label="Claim",
            description="Beanspruche das Ticket",
            value="claim"
        ),
        discord.SelectOption(
            label="User Blockieren",
            description="Blockiere den User",
            value="block"
        ),
    ]

    @discord.ui.select(
        min_values=1,
        max_values=1,
        placeholder="Was möchtest du tun?",
        options=options,
        custom_id="select",)
    async def select_callback(self, select, interaction):
        if select.values[0] == "block":
            cursor = await conn.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            user_id_tuple = await cursor.fetchone()
            user_id = user_id_tuple[0]
            user = bot.get_user(user_id)
            if user is None:
                user = await bot.fetch_user(user_id)
            await blacklist_db.add_blacklist(user_id)
            embed = discord.Embed(
                title="Du wurdest ausgeschlossen!",
                description=f"Du wurdest vom Support ausgeschlossen!",)
            await user.send(embed=embed)
            await interaction.response.send_message("Der User wurde blockiert!")
            await conn.execute("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            await conn.commit()
            await asyncio.sleep(5)
            await interaction.message.channel.delete()


        elif select.values[0] == "close":
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Nur Admins können Tickets direkt schließen!", ephemeral=True)
                return

            cursor = await conn.execute("SELECT user_id, claimed_by, claimed_at FROM tickets WHERE channel_id = ?",
                                        (interaction.channel.id,))

            ticket_data = await cursor.fetchone()

            if ticket_data is None:
                await interaction.response.send_message("Kein passendes Ticket gefunden.")
                return

            user_id, claimed_by, claimed_at = ticket_data

            # Update statistics if the ticket was claimed
            if claimed_by:
                await update_ticket_stats(claimed_by, "close")
                if claimed_at:
                    # Calculate response time in minutes
                    response_time = (datetime.datetime.now() - datetime.datetime.fromisoformat(
                        claimed_at)).total_seconds() / 60
                    await update_ticket_stats(claimed_by, None, response_time)

            guild = bot.get_guild(guild_id)
            category = guild.get_channel(category_id)
            log_channel = guild.get_channel(log_channel_id)

            # Export chat history before closing
            transcript = await chat_exporter.export(
                interaction.channel,
                limit=None,
                tz_info="Europe/Berlin",
                guild=guild,
                bot=bot
            )

            if transcript is not None:
                transcript_file = discord.File(
                    io.BytesIO(transcript.encode()),
                    filename=f"transcript-{interaction.channel.name}.html"
                )

                log_embed = discord.Embed(
                    title="Ticket geschlossen",
                    description=f"**Ticket:** {interaction.channel.name}\n"
                                f"**Geschlossen von:** {interaction.user.mention}\n"
                                f"**User:** <@{user_id}>\n"
                                f"**Ticket ID:** {interaction.channel.id}",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now()
                )

                log_embed.set_footer(text=f"Ticket-Log • {guild.name}")
                await log_channel.send(embed=log_embed, file=transcript_file)

            await conn.execute("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            await conn.commit()

            user = bot.get_user(user_id)
            if user is None:
                user = await bot.fetch_user(user_id)

            await interaction.response.send_message("Ticket wird geschlossen!")

            # Create closure embed and feedback request in the same message
            close_embed = discord.Embed(
                title="Ticket geschlossen!",
                description=f"Das Ticket wurde von {interaction.user.mention} geschlossen.",
                color=discord.Color.red()
            )

            close_embed.set_author(name=f"{interaction.user}", icon_url=interaction.user.avatar.url)

            feedback_embed = discord.Embed(
                title="📝 Feedback",
                description="Wie zufrieden warst du mit der Bearbeitung deines Tickets?\nBitte bewerte mit 1-5 Sternen:",
                color=discord.Color.blue()
            )

            # Send both embeds with feedback buttons
            await user.send(embeds=[close_embed, feedback_embed],
                            view=FeedbackView(str(interaction.channel.id), claimed_by))

            await interaction.message.channel.delete()

            # Handle queued tickets
            cursor = await conn.execute("SELECT user_id FROM ticket_queue ORDER BY created_at LIMIT 1")
            queued_ticket = await cursor.fetchone()

            if queued_ticket:
                queued_user_id = queued_ticket[0]
                await conn.execute("DELETE FROM ticket_queue WHERE user_id = ?", (queued_user_id,))
                await conn.commit()

                channel = await category.create_text_channel(f"ticket-{user.name}")
                await conn.execute("INSERT INTO tickets (user_id, channel_id) VALUES (?, ?)",
                                   (queued_user_id, channel.id))
                await conn.commit()

                teamping = '<@&1234626371050012684>'
                await channel.send(teamping)
                await channel.send(f"Neues Ticket für User {user.mention} aus der Warteschlange.")

        elif select.values[0] == "claim":
            cursor = await conn.execute("SELECT user_id, claimed_by FROM tickets WHERE channel_id = ?",
                                        (interaction.channel.id,))
            ticket_data = await cursor.fetchone()

            if not ticket_data:
                await interaction.response.send_message("Ticket nicht gefunden!", ephemeral=True)
                return

            user_id, claimed_by = ticket_data

            if claimed_by:
                await interaction.response.send_message("Dieses Ticket wurde bereits beansprucht!", ephemeral=True)
                return

            # Update ticket claim status
            await conn.execute(
                "UPDATE tickets SET claimed_by = ?, claimed_at = ? WHERE channel_id = ?",
                (interaction.user.id, datetime.datetime.now(), interaction.channel.id)
            )
            await conn.commit()

            # Update statistics
            await update_ticket_stats(interaction.user.id, "handle")

            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
            embed = discord.Embed(
                title="Ticket wurde beansprucht!",
                description=f"Guten Tag! Mein Name ist {interaction.user.mention} und ich bin hier, um dir bei deinem Anliegen zu helfen. Ich habe dein Ticket übernommen und werde mein Bestes tun, um dir so schnell wie möglich weiterzuhelfen.\n\n"
                            f"Wie kann ich dir heute behilflich sein? Bitte gib mir so viele Details wie möglich, damit ich dein Problem effizient lösen kann."
            )
            await user.send(embed=embed)
            await interaction.response.send_message("Das Ticket wurde beansprucht!")


        elif select.values[0] == "close_request":

            cursor = await conn.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))

            user_id_tuple = await cursor.fetchone()

            if not user_id_tuple:
                await interaction.response.send_message("Ticket nicht gefunden!", ephemeral=True)
                return

            user_id = user_id_tuple[0]

            user = bot.get_user(user_id)

            if user is None:
                user = await bot.fetch_user(user_id)

            class CloseRequestButtons(discord.ui.View):

                def __init__(self, channel_id, user):
                    super().__init__(timeout=None)
                    self.channel_id = channel_id
                    self.user = user

                @discord.ui.button(label="Ja, schließen", style=discord.ButtonStyle.green, custom_id="accept_close")
                async def accept_callback(self, button, interaction):
                    try:
                        # Deaktiviere alle Buttons
                        for item in self.children:
                            item.disabled = True

                        # Aktualisiere die Message mit deaktivierten Buttons
                        await interaction.message.edit(view=self)
                        await interaction.response.send_message("Ticket wird geschlossen...", ephemeral=True)

                        guild = bot.get_guild(guild_id)
                        channel = guild.get_channel(self.channel_id)

                        if channel:
                            # Get ticket data for statistics before deleting
                            cursor = await conn.execute(
                                "SELECT claimed_by, claimed_at FROM tickets WHERE channel_id = ?",
                                (self.channel_id,))

                            ticket_data = await cursor.fetchone()

                            if ticket_data:
                                claimed_by, claimed_at = ticket_data

                                if claimed_by:
                                    await update_ticket_stats(claimed_by, "close")

                                    if claimed_at:
                                        response_time = (datetime.datetime.now() - datetime.datetime.fromisoformat(
                                            claimed_at)).total_seconds() / 60
                                        await update_ticket_stats(claimed_by, None, response_time)

                            await conn.execute("DELETE FROM tickets WHERE channel_id = ?", (self.channel_id,))
                            await conn.commit()

                            close_embed = discord.Embed(
                                title="Ticket wird geschlossen",
                                description="Der User hat der Schließung zugestimmt.",
                                color=discord.Color.green()
                            )

                            feedback_embed = discord.Embed(
                                title="📝 Feedback",
                                description="Wie zufrieden warst du mit der Bearbeitung deines Tickets?\nBitte bewerte mit 1-5 Sternen:",
                                color=discord.Color.blue()
                            )

                            # Send both embeds with feedback buttons
                            await self.user.send(embeds=[close_embed, feedback_embed],
                                                view=FeedbackView(str(self.channel_id), claimed_by))
                            await channel.send("Ticket wird in 5 Sekunden geschlossen.")
                            await asyncio.sleep(5)
                            await channel.delete()

                            # Handle queued tickets
                            await self.handle_queued_tickets(guild)

                    except Exception as e:
                        print(f"Error in accept_callback: {e}")
                        await interaction.followup.send("Ein Fehler ist aufgetreten.", ephemeral=True)

                @discord.ui.button(label="Nein, offen lassen", style=discord.ButtonStyle.red, custom_id="reject_close")
                async def reject_callback(self, button, interaction):
                    try:
                        # Deaktiviere alle Buttons
                        for item in self.children:
                            item.disabled = True

                        # Aktualisiere die Message mit deaktivierten Buttons
                        await interaction.message.edit(view=self)

                        guild = bot.get_guild(guild_id)
                        channel = guild.get_channel(self.channel_id)

                        if channel:
                            reject_embed = discord.Embed(
                                title="Schließung abgelehnt",
                                description="Der User möchte das Ticket noch offen lassen.",
                                color=discord.Color.red()
                            )

                            await channel.send(embed=reject_embed)
                            await interaction.response.send_message("Danke für deine Rückmeldung!", ephemeral=True)

                    except Exception as e:
                        print(f"Error in reject_callback: {e}")
                        await interaction.followup.send("Ein Fehler ist aufgetreten.", ephemeral=True)

                async def handle_queued_tickets(self, guild):
                    try:
                        cursor = await conn.execute("SELECT user_id FROM ticket_queue ORDER BY created_at LIMIT 1")
                        queued_ticket = await cursor.fetchone()

                        if queued_ticket:
                            queued_user_id = queued_ticket[0]
                            await conn.execute("DELETE FROM ticket_queue WHERE user_id = ?", (queued_user_id,))
                            await conn.commit()

                            category = guild.get_channel(category_id)
                            queued_user = await bot.fetch_user(queued_user_id)
                            new_channel = await category.create_text_channel(f"ticket-{queued_user.name}")

                            await conn.execute("INSERT INTO tickets (user_id, channel_id) VALUES (?, ?)",
                                               (queued_user_id, new_channel.id))
                            await conn.commit()

                            teamping = '<@&1234626371050012684>'
                            await new_channel.send(teamping)
                            await new_channel.send(
                                f"Neues Ticket für User {queued_user.mention} aus der Warteschlange.")

                    except Exception as e:
                        print(f"Error handling queued tickets: {e}")

            try:
                user_embed = discord.Embed(
                    title="Schließungsanfrage",
                    description=f"{interaction.user.mention} möchte das Ticket schließen.\nBist du damit einverstanden?",
                    color=discord.Color.yellow()
                )

                await user.send(embed=user_embed, view=CloseRequestButtons(interaction.channel.id, user))
                await interaction.response.send_message("Schließungsanfrage wurde an den User gesendet.",
                                                        ephemeral=True)

            except Exception as e:
                print(f"Error in close_request: {e}")
                await interaction.response.send_message("Ein Fehler ist aufgetreten.", ephemeral=True)
class DMMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    options = [
        discord.SelectOption(
            label="Ticket erstellen",
            description="Erstelle ein Support-Ticket",
            emoji="🎫",
            value="create_ticket"
        ),
        discord.SelectOption(
            label="FAQ",
            description="Häufig gestellte Fragen",
            emoji="❓",
            value="faq"
        ),
        discord.SelectOption(
            label="Server Regeln",
            description="Zeige die Server-Regeln",
            emoji="📜",
            value="rules"
        ),
        discord.SelectOption(
            label="Hilfe & Support",
            description="Allgemeine Informationen zum Support",
            emoji="ℹ️",
            value="help"
        )
    ]

    @discord.ui.select(
        min_values=1,
        max_values=1,
        placeholder="Wähle eine Option",
        options=options,
        custom_id="dm_menu"
    )
    async def select_callback(self, select, interaction):
        if select.values[0] == "create_ticket":
            if await has_ticket(interaction.user.id):
                await interaction.response.send_message("Du hast bereits ein offenes Ticket!", ephemeral=True)
                return

            if await blacklist_db.get_blacklist(interaction.user.id) is not None:
                await interaction.response.send_message("Du bist blockiert und kannst kein Ticket erstellen.",
                                                        ephemeral=True)
                return

            # Set a flag in the database to indicate this user is in the ticket creation process
            await conn.execute("""CREATE TABLE IF NOT EXISTS pending_tickets 
                                    (user_id INTEGER PRIMARY KEY, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
            await conn.execute("INSERT OR REPLACE INTO pending_tickets (user_id) VALUES (?)", (interaction.user.id,))
            await conn.commit()

            embed = discord.Embed(
                title="📝 Ticket erstellen",
                description="Bitte beschreibe dein Anliegen in der nächsten Nachricht ausführlich.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif select.values[0] == "faq":
            embed = discord.Embed(
                title="❓ Häufig gestellte Fragen",
                description=(
                    "**Wie erstelle ich ein Ticket?**\n"
                    "→ Wähle 'Ticket erstellen' aus dem Menü\n\n"
                    "**Wie lange dauert eine Antwort?**\n"
                    "→ Wir versuchen innerhalb von 24 Stunden zu antworten\n\n"
                    "**Was tun bei dringenden Anliegen?**\n"
                    "→ Bitte erwähne dies in deinem Ticket\n\n"
                    "**Kann ich mehrere Tickets erstellen?**\n"
                    "→ Nein, bitte warte bis dein aktuelles Ticket geschlossen ist"
                ),
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif select.values[0] == "rules":
            embed = discord.Embed(
                title="📜 Support-Regeln",
                description=(
                    "1. Sei respektvoll im Umgang mit dem Support-Team\n"
                    "2. Beschreibe dein Anliegen klar und deutlich\n"
                    "3. Hab Geduld - wir antworten so schnell wie möglich\n"
                    "4. Ein Ticket pro Person/Problem\n"
                    "5. Missbrauch führt zum Ausschluss vom Support"
                ),
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif select.values[0] == "help":
            embed = discord.Embed(
                title="ℹ️ Hilfe & Support",
                description=(
                    "**Support-Zeiten:**\n"
                    "Mo-Fr: 10:00 - 22:00 Uhr\n"
                    "Sa-So: 12:00 - 20:00 Uhr\n\n"
                    "**Wichtige Hinweise:**\n"
                    "• Beschreibe dein Problem ausführlich\n"
                    "• Füge Screenshots hinzu wenn möglich\n"
                    "• Bleib freundlich und geduldig\n\n"
                    "Bei Fragen kannst du jederzeit ein Ticket erstellen!"
                ),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class TutorialView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Weiterleitung", style=discord.ButtonStyle.success, emoji="<:9829namodicon:1236228675574431744>", custom_id="keks", row=2)
    async def button_callback1(self, button, interaction):
        embed = discord.Embed(
            title="Weiterleitung",
            description="Bitte wähle aus an wen du das Ticket weiterleiten möchtest!\n"
                        "Sollte kein passender Teamler online sein, schreibe bitte in das Ticket das keiner da ist!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=Ticketweiterleitung(), ephemeral=True)


    @discord.ui.button(label="Ticket Menü", emoji="<:menu:1297338007904325724>", style=discord.ButtonStyle.success, custom_id="pizza", row=1)
    async def button_callback2(self, button, interaction):
        button.disabled = False
        embed = discord.Embed(
            title="Ticket Menü",
            description="Bitte wähle aus was du tun möchtest!\n"
                        "Ticket erst schließen wenn das Problem gelöst wurde!\n\n"
                        "Ticket beanspruchen wenn du das Ticket bearbeiten möchtest!\n"
                        "Sollte das Ticket bereits beansprucht sein, schreibt nur der zugeteilte Supporter in das Ticket!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=Ticketmenu(), ephemeral=True)



class bewertung(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bewertungen", style=discord.ButtonStyle.success, custom_id="keks", row=2)
    async def button_callback1(self, button, interaction):
        embed = discord.Embed(
            title="Bewertungen",
            description="Hier findest du die Bewertungen zu dem supporter\n"
                        "Sollte kein passender Teamler online sein, schreibe bitte in das Ticket das keiner da ist!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=Ticketweiterleitung(), ephemeral=True)


class FeedbackModal(discord.ui.Modal):
    def __init__(self, ticket_id: str, team_member_id: int, rating: int, original_view=None) -> None:
        super().__init__(title="Feedback")
        self.ticket_id = ticket_id
        self.team_member_id = team_member_id
        self.rating = rating
        self.original_view = original_view  # Corrected spelling

        self.feedback = discord.ui.InputText(
            label="Zusätzliches Feedback (optional)",
            placeholder="Beschreibe deine Erfahrung...",
            required=False,
            max_length=1000,
            style=discord.InputTextStyle.long
        )
        self.add_item(self.feedback)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Save the feedback to database
        await self.save_feedback(
            user_id=interaction.user.id,
            rating=self.rating,
            feedback_text=self.feedback.value
        )

        # Create thank you embed
        thank_you_embed = discord.Embed(
            title="Danke für dein Feedback!",
            description=f"Du hast {self.rating} {'Stern' if self.rating == 1 else 'Sterne'} gegeben.",
            color=discord.Color.green()
        )
        if self.feedback.value:
            thank_you_embed.add_field(
                name="Dein Feedback",
                value=self.feedback.value[:1024],  # Discord embed field limit
                inline=False
            )

        await interaction.followup.send(embed=thank_you_embed, ephemeral=True)

        # Update the original message
        original_message = interaction.message
        if self.original_view:
            for child in self.original_view.children:
                child.disabled = True
            await interaction.message.edit(view=self.original_view)

    async def save_feedback(self, user_id: int, rating: int, feedback_text: str = None):
        async with aiosqlite.connect("tickets.db") as db:
            await db.execute("""
                INSERT INTO ticket_feedback 
                (ticket_id, user_id, team_member_id, rating, feedback_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                self.ticket_id,
                user_id,
                self.team_member_id,
                rating,
                feedback_text,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            await db.commit()


class FeedbackView(discord.ui.View):
    def __init__(self, ticket_id: str, team_member_id: int):
        super().__init__(timeout=600)  # 10 minute timeout
        self.ticket_id = ticket_id
        self.team_member_id = team_member_id

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.secondary, custom_id="rating_1")
    async def rating_1(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.handle_rating(interaction, 1)

    @discord.ui.button(label="⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rating_2")
    async def rating_2(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.handle_rating(interaction, 2)

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rating_3")
    async def rating_3(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.handle_rating(interaction, 3)

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rating_4")
    async def rating_4(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.handle_rating(interaction, 4)

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rating_5")
    async def rating_5(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.handle_rating(interaction, 5)

    async def handle_rating(self, interaction: discord.Interaction, rating: int):
        modal = FeedbackModal(self.ticket_id, self.team_member_id, rating)
        await interaction.response.send_modal(modal)

    async def update_team_member_stats(self, rating: int):
        async with aiosqlite.connect("tickets.db") as db:
            # Get current stats
            cursor = await db.execute("""
                SELECT avg_rating, total_ratings 
                FROM ticket_stats 
                WHERE team_member_id = ?
            """, (self.team_member_id,))
            stats = await cursor.fetchone()

            if stats is None:
                current_avg = 0
                total_ratings = 0
            else:
                current_avg = stats[0] or 0
                total_ratings = stats[1] or 0

            # Calculate new average
            new_total = total_ratings + 1
            new_avg = ((current_avg * total_ratings) + rating) / new_total

            # Update stats
            await db.execute("""
                UPDATE ticket_stats 
                SET avg_rating = ?, total_ratings = ?
                WHERE team_member_id = ?
            """, (round(new_avg, 2), new_total, self.team_member_id))
            await db.commit()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return


bot.loop.run_until_complete(setup_database())
bot.run(TOKEN)
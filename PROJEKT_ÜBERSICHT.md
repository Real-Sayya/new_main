# Discord Bot - Projekt Übersicht (GSv2.0)

**Letzte Aktualisierung:** 06.10.2025

## 📋 Projekt-Beschreibung

Discord-Bot für ein umfangreiches Server-Management-System mit Ticket-Support, Terminal-Emulation und Moderations-Features.

## 🏗️ Projektstruktur

```
new_main/
├── main.py                 # Haupt-Bot & Ticket-System
├── Data/                   # Datenbanken & Konfiguration
│   ├── tickets.db         # Ticket-Datenbank
│   ├── terminal_*.db      # Terminal-System Datenbanken
│   ├── apt.db             # APT-Paketmanager DB
│   ├── moderation.db      # Moderations-Datenbank
│   ├── personalities.json # AI/Bot-Persönlichkeiten
│   ├── terminal_config.json
│   └── help_content.json
├── System/                 # Bot-Module (Cogs)
│   ├── terminal_core.py   # Terminal-Hauptsystem
│   ├── moderation.py      # Moderations-System
│   ├── apt.py             # Paket-Manager
│   ├── roles.py           # Rollen-Verwaltung
│   └── terminal/          # Terminal-Komponenten
│       ├── user_manager.py
│       ├── filesystem.py
│       ├── permissions.py
│       ├── channel_manager.py
│       ├── mod_manager.py
│       ├── role_manager.py
│       └── ...
└── Team/
    └── blacklist.py       # User-Blacklist
```

## 🎯 Hauptfunktionen

### 1. Ticket-System (main.py)
- **Automatische Kategorisierung**: Tickets werden basierend auf Keywords automatisch kategorisiert
  - Kategorien: Allgemein, Technisch, Moderation, Partner
- **Warteschlangen-System**: Max. 5 gleichzeitige Tickets, weitere in Warteschlange
- **DM-Integration**: User können über DMs mit Support kommunizieren
- **Statistiken**: Tracking von Response-Zeit, Bewertungen, gelösten Tickets
- **Feedback-System**: 5-Sterne-Bewertung mit optionalem Text-Feedback
- **Chat-Export**: Automatisches Transcript beim Schließen (HTML)
- **Claim-System**: Supporter können Tickets beanspruchen
- **Weiterleitung**: An Admin, Developer, Moderator oder Management

### 2. Terminal-System (System/terminal_core.py)
Vollständige Linux-ähnliche Terminal-Emulation in Discord:

**User-Management:**
- Register/Login-System mit Passwörtern (Modal-basiert)
- Root/Sudo-Zugriff mit separaten Passwörtern
- User-Rollen und Berechtigungen

**Filesystem:**
- Virtuelles Dateisystem (ls, cd, pwd, mkdir, touch, cat, rm, etc.)
- Permissions (chmod)
- Datei-Operationen (mv, cp, find, grep)

**Sicherheit:**
- Channel-Trust-System (nur in trusted channels)
- Sudo/Root-Authentifizierung
- Permission-Management
- Logging aller Aktivitäten

### 3. Moderations-System (System/moderation.py)
- **Warn-System**: Automatische Aktionen bei 3, 5, 10 Warnungen
- **Moderation-Commands**: warn, kick, ban, unban, timeout, untimeout
- **ModLog**: Vollständige Historie aller Moderations-Aktionen
- **Case-System**: Jede Aktion bekommt eine Case-ID

### 4. APT Paket-Manager (System/apt.py)
- Paket-Installation und Verwaltung
- User-basierte Paket-Tracking
- Statistiken über Paket-Nutzung

### 5. Rollen-System (System/roles.py)
- Dynamische Rollen-Verwaltung
- Temporäre Rollen
- Rollen-Anfragen

## 🗄️ Datenbank-Schema

### Tickets (Data/tickets.db)
- `tickets`: channel_id, user_id, blocked, priority, claimed_by, claimed_at, category
- `ticket_stats`: Supporter-Statistiken (handled, closed, avg_response_time, ratings)
- `ticket_feedback`: User-Bewertungen
- `ticket_queue`: Warteschlange
- `pending_tickets`: Ticket-Erstellung in Arbeit

### Terminal (Data/terminal_*.db)
- `terminal_users.db`: User-Accounts, Passwörter, Berechtigungen
- `terminal_fs.db`: Virtuelles Dateisystem
- `terminal_channels.db`: Trusted Channels

### Moderation (Data/moderation.db)
- Moderations-Cases
- Warnungen
- Mod-Logs

## 🔑 Wichtige IDs

```python
guild_id = 1356278624411713676
category_id = 1378366027586600960  # Ticket-Kategorie
log_channel_id = 1378360358602801182

# Team-Rollen
Admin: 1331409215096488016
Developer: 1234626366079635557
Moderator: 1234626368160006265
Management: 1234626372249587794
```

## 🔧 Technologie-Stack

- **Discord.py / py-cord**: Discord-Bot Framework
- **aiosqlite**: Async SQLite-Datenbank
- **chat_exporter**: Ticket-Transcript-Export
- **pyfiglet**: ASCII-Art

## 📝 Wichtige Hinweise

1. **Token-Sicherheit**: Bot-Token liegt im Code (Zeile 17) - sollte in .env ausgelagert werden!
2. **Moderation**: Automatische Eskalation bei mehreren Warnungen
3. **Ticket-Kategorisierung**: Keyword-basiert, kann erweitert werden
4. **Terminal**: Channel muss erst mit `root channel trust` freigegeben werden
5. **Feedback**: Wird automatisch nach Ticket-Schließung angefordert

## 🚀 Bot starten

```bash
python main.py
```

Der Bot lädt automatisch alle Cogs aus `System/` und `Team/`.

## 🔐 Sicherheitsfeatures

- Blacklist-System für problematische User
- Channel-Trust-System für Terminal
- Passwort-geschützter Root/Sudo-Zugang
- Permission-basierte Befehlsausführung
- Vollständiges Logging aller Aktionen

## 📊 Statistiken & Tracking

- Ticket-Response-Zeiten
- Supporter-Bewertungen
- Moderations-Historie
- Paket-Installations-Statistiken
- User-Aktivitäten im Terminal

---

**Für zukünftige Entwicklungen:**
- Bot-Token auslagern
- Weitere Ticket-Kategorien hinzufügen
- Terminal-Commands erweitern
- Automatische Backups implementieren

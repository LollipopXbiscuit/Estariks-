# Overview

This is a Telegram character catcher bot called "Estariks Bot" that operates as a gamified character collection system. The bot sends anime character images to Telegram groups after every 100 messages, and users can guess the character names to add them to their personal collections. The system includes trading, gifting, favorites, and leaderboard features to create an engaging community-driven game.

# Recent Changes

## January 29, 2026
- **Complete Rebranding**: Rebranded "Waifu & Husbando Catcher" to "Estariks Bot".
- **Rarity Overhaul**: Replaced the entire rarity system with new tiers:
  - 🪄 Catapult (Ultra Rare - Star equivalent)
  - 🗡 Knight (Event/Rare - Zenith equivalent)
  - ⚡️ Ninja
  - 🔮 Flat (Retro equivalent)
  - 🟡 Legendary
  - 🟠 Rare
  - ⚪️ Common
- **UI Refresh**: Updated `/start` command with a new animated GIF background and custom welcome message.
- **Spawning System**: Updated weights and interval logic to match the new rarity tiers.

## December 9, 2025
- **Christmas Event System**: Added comprehensive event system for seasonal character spawning
  - `/startevent` - Sudo-only command to start Christmas event where only 🎄 characters spawn
  - `/endevent` - Sudo-only command to end the event and return to normal spawns
  - `/eventstatus` - Public command to check if an event is active
  - All spawn paths (regular, Star, and /summon) respect the event filter
  - Event state persisted in MongoDB across bot restarts
  - Safety check prevents starting event when no matching characters exist
- **Database**: Added `event_settings_collection` for event state persistence
- **/update Command Fix**: Fixed critical bug where updating a character's image didn't sync to user collections
  - Now properly updates img_url in all user collections when a character is updated
  - Shows confirmation with count of updated user collections
- **Harem Display Fix**: Fixed issue where harem showed text-only output when favorite character is missing
  - Now falls back to displaying a random character from user's collection

## December 2, 2025
- **Inline Query Search Fix**: Fixed bug where searching characters with special characters (like `(`, `)`, `[`, `]`, `*`, etc.) would crash the inline query
  - Added proper regex escaping using `re.escape()` for user search input
  - Search queries now work correctly with any characters the user types
  - Applied fix to both general character search and collection search filters
- **Inline Query Variable Fix**: Fixed potential unbound variable error in inline query handler
  - Moved `user` and `all_characters` initialization to beginning of function
  - Prevents errors when processing non-collection queries
- **Harem Navigation Fix**: Fixed bug where sudo users couldn't navigate through other users' harem pages
  - Sudo users viewing another user's harem can now use the navigation buttons
  - Non-sudo users still cannot access others' harems (security preserved)

## November 29, 2025
- **Spawn System Overhaul**: Fixed weighted random selection to properly respect rarity spawn rates
  - Previously: System used `random.choice` which gave equal chance to all characters regardless of rarity
  - Now: Uses `random.choices` with proper weights to select rarity FIRST, then picks a random character from that rarity
  - This fixes the bug where Mythic characters spawned as often as Common ones
- **Retro Added to Regular Spawns**: Removed separate 2000-message Retro system, now spawns in regular weighted system
- **Zenith & Limited Edition EXTREMELY Rare**: Made these ultra-rare tiers nearly impossible to get
  - Zenith: ~0.04% spawn chance (weight: 0.1)
  - Limited Edition: ~0.02% spawn chance (weight: 0.05)
- **New Spawn Weights** (approximate percentages):
  - Common: ~36% | Uncommon: ~29% | Rare: ~18% | Epic: ~11%
  - Legendary: ~3.6% | Mythic: ~1.8% | Retro: ~0.7%
  - Zenith: ~0.04% | Limited Edition: ~0.02%
  - Star: Main GC only every 200 messages (special system)
- **Star Rarity in /upload**: Added Star rarity (number 8) to upload command, shifted Zenith to 9 and Limited Edition to 10

## November 21, 2025
- **Star Rarity System**: Added new Star (⭐) rarity tier positioned above Zenith in the rarity hierarchy
  - Star characters only spawn in the main group chat (ID: -1002961536913) every 200 messages
  - Added Star to all rarity emoji mappings and ordering lists throughout the codebase
  - Star characters are excluded from regular spawn pools and appear only in the designated chat
  - Updated `/rarity` command to display Star spawn information
- **Retro Spawn Interval Update**: Changed Retro character spawn frequency from every 4000 messages to every 2000 messages
  - Updated all documentation and help text to reflect new 2000-message interval
  - Retro spawn logic in message_counter now triggers at 2000-message intervals
- **/all Command**: Added new `/all` command to display collection progress across all rarities
  - Shows owned vs total characters for each rarity tier
  - Displays visual progress bars (10 blocks: ▰ filled, ▱ empty) with percentage completion
  - Rarity order: Limited Edition, Star, Zenith, Retro, Mythic, Legendary, Epic, Rare, Uncommon, Common
  - Format example: "🏵 Mythic: 57/249 ▰▰▱▱▱▱▱▱▱▱ 23%"

## September 30, 2025
- **Video Detection Fix for URLs Without Extensions**: Fixed video detection to work with URLs that don't have file extensions (like cloudflare /dl/ links)
  - Changed all video detection checks from `is_video_url()` to `is_video_character()` across harem.py, inlinequery.py, and upload.py
  - Now correctly detects videos using both URL extensions AND the 🎬 emoji marker in character names
  - Fixes issue where videos served from cloudflare and other services without file extensions in URLs weren't being recognized as videos
  - Affected commands: `/harem`, `/fav`, `/find`, and inline queries
- **Non-Discord MP4 Fallback Handling**: Fixed issue where non-Discord MP4 links weren't displaying in commands and inline queries
  - Added comprehensive video-to-photo fallback system across all display paths
  - When video format fails (especially in Telegram inline queries), gracefully falls back to displaying as photo with 🎬 indicator
  - Implemented fallback handling in `/find`, `/fav`, harem display (both message and callback paths), and inline queries
  - Added detailed error logging to track URL failures and diagnose issues with video display
  - All video fallbacks now consistently mark with 🎬 [Video] indicator so users know it's a video character
- **Video Upload Support**: Added MP4 and other video format support to `/upload` command. Videos are now validated and sent using `send_video` API
- **Video Display Support**: Fixed all display commands to properly play videos instead of showing them as broken images
  - `/find` command now displays videos correctly
  - `/fav` command plays videos when favoriting video characters
  - Harem preview shows videos for favorite and random characters
  - Inline queries support video results with proper MIME types (MP4, WEBM, MOV, AVI, MKV, FLV)
- **Character Name Filtering**: Fixed `/sorts character` command to support partial name matching. Now "Ashley" will match "Ashley Graves ⛩️" and other character names with emojis
- **Locked Spawns Display**: Fixed `lockedspawns` command to include Retro rarity characters in the display
- **Pagination Enhancement**: Added next/previous navigation buttons to `lockedspawns` command for better navigation through locked characters (20 per page)

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Core Bot Framework
- **Telegram Bot API**: Uses python-telegram-bot v20.6 for main bot functionality and command handling
- **Pyrogram**: Secondary Telegram client library for additional features like admin controls and message handling
- **Dual Client Pattern**: Implements both python-telegram-bot (application) and Pyrogram (shivuu) clients for different use cases

## Database Design
- **MongoDB with Motor**: Async MongoDB driver for all data persistence
- **Collections Structure**:
  - `anime_characters_lol`: Stores character data (id, name, anime, rarity, image URL)
  - `user_collection_lmaoooo`: User's collected characters
  - `user_totals_lmaoooo`: User statistics and totals
  - `group_user_totalsssssss`: Group-specific user statistics
  - `top_global_groups`: Global group leaderboards
  - `total_pm_users`: Private message users tracking
  - `event_settings`: Stores active event state (type, active flag, start time)

## Message Processing Architecture
- **Message Counter System**: Tracks messages per group with customizable frequency (default 100 messages)
- **Async Locks**: Prevents race conditions using asyncio locks per chat
- **Character Spawning**: Automatic character deployment based on message thresholds
- **Spam Prevention**: Built-in rate limiting and spam counters

## Command System
- **Modular Design**: Commands organized in separate modules for maintainability
- **Admin Controls**: Role-based permissions using Pyrogram's chat member status
- **User Commands**: `/guess`, `/fav`, `/trade`, `/gift`, `/collection`, `/topgroups`, `/all`
- **Admin Commands**: `/upload`, `/changetime`, `/broadcast`, `/startevent`, `/endevent`
- **Event Commands**: `/eventstatus` (public)

## Caching Strategy
- **TTL Cache**: Uses cachetools for temporary data storage
- **User Collection Cache**: 60-second TTL for frequently accessed user data
- **Character Cache**: 10-hour TTL for character data
- **Database Indexing**: Strategic indexes on frequently queried fields

## Rarity System
- **Tiered Rarity**: 10-tier system with weighted spawn rates
  - Common ⚪️ (~36%), Uncommon 🟢 (~29%), Rare 🔵 (~18%), Epic 🟣 (~11%)
  - Legendary 🟡 (~3.6%), Mythic 🏵 (~1.8%), Retro 🍥 (~0.7%)
  - Zenith 🪩 (~0.04%), Limited Edition 🍬 (~0.02%) - EXTREMELY rare
  - Star ⭐ (exclusive to main GC, spawns every 200 messages)
- **Weighted Selection**: System picks rarity first using weights, then selects random character from that rarity
- **Chat-Specific Spawning**: Star rarity only spawns in designated main group chat
- **Auto-incrementing IDs**: Sequence-based character ID generation
- **Image Validation**: URL validation before character upload

# External Dependencies

## Database Services
- **MongoDB Atlas**: Cloud MongoDB instance for data persistence
- **Connection String**: Configured via environment variables for security

## Telegram Platform
- **Bot API**: Official Telegram Bot API for bot operations
- **MTProto API**: Direct Telegram API access via Pyrogram for advanced features
- **File Storage**: Telegram's built-in file hosting for character images

## Image Hosting
- **Telegraph**: Primary image hosting service for character images
- **URL Validation**: Validates image URLs before storing in database

## Python Libraries
- **Core**: python-telegram-bot, pyrogram, motor (async MongoDB)
- **Utilities**: aiohttp, requests, python-dotenv, cachetools
- **Scheduling**: apscheduler for background tasks
- **Rate Limiting**: pyrate-limiter for API call management

## Configuration Management
- **Environment Variables**: Sensitive data stored in environment variables
- **Config Classes**: Separate Production/Development configuration classes
- **Runtime**: Python 3.11.0 specified for deployment compatibility
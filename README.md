# Cargo Manifest Remastered

A comprehensive plugin for [EDMC](https://github.com/EDCD/EDMarketConnector) that provides detailed cargo tracking, trading analytics, and Discord integration for Elite Dangerous.

## Features

### 📦 Cargo Management
- **Real-time cargo tracking** with detailed manifest display
- **Cargo rack analysis** showing equipped racks and total capacity
- **Mission cargo identification** and stolen goods tracking
- **Support for all cargo types** including standard, refinery, and limpet configurations

### 💰 Trading & Analytics
- **Purchase history tracking** for profit/loss calculations
- **Real-time profit/loss display** on cargo sales
- **Total trade profit/loss tracking** across sessions
- **Budget tracking** with credit goal monitoring and progress visualization

### 👨‍✈️ Captain Information
- **Commander name display** and tracking
- **Trade rank progression** with percentage progress
- **Credits display** with large number formatting

### 🎮 Discord Integration
- **Discord webhooks** for cargo buy/sell notifications
- **Rich embeds** with detailed trade information including profit/loss
- **Customizable bot name and avatar** for webhook messages
- **Discord Status Updates** showing current activity and location
- **Activity-based status** (Trading, Exploring, Transporting, Docked)

### ⚙️ Advanced Features
- **Multi-section interface** with dropdown navigation
- **Configurable display options** for trade rank and credits
- **Automatic cargo type detection** (Cargo, Refinery, Limpet)
- **MK II cargo rack support** with enhanced capacity detection
- **Large number support** for high-value transactions

## Screenshots

### Main Plugin Interface
![Main Interface](https://i.imgur.com/AZejkZ3.png)

### Discord Webhook Notifications
![Discord Webhook](https://i.imgur.com/4FalSe2.png)

### Settings Configuration
![Settings Panel](https://i.imgur.com/oZLhR3q.png)

### Trading Analytics Display
![Trading Analytics](https://i.imgur.com/uIAQksG.png)

### Cargo Racks Analysis
![Cargo Racks](https://i.imgur.com/7TqoR8U.png)

### Budget Tracking Interface
![Budget Tracking](https://i.imgur.com/ytOctAN.png)

### Captain Information Display
![Captain Info](https://i.imgur.com/AmR2TTe.png)

## Installation

1. Download the [latest release](https://github.com/inerdy/cargo-manifest-remastered/releases)
2. Extract the zip folder to your EDMC plugin directory
   - Plugin directory can be located through EDMC settings
   - Default location: `%APPDATA%\EDMarketConnector\plugins\`

## Configuration

### Basic Settings
- **Hide update indicator**: Disable the update available notification
- **Show trade rank**: Display current trade rank in manifest
- **Show credits**: Display current credit balance

### Discord Webhooks
- **Enable Discord webhooks**: Turn on webhook notifications
- **Webhook URL**: Your Discord webhook URL for notifications
- **Bot Name**: Custom name for webhook messages (optional)
- **Avatar URL**: Custom avatar for webhook messages (optional)
- **Bot Image URL**: Custom image for webhook embeds (optional)

### Discord Status Updates
- **Enable Discord Status Updates**: Show current activity in Discord
- **Status Webhook URL**: Separate webhook for status updates (optional)

### Budget Tracking
- **Enable budget tracking**: Turn on credit goal monitoring
- **Credit Goal**: Set your target credit amount (supports large numbers)

## Interface Sections

### Manifest
Displays current cargo manifest with:
- Cargo type and capacity
- Total trade profit/loss
- Detailed cargo item list
- Mission and stolen goods indicators

### Captain Information
Shows commander details including:
- Current credits
- Trade rank and progress
- Exploration rank and progress

### Budget
Budget tracking interface with:
- Credit goal progress
- Visual progress indicators
- Remaining credits needed
- Goal completion status

### Cargo Racks
Detailed cargo rack analysis:
- List of equipped cargo racks
- Individual rack capacities
- Total cargo capacity
- Support for MK II enhanced racks

## Compatibility

- **Python 3**: Required (EDMC versions 3.46+)
- **EDMC 4.1.6+**: Full compatibility with all features
- **EDMC 4.1.5 and earlier**: Basic functionality with known cargo display issues

## Discord Webhook Setup

1. Create a Discord webhook in your server:
   - Server Settings → Integrations → Webhooks → New Webhook
2. Copy the webhook URL
3. Paste it into the plugin settings
4. Enable webhooks in the plugin configuration

### Webhook Features
- **Cargo purchases**: Detailed buy notifications with location
- **Cargo sales**: Profit/loss calculations with trade analytics
- **Status updates**: Real-time activity and location updates
- **Custom styling**: Configurable bot name and avatar

## Trading Analytics

The plugin automatically tracks:
- **Purchase history** for all cargo types
- **Average buy prices** for profit calculations
- **Real-time profit/loss** on sales
- **Total trade performance** across sessions
- **Budget progress** toward credit goals



## Troubleshooting

### Common Issues
- **Cargo not displaying**: Check EDMC version compatibility
- **Webhooks not working**: Verify webhook URL and permissions
- **Ranks not showing**: Ensure game is generating journal events
- **MK II racks not detected**: Plugin will auto-detect based on capacity (dosen't seem to work correclty)

### Debug Logging
The plugin creates debug logs in the plugin directory for troubleshooting.

## Credits

- **Original plugin**: [RemainNA](https://github.com/RemainNA/cargo-manifest)
- **EDMC**: [EDMarketConnector](https://github.com/EDCD/EDMarketConnector)
- **Commodity data**: [EDCD/FDevIDs](https://github.com/EDCD/FDevIDs)


## Support

- **GitHub Issues**: Report bugs and feature requests

## License

This project is open source. See the LICENSE file for details.

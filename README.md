# FUT.GG Extinct Player Monitor

A Python bot that monitors [FUT.GG](https://www.fut.gg/players/) for extinct players and sends real-time alerts to Telegram and Discord.

## Features

- **Real-time Monitoring**: Checks FUT.GG every 5-10 minutes for extinct players
- **Dual Notifications**: Sends alerts to both Telegram and Discord
- **Player Images**: Includes actual player card images in Discord alerts
- **Smart Cooldowns**: Prevents spam with 6-hour cooldowns per player
- **Web Dashboard**: Simple web interface to monitor status
- **Database Backup**: Download/upload functionality for data persistence
- **Cloud Ready**: Optimized for Render.com deployment

## Quick Setup

### 1. Get Your Bot Tokens

**Telegram Bot:**
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Save your bot token
4. Add the bot to your chat/channel and get the chat ID

**Discord Webhook (Optional):**
1. Go to your Discord server settings
2. Navigate to Integrations > Webhooks
3. Create a new webhook and copy the URL

### 2. Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

1. Fork this repository
2. Connect your GitHub to Render.com
3. Create a new Web Service
4. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `TELEGRAM_CHAT_ID`: Your Telegram chat ID
   - `DISCORD_WEBHOOK_URL`: Your Discord webhook URL (optional)

### 3. Local Development

```bash
git clone https://github.com/yourusername/fut-gg-extinct-monitor.git
cd fut-gg-extinct-monitor

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export DISCORD_WEBHOOK_URL="your_discord_webhook"

# Run the bot
python app.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Yes | - | Your Telegram chat/channel ID |
| `DISCORD_WEBHOOK_URL` | No | - | Discord webhook URL for alerts |
| `MONITORING_CYCLE_INTERVAL` | No | 10 | Minutes between monitoring cycles |
| `ALERT_COOLDOWN_HOURS` | No | 6 | Hours before re-alerting same player |
| `MAX_PAGES_TO_SCRAPE` | No | 10 | Pages to scrape initially |
| `CARDS_TO_MONITOR_PER_CYCLE` | No | 30 | Cards to check per cycle |
| `SEND_CYCLE_SUMMARIES` | No | true | Send monitoring summary messages |

## How It Works

1. **Initial Scraping**: The bot scrapes FUT.GG player pages to build a database
2. **Continuous Monitoring**: Every 5-10 minutes, checks random players for extinct status
3. **Extinction Detection**: Looks for "EXTINCT" text in player price sections
4. **Alert System**: Sends notifications when extinct players are found
5. **Image Extraction**: Includes player card images in Discord alerts
6. **Cooldown Management**: Prevents duplicate alerts with smart cooldowns

## Sample Alerts

**Telegram:**
```
🔥 EXTINCT PLAYER DETECTED! 🔥

🃏 Debinha
⭐ Rating: 89
💰 Status: EXTINCT
📈 This player is not available on the market!
⚡ Perfect time to list if you have this card!
```

**Discord:**
- Clean embed with player name and rating
- "EXTINCT" status clearly displayed  
- Player card image as thumbnail
- Direct link to FUT.GG page

## Web Dashboard

Access your bot's dashboard at your Render URL:

- **Status Monitoring**: Real-time bot status and card count
- **Database Backup**: Download/upload your player database
- **Configuration**: View current settings
- **Debug Info**: Environment and thread status

## File Structure

```
fut-gg-extinct-monitor/
├── app.py                      # Flask web interface
├── fut_gg_extinct_monitor.py   # Main monitoring logic
├── config.py                   # Configuration management
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render deployment config
└── README.md                   # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Troubleshooting

**Bot not starting:**
- Check that `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set
- Verify bot has permission to send messages to your chat

**No extinct alerts:**
- Monitor may be checking different players each cycle
- Check web dashboard for monitoring status
- Extinct players are rare - be patient!

**Database issues:**
- Use the backup/restore feature in web dashboard
- Database resets on Render restarts (free tier limitation)

## License

MIT License - feel free to modify and distribute.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review Render logs for detailed error messages
- Open an issue on GitHub
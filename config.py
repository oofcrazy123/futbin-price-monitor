import os

class Config:
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # Discord Configuration (Optional)
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
    
    # Monitoring Settings
    MONITORING_CYCLE_INTERVAL = int(os.getenv('MONITORING_CYCLE_INTERVAL', '10'))  # minutes between checks
    ALERT_COOLDOWN_HOURS = int(os.getenv('ALERT_COOLDOWN_HOURS', '6'))  # hours before re-alerting same card
    
    # Scraping Settings
    MAX_PAGES_TO_SCRAPE = int(os.getenv('MAX_PAGES_TO_SCRAPE', '10'))  # pages to scrape initially
    CARDS_TO_MONITOR_PER_CYCLE = int(os.getenv('CARDS_TO_MONITOR_PER_CYCLE', '30'))  # cards per monitoring cycle
    
    # Advanced Settings
    SKIP_SCRAPING = os.getenv('SKIP_SCRAPING', 'false').lower() == 'true'
    SEND_CYCLE_SUMMARIES = os.getenv('SEND_CYCLE_SUMMARIES', 'true').lower() == 'true'
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        if not cls.TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")
        
        print("✅ Configuration validated successfully")
        return True
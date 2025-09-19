import os
from datetime import timedelta

# Try to load from .env file (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded .env file for local development")
except ImportError:
    print("📦 python-dotenv not installed, using system environment variables only")
except Exception as e:
    print(f"⚠️ Error loading .env file: {e}")

class Config:
    """Configuration class that handles both local .env and production environment variables"""
    
    # =============================================================================
    # TELEGRAM CONFIGURATION (Required)
    # =============================================================================
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # =============================================================================
    # DISCORD CONFIGURATION (Optional)
    # =============================================================================
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
    
    # =============================================================================
    # PRICE GAP ALERT CONFIGURATION
    # =============================================================================
    MINIMUM_PRICE_GAP_COINS = int(os.getenv('MINIMUM_PRICE_GAP_COINS', '1000'))
    MINIMUM_PRICE_GAP_PERCENTAGE = float(os.getenv('MINIMUM_PRICE_GAP_PERCENTAGE', '5'))
    MINIMUM_CARD_PRICE = int(os.getenv('MINIMUM_CARD_PRICE', '5000'))
    
    # =============================================================================
    # SCRAPING CONFIGURATION  
    # =============================================================================
    PAGES_TO_SCRAPE = int(os.getenv('PAGES_TO_SCRAPE', '50'))  # Reduced for faster startup
    MAX_PAGES = int(os.getenv('MAX_PAGES', '786'))
    CARDS_PER_PAGE = int(os.getenv('CARDS_PER_PAGE', '30'))
    SKIP_SCRAPING = os.getenv('SKIP_SCRAPING', 'False').lower() == 'true'
    
    # =============================================================================
    # MONITORING CONFIGURATION
    # =============================================================================
    ALERT_COOLDOWN_MINUTES = int(os.getenv('ALERT_COOLDOWN_MINUTES', '60'))
    MONITORING_CYCLE_INTERVAL = int(os.getenv('MONITORING_CYCLE_INTERVAL', '45'))
    
    # =============================================================================
    # NOTIFICATION CONFIGURATION
    # =============================================================================
    PROGRESS_NOTIFICATION_INTERVAL = int(os.getenv('PROGRESS_NOTIFICATION_INTERVAL', '10'))
    SEND_CYCLE_SUMMARIES = os.getenv('SEND_CYCLE_SUMMARIES', 'True').lower() == 'true'
    
    # =============================================================================
    # SCRAPING DELAY CONFIGURATION (Anti-detection)
    # =============================================================================
    SCRAPING_DELAY_MIN = float(os.getenv('SCRAPING_DELAY_MIN', '3.0'))
    SCRAPING_DELAY_MAX = float(os.getenv('SCRAPING_DELAY_MAX', '6.0'))
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN environment variable is required")
        
        if not cls.TELEGRAM_CHAT_ID:
            raise ValueError("❌ TELEGRAM_CHAT_ID environment variable is required")
        
        print("✅ Configuration loaded successfully!")
        print(f"📊 Alert thresholds: {cls.MINIMUM_PRICE_GAP_COINS:,} coins, {cls.MINIMUM_PRICE_GAP_PERCENTAGE}%")
        print(f"💰 Minimum card value: {cls.MINIMUM_CARD_PRICE:,} coins")
        print(f"📄 Scraping plan: {cls.PAGES_TO_SCRAPE} pages ({cls.PAGES_TO_SCRAPE * cls.CARDS_PER_PAGE:,} cards)")
        print(f"⏰ Alert cooldown: {cls.ALERT_COOLDOWN_MINUTES} minutes")
        
        # Discord optional
        if cls.DISCORD_WEBHOOK_URL:
            print("📢 Discord notifications: ENABLED")
        else:
            print("📢 Discord notifications: DISABLED (set DISCORD_WEBHOOK_URL to enable)")
        
        return True
    
    @classmethod
    def get_scraping_delay_range(cls):
        """Get the delay range for scraping between pages"""
        return cls.SCRAPING_DELAY_MIN, cls.SCRAPING_DELAY_MAX
    
    @classmethod
    def get_alert_cooldown_timedelta(cls):
        """Get alert cooldown as timedelta object"""
        return timedelta(minutes=cls.ALERT_COOLDOWN_MINUTES)
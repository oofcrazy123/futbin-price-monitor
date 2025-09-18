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
    """Centralized configuration for Futbin Price Monitor"""
    
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
    # PRICE ALERT CONFIGURATION
    # =============================================================================
    
    # Minimum profit after EA tax to trigger alert (in coins)
    MINIMUM_PRICE_GAP_COINS = int(os.getenv('MINIMUM_PRICE_GAP_COINS', '1000'))
    
    # Minimum profit percentage to trigger alert (based on buy price)
    MINIMUM_PRICE_GAP_PERCENTAGE = float(os.getenv('MINIMUM_PRICE_GAP_PERCENTAGE', '5'))
    
    # Only monitor cards worth at least this much (filters out low-value cards)
    MINIMUM_CARD_PRICE = int(os.getenv('MINIMUM_CARD_PRICE', '3000'))
    
    # Prevent duplicate alerts for same card within this timeframe (minutes)
    ALERT_COOLDOWN_MINUTES = int(os.getenv('ALERT_COOLDOWN_MINUTES', '20'))
    
    # =============================================================================
    # SCRAPING CONFIGURATION
    # =============================================================================
    
    # Number of pages to scrape initially (30 cards per page)
    PAGES_TO_SCRAPE = int(os.getenv('PAGES_TO_SCRAPE', '100'))
    
    # Maximum pages available on Futbin
    MAX_PAGES = int(os.getenv('MAX_PAGES', '786'))
    
    # Cards per page (Futbin standard)
    CARDS_PER_PAGE = int(os.getenv('CARDS_PER_PAGE', '30'))
    
    # =============================================================================
    # ANTI-DETECTION CONFIGURATION
    # =============================================================================
    
    # Delay between page scraping (seconds) - prevents Cloudflare blocking
    SCRAPING_DELAY_MIN = float(os.getenv('SCRAPING_DELAY_MIN', '3'))
    SCRAPING_DELAY_MAX = float(os.getenv('SCRAPING_DELAY_MAX', '6'))
    
    # Delay between individual card price checks (seconds)
    PRICE_CHECK_DELAY_MIN = float(os.getenv('PRICE_CHECK_DELAY_MIN', '4'))
    PRICE_CHECK_DELAY_MAX = float(os.getenv('PRICE_CHECK_DELAY_MAX', '8'))
    
    # How often to run full monitoring cycles (minutes)
    MONITORING_CYCLE_INTERVAL = int(os.getenv('MONITORING_CYCLE_INTERVAL', '45'))
    
    # Number of cards to monitor per cycle
    CARDS_PER_MONITORING_CYCLE = int(os.getenv('CARDS_PER_MONITORING_CYCLE', '100'))
    
    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    
    # Database file path
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'futbin_cards.db')
    
    # =============================================================================
    # NOTIFICATION CONFIGURATION
    # =============================================================================
    
    # Send progress notifications every N pages during scraping
    PROGRESS_NOTIFICATION_INTERVAL = int(os.getenv('PROGRESS_NOTIFICATION_INTERVAL', '25'))
    
    # Send cycle summary notifications
    SEND_CYCLE_SUMMARIES = os.getenv('SEND_CYCLE_SUMMARIES', 'true').lower() == 'true'
    
    # =============================================================================
    # VALIDATION AND SETUP
    # =============================================================================
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        errors = []
        
        # Required configurations
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is required")
        
        # Validation checks
        if cls.MINIMUM_PRICE_GAP_COINS < 100:
            errors.append("MINIMUM_PRICE_GAP_COINS should be at least 100")
        
        if cls.MINIMUM_PRICE_GAP_PERCENTAGE < 1:
            errors.append("MINIMUM_PRICE_GAP_PERCENTAGE should be at least 1")
        
        if cls.PAGES_TO_SCRAPE > cls.MAX_PAGES:
            errors.append(f"PAGES_TO_SCRAPE ({cls.PAGES_TO_SCRAPE}) cannot exceed MAX_PAGES ({cls.MAX_PAGES})")
        
        if errors:
            error_msg = "❌ Configuration errors:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)
        
        # Success message
        print("✅ Configuration loaded successfully!")
        print(f"📊 Alert thresholds: {cls.MINIMUM_PRICE_GAP_COINS:,} coins, {cls.MINIMUM_PRICE_GAP_PERCENTAGE}%")
        print(f"💰 Minimum card value: {cls.MINIMUM_CARD_PRICE:,} coins")
        print(f"📄 Scraping plan: {cls.PAGES_TO_SCRAPE} pages ({cls.PAGES_TO_SCRAPE * cls.CARDS_PER_PAGE:,} cards)")
        print(f"⏰ Alert cooldown: {cls.ALERT_COOLDOWN_MINUTES} minutes")
        print(f"🔄 Monitoring cycle: Every {cls.MONITORING_CYCLE_INTERVAL} minutes")
        
        # Optional features
        if cls.DISCORD_WEBHOOK_URL:
            print("📢 Discord notifications: ENABLED")
        else:
            print("📢 Discord notifications: DISABLED (set DISCORD_WEBHOOK_URL to enable)")
        
        return True
    
    @classmethod
    def get_scraping_delay_range(cls):
        """Get random delay range for scraping"""
        return (cls.SCRAPING_DELAY_MIN, cls.SCRAPING_DELAY_MAX)
    
    @classmethod
    def get_price_check_delay_range(cls):
        """Get random delay range for price checking"""
        return (cls.PRICE_CHECK_DELAY_MIN, cls.PRICE_CHECK_DELAY_MAX)
    
    @classmethod
    def get_alert_cooldown_timedelta(cls):
        """Get alert cooldown as timedelta object"""
        return timedelta(minutes=cls.ALERT_COOLDOWN_MINUTES)
    
    @classmethod
    def get_monitoring_cycle_seconds(cls):
        """Get monitoring cycle interval in seconds"""
        return cls.MONITORING_CYCLE_INTERVAL * 60

# Test environment variables on import
if __name__ == "__main__":
    print("Testing configuration...")
    try:
        Config.validate_config()
        print("✅ All configuration tests passed!")
    except ValueError as e:
        print(f"❌ Configuration test failed: {e}")
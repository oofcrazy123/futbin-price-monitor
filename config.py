import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

class Config:
    """Configuration class that handles both local .env and production environment variables"""
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # Price Gap Alert Configuration
    MINIMUM_PRICE_GAP_COINS = int(os.getenv('MINIMUM_PRICE_GAP_COINS', '1000'))
    MINIMUM_PRICE_GAP_PERCENTAGE = float(os.getenv('MINIMUM_PRICE_GAP_PERCENTAGE', '5'))
    MINIMUM_CARD_PRICE = int(os.getenv('MINIMUM_CARD_PRICE', '5000'))
    
    # Scraping Configuration  
    PAGES_TO_SCRAPE = int(os.getenv('PAGES_TO_SCRAPE', '100'))
    MAX_PAGES = int(os.getenv('MAX_PAGES', '786'))
    CARDS_PER_PAGE = int(os.getenv('CARDS_PER_PAGE', '30'))
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        if not cls.TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")
        
        print("✅ Configuration loaded successfully!")
        print(f"📊 Monitoring settings: {cls.MINIMUM_PRICE_GAP_COINS:,} coins, {cls.MINIMUM_PRICE_GAP_PERCENTAGE}%")
        print(f"📄 Scraping: {cls.PAGES_TO_SCRAPE} pages ({cls.PAGES_TO_SCRAPE * cls.CARDS_PER_PAGE:,} cards)")
        
        return True

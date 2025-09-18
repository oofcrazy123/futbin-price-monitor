import requests
import time
import json
import sqlite3
from datetime import datetime, timedelta
import random
from bs4 import BeautifulSoup
import os
import threading

# Try to load from .env file (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded .env file for local development")
except ImportError:
    print("📦 python-dotenv not installed, using system environment variables only")

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
            raise ValueError("❌ TELEGRAM_BOT_TOKEN environment variable is required")
        
        if not cls.TELEGRAM_CHAT_ID:
            raise ValueError("❌ TELEGRAM_CHAT_ID environment variable is required")
        
        print("✅ Configuration loaded successfully!")
        print(f"📊 Alert thresholds: {cls.MINIMUM_PRICE_GAP_COINS:,} coins, {cls.MINIMUM_PRICE_GAP_PERCENTAGE}%")
        print(f"💰 Minimum card value: {cls.MINIMUM_CARD_PRICE:,} coins")
        print(f"📄 Scraping plan: {cls.PAGES_TO_SCRAPE} pages ({cls.PAGES_TO_SCRAPE * cls.CARDS_PER_PAGE:,} cards)")
        
        return True

class FutbinPriceMonitor:
    def __init__(self, db_path="futbin_cards.db"):
        # Validate configuration on startup
        Config.validate_config()
        
        self.db_path = db_path
        self.session = requests.Session()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        self.init_database()
    
    def rotate_user_agent(self):
        """Rotate user agent to avoid detection"""
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents)
        })
    
    def init_database(self):
        """Initialize SQLite database (YOUR own database!)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rating INTEGER,
                position TEXT,
                club TEXT,
                nation TEXT,
                league TEXT,
                card_type TEXT,
                futbin_url TEXT UNIQUE,
                futbin_id TEXT,
                last_price_check TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER,
                platform TEXT,
                buy_price INTEGER,
                sell_price INTEGER,
                sell_price_after_tax INTEGER,
                profit_after_tax INTEGER,
                percentage_profit REAL,
                ea_tax INTEGER,
                alert_sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (card_id) REFERENCES cards (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized!")
    
    def scrape_futbin_cards_list(self, page_num):
        """
        Scrape cards from a Futbin players page
        Based on the GitHub repo logic but simplified
        """
        try:
            self.rotate_user_agent()
            
            url = f'https://www.futbin.com/players?page={page_num}'
            response = self.session.get(url)
            
            if response.status_code != 200:
                print(f"❌ Failed to get page {page_num}: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            cards = []
            
            # Find player rows (similar to GitHub repo)
            for row_class in ['player_tr_1', 'player_tr_2']:
                player_rows = soup.find_all('tr', class_=row_class)
                
                for row in player_rows:
                    try:
                        card_data = self.extract_card_data(row)
                        if card_data:
                            cards.append(card_data)
                    except Exception as e:
                        print(f"Error extracting card: {e}")
                        continue
            
            return cards
            
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            return []
    
    def extract_card_data(self, row):
        """Extract card information from a table row"""
        try:
            # Get player name and URL
            name_link = row.find('a', class_='player_name_players_table')
            if not name_link:
                # Try alternative selectors for current Futbin structure
                name_link = row.find('a', href=lambda x: x and '/player/' in str(x))
            
            if not name_link:
                return None
            
            name = name_link.get_text(strip=True)
            futbin_url = name_link['href']
            
            # Ensure full URL
            if futbin_url.startswith('/'):
                futbin_url = 'https://www.futbin.com' + futbin_url
            
            # Extract futbin ID from URL (format: /26/player/18710/henry)
            url_parts = futbin_url.split('/')
            futbin_id = url_parts[-2] if len(url_parts) > 2 else None
            
            # Get rating
            rating_elem = row.find('span', class_='rating')
            rating = int(rating_elem.get_text(strip=True)) if rating_elem else 0
            
            # Get position
            position_elem = row.find('td', class_='position')
            position = position_elem.get_text(strip=True) if position_elem else ''
            
            # Get club
            club_elem = row.find('a', href=lambda x: x and '/club/' in str(x))
            club = club_elem.get_text(strip=True) if club_elem else ''
            
            # Get nation
            nation_elem = row.find('a', href=lambda x: x and '/nation/' in str(x))
            nation = nation_elem.get_text(strip=True) if nation_elem else ''
            
            # Get league
            league_elem = row.find('a', href=lambda x: x and '/league/' in str(x))
            league = league_elem.get_text(strip=True) if league_elem else ''
            
            # Determine card type based on rating/special indicators
            card_type = 'Gold' if rating >= 75 else 'Silver' if rating >= 65 else 'Bronze'
            if any(keyword in name.lower() for keyword in ['toty', 'tots', 'motm', 'if', 'sbc']):
                card_type = 'Special'
            
            return {
                'name': name,
                'rating': rating,
                'position': position,
                'club': club,
                'nation': nation,
                'league': league,
                'card_type': card_type,
                'futbin_url': futbin_url,
                'futbin_id': futbin_id
            }
            
        except Exception as e:
            print(f"Error extracting card data: {e}")
            return None
    
    def save_cards_to_db(self, cards):
        """Save scraped cards to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        for card in cards:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO cards 
                    (name, rating, position, club, nation, league, card_type, futbin_url, futbin_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    card['name'], card['rating'], card['position'], card['club'],
                    card['nation'], card['league'], card['card_type'], 
                    card['futbin_url'], card['futbin_id']
                ))
                if cursor.rowcount > 0:
                    saved_count += 1
            except Exception as e:
                print(f"Error saving card {card['name']}: {e}")
        
        conn.commit()
        conn.close()
        return saved_count
    
    def scrape_all_cards(self):
        """Scrape cards from all pages (like the GitHub repo but YOUR database)"""
        print(f"🚀 Starting to scrape {Config.PAGES_TO_SCRAPE} pages ({Config.PAGES_TO_SCRAPE * Config.CARDS_PER_PAGE} cards)...")
        
        total_saved = 0
        
        for page in range(1, Config.PAGES_TO_SCRAPE + 1):
            try:
                print(f"📄 Scraping page {page}/{Config.PAGES_TO_SCRAPE}...")
                
                cards = self.scrape_futbin_cards_list(page)
                if cards:
                    saved = self.save_cards_to_db(cards)
                    total_saved += saved
                    print(f"✅ Page {page}: Found {len(cards)} cards, saved {saved} new cards")
                else:
                    print(f"⚠️ Page {page}: No cards found")
                
                # Progress notification every 25 pages
                if page % 25 == 0:
                    self.send_telegram_notification(
                        f"📊 Scraping Progress: {page}/{Config.PAGES_TO_SCRAPE} pages complete\n"
                        f"💾 Total cards saved: {total_saved}"
                    )
                
                # Random delay between pages (3-6 seconds)
                time.sleep(random.uniform(3, 6))
                
            except Exception as e:
                print(f"❌ Error on page {page}: {e}")
                continue
        
        print(f"🎉 Scraping complete! Total cards saved: {total_saved}")
        self.send_telegram_notification(
            f"🎉 Futbin scraping complete!\n"
            f"📊 Pages scraped: {Config.PAGES_TO_SCRAPE}\n"
            f"💾 Total cards in database: {total_saved}\n"
            f"🤖 Price monitoring will start now!"
        )
        
        return total_saved
    
    def scrape_card_prices(self, futbin_url):
        """Scrape current prices from a card's Futbin page"""
        try:
            self.rotate_user_agent()
            response = self.session.get(futbin_url)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            prices = {'ps': [], 'xbox': [], 'pc': []}
            
            # Look for the price container sections with updated selectors
            
            # Try multiple methods to find price data
            prices_found = False
            
            # Method 1: Look for table cells with coin images (current structure)
            price_cells = soup.find_all('td', string=lambda text: text and ('K' in str(text) or 'M' in str(text)))
            if price_cells:
                all_prices = []
                for cell in price_cells:
                    try:
                        price_text = cell.get_text(strip=True)
                        if price_text and price_text != '0':
                            price = self.parse_price_text(price_text)
                            if price > 0:
                                all_prices.append(price)
                    except:
                        continue
                
                # Assign prices to platforms (first few go to PS, others to Xbox/PC)
                if all_prices:
                    all_prices = sorted(list(set(all_prices)))
                    prices['ps'] = all_prices[:min(5, len(all_prices))]
                    if len(all_prices) > 5:
                        prices['xbox'] = all_prices[5:min(10, len(all_prices))]
                    prices_found = True
            
            # Method 2: Console-specific sections (fallback)
            if not prices_found:
                console_sections = {
                    'ps': soup.find('div', {'id': 'ps-prices'}) or soup.find('[data-console="ps"]'),
                    'xbox': soup.find('div', {'id': 'xbox-prices'}) or soup.find('[data-console="xbox"]'), 
                    'pc': soup.find('div', {'id': 'pc-prices'}) or soup.find('[data-console="pc"]')
                }
                
                for platform, section in console_sections.items():
                    if section:
                        price_selectors = [
                            '.bin-price', '.price-value', '.lowest-price', 
                            '[data-price]', '.market-price', '.current-price'
                        ]
                        
                        platform_prices = []
                        for selector in price_selectors:
                            price_elements = section.select(selector)
                            for elem in price_elements:
                                try:
                                    price_text = elem.get_text(strip=True)
                                    if price_text and price_text != '0' and price_text != '-':
                                        price = self.parse_price_text(price_text)
                                        if price > 0:
                                            platform_prices.append(price)
                                except:
                                    continue
                            
                            # Also try data attributes
                            if hasattr(elem, 'get') and elem.get('data-price'):
                                try:
                                    price = int(elem.get('data-price'))
                                    if price > 0:
                                        platform_prices.append(price)
                                except:
                                    continue
                        
                        # Remove duplicates and sort
                        prices[platform] = sorted(list(set(platform_prices)))
            
            # Method 3: If no console-specific sections found, try general approach
            if all(len(prices[p]) == 0 for p in prices):
                # Look for any price elements on the page
                all_price_elements = soup.select('.price, [class*="price"], [data-price]')
                general_prices = []
                
                for elem in all_price_elements:
                    try:
                        price_text = elem.get_text(strip=True)
                        if price_text:
                            price = self.parse_price_text(price_text)
                            if price > 0:
                                general_prices.append(price)
                    except:
                        continue
                
                # If we found prices but couldn't categorize by platform,
                # assume they're for the default platform (PS)
                if general_prices:
                    prices['ps'] = sorted(list(set(general_prices)))
            
            return prices
            
        except Exception as e:
            print(f"Error scraping prices from {futbin_url}: {e}")
            return None
    
    def parse_price_text(self, price_text):
        """Parse price text into integer coins"""
        try:
            # Clean the price text
            cleaned = price_text.replace(',', '').replace(' ', '').upper()
            
            # Handle different formats
            if 'K' in cleaned:
                # Handle "1.5K", "15K", etc.
                number = float(cleaned.replace('K', ''))
                return int(number * 1000)
            elif 'M' in cleaned:
                # Handle "1.2M", "15M", etc.
                number = float(cleaned.replace('M', ''))
                return int(number * 1000000)
            else:
                # Direct number
                return int(cleaned)
        except:
            return 0
    
    def analyze_price_gap(self, prices_list):
        """
        Analyze price gap between first and second lowest prices
        Calculate actual trading profit after EA tax
        """
        if len(prices_list) < 2:
            return None
        
        # Sort to ensure we have lowest prices first
        sorted_prices = sorted(prices_list)
        buy_price = sorted_prices[0]  # First (lowest) price - what we buy for
        sell_price = sorted_prices[1]  # Second price - what we sell for
        
        if buy_price < Config.MINIMUM_CARD_PRICE:
            return None
        
        # Calculate EA tax (5% on all sales)
        ea_tax = sell_price * 0.05
        sell_price_after_tax = sell_price - ea_tax
        
        # Calculate actual profit
        raw_profit = sell_price - buy_price
        profit_after_tax = sell_price_after_tax - buy_price
        
        # Only alert if there's actual profit after tax
        if profit_after_tax < Config.MINIMUM_PRICE_GAP_COINS:
            return None
        
        # Calculate percentage profit (based on buy price)
        percentage_profit = (profit_after_tax / buy_price) * 100
        
        if percentage_profit < Config.MINIMUM_PRICE_GAP_PERCENTAGE:
            return None
        
        return {
            'buy_price': buy_price,
            'sell_price': sell_price,
            'sell_price_after_tax': int(sell_price_after_tax),
            'raw_profit': raw_profit,
            'profit_after_tax': int(profit_after_tax),
            'percentage_profit': percentage_profit,
            'ea_tax': int(ea_tax)
        }
    
    def send_telegram_notification(self, message):
        """Send notification to Telegram using config"""
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': Config.TELEGRAM_CHAT_ID,
            'text': message
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print("✅ Telegram notification sent")
            else:
                print(f"❌ Telegram error: {response.status_code}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")
    
    def send_price_alert(self, card_info, platform, gap_info):
        """Send price gap alert with proper trading calculations"""
        
        # Calculate profit margins for better context
        profit_margin = (gap_info['profit_after_tax'] / gap_info['buy_price']) * 100
        
        # Determine profit quality
        if profit_margin >= 20:
            profit_emoji = "🤑"
            profit_quality = "EXCELLENT"
        elif profit_margin >= 10:
            profit_emoji = "💰"
            profit_quality = "GOOD"
        else:
            profit_emoji = "💡"
            profit_quality = "DECENT"
        
        message = f"""
🚨 {profit_emoji} TRADING OPPORTUNITY - {profit_quality} 🚨

🃏 **{card_info['name']}**
📱 Platform: {platform.upper()}
⭐ Rating: {card_info['rating']} | 🏆 {card_info['position']}
🏟️ {card_info.get('club', 'N/A')} | 🌍 {card_info.get('nation', 'N/A')}

💸 **TRADING DETAILS:**
├─ 🛒 Buy Price: {gap_info['buy_price']:,} coins
├─ 🏷️ Sell Price: {gap_info['sell_price']:,} coins
├─ 💸 EA Tax (5%): -{gap_info['ea_tax']:,} coins
├─ 💰 After Tax: {gap_info['sell_price_after_tax']:,} coins
└─ 🎯 **PROFIT: {gap_info['profit_after_tax']:,} coins ({profit_margin:.1f}%)**

📊 **STRATEGY:**
1️⃣ Buy at: {gap_info['buy_price']:,} coins (lowest BIN)
2️⃣ Sell at: {gap_info['sell_price']:,} coins (2nd lowest)
3️⃣ Profit: {gap_info['profit_after_tax']:,} coins after tax

🔗 {card_info['futbin_url']}
⏰ {datetime.now().strftime('%H:%M:%S')}

⚡ **Quick Math:**
Raw Profit: {gap_info['raw_profit']:,} | EA Tax: {gap_info['ea_tax']:,} | Net: {gap_info['profit_after_tax']:,}
        """
        
        self.send_telegram_notification(message.strip())
        
        # Save alert to database
        self.save_price_alert(card_info['id'], platform, gap_info)
        print(f"🚨 TRADING ALERT: {card_info['name']} ({platform}) - Buy {gap_info['buy_price']:,}, Sell {gap_info['sell_price']:,}, Profit {gap_info['profit_after_tax']:,}")
    
    def save_price_alert(self, card_id, platform, gap_info):
        """Save price alert to database with updated schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO price_alerts 
            (card_id, platform, buy_price, sell_price, sell_price_after_tax, profit_after_tax, percentage_profit, ea_tax)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            card_id, platform, gap_info['buy_price'], gap_info['sell_price'],
            gap_info['sell_price_after_tax'], gap_info['profit_after_tax'], 
            gap_info['percentage_profit'], gap_info['ea_tax']
        ))
        
        conn.commit()
        conn.close()
    
    def get_cards_to_monitor(self, limit=200):
        """Get cards from database to monitor for price gaps"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Focus on high-value cards first
        cursor.execute('''
            SELECT id, name, rating, position, club, nation, league, futbin_url
            FROM cards 
            WHERE rating >= 80 
            ORDER BY rating DESC, name ASC
            LIMIT ?
        ''', (limit,))
        
        cards = []
        for row in cursor.fetchall():
            cards.append({
                'id': row[0],
                'name': row[1],
                'rating': row[2],
                'position': row[3],
                'club': row[4],
                'nation': row[5],
                'league': row[6],
                'futbin_url': row[7]
            })
        
        conn.close()
        return cards
    
    def run_price_monitoring(self):
        """Main monitoring loop"""
        print("🤖 Starting price monitoring...")
        
        while True:
            try:
                cards = self.get_cards_to_monitor(100)  # Monitor 100 cards per cycle
                if not cards:
                    print("❌ No cards in database! Run scraping first.")
                    return
                
                print(f"📊 Monitoring {len(cards)} cards for price gaps...")
                
                for i, card in enumerate(cards):
                    try:
                        prices = self.scrape_card_prices(card['futbin_url'])
                        
                        if prices:
                            for platform, price_list in prices.items():
                                if len(price_list) >= 2:
                                    gap_info = self.analyze_price_gap(price_list)
                                    if gap_info:
                                        self.send_price_alert(card, platform, gap_info)
                        
                        # Progress update
                        if (i + 1) % 25 == 0:
                            print(f"✅ Checked {i + 1}/{len(cards)} cards...")
                        
                        # Delay between requests
                        time.sleep(random.uniform(4, 8))
                        
                    except Exception as e:
                        print(f"Error monitoring {card['name']}: {e}")
                        continue
                
                print("💤 Cycle complete. Waiting 45 minutes for next check...")
                time.sleep(2700)  # 45 minutes
                
            except KeyboardInterrupt:
                print("🛑 Monitoring stopped!")
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(300)
    
    def run_complete_system(self):
        """Run the complete system: scrape cards, then monitor prices"""
        print("🚀 Starting complete Futbin Price Gap Monitor system!")
        
        # First, check if we have cards in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cards')
        card_count = cursor.fetchone()[0]
        conn.close()
        
        if card_count < 100:
            print(f"📊 Only {card_count} cards in database. Starting scraping...")
            self.scrape_all_cards()
        else:
            print(f"✅ Found {card_count} cards in database. Starting monitoring...")
        
        # Start price monitoring
        self.run_price_monitoring()

if __name__ == "__main__":
    # Run the complete system
    monitor = FutbinPriceMonitor()
    monitor.run_complete_system()
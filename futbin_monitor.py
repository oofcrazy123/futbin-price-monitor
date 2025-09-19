import requests
import time
import json
import sqlite3
from datetime import datetime, timedelta
import random
from bs4 import BeautifulSoup
import os
import threading
from config import Config

# Test environment variables immediately
print(f"🔑 Bot token available: {'Yes' if Config.TELEGRAM_BOT_TOKEN else 'No'}")
print(f"💬 Chat ID available: {'Yes' if Config.TELEGRAM_CHAT_ID else 'No'}")
if Config.DISCORD_WEBHOOK_URL:
    print(f"📢 Discord webhook available: Yes")
else:
    print(f"📢 Discord webhook available: No")

class FutbinPriceMonitor:
    def __init__(self, db_path="futbin_cards.db"):
        # Validate configuration on startup
        Config.validate_config()
        
        # For cloud deployment, try to use a persistent path
        if os.getenv('RENDER_EXTERNAL_HOSTNAME'):
            # We're on Render - try to use a persistent location
            db_path = "/opt/render/project/src/futbin_cards.db"
            print(f"🌐 Running on Render, using database path: {db_path}")
        else:
            print(f"🏠 Running locally, using database path: {db_path}")
        
        self.db_path = db_path
        
        # Test database write permissions
        try:
            test_conn = sqlite3.connect(self.db_path)
            test_conn.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER)")
            test_conn.execute("INSERT INTO test_table (id) VALUES (1)")
            test_conn.execute("DROP TABLE test_table")
            test_conn.commit()
            test_conn.close()
            print("✅ Database write test successful")
        except Exception as e:
            print(f"⚠️ Database write test failed: {e}")
            print("📁 Trying alternative database location...")
            # Fallback to /tmp (temporary but works)
            self.db_path = "/tmp/futbin_cards.db"
            print(f"🔄 Using fallback database path: {self.db_path}")
        
        self.session = requests.Session()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        self.init_database()
        self.startup_sent = False  # Flag to prevent duplicate startup messages
    
    def rotate_user_agent(self):
        """Rotate user agent to avoid detection"""
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents)
        })
    
    def init_database(self):
        """Initialize SQLite database (YOUR own database!)"""
        print(f"🔧 Initializing database at: {self.db_path}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print("📋 Creating cards table...")
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
            
            print("📋 Creating price_alerts table...")
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS startup_locks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    startup_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    instance_id TEXT UNIQUE
                )
            ''')
            
            conn.commit()
            
            # Test if we can actually read/write
            cursor.execute('SELECT COUNT(*) FROM cards')
            existing_cards = cursor.fetchone()[0]
            print(f"📊 Database initialized! Existing cards: {existing_cards}")
            
            conn.close()
            print("✅ Database initialization successful!")
            
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def check_and_send_startup_notification(self):
        """Send startup notification only once per deployment - improved logic"""
        if self.startup_sent:
            return
        
        # Create a more unique instance ID
        import uuid
        instance_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Use a more aggressive lock to prevent race conditions
            # Try to insert our instance ID immediately - this will fail if another instance is already starting
            cursor.execute('''
                INSERT INTO startup_locks (instance_id, startup_time)
                VALUES (?, ?)
            ''', (instance_id, datetime.now()))
            
            conn.commit()
            
            # If we got here, we successfully claimed the startup lock
            print(f"✅ Startup lock acquired: {instance_id}")
            
            # Send startup notification
            self.send_notification_to_all(
                f"🤖 Futbin Bot Started!\n"
                f"📊 Scraping {Config.PAGES_TO_SCRAPE} pages ({Config.PAGES_TO_SCRAPE * Config.CARDS_PER_PAGE:,} cards)\n"
                f"⚡ Running on cloud infrastructure\n"
                f"💰 Alert thresholds: {Config.MINIMUM_PRICE_GAP_COINS:,} coins, {Config.MINIMUM_PRICE_GAP_PERCENTAGE}%\n"
                f"⏰ Alert cooldown: {Config.ALERT_COOLDOWN_MINUTES} minutes\n"
                f"🔑 Instance: {instance_id[:12]}",
                "🚀 Bot Started"
            )
            
            self.startup_sent = True
            print("✅ Startup notification sent")
            
        except sqlite3.IntegrityError:
            # Another instance already claimed the startup lock
            print(f"⚠️ Another instance already started, skipping startup notification")
            self.startup_sent = True
        except Exception as e:
            print(f"Error with startup notification: {e}")
            # Don't block the bot if notification fails
            self.startup_sent = True
        finally:
            try:
                conn.close()
            except:
                pass
    
    def scrape_futbin_cards_list(self, page_num):
        """
        Scrape cards from a Futbin players page - Updated for current structure
        """
        try:
            self.rotate_user_agent()
            
            url = f'https://www.futbin.com/players?page={page_num}'
            print(f"🌐 Fetching: {url}")
            response = self.session.get(url)
            
            if response.status_code != 200:
                print(f"❌ Failed to get page {page_num}: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            cards = []
            
            print(f"📄 Page {page_num} - Content length: {len(response.content)} bytes")
            
            # Debug: Save a sample of the HTML to see the actual structure
            if page_num == 1:
                print("🔍 DEBUG: Analyzing page structure...")
                print(f"Page title: {soup.title.string if soup.title else 'No title'}")
                
                # Look for any tables on the page
                all_tables = soup.find_all('table')
                print(f"Found {len(all_tables)} tables on the page")
                
                # Look for any player links
                all_player_links = soup.find_all('a', href=lambda x: x and '/player/' in str(x))
                print(f"Found {len(all_player_links)} total player links")
                
                if len(all_player_links) < 10:
                    print("⚠️ WARNING: Very few player links found - website structure may have changed")
                    print("First few links found:")
                    for i, link in enumerate(all_player_links[:5]):
                        print(f"  {i+1}. {link.get('href')} - {link.get_text(strip=True)}")
            
            # Look for the main players table
            players_table = soup.find('table', class_='futbin-table players-table')
            if not players_table:
                players_table = soup.find('table', class_='futbin-table')
            
            if players_table:
                print("✅ Found futbin-table")
                
                # Look for tbody with player rows
                tbody = players_table.find('tbody', class_='with-border with-background')
                if not tbody:
                    tbody = players_table.find('tbody')
                
                if tbody:
                    print("✅ Found tbody section")
                    
                    # Find all table rows in tbody
                    player_rows = tbody.find_all('tr')
                    print(f"🔍 Found {len(player_rows)} rows in tbody")
                    
                    if len(player_rows) == 0:
                        print("⚠️ WARNING: No rows found in tbody - this could be why card count is low")
                    
                    for i, row in enumerate(player_rows):
                        try:
                            # Look for player links in this row
                            player_links = row.find_all('a', href=lambda x: x and '/player/' in str(x))
                            
                            if player_links:
                                # Extract data from the row
                                card_data = self.extract_card_from_row(row, player_links)
                                if card_data:
                                    cards.append(card_data)
                                    if i < 3:  # Show first 3 for debugging
                                        print(f"✅ Extracted: {card_data['name']} ({card_data['rating']})")
                                else:
                                    if i < 3:  # Show failures for first few rows
                                        print(f"❌ Failed to extract from row {i+1}")
                        except Exception as e:
                            print(f"Error processing row {i}: {e}")
                            continue
                else:
                    print("❌ No tbody found in table")
            else:
                print("❌ No futbin-table found, trying alternative approach...")
                
                # Fallback: Look for any player links on the page
                all_player_links = soup.find_all('a', href=lambda x: x and '/player/' in str(x))
                print(f"🔗 Found {len(all_player_links)} total player links on page")
                
                if len(all_player_links) == 0:
                    print("❌ CRITICAL: No player links found at all - Futbin structure has likely changed")
                    return []
                
                # Group by player URL to avoid duplicates
                unique_players = {}
                for link in all_player_links:
                    href = link.get('href', '')
                    if href not in unique_players:
                        unique_players[href] = {
                            'url': href,
                            'texts': [link.get_text(strip=True)]
                        }
                    else:
                        unique_players[href]['texts'].append(link.get_text(strip=True))
                
                print(f"🔗 Found {len(unique_players)} unique player URLs")
                
                # Convert to card format
                for url, data in unique_players.items():
                    try:
                        card_data = self.extract_card_from_link_data(url, data['texts'])
                        if card_data:
                            cards.append(card_data)
                    except Exception as e:
                        continue
            
            print(f"✅ Page {page_num}: Extracted {len(cards)} cards total")
            
            # Show sample of extracted cards
            for i, card in enumerate(cards[:3]):
                print(f"🃏 Card {i+1}: {card['name']} ({card['rating']}) - {card['futbin_id']}")
            
            return cards
            
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_card_from_row(self, row, player_links):
        """Extract card data from a table row"""
        try:
            # Get the main player link (usually the first one)
            main_link = player_links[0]
            href = main_link.get('href', '')
            
            # Extract player name from link text or nearby elements
            name = main_link.get_text(strip=True)
            if not name or len(name) < 2:
                # Try to find name in other cells
                name_cells = row.find_all('td')
                for cell in name_cells:
                    cell_text = cell.get_text(strip=True)
                    if cell_text and len(cell_text) > 2 and any(c.isalpha() for c in cell_text):
                        if not cell_text.isdigit():
                            name = cell_text
                            break
            
            # Extract rating - look for number between 40-99
            rating = 0
            all_text = row.get_text()
            import re
            rating_matches = re.findall(r'\b([4-9][0-9])\b', all_text)
            if rating_matches:
                rating = int(rating_matches[0])
            
            # Extract futbin ID from URL
            futbin_id = None
            if '/player/' in href:
                url_parts = href.split('/')
                if len(url_parts) >= 4:
                    futbin_id = url_parts[3]
            
            if name and rating > 0 and futbin_id:
                futbin_url = 'https://www.futbin.com' + href if href.startswith('/') else href
                
                return {
                    'name': name,
                    'rating': rating,
                    'position': '',
                    'club': '',
                    'nation': '',
                    'league': '',
                    'card_type': 'Gold' if rating >= 75 else 'Silver' if rating >= 65 else 'Bronze',
                    'futbin_url': futbin_url,
                    'futbin_id': futbin_id
                }
            
            return None
            
        except Exception as e:
            print(f"Error extracting from row: {e}")
            return None
    
    def extract_card_from_link_data(self, url, texts):
        """Extract card data from link URL and associated texts"""
        try:
            # Find the best name from texts
            name = ""
            rating = 0
            
            for text in texts:
                text = text.strip()
                if text:
                    # If it's a number and looks like a rating
                    if text.isdigit() and 40 <= int(text) <= 99:
                        rating = int(text)
                    # If it's text and longer than current name
                    elif len(text) > len(name) and any(c.isalpha() for c in text):
                        name = text
            
            # Extract futbin ID from URL
            futbin_id = None
            if '/player/' in url:
                url_parts = url.split('/')
                if len(url_parts) >= 4:
                    futbin_id = url_parts[3]
            
            if name and rating > 0 and futbin_id:
                futbin_url = 'https://www.futbin.com' + url if url.startswith('/') else url
                
                return {
                    'name': name,
                    'rating': rating,
                    'position': '',
                    'club': '',
                    'nation': '',
                    'league': '',
                    'card_type': 'Gold' if rating >= 75 else 'Silver' if rating >= 65 else 'Bronze',
                    'futbin_url': futbin_url,
                    'futbin_id': futbin_id
                }
            
            return None
            
        except Exception as e:
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
                
                # Progress notification every N pages (configurable) - but not too frequent
                if page % Config.PROGRESS_NOTIFICATION_INTERVAL == 0 and page > 0:
                    print(f"📊 Progress: {page}/{Config.PAGES_TO_SCRAPE} pages, {total_saved} cards saved")
                    # Only send notification every 50 pages to avoid spam
                    if page % 50 == 0:
                        self.send_notification_to_all(
                            f"📊 Scraping Progress: {page}/{Config.PAGES_TO_SCRAPE} pages complete\n"
                            f"💾 Total cards saved: {total_saved}",
                            "📊 Scraping Progress"
                        )
                
                # Random delay between pages (configurable)
                delay_min, delay_max = Config.get_scraping_delay_range()
                time.sleep(random.uniform(delay_min, delay_max))
                
            except Exception as e:
                print(f"❌ Error on page {page}: {e}")
                continue
        
        print(f"🎉 Scraping complete! Total cards saved: {total_saved}")
        self.send_notification_to_all(
            f"🎉 Futbin scraping complete!\n"
            f"📊 Pages scraped: {Config.PAGES_TO_SCRAPE}\n"
            f"💾 Total cards in database: {total_saved}\n"
            f"🤖 Price monitoring will start now!",
            "✅ Scraping Complete"
        )
        
        return total_saved
    
    def scrape_card_prices(self, futbin_url):
        """
        Scrape current BIN prices from a card's individual Futbin page
        Target ONLY the first and second lowest BIN prices
        """
        try:
            self.rotate_user_agent()
            response = self.session.get(futbin_url)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            prices = {'ps': [], 'xbox': [], 'pc': []}
            
            print(f"💰 Extracting BIN prices from: {futbin_url}")
            
            # Get EXACTLY the first and second lowest prices
            bin_prices = []
            
            # First BIN price: class="price inline-with-icon lowest-price-1"
            first_price_elem = soup.find(class_="price inline-with-icon lowest-price-1")
            if first_price_elem:
                try:
                    first_price_text = first_price_elem.get_text(strip=True)
                    first_price = self.parse_price_text(first_price_text)
                    if first_price > 0:
                        bin_prices.append(first_price)
                        print(f"💰 First BIN: {first_price:,} coins")
                except Exception as e:
                    print(f"Error parsing first price: {e}")
            
            # Second BIN price: Find ONLY the first occurrence of "lowest-price inline-with-icon"
            second_price_elements = soup.find_all(class_="lowest-price inline-with-icon")
            if second_price_elements and len(second_price_elements) > 0:
                try:
                    # Take only the FIRST element (second lowest price)
                    second_price_elem = second_price_elements[0]
                    second_price_text = second_price_elem.get_text(strip=True)
                    second_price = self.parse_price_text(second_price_text)
                    if second_price > 0 and second_price != first_price:
                        bin_prices.append(second_price)
                        print(f"💰 Second BIN: {second_price:,} coins")
                except Exception as e:
                    print(f"Error parsing second price: {e}")
            
            # ONLY use the first two prices - ignore 3rd, 4th, etc.
            if len(bin_prices) >= 2:
                # Sort to ensure first is lowest, second is second lowest
                bin_prices = sorted(bin_prices[:2])
                print(f"💰 Final BIN prices: {bin_prices[0]:,} → {bin_prices[1]:,}")
                prices['ps'] = bin_prices
                return prices
            else:
                print(f"❌ Found only {len(bin_prices)} valid prices, need at least 2")
                return None
            
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
    
    def send_discord_general_notification(self, message, title="Futbin Price Monitor"):
        """Send general Discord notification (non-trading alerts)"""
        if not Config.DISCORD_WEBHOOK_URL:
            return  # Discord not configured
        
        # Simple embed for general notifications
        embed = {
            "title": title,
            "description": message,
            "color": 0x0099ff,  # Blue color
            "timestamp": datetime.now().isoformat()
        }
        
        payload = {
            "embeds": [embed]
        }
        
        try:
            response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("✅ Discord notification sent")
            else:
                print(f"❌ Discord error: {response.status_code}")
        except Exception as e:
            print(f"❌ Discord error: {e}")
    
    def send_notification_to_all(self, message, title="Futbin Price Monitor"):
        """Send notification to both Telegram and Discord"""
        # Send to Telegram
        self.send_telegram_notification(message)
        
        # Send to Discord
        self.send_discord_general_notification(message, title)
    
    def send_price_alert(self, card_info, platform, gap_info):
        """Send price gap alert with proper trading calculations"""
        
        # First, check if we should send this alert (prevent duplicates)
        alert_saved = self.save_price_alert(card_info['id'], platform, gap_info)
        if not alert_saved:
            return  # Skip if duplicate
        
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
        
        # Telegram message
        telegram_message = f"""
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
        
        # Send to Telegram
        self.send_telegram_notification(telegram_message.strip())
        
        # Send to Discord if enabled
        self.send_discord_notification(card_info, platform, gap_info, profit_margin, profit_quality)
        
        print(f"🚨 TRADING ALERT: {card_info['name']} ({platform}) - Buy {gap_info['buy_price']:,}, Sell {gap_info['sell_price']:,}, Profit {gap_info['profit_after_tax']:,}")
        
    def send_discord_notification(self, card_info, platform, gap_info, profit_margin, profit_quality):
        """Send Discord webhook notification"""
        if not Config.DISCORD_WEBHOOK_URL:
            return  # Discord not configured
        
        # Determine profit quality emoji and color
        if profit_margin >= 20:
            profit_emoji = "🤑"
            color = 0x00ff00  # Green
        elif profit_margin >= 10:
            profit_emoji = "💰"
            color = 0xffaa00  # Orange
        else:
            profit_emoji = "💡"
            color = 0x0099ff  # Blue
        
        # Clean, simple Discord embed
        embed = {
            "title": f"{profit_emoji} {card_info['name']} - {profit_quality} OPPORTUNITY",
            "description": f"**Rating {card_info['rating']} | {card_info['position']} | {platform.upper()}**",
            "color": color,
            "fields": [
                {
                    "name": "💰 Buy Price",
                    "value": f"{gap_info['buy_price']:,}",
                    "inline": True
                },
                {
                    "name": "🏷️ Sell Price", 
                    "value": f"{gap_info['sell_price']:,}",
                    "inline": True
                },
                {
                    "name": "🎯 Profit",
                    "value": f"**{gap_info['profit_after_tax']:,}** ({profit_margin:.1f}%)",
                    "inline": True
                }
            ],
            "url": card_info['futbin_url'],
            "thumbnail": {
                "url": card_info['futbin_url']
            },
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": f"EA Tax: {gap_info['ea_tax']:,} | After Tax: {gap_info['sell_price_after_tax']:,}"
            }
        }
        
        payload = {
            "embeds": [embed]
        }
        
        try:
            response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("✅ Discord notification sent")
            else:
                print(f"❌ Discord error: {response.status_code}")
        except Exception as e:
            print(f"❌ Discord error: {e}")
    
    def save_price_alert(self, card_id, platform, gap_info):
        """Save price alert to database and prevent duplicates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if we already sent an alert for this card/platform recently
        cooldown_time = datetime.now() - timedelta(minutes=Config.ALERT_COOLDOWN_MINUTES)
        cursor.execute('''
            SELECT COUNT(*) FROM price_alerts 
            WHERE card_id = ? AND platform = ? AND alert_sent_at > ?
        ''', (card_id, platform, cooldown_time))
        
        recent_alerts = cursor.fetchone()[0]
        
        if recent_alerts > 0:
            print(f"⚠️ Alert already sent for card {card_id} ({platform}) in the last {Config.ALERT_COOLDOWN_MINUTES} minutes, skipping...")
            conn.close()
            return False
        
        # Save new alert
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
        return True
    
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
        """Main monitoring loop - respecting Cloudflare delays"""
        print("🤖 Starting price monitoring with proper anti-detection delays...")
        
        while True:
            try:
                cards = self.get_cards_to_monitor(100)  # Back to 100 cards per cycle
                if not cards:
                    print("❌ No cards in database! This shouldn't happen after scraping.")
                    # If database is empty, do a quick re-scrape
                    print("🔄 Re-scraping essential cards...")
                    self.scrape_all_cards()
                    continue
                
                print(f"📊 Monitoring {len(cards)} cards for price gaps...")
                print("⏱️ Using proper delays to avoid Cloudflare detection...")
                
                alerts_sent = 0
                for i, card in enumerate(cards):
                    try:
                        prices = self.scrape_card_prices(card['futbin_url'])
                        
                        if prices:
                            for platform, price_list in prices.items():
                                if len(price_list) >= 2:
                                    gap_info = self.analyze_price_gap(price_list)
                                    if gap_info:
                                        self.send_price_alert(card, platform, gap_info)
                                        alerts_sent += 1
                        
                        # Progress update every 25 cards (original frequency)
                        if (i + 1) % 25 == 0:
                            print(f"✅ Checked {i + 1}/{len(cards)} cards... Alerts sent: {alerts_sent}")
                        
                        # IMPORTANT: Original delay range (4-8 seconds) for price monitoring
                        time.sleep(random.uniform(4, 8))
                        
                    except Exception as e:
                        print(f"Error monitoring {card['name']}: {e}")
                        continue
                
                # Send cycle completion notification
                if Config.SEND_CYCLE_SUMMARIES and alerts_sent > 0:
                    self.send_notification_to_all(
                        f"📊 Monitoring cycle complete!\n"
                        f"🔍 Checked {len(cards)} cards\n"
                        f"🚨 Sent {alerts_sent} trading alerts\n"
                        f"⏰ Next check in {Config.MONITORING_CYCLE_INTERVAL} minutes",
                        "📊 Cycle Complete"
                    )
                else:
                    print(f"📊 Cycle complete - no trading opportunities found this round")
                
                print(f"💤 Cycle complete. Sent {alerts_sent} alerts. Waiting 45 minutes for next check...")
                time.sleep(2700)  # Back to 45 minutes (original timing)
                
            except KeyboardInterrupt:
                print("🛑 Monitoring stopped!")
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(300)  # 5 minutes on error
    
    def run_complete_system(self):
        """Run the complete system: scrape cards, then monitor prices"""
        print("🚀 Starting complete Futbin Price Gap Monitor system!")
        print("⚠️ Running on free tier - database will reset on restart")
        
        # Send startup notification first
        self.check_and_send_startup_notification()
        
        # Check current database state
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cards')
        card_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"📊 Current cards in database: {card_count}")
        
        # On free tier, we'll always start fresh, so reduce scraping pages for faster startup
        if card_count == 0:
            print("🚀 Database is empty - starting fresh scraping session")
            print(f"📄 Will scrape {Config.PAGES_TO_SCRAPE} pages for quick startup")
            
            self.scrape_all_cards()
        else:
            print(f"✅ Found {card_count} cards in database. Starting monitoring...")
        
        # Start price monitoring immediately after scraping
        print("🎯 Starting price monitoring for trading opportunities...")
        self.run_price_monitoring()

# Entry point for running the monitor
if __name__ == "__main__":
    # Run the complete system
    monitor = FutbinPriceMonitor()
    monitor.run_complete_system()
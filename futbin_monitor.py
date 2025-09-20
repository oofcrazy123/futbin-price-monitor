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
                f"📊 Scraping {getattr(Config, 'PAGES_TO_SCRAPE', 50)} pages\n"
                f"⚡ Running on cloud infrastructure\n"
                f"💰 Alert thresholds: {getattr(Config, 'MINIMUM_PRICE_GAP_COINS', 5000):,} coins, {getattr(Config, 'MINIMUM_PRICE_GAP_PERCENTAGE', 10)}%\n"
                f"⏰ Alert cooldown: {getattr(Config, 'ALERT_COOLDOWN_MINUTES', 30)} minutes\n"
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
        """Scrape cards from a Futbin players page - Updated for current structure"""
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
            return cards
            
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_player_name_from_url(self, futbin_url):
    """Extract player name from Futbin URL when database name is unreliable"""
    try:
        if not futbin_url:
            return None
        
        # Split URL and get the last part which contains the player name
        url_parts = futbin_url.split('/')
        if len(url_parts) < 2:
            return None
        
        # Get the last segment (player name)
        name_segment = url_parts[-1]
        
        # Remove any query parameters
        if '?' in name_segment:
            name_segment = name_segment.split('?')[0]
        
        # Replace hyphens and underscores with spaces
        clean_name = name_segment.replace('-', ' ').replace('_', ' ')
        
        # Capitalize each word properly
        formatted_name = ' '.join(word.capitalize() for word in clean_name.split())
        
        # Basic validation - should be more than just numbers
        if formatted_name and not formatted_name.isdigit() and len(formatted_name) > 2:
            return formatted_name
        
        return None
        
    except Exception as e:
        print(f"Error extracting name from URL {futbin_url}: {e}")
        return None
    
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
        """Scrape cards from all pages"""
        pages_to_scrape = getattr(Config, 'PAGES_TO_SCRAPE', 50)
        print(f"🚀 Starting to scrape {pages_to_scrape} pages...")
        
        total_saved = 0
        
        for page in range(1, pages_to_scrape + 1):
            try:
                print(f"📄 Scraping page {page}/{pages_to_scrape}...")
                
                cards = self.scrape_futbin_cards_list(page)
                if cards:
                    saved = self.save_cards_to_db(cards)
                    total_saved += saved
                    print(f"✅ Page {page}: Found {len(cards)} cards, saved {saved} new cards")
                else:
                    print(f"⚠️ Page {page}: No cards found")
                
                # Random delay between pages
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                print(f"❌ Error on page {page}: {e}")
                continue
        
        print(f"🎉 Scraping complete! Total cards saved: {total_saved}")
        self.send_notification_to_all(
            f"🎉 Futbin scraping complete!\n"
            f"📊 Pages scraped: {pages_to_scrape}\n"
            f"💾 Total cards in database: {total_saved}\n"
            f"🤖 Price monitoring will start now!",
            "✅ Scraping Complete"
        )
        
        return total_saved
    
    def scrape_card_prices(self, futbin_url):
        """Scrape current BIN prices from a card's individual Futbin page"""
        try:
            self.rotate_user_agent()
            response = self.session.get(futbin_url)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            prices = {'ps': [], 'xbox': [], 'pc': []}
            
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
                except Exception as e:
                    print(f"Error parsing second price: {e}")
            
            # ONLY use the first two prices - ignore 3rd, 4th, etc.
            if len(bin_prices) >= 2:
                # Sort to ensure first is lowest, second is second lowest
                bin_prices = sorted(bin_prices[:2])
                prices['ps'] = bin_prices
                return prices
            else:
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
    def analyze_price_gap(self, prices_list, card_id=None):
        """Analyze price gap between first and second lowest prices"""
        if len(prices_list) < 2:
            return None
        
        # Sort to ensure we have lowest prices first
        sorted_prices = sorted(prices_list)
        buy_price = sorted_prices[0]  # First (lowest) price - what we buy for
        sell_price = sorted_prices[1]  # Second price - what we sell for
        
        # Basic validation
        if buy_price <= 0 or sell_price <= 0 or sell_price <= buy_price:
            return None
        
        min_card_price = getattr(Config, 'MINIMUM_CARD_PRICE', 1000)
        if buy_price < min_card_price:
            return None
        
        # Calculate EA tax (5% on all sales)
        ea_tax = sell_price * 0.05
        sell_price_after_tax = sell_price - ea_tax
        
        # Calculate actual profit
        profit_after_tax = sell_price_after_tax - buy_price
        
        # Only alert if there's actual meaningful profit after tax
        min_gap_coins = getattr(Config, 'MINIMUM_PRICE_GAP_COINS', 5000)
        if profit_after_tax < min_gap_coins:
            return None
        
        # Calculate percentage profit (based on buy price)
        percentage_profit = (profit_after_tax / buy_price) * 100
        
        min_gap_percentage = getattr(Config, 'MINIMUM_PRICE_GAP_PERCENTAGE', 10)
        if percentage_profit < min_gap_percentage:
            return None
        
        return {
            'buy_price': buy_price,
            'sell_price': sell_price,
            'sell_price_after_tax': int(sell_price_after_tax),
            'raw_profit': sell_price - buy_price,
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
    
    def get_player_image_from_url(self, futbin_url):
        """Extract the og:image from Futbin page - same image Telegram shows"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(futbin_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for og:image meta tag (this is what Telegram uses)
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    return og_image['content']
                
                # Fallback: look for player image in the page
                player_img = soup.find('img', {'class': 'player-img'}) or \
                           soup.find('img', {'id': 'player-img'}) or \
                           soup.find('img', src=lambda x: x and 'players' in x)
                
                if player_img and player_img.get('src'):
                    img_src = player_img['src']
                    # Convert relative URL to absolute
                    if img_src.startswith('//'):
                        return f"https:{img_src}"
                    elif img_src.startswith('/'):
                        return f"https://www.futbin.com{img_src}"
                    else:
                        return img_src
                        
        except Exception as e:
            print(f"❌ Error extracting player image: {e}")
        
        return None
    
    def send_discord_notification(self, card_info, platform, gap_info, profit_margin, profit_quality):
        """Send Discord notification with proper player name and same image as Telegram"""
        if not Config.DISCORD_WEBHOOK_URL:
            return  # Discord not configured
        
        # Color based on profit margin
        if profit_margin >= 30:
            color = 0xff4500  # Red-orange
        elif profit_margin >= 20:
            color = 0x00ff00  # Green
        elif profit_margin >= 10:
            color = 0xffa500  # Orange
        else:
            color = 0x0099ff  # Blue
        
        # Get the same player image that Telegram shows
        thumbnail_url = None
        if 'futbin_url' in card_info and card_info['futbin_url']:
            thumbnail_url = self.get_player_image_from_url(card_info['futbin_url'])
            
            # Fallback to direct CDN URL if og:image extraction fails
            if not thumbnail_url:
                url_parts = card_info['futbin_url'].split('/')
                if len(url_parts) >= 6:
                    try:
                        futbin_id = url_parts[5]
                        thumbnail_url = f"https://cdn3.futbin.com/content/fifa26/img/players/{futbin_id}.png?fm=png&ixlib=java-2.1.0&w=324&s=09330e054dcaf6ca1595f92fee17894a"
                    except:
                        pass
        
        # Title exactly like the image
        title = "FutBin Error Found 🔍"
        
        # Try to get name from database first, then extract from URL if needed
        player_name = card_info.get('name', '')
        if not player_name or player_name.isdigit() or len(player_name) < 3:
            # Database name is unreliable, extract from URL
            extracted_name = self.extract_player_name_from_url(card_info.get('futbin_url'))
            player_name = extracted_name if extracted_name else 'Unknown Player'
        
        # Description with exact format from image - using PLAYER NAME not rating
        description = f"""**Player**
{player_name}
**Platform**
{platform.title()}
**Market Price**
{gap_info['sell_price']:,}
**Buy Price**
{gap_info['buy_price']:,}
**Profit (Untaxed)**
{gap_info['raw_profit']:,}
**Profit (-5%)**
{gap_info['profit_after_tax']:,}
**Link**
[FutBin]({card_info['futbin_url']})"""
        
        # Clean embed that matches the format
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "url": card_info['futbin_url']
        }
        
        # Add the same player image that Telegram shows
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
            print(f"🖼️ Using player image: {thumbnail_url}")
        else:
            print("⚠️ No player image found")
        
        payload = {
            "embeds": [embed]
        }
        
        try:
            response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print(f"✅ Discord notification sent for {player_name}")
            else:
                print(f"❌ Discord error: {response.status_code}")
        except Exception as e:
            print(f"❌ Discord error: {e}")
    
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
    
    def save_price_alert(self, card_id, platform, gap_info):
        """Save price alert to database and prevent duplicates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if we already sent an alert for this card/platform recently
        cooldown_minutes = getattr(Config, 'ALERT_COOLDOWN_MINUTES', 30)
        cooldown_time = datetime.now() - timedelta(minutes=cooldown_minutes)
        cursor.execute('''
            SELECT COUNT(*) FROM price_alerts 
            WHERE card_id = ? AND platform = ? AND alert_sent_at > ?
        ''', (card_id, platform, cooldown_time))
        
        recent_alerts = cursor.fetchone()[0]
        
        if recent_alerts > 0:
            print(f"⚠️ Alert already sent for card {card_id} ({platform}) in the last {cooldown_minutes} minutes, skipping...")
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
    
    def get_cards_to_monitor(self, limit=1000):
        """Get cards from database to monitor for price gaps - focuses on viable trading cards"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get a balanced mix of cards across viable rating ranges
        cards = []
        
        # 1. High-rated cards (85+) - 20% of monitoring
        high_rated_limit = int(limit * 0.20)
        cursor.execute('''
            SELECT id, name, rating, position, club, nation, league, futbin_url
            FROM cards 
            WHERE rating >= 85 
            ORDER BY rating DESC, RANDOM()
            LIMIT ?
        ''', (high_rated_limit,))
        
        for row in cursor.fetchall():
            cards.append({
                'id': row[0], 'name': row[1], 'rating': row[2], 'position': row[3],
                'club': row[4], 'nation': row[5], 'league': row[6], 'futbin_url': row[7]
            })
        
        # 2. Mid-rated cards (75-84) - 50% of monitoring
        mid_rated_limit = int(limit * 0.50)
        cursor.execute('''
            SELECT id, name, rating, position, club, nation, league, futbin_url
            FROM cards 
            WHERE rating >= 75 AND rating < 85
            ORDER BY RANDOM()
            LIMIT ?
        ''', (mid_rated_limit,))
        
        for row in cursor.fetchall():
            cards.append({
                'id': row[0], 'name': row[1], 'rating': row[2], 'position': row[3],
                'club': row[4], 'nation': row[5], 'league': row[6], 'futbin_url': row[7]
            })
        
        # 3. Budget cards (65-74) - 25% of monitoring  
        budget_limit = int(limit * 0.25)
        cursor.execute('''
            SELECT id, name, rating, position, club, nation, league, futbin_url
            FROM cards 
            WHERE rating >= 65 AND rating < 75
            ORDER BY RANDOM()
            LIMIT ?
        ''', (budget_limit,))
        
        for row in cursor.fetchall():
            cards.append({
                'id': row[0], 'name': row[1], 'rating': row[2], 'position': row[3],
                'club': row[4], 'nation': row[5], 'league': row[6], 'futbin_url': row[7]
            })
        
        # 4. Special consideration for very high-rated cards (90+) - 5% of monitoring
        special_limit = int(limit * 0.05)
        cursor.execute('''
            SELECT id, name, rating, position, club, nation, league, futbin_url
            FROM cards 
            WHERE rating >= 90
            ORDER BY rating DESC, RANDOM()
            LIMIT ?
        ''', (special_limit,))
        
        for row in cursor.fetchall():
            cards.append({
                'id': row[0], 'name': row[1], 'rating': row[2], 'position': row[3],
                'club': row[4], 'nation': row[5], 'league': row[6], 'futbin_url': row[7]
            })
        
        conn.close()
        
        # Shuffle the final list to mix different rating ranges
        random.shuffle(cards)
        
        print(f"📊 Monitoring mix: {high_rated_limit} high-rated (85+), {mid_rated_limit} mid-rated (75-84), {budget_limit} budget (65-74), {special_limit} elite (90+) cards")
        
        return cards
    
    def run_price_monitoring(self):
        """Main monitoring loop - respecting Cloudflare delays"""
        print("🤖 Starting price monitoring with proper anti-detection delays...")
        
        while True:
            try:
                cards = self.get_cards_to_monitor(100)  # Monitor 100 cards per cycle
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
                                    gap_info = self.analyze_price_gap(price_list, card['id'])
                                    
                                    if gap_info:
                                        self.send_price_alert(card, platform, gap_info)
                                        alerts_sent += 1
                        
                        # Progress update every 25 cards
                        if (i + 1) % 25 == 0:
                            print(f"✅ Checked {i + 1}/{len(cards)} cards... Alerts sent: {alerts_sent}")
                        
                        # IMPORTANT: Delay range (4-8 seconds) for price monitoring
                        time.sleep(random.uniform(4, 8))
                        
                    except Exception as e:
                        print(f"Error monitoring {card['name']}: {e}")
                        continue
                
                # Send cycle completion notification
                send_summaries = getattr(Config, 'SEND_CYCLE_SUMMARIES', False)
                if send_summaries and alerts_sent > 0:
                    self.send_notification_to_all(
                        f"📊 Monitoring cycle complete!\n"
                        f"🔍 Checked {len(cards)} cards\n"
                        f"🚨 Sent {alerts_sent} trading alerts\n"
                        f"⏰ Next check in 45 minutes",
                        "📊 Cycle Complete"
                    )
                else:
                    print(f"📊 Cycle complete - no trading opportunities found this round")
                
                print(f"💤 Cycle complete. Sent {alerts_sent} alerts. Waiting 45 minutes for next check...")
                time.sleep(2700)  # 45 minutes
                
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
        
        # Check if scraping should be skipped
        skip_scraping = getattr(Config, 'SKIP_SCRAPING', False)
        if skip_scraping:
            print("⚠️ SKIP_SCRAPING enabled - bypassing scraping phase")
            if card_count == 0:
                print("❌ WARNING: Database is empty but scraping is disabled!")
                self.send_notification_to_all(
                    "⚠️ Database is empty but scraping is disabled!\n"
                    "Remove SKIP_SCRAPING environment variable to enable scraping.",
                    "❌ Configuration Warning"
                )
            else:
                print(f"✅ Using existing {card_count:,} cards in database")
                self.send_notification_to_all(
                    f"✅ Using existing database with {card_count:,} cards\n"
                    f"🤖 Starting price monitoring immediately!",
                    "📊 Monitoring Started"
                )
        elif card_count == 0:
            print("🚀 Database is empty - starting fresh scraping session")
            pages_to_scrape = getattr(Config, 'PAGES_TO_SCRAPE', 50)
            print(f"📄 Will scrape {pages_to_scrape} pages for quick startup")
            
            self.scrape_all_cards()
        elif card_count < 1000:
            print(f"⚠️ Database has only {card_count} cards - may want to scrape more")
            self.send_notification_to_all(
                f"⚠️ Database has only {card_count:,} cards\n"
                f"🤖 Starting monitoring with existing data\n"
                f"💡 Consider re-scraping for more comprehensive coverage",
                "📊 Monitoring Started"
            )
        else:
            print(f"✅ Found {card_count:,} cards in database. Starting monitoring...")
            self.send_notification_to_all(
                f"✅ Database loaded with {card_count:,} cards\n"
                f"🤖 Starting price monitoring for trading opportunities!",
                "📊 Monitoring Started"
            )
        
        # Start price monitoring immediately after scraping
        print("🎯 Starting price monitoring for trading opportunities...")
        self.run_price_monitoring()


# Entry point for running the monitor
if __name__ == "__main__":
    try:
        print("🚀 Initializing Futbin Price Monitor...")
        # Run the complete system
        monitor = FutbinPriceMonitor()
        monitor.run_complete_system()
    except KeyboardInterrupt:
        print("\n🛑 Monitor stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        

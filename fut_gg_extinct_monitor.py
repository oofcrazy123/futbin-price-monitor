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

class FutGGExtinctMonitor:
    def __init__(self, db_path="fut_extinct_cards.db"):
        # Validate configuration on startup
        Config.validate_config()
        
        # For cloud deployment, try to use a persistent path
        if os.getenv('RENDER_EXTERNAL_HOSTNAME'):
            db_path = "/opt/render/project/src/fut_extinct_cards.db"
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
            self.db_path = "/tmp/fut_extinct_cards.db"
            print(f"📄 Using fallback database path: {self.db_path}")
        
        self.session = requests.Session()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        self.init_database()
        self.startup_sent = False
    
    def rotate_user_agent(self):
        """Rotate user agent to avoid detection"""
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents)
        })
    
    def init_database(self):
        """Initialize SQLite database for extinct card monitoring"""
        print(f"🔧 Initializing database at: {self.db_path}")
        
        try:
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
                    fut_gg_url TEXT UNIQUE,
                    fut_gg_id TEXT,
                    last_check TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS extinct_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER,
                    platform TEXT,
                    extinct_status BOOLEAN DEFAULT 1,
                    alert_sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP NULL,
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS card_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER,
                    status_type TEXT,
                    status_value TEXT,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (card_id) REFERENCES cards (id)
                )
            ''')
            
            conn.commit()
            
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
        """Send startup notification only once per deployment"""
        if self.startup_sent:
            return
        
        import uuid
        instance_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO startup_locks (instance_id, startup_time)
                VALUES (?, ?)
            ''', (instance_id, datetime.now()))
            
            conn.commit()
            
            print(f"✅ Startup lock acquired: {instance_id}")
            
            self.send_notification_to_all(
                f"🤖 FUT.GG Extinct Monitor Started!\n"
                f"🔍 Using HTML scraping to monitor extinct players\n"
                f"⚡ Running on cloud infrastructure\n"
                f"⏰ Check interval: 5-10 minutes\n"
                f"🔒 Instance: {instance_id[:12]}",
                "🚀 Extinct Monitor Started"
            )
            
            self.startup_sent = True
            print("✅ Startup notification sent")
            
        except sqlite3.IntegrityError:
            print(f"⚠️ Another instance already started")
            self.startup_sent = True
        except Exception as e:
            print(f"Error with startup notification: {e}")
            self.startup_sent = True
        finally:
            try:
                conn.close()
            except:
                pass
    
    def scrape_fut_gg_players(self, page_num=1):
        """
        Scrape players from fut.gg players page using HTML parsing
        """
        try:
            self.rotate_user_agent()
            
            url = f'https://www.fut.gg/players/?page={page_num}'
            print(f"🌐 Scraping HTML page: {url}")
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Failed to get page {page_num}: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            cards = []
            
            # Look for player links
            player_links = soup.find_all('a', href=lambda x: x and '/players/' in str(x))
            
            print(f"🔗 Found {len(player_links)} player links on page {page_num}")
            
            if len(player_links) == 0:
                print("⚠️ WARNING: No player links found - website structure may have changed")
                return []
            
            # Extract unique players
            unique_players = {}
            for link in player_links:
                href = link.get('href', '')
                if href not in unique_players:
                    card_data = self.extract_player_data_from_link(link, soup)
                    if card_data:
                        unique_players[href] = card_data
            
            cards = list(unique_players.values())
            
            print(f"✅ HTML Scraping page {page_num}: Extracted {len(cards)} unique cards")
            
            return cards
            
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            return []
    
    def find_extinct_boundary(self):
        """
        Dynamically find where extinct players end in the price-sorted list
        Returns: (last_extinct_page, estimated_total_extinct_players)
        """
        print("🔍 Finding current extinct zone boundary...")
        
        # Start checking from a reasonable page (around where extinctions usually end)
        test_pages = [35, 40, 45, 50, 30, 25, 20]  # Start middle, then expand search
        last_extinct_page = 0
        
        for page in test_pages:
            try:
                print(f"🧪 Testing page {page} for extinct players...")
                cards = self.scrape_fut_gg_players_sorted(page)
                
                if not cards:
                    continue
                
                extinct_count = sum(1 for card in cards if card.get('appears_extinct', False))
                print(f"📊 Page {page}: {extinct_count}/{len(cards)} players extinct")
                
                if extinct_count > 0:
                    # Found extinct players, this page is in the zone
                    if page > last_extinct_page:
                        last_extinct_page = page
                
                time.sleep(random.uniform(1, 2))  # Be respectful
                
            except Exception as e:
                print(f"⚠️ Error testing page {page}: {e}")
                continue
        
        # Now do a more precise search around the boundary we found
        if last_extinct_page > 0:
            # Check a few pages after our highest extinct page to find exact boundary
            for page in range(last_extinct_page + 1, min(last_extinct_page + 10, 60)):
                try:
                    cards = self.scrape_fut_gg_players_sorted(page)
                    if not cards:
                        break
                        
                    extinct_count = sum(1 for card in cards if card.get('appears_extinct', False))
                    
                    if extinct_count > 0:
                        last_extinct_page = page
                    else:
                        # No extinct players on this page, we've found the boundary
                        break
                    
                    time.sleep(random.uniform(0.5, 1))
                    
                except Exception as e:
                    print(f"⚠️ Error in boundary search page {page}: {e}")
                    break
        
        # Estimate total extinct players (assuming ~20-40 per page)
        estimated_total = last_extinct_page * 30  # Conservative estimate
        
        print(f"🎯 Extinct zone boundary found!")
        print(f"📍 Last page with extinct players: {last_extinct_page}")
        print(f"📊 Estimated total extinct players: ~{estimated_total}")
        
        return last_extinct_page, estimated_total
    
    def scrape_fut_gg_players_sorted(self, page=1):
        """
        Scrape players from fut.gg sorted by current price (extinct first)
        """
        url = f"https://www.fut.gg/players/?page={page}&sorts=current_price"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for player cards - fut.gg uses specific structure
            # Try multiple selectors to find the player cards
            player_containers = (
                soup.find_all('div', class_=lambda x: x and 'player' in x.lower()) or
                soup.find_all('a', href=lambda x: x and '/players/' in x) or
                soup.find_all('div', class_=lambda x: x and any(term in x.lower() for term in ['card', 'item', 'grid']))
            )
            
            cards = []
            for container in player_containers:
                try:
                    # Extract player information
                    name_element = (
                        container.find('h3') or 
                        container.find('h2') or
                        container.find(text=lambda x: x and len(x.strip()) > 2 and x.strip().replace(' ', '').isalpha())
                    )
                    
                    name = name_element.strip() if isinstance(name_element, str) else (
                        name_element.text.strip() if name_element else 'Unknown'
                    )
                    
                    # Check for extinct status - look for "EXTINCT" text
                    container_html = str(container)
                    is_extinct = (
                        'EXTINCT' in container_html or 
                        container.find(text=lambda x: x and 'EXTINCT' in x.upper()) is not None
                    )
                    
                    # Try to find price element to double-check extinct status
                    price_element = container.find(class_=lambda x: x and any(term in x.lower() for term in ['price', 'cost', 'coin']))
                    if price_element and 'EXTINCT' in price_element.text.upper():
                        is_extinct = True
                    
                    # Extract other details with flexible selectors
                    rating = self.extract_rating_flexible(container)
                    position = self.extract_position_flexible(container)
                    club = self.extract_club_flexible(container)
                    nation = self.extract_nation_flexible(container)
                    league = self.extract_league_flexible(container)
                    
                    # Get player URL
                    link_element = container.find('a', href=True) or container if container.name == 'a' else None
                    player_url = ""
                    if link_element:
                        href = link_element.get('href', '')
                        if href.startswith('/'):
                            player_url = f"https://www.fut.gg{href}"
                        elif href.startswith('http'):
                            player_url = href
                    
                    # Only add if we have at least a name
                    if name and name != 'Unknown' and len(name) > 1:
                        card_data = {
                            'name': name,
                            'rating': rating,
                            'position': position,
                            'club': club,
                            'nation': nation,
                            'league': league,
                            'fut_gg_url': player_url,
                            'appears_extinct': is_extinct,
                            'fut_gg_id': self.extract_fut_gg_id(player_url)
                        }
                        
                        cards.append(card_data)
                    
                except Exception as e:
                    continue  # Skip problematic cards
            
            extinct_count = sum(1 for c in cards if c.get('appears_extinct', False))
            print(f"📄 Page {page}: Found {len(cards)} cards, {extinct_count} appear extinct")
            return cards
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error scraping page {page}: {e}")
            return []
        except Exception as e:
            print(f"❌ Error scraping page {page}: {e}")
            return []
        
    def extract_player_data_from_link(self, link, soup):
        """Extract player data from a link element using HTML parsing"""
        try:
            href = link.get('href', '')
            
            # Find the card container that holds this link
            card_container = link.find_parent(['div', 'article', 'section'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['card', 'player', 'item']
            ))
            
            if not card_container:
                card_container = link.find_parent(['div', 'li'])
            
            # Extract name from link text or nearby elements
            name = link.get_text(strip=True)
            if not name or len(name) < 2:
                # Try to find name in the container
                name_elem = card_container.find(['h1', 'h2', 'h3', 'h4', 'span'], 
                                               string=lambda x: x and len(str(x).strip()) > 2)
                if name_elem:
                    name = name_elem.get_text(strip=True)
            
            # Extract rating using regex
            rating = 0
            if card_container:
                rating_text = card_container.get_text()
                import re
                rating_matches = re.findall(r'\b([4-9][0-9])\b', rating_text)
                if rating_matches:
                    rating = int(rating_matches[0])
            
            # Extract fut.gg ID from URL
            fut_gg_id = None
            if '/players/' in href:
                url_parts = href.split('/')
                for i, part in enumerate(url_parts):
                    if part == 'players' and i + 1 < len(url_parts):
                        fut_gg_id = url_parts[i + 1].split('?')[0]  # Remove query parameters
                        break
            
            if name and rating > 0 and fut_gg_id:
                fut_gg_url = 'https://www.fut.gg' + href if href.startswith('/') else href
                
                return {
                    'name': name,
                    'rating': rating,
                    'position': '',
                    'club': '',
                    'nation': '',
                    'league': '',
                    'card_type': 'Gold' if rating >= 75 else 'Silver' if rating >= 65 else 'Bronze',
                    'fut_gg_url': fut_gg_url,
                    'fut_gg_id': fut_gg_id
                }
            
            return None
            
        except Exception as e:
            print(f"Error extracting player data: {e}")
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
                    (name, rating, position, club, nation, league, card_type, fut_gg_url, fut_gg_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    card['name'], card['rating'], card['position'], card['club'],
                    card['nation'], card['league'], card['card_type'], 
                    card['fut_gg_url'], card['fut_gg_id']
                ))
                if cursor.rowcount > 0:
                    saved_count += 1
            except Exception as e:
                print(f"Error saving card {card['name']}: {e}")
        
        conn.commit()
        conn.close()
        return saved_count
    
    def scrape_all_players(self, max_pages=10):
        """Scrape players from multiple pages using HTML parsing"""
        print(f"🚀 Starting HTML scraping of {max_pages} pages...")
        
        total_saved = 0
        
        for page in range(1, max_pages + 1):
            try:
                print(f"📄 HTML scraping page {page}/{max_pages}...")
                
                cards = self.scrape_fut_gg_players(page)
                if cards:
                    saved = self.save_cards_to_db(cards)
                    total_saved += saved
                    print(f"✅ Page {page}: Found {len(cards)} cards, saved {saved} new cards")
                else:
                    print(f"⚠️ Page {page}: No cards found")
                    if page > 1:
                        break
                
                # Delay between pages to avoid detection
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                print(f"❌ Error on page {page}: {e}")
                continue
        
        print(f"🎉 HTML scraping complete! Total cards saved: {total_saved}")
        self.send_notification_to_all(
            f"🎉 HTML scraping complete!\n"
            f"📊 Pages scraped: {max_pages}\n"
            f"💾 Total cards in database: {total_saved}\n"
            f"🤖 Starting extinct monitoring!",
            "✅ Scraping Complete"
        )
        
    def scrape_price_sorted_pages(self, max_pages=5):
        """
        Scrape the price-sorted pages where extinct players appear first
        """
        print(f"🚀 Scraping price-sorted pages for extinct players...")
        
        total_extinct_found = 0
        total_saved = 0
        
        for page in range(1, max_pages + 1):
            try:
                self.rotate_user_agent()
                
                url = f'https://www.fut.gg/players/?page={page}&sorts=current_price'
                print(f"🌐 Scraping price-sorted page: {url}")
                response = self.session.get(url, timeout=30)
                
                if response.status_code != 200:
                    print(f"❌ Failed to get sorted page {page}: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for player links
                player_links = soup.find_all('a', href=lambda x: x and '/players/' in str(x))
                
                if len(player_links) == 0:
                    print(f"⚠️ No player links found on sorted page {page}")
                    continue
                
                extinct_found_on_page = 0
                cards_on_page = []
                
                # Check each player on this page for extinction indicators
                unique_players = {}
                for link in player_links:
                    href = link.get('href', '')
                    if href not in unique_players:
                        # Check if this player appears extinct on the listing page
                        appears_extinct = self.check_extinction_on_listing_page(link, soup)
                        
                        card_data = self.extract_player_data_from_link(link, soup)
                        if card_data:
                            card_data['appears_extinct'] = appears_extinct
                            unique_players[href] = card_data
                            cards_on_page.append(card_data)
                            
                            if appears_extinct:
                                extinct_found_on_page += 1
                
                print(f"📊 Page {page}: {extinct_found_on_page}/{len(cards_on_page)} players appear extinct")
                
                # Save all cards from this page to database
                if cards_on_page:
                    saved = self.save_cards_to_db(cards_on_page)
                    total_saved += saved
                
                total_extinct_found += extinct_found_on_page
                
                # If we find very few extinct players on this page, we might be past the extinct zone
                if extinct_found_on_page == 0 and page > 1:
                    print(f"🎯 No extinct players found on page {page}, stopping price-sorted scraping")
                    break
                
                # Delay between pages
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                print(f"❌ Error scraping sorted page {page}: {e}")
                continue
        
        print(f"🎉 Price-sorted scraping complete! Found {total_extinct_found} extinct indicators, saved {total_saved} cards")
        
        return total_extinct_found, total_saved
    
    def check_extinction_on_listing_page(self, link, soup):
        """
        Check if a player appears extinct on the listing page itself
        """
        try:
            # Find the parent container for this player link
            card_container = link.find_parent(['div', 'article', 'section', 'li'])
            if not card_container:
                return False
            
            # Look for price information in the container
            container_text = card_container.get_text().upper()
            
            # Check for explicit "EXTINCT" text
            if "EXTINCT" in container_text:
                return True
            
            # Look for price elements - if no price elements found, likely extinct
            price_indicators = ['price', 'cost', 'coin', 'value', 'buy', 'sell']
            price_elements = []
            
            for indicator in price_indicators:
                elements = card_container.find_all(class_=lambda x: x and indicator in x.lower())
                price_elements.extend(elements)
            
            # Also look for elements containing numbers that could be prices
            number_elements = card_container.find_all(text=lambda x: x and any(char.isdigit() for char in x))
            
            # If we find "EXTINCT" in any price-related element, it's extinct
            for element in price_elements:
                if element and "EXTINCT" in element.get_text().upper():
                    return True
            
            # Check if there are suspiciously few price indicators (could indicate extinction)
            if len(price_elements) == 0 and len(number_elements) < 2:
                # Very few price indicators, might be extinct
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Error checking extinction status: {e}")
            return False
    
    def check_player_extinct_status(self, fut_gg_url):
        """
        Check if a specific player is extinct using HTML parsing
        """
        try:
            self.rotate_user_agent()
            response = self.session.get(fut_gg_url, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Failed to check extinct status: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for extinct indicators in HTML
            extinct_elements = soup.find_all(class_="flex items-center justify-center grow shrink-0 gap-[0.1em]")
            
            is_extinct = False
            for element in extinct_elements:
                text = element.get_text(strip=True).upper()
                if "EXTINCT" in text:
                    print(f"🔥 EXTINCT found: {text}")
                    is_extinct = True
                    break
            
            if not is_extinct:
                # Also check for any element containing "EXTINCT" as backup
                all_text = soup.get_text().upper()
                if "EXTINCT" in all_text:
                    print(f"🔥 EXTINCT detected in page content")
                    is_extinct = True
            
            # Extract player image URL while we're here
            player_image_url = None
            img_elements = soup.find_all('img', alt=lambda x: x and any(word in str(x).lower() for word in ['team of the week', 'player', 'card']))
            
            for img in img_elements:
                src = img.get('src', '')
                if 'fut.gg' in src and ('cdn-cgi' in src or 'image' in src):
                    player_image_url = src
                    break
            
            return {"extinct": is_extinct, "image_url": player_image_url}
            
        except Exception as e:
            print(f"Error checking extinct status for {fut_gg_url}: {e}")
            return None
    
    def send_telegram_notification(self, message):
        """Send notification to Telegram"""
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': Config.TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print("✅ Telegram notification sent")
            else:
                print(f"❌ Telegram error: {response.status_code}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")
    
    def send_discord_extinct_notification(self, card_info, image_url=None):
        """Send simple Discord notification for extinct players"""
        if not Config.DISCORD_WEBHOOK_URL:
            return
        
        embed = {
            "title": f"EXTINCT: {card_info['name']}",
            "description": f"Rating {card_info['rating']} - No longer available on market",
            "color": 0xff0000,
            "url": card_info['fut_gg_url'],
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {
                    "name": "Status",
                    "value": "EXTINCT",
                    "inline": True
                },
                {
                    "name": "Rating", 
                    "value": str(card_info['rating']),
                    "inline": True
                }
            ]
        }
        
        # Add player image if provided
        if image_url:
            embed["thumbnail"] = {"url": image_url}
        
        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("✅ Discord extinct alert sent")
            else:
                print(f"❌ Discord error: {response.status_code}")
        except Exception as e:
            print(f"❌ Discord error: {e}")
    
    def send_discord_notification(self, message, title="FUT.GG Extinct Monitor"):
        """Send general Discord notification"""
        if not Config.DISCORD_WEBHOOK_URL:
            return
        
        embed = {
            "title": title,
            "description": message,
            "color": 0x0099ff,
            "timestamp": datetime.now().isoformat()
        }
        
        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("✅ Discord notification sent")
            else:
                print(f"❌ Discord error: {response.status_code}")
        except Exception as e:
            print(f"❌ Discord error: {e}")
    
    def send_notification_to_all(self, message, title="FUT.GG Extinct Monitor"):
        """Send notification to both platforms"""
        self.send_telegram_notification(message)
        self.send_discord_notification(message, title)
    
    def send_extinct_alert(self, card_info, image_url=None):
        """Send extinct player alert"""
        # Check if we already sent an alert recently
        alert_saved = self.save_extinct_alert(card_info['id'])
        if not alert_saved:
            return
        
        # Telegram message
        telegram_message = f"""
🔥 <b>EXTINCT PLAYER DETECTED!</b> 🔥

🃏 <b>{card_info['name']}</b>
⭐ Rating: {card_info['rating']}
🏆 Position: {card_info['position'] or 'Unknown'}
🏟️ Club: {card_info.get('club', 'Unknown')}
🌍 Nation: {card_info.get('nation', 'Unknown')}

💰 <b>Status: EXTINCT</b>
📈 This player is not available on the market!
⚡ Perfect time to list if you have this card!

🔗 <a href="{card_info['fut_gg_url']}">View on FUT.GG</a>
⏰ {datetime.now().strftime('%H:%M:%S')}

💡 <b>Action:</b> If you own this card, list it now for maximum profit!
        """
        
        self.send_telegram_notification(telegram_message.strip())
        self.send_discord_extinct_notification(card_info, image_url)
        
        print(f"🔥 EXTINCT ALERT: {card_info['name']} ({card_info['rating']}) - Market extinct!")
    
    def save_extinct_alert(self, card_id):
        """Save extinct alert and prevent duplicates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if we already sent an alert recently
        cooldown_time = datetime.now() - timedelta(hours=Config.ALERT_COOLDOWN_HOURS)
        cursor.execute('''
            SELECT COUNT(*) FROM extinct_alerts 
            WHERE card_id = ? AND alert_sent_at > ? AND resolved_at IS NULL
        ''', (card_id, cooldown_time))
        
        recent_alerts = cursor.fetchone()[0]
        
        if recent_alerts > 0:
            print(f"⚠️ Alert cooldown active for card {card_id}")
            conn.close()
            return False
        
        # Save new alert
        cursor.execute('''
            INSERT INTO extinct_alerts 
            (card_id, platform, extinct_status)
            VALUES (?, ?, ?)
        ''', (card_id, 'fut_gg', True))
        
        conn.commit()
        conn.close()
        return True
    
    def get_cards_to_monitor(self, limit=50):
        """Get cards from database to monitor"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, rating, position, club, nation, league, fut_gg_url, fut_gg_id
            FROM cards 
            ORDER BY RANDOM()
            LIMIT ?
        ''', (limit,))
        
        cards = []
        for row in cursor.fetchall():
            cards.append({
                'id': row[0], 'name': row[1], 'rating': row[2], 'position': row[3],
                'club': row[4], 'nation': row[5], 'league': row[6], 
                'fut_gg_url': row[7], 'fut_gg_id': row[8]
            })
        
        conn.close()
        return cards
    
    def log_card_status(self, card_id, status_type, status_value):
        """Log card status to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO card_status_history 
                (card_id, status_type, status_value)
                VALUES (?, ?, ?)
            ''', (card_id, status_type, status_value))
            
            conn.commit()
            conn.close()
        except Exception as e:
            pass  # Don't let logging errors break monitoring
    
    def run_extinct_monitoring(self):
        """Main monitoring loop using price-sorted HTML scraping"""
        print("🤖 Starting price-sorted HTML scraping extinct monitoring...")
        
        cycle_count = 0
        
        while True:
            try:
                # Use price-sorted approach to find extinct players
                print("🔍 Checking price-sorted pages for extinct players...")
                
                extinct_indicators, cards_found = self.scrape_price_sorted_pages(5)  # Check first 5 sorted pages
                
                if extinct_indicators > 0:
                    print(f"🎯 Found {extinct_indicators} extinct indicators on price-sorted pages")
                    
                    # Now check the individual pages of players that appeared extinct
                    cards_to_verify = self.get_recently_added_cards(50)  # Get recently scraped cards
                    
                    verified_extinct = 0
                    for i, card in enumerate(cards_to_verify):
                        try:
                            # Double-check by visiting individual player page
                            status_result = self.check_player_extinct_status(card['fut_gg_url'])
                            
                            if status_result and status_result.get('extinct'):
                                self.send_extinct_alert(card, status_result.get('image_url'))
                                verified_extinct += 1
                                self.log_card_status(card['id'], 'extinct', 'true')
                            elif status_result and not status_result.get('extinct'):
                                self.log_card_status(card['id'], 'available', 'true')
                            
                            # Progress update
                            if (i + 1) % 10 == 0:
                                print(f"✅ Verified {i + 1}/{len(cards_to_verify)} cards... Confirmed extinct: {verified_extinct}")
                            
                            # Delay between individual checks
                            time.sleep(random.uniform(3, 6))
                            
                        except Exception as e:
                            print(f"Error verifying {card['name']}: {e}")
                            continue
                    
                    cycle_count += 1
                    
                    if verified_extinct > 0:
                        self.send_notification_to_all(
                            f"🔍 Price-sorted monitoring cycle #{cycle_count} complete!\n"
                            f"📊 Found {extinct_indicators} extinct indicators, verified {verified_extinct} extinct players\n"
                            f"🔥 Confirmed extinct players sent as alerts\n"
                            f"⏰ Next check in {Config.MONITORING_CYCLE_INTERVAL} minutes",
                            "🔍 Cycle Complete"
                        )
                    else:
                        print(f"🔍 Cycle #{cycle_count} - extinct indicators found but none verified")
                
                else:
                    print("🔍 No extinct indicators found on price-sorted pages")
                    cycle_count += 1
                
                # Wait based on config
                wait_time = Config.MONITORING_CYCLE_INTERVAL * 60  # Convert minutes to seconds
                print(f"💤 Cycle #{cycle_count} complete. Waiting {wait_time/60} minutes...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("🛑 Monitoring stopped!")
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(60)
    
    def get_recently_added_cards(self, limit=50):
        """Get recently added cards (likely from price-sorted scraping)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get most recently added cards (likely the ones we just scraped from sorted pages)
        cursor.execute('''
            SELECT id, name, rating, position, club, nation, league, fut_gg_url, fut_gg_id
            FROM cards 
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        cards = []
        for row in cursor.fetchall():
            cards.append({
                'id': row[0], 'name': row[1], 'rating': row[2], 'position': row[3],
                'club': row[4], 'nation': row[5], 'league': row[6], 
                'fut_gg_url': row[7], 'fut_gg_id': row[8]
            })
        
        conn.close()
        return cards
    
    def run_complete_system(self):
        """Run the complete extinct monitoring system using dynamic extinct zone detection"""
        print("🚀 Starting FUT.GG Extinct Player Monitor with Dynamic Zone Detection!")
        
        # Send startup notification
        self.check_and_send_startup_notification()
        
        # Check current database state
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cards')
        card_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"📊 Current cards in database: {card_count}")
        
        # Check if we should skip scraping
        skip_scraping = os.getenv('SKIP_SCRAPING', 'false').lower() == 'true'
        
        if skip_scraping and card_count > 0:
            print("⚠️ SKIP_SCRAPING enabled - using existing database")
            self.send_notification_to_all(
                f"✅ Using existing database with {card_count:,} cards\n"
                f"🎯 Starting dynamic extinct zone monitoring!",
                "🎯 Zone Monitoring Started"
            )
        elif card_count < 100:
            print("📄 Database needs players - starting extinct zone scraping...")
            scraped = self.scrape_extinct_zone_players()
            
            if scraped > 0:
                print(f"✅ Scraped {scraped} players from extinct zone. Starting monitoring...")
            else:
                print("⚠️ No players scraped from extinct zone - will try monitoring anyway")
        else:
            print(f"✅ Found {card_count:,} cards in database")
            self.send_notification_to_all(
                f"✅ Database ready with {card_count:,} cards\n"
                f"🎯 Starting dynamic extinct zone monitoring!",
                "🎯 Zone Monitoring Started"
            )
        
        # Start the dynamic extinct zone monitoring
        print("🔥 Starting dynamic extinct zone monitoring...")
        self.monitor_extinct_zone()

    
    def check_player_extinct_status(self, fut_gg_url):
        """
        Check if a specific player is extinct using HTML parsing
        """
        try:
            self.rotate_user_agent()
            response = self.session.get(fut_gg_url, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Failed to check extinct status: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for extinct indicators in HTML
            extinct_elements = soup.find_all(class_="flex items-center justify-center grow shrink-0 gap-[0.1em]")
            
            is_extinct = False
            for element in extinct_elements:
                text = element.get_text(strip=True).upper()
                if "EXTINCT" in text:
                    print(f"🔥 EXTINCT found: {text}")
                    is_extinct = True
                    break
            
            if not is_extinct:
                # Also check for any element containing "EXTINCT" as backup
                all_text = soup.get_text().upper()
                if "EXTINCT" in all_text:
                    print(f"🔥 EXTINCT detected in page content")
                    is_extinct = True
            
            # Extract player image URL while we're here
            player_image_url = None
            img_elements = soup.find_all('img', alt=lambda x: x and any(word in str(x).lower() for word in ['team of the week', 'player', 'card']))
            
            for img in img_elements:
                src = img.get('src', '')
                if 'fut.gg' in src and ('cdn-cgi' in src or 'image' in src):
                    player_image_url = src
                    break
            
            return {"extinct": is_extinct, "image_url": player_image_url}
            
        except Exception as e:
            print(f"Error checking extinct status for {fut_gg_url}: {e}")
            return None
    
    def send_telegram_notification(self, message):
        """Send notification to Telegram"""
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': Config.TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print("✅ Telegram notification sent")
            else:
                print(f"❌ Telegram error: {response.status_code}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")
    
    def send_discord_extinct_notification(self, card_info, image_url=None):
        """Send simple Discord notification for extinct players"""
        if not Config.DISCORD_WEBHOOK_URL:
            return
        
        embed = {
            "title": f"EXTINCT: {card_info['name']}",
            "description": f"Rating {card_info['rating']} - No longer available on market",
            "color": 0xff0000,
            "url": card_info['fut_gg_url'],
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {
                    "name": "Status",
                    "value": "EXTINCT",
                    "inline": True
                },
                {
                    "name": "Rating", 
                    "value": str(card_info['rating']),
                    "inline": True
                }
            ]
        }
        
        # Add player image if provided
        if image_url:
            embed["thumbnail"] = {"url": image_url}
        
        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("✅ Discord extinct alert sent")
            else:
                print(f"❌ Discord error: {response.status_code}")
        except Exception as e:
            print(f"❌ Discord error: {e}")
    
    def send_discord_notification(self, message, title="FUT.GG Extinct Monitor"):
        """Send general Discord notification"""
        if not Config.DISCORD_WEBHOOK_URL:
            return
        
        embed = {
            "title": title,
            "description": message,
            "color": 0x0099ff,
            "timestamp": datetime.now().isoformat()
        }
        
        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("✅ Discord notification sent")
            else:
                print(f"❌ Discord error: {response.status_code}")
        except Exception as e:
            print(f"❌ Discord error: {e}")
    
    def send_notification_to_all(self, message, title="FUT.GG Extinct Monitor"):
        """Send notification to both platforms"""
        self.send_telegram_notification(message)
        self.send_discord_notification(message, title)
    
    def send_extinct_alert(self, card_info, image_url=None):
        """Send extinct player alert"""
        # Check if we already sent an alert recently
        alert_saved = self.save_extinct_alert(card_info['id'])
        if not alert_saved:
            return
        
        # Telegram message
        telegram_message = f"""
🔥 <b>EXTINCT PLAYER DETECTED!</b> 🔥

🃏 <b>{card_info['name']}</b>
⭐ Rating: {card_info['rating']}
🏆 Position: {card_info['position'] or 'Unknown'}
🏟️ Club: {card_info.get('club', 'Unknown')}
🌍 Nation: {card_info.get('nation', 'Unknown')}

💰 <b>Status: EXTINCT</b>
📈 This player is not available on the market!
⚡ Perfect time to list if you have this card!

🔗 <a href="{card_info['fut_gg_url']}">View on FUT.GG</a>
⏰ {datetime.now().strftime('%H:%M:%S')}

💡 <b>Action:</b> If you own this card, list it now for maximum profit!
        """
        
        self.send_telegram_notification(telegram_message.strip())
        self.send_discord_extinct_notification(card_info, image_url)
        
        print(f"🔥 EXTINCT ALERT: {card_info['name']} ({card_info['rating']}) - Market extinct!")
    
    def save_extinct_alert(self, card_id):
        """Save extinct alert and prevent duplicates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if we already sent an alert recently
        cooldown_time = datetime.now() - timedelta(hours=Config.ALERT_COOLDOWN_HOURS)
        cursor.execute('''
            SELECT COUNT(*) FROM extinct_alerts 
            WHERE card_id = ? AND alert_sent_at > ? AND resolved_at IS NULL
        ''', (card_id, cooldown_time))
        
        recent_alerts = cursor.fetchone()[0]
        
        if recent_alerts > 0:
            print(f"⚠️ Alert cooldown active for card {card_id}")
            conn.close()
            return False
        
        # Save new alert
        cursor.execute('''
            INSERT INTO extinct_alerts 
            (card_id, platform, extinct_status)
            VALUES (?, ?, ?)
        ''', (card_id, 'fut_gg', True))
        
        conn.commit()
        conn.close()
        return True
    
    def get_cards_to_monitor(self, limit=50):
        """Get cards from database to monitor"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, rating, position, club, nation, league, fut_gg_url, fut_gg_id
            FROM cards 
            ORDER BY RANDOM()
            LIMIT ?
        ''', (limit,))
        
        cards = []
        for row in cursor.fetchall():
            cards.append({
                'id': row[0], 'name': row[1], 'rating': row[2], 'position': row[3],
                'club': row[4], 'nation': row[5], 'league': row[6], 
                'fut_gg_url': row[7], 'fut_gg_id': row[8]
            })
        
        conn.close()
        return cards
    
    def log_card_status(self, card_id, status_type, status_value):
        """Log card status to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO card_status_history 
                (card_id, status_type, status_value)
                VALUES (?, ?, ?)
            ''', (card_id, status_type, status_value))
            
            conn.commit()
            conn.close()
        except Exception as e:
            pass  # Don't let logging errors break monitoring
    
    def run_extinct_monitoring(self):
        """Main monitoring loop using HTML scraping"""
        print("🤖 Starting HTML scraping-based extinct monitoring...")
        
        cycle_count = 0
        
        while True:
            try:
                cards = self.get_cards_to_monitor(Config.CARDS_TO_MONITOR_PER_CYCLE)
                if not cards:
                    print("❌ No cards in database! Running scraping...")
                    self.scrape_all_players(5)
                    continue
                
                print(f"🔍 HTML monitoring {len(cards)} cards for extinct status...")
                
                extinct_found = 0
                for i, card in enumerate(cards):
                    try:
                        status_result = self.check_player_extinct_status(card['fut_gg_url'])
                        
                        if status_result and status_result.get('extinct'):
                            self.send_extinct_alert(card, status_result.get('image_url'))
                            extinct_found += 1
                            self.log_card_status(card['id'], 'extinct', 'true')
                        elif status_result and not status_result.get('extinct'):
                            self.log_card_status(card['id'], 'available', 'true')
                        
                        # Progress update
                        if (i + 1) % 10 == 0:
                            print(f"✅ Checked {i + 1}/{len(cards)} cards... Extinct found: {extinct_found}")
                        
                        # Delay between checks
                        time.sleep(random.uniform(3, 6))
                        
                    except Exception as e:
                        print(f"Error monitoring {card['name']}: {e}")
                        continue
                
                cycle_count += 1
                
                if extinct_found > 0:
                    self.send_notification_to_all(
                        f"🔍 HTML monitoring cycle #{cycle_count} complete!\n"
                        f"📊 Checked {len(cards)} cards via HTML scraping\n"
                        f"🔥 Found {extinct_found} extinct players\n"
                        f"⏰ Next check in {Config.MONITORING_CYCLE_INTERVAL} minutes",
                        "🔍 Cycle Complete"
                    )
                else:
                    print(f"🔍 Cycle #{cycle_count} complete - no extinct players found")
                
                # Wait based on config
                wait_time = Config.MONITORING_CYCLE_INTERVAL * 60  # Convert minutes to seconds
                print(f"💤 Cycle #{cycle_count} complete. Found {extinct_found} extinct players. Waiting {wait_time/60} minutes...")
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("🛑 Monitoring stopped!")
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(60)
    
    def run_complete_system(self):
        """Run the complete extinct monitoring system using HTML scraping"""
        print("🚀 Starting FUT.GG Extinct Player Monitor with HTML Scraping!")
        
        # Send startup notification
        self.check_and_send_startup_notification()
        
        # Check current database state
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cards')
        card_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"📊 Current cards in database: {card_count}")
        
        if Config.SKIP_SCRAPING and card_count > 0:
            print("⚠️ SKIP_SCRAPING enabled - using existing database")
            self.send_notification_to_all(
                f"✅ Using existing database with {card_count:,} cards\n"
                f"🔍 Starting HTML scraping-based monitoring!",
                "🔍 Monitoring Started"
            )
        elif card_count < 100:
            print("📄 Database needs players - starting HTML scraping...")
            scraped = self.scrape_all_players(Config.MAX_PAGES_TO_SCRAPE)
            
            if scraped > 0:
                print(f"✅ HTML scraped {scraped} players. Starting monitoring...")
            else:
                print("⚠️ No players scraped - will try monitoring anyway")
        else:
            print(f"✅ Found {card_count:,} cards in database")
            self.send_notification_to_all(
                f"✅ Database ready with {card_count:,} cards\n"
                f"🔍 Starting HTML scraping-based monitoring!",
                "🔍 Monitoring Started"
            )
        
        # Start HTML scraping-based extinct monitoring
        print("🔥 Starting HTML scraping-based extinct monitoring...")
        self.run_extinct_monitoring()

# Entry point
if __name__ == "__main__":
    monitor = FutGGExtinctMonitor()
    monitor.run_complete_system()
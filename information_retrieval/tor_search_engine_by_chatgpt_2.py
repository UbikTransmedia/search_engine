import threading
import requests
from bs4 import BeautifulSoup
import re
import time
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from stem import Signal
from stem.control import Controller
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the TorSession class
class TorSession:
    def __init__(self, tor_password=None, port=9051, proxy_port=9050, verbose=False):
        self.tor_password = tor_password
        self.port = port
        self.proxy_port = proxy_port
        self.session = None
        self.verbose = verbose
    
    def connect(self):
        try:
            with Controller.from_port(port=self.port) as controller:
                if self.tor_password:
                    controller.authenticate(password=self.tor_password)
                else:
                    controller.authenticate()
                controller.signal(Signal.NEWNYM)
                if self.verbose:
                    print("🌐 Connected to TOR")
            self.session = requests.Session()
            self.session.proxies = {
                'http': f'socks5h://127.0.0.1:{self.proxy_port}',
                'https': f'socks5h://127.0.0.1:{self.proxy_port}'
            }
        except Exception as e:
            logging.error(f"Failed to connect to TOR: {e}")
            self.session = None

    def get_session(self):
        if not self.session:
            self.connect()
        return self.session

# Define the DatabaseManager class
class DatabaseManager:
    def __init__(self, db_name="web_crawler.db", verbose=False):
        self.verbose = verbose
        try:
            self.conn = sqlite3.connect(db_name, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self.create_tables()
            if self.verbose:
                print("📁 Connected to SQLite database")
        except sqlite3.Error as e:
            logging.error(f"Failed to connect to database: {e}")
            self.conn = None
            self.cursor = None

    def create_tables(self):
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY,
                    url TEXT UNIQUE,
                    content TEXT
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS link_relations (
                    id INTEGER PRIMARY KEY,
                    from_link INTEGER,
                    to_link INTEGER,
                    FOREIGN KEY(from_link) REFERENCES links(id),
                    FOREIGN KEY(to_link) REFERENCES links(id)
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS link_checks (
                    id INTEGER PRIMARY KEY,
                    link_id INTEGER,
                    check_time TIMESTAMP,
                    success INTEGER,
                    FOREIGN KEY(link_id) REFERENCES links(id)
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS link_uptime (
                    id INTEGER PRIMARY KEY,
                    link_id INTEGER,
                    mean_uptime REAL,
                    period_start TIMESTAMP,
                    period_end TIMESTAMP,
                    FOREIGN KEY(link_id) REFERENCES links(id)
                )
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Failed to create tables: {e}")

    def insert_link(self, url, content):
        try:
            self.cursor.execute("INSERT INTO links (url, content) VALUES (?, ?)", (url, content))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            try:
                return self.cursor.execute("SELECT id FROM links WHERE url = ?", (url,)).fetchone()[0]
            except sqlite3.Error as e:
                logging.error(f"Failed to fetch link ID: {e}")
                return None
        except sqlite3.Error as e:
            logging.error(f"Failed to insert link: {e}")
            return None

    def insert_link_relation(self, from_link_id, to_link_id):
        try:
            self.cursor.execute("INSERT INTO link_relations (from_link, to_link) VALUES (?, ?)", (from_link_id, to_link_id))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Failed to insert link relation: {e}")

    def log_link_check(self, link_id, success):
        try:
            self.cursor.execute("INSERT INTO link_checks (link_id, check_time, success) VALUES (?, ?, ?)", 
                                (link_id, datetime.now(), int(success)))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Failed to log link check: {e}")

    def calculate_mean_uptime(self, link_id, period_start, period_end):
        try:
            self.cursor.execute("""
                SELECT AVG(success) FROM link_checks
                WHERE link_id = ? AND check_time BETWEEN ? AND ?
            """, (link_id, period_start, period_end))
            result = self.cursor.fetchone()
            return result[0] if result[0] is not None else 0
        except sqlite3.Error as e:
            logging.error(f"Failed to calculate mean uptime: {e}")
            return 0

    def save_mean_uptime(self, link_id, mean_uptime, period_start, period_end):
        try:
            self.cursor.execute("INSERT INTO link_uptime (link_id, mean_uptime, period_start, period_end) VALUES (?, ?, ?, ?)", 
                                (link_id, mean_uptime, period_start, period_end))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Failed to save mean uptime: {e}")

    def get_all_links(self):
        try:
            self.cursor.execute("SELECT * FROM links")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Failed to fetch links: {e}")
            return []

    def get_link_relations(self):
        try:
            self.cursor.execute("SELECT from_link, to_link FROM link_relations")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Failed to fetch link relations: {e}")
            return []

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except sqlite3.Error as e:
                logging.error(f"Failed to close database: {e}")

# Define the LinkCrawler class
class LinkCrawler(threading.Thread):
    def __init__(self, tor_session, db_manager, seed_urls, depth=2, retries=3, verbose=False):
        threading.Thread.__init__(self)
        self.session = tor_session.get_session()
        self.db_manager = db_manager
        self.seed_urls = seed_urls
        self.depth = depth
        self.retries = retries
        self.verbose = verbose

    def sanitize_content(self, text):
        try:
            text = text.lower()
            text = re.sub(r'\W+', ' ', text)
            tokens = text.split()
            stop_words = set(stopwords.words('english'))
            sanitized_tokens = [word for word in tokens if word not in stop_words]
            return ' '.join(sanitized_tokens)
        except Exception as e:
            logging.error(f"Failed to sanitize content: {e}")
            return ""

    def crawl(self, url, retries_left=None):
        if not self.session:
            logging.error("No TOR session available")
            return set()

        if retries_left is None:
            retries_left = self.retries

        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text(separator=' ')
            sanitized_text = self.sanitize_content(text)

            from_link_id = self.db_manager.insert_link(url, sanitized_text)
            if from_link_id is None:
                return set()

            links = set()
            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href']
                if link.startswith('http'):
                    to_link_id = self.db_manager.insert_link(link, '')
                    if to_link_id:
                        self.db_manager.insert_link_relation(from_link_id, to_link_id)
                        links.add(link)

            self.db_manager.log_link_check(from_link_id, success=True)
            if self.verbose:
                print(f"✅ Successfully crawled: {url}")

            return links
        except requests.RequestException as e:
            logging.error(f"Failed to crawl {url}: {e}")
            if retries_left > 0:
                if self.verbose:
                    print(f"🔄 Retrying {url} ({retries_left} retries left)")
                time.sleep(5)
                return self.crawl(url, retries_left=retries_left - 1)
            else:
                from_link_id = self.db_manager.insert_link(url, '')
                self.db_manager.log_link_check(from_link_id, success=False)
                if self.verbose:
                    print(f"❌ Failed to crawl after retries: {url}")
                return set()

    def run(self):
        to_crawl = set(self.seed_urls)

        while True:
            if not to_crawl:
                to_crawl = set(self.seed_urls)  # Re-crawl seed URLs after finishing

            next_to_crawl = set()
            for url in to_crawl:
                if url not in [row[1] for row in self.db_manager.get_all_links()]:
                    links = self.crawl(url)
                    next_to_crawl.update(links)

            to_crawl = next_to_crawl
            time.sleep(10)  # Add a delay to avoid overloading servers

# Define the ReverseIndexer class
class ReverseIndexer(threading.Thread):
    def __init__(self, db_manager, verbose=False):
        threading.Thread.__init__(self)
        self.db_manager = db_manager
        self.indexing_complete = False
        self.vectorizer = None
        self.tfidf_matrix = None
        self.links = []
        self.verbose = verbose

    def create_reverse_index(self):
        try:
            self.links = self.db_manager.get_all_links()
            corpus = [link[2] for link in self.links]
            self.vectorizer = TfidfVectorizer()
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
            if self.verbose:
                print("🔄 Reverse index created")
        except Exception as e:
            logging.error(f"Failed to create reverse index: {e}")
            self.vectorizer = None
            self.tfidf_matrix = None

    def calculate_pagerank(self, iterations=100, d=0.85):
        links = self.db_manager.get_all_links()
        num_links = len(links)
        if num_links == 0:
            logging.error("No links found for PageRank calculation.")
            return {}

        pagerank = {link[0]: 1 / num_links for link in links}
        inbound_links = defaultdict(list)

        for from_link, to_link in self.db_manager.get_link_relations():
            inbound_links[to_link].append(from_link)

        for i in range(iterations):
            new_pagerank = {}
            for link_id in pagerank:
                incoming_score = sum(pagerank[in_link] / len(inbound_links[in_link]) for in_link in inbound_links[link_id])
                new_pagerank[link_id] = (1 - d) / num_links + d * incoming_score

            pagerank = new_pagerank

        if self.verbose:
            print("🔄 PageRank calculated")

        return pagerank

    def rank_websites(self, query, top_n=10):
        if self.vectorizer is None or self.tfidf_matrix is None:
            logging.error("Index not built yet")
            return []

        try:
            pagerank = self.calculate_pagerank()
            query_vector = self.vectorizer.transform([query])
            cosine_similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()

            combined_scores = []
            for i, link in enumerate(self.links):
                pr_score = pagerank.get(link[0], 0)
                combined_score = cosine_similarities[i] * pr_score
                combined_scores.append((link[1], combined_score))

            combined_scores.sort(key=lambda x: x[1], reverse=True)

            if self.verbose:
                print("🔍 Websites ranked for query")

            return combined_scores[:top_n]
        except Exception as e:
            logging.error(f"Failed to rank websites: {e}")
            return []

    def run(self):
        while True:
            self.indexing_complete = False
            self.create_reverse_index()
            self.indexing_complete = True
            time.sleep(30)  # Rebuild the index every 30 seconds

# Define the QueryEngine class
class QueryEngine:
    def __init__(self, reverse_indexer, verbose=False):
        self.reverse_indexer = reverse_indexer
        self.verbose = verbose

    def query(self, search_terms):
        while not self.reverse_indexer.indexing_complete:
            logging.info("Waiting for index to be built...")
            time.sleep(1)

        results = self.reverse_indexer.rank_websites(search_terms)
        if results:
            for result in results:
                print(f"URL: {result[0]}, Combined Score: {result[1]}")
        else:
            print("No results found.")

# Define the UptimeRetriever class
class UptimeRetriever:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def get_uptime(self, link_id, start_time, end_time):
        return self.db_manager.calculate_mean_uptime(link_id, start_time, end_time)

# Main execution flow
if __name__ == "__main__":
    # Verbose mode flag
    verbose_mode = True

    # Create and connect a TOR session
    tor_session = TorSession(tor_password='YOUR_TOR_PASSWORD', verbose=verbose_mode)
    tor_session.connect()

    # Initialize the database manager
    db_manager = DatabaseManager(verbose=verbose_mode)

    if db_manager.conn is None:
        logging.error("Database connection failed. Exiting...")
        exit(1)

    # Seed URLs to start crawling
    seed_urls = [
        "http://example1.com",
        "http://example2.com",
    ]

    # Initialize and start the link crawler
    crawler = LinkCrawler(tor_session, db_manager, seed_urls, verbose=verbose_mode)
    crawler.start()

    # Initialize and start the reverse indexer
    indexer = ReverseIndexer(db_manager, verbose=verbose_mode)
    indexer.start()

    # Initialize the query engine
    query_engine = QueryEngine(indexer, verbose=verbose_mode)

    # Main loop to handle user queries
    try:
        while True:
            search_terms = input("Enter search query: ")
            if search_terms.lower() == 'exit':
                break
            query_engine.query(search_terms)
    except KeyboardInterrupt:
        logging.info("Process interrupted by user. Exiting...")
    finally:
        if db_manager.conn:
            db_manager.close()
        logging.info("Database connection closed.")
"""

# Write the main script to a file
os.makedirs(f'{base_dir}/scripts', exist_ok=True)
with open(f'{base_dir}/scripts/web_crawler.py', 'w') as f:
    f.write(main_script_content)

# Now, let's package this into a ZIP file
zip_filename = f'{base_dir}.zip'
with zipfile.ZipFile(zip_filename, 'w') as zipf:
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            zipf.write(os.path.join(root, file))

zip_filename

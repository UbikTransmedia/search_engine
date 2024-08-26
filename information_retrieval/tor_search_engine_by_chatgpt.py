import threading
import requests
from bs4 import BeautifulSoup
import re
import time
import sqlite3
from collections import defaultdict
from stem import Signal
from stem.control import Controller
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class TorSession:
    def __init__(self, tor_password=None, port=9051, proxy_port=9050):
        self.tor_password = tor_password
        self.port = port
        self.proxy_port = proxy_port
        self.session = None
    
    def connect(self):
        with Controller.from_port(port=self.port) as controller:
            if self.tor_password:
                controller.authenticate(password=self.tor_password)
            else:
                controller.authenticate()
            controller.signal(Signal.NEWNYM)
            print("Connected to TOR")

        self.session = requests.Session()
        self.session.proxies = {
            'http': f'socks5h://127.0.0.1:{self.proxy_port}',
            'https': f'socks5h://127.0.0.1:{self.proxy_port}'
        }

    def get_session(self):
        if not self.session:
            self.connect()
        return self.session


class DatabaseManager:
    def __init__(self, db_name="web_crawler.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
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
        self.conn.commit()

    def insert_link(self, url, content):
        try:
            self.cursor.execute("INSERT INTO links (url, content) VALUES (?, ?)", (url, content))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            return self.cursor.execute("SELECT id FROM links WHERE url = ?", (url,)).fetchone()[0]

    def insert_link_relation(self, from_link_id, to_link_id):
        self.cursor.execute("INSERT INTO link_relations (from_link, to_link) VALUES (?, ?)", (from_link_id, to_link_id))
        self.conn.commit()

    def get_all_links(self):
        self.cursor.execute("SELECT * FROM links")
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()


class LinkCrawler(threading.Thread):
    def __init__(self, tor_session, db_manager, seed_urls, depth=2):
        threading.Thread.__init__(self)
        self.session = tor_session.get_session()
        self.db_manager = db_manager
        self.seed_urls = seed_urls
        self.depth = depth

    def sanitize_content(self, text):
        text = text.lower()
        text = re.sub(r'\W+', ' ', text)
        tokens = text.split()
        stop_words = set(stopwords.words('english'))
        sanitized_tokens = [word for word in tokens if word not in stop_words]
        return ' '.join(sanitized_tokens)

    def crawl(self, url):
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text(separator=' ')
            sanitized_text = self.sanitize_content(text)

            from_link_id = self.db_manager.insert_link(url, sanitized_text)
            links = set()

            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href']
                if link.startswith('http'):
                    to_link_id = self.db_manager.insert_link(link, '')
                    self.db_manager.insert_link_relation(from_link_id, to_link_id)
                    links.add(link)

            return links
        except requests.RequestException as e:
            print(f"Failed to crawl {url}: {e}")
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


class ReverseIndexer(threading.Thread):
    def __init__(self, db_manager):
        threading.Thread.__init__(self)
        self.db_manager = db_manager
        self.indexing_complete = False

    def create_reverse_index(self):
        links = self.db_manager.get_all_links()
        corpus = [link[2] for link in links]
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(corpus)
        return links, vectorizer, tfidf_matrix

    def rank_websites(self, query, top_n=10):
        links, vectorizer, tfidf_matrix = self.create_reverse_index()
        query_vector = vectorizer.transform([query])
        cosine_similarities = cosine_similarity(query_vector, tfidf_matrix).flatten()
        ranked_indices = cosine_similarities.argsort()[-top_n:][::-1]
        return [(links[i][1], cosine_similarities[i]) for i in ranked_indices]

    def run(self):
        while True:
            self.indexing_complete = False
            self.create_reverse_index()
            self.indexing_complete = True
            time.sleep(30)  # Rebuild the index every 30 seconds


class QueryEngine:
    def __init__(self, reverse_indexer):
        self.reverse_indexer = reverse_indexer

    def query(self, search_terms):
        while not self.reverse_indexer.indexing_complete:
            time.sleep(1)  # Wait for the index to be built

        results = self.reverse_indexer.rank_websites(search_terms)
        for result in results:
            print(f"URL: {result[0]}, Score: {result[1]}")


# Example usage
if __name__ == "__main__":
    # Create and connect a TOR session
    tor_session = TorSession(tor_password='YOUR_TOR_PASSWORD')
    tor_session.connect()

    # Initialize the database manager
    db_manager = DatabaseManager()

    # Seed URLs to start crawling
    seed_urls = [
        "http://example1.com",
        "http://example2.com",
    ]

    # Initialize and start the link crawler
    crawler = LinkCrawler(tor_session, db_manager, seed_urls)
    crawler.start()

    # Initialize and start the reverse indexer
    indexer = ReverseIndexer(db_manager)
    indexer.start()

    # Initialize the query engine
    query_engine = QueryEngine(indexer)

    # Main loop to handle user queries
    while True:
        search_terms = input("Enter search query: ")
        if search_terms.lower() == 'exit':
            break
        query_engine.query(search_terms)

    # Close the database connection
    db_manager.close()

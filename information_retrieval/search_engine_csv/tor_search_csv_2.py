import threading
import requests
from bs4 import BeautifulSoup
import re
import time
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from stem import Signal
from stem.control import Controller
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging
import ssl

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to change the Tor IP address
def change_tor_identity(password=None, port=9051):
    with Controller.from_port(port=port) as controller:
        controller.authenticate(password=password)
        controller.signal(Signal.NEWNYM)
        logging.info("Tor identity changed.")

# Configure a session to use Tor as a proxy
def get_tor_session(proxy_port=9050):
    session = requests.session()
    session.proxies = {
        'http': f'socks5h://127.0.0.1:{proxy_port}',
        'https': f'socks5h://127.0.0.1:{proxy_port}'
    }
    return session

# TorSession class to handle Tor connections with SSL support
class TorSession:
    def __init__(self, tor_password=None, port=9051, proxy_port=9050):
        self.tor_password = tor_password
        self.port = port
        self.proxy_port = proxy_port
        self.session = None
        self.ssl_context = ssl.create_default_context()

    def connect(self):
        attempt = 0
        while self.session is None and attempt < 5:  # Retry connection up to 5 times
            try:
                change_tor_identity(password=self.tor_password, port=self.port)
                self.session = get_tor_session(proxy_port=self.proxy_port)
                logging.info("Connected to TOR with SSL support")
            except Exception as e:
                logging.error(f"Failed to connect to TOR: {e}")
                attempt += 1
                time.sleep(5)  # Wait before retrying

    def get_session(self):
        if not self.session:
            self.connect()
        return self.session

class JSONManager:
    def __init__(self, index_file='reverse_index.json'):
        self.index_file = index_file
        self.data = {
            "links": [],
            "link_relations": [],
            "reverse_index": {}
        }

        if os.path.exists(self.index_file):
            with open(self.index_file, 'r') as file:
                self.data = json.load(file)
        else:
            self._save_json()

    def _save_json(self):
        with open(self.index_file, 'w') as file:
            json.dump(self.data, file, indent=4)

    def insert_link(self, url, content):
        try:
            existing_id = self.get_link_id(url)
            if existing_id:
                return existing_id

            next_id = len(self.data["links"]) + 1
            self.data["links"].append({"id": next_id, "url": url, "content": content})
            self._save_json()
            return next_id
        except Exception as e:
            logging.error(f"Failed to insert link: {e}")
            return None

    def insert_link_relation(self, from_link_id, to_link_id):
        try:
            self.data["link_relations"].append({"from_link": from_link_id, "to_link": to_link_id})
            self._save_json()
        except Exception as e:
            logging.error(f"Failed to insert link relation: {e}")

    def get_link_id(self, url):
        try:
            for link in self.data["links"]:
                if link["url"] == url:
                    return link["id"]
            return None
        except Exception as e:
            logging.error(f"Failed to get link ID: {e}")
            return None

    def get_all_links(self):
        try:
            return self.data["links"]
        except Exception as e:
            logging.error(f"Failed to fetch links: {e}")
            return []

    def get_link_relations(self):
        try:
            return [(rel["from_link"], rel["to_link"]) for rel in self.data["link_relations"]]
        except Exception as e:
            logging.error(f"Failed to fetch link relations: {e}")
            return []

class LinkCrawler(threading.Thread):
    def __init__(self, tor_session, json_manager, seed_urls, depth=100, retries=5):
        threading.Thread.__init__(self)
        self.session = tor_session.get_session()
        self.json_manager = json_manager
        self.seed_urls = seed_urls
        self.depth = depth
        self.retries = retries

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
            response = self.session.get(url, timeout=120)
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text(separator=' ')
            sanitized_text = self.sanitize_content(text)

            from_link_id = self.json_manager.insert_link(url, sanitized_text)
            if from_link_id is None:
                return set()

            links = set()
            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href']
                if link.startswith('http'):
                    to_link_id = self.json_manager.insert_link(link, '')
                    if to_link_id:
                        self.json_manager.insert_link_relation(from_link_id, to_link_id)
                        links.add(link)

            logging.info(f"Successfully crawled: {url}")

            return links
        except requests.RequestException as e:
            logging.error(f"Failed to crawl {url}: {e}")
            if retries_left > 0:
                logging.info(f"Retrying {url} ({retries_left} retries left)")
                time.sleep(5)
                return self.crawl(url, retries_left=retries_left - 1)
            else:
                from_link_id = self.json_manager.insert_link(url, '')
                logging.error(f"Failed to crawl after retries: {url}")
                return set()

    def run(self):
        while True:
            try:
                to_crawl = set(self.seed_urls)
                while to_crawl:
                    next_to_crawl = set()
                    for url in to_crawl:
                        if url not in [link['url'] for link in self.json_manager.get_all_links()]:
                            links = self.crawl(url)
                            next_to_crawl.update(links)
                    to_crawl = next_to_crawl
                time.sleep(10)
            except Exception as e:
                logging.error(f"LinkCrawler encountered an error: {e}")
                time.sleep(5)  # Wait before restarting

class ReverseIndexer(threading.Thread):
    def __init__(self, json_manager):
        threading.Thread.__init__(self)
        self.json_manager = json_manager
        self.indexing_complete = False
        self.vectorizer = None
        self.tfidf_matrix = None
        self.links = []

    def create_reverse_index(self):
        try:
            self.links = self.json_manager.get_all_links()
            corpus = [link['content'] for link in self.links]
            self.vectorizer = TfidfVectorizer()
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

            reverse_index = {}
            for i, link in enumerate(self.links):
                reverse_index[link['url']] = {
                    "id": link["id"],
                    "tfidf_vector": self.tfidf_matrix[i].toarray().tolist()
                }

            self.json_manager.data["reverse_index"] = reverse_index
            self.json_manager._save_json()

            logging.info("Reverse index created and saved to JSON")
        except Exception as e:
            logging.error(f"Failed to create reverse index: {e}")
            self.vectorizer = None
            self.tfidf_matrix = None

    def calculate_pagerank(self, iterations=100, d=0.85):
        try:
            links = self.json_manager.get_all_links()
            num_links = len(links)
            if num_links == 0:
                logging.error("No links found for PageRank calculation.")
                return {}

            pagerank = {link['id']: 1 / num_links for link in links}
            inbound_links = defaultdict(list)

            for from_link, to_link in self.json_manager.get_link_relations():
                inbound_links[to_link].append(from_link)

            for i in range(iterations):
                new_pagerank = {}
                for link_id in pagerank:
                    incoming_score = sum(pagerank[in_link] / len(inbound_links[in_link]) for in_link in inbound_links[link_id])
                    new_pagerank[link_id] = (1 - d) / num_links + d * incoming_score

                pagerank = new_pagerank

            logging.info("PageRank calculated")
            return pagerank
        except Exception as e:
            logging.error(f"Failed to calculate PageRank: {e}")
            return {}

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
                pr_score = pagerank.get(link['id'], 0)
                combined_score = cosine_similarities[i] * pr_score
                combined_scores.append((link['url'], combined_score))

            combined_scores.sort(key=lambda x: x[1], reverse=True)
            logging.info("Websites ranked for query")
            return combined_scores[:top_n]
        except Exception as e:
            logging.error(f"Failed to rank websites: {e}")
            return []

    def run(self):
        while True:
            try:
                self.indexing_complete = False
                self.create_reverse_index()
                self.indexing_complete = True
                time.sleep(30)
            except Exception as e:
                logging.error(f"ReverseIndexer encountered an error: {e}")
                time.sleep(5)  # Wait before restarting

class QueryEngine:
    def __init__(self, reverse_indexer):
        self.reverse_indexer = reverse_indexer

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

class REPL:
    def __init__(self, json_manager, query_engine):
        self.json_manager = json_manager
        self.query_engine = query_engine

    def start(self):
        print("REPL started. Type 'exit' to quit.")
        while True:
            command = input(">>> ")
            if command.lower() == "exit":
                break
            elif command.lower().startswith("query"):
                query = command[6:]
                self.query_engine.query(query)
            else:
                print("Invalid command.")

if __name__ == "__main__":
    # Create and connect a TOR session
    tor_session = TorSession(tor_password='kiwi')
    tor_session.connect()

    # Initialize the JSON manager
    json_manager = JSONManager()

    # Seed URLs to start crawling
    seed_urls = [
        "http://torlinksge6enmcyyuxjpjkoouw4oorgdgeo7ftnq3zodj7g2zxi3kyd.onion/",
        "http://zqktlwiuavvvqqt4ybvgvi7tyo4hjl5xgfuvpdf6otjiycgwqbym2qad.onion/",
        "http://answerszuvs3gg2l64e6hmnryudl5zgrmwm3vh65hzszdghblddvfiqd.onion/",
        "http://libraryfyuybp7oyidyya3ah5xvwgyx6weauoini7zyz555litmmumad.onion",
        "http://nv3x2jozywh63fkohn5mwp2d73vasusjixn3im3ueof52fmbjsigw6ad.onion",
        "http://darkfailenbsdla5mal2mxn2uz66od5vtzd5qozslagrfzachha3f3id.onion",
        "http://dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion ",
        "https://www.bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion",
        "http://http://p53lf57qovyuvwsc6xnrppyply3vtqm7l6pcobkmyqsiofyeznfu5uqd.onion",
        "https://www.nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljsciiyd.onion",
        "http://darkzzx4avcsuofgfez5zq75cqc4mprjvfqywo45dfcaxrwqg6qrlfid.onion/"

    ]

    # Initialize and start the link crawler
    crawler = LinkCrawler(tor_session, json_manager, seed_urls)
    crawler.start()

    # Initialize and start the reverse indexer
    indexer = ReverseIndexer(json_manager)
    indexer.start()

    # Initialize the query engine
    query_engine = QueryEngine(indexer)

    # Start REPL for database queries
    repl = REPL(json_manager, query_engine)
    repl.start()

    # Ensure threads are joined before exiting
    crawler.join()
    indexer.join()

    logging.info("JSON-based search engine terminated.")

import threading
import requests
from bs4 import BeautifulSoup
import re
import time
import json
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta
from stem import Signal
from stem.control import Controller
from nltk.corpus import stopwords
import math
import logging
import ssl
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
                with Controller.from_port(port=self.port) as controller:
                    if self.tor_password:
                        controller.authenticate(password=self.tor_password)
                    else:
                        controller.authenticate()
                    controller.signal(Signal.NEWNYM)
                    print(f"{Fore.GREEN}🌐 Connected to TOR with SSL support")
                self.session = requests.Session()
                self.session.proxies = {
                    'http': f'socks5h://127.0.0.1:{self.proxy_port}',
                    'https': f'socks5h://127.0.0.1:{self.proxy_port}'
                }
            except Exception as e:
                print(f"{Fore.RED}❌ Failed to connect to TOR: {e}")
                attempt += 1
                time.sleep(5)  # Wait before retrying

    def get_session(self):
        if not self.session:
            self.connect()
        return self.session

class LinkIndexManager:
    def __init__(self, link_index_file='link_index.json'):
        self.link_index_file = link_index_file
        self.links = []

        if os.path.exists(self.link_index_file):
            with open(self.link_index_file, 'r') as file:
                self.links = json.load(file)
            print(f"{Fore.YELLOW}📂 Loaded existing link index from {self.link_index_file}")
        else:
            self._save_json()

    def _save_json(self):
        with open(self.link_index_file, 'w') as file:
            json.dump(self.links, file, indent=4)

    def insert_link(self, url, content, title=None, date=None, metadata=None):
        try:
            existing_id = self.get_link_id(url)
            if existing_id:
                return existing_id

            next_id = len(self.links) + 1
            link_info = {
                "id": next_id,
                "url": url,
                "content": content,
                "title": title,
                "date": date,
                "metadata": metadata
            }

            self.links.append(link_info)
            self._save_json()
            print(f"{Fore.BLUE}📝 Link inserted: {url}")
            return next_id
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to insert link: {e}")
            return None

    def get_link_id(self, url):
        try:
            for link in self.links:
                if link["url"] == url:
                    return link["id"]
            return None
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to get link ID: {e}")
            return None

    def get_all_links(self):
        try:
            return self.links
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to fetch links: {e}")
            return []

class ReverseContentIndexManager:
    def __init__(self, reverse_index_file='reverse_content_index.json'):
        self.reverse_index_file = reverse_index_file
        self.reverse_index = {}

        if os.path.exists(self.reverse_index_file):
            with open(self.reverse_index_file, 'r') as file:
                self.reverse_index = json.load(file)
            print(f"{Fore.YELLOW}📂 Loaded existing reverse content index from {self.reverse_index_file}")
        else:
            self._save_json()

    def _save_json(self):
        with open(self.reverse_index_file, 'w') as file:
            json.dump(self.reverse_index, file, indent=4)

    def update_reverse_index(self, link_info, doc_id):
        try:
            tokens = link_info["content"].split()
            terms = defaultdict(list)
            for pos, token in enumerate(tokens):
                terms[token].append(pos)

            for term, positions in terms.items():
                if term not in self.reverse_index:
                    self.reverse_index[term] = {}
                self.reverse_index[term][doc_id] = positions

            self._save_json()
            print(f"{Fore.BLUE}🔄 Reverse index updated for doc_id {doc_id}")
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to update reverse index: {e}")

    def get_reverse_index(self):
        try:
            return self.reverse_index
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to fetch reverse index: {e}")
            return {}

class LinkCrawler(threading.Thread):
    def __init__(self, tor_session, link_index_manager, reverse_index_manager, seed_urls, depth=100, retries=5):
        threading.Thread.__init__(self)
        self.session = tor_session.get_session()
        self.link_index_manager = link_index_manager
        self.reverse_index_manager = reverse_index_manager
        self.seed_urls = seed_urls
        self.to_crawl = set(seed_urls)
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
            print(f"{Fore.RED}❌ Failed to sanitize content: {e}")
            return ""

    def extract_metadata(self, soup):
        try:
            title = soup.title.string if soup.title else None
            date = soup.find('meta', {'name': 'date'}) or soup.find('meta', {'property': 'og:date'})
            date = date['content'] if date else None
            metadata = {meta.attrs['name']: meta.attrs['content'] for meta in soup.find_all('meta') if 'name' in meta.attrs and 'content' in meta.attrs}
            return title, date, metadata
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to extract metadata: {e}")
            return None, None, None

    def crawl(self, url, retries_left=None):
        if not self.session:
            print(f"{Fore.RED}❌ No TOR session available")
            return set()

        if retries_left is None:
            retries_left = self.retries

        try:
            response = self.session.get(url, timeout=120)
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text(separator=' ')
            sanitized_text = self.sanitize_content(text)
            title, date, metadata = self.extract_metadata(soup)

            doc_id = self.link_index_manager.insert_link(url, sanitized_text, title, date, metadata)
            if doc_id:
                self.reverse_index_manager.update_reverse_index(self.link_index_manager.links[doc_id-1], doc_id)

            print(f"{Fore.GREEN}✅ Successfully crawled: {url}")

            links = set()
            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href']
                if link.startswith('http') and link not in self.seed_urls:
                    self.seed_urls.append(link)  # Add new links to the seed list
                    links.add(link)

            return links
        except requests.RequestException as e:
            print(f"{Fore.RED}❌ Failed to crawl {url}: {e}")
            if retries_left > 0:
                retry_delay = random.randint(5, 20)
                print(f"{Fore.YELLOW}🔄 Retrying {url} in {retry_delay} seconds ({retries_left} retries left)")
                time.sleep(retry_delay)
                return self.crawl(url, retries_left=retries_left - 1)
            else:
                print(f"{Fore.RED}❌ Failed to crawl after retries: {url}")
                return set()

    def run(self):
        while True:
            try:
                if not self.to_crawl:
                    print(f"{Fore.YELLOW}🔄 All links crawled. Restarting crawl cycle.")
                    self.to_crawl = set(self.seed_urls)  # Restart crawling with the full list

                next_to_crawl = set()
                for url in self.to_crawl:
                    if url not in [link['url'] for link in self.link_index_manager.get_all_links()]:
                        links = self.crawl(url)
                        next_to_crawl.update(links)
                self.to_crawl = next_to_crawl
                print(f"{Fore.BLUE}🌍 Crawling cycle completed. Sleeping...")
                time.sleep(10)
            except Exception as e:
                print(f"{Fore.RED}❌ LinkCrawler encountered an error: {e}")
                time.sleep(5)  # Wait before restarting

class ReverseIndexer:
    def __init__(self, link_index_manager, reverse_index_manager):
        self.link_index_manager = link_index_manager
        self.reverse_index_manager = reverse_index_manager
        self.indexing_complete = False

    def calculate_idf(self, term):
        try:
            doc_count = len(self.link_index_manager.get_all_links())
            term_docs = len(self.reverse_index_manager.get_reverse_index().get(term, {}))
            return math.log(doc_count / (1 + term_docs))
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to calculate IDF for term {term}: {e}")
            return 0.0

    def calculate_tfidf(self, term, doc_id):
        try:
            tf = len(self.reverse_index_manager.get_reverse_index().get(term, {}).get(doc_id, []))
            idf = self.calculate_idf(term)
            return tf * idf
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to calculate TF-IDF for term {term} in doc {doc_id}: {e}")
            return 0.0

    def rank_websites(self, query, top_n=10):
        try:
            results = []
            reverse_index = self.reverse_index_manager.get_reverse_index()

            for term in query.split():
                if term in reverse_index:
                    for doc_id, positions in reverse_index[term].items():
                        tfidf_score = self.calculate_tfidf(term, doc_id)
                        link_info = next((link for link in self.link_index_manager.get_all_links() if link['id'] == doc_id), None)
                        if link_info:
                            result = {
                                "site_name": link_info.get("title", ""),
                                "link_url": link_info["url"],
                                "score": tfidf_score,
                                "found_terms": term,
                                "frequency": len(positions)
                            }
                            results.append(result)

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_n]
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to rank websites for query '{query}': {e}")
            return []

class QueryEngine:
    def __init__(self, reverse_indexer):
        self.reverse_indexer = reverse_indexer

    def query(self, search_terms):
        results = self.reverse_indexer.rank_websites(search_terms)
        if results:
            print(f"{Fore.BLUE}🔍 Query results:")
            for result in results:
                print(f"{Fore.GREEN}🌐 Site Name: {Fore.CYAN}{result['site_name']}, {Fore.GREEN}URL: {Fore.CYAN}{result['link_url']}, {Fore.GREEN}Score: {Fore.YELLOW}{result['score']}, {Fore.GREEN}Found Terms: {Fore.MAGENTA}{result['found_terms']}, {Fore.GREEN}Frequency: {Fore.MAGENTA}{result['frequency']}")
        else:
            print(f"{Fore.RED}❌ No results found.")

class REPL:
    def __init__(self, query_engine):
        self.query_engine = query_engine

    def start(self):
        print(f"{Fore.GREEN}💻 REPL started. Type 'exit' to quit.")
        while True:
            command = input(f"{Fore.YELLOW}>>> ")
            if command.lower() == "exit":
                break
            elif command.lower().startswith("query"):
                query = command[6:]
                self.query_engine.query(query)
            else:
                print(f"{Fore.RED}❌ Invalid command.")

if __name__ == "__main__":
    # Create and connect a TOR session
    tor_session = TorSession(tor_password='kiwi')
    tor_session.connect()

    # Initialize the LinkIndex and ReverseContentIndex managers
    link_index_manager = LinkIndexManager()
    reverse_index_manager = ReverseContentIndexManager()

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
        "http://p53lf57qovyuvwsc6xnrppyply3vtqm7l6pcobkmyqsiofyeznfu5uqd.onion",
        "https://www.nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljsciiyd.onion",
        "http://darkzzx4avcsuofgfez5zq75cqc4mprjvfqywo45dfcaxrwqg6qrlfid.onion/"
    ]

    # Initialize and start the link crawler
    crawler = LinkCrawler(tor_session, link_index_manager, reverse_index_manager, seed_urls)
    crawler.start()

    # Initialize the reverse indexer
    indexer = ReverseIndexer(link_index_manager, reverse_index_manager)

    # Initialize the query engine
    query_engine = QueryEngine(indexer)

    # Start REPL for database queries
    repl = REPL(query_engine)
    repl.start()

    # Ensure threads are joined before exiting
    crawler.join()

    print(f"{Fore.BLUE}🔔 JSON-based search engine terminated.")

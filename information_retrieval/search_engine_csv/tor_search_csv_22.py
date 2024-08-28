import aiohttp
import asyncio
import concurrent.futures
import json
import logging
import math
import matplotlib.pyplot as plt
import networkx as nx
import os
import random
import re
import requests
import signal
import ssl
import threading
import time
from bs4 import BeautifulSoup
from collections import defaultdict
from colorama import Fore, Style, init
from copy import deepcopy
from datetime import datetime
from nltk.corpus import stopwords
from stem import Signal
from stem.control import Controller
from urllib.parse import urlparse
from wordcloud import WordCloud

#matplotlib.use('Agg')  # Use 'Agg' backend for headless environments

# Initialize colorama for colorful console output
init(autoreset=True)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ANSI escape sequences for custom RGB colors
# MAGENTA = "\033[38;2;255;0;255m"
# CORAL = "\033[38;2;255;127;80m"
# CYAN = "\033[38;2;0;255;255m"
# YELLOW = "\033[38;2;255;255;0m"
# GREEN = "\033[38;2;0;255;0m"
# BLUE = "\033[38;2;0;0;255m"
# RED = "\033[38;2;255;0;0m"
# RESET = "\033[0m"
MAGENTA = "\033[38;2;127;255;212m"
CORAL = "\033[38;2;244;164;96m" 
CYAN = "\033[38;2;135;206;235m" 
YELLOW = "\033[38;2;255;255;153m"
GREEN = "\033[38;2;102;205;170m"
BLUE = "\033[38;2;70;130;180m"
RED = "\033[38;2;240;128;128m"
RESET = "\033[0m"

class TorSession:
    def __init__(self, tor_password=None, port=9051, proxy_port=9050, pool_connections=100, pool_maxsize=100):
        self.tor_password = tor_password
        self.port = port
        self.proxy_port = proxy_port
        self.session = None
        self.ssl_context = ssl.create_default_context()
        self.pool_connections = pool_connections
        self.pool_maxsize = pool_maxsize
        self.controller = None

    def connect(self):
        attempt = 0
        while self.session is None and attempt < 5:  # Retry connection up to 5 times
            try:
                self.controller = Controller.from_port(port=self.port)
                if self.tor_password:
                    self.controller.authenticate(password=self.tor_password)
                else:
                    self.controller.authenticate()
                self.controller.signal(Signal.NEWNYM)
                print(f"{CYAN}🔗 TOR Session established with SSL support{RESET}")

                self.session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(pool_connections=self.pool_connections, pool_maxsize=self.pool_maxsize)
                self.session.mount('http://', adapter)
                self.session.mount('https://', adapter)
                self.session.proxies = {
                    'http': f'socks5h://127.0.0.1:{self.proxy_port}',
                    'https': f'socks5h://127.0.0.1:{self.proxy_port}'
                }
            except Exception as e:
                print(f"{RED}❗ Error: Failed to connect to TOR: {e}{RESET}")
                attempt += 1
                self.controller = None  # Reset controller on failure
                time.sleep(5)  # Wait before retrying

    def get_session(self):
        if not self.session:
            self.connect()
        return self.session

    def close_controller(self):
        if self.controller:
            try:
                self.controller.close()
                print(f"{YELLOW}⚠️ TOR Controller closed.{RESET}")
            except Exception as e:
                print(f"{RED}❗ Error: Failed to close TOR Controller: {e}{RESET}")

class LinkIndexManager:
    def __init__(self, link_index_file='link_index.json'):
        self.link_index_file = link_index_file
        self.links = []

        if os.path.exists(self.link_index_file):
            with open(self.link_index_file, 'r') as file:
                try:
                    self.links = json.load(file)
                    print(f"{YELLOW}📄 Loaded existing link index from {self.link_index_file}{RESET}")
                except json.JSONDecodeError:
                    print(f"{RED}❗ Error: Failed to load {self.link_index_file}. Initializing a new link index.{RESET}")
                    self.links = []
                    self._save_json()
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
            print(f"{GREEN}✅✅✅ Link indexed: {url} (ID: {next_id}){RESET}")
            return next_id
        except Exception as e:
            print(f"{RED}❗ Error: Failed to insert link: {e}{RESET}")
            return None

    def get_link_id(self, url):
        try:
            for link in self.links:
                if link["url"] == url:
                    return link["id"]
            return None
        except Exception as e:
            print(f"{RED}❗ Error: Failed to get link ID: {e}{RESET}")
            return None

    def get_all_links(self):
        try:
            return self.links
        except Exception as e:
            print(f"{RED}❗ Error: Failed to fetch links: {e}{RESET}")
            return []

class ReverseContentIndexManager:
    def __init__(self, reverse_index_file='reverse_content_index.json'):
        self.reverse_index_file = reverse_index_file
        self.reverse_index = {}

        if os.path.exists(self.reverse_index_file):
            with open(self.reverse_index_file, 'r') as file:
                try:
                    self.reverse_index = json.load(file)
                    print(f"{YELLOW}📂 Loaded existing reverse content index from {self.reverse_index_file}{RESET}")
                except json.JSONDecodeError:
                    print(f"{RED}❗ Error: Failed to load {self.reverse_index_file}. Initializing a new reverse content index.{RESET}")
                    self.reverse_index = {}
                    self._save_json()
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
            print(f"{BLUE}🔍 Reverse index updated for document ID: {doc_id}{RESET}")
        except Exception as e:
            print(f"{RED}❗ Error: Failed to update reverse index: {e}{RESET}")

    def get_reverse_index(self):
        try:
            return self.reverse_index
        except Exception as e:
            print(f"{RED}❗ Error: Failed to fetch reverse index: {e}{RESET}")
            return {}

class LinkRelationshipManager:
    def __init__(self, link_relationship_file='link_relationship.json'):
        self.link_relationship_file = link_relationship_file
        self.link_relationships = defaultdict(list)

        if os.path.exists(self.link_relationship_file):
            with open(self.link_relationship_file, 'r') as file:
                try:
                    self.link_relationships = defaultdict(list, json.load(file))
                    print(f"{YELLOW}📊 Loaded existing link relationships from {self.link_relationship_file}{RESET}")
                except json.JSONDecodeError:
                    print(f"{RED}❗ Error: Failed to load {self.link_relationship_file}. Initializing a new link relationship structure.{RESET}")
                    self.link_relationships = defaultdict(list)
                    self._save_json()
        else:
            self._save_json()

    def _save_json(self):
        with open(self.link_relationship_file, 'w') as file:
            json.dump(self.link_relationships, file, indent=4)

    def add_relationship(self, from_url, to_urls):
        try:
            # Work with a copy to avoid modifying the dictionary during iteration
            current_relationships = deepcopy(self.link_relationships.get(from_url, []))

            # Add the new URLs to the copy
            current_relationships.extend(to_urls)

            # Now update the original dictionary with the modified copy
            self.link_relationships[from_url] = current_relationships
            
            self._save_json()
            print(f"{CYAN}🔗 Relationships added for {from_url}{RESET}")
        except Exception as e:
            print(f"{RED}❗ Error: Failed to add relationships: {e}{RESET}")


class LinkCrawler(threading.Thread):
    def __init__(self, tor_session, link_index_manager, reverse_index_manager, relationship_manager, seed_urls, depth=10, retries=2, discovered_links_file='discovered_onion_links.json', crawled_sites_file='crawled_sites.json'):
        threading.Thread.__init__(self)
        self.session = tor_session.get_session()
        self.link_index_manager = link_index_manager
        self.reverse_index_manager = reverse_index_manager
        self.relationship_manager = relationship_manager
        self.seed_urls = seed_urls
        self.to_crawl = [(url, 0) for url in seed_urls]
        self.depth = depth
        self.retries = retries
        self.discovered_links_file = discovered_links_file
        self.crawled_sites_file = crawled_sites_file
        self.discovered_links = set()
        self.crawled_sites = {}

        self._load_discovered_links()
        self._load_crawled_sites()

    def _load_discovered_links(self):
        if os.path.exists(self.discovered_links_file):
            with open(self.discovered_links_file, 'r') as file:
                self.discovered_links = set(json.load(file))
                print(f"{YELLOW}📂 Loaded existing discovered .onion links from {self.discovered_links_file}{RESET}")

                for link in self.discovered_links:
                    if link not in self.seed_urls:
                        self.seed_urls.append(link)
                        print(f"{CYAN}➕ Added {link} from discovered links to seed URLs{RESET}")
                        self.to_crawl.append((link, 0))

    def _load_crawled_sites(self):
        if os.path.exists(self.crawled_sites_file):
            with open(self.crawled_sites_file, 'r') as file:
                self.crawled_sites = json.load(file)
                print(f"{YELLOW}📂 Loaded existing crawled sites from {self.crawled_sites_file}{RESET}")

    def save_crawled_sites(self):
        with open(self.crawled_sites_file, 'w') as file:
            json.dump(self.crawled_sites, file, indent=4)
        print(f"{GREEN}💾 Saved crawled sites log{RESET}")

    def save_discovered_links(self):
        with open(self.discovered_links_file, 'w') as file:
            json.dump(list(self.discovered_links), file, indent=4)
        print(f"{GREEN}💾 Saved discovered links log{RESET}")

    def sanitize_content(self, text):
        try:
            text = text.lower()
            text = re.sub(r'\W+', ' ', text)
            tokens = text.split()
            stop_words = set(stopwords.words('english'))
            sanitized_tokens = (word for word in tokens if word not in stop_words)
            return ' '.join(sanitized_tokens)
        except Exception as e:
            print(f"{RED}❗ Error: Failed to sanitize content: {e}{RESET}")
            return ""

    def validate_url(self, url):
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        return parsed.netloc.endswith('.onion')

    def exponential_backoff(self, retries):
        base_delay = 5
        max_delay = 300
        delay = min(max_delay, base_delay * math.pow(2, retries))
        return delay

    def crawl(self, url, depth, retries_left=None):
        if retries_left is None:
            retries_left = self.retries

        if not self.validate_url(url):
            print(f"{RED}❗ Error: Invalid or skipped URL: {url}{RESET} ({len(self.seed_urls)} seed URLs, {len(self.to_crawl)} left to crawl)")
            return set()

        if url in self.crawled_sites and self.crawled_sites[url]["status"] == "crawled":
            print(f"{YELLOW}🔄 Skipping already crawled site: {url}{RESET} ({len(self.seed_urls)} seed URLs, {len(self.to_crawl)} left to crawl)")
            return set()

        try:
            start_time = time.time()
            response = self.session.get(url, timeout=120)
            elapsed_time = time.time() - start_time
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text(separator=' ')
            sanitized_text = self.sanitize_content(text)

            title = soup.title.string if soup.title else None
            date = None
            metadata = {}

            doc_id = self.link_index_manager.insert_link(url, sanitized_text, title, date, metadata)
            if doc_id:
                self.reverse_index_manager.update_reverse_index(self.link_index_manager.links[doc_id - 1], doc_id)

            print(f"{GREEN}✅ Crawling successful: {url}{RESET} ({len(self.seed_urls)} seed URLs, {len(self.to_crawl)} left to crawl)")

            self.crawled_sites[url] = {
                "last_checked": time.ctime(),
                "response_time": elapsed_time,
                "result": "success",
                "status": "crawled"
            }
            self.save_crawled_sites()

            links = set()
            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href']
                if self.validate_url(link):
                    if link not in self.discovered_links:
                        print(f"{BLUE}🔍 Discovered new .onion link: {link}{RESET} ({len(self.seed_urls)} seed URLs, {len(self.to_crawl)} left to crawl)")
                        self.discovered_links.add(link)
                        self.save_discovered_links()
                    if link not in self.seed_urls:
                        self.seed_urls.append(link)
                        print(f"{CYAN}➕ Added {link} to seed URLs{RESET} ({len(self.seed_urls)} seed URLs, {len(self.to_crawl)} left to crawl)")
                        self.to_crawl.append((link, depth + 1))
                    links.add(link)

            if links:
                self.relationship_manager.add_relationship(url, links)

            return links
        except requests.exceptions.ConnectionError as e:
            elapsed_time = time.time() - start_time
            print(f"{RED}❗ Connection Error: Failed to crawl {url}: {e}{RESET} ({len(self.seed_urls)} seed URLs, {len(self.to_crawl)} left to crawl)")

            self.crawled_sites[url] = {
                "last_checked": time.ctime(),
                "response_time": elapsed_time,
                "result": str(e),
                "status": "failed"
            }
            self.save_crawled_sites()

            if retries_left > 0:
                retry_delay = self.exponential_backoff(self.retries - retries_left)
                print(f"{YELLOW}🔄 Retrying {url} in {retry_delay:.2f} seconds ({retries_left} retries left){RESET}")
                time.sleep(retry_delay)
                return self.crawl(url, depth, retries_left=retries_left - 1)
            else:
                print(f"{RED}❗ Error: Max retries reached for {url}. Skipping to next URL.{RESET}")
                return set()
        except requests.exceptions.RequestException as e:
            elapsed_time = time.time() - start_time
            print(f"{RED}❗ Error: Failed to crawl {url}: {e}{RESET} ({len(self.seed_urls)} seed URLs, {len(self.to_crawl)} left to crawl)")

            self.crawled_sites[url] = {
                "last_checked": time.ctime(),
                "response_time": elapsed_time,
                "result": str(e),
                "status": "failed"
            }
            self.save_crawled_sites()

            if retries_left > 0:
                retry_delay = self.exponential_backoff(self.retries - retries_left)
                print(f"{YELLOW}🔄 Retrying {url} in {retry_delay:.2f} seconds ({retries_left} retries left){RESET}")
                time.sleep(retry_delay)
                return self.crawl(url, depth, retries_left=retries_left - 1)
            else:
                print(f"{RED}❗ Error: Max retries reached for {url}. Skipping to next URL.{RESET}")
                return set()
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"{RED}❗ Critical Error: {e}{RESET} ({len(self.seed_urls)} seed URLs, {len(self.to_crawl)} left to crawl)")

            self.crawled_sites[url] = {
                "last_checked": time.ctime(),
                "response_time": elapsed_time,
                "result": str(e),
                "status": "failed"
            }
            self.save_crawled_sites()

            return set()

    def run(self):
        while True:
            try:
                if not self.to_crawl:
                    print(f"{YELLOW}🔄 All links crawled. Restarting crawl cycle.{RESET}")
                    for url in self.crawled_sites:
                        self.crawled_sites[url]["status"] = "not crawled"
                    self.seed_urls = list(self.crawled_sites.keys())
                    self.to_crawl = [(url, 0) for url in self.seed_urls]

                # Randomize the seed URLs order and select a subset
                random.shuffle(self.to_crawl)
                subset_to_crawl = random.sample(self.to_crawl, min(10, len(self.to_crawl)))  # Adjust the subset size as needed

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(self.crawl, url, depth) for url, depth in subset_to_crawl]
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            print(f"{RED}❗ Error in thread execution: {e}{RESET}")

                print(f"{BLUE}🌐 Crawling cycle completed. Sleeping before the next cycle...{RESET}")
                time.sleep(10)
            except Exception as e:
                print(f"{RED}❗ Error: LinkCrawler encountered an error: {e}{RESET}")
                time.sleep(5)  # Wait before restarting


class SearchEngineCrawler(threading.Thread):
    def __init__(self, tor_session, link_index_manager, reverse_index_manager, search_engines, query_interval=300, discovered_links_file='discovered_onion_links.json'):
        threading.Thread.__init__(self)
        self.session = tor_session.get_session()
        self.link_index_manager = link_index_manager
        self.reverse_index_manager = reverse_index_manager
        self.search_engines = search_engines
        self.query_interval = query_interval
        self.discovered_links_file = discovered_links_file
        self.discovered_links = set()
        self.used_terms = set()  # To keep track of used search terms

        self._load_discovered_links()

    def _load_discovered_links(self):
        if os.path.exists(self.discovered_links_file):
            with open(self.discovered_links_file, 'r') as file:
                self.discovered_links = set(json.load(file))
                print(f"{YELLOW}📂 Loaded existing discovered .onion links from {self.discovered_links_file}{RESET}")

    def extract_onion_links(self, text):
        # Regex to detect .onion links
        pattern = r'https?://[a-zA-Z0-9]{16,56}\.onion\b'
        return re.findall(pattern, text)

    def save_discovered_links(self):
        if os.path.exists(self.discovered_links_file):
            with open(self.discovered_links_file, 'r') as file:
                existing_links = set(json.load(file))
        else:
            existing_links = set()

        existing_links.update(self.discovered_links)

        with open(self.discovered_links_file, 'w') as file:
            json.dump(list(existing_links), file, indent=4)
        
        print(f"{GREEN}💾 Saved discovered links to {self.discovered_links_file}{RESET}")

    def get_random_term(self):
        reverse_index = self.reverse_index_manager.get_reverse_index()
        unused_terms = set(reverse_index.keys()) - self.used_terms
        
        if not unused_terms:
            print(f"{RED}❗ Error: No unused search terms available!{RESET}")
            return None
        
        search_term = random.choice(list(unused_terms))
        self.used_terms.add(search_term)
        return search_term

    def perform_search(self, search_engine_url, search_term):
        try:
            query_url = search_engine_url.replace('SEARCH_TERM', search_term)
            print(f"{CYAN}🔍🔍🔍 Querying URL: {query_url}{RESET}")
            
            response = self.session.get(query_url, timeout=120)
            print(f"{YELLOW}🔍 Response Status Code: {response.status_code}{RESET}")
            
            if response.status_code == 200:
                print(f"{GREEN}✅ Valid search page returned from {query_url}{RESET}")
            else:
                print(f"{YELLOW}⚠️ Search page returned status code {response.status_code} for {query_url}{RESET}")
                return set()

            print(f"{CYAN}🔍🔍🔍 Response Content Snippet: {response.text[1000:1500]}{RESET}")

            soup = BeautifulSoup(response.content, 'html.parser')
            links = set()

            a_tags = list(soup.find_all('a', href=True))

            for a_tag in a_tags:
                link = a_tag['href']
                onion_links = self.extract_onion_links(link)
                for onion_link in onion_links:
                    if onion_link not in self.discovered_links:
                        print(f"{BLUE}🔗 Discovered new .onion link: {onion_link}{RESET}")
                        self.discovered_links.add(onion_link)
                        self.save_discovered_links()  
                        print(f"{GREEN}💾 Added {onion_link} to {self.discovered_links_file}{RESET}")
                        links.add(onion_link)

            return links
        except Exception as e:
            print(f"{RED}❗ Error: Failed to perform search on {search_engine_url} with term '{search_term}': {e}{RESET}")
            return set()

    def run(self):
        while True:
            try:
                search_term = self.get_random_term()
                if search_term:
                    search_engine_url = random.choice(self.search_engines)
                    print(f"{CYAN}🔍 Performing search with term: {search_term} on {search_engine_url}{RESET}")
                    links = self.perform_search(search_engine_url, search_term)

                    for link in links:
                        print(f"{BLUE}🔗 Found and saved link: {link}{RESET}")

                time.sleep(self.query_interval)  
            except Exception as e:
                print(f"{RED}❗ Error: SearchEngineCrawler encountered an error: {e}{RESET}")
                time.sleep(10)


class ReverseIndexer(threading.Thread):
    def __init__(self, link_index_manager, reverse_index_manager):
        threading.Thread.__init__(self)
        self.link_index_manager = link_index_manager
        self.reverse_index_manager = reverse_index_manager
        self.indexing_complete = False

    def calculate_idf(self, term):
        try:
            doc_count = len(self.link_index_manager.get_all_links())
            term_docs = len(self.reverse_index_manager.get_reverse_index().get(term, {}))
            return math.log(doc_count / (1 + term_docs))
        except Exception as e:
            print(f"{RED}❗ Error: Failed to calculate IDF for term {term}: {e}{RESET}")
            return 0.0

    def calculate_tfidf(self, term, doc_id):
        try:
            tf = len(self.reverse_index_manager.get_reverse_index().get(term, {}).get(doc_id, []))
            idf = self.calculate_idf(term)
            return tf * idf
        except Exception as e:
            print(f"{RED}❗ Error: Failed to calculate TF-IDF for term {term} in doc {doc_id}: {e}{RESET}")
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
            print(f"{RED}❗ Error: Failed to rank websites for query '{query}': {e}{RESET}")
            return []

    def run(self):
        while True:
            try:
                self.indexing_complete = False
                self.rank_websites('')  # Trigger indexing (adjust logic as needed)
                self.indexing_complete = True
                print(f"{GREEN}📊 Indexing completed.{RESET}")
                time.sleep(30)
            except Exception as e:
                print(f"{RED}❗ Error: ReverseIndexer encountered an error: {e}{RESET}")
                time.sleep(5)  # Wait before restarting

class VisualizationManager(threading.Thread):
    def __init__(self, reverse_index_manager, relationship_manager):
        threading.Thread.__init__(self)
        self.reverse_index_manager = reverse_index_manager
        self.relationship_manager = relationship_manager
        # List of colormaps
        self.colormaps = [
            'Accent', 'Accent_r', 'Blues', 'Blues_r', 'BrBG', 'BrBG_r', 'BuGn', 'BuGn_r', 'BuPu', 'BuPu_r', 'CMRmap', 'CMRmap_r', 'Dark2', 'Dark2_r', 'GnBu', 'GnBu_r', 'Grays', 'Greens', 'Greens_r', 'Greys', 'Greys_r', 'OrRd', 'OrRd_r', 'Oranges', 'Oranges_r', 'PRGn', 'PRGn_r', 'Paired', 'Paired_r', 'Pastel1', 'Pastel1_r', 'Pastel2', 'Pastel2_r', 'PiYG', 'PiYG_r', 'PuBu', 'PuBuGn', 'PuBuGn_r', 'PuBu_r', 'PuOr', 'PuOr_r', 'PuRd', 'PuRd_r', 'Purples', 'Purples_r', 'RdBu', 'RdBu_r', 'RdGy', 'RdGy_r', 'RdPu', 'RdPu_r', 'RdYlBu', 'RdYlBu_r', 'RdYlGn', 'RdYlGn_r', 'Reds', 'Reds_r', 'Set1', 'Set1_r', 'Set2', 'Set2_r', 'Set3', 'Set3_r', 'Spectral', 'Spectral_r', 'Wistia', 'Wistia_r', 'YlGn', 'YlGnBu', 'YlGnBu_r', 'YlGn_r', 'YlOrBr', 'YlOrBr_r', 'YlOrRd', 'YlOrRd_r', 'afmhot', 'afmhot_r', 'autumn', 'autumn_r', 'binary', 'binary_r', 'bone', 'bone_r', 'brg', 'brg_r', 'bwr', 'bwr_r', 'cividis', 'cividis_r', 'cool', 'cool_r', 'coolwarm', 'coolwarm_r', 'copper', 'copper_r', 'cubehelix', 'cubehelix_r', 'flag', 'flag_r', 'gist_earth', 'gist_earth_r', 'gist_gray', 'gist_gray_r', 'gist_grey', 'gist_heat', 'gist_heat_r', 'gist_ncar', 'gist_ncar_r', 'gist_rainbow', 'gist_rainbow_r', 'gist_stern', 'gist_stern_r', 'gist_yarg', 'gist_yarg_r', 'gist_yerg', 'gnuplot', 'gnuplot2', 'gnuplot2_r', 'gnuplot_r', 'gray', 'gray_r', 'grey', 'hot', 'hot_r', 'hsv', 'hsv_r', 'inferno', 'inferno_r', 'jet', 'jet_r', 'magma', 'magma_r', 'nipy_spectral', 'nipy_spectral_r', 'ocean', 'ocean_r', 'pink', 'pink_r', 'plasma', 'plasma_r', 'prism', 'prism_r', 'rainbow', 'rainbow_r', 'seismic', 'seismic_r', 'spring', 'spring_r', 'summer', 'summer_r', 'tab10', 'tab10_r', 'tab20', 'tab20_r', 'tab20b', 'tab20b_r', 'tab20c', 'tab20c_r', 'terrain', 'terrain_r', 'turbo', 'turbo_r', 'twilight', 'twilight_r', 'twilight_shifted', 'twilight_shifted_r', 'viridis', 'viridis_r', 'winter', 'winter_r'
        ]

    def create_term_cloud(self):
        try:
            word_frequencies = defaultdict(int)
            reverse_index = self.reverse_index_manager.get_reverse_index()

            if not reverse_index:
                print(f"{YELLOW}⚠️ Reverse index is empty. Term cloud cannot be generated.{RESET}")
                return

            for term, doc_data in reverse_index.items():
                word_frequencies[term] += len(doc_data)

            print(f"{CYAN}🔍 Word Frequencies: {len(word_frequencies)} terms collected{RESET}")

            color = random.choice(self.colormaps)
            wordcloud = WordCloud(width=5000, height=5000, background_color="black", colormap=color).generate_from_frequencies(word_frequencies)
            
            output_path = "term_cloud.png"
            print(f"🧑‍🎨 Saving word cloud to {output_path}")
            wordcloud.to_file(output_path)

            if os.path.exists(output_path):
                print(f"{GREEN}✅ term_cloud.png successfully saved.{RESET}")
            else:
                print(f"{RED}❗ Error: term_cloud.png was not saved correctly.{RESET}")

        except Exception as e:
            print(f"{RED}🧑‍🎨❗ Error: Failed to create term cloud: {e}{RESET}")

    def create_link_cloud(self):
        try:
            relationship_snapshot = dict(self.relationship_manager.link_relationships)
            G = nx.Graph()
            for from_url, to_urls in relationship_snapshot.items():
                from_node = f"{from_url}"
                for to_url in to_urls:
                    to_node = f"{to_url}"
                    G.add_edge(from_node, to_node)

            num_nodes = len(G.nodes())
            figsize = (min(50, 10 * num_nodes), min(50, 10 * num_nodes))
            figsize = (min(figsize[0], 50), min(figsize[1], 50))

            plt.figure(figsize=figsize)
            pos = nx.spring_layout(G, k=0.1, iterations=50)
            node_sizes = [len(relationship_snapshot.get(node, [])) * 10 for node in G.nodes()]

            for node, (x, y) in pos.items():
                plt.text(x, y, s=node, fontsize=10, color="yellow", ha='center', va='center', alpha=0.2)

            nx.draw(G, pos, with_labels=False, node_size=node_sizes, edge_color="white", node_color="red", linewidths=0.5)
            plt.gca().set_facecolor("black")

            output_path = "link_cloud.png"
            print(f"🧑‍🎨 Saving link cloud to {output_path}")
            plt.savefig(output_path, facecolor="black", dpi=min(5000/figsize[0], 5000/figsize[1]))
            plt.close()

            if os.path.exists(output_path):
                print(f"{GREEN}✅ Link cloud generated and saved as {output_path}{RESET}")
            else:
                print(f"{RED}❗ Error: Failed to save the link cloud. File does not exist after saving attempt.{RESET}")

        except Exception as e:
            print(f"{RED}🧑‍🎨❗ Error: Failed to create link cloud: {e}{RESET}")

    def run(self):
        while True:
            try:
                self.create_term_cloud()
                self.create_link_cloud()
                time.sleep(60)
            except Exception as e:
                print(f"{RED}🧑‍🎨❗ Error: VisualizationManager encountered an error: {e}{RESET}")
                time.sleep(30)


class KPIManager(threading.Thread):
    def __init__(self, link_index_manager, reverse_index_manager, relationship_manager, kpi_file='kpis.json'):
        threading.Thread.__init__(self)
        self.link_index_manager = link_index_manager
        self.reverse_index_manager = reverse_index_manager
        self.relationship_manager = relationship_manager
        self.kpi_file = kpi_file

        # Initialize KPI storage
        if not os.path.exists(self.kpi_file):
            self._initialize_kpi_file()

    def _initialize_kpi_file(self):
        with open(self.kpi_file, 'w') as file:
            json.dump([], file, indent=4)

    def calculate_kpis(self):
        try:
            total_links = len(self.link_index_manager.get_all_links())
            total_terms = len(self.reverse_index_manager.get_reverse_index())
            total_relationships = sum(len(urls) for urls in self.relationship_manager.link_relationships.values())
            mean_response_time = self._calculate_mean_response_time()
            mutual_link_ratio = self._calculate_mutual_link_ratio()
            link_loops_count = self._count_link_loops()

            kpis = {
                "timestamp": datetime.now().isoformat(),
                "total_links_indexed": total_links,
                "total_terms_indexed": total_terms,
                "total_relationships_indexed": total_relationships,
                "mean_response_time": mean_response_time,
                "mutual_link_ratio": mutual_link_ratio,
                "link_loops_count": link_loops_count
            }

            print(f"{CYAN}📊 Calculated KPIs: {kpis}{RESET}")

            return kpis
        except Exception as e:
            print(f"{RED}❗ Error: Failed to calculate KPIs: {e}{RESET}")
            return None

    def _calculate_mean_response_time(self):
        try:
            response_times = [site["response_time"] for site in self.link_index_manager.crawled_sites.values() if "response_time" in site]
            if response_times:
                return sum(response_times) / len(response_times)
            return 0
        except Exception as e:
            print(f"{RED}❗ Error: Failed to calculate mean response time: {e}{RESET}")
            return 0

    def _calculate_mutual_link_ratio(self):
        try:
            mutual_links = 0
            total_links = 0

            for from_url, to_urls in self.relationship_manager.link_relationships.items():
                for to_url in to_urls:
                    total_links += 1
                    if to_url in self.relationship_manager.link_relationships and from_url in self.relationship_manager.link_relationships[to_url]:
                        mutual_links += 1

            if total_links > 0:
                return mutual_links / total_links
            return 0
        except Exception as e:
            print(f"{RED}❗ Error: Failed to calculate mutual link ratio: {e}{RESET}")
            return 0

    def _count_link_loops(self):
        try:
            link_loops = 0
            for from_url, to_urls in self.relationship_manager.link_relationships.items():
                if from_url in to_urls:
                    link_loops += 1
            return link_loops
        except Exception as e:
            print(f"{RED}❗ Error: Failed to count link loops: {e}{RESET}")
            return 0

    def store_kpis(self, kpis):
        try:
            if kpis:
                with open(self.kpi_file, 'r+') as file:
                    data = json.load(file)
                    data.append(kpis)
                    file.seek(0)
                    json.dump(data, file, indent=4)
                print(f"{GREEN}💾 KPIs saved to {self.kpi_file}{RESET}")
        except Exception as e:
            print(f"{RED}❗ Error: Failed to save KPIs: {e}{RESET}")

    def run(self):
        while True:
            try:
                kpis = self.calculate_kpis()
                self.store_kpis(kpis)
                time.sleep(60)  # Repeat every 60 seconds
            except Exception as e:
                print(f"{RED}❗ Error: KPIManager encountered an error: {e}{RESET}")
                time.sleep(60)  # Wait before retrying



class QueryEngine:
    def __init__(self, reverse_indexer):
        self.reverse_indexer = reverse_indexer

    def query(self, search_terms):
        results = self.reverse_indexer.rank_websites(search_terms)
        if results:
            print(f"{CYAN}🔍 Query results:{RESET}")
            for result in results:
                print(
                    f"{GREEN}🌐 Site: {MAGENTA}{result['site_name']}, ",
                    f"{GREEN}URL: {CYAN}{result['link_url']}, ",
                    f"{GREEN}Score: {YELLOW}{result['score']}, ",
                    f"{GREEN}Terms Found: {CORAL}{result['found_terms']}, ",
                    f"{GREEN}Frequency: {CORAL}{result['frequency']}{RESET}"
                )
        else:
            print(f"{RED}❗ No results found.{RESET}")

class REPL:
    def __init__(self, query_engine):
        self.query_engine = query_engine

    def start(self):
        print(f"{GREEN}💻 REPL started. Type 'exit' to quit.{RESET}")
        while True:
            command = input(f"{YELLOW}>>> {RESET}")
            if command.lower() == "exit":
                break
            elif command.lower().startswith("query"):
                query = command[6:]
                self.query_engine.query(query)
            else:
                print(f"{RED}❗ Invalid command.{RESET}")


def handle_exit_signal(signum, frame):
    print(f"{RED}❗ Exiting gracefully...{RESET}")
    raise SystemExit()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)

    tor_session = TorSession(tor_password='kiwi')
    tor_session.connect()

    link_index_manager = LinkIndexManager()
    reverse_index_manager = ReverseContentIndexManager()
    relationship_manager = LinkRelationshipManager()

    seed_urls = [
        "http://darkzzx4avcsuofgfez5zq75cqc4mprjvfqywo45dfcaxrwqg6qrlfid.onion/",
        "http://kx5thpx2olielkihfyo4jgjqfb7zx7wxr3sd4xzt26ochei4m6f7tayd.onion",
        "http://darkzzx4avcsuofgfez5zq75cqc4mprjvfqywo45dfcaxrwqg6qrlfid.onion",
        "http://anonyradixhkgh5myfrkarggfnmdzzhhcgoy2v66uf7sml27to5n2tid.onion",
        "http://ciadotgov4sjwlzihbbgxnqg3xiyrg7so2r2o3lt5wz5ypk4sxyjstad.onion",
        "https://github.com/alecmuffett/real-world-onion-sites?tab=readme-ov-file",
        "https://gitlab.torproject.org/legacy/trac/-/wikis/org/projects/WeSupportTor",
        "http://rambleeeqrhty6s5jgefdfdtc6tfgg4jj6svr4jpgk4wjtg3qshwbaad.onion/",
        "http://vww6ybal4bd7szmgncyruucpgfkqahzddi37ktceo3ah7ngmcopnpyyd.onion/",
        "https://27m3p2uv7igmj6kvd4ql3cct5h3sdwrsajovkkndeufumzyfhlfev4qd.onion/",
        "http://danielas3rtn54uwmofdo3x2bsdifr47huasnmbgqzfrec5ubupvtpid.onion/",
        "http://torlinksge6enmcyyuxjpjkoouw4oorgdgeo7ftnq3zodj7g2zxi3kyd.onion/",
        "http://zqktlwiuavvvqqt4ybvgvi7tyo4hjl5xgfuvpdf6otjiycgwqbym2qad.onion/",
        "http://answerszuvs3gg2l64e6hmnryudl5zgrmwm3vh65hzszdghblddvfiqd.onion/",
        "http://libraryfyuybp7oyidyya3ah5xvwgyx6weauoini7zyz555litmmumad.onion",
        "http://nv3x2jozywh63fkohn5mwp2d73vasusjixn3im3ueof52fmbjsigw6ad.onion",
        "http://darkfailenbsdla5mal2mxn2uz66od5vtzd5qozslagrfzachha3f3id.onion",
        "http://dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion ",
        "http://p53lf57qovyuvwsc6xnrppyply3vtqm7l6pcobkmyqsiofyeznfu5uqd.onion",
        "http://darkzzx4avcsuofgfez5zq75cqc4mprjvfqywo45dfcaxrwqg6qrlfid.onion/",
        "http://p53lf57qovyuvwsc6xnrppyply3vtqm7l6pcobkmyqsiofyeznfu5uqd.onion",
    ]

    # "https://www.bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion",
    # "https://www.nytimesn7cgmftshazwhfgzm37qxb44r64ytbb2dj3x62d2lljsciiyd.onion",

    # Search Engine URLs with SEARCH_TERM placeholder
    search_engines = [
        'http://xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5aygthi7d6rplyvk3noyd.onion/cgi-bin/omega/omega?P=SEARCH_TERM', # Torch
        'http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q=SEARCH_TERM',  # Ahmia - works but man in the middle
    ]


    random.seed(time.time())
    random.shuffle(seed_urls)

    crawler = LinkCrawler(tor_session, link_index_manager, reverse_index_manager, relationship_manager, seed_urls)
    visualization_manager = VisualizationManager(reverse_index_manager, relationship_manager)
    kpi_manager = KPIManager(link_index_manager, reverse_index_manager, relationship_manager)

    search_engine_crawler = SearchEngineCrawler(tor_session, link_index_manager, reverse_index_manager, search_engines)
    search_engine_crawler.start()

    crawler.start()
    visualization_manager.start()
    kpi_manager.start()

    crawler.join()
    visualization_manager.join()
    kpi_manager.join()
    search_engine_crawler.join()

    tor_session.close_controller()

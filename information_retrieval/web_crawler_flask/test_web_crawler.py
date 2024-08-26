
import unittest
from datetime import datetime, timedelta
from main_script import TorSession, DatabaseManager, LinkCrawler, ReverseIndexer, QueryEngine, UptimeRetriever

class TestTorSession(unittest.TestCase):
    def test_connection(self):
        tor_session = TorSession(tor_password='test_password')
        tor_session.connect()
        self.assertIsNotNone(tor_session.get_session(), "Failed to connect to TOR")

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_name="test_web_crawler.db")

    def tearDown(self):
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS links")
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS link_relations")
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS link_checks")
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS link_uptime")
        self.db_manager.close()

    def test_create_tables(self):
        self.db_manager.create_tables()
        self.db_manager.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = self.db_manager.cursor.fetchall()
        self.assertTrue(len(tables) >= 4, "Not all tables were created")

    def test_insert_link(self):
        link_id = self.db_manager.insert_link("http://example.com", "Example content")
        self.assertIsNotNone(link_id, "Failed to insert link")

    def test_log_link_check(self):
        link_id = self.db_manager.insert_link("http://example.com", "Example content")
        self.db_manager.log_link_check(link_id, success=True)
        self.db_manager.cursor.execute("SELECT * FROM link_checks WHERE link_id=?", (link_id,))
        log = self.db_manager.cursor.fetchone()
        self.assertIsNotNone(log, "Failed to log link check")

    def test_calculate_mean_uptime(self):
        link_id = self.db_manager.insert_link("http://example.com", "Example content")
        period_start = datetime.now() - timedelta(days=1)
        period_end = datetime.now()
        self.db_manager.log_link_check(link_id, success=True)
        self.db_manager.log_link_check(link_id, success=False)
        mean_uptime = self.db_manager.calculate_mean_uptime(link_id, period_start, period_end)
        self.assertTrue(0 <= mean_uptime <= 1, "Mean uptime calculation failed")

class TestLinkCrawler(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_name="test_web_crawler.db")
        self.tor_session = TorSession(tor_password='test_password')
        self.tor_session.connect()

    def tearDown(self):
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS links")
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS link_relations")
        self.db_manager.close()

    def test_crawl(self):
        crawler = LinkCrawler(self.tor_session, self.db_manager, seed_urls=["http://example.com"], verbose=False)
        links = crawler.crawl("http://example.com")
        self.assertIsInstance(links, set, "Crawling failed to return a set of links")

class TestReverseIndexer(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_name="test_web_crawler.db")
        self.db_manager.insert_link("http://example.com", "Example content")

    def tearDown(self):
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS links")
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS link_relations")
        self.db_manager.close()

    def test_create_reverse_index(self):
        indexer = ReverseIndexer(self.db_manager)
        indexer.create_reverse_index()
        self.assertIsNotNone(indexer.vectorizer, "Failed to create reverse index")

class TestUptimeRetriever(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_name="test_web_crawler.db")
        self.link_id = self.db_manager.insert_link("http://example.com", "Example content")

    def tearDown(self):
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS links")
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS link_relations")
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS link_checks")
        self.db_manager.cursor.execute("DROP TABLE IF EXISTS link_uptime")
        self.db_manager.close()

    def test_get_uptime(self):
        period_start = datetime.now() - timedelta(days=1)
        period_end = datetime.now()
        self.db_manager.log_link_check(self.link_id, success=True)
        self.db_manager.log_link_check(self.link_id, success=False)
        uptime_retriever = UptimeRetriever(self.db_manager)
        uptime = uptime_retriever.get_uptime(self.link_id, period_start, period_end)
        self.assertTrue(0 <= uptime <= 1, "Uptime retrieval failed")

if __name__ == "__main__":
    unittest.main()
        

from flask import Flask, render_template, request, redirect, url_for
from main_script import DatabaseManager, QueryEngine, UptimeRetriever, ReverseIndexer, LinkCrawler, TorSession

app = Flask(__name__)
db_manager = DatabaseManager(verbose=False)
tor_session = TorSession(tor_password='YOUR_TOR_PASSWORD', verbose=False)
tor_session.connect()
crawler = LinkCrawler(tor_session, db_manager, seed_urls=["http://example.com"], verbose=False)
indexer = ReverseIndexer(db_manager, verbose=False)
query_engine = QueryEngine(indexer, verbose=False)
uptime_retriever = UptimeRetriever(db_manager)


@app.route('/')
def dashboard():
    total_links = len(db_manager.get_all_links())
    return render_template('dashboard.html', total_links=total_links)


@app.route('/manage_links')
def manage_links():
    links = db_manager.get_all_links()
    return render_template('manage_links.html', links=links)


@app.route('/run_crawler', methods=['POST'])
def run_crawler():
    crawler.start()
    return redirect(url_for('dashboard'))


@app.route('/query', methods=['GET', 'POST'])
def query():
    if request.method == 'POST':
        search_terms = request.form['search_terms']
        results = query_engine.query(search_terms)
        return render_template('query.html', results=results)
    return render_template('query.html')


@app.route('/uptime/<int:link_id>')
def uptime(link_id):
    period_start = request.args.get('start', datetime.now() - timedelta(days=7))
    period_end = request.args.get('end', datetime.now())
    uptime = uptime_retriever.get_uptime(link_id, period_start, period_end)
    return f"Mean uptime for link {link_id}: {uptime:.2f}"


if __name__ == "__main__":
    import unittest
    unittest.main(module='test_web_crawler', exit=False)
    app.run(debug=True)
        
# Tor Crawler and Indexer

This project is a comprehensive Python-based crawler and indexer designed to explore, crawl, and index hidden services on the Tor network (".onion" sites). The system can analyze and visualize relationships between different sites, generate reverse content indices, and provide TF-IDF based search capabilities over the crawled content.

![Screenshot of the app](img/link_cloud2.png)

## Features

- **Tor Integration**: Establishes a secure session over the Tor network to anonymously crawl `.onion` sites.
- **Crawling Mechanism**: A robust multi-threaded crawler that can handle retries, validate URLs, and avoid crawling already indexed sites.
- **Content Indexing**: Indexes the content of crawled sites, creating a reverse index for fast search and retrieval.
- **Link Relationship Mapping**: Captures and maps relationships between different `.onion` links discovered during the crawl.
- **TF-IDF Based Search**: Implements a simple search engine using TF-IDF to rank indexed pages based on query relevance.
- **Visualization**: Generates visual representations of term frequency (word clouds) and site relationships (network graphs).

![Screenshot of the app](img/output1.png)

## Key Components

- **TorSession**: Manages the connection to the Tor network, establishing a secure session for crawling `.onion` sites.
  
- **LinkCrawler**: Crawls the dark web, discovering new `.onion` links, indexing content, and managing relationships between links.

- **SearchEngineCrawler**: Queries dark web search engines to discover additional `.onion` links.

- **LinkIndexManager**: Handles storing and retrieving indexed links.

- **ReverseContentIndexManager**: Manages the reverse index, mapping search terms to the documents in which they appear.

- **LinkRelationshipManager**: Tracks relationships between different `.onion` sites, such as mutual links and loops.

- **KPIManager**: Calculates and stores KPIs, such as:
  - Mean response time of crawled sites
  - Ratio of mutual links
  - Count of link loops where a link points to itself
  - Total number of links indexed
  - Total number of terms indexed

- **VisualizationManager**: Generates word clouds and link graphs to visualize the indexed content and relationships.

- **REPL and QueryEngine**: Provides an interactive shell for querying the indexed data.


![Screenshot of the app](img/term_cloud.png)

## Installation

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/yourusername/tor-crawler-indexer.git
    cd tor-crawler-indexer
    ```

2. **Install Dependencies**:
    Ensure you have Python 3.x installed. Install the required Python packages using pip:

3. **Configure Tor Authentication Cookie**:
    Before running the crawler, make sure that the Tor authentication cookie is properly configured. This is essential for establishing a secure session with the Tor network. You can typically find the `control_auth_cookie` in the Tor data directory, often located at `/var/lib/tor`. Ensure that your TorSession class is configured to read this cookie.

4. **Run the Crawler**:
    Ensure you have the Tor service running on your system. Start the crawler by running the main script:
    ```bash
    python tor_search_csv_xx.py
    ```

## Usage

- **Starting the Crawler**: The crawler starts automatically and begins to explore the `.onion` sites listed in the seed URLs. It indexes the content and discovers new links recursively.

- **Querying the Index**: Use the REPL to interact with the indexed data. Type `query <search terms>` to search the index.

- **Visualization**: The system automatically generates visualizations of the data, including term clouds and link clouds, saved as `term_cloud.png` and `link_cloud.png` respectively.

## Files

- **tor_search_csv_14.py**: The main script containing all the classes and logic for crawling, indexing, and visualization.
- **link_index.json**: Stores the indexed data of crawled links.
- **reverse_content_index.json**: Contains the reverse index of terms used for search queries.
- **link_relationship.json**: Tracks the discovered relationships between different `.onion` sites.
- **discovered_onion_links.json**: Logs all `.onion` links discovered during the crawl.
- **crawled_sites.json**: Stores metadata about the sites that have been crawled, including their status and response times.
- **term_cloud.png**: A visual representation of the most common terms in the indexed content.
- **link_cloud.png**: A network graph showing the interconnections between discovered `.onion` sites.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.


# Tor Crawler and Indexer

This project is a multi-threaded crawler designed to explore `.onion` websites on the Tor network. It indexes the content of these sites, tracks relationships between them, and generates visual representations such as link clouds and term clouds. The system also provides real-time querying and visualization of the indexed data.

## Features

- **Tor Integration**: Connects to the Tor network using a SOCKS proxy with SSL support.
- **Link Indexing**: Indexes URLs, content, titles, dates, and metadata from crawled `.onion` sites.
- **Reverse Content Indexing**: Creates an index of terms found in the content, tracking their positions within documents.
- **Link Relationships**: Tracks and stores the relationships between different `.onion` sites based on hyperlinks.
- **Visualization**: Generates visual representations of link relationships (link cloud) and term frequencies (term cloud).
- **Real-time Querying**: Provides a REPL (Read-Eval-Print Loop) for querying the indexed data in real-time.
- **Error Handling**: Robust error handling with retries and exponential backoff strategies.
- **Graceful Shutdown**: Includes signal handling for clean termination.

## Components

### 1. TorSession
- **Purpose**: Manages the connection to the Tor network.
- **Key Features**:
  - Handles SSL connections.
  - Reconnects if the session is lost.
  - Configurable retry attempts for establishing the connection.

### 2. LinkIndexManager
- **Purpose**: Manages the indexing of URLs and their associated content.
- **Key Features**:
  - Stores link details such as URL, content, title, date, and metadata.
  - Efficiently retrieves link data by ID.

### 3. ReverseContentIndexManager
- **Purpose**: Creates and manages an index of terms found in the content of crawled sites.
- **Key Features**:
  - Tracks the position of terms within documents.
  - Supports efficient querying of term positions across multiple documents.

### 4. LinkRelationshipManager
- **Purpose**: Manages the relationships between sites based on hyperlinks.
- **Key Features**:
  - Stores relationships between URLs.
  - Generates visualizations of these relationships as a link cloud.

### 5. LinkCrawler
- **Purpose**: Crawls the web, starting with a set of seed URLs.
- **Key Features**:
  - Handles retries and errors using exponential backoff.
  - Tracks and logs the crawling process, including discovered links.
  - Multi-threaded for efficient crawling.

### 6. ReverseIndexer
- **Purpose**: Computes TF-IDF scores for terms in the indexed content.
- **Key Features**:
  - Ranks websites based on relevance to query terms.
  - Supports real-time indexing and updating of the reverse index.

### 7. VisualizationManager
- **Purpose**: Generates visual representations of the crawled data.
- **Key Features**:
  - Creates and updates term clouds and link clouds.
  - Saves visualizations as `.png` files for further analysis.

### 8. QueryEngine
- **Purpose**: Allows querying of the indexed data.
- **Key Features**:
  - Supports real-time queries through a REPL interface.
  - Displays search results with relevant metadata.

### 9. REPL
- **Purpose**: Provides a command-line interface for querying the data.
- **Key Features**:
  - Simple commands for querying indexed data.
  - Graceful handling of invalid commands.

## Workflows

1. **Crawling**: The `LinkCrawler` starts with a set of seed URLs and explores linked `.onion` sites up to a specified depth. Discovered links are dynamically added to the queue, and results are indexed.

2. **Indexing**: As content is crawled, the `LinkIndexManager` and `ReverseContentIndexManager` store the data, creating a searchable index of content and link relationships.

3. **Visualization**: The `VisualizationManager` periodically updates visual representations of the indexed data, saving images of term clouds and link clouds.

4. **Querying**: The `QueryEngine` processes user queries in real-time, providing insights based on the indexed data.

5. **Error Handling**: The system is designed to handle connection issues, retries, and other errors gracefully, ensuring continuous operation.

## Strengths

- **Scalable**: Multi-threaded design allows for efficient crawling and processing of large amounts of data.
- **Robust**: Comprehensive error handling and retry mechanisms ensure resilience against network issues.
- **Real-Time**: The REPL interface allows for real-time interaction with the indexed data.
- **Visual Insights**: Automatically generates useful visual representations of the data.

## Weaknesses

- **Resource Intensive**: Multi-threading and constant crawling can be resource-intensive, especially on limited hardware.
- **Dependency on Tor**: The system's performance and reliability are tied to the Tor network's stability.

## Opportunities

- **Scalability Improvements**: Transitioning to a database system (like SQLite) could improve performance and scalability.
- **Enhanced Visualization**: More sophisticated visualizations (e.g., interactive graphs) could be added.
- **Machine Learning**: Integrating machine learning models could improve the ranking of websites and the relevance of search results.

## Threats

- **Network Instability**: Tor network instability could impact the crawler's effectiveness.
- **Legal Concerns**: Crawling `.onion` sites might involve legal risks depending on jurisdiction.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/your-repo.git

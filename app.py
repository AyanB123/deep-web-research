import streamlit as st
import os
import time
import datetime
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import io
import base64
import json

from config import Config
from agent import ResearchAgent
from utils import log_action
from onion_database import OnionLinkDatabase
from enhanced_crawler import EnhancedTorCrawler
from seed_data import seed_initial_directories, verify_seed_links

# Initialize required directories
Config.init_directories()

# Setup the Streamlit page
st.set_page_config(page_title="Tor Deep Research Agent", layout="wide")
st.title("🕵️‍♀️ Tor Web Deep Research Agent")
st.markdown("Unleash a powerful AI to explore the dark web's depths using our comprehensive discovery system.")

# Initialize and check database on startup
def initialize_database():
    """Initialize the onion link database and seed it if necessary."""
    db = OnionLinkDatabase()
    stats = db.get_statistics()
    
    # Check if database is empty and needs seeding
    if stats["total_links"] == 0:
        with st.spinner("Initializing onion link database with seed data..."):
            seed_initial_directories(db)
            st.success(f"Database initialized with seed data")
    
    # Store database stats in session state
    st.session_state["db_stats"] = stats
    db.close()
    return stats

# Initialize database if not already done
if "db_initialized" not in st.session_state:
    initialize_database()
    st.session_state["db_initialized"] = True

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    
    # AI Model Configuration
    st.subheader("AI Model")
    model_choice = st.selectbox("Gemini Model", Config.GEMINI_MODELS, index=Config.GEMINI_MODELS.index(Config.DEFAULT_MODEL))
    
    # Tor Network Configuration
    st.subheader("Tor Network")
    tor_enabled = st.checkbox("Enable Tor Network", value=True)
    
    # Check Tor connection status if enabled
    if tor_enabled:
        if "tor_status" not in st.session_state or st.button("Check Tor Connection"):
            with st.spinner("Checking Tor connection..."):
                from enhanced_crawler import EnhancedTorCrawler
                crawler = EnhancedTorCrawler()
                crawler.start_tor_session()
                st.session_state["tor_status"] = crawler.check_tor_connection()
                crawler.close()
        
        status_color = "green" if st.session_state.get("tor_status", False) else "red"
        status_text = "Connected" if st.session_state.get("tor_status", False) else "Disconnected"
        st.markdown(f"<span style='color: {status_color}; font-weight: bold;'>Tor Status: {status_text} ●</span>", unsafe_allow_html=True)
    else:
        st.session_state.pop("tor_status", None)  # Clear status if disabled
        st.markdown("<span style='color: grey; font-weight: bold;'>Tor Status: Disabled ●</span>", unsafe_allow_html=True)
    
    # Discovery Configuration
    st.subheader("Discovery Settings")
    discovery_mode = st.selectbox(
        "Discovery Mode", 
        ["passive", "active", "aggressive"],
        format_func=lambda x: x.capitalize(),
        index=["passive", "active", "aggressive"].index(Config.DISCOVERY_MODE),
        help="Passive: Use existing database only. Active: Discover new sites. Aggressive: Maximum discovery."
    )
    
    depth = st.slider("Crawl Depth", 1, 20, Config.CRAWL_DEPTH, help="Maximum depth for recursive crawling")
    batch_size = st.slider("Batch Size", 5, 30, Config.BATCH_CRAWL_SIZE, help="Number of sites to crawl in one batch")
    
    # Research Mode Selection
    st.subheader("Research Mode")
    mode = st.selectbox(
        "Research Mode", 
        ["Exploratory", "Deep Dive", "Stealth"],
        help="Exploratory: Broad search. Deep Dive: Thorough analysis. Stealth: Minimal footprint."
    )
    
    # Database Stats
    st.subheader("Database Statistics")
    if st.button("Refresh Database Stats"):
        with st.spinner("Refreshing database statistics..."):
            db_stats = initialize_database()
    else:
        db_stats = st.session_state.get("db_stats", {})
    
    if db_stats:
        st.metric("Total Links", db_stats.get("total_links", 0))
        
        # Status breakdown
        st.caption("Links by Status")
        status_counts = db_stats.get("status_counts", {})
        for status, count in status_counts.items():
            st.text(f"• {status.capitalize()}: {count}")
        
        # Category breakdown
        st.caption("Links by Category")
        category_counts = db_stats.get("category_counts", {})
        for category, count in category_counts.items():
            if category:  # Skip empty categories
                st.text(f"• {category.capitalize()}: {count}")
    
    # Database Management
    st.subheader("Database Management")
    db_action = st.selectbox(
        "Database Action", 
        ["None", "Export Database", "Verify Seed Links", "Backup Database"],
        index=0
    )
    
    if db_action == "Export Database" and st.button("Execute Action"):
        with st.spinner("Exporting database to JSON..."):
            db = OnionLinkDatabase()
            export_path = os.path.join(Config.EXPORT_DIR, f"onion_links_export_{int(time.time())}.json")
            success = db.export_links(export_path)
            db.close()
            
            if success:
                st.success(f"Database exported to {export_path}")
            else:
                st.error("Failed to export database")
    
    elif db_action == "Verify Seed Links" and st.button("Execute Action"):
        with st.spinner("Verifying seed links (this may take a while)..."):
            stats = verify_seed_links()
            st.success(f"Verified {stats['total']} seed links: {stats['successful']} active, {stats['failed']} failed")
    
    elif db_action == "Backup Database" and st.button("Execute Action"):
        with st.spinner("Backing up database..."):
            import shutil
            backup_path = os.path.join(Config.EXPORT_DIR, f"onion_db_backup_{int(time.time())}.db")
            shutil.copy2(Config.ONION_DB_PATH, backup_path)
            st.success(f"Database backed up to {backup_path}")

# Set up the main content area with tabs
tabs = st.tabs(["Research", "Onion Link Explorer", "Network Visualization"])

# Research Tab
with tabs[0]:
    st.header("Dark Web Research")  
    query = st.text_area("Research Query", placeholder="E.g., Investigate dark web forums for cryptocurrency scams")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        start_button = st.button("Start Research", use_container_width=True)
    with col2:
        clear_button = st.button("Clear Results", use_container_width=True)
    
    if start_button:
        # Store all configuration settings in session state
        st.session_state["research_query"] = query
        st.session_state["model_choice"] = model_choice
        st.session_state["discovery_mode"] = discovery_mode
        st.session_state["depth"] = depth
        st.session_state["batch_size"] = batch_size
        st.session_state["tor_enabled"] = tor_enabled
        st.session_state["mode"] = mode
        
        # Update Config with current settings
        Config.DISCOVERY_MODE = discovery_mode
        Config.CRAWL_DEPTH = depth
        Config.BATCH_CRAWL_SIZE = batch_size
        
        st.info("Research in progress... This may take several minutes depending on your discovery settings.")
    
    if clear_button:
        # Clear research results from session state
        for key in ["research_query", "results", "final_report", "link_data"]:
            if key in st.session_state:
                del st.session_state[key]
        st.success("Research results cleared.")

# Onion Link Explorer Tab
with tabs[1]:
    st.header("Onion Link Database Explorer")
    
    # Database query controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_type = st.selectbox("Search By", ["Keyword", "Category", "Status"])
    
    with col2:
        if search_type == "Keyword":
            search_term = st.text_input("Search Term")
        elif search_type == "Category":
            db = OnionLinkDatabase()
            categories = list(db.get_statistics().get("category_counts", {}).keys())
            db.close()
            search_term = st.selectbox("Category", categories)
        elif search_type == "Status":
            search_term = st.selectbox("Status", ["new", "active", "inactive", "error", "blacklisted"])
    
    with col3:
        limit = st.slider("Result Limit", 5, 100, 25)
    
    if st.button("Search Database"):
        with st.spinner("Searching onion link database..."):
            db = OnionLinkDatabase()
            
            if search_type == "Keyword" and search_term:
                results = db.search_links(search_term, limit=limit)
            elif search_type == "Category":
                results = db.get_links_by_category(search_term, limit=limit)
            elif search_type == "Status":
                results = db.get_links_by_status(search_term, limit=limit)
            else:
                results = []
            
            db.close()
            
            if results:
                # Convert to DataFrame for display
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True)
                
                # Store in session state for visualization
                st.session_state["link_data"] = results
                
                # Add button to visualize these links
                if st.button("Visualize These Links"):
                    st.session_state["visualize_links"] = True
            else:
                st.warning("No results found.")

# Network Visualization Tab
with tabs[2]:
    st.header("Dark Web Network Visualization")
    
    # Check if we have link data to visualize
    if "link_data" in st.session_state and st.session_state["link_data"]:
        # Create network visualization
        st.subheader("Link Network")
        
        G = nx.DiGraph()
        
        # Add nodes and edges from link data
        for link in st.session_state["link_data"]:
            url = link.get("url", "")
            if url:  # Ensure we have a URL
                G.add_node(url, type="source")
                
                # If there are connected links, add those too
                discovery_source = link.get("discovery_source", "")
                if discovery_source and discovery_source != "seed_data":
                    G.add_node(discovery_source, type="source")
                    G.add_edge(discovery_source, url)
        
        if G.number_of_nodes() > 0:
            # Generate the visualization
            plt.figure(figsize=(12, 10))
            
            # Use different colors for different node types
            node_colors = ["lightblue" if G.nodes[n].get("type") == "source" else "lightgreen" for n in G.nodes()]
            
            # Draw the graph
            pos = nx.spring_layout(G, seed=42)  # Consistent layout
            nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=500, font_size=8, 
                   font_weight="bold", edge_color="gray", arrows=True)
            
            # Convert to image
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
            buf.seek(0)
            img_str = base64.b64encode(buf.read()).decode()
            
            # Display the image
            st.image(f"data:image/png;base64,{img_str}", use_column_width=True)
            
            # Network statistics
            st.subheader("Network Statistics")
            col1, col2, col3 = st.columns(3)
            col1.metric("Nodes", G.number_of_nodes())
            col2.metric("Edges", G.number_of_edges())
            col3.metric("Connected Components", nx.number_connected_components(G.to_undirected()))
        else:
            st.warning("Not enough data to generate network visualization.")
    else:
        st.info("No link data available for visualization. Use the Onion Link Explorer tab to search for links or run a research query.")

# Run research if query exists in session state
if "research_query" in st.session_state and tabs[0].selectbox("View Results", ["Research Results", "Raw Data"], index=0) == "Research Results":
    # Create progress indicators
    if "results" not in st.session_state:
        progress_container = tabs[0].container()
        progress_text = progress_container.empty()
        progress_bar = progress_container.progress(0)
        
        # Initialize agent with the selected model
        agent = ResearchAgent(model_name=st.session_state["model_choice"])
        graph = agent.build_graph()
        
        # Prepare input state for the agent
        inputs = {
            "query": st.session_state["research_query"],
            "plan": [],
            "crawled_data": [],
            "report": "",
            "chat_history": [],
            "discovery_stats": {}
        }
        
        # Initialize results list
        results = []
        progress_text.text("Initializing research agent...")
        progress_bar.progress(10)
        
        # Run the agent graph and collect results
        step_count = 0
        for output in graph.stream(inputs):
            results.append(output)
            step_count += 1
            
            # Update progress
            if "planner" in output:
                progress_text.text("Generating research plan...")
                progress_bar.progress(25)
            elif "crawler" in output:
                progress_text.text("Crawling dark web sites...")
                progress_bar.progress(50)
            elif "analyzer" in output:
                progress_text.text("Analyzing collected data...")
                progress_bar.progress(75)
            elif "report_generator" in output:
                progress_text.text("Generating final report...")
                progress_bar.progress(90)
        
        # Final progress update
        progress_text.text("Research complete!")
        progress_bar.progress(100)
        
        # Store results in session state
        st.session_state["results"] = results
        
        # Extract the final report
        if results:
            final_state = results[-1]
            if "report_generator" in final_state and "report" in final_state["report_generator"]:
                st.session_state["final_report"] = final_state["report_generator"]["report"]
            
            # Extract link data for visualization
            if len(results) > 1 and "crawler" in results[-2]:
                link_data = []
                for data in results[-2]["crawler"]["crawled_data"]:
                    # Each crawled data entry should have url and links
                    if isinstance(data, dict) and "url" in data and "links" in data:
                        source_url = data["url"]
                        for target_url in data["links"]:
                            link_data.append({
                                "source": source_url,
                                "target": target_url
                            })
                st.session_state["link_data"] = link_data
    
    # Display the final report if available
    if "final_report" in st.session_state:
        tabs[0].subheader("Research Report")
        tabs[0].markdown(st.session_state["final_report"])
        
        # Display discovery statistics if available
        if "results" in st.session_state and len(st.session_state["results"]) > 1:
            for output in st.session_state["results"]:
                if "crawler" in output and "discovery_stats" in output["crawler"]:
                    stats = output["crawler"]["discovery_stats"]
                    if stats:
                        tabs[0].subheader("Discovery Statistics")
                        col1, col2, col3, col4 = tabs[0].columns(4)
                        col1.metric("Directories Crawled", stats.get("directories_crawled", 0))
                        col2.metric("Search Engines Queried", stats.get("search_engines_queried", 0))
                        col3.metric("Sites Crawled", stats.get("sites_crawled", 0))
                        col4.metric("New Links Discovered", stats.get("new_links_discovered", 0))
                    break
        
        # Create network visualization
        if "link_data" in st.session_state and st.session_state["link_data"]:
            tabs[0].subheader("Dark Web Network Visualization")
            
            # Create the graph
            G = nx.DiGraph()
            for link in st.session_state["link_data"]:
                if "source" in link and "target" in link:
                    G.add_edge(link["source"], link["target"])
            
            if G.number_of_nodes() > 0:
                # Generate visualization
                plt.figure(figsize=(12, 10))
                pos = nx.spring_layout(G, seed=42)  # Consistent layout
                nx.draw(G, pos, with_labels=True, node_color="lightblue", node_size=500, 
                       font_size=8, edge_color="gray", arrows=True)
                
                # Convert to image
                buf = io.BytesIO()
                plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
                buf.seek(0)
                img_str = base64.b64encode(buf.read()).decode()
                
                # Display the image
                tabs[0].image(f"data:image/png;base64,{img_str}", use_column_width=True)
            else:
                tabs[0].warning("No link data available for visualization.")
    else:
        tabs[0].warning("No research results available. Please start a new research query.")

# Display raw data if selected
elif "research_query" in st.session_state and tabs[0].selectbox("View Results", ["Research Results", "Raw Data"], index=0) == "Raw Data":
    if "results" in st.session_state:
        tabs[0].subheader("Raw Research Data")
        tabs[0].json(st.session_state["results"])
    else:
        tabs[0].warning("No research data available.")

# Add a footer with version info
st.markdown("---")
st.caption(f"Tor Deep Research Agent v2.0 - Last updated: {datetime.datetime.now().strftime('%Y-%m-%d')}")

# Initialize directories when the app starts
if not os.path.exists(Config.DATA_DIR):
    os.makedirs(Config.DATA_DIR)
if not os.path.exists(Config.EXPORT_DIR):
    os.makedirs(Config.EXPORT_DIR)

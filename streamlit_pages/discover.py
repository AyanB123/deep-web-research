"""
Discovery page for the Dark Web Discovery System Streamlit app.
"""

import datetime
import threading
import pandas as pd
import streamlit as st
import plotly.express as px
import uuid

def render_discover():
    """
    Render the discovery page with search and directory crawl options.
    """
    st.title("🔍 Discover")
    st.markdown("Discover new onion sites through search engines and directories")
    
    # Check if system is initialized
    if not st.session_state.db_initialized:
        st.warning("System not fully initialized. Please wait...")
        return
    
    # Create tabs for different discovery methods
    tab1, tab2, tab3 = st.tabs(["Search Engines", "Directories", "Discovery Results"])
    
    with tab1:
        render_search_engines_tab()
    
    with tab2:
        render_directories_tab()
    
    with tab3:
        render_discovery_results_tab()

def render_search_engines_tab():
    """Render the search engines discovery tab."""
    st.markdown("### Search Dark Web Search Engines")
    st.markdown("Discover onion sites by querying Tor search engines")
    
    # Get available search engines
    try:
        search_engines = st.session_state.link_db.get_links_by_category("search_engine")
        
        if not search_engines:
            st.warning("No search engines found in the database. Run seed data first.")
            
            # Add seed data button
            if st.button("Seed Search Engines"):
                from seed_data import seed_search_engines
                with st.spinner("Seeding search engines..."):
                    result = seed_search_engines(st.session_state.link_db)
                    st.success(f"Added {result} search engines to the database")
                st.experimental_rerun()
                
            return
        
        # Display available search engines
        engine_df = pd.DataFrame([{
            "Name": engine.get("title", "Unknown"),
            "URL": engine.get("url", ""),
            "Status": engine.get("status", "unknown")
        } for engine in search_engines])
        
        with st.expander("Available Search Engines", expanded=False):
            st.dataframe(engine_df, use_container_width=True)
        
        # Search form
        with st.form("search_engines_form"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                search_query = st.text_input("Search Query", placeholder="Enter search terms...")
            
            with col2:
                max_engines = st.number_input("Max Engines", min_value=1, max_value=len(search_engines), value=min(3, len(search_engines)))
            
            # Advanced options
            with st.expander("Advanced Options", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    use_clearnet = st.checkbox("Use clearnet fallback if Tor fails", value=True)
                
                with col2:
                    store_in_db = st.checkbox("Store results in database", value=True)
            
            # Submit button
            search_submitted = st.form_submit_button("Search", use_container_width=True)
            
            if search_submitted:
                if not search_query:
                    st.error("Please enter a search query")
                else:
                    # Generate a unique crawler ID
                    crawler_id = f"search_{uuid.uuid4().hex[:8]}"
                    
                    # Update WebSocket with starting status
                    if st.session_state.websocket_manager:
                        st.session_state.websocket_manager.emit_crawl_progress(
                            crawler_id=crawler_id,
                            url=f"Search: {search_query}",
                            status="starting",
                            progress=0,
                            details={"query": search_query, "max_engines": max_engines}
                        )
                    
                    # Start search in a background thread
                    def run_search():
                        try:
                            # Update progress
                            if st.session_state.websocket_manager:
                                st.session_state.websocket_manager.emit_crawl_progress(
                                    crawler_id=crawler_id,
                                    url=f"Search: {search_query}",
                                    status="running",
                                    progress=10,
                                    details={"query": search_query, "max_engines": max_engines}
                                )
                            
                            # Run search
                            results = st.session_state.crawler.search_engines_query(
                                search_query, 
                                max_engines=max_engines
                            )
                            
                            # Update progress
                            if st.session_state.websocket_manager:
                                st.session_state.websocket_manager.emit_crawl_progress(
                                    crawler_id=crawler_id,
                                    url=f"Search: {search_query}",
                                    status="completed",
                                    progress=100,
                                    details={
                                        "query": search_query, 
                                        "max_engines": max_engines,
                                        "results_count": len(results) if results else 0
                                    }
                                )
                                
                                # Emit discovery events for each result
                                for url in results:
                                    st.session_state.websocket_manager.emit_discovery(
                                        url=url,
                                        source=f"search:{search_query}",
                                        details={"query": search_query}
                                    )
                        
                        except Exception as e:
                            # Update with error status
                            if st.session_state.websocket_manager:
                                st.session_state.websocket_manager.emit_crawl_progress(
                                    crawler_id=crawler_id,
                                    url=f"Search: {search_query}",
                                    status="error",
                                    progress=0,
                                    details={"error": str(e)}
                                )
                                
                                st.session_state.websocket_manager.emit_error(
                                    error_type="search_error",
                                    message=f"Error searching for '{search_query}': {str(e)}",
                                    details={"query": search_query}
                                )
                    
                    # Start search thread
                    search_thread = threading.Thread(target=run_search)
                    search_thread.daemon = True
                    search_thread.start()
                    
                    st.success(f"Search started for query: {search_query}")
    
    except Exception as e:
        st.error(f"Error loading search engines: {str(e)}")

def render_directories_tab():
    """Render the directories discovery tab."""
    st.markdown("### Discover from Directories")
    st.markdown("Extract onion links from directory sites")
    
    # Get available directories
    try:
        directories = st.session_state.link_db.get_links_by_category("directory")
        
        if not directories:
            st.warning("No directories found in the database. Run seed data first.")
            
            # Add seed data button
            if st.button("Seed Directories"):
                from seed_data import seed_directories
                with st.spinner("Seeding directories..."):
                    result = seed_directories(st.session_state.link_db)
                    st.success(f"Added {result} directories to the database")
                st.experimental_rerun()
                
            return
        
        # Display available directories
        dir_df = pd.DataFrame([{
            "Name": directory.get("title", "Unknown"),
            "URL": directory.get("url", ""),
            "Status": directory.get("status", "unknown")
        } for directory in directories])
        
        with st.expander("Available Directories", expanded=False):
            st.dataframe(dir_df, use_container_width=True)
        
        # Directory crawl form
        with st.form("directories_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                max_sites = st.number_input("Maximum Directories", 
                                          min_value=1, 
                                          max_value=len(directories), 
                                          value=min(5, len(directories)))
            
            with col2:
                parallel = st.checkbox("Use Parallel Crawling", value=True)
            
            # Advanced options
            with st.expander("Advanced Options", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    verify_links = st.checkbox("Verify discovered links", value=False)
                
                with col2:
                    filter_content = st.checkbox("Filter NSFW content", value=True)
            
            # Submit button
            crawl_submitted = st.form_submit_button("Discover from Directories", use_container_width=True)
            
            if crawl_submitted:
                # Generate a unique crawler ID
                crawler_id = f"directory_{uuid.uuid4().hex[:8]}"
                
                # Update WebSocket with starting status
                if st.session_state.websocket_manager:
                    st.session_state.websocket_manager.emit_crawl_progress(
                        crawler_id=crawler_id,
                        url="Directory Discovery",
                        status="starting",
                        progress=0,
                        details={"max_sites": max_sites, "parallel": parallel}
                    )
                
                # Start discovery in a background thread
                def run_discovery():
                    try:
                        # Update progress
                        if st.session_state.websocket_manager:
                            st.session_state.websocket_manager.emit_crawl_progress(
                                crawler_id=crawler_id,
                                url="Directory Discovery",
                                status="running",
                                progress=10,
                                details={"max_sites": max_sites, "parallel": parallel}
                            )
                        
                        # Set parallel crawling based on checkbox
                        original_parallel = st.session_state.crawler.parallel_enabled
                        st.session_state.crawler.parallel_enabled = parallel
                        
                        # Run discovery
                        discovered = st.session_state.crawler.discover_from_directories(
                            max_sites=max_sites
                        )
                        
                        # Restore original parallel setting
                        st.session_state.crawler.parallel_enabled = original_parallel
                        
                        # Update progress
                        if st.session_state.websocket_manager:
                            st.session_state.websocket_manager.emit_crawl_progress(
                                crawler_id=crawler_id,
                                url="Directory Discovery",
                                status="completed",
                                progress=100,
                                details={
                                    "max_sites": max_sites,
                                    "discovered_count": discovered
                                }
                            )
                    
                    except Exception as e:
                        # Update with error status
                        if st.session_state.websocket_manager:
                            st.session_state.websocket_manager.emit_crawl_progress(
                                crawler_id=crawler_id,
                                url="Directory Discovery",
                                status="error",
                                progress=0,
                                details={"error": str(e)}
                            )
                            
                            st.session_state.websocket_manager.emit_error(
                                error_type="directory_error",
                                message=f"Error discovering from directories: {str(e)}",
                                details={"max_sites": max_sites}
                            )
                
                # Start discovery thread
                discovery_thread = threading.Thread(target=run_discovery)
                discovery_thread.daemon = True
                discovery_thread.start()
                
                st.success(f"Directory discovery started with {max_sites} directories")
    
    except Exception as e:
        st.error(f"Error loading directories: {str(e)}")

def render_discovery_results_tab():
    """Render the discovery results tab."""
    st.markdown("### Recent Discoveries")
    st.markdown("Recently discovered onion links")
    
    # Get recent discoveries
    try:
        recent_links = st.session_state.link_db.get_recent_links(limit=50)
        
        if not recent_links:
            st.info("No recent discoveries found.")
            return
        
        # Process links for display
        display_links = []
        for link in recent_links:
            # Extract discovery date
            discovery_date = ""
            if link.get("metadata") and "discovery_date" in link["metadata"]:
                discovery_date = link["metadata"]["discovery_date"]
            
            # Format for display
            display_links.append({
                "URL": link.get("url", ""),
                "Title": link.get("title", "Unknown"),
                "Category": link.get("category", "unknown"),
                "Discovery Source": link.get("discovery_source", ""),
                "Date Discovered": discovery_date
            })
        
        # Create dataframe
        df = pd.DataFrame(display_links)
        
        # Add filter
        st.markdown("#### Filter Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            filter_category = st.selectbox(
                "Filter by Category",
                ["All"] + sorted(list(set([link["Category"] for link in display_links if link["Category"]])))
            )
        
        with col2:
            filter_source = st.selectbox(
                "Filter by Source",
                ["All"] + sorted(list(set([link["Discovery Source"] for link in display_links if link["Discovery Source"]])))
            )
        
        # Apply filters
        filtered_df = df.copy()
        
        if filter_category != "All":
            filtered_df = filtered_df[filtered_df["Category"] == filter_category]
        
        if filter_source != "All":
            filtered_df = filtered_df[filtered_df["Discovery Source"] == filter_source]
        
        # Display results
        st.markdown(f"#### Results ({len(filtered_df)} links)")
        st.dataframe(filtered_df, use_container_width=True)
        
        # Visualization of discovery sources
        if len(df) > 0:
            source_counts = df["Discovery Source"].value_counts().reset_index()
            source_counts.columns = ["Source", "Count"]
            
            fig = px.pie(
                source_counts,
                values="Count",
                names="Source",
                title="Discovery Sources"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Refresh Results", use_container_width=True):
                st.experimental_rerun()
        
        with col2:
            if st.button("Export Results", use_container_width=True):
                # Generate temp file name
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"discovery_results_{timestamp}.csv"
                
                # Export to CSV
                if st.session_state.export_manager:
                    export_path = st.session_state.export_manager.export_links(
                        format="csv",
                        template="basic",
                        filename=filename,
                        filters={"limit": 50}
                    )
                    
                    st.success(f"Results exported to {export_path}")
                else:
                    st.error("Export manager not initialized")
        
        with col3:
            if st.button("Crawl Selected", use_container_width=True):
                st.info("Feature not yet implemented")
    
    except Exception as e:
        st.error(f"Error loading recent discoveries: {str(e)}")

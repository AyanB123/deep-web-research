"""
Dashboard page for the Dark Web Discovery System Streamlit app.
"""

import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import the adapter
from app_adapter import StreamlitAdapter

def render_dashboard():
    """
    Render the dashboard page with system statistics and visualizations.
    """
    # Get adapter instance from session state or create a new one
    adapter = st.session_state.adapter if hasattr(st.session_state, 'adapter') else StreamlitAdapter()
    
    st.title("🌐 Dashboard")
    st.markdown("System overview and statistics")
    
    # Check if system is initialized
    if not adapter.state.get("db_initialized", False):
        st.warning("System not fully initialized. Please wait...")
        return
    
    # Create layout with columns
    col1, col2, col3 = st.columns(3)
    
    # Get database stats
    try:
        # Get link_db component through adapter
        link_db = adapter.get_link_db()
        stats = link_db.get_database_stats()
        
        # Display key metrics
        with col1:
            st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Total Links</div>
                <div class="metric-value">{:,}</div>
            </div>
            """.format(stats['total_links']), unsafe_allow_html=True)
            
        with col2:
            st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Active Links</div>
                <div class="metric-value">{:,}</div>
            </div>
            """.format(stats['active_links']), unsafe_allow_html=True)
            
        with col3:
            discovered_today = adapter.state.get("crawler_operations.discovery_stats.today_discovered", 0)
            st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Discovered Today</div>
                <div class="metric-value">{:,}</div>
            </div>
            """.format(discovered_today), unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"Error loading database statistics: {str(e)}")
    
    # Recent activity
    st.markdown("## Recent Activity")
    
    # Active crawls
    active_crawls = adapter.state.get("crawler_operations.active_crawls", {})
    if active_crawls:
        st.markdown("### Active Crawls")
        
        # Create dataframe for active crawls
        crawl_data = []
        for crawler_id, crawl in active_crawls.items():
            crawl_data.append({
                "URL": crawl["url"],
                "Status": crawl["status"],
                "Progress": f"{crawl['progress']:.1f}%",
                "Started": crawl.get("timestamp", "")
            })
        
        if crawl_data:
            crawl_df = pd.DataFrame(crawl_data)
            st.dataframe(crawl_df, use_container_width=True)
            
            # Progress bars
            for crawler_id, crawl in active_crawls.items():
                label = f"{crawl['url'][:40]}..." if len(crawl['url']) > 40 else crawl['url']
                st.progress(crawl["progress"] / 100, text=f"{label} - {crawl['status']} ({crawl['progress']:.1f}%)")
    else:
        st.info("No active crawls at the moment.")
    
    # Recent errors
    recent_errors = adapter.state.get("crawler_operations.last_errors", [])
    if recent_errors:
        with st.expander("Recent Errors", expanded=False):
            for error in recent_errors:
                st.markdown(f"""
                <div class="status-box status-error">
                    <strong>{error['type'].upper()}:</strong> {error['message']}
                    <br><small>{error['timestamp']}</small>
                </div>
                """, unsafe_allow_html=True)
    
    # Dashboard visualizations
    st.markdown("## System Analytics")
    
    tab1, tab2, tab3 = st.tabs(["Link Status", "Categories", "Discovery Trends"])
    
    with tab1:
        try:
            # Link status distribution
            status_counts = stats.get('status_counts', {})
            if status_counts:
                # Create pie chart
                fig = go.Figure(data=[go.Pie(
                    labels=list(status_counts.keys()),
                    values=list(status_counts.values()),
                    hole=.3
                )])
                
                fig.update_layout(
                    title='Link Status Distribution',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No status data available.")
        except Exception as e:
            st.error(f"Error generating status chart: {str(e)}")
    
    with tab2:
        try:
            # Category distribution
            category_counts = stats.get('category_counts', {})
            if category_counts:
                # Create bar chart
                fig = px.bar(
                    x=list(category_counts.keys()),
                    y=list(category_counts.values()),
                    labels={'x': 'Category', 'y': 'Count'},
                    title='Link Categories'
                )
                
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No category data available.")
        except Exception as e:
            st.error(f"Error generating category chart: {str(e)}")
    
    with tab3:
        try:
            # Discovery trends
            discovery_data = st.session_state.link_db.get_discovery_trend_data(days=30)
            if discovery_data:
                # Convert to DataFrame
                df = pd.DataFrame(discovery_data)
                df['date'] = pd.to_datetime(df['date'])
                
                # Create line chart
                fig = px.line(
                    df,
                    x='date',
                    y='count',
                    title='Discovery Trend (Last 30 Days)'
                )
                
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No trend data available.")
        except Exception as e:
            st.error(f"Error generating trend chart: {str(e)}")
    
    # Quick actions card
    st.markdown("## Quick Actions")
    
    # Create two columns for actions
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container():
            st.markdown("### Discover Links")
            
            # Quick discovery form
            with st.form("quick_discovery_form"):
                search_query = st.text_input("Search Query", "")
                search_engines = st.slider("Number of Search Engines", 1, 5, 2)
                
                discover_submitted = st.form_submit_button("Discover")
                
                if discover_submitted and search_query:
                    # Start discovery in a background thread
                    crawler = adapter.get_crawler()
                    if crawler:
                        crawler.search_engines_query(search_query, max_engines=search_engines)
                        adapter.add_notification(f"Discovery started for query: {search_query}", "info")
                        st.success(f"Discovery started for query: {search_query}")
                    else:
                        st.error("Crawler not initialized")
    
    with col2:
        with st.container():
            st.markdown("### Crawl Links")
            
            # Quick crawl form
            with st.form("quick_crawl_form"):
                batch_size = st.slider("Batch Size", 5, 30, 10)
                max_depth = st.slider("Max Depth", 0, 3, 1)
                
                crawl_submitted = st.form_submit_button("Crawl Batch")
                
                if crawl_submitted:
                    # Start crawl in a background thread
                    crawler = adapter.get_crawler()
                    if crawler:
                        results = crawler.batch_crawl(batch_size=batch_size)
                        adapter.add_notification(f"Batch crawl started for {batch_size} links", "info")
                        st.success(f"Batch crawl started for {batch_size} links")
                    else:
                        st.error("Crawler not initialized")
    
    # System notifications
    notifications = adapter.state.get("notifications", [])
    if notifications:
        st.markdown("## Recent Notifications")
        
        for notification in reversed(notifications[-5:]):
            message = notification["message"]
            type = notification["type"]
            timestamp = notification["timestamp"]
            
            # Determine notification style
            if type == "error":
                style_class = "status-error"
            elif type == "warning":
                style_class = "status-pending"
            else:
                style_class = "status-active"
            
            # Display notification
            st.markdown(f"""
            <div class="status-box {style_class}">
                {message}
                <br><small>{timestamp}</small>
            </div>
            """, unsafe_allow_html=True)

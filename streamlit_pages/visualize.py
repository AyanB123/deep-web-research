"""
Visualization page for the Dark Web Discovery System Streamlit app.
"""

import os
import tempfile
import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from streamlit.components.v1 import html
import networkx as nx

def render_visualize():
    """
    Render the visualization page with interactive network graphs and charts.
    """
    st.title("📊 Visualize")
    st.markdown("Visualize dark web connections and content")
    
    # Check if system is initialized
    if not st.session_state.db_initialized:
        st.warning("System not fully initialized. Please wait...")
        return
    
    # Create tabs for different visualization types
    tab1, tab2, tab3, tab4 = st.tabs([
        "Network Graph", 
        "Domain Analysis", 
        "Category Distribution", 
        "Discovery Timeline"
    ])
    
    with tab1:
        render_network_graph()
    
    with tab2:
        render_domain_analysis()
    
    with tab3:
        render_category_distribution()
    
    with tab4:
        render_discovery_timeline()

def render_network_graph():
    """Render the network graph visualization tab."""
    st.markdown("### Interactive Network Graph")
    st.markdown("Visualize connections between onion sites")
    
    # Filter options
    with st.expander("Visualization Options", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            color_by = st.selectbox(
                "Color nodes by",
                ["category", "status", "safety", "community"],
                index=0
            )
        
        with col2:
            category_filter = st.selectbox(
                "Filter by category",
                ["All"] + sorted(["directory", "search_engine", "marketplace", "forum", "blog", "service", "social", "other", "unknown"]),
                index=0
            )
            category_filter = None if category_filter == "All" else category_filter
        
        with col3:
            max_nodes = st.slider(
                "Maximum nodes",
                min_value=50,
                max_value=500,
                value=200,
                step=50
            )
    
    # Additional filters
    with st.expander("Advanced Filters", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            status_filter = st.selectbox(
                "Filter by status",
                ["All", "active", "error", "pending", "blacklisted"],
                index=0
            )
            status_filter = None if status_filter == "All" else status_filter
        
        with col2:
            include_blacklisted = st.checkbox("Include blacklisted", value=False)
        
        search_query = st.text_input("Search in URL or title", "")
        
        max_days_old = st.slider(
            "Maximum age in days",
            min_value=1,
            max_value=365,
            value=30,
            step=1
        )
    
    # Build and display network graph
    if st.button("Generate Network Graph", use_container_width=True):
        with st.spinner("Building network graph..."):
            try:
                # Set max nodes limit for visualizer
                st.session_state.network_visualizer.max_nodes = max_nodes
                
                # Build graph with filters
                G = st.session_state.network_visualizer.build_network_graph(
                    category_filter=category_filter,
                    status_filter=status_filter,
                    search_query=search_query if search_query else None,
                    include_blacklisted=include_blacklisted,
                    max_days_old=max_days_old
                )
                
                # Display network stats
                st.markdown(f"#### Network Statistics")
                st.markdown(f"Nodes: **{G.number_of_nodes()}** | Edges: **{G.number_of_edges()}**")
                
                # Create visualization based on graph size
                if G.number_of_nodes() > 0:
                    if G.number_of_nodes() <= 200:
                        # For smaller graphs, use interactive HTML
                        html_file = st.session_state.network_visualizer.create_interactive_graph(
                            G, 
                            color_by=color_by,
                            height="600px",
                            width="100%"
                        )
                        
                        # Display the HTML file
                        with open(html_file, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                        
                        st.components.v1.html(html_content, height=600, scrolling=True)
                        
                        # Provide download link
                        with open(html_file, 'rb') as f:
                            html_bytes = f.read()
                        
                        st.download_button(
                            label="Download Interactive Graph",
                            data=html_bytes,
                            file_name="dark_web_network.html",
                            mime="text/html"
                        )
                    else:
                        # For larger graphs, use Plotly
                        fig = st.session_state.network_visualizer.create_plotly_graph(
                            G,
                            color_by=color_by
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Export options
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("Export to GraphML", use_container_width=True):
                            graphml_file = st.session_state.network_visualizer.export_graph_to_graphml(
                                G,
                                filename=f"network_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.graphml"
                            )
                            
                            st.success(f"Graph exported to GraphML: {graphml_file}")
                    
                    with col2:
                        if st.button("Export Node Data", use_container_width=True):
                            # Convert graph to dataframe
                            node_data = []
                            for node, attrs in G.nodes(data=True):
                                node_data.append({
                                    "url": node,
                                    **attrs
                                })
                            
                            df = pd.DataFrame(node_data)
                            
                            # Use temp file for download
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                                df.to_csv(tmp.name, index=False)
                                tmp_path = tmp.name
                            
                            with open(tmp_path, 'rb') as f:
                                csv_bytes = f.read()
                            
                            st.download_button(
                                label="Download Node Data CSV",
                                data=csv_bytes,
                                file_name="network_nodes.csv",
                                mime="text/csv"
                            )
                            
                            # Clean up temp file
                            os.unlink(tmp_path)
                else:
                    st.warning("No nodes found with the current filters.")
            except Exception as e:
                st.error(f"Error generating network graph: {str(e)}")

def render_domain_analysis():
    """Render the domain analysis visualization tab."""
    st.markdown("### Domain Analysis")
    st.markdown("Analyze domain distribution and clustering")
    
    # Get domain hierarchy
    if st.button("Generate Domain Analysis", use_container_width=True):
        with st.spinner("Analyzing domains..."):
            try:
                # Build graph
                G = st.session_state.network_visualizer.build_network_graph()
                
                # Create domain hierarchy visualization
                fig = st.session_state.network_visualizer.create_domain_hierarchy_visualization(G)
                
                # Display visualization
                st.plotly_chart(fig, use_container_width=True)
                
                # Domain clustering analysis
                st.markdown("#### Domain Clustering")
                
                # Group nodes by domain
                domain_groups = {}
                for node, attrs in G.nodes(data=True):
                    domain = attrs.get("domain", "")
                    if domain:
                        if domain not in domain_groups:
                            domain_groups[domain] = []
                        domain_groups[domain].append(node)
                
                # Create dataframe
                domain_data = []
                for domain, nodes in domain_groups.items():
                    if len(nodes) >= 2:  # Only include domains with multiple pages
                        domain_data.append({
                            "Domain": domain,
                            "Pages": len(nodes),
                            "Categories": ", ".join(set([G.nodes[node].get("category", "unknown") for node in nodes]))
                        })
                
                # Sort by number of pages
                domain_df = pd.DataFrame(domain_data).sort_values(by="Pages", ascending=False)
                
                if not domain_df.empty:
                    st.dataframe(domain_df, use_container_width=True)
                else:
                    st.info("No domains with multiple pages found.")
            except Exception as e:
                st.error(f"Error generating domain analysis: {str(e)}")

def render_category_distribution():
    """Render the category distribution visualization tab."""
    st.markdown("### Category Distribution")
    st.markdown("Visualize the distribution of content categories")
    
    # Generate category visualization
    if st.button("Generate Category Analysis", use_container_width=True):
        with st.spinner("Analyzing categories..."):
            try:
                # Build graph
                G = st.session_state.network_visualizer.build_network_graph()
                
                # Create category distribution visualization
                fig = st.session_state.network_visualizer.create_category_distribution(G)
                
                # Display visualization
                st.plotly_chart(fig, use_container_width=True)
                
                # Create safety distribution visualization if available
                safety_fig = st.session_state.network_visualizer.create_safety_distribution(G)
                
                st.markdown("#### Content Safety Distribution")
                st.plotly_chart(safety_fig, use_container_width=True)
                
                # Advanced category analysis
                if st.session_state.content_analyzer and Config.ANALYTICS_ENABLED:
                    st.markdown("#### Detailed Category Analysis")
                    
                    # Get all categories used
                    categories = set()
                    for node, attrs in G.nodes(data=True):
                        cat = attrs.get("category", "unknown")
                        if cat:
                            categories.add(cat)
                    
                    # Category descriptions
                    category_descriptions = {
                        "directory": "Link collections and directories",
                        "search_engine": "Search engines for onion sites",
                        "marketplace": "Sites for buying/selling goods or services",
                        "forum": "Discussion forums and message boards",
                        "blog": "Personal or organizational blogs",
                        "service": "Service providers (hosting, email, etc.)",
                        "social": "Social networking sites",
                        "other": "Other categorized sites",
                        "unknown": "Uncategorized sites"
                    }
                    
                    # Display category details
                    for category in sorted(categories):
                        if category in category_descriptions:
                            st.markdown(f"**{category.title()}**: {category_descriptions[category]}")
                            
                            # Count sites in this category
                            count = sum(1 for _, attrs in G.nodes(data=True) if attrs.get("category") == category)
                            st.markdown(f"Sites in this category: {count}")
                            
                            # Add expander for examples
                            with st.expander(f"Example {category} sites", expanded=False):
                                examples = []
                                for node, attrs in G.nodes(data=True):
                                    if attrs.get("category") == category:
                                        examples.append({
                                            "Title": attrs.get("title", "Unknown"),
                                            "URL": node,
                                            "Status": attrs.get("status", "unknown")
                                        })
                                        if len(examples) >= 5:
                                            break
                                
                                if examples:
                                    st.dataframe(pd.DataFrame(examples), use_container_width=True)
                                else:
                                    st.info("No examples available.")
            except Exception as e:
                st.error(f"Error generating category analysis: {str(e)}")

def render_discovery_timeline():
    """Render the discovery timeline visualization tab."""
    st.markdown("### Discovery Timeline")
    st.markdown("Visualize when links were discovered over time")
    
    # Time range selector
    col1, col2 = st.columns(2)
    
    with col1:
        days = st.slider(
            "Days to include",
            min_value=7,
            max_value=365,
            value=30,
            step=1
        )
    
    with col2:
        group_by = st.selectbox(
            "Group by",
            ["day", "week", "month"],
            index=0
        )
    
    # Generate timeline
    if st.button("Generate Timeline", use_container_width=True):
        with st.spinner("Building timeline..."):
            try:
                # Build graph
                G = st.session_state.network_visualizer.build_network_graph(max_days_old=days)
                
                # Create discovery timeline visualization
                fig = st.session_state.network_visualizer.create_discovery_timeline(G)
                
                # Display visualization
                st.plotly_chart(fig, use_container_width=True)
                
                # Get discovery data from database for more detailed analysis
                discovery_data = st.session_state.link_db.get_discovery_trend_data(
                    days=days,
                    group_by=group_by
                )
                
                if discovery_data:
                    # Convert to DataFrame
                    df = pd.DataFrame(discovery_data)
                    
                    # Display as table
                    st.markdown("#### Discovery Data")
                    st.dataframe(df, use_container_width=True)
                    
                    # Create additional visualization - cumulative growth
                    if len(df) > 1:
                        # Add cumulative count
                        df['cumulative'] = df['count'].cumsum()
                        
                        # Create line chart
                        fig2 = px.line(
                            df,
                            x='date',
                            y='cumulative',
                            title='Cumulative Growth Over Time'
                        )
                        
                        fig2.update_layout(height=400)
                        st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No discovery data available for the selected time range.")
            except Exception as e:
                st.error(f"Error generating timeline: {str(e)}")

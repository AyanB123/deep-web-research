"""
Export page for the Dark Web Discovery System Streamlit app.
"""

import os
import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import time

def render_export():
    """
    Render the export page with various export options.
    """
    st.title("📤 Export")
    st.markdown("Export discovered data in various formats")
    
    # Check if system is initialized
    if not st.session_state.db_initialized:
        st.warning("System not fully initialized. Please wait...")
        return
    
    # Check if export manager is available
    if not st.session_state.export_manager:
        st.error("Export manager not initialized")
        return
    
    # Create tabs for different export types
    tab1, tab2, tab3 = st.tabs([
        "Data Export", 
        "Visualization Export",
        "Export History"
    ])
    
    with tab1:
        render_data_export()
    
    with tab2:
        render_visualization_export()
    
    with tab3:
        render_export_history()

def render_data_export():
    """Render the data export tab."""
    st.markdown("### Export Data")
    st.markdown("Export link data in various formats with real-time preview")
    
    # Check if our export preview component is available
    try:
        from streamlit_components.export_preview import render_export_preview
        
        # Use the new interactive export preview component
        render_export_preview(st.session_state.export_manager, key="main_export")
    except ImportError:
        # Fall back to the old export form if the component isn't available
        st.warning("Enhanced export preview not available. Using basic export form.")
        
        # Export form
        with st.form("export_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                export_format = st.selectbox(
                    "Export Format",
                    ["CSV", "Excel", "JSON", "GraphML", "HTML"],
                    index=0
                )
            
            with col2:
                template = st.selectbox(
                    "Template",
                    ["basic", "full", "minimal", "analysis"],
                    index=0,
                    help="Template determines which fields are included in the export"
                )
        
        # Filters section
        st.markdown("#### Filters")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            category_filter = st.selectbox(
                "Category",
                ["All"] + sorted(["directory", "search_engine", "marketplace", "forum", "blog", "service", "social", "other", "unknown"]),
                index=0
            )
            category_filter = None if category_filter == "All" else category_filter
        
        with col2:
            status_filter = st.selectbox(
                "Status",
                ["All", "active", "error", "pending", "blacklisted"],
                index=0
            )
            status_filter = None if status_filter == "All" else status_filter
        
        with col3:
            max_results = st.number_input(
                "Max Results",
                min_value=10,
                max_value=10000,
                value=1000,
                step=100
            )
        
        # Advanced filters
        with st.expander("Advanced Filters", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                date_from = st.date_input(
                    "From Date",
                    value=datetime.datetime.now() - datetime.timedelta(days=30),
                    format="YYYY-MM-DD"
                )
            
            with col2:
                date_to = st.date_input(
                    "To Date",
                    value=datetime.datetime.now(),
                    format="YYYY-MM-DD"
                )
            
            search_query = st.text_input("Search in URL or title", "")
            
            include_blacklisted = st.checkbox("Include blacklisted", value=False)
        
        # Submit button
        export_submitted = st.form_submit_button("Export Data", use_container_width=True)
        
        if export_submitted:
            with st.spinner(f"Exporting data to {export_format}..."):
                try:
                    # Build filters
                    filters = {
                        "category": category_filter,
                        "status": status_filter,
                        "search_query": search_query if search_query else None,
                        "include_blacklisted": include_blacklisted,
                        "date_from": date_from.strftime("%Y-%m-%d") if date_from else None,
                        "date_to": date_to.strftime("%Y-%m-%d") if date_to else None,
                        "limit": max_results
                    }
                    
                    # Remove None values
                    filters = {k: v for k, v in filters.items() if v is not None}
                    
                    # Generate timestamp for filename
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    # Determine file extension
                    ext_map = {
                        "CSV": "csv",
                        "Excel": "xlsx",
                        "JSON": "json",
                        "GraphML": "graphml",
                        "HTML": "html"
                    }
                    
                    filename = f"export_{timestamp}.{ext_map[export_format]}"
                    
                    # Execute export
                    export_path = st.session_state.export_manager.export_links(
                        format=export_format.lower(),
                        template=template,
                        filename=filename,
                        filters=filters
                    )
                    
                    # Check if export was successful
                    if export_path and os.path.exists(export_path):
                        # Read file for download
                        with open(export_path, 'rb') as f:
                            file_data = f.read()
                        
                        # Determine MIME type
                        mime_map = {
                            "CSV": "text/csv",
                            "Excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "JSON": "application/json",
                            "GraphML": "application/xml",
                            "HTML": "text/html"
                        }
                        
                        # Create download button
                        st.download_button(
                            label=f"Download {export_format} File",
                            data=file_data,
                            file_name=filename,
                            mime=mime_map[export_format]
                        )
                        
                        # Show success message
                        st.success(f"Export completed successfully: {filename}")
                        
                        # Show preview if possible
                        if export_format in ["CSV", "Excel", "JSON"]:
                            with st.expander("Data Preview", expanded=True):
                                if export_format == "CSV":
                                    df = pd.read_csv(export_path)
                                    st.dataframe(df.head(10), use_container_width=True)
                                elif export_format == "Excel":
                                    df = pd.read_excel(export_path)
                                    st.dataframe(df.head(10), use_container_width=True)
                                elif export_format == "JSON":
                                    import json
                                    with open(export_path, 'r') as f:
                                        data = json.load(f)
                                    if isinstance(data, list) and len(data) > 0:
                                        # Convert first 10 items to dataframe
                                        df = pd.DataFrame(data[:10])
                                        st.dataframe(df, use_container_width=True)
                                    else:
                                        st.json(data)
                    else:
                        st.error(f"Export failed or file not found: {export_path}")
                
                except Exception as e:
                    st.error(f"Error exporting data: {str(e)}")

def render_visualization_export():
    """Render the visualization export tab."""
    st.markdown("### Export Visualizations")
    st.markdown("Export interactive visualizations and reports")
    
    # Visualization type selector
    viz_type = st.selectbox(
        "Visualization Type",
        ["Network Graph", "Domain Hierarchy", "Category Distribution", "Timeline"],
        index=0
    )
    
    # Options based on visualization type
    if viz_type == "Network Graph":
        col1, col2 = st.columns(2)
        
        with col1:
            color_by = st.selectbox(
                "Color nodes by",
                ["category", "status", "safety", "community"],
                index=0
            )
        
        with col2:
            max_nodes = st.slider(
                "Maximum nodes",
                min_value=50,
                max_value=500,
                value=200,
                step=50
            )
        
        # Filter options
        with st.expander("Filters", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                category_filter = st.selectbox(
                    "Filter by category",
                    ["All"] + sorted(["directory", "search_engine", "marketplace", "forum", "blog", "service", "social", "other", "unknown"]),
                    index=0
                )
                category_filter = None if category_filter == "All" else category_filter
            
            with col2:
                status_filter = st.selectbox(
                    "Filter by status",
                    ["All", "active", "error", "pending", "blacklisted"],
                    index=0
                )
                status_filter = None if status_filter == "All" else status_filter
    
    elif viz_type == "Domain Hierarchy":
        col1, col2 = st.columns(2)
        
        with col1:
            max_domains = st.slider(
                "Maximum domains",
                min_value=10,
                max_value=100,
                value=30,
                step=5
            )
        
        with col2:
            min_pages = st.slider(
                "Minimum pages per domain",
                min_value=1,
                max_value=10,
                value=2,
                step=1
            )
    
    elif viz_type == "Category Distribution":
        col1, col2 = st.columns(2)
        
        with col1:
            include_unknown = st.checkbox("Include Unknown Category", value=True)
        
        with col2:
            chart_type = st.selectbox(
                "Chart Type",
                ["Pie", "Bar"],
                index=0
            )
    
    elif viz_type == "Timeline":
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
    
    # Export button
    if st.button("Generate and Export", use_container_width=True):
        with st.spinner(f"Generating {viz_type}..."):
            try:
                # Handle different visualization types
                if viz_type == "Network Graph":
                    # Set max nodes limit for visualizer
                    st.session_state.network_visualizer.max_nodes = max_nodes
                    
                    # Build graph with filters
                    G = st.session_state.network_visualizer.build_network_graph(
                        category_filter=category_filter,
                        status_filter=status_filter
                    )
                    
                    # Create interactive visualization
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"network_graph_{timestamp}.html"
                    
                    # Generate HTML file
                    html_file = st.session_state.network_visualizer.create_interactive_graph(
                        G, 
                        color_by=color_by,
                        height="800px",
                        width="100%",
                        output_path=os.path.join(st.session_state.export_manager.export_dir, filename)
                    )
                    
                    # Read for download
                    with open(html_file, 'rb') as f:
                        file_data = f.read()
                    
                    # Create download button
                    st.download_button(
                        label="Download Interactive Network Graph",
                        data=file_data,
                        file_name=filename,
                        mime="text/html"
                    )
                    
                    # Display preview
                    with st.expander("Preview", expanded=True):
                        st.components.v1.html(file_data.decode('utf-8'), height=600, scrolling=True)
                    
                    st.success(f"Network graph exported successfully: {filename}")
                
                elif viz_type == "Domain Hierarchy":
                    # Build graph
                    G = st.session_state.network_visualizer.build_network_graph()
                    
                    # Create domain hierarchy
                    fig = st.session_state.network_visualizer.create_domain_hierarchy_visualization(
                        G,
                        max_domains=max_domains,
                        min_pages=min_pages
                    )
                    
                    # Generate HTML file
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"domain_hierarchy_{timestamp}.html"
                    
                    # Save figure
                    fig.write_html(os.path.join(st.session_state.export_manager.export_dir, filename))
                    
                    # Read for download
                    with open(os.path.join(st.session_state.export_manager.export_dir, filename), 'rb') as f:
                        file_data = f.read()
                    
                    # Create download button
                    st.download_button(
                        label="Download Domain Hierarchy",
                        data=file_data,
                        file_name=filename,
                        mime="text/html"
                    )
                    
                    # Display preview
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.success(f"Domain hierarchy exported successfully: {filename}")
                
                elif viz_type == "Category Distribution":
                    # Build graph
                    G = st.session_state.network_visualizer.build_network_graph()
                    
                    # Create category distribution
                    fig = st.session_state.network_visualizer.create_category_distribution(
                        G,
                        include_unknown=include_unknown,
                        chart_type=chart_type.lower()
                    )
                    
                    # Generate HTML file
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"category_distribution_{timestamp}.html"
                    
                    # Save figure
                    fig.write_html(os.path.join(st.session_state.export_manager.export_dir, filename))
                    
                    # Read for download
                    with open(os.path.join(st.session_state.export_manager.export_dir, filename), 'rb') as f:
                        file_data = f.read()
                    
                    # Create download button
                    st.download_button(
                        label="Download Category Distribution",
                        data=file_data,
                        file_name=filename,
                        mime="text/html"
                    )
                    
                    # Display preview
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.success(f"Category distribution exported successfully: {filename}")
                
                elif viz_type == "Timeline":
                    # Build graph
                    G = st.session_state.network_visualizer.build_network_graph(max_days_old=days)
                    
                    # Create timeline
                    fig = st.session_state.network_visualizer.create_discovery_timeline(
                        G,
                        group_by=group_by
                    )
                    
                    # Generate HTML file
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"discovery_timeline_{timestamp}.html"
                    
                    # Save figure
                    fig.write_html(os.path.join(st.session_state.export_manager.export_dir, filename))
                    
                    # Read for download
                    with open(os.path.join(st.session_state.export_manager.export_dir, filename), 'rb') as f:
                        file_data = f.read()
                    
                    # Create download button
                    st.download_button(
                        label="Download Discovery Timeline",
                        data=file_data,
                        file_name=filename,
                        mime="text/html"
                    )
                    
                    # Display preview
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.success(f"Discovery timeline exported successfully: {filename}")
            
            except Exception as e:
                st.error(f"Error generating visualization: {str(e)}")

def render_export_history():
    """Render the export history tab."""
    st.markdown("### Export History")
    st.markdown("View and download previous exports")
    
    # Refresh button
    if st.button("Refresh Export History", use_container_width=True):
        st.experimental_rerun()
    
    try:
        # List files in export directory
        export_dir = st.session_state.export_manager.export_dir
        files = []
        
        if os.path.exists(export_dir):
            for filename in os.listdir(export_dir):
                file_path = os.path.join(export_dir, filename)
                if os.path.isfile(file_path):
                    # Get file stats
                    stats = os.stat(file_path)
                    
                    # Add to list
                    files.append({
                        "Filename": filename,
                        "Size (KB)": round(stats.st_size / 1024, 2),
                        "Created": datetime.datetime.fromtimestamp(stats.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                        "Path": file_path
                    })
        
        if files:
            # Sort by creation time (newest first)
            files.sort(key=lambda x: x["Created"], reverse=True)
            
            # Convert to dataframe
            files_df = pd.DataFrame(files)
            
            # Display table
            st.dataframe(files_df[["Filename", "Size (KB)", "Created"]], use_container_width=True)
            
            # File action
            st.markdown("#### Download Export File")
            
            selected_file = st.selectbox(
                "Select file to download",
                [f["Filename"] for f in files]
            )
            
            if selected_file:
                # Find file path
                file_path = next((f["Path"] for f in files if f["Filename"] == selected_file), None)
                
                if file_path and os.path.exists(file_path):
                    # Read file for download
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    
                    # Determine MIME type
                    mime_type = "application/octet-stream"
                    if selected_file.endswith(".csv"):
                        mime_type = "text/csv"
                    elif selected_file.endswith(".xlsx"):
                        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    elif selected_file.endswith(".json"):
                        mime_type = "application/json"
                    elif selected_file.endswith(".graphml"):
                        mime_type = "application/xml"
                    elif selected_file.endswith(".html"):
                        mime_type = "text/html"
                    
                    # Create download button
                    st.download_button(
                        label=f"Download {selected_file}",
                        data=file_data,
                        file_name=selected_file,
                        mime=mime_type
                    )
        else:
            st.info("No export files found.")
    
    except Exception as e:
        st.error(f"Error loading export history: {str(e)}")

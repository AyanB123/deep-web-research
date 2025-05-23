"""
Export preview component for Streamlit.
Provides interactive previews of data exports in various formats.
"""

import streamlit as st
import pandas as pd
import json
import tempfile
import os
import base64
from typing import Dict, List, Any, Optional, Union

from export_manager import ExportManager
from streamlit_components.card import render_card


def render_csv_preview(data: List[Dict], fields: List[str], max_rows: int = 10):
    """
    Render a preview of CSV export.
    
    Args:
        data: Export data
        fields: Fields to include
        max_rows: Maximum number of rows to display
    """
    # Convert to DataFrame for display
    df = pd.DataFrame(data[:max_rows])
    
    # Subset to selected fields if they exist
    existing_fields = [f for f in fields if f in df.columns]
    if existing_fields:
        df = df[existing_fields]
    
    # Display preview
    st.dataframe(df, use_container_width=True)
    
    # Show note about preview
    if len(data) > max_rows:
        st.caption(f"Showing {max_rows} of {len(data)} rows in the preview.")


def render_json_preview(data: List[Dict], fields: List[str], max_items: int = 5):
    """
    Render a preview of JSON export.
    
    Args:
        data: Export data
        fields: Fields to include
        max_items: Maximum number of items to display
    """
    # Prepare preview data
    preview_data = []
    for item in data[:max_items]:
        # Keep only selected fields
        preview_item = {k: v for k, v in item.items() if k in fields}
        preview_data.append(preview_item)
    
    # Format as JSON
    json_str = json.dumps(preview_data, indent=2)
    
    # Display in code block
    st.code(json_str, language="json")
    
    # Show note about preview
    if len(data) > max_items:
        st.caption(f"Showing {max_items} of {len(data)} items in the preview.")


def render_html_preview(data: List[Dict], fields: List[str], max_rows: int = 10):
    """
    Render a preview of HTML export.
    
    Args:
        data: Export data
        fields: Fields to include
        max_rows: Maximum number of rows to display
    """
    # Convert to DataFrame for display
    df = pd.DataFrame(data[:max_rows])
    
    # Subset to selected fields if they exist
    existing_fields = [f for f in fields if f in df.columns]
    if existing_fields:
        df = df[existing_fields]
    
    # Create HTML table
    html = df.to_html(index=False, escape=True, classes="table table-striped")
    
    # Add some basic styling
    html = f"""
    <style>
    .table {{
        width: 100%;
        border-collapse: collapse;
        font-family: Arial, sans-serif;
    }}
    .table th {{
        background-color: #f2f2f2;
        padding: 8px;
        text-align: left;
        border-bottom: 2px solid #ddd;
    }}
    .table td {{
        padding: 8px;
        border-bottom: 1px solid #ddd;
    }}
    .table tr:nth-child(even) {{
        background-color: #f9f9f9;
    }}
    </style>
    {html}
    """
    
    # Display HTML
    st.markdown(html, unsafe_allow_html=True)
    
    # Show note about preview
    if len(data) > max_rows:
        st.caption(f"Showing {max_rows} of {len(data)} rows in the preview.")


def render_graphml_preview(data: List[Dict], manager: ExportManager):
    """
    Render a preview of GraphML export.
    
    Args:
        data: Export data
        manager: Export manager instance
    """
    # Create a temporary graph visualization
    with st.spinner("Generating graph preview..."):
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_file:
            # Create a temporary GraphML file
            with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as graphml_file:
                graphml_path = graphml_file.name
            
            # Export to GraphML
            manager._export_to_graphml(data, graphml_path)
            
            # Create a graph from the GraphML
            import networkx as nx
            try:
                G = nx.read_graphml(graphml_path)
                
                # Create a basic visualization if network_visualizer is available
                if manager.network_visualizer:
                    fig = manager.network_visualizer.create_plotly_graph(G)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # Simple fallback
                    st.write(f"Graph contains {len(G.nodes)} nodes and {len(G.edges)} edges.")
                    
                    # Show a few nodes
                    if G.nodes:
                        st.write("Sample nodes:")
                        for i, node in enumerate(list(G.nodes())[:5]):
                            st.write(f"- {node}")
                            if i >= 4:
                                break
            except Exception as e:
                st.error(f"Error generating graph preview: {str(e)}")
            
            # Clean up temporary files
            try:
                os.unlink(graphml_path)
            except:
                pass


def render_excel_preview(data: List[Dict], fields: List[str], max_rows: int = 10):
    """
    Render a preview of Excel export.
    
    Args:
        data: Export data
        fields: Fields to include
        max_rows: Maximum number of rows to display
    """
    # This is similar to CSV preview but we'll add Excel-specific formatting
    # Convert to DataFrame for display
    df = pd.DataFrame(data[:max_rows])
    
    # Subset to selected fields if they exist
    existing_fields = [f for f in fields if f in df.columns]
    if existing_fields:
        df = df[existing_fields]
    
    # Display preview
    st.dataframe(df, use_container_width=True)
    
    # Show note about Excel features
    st.info("The Excel export will include formatted headers, auto-sized columns, and filters.")
    
    # Show note about preview
    if len(data) > max_rows:
        st.caption(f"Showing {max_rows} of {len(data)} rows in the preview.")


def create_download_link(file_path: str, link_text: str = "Download File"):
    """
    Create a download link for a file.
    
    Args:
        file_path: Path to the file
        link_text: Text for the download link
        
    Returns:
        HTML for download link
    """
    with open(file_path, "rb") as f:
        data = f.read()
    
    b64 = base64.b64encode(data).decode()
    file_name = os.path.basename(file_path)
    mime_type = "application/octet-stream"
    
    # Determine MIME type based on extension
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        mime_type = "text/csv"
    elif ext == ".json":
        mime_type = "application/json"
    elif ext == ".html":
        mime_type = "text/html"
    elif ext == ".xlsx":
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif ext == ".graphml":
        mime_type = "application/xml"
    
    href = f'<a href="data:{mime_type};base64,{b64}" download="{file_name}">{link_text}</a>'
    return href


class ExportPreviewComponent:
    """
    Export preview component for Streamlit.
    Provides interactive previews of data exports.
    """
    
    def __init__(self, 
                 export_manager: ExportManager,
                 key: str = "export_preview"):
        """
        Initialize the export preview component.
        
        Args:
            export_manager: Export manager instance
            key: Component key prefix
        """
        self.manager = export_manager
        self.key_prefix = key
        
        # Ensure session state items exist
        if f"{self.key_prefix}_format" not in st.session_state:
            st.session_state[f"{self.key_prefix}_format"] = "csv"
        
        if f"{self.key_prefix}_template" not in st.session_state:
            st.session_state[f"{self.key_prefix}_template"] = "basic"
        
        if f"{self.key_prefix}_custom_fields" not in st.session_state:
            st.session_state[f"{self.key_prefix}_custom_fields"] = []
        
        if f"{self.key_prefix}_filters" not in st.session_state:
            st.session_state[f"{self.key_prefix}_filters"] = {}
    
    def render_format_selector(self, container):
        """Render format selection controls."""
        # Get available formats
        formats = self.manager.get_available_formats()
        
        # Format selector
        format_options = list(formats.keys())
        format_labels = [f"{k} - {v}" for k, v in formats.items()]
        
        selected_format = container.selectbox(
            "Export Format",
            options=format_options,
            format_func=lambda x: formats[x],
            index=format_options.index(st.session_state[f"{self.key_prefix}_format"]),
            key=f"{self.key_prefix}_format_select"
        )
        
        # Update session state
        st.session_state[f"{self.key_prefix}_format"] = selected_format
        
        return selected_format
    
    def render_template_selector(self, container):
        """Render template selection controls."""
        # Get available templates
        templates = self.manager.get_available_templates()
        
        # Add custom template option
        all_templates = templates.copy()
        all_templates["custom"] = {
            "name": "Custom Template",
            "description": "Create a custom template with selected fields",
            "fields": []
        }
        
        # Template selector
        template_options = list(all_templates.keys())
        
        selected_template = container.selectbox(
            "Export Template",
            options=template_options,
            format_func=lambda x: all_templates[x]["name"],
            index=template_options.index(st.session_state[f"{self.key_prefix}_template"]),
            key=f"{self.key_prefix}_template_select"
        )
        
        # Update session state
        st.session_state[f"{self.key_prefix}_template"] = selected_template
        
        # Display template description
        container.caption(all_templates[selected_template]["description"])
        
        # If custom template, show field selector
        if selected_template == "custom":
            self.render_custom_field_selector(container)
        
        return selected_template
    
    def render_custom_field_selector(self, container):
        """Render custom field selector."""
        # Get all possible fields
        all_fields = [
            "url", "title", "description", "category", "status", "last_checked", 
            "discovery_date", "discovery_source", "content_preview", "metadata",
            "domain", "safety_score", "safety_categories", "was_filtered", 
            "filter_reason", "tags", "links_to", "linked_from"
        ]
        
        # Show field selector
        selected_fields = container.multiselect(
            "Select Fields",
            options=all_fields,
            default=st.session_state[f"{self.key_prefix}_custom_fields"] or ["url", "title", "category"],
            key=f"{self.key_prefix}_fields_select"
        )
        
        # Update session state
        st.session_state[f"{self.key_prefix}_custom_fields"] = selected_fields
        
        return selected_fields
    
    def render_filter_controls(self, container):
        """Render filter controls."""
        # Get current filters
        filters = st.session_state[f"{self.key_prefix}_filters"]
        
        # Show filter controls
        with container.expander("Filters", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                # Category filter
                category = st.selectbox(
                    "Category",
                    [None, "directory", "search_engine", "marketplace", "forum", "blog", "service", "social", "other"],
                    index=0,
                    key=f"{self.key_prefix}_category_filter"
                )
                filters["category"] = category
                
                # Status filter
                status = st.selectbox(
                    "Status",
                    [None, "active", "error", "pending", "blacklisted", "clearnet_fallback"],
                    index=0,
                    key=f"{self.key_prefix}_status_filter"
                )
                filters["status"] = status
            
            with col2:
                # Max days old
                max_days = st.number_input(
                    "Max Days Old",
                    min_value=0,
                    value=filters.get("max_days_old", 0) or 0,
                    step=1,
                    key=f"{self.key_prefix}_max_days_filter"
                )
                filters["max_days_old"] = max_days if max_days > 0 else None
                
                # Include blacklisted
                include_blacklisted = st.checkbox(
                    "Include Blacklisted",
                    value=filters.get("include_blacklisted", False),
                    key=f"{self.key_prefix}_blacklisted_filter"
                )
                filters["include_blacklisted"] = include_blacklisted
            
            # Search query
            search_query = st.text_input(
                "Search Query",
                value=filters.get("search_query", ""),
                key=f"{self.key_prefix}_search_filter"
            )
            filters["search_query"] = search_query if search_query else None
        
        # Update session state
        st.session_state[f"{self.key_prefix}_filters"] = filters
        
        return filters
    
    def render_preview(self, container):
        """Render export preview."""
        # Get current settings
        format_type = st.session_state[f"{self.key_prefix}_format"]
        template = st.session_state[f"{self.key_prefix}_template"]
        custom_fields = st.session_state[f"{self.key_prefix}_custom_fields"]
        filters = st.session_state[f"{self.key_prefix}_filters"]
        
        # Get fields based on template
        if template == "custom":
            fields = custom_fields
        elif template in self.manager.TEMPLATES:
            fields = self.manager.TEMPLATES[template]["fields"]
        else:
            fields = self.manager.TEMPLATES["basic"]["fields"]
        
        # Get preview data
        with st.spinner("Loading preview data..."):
            # Get filtered links
            links = self.manager._get_filtered_links(filters)
            
            # Prepare data for preview
            preview_data = self.manager._prepare_export_data(links, fields)
        
        # Show data stats
        container.markdown(f"### Preview ({len(preview_data)} records)")
        
        # Show appropriate preview based on format
        if format_type == "csv":
            render_csv_preview(preview_data, fields)
        elif format_type == "excel":
            render_excel_preview(preview_data, fields)
        elif format_type == "json":
            render_json_preview(preview_data, fields)
        elif format_type == "html":
            render_html_preview(preview_data, fields)
        elif format_type == "graphml":
            render_graphml_preview(preview_data, self.manager)
    
    def render_export_button(self, container):
        """Render export button."""
        # Get current settings
        format_type = st.session_state[f"{self.key_prefix}_format"]
        template = st.session_state[f"{self.key_prefix}_template"]
        custom_fields = st.session_state[f"{self.key_prefix}_custom_fields"]
        filters = st.session_state[f"{self.key_prefix}_filters"]
        
        # File name input
        filename = container.text_input(
            "Export Filename",
            value=f"export_{datetime.datetime.now().strftime('%Y%m%d')}",
            key=f"{self.key_prefix}_filename"
        )
        
        # Export button
        if container.button("Generate Export", key=f"{self.key_prefix}_export_button"):
            with st.spinner("Generating export..."):
                try:
                    # Generate export
                    export_path = self.manager.export_links(
                        format=format_type,
                        template=template,
                        filename=filename,
                        filters=filters,
                        custom_fields=custom_fields if template == "custom" else None
                    )
                    
                    # Show success message
                    container.success(f"Export generated successfully!")
                    
                    # Create download link
                    download_link = create_download_link(
                        export_path, 
                        f"Download {os.path.basename(export_path)}"
                    )
                    container.markdown(download_link, unsafe_allow_html=True)
                    
                    # Store in session state for later
                    if "recent_exports" not in st.session_state:
                        st.session_state.recent_exports = []
                    
                    export_info = {
                        "path": export_path,
                        "filename": os.path.basename(export_path),
                        "format": format_type,
                        "template": template,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "record_count": len(self.manager._get_filtered_links(filters))
                    }
                    
                    st.session_state.recent_exports.append(export_info)
                    
                    # Send notification about completed export
                    self._send_export_notification(export_info)
                    
                except Exception as e:
                    container.error(f"Error generating export: {str(e)}")
    
    def _send_export_notification(self, export_info):
        """
        Send a notification about a completed export.
        
        Args:
            export_info: Export information dictionary
        """
        # Check if notification system is available
        if "notification_system" not in st.session_state or not st.session_state.notification_system:
            return
        
        # Format message based on export type
        format_name = self.manager.FORMATS.get(export_info["format"], export_info["format"]).split(" ")[0]
        template_name = self.manager.TEMPLATES.get(export_info["template"], {}).get("name", export_info["template"])
        
        # Create notification title and message
        title = f"Export Completed: {format_name}"
        message = f"Export completed successfully: {export_info['filename']}"
        details = f"Format: {format_name}, Template: {template_name}, Records: {export_info['record_count']}"
        
        # Send notification
        try:
            st.session_state.notification_system.add_notification(
                title=title,
                message=message,
                details=details,
                notification_type="export",
                level="success",
                actions=[
                    {
                        "label": "View Exports",
                        "target": "/export"
                    }
                ],
                data={
                    "export_path": export_info["path"],
                    "export_info": export_info
                }
            )
            
            # Also send WebSocket notification if available
            self._send_websocket_notification(export_info)
            
        except Exception as e:
            print(f"Error sending export notification: {str(e)}")
    
    def _send_websocket_notification(self, export_info):
        """
        Send a WebSocket notification about export completion.
        
        Args:
            export_info: Export information dictionary
        """
        # Check if WebSocket is available
        if "websocket" not in st.session_state or not st.session_state.websocket:
            return
        
        try:
            # Send export completion message via WebSocket
            st.session_state.websocket.send_message(
                "export_complete",
                {
                    "filename": export_info["filename"],
                    "format": export_info["format"],
                    "template": export_info["template"],
                    "timestamp": export_info["timestamp"],
                    "record_count": export_info["record_count"]
                },
                priority="normal"
            )
        except Exception as e:
            print(f"Error sending WebSocket export notification: {str(e)}")
    
    def render(self):
        """Render the export preview component."""
        st.markdown("## Export Preview")
        
        # Create layout
        config_col, preview_col = st.columns([1, 2])
        
        # Configuration column
        with config_col:
            # Format selector
            format_type = self.render_format_selector(config_col)
            
            # Template selector
            template = self.render_template_selector(config_col)
            
            # Filter controls
            filters = self.render_filter_controls(config_col)
            
            # Export button
            self.render_export_button(config_col)
        
        # Preview column
        with preview_col:
            self.render_preview(preview_col)


def render_export_preview(export_manager: ExportManager, key: str = "export_preview"):
    """
    Render an export preview component.
    
    Args:
        export_manager: Export manager instance
        key: Component key prefix
    """
    component = ExportPreviewComponent(
        export_manager=export_manager,
        key=key
    )
    
    component.render()

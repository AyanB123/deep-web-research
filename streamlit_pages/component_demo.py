"""
Component Demo page for the Dark Web Discovery System.
Showcases UI components from the component library.
"""

import streamlit as st
import datetime
import random
from app_adapter import StreamlitAdapter
from streamlit_components.theme import apply_theme, get_theme_colors
from streamlit_components.card import render_card, render_stat_card, render_link_card
from streamlit_components.metrics import render_metric, render_metric_group, render_value_comparison
from streamlit_components.status import render_status_indicator, render_progress, render_status_timeline

def render_component_demo():
    """Render the component demo page."""
    st.title("UI Component Library")
    
    # Apply theme
    apply_theme(dark_mode=False)
    theme = get_theme_colors()
    
    st.markdown("""
    This page demonstrates the UI components available in the component library.
    These components provide consistent styling and behavior across the application.
    """)
    
    # Tabs for component categories
    tab1, tab2, tab3, tab4 = st.tabs(["Cards", "Metrics", "Status", "Advanced"])
    
    with tab1:
        st.header("Card Components")
        
        st.subheader("Basic Card")
        render_card(
            title="Basic Card",
            subtitle="A simple card with title and content",
            content=lambda: st.write("This is the content of the card. It can contain any Streamlit elements.")
        )
        
        st.subheader("Card with Footer")
        render_card(
            title="Card with Footer",
            content=lambda: st.write("This card has a footer section for additional information or actions."),
            footer=lambda: st.button("Action Button", key="card_footer_button")
        )
        
        st.subheader("Colored Border Card")
        render_card(
            title="Colored Border Card",
            content=lambda: st.write("This card has a colored left border to indicate importance or category."),
            border_color=theme["primary"]
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Stat Card")
            render_stat_card(
                title="Total Discoveries",
                value=12548,
                subtitle="Last 30 days",
                delta=5.4,
                delta_description="vs last month"
            )
        
        with col2:
            st.subheader("Link Card")
            render_link_card(
                title="Documentation Link",
                url="https://example.com/docs",
                description="Visit our documentation for more information",
                icon="📚"
            )
    
    with tab2:
        st.header("Metric Components")
        
        st.subheader("Basic Metrics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            render_metric(
                label="Total Onion Links",
                value=8462,
                delta=324,
                delta_description="this week"
            )
        
        with col2:
            render_metric(
                label="Success Rate",
                value=87.5,
                delta=2.3,
                suffix="%",
                color=theme["success"]
            )
        
        with col3:
            render_metric(
                label="Average Response Time",
                value=1.2,
                delta=-0.3,
                suffix="s",
                color=theme["info"]
            )
        
        st.subheader("Metric Group")
        render_metric_group([
            {
                "label": "Discovered Today",
                "value": 126,
                "delta": 14,
                "color": theme["primary"]
            },
            {
                "label": "Success Rate",
                "value": 92.8,
                "suffix": "%",
                "delta": 1.2,
                "color": theme["success"]
            },
            {
                "label": "Failed Connections",
                "value": 47,
                "delta": -5,
                "color": theme["error"]
            },
            {
                "label": "Average Depth",
                "value": 3.2,
                "delta": 0.2,
                "color": theme["info"]
            }
        ])
        
        st.subheader("Value Comparison")
        render_value_comparison(
            title="Service Types",
            value1=62,
            value2=38,
            label1="HTTP Services",
            label2="HTTPS Services",
            is_percentage=True,
            color1=theme["primary"],
            color2=theme["secondary"],
            description="Distribution of service types across discovered onion links"
        )
        
        render_value_comparison(
            title="Content Languages",
            value1=752,
            value2=348,
            label1="English",
            label2="Other Languages",
            color1=theme["success"],
            color2=theme["info"],
            description="Language distribution in analyzed content"
        )
    
    with tab3:
        st.header("Status Components")
        
        st.subheader("Status Indicators")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            render_status_indicator("success", "Online", "Service is operating normally")
        
        with col2:
            render_status_indicator("warning", "Degraded", "Service experiencing slowdowns")
        
        with col3:
            render_status_indicator("error", "Offline", "Service is unavailable")
        
        with col4:
            render_status_indicator("info", "Updating", "Service is being updated")
        
        st.subheader("Progress Bars")
        
        render_progress(
            value=75,
            label="Crawl Progress",
            description="3 of 4 stages completed",
            show_percentage=True
        )
        
        render_progress(
            value=45,
            label="Data Processing",
            description="Estimated completion in 5 minutes",
            color=theme["warning"],
            animate=True
        )
        
        render_progress(
            value=100,
            label="Export Completed",
            description="All data successfully exported",
            color=theme["success"]
        )
        
        st.subheader("Status Timeline")
        render_status_timeline(
            steps=[
                {
                    "label": "Initialization",
                    "status": "success",
                    "description": "System initialized successfully",
                    "time": "10:15 AM"
                },
                {
                    "label": "Data Collection",
                    "status": "success",
                    "description": "Collected data from 5 sources",
                    "time": "10:20 AM"
                },
                {
                    "label": "Processing",
                    "status": "info",
                    "description": "Processing 2,450 records",
                    "time": "10:25 AM"
                },
                {
                    "label": "Validation",
                    "status": "pending",
                    "description": "Waiting for processing to complete",
                    "time": ""
                },
                {
                    "label": "Export",
                    "status": "pending",
                    "description": "Final step",
                    "time": ""
                }
            ],
            current_step=2,
            show_time=True
        )
    
    with tab4:
        st.header("Advanced Components")
        
        st.subheader("Interactive Card Demo")
        
        # Demo data
        crawl_statuses = ["Running", "Completed", "Failed", "Queued"]
        current_statuses = {
            "Crawler A": random.choice(crawl_statuses),
            "Crawler B": random.choice(crawl_statuses),
            "Crawler C": random.choice(crawl_statuses)
        }
        
        # Interactive cards
        st.markdown("Click on a card to view details")
        
        for crawler, status in current_statuses.items():
            # Determine color based on status
            if status == "Running":
                color = theme["info"]
                progress = random.randint(10, 90)
            elif status == "Completed":
                color = theme["success"]
                progress = 100
            elif status == "Failed":
                color = theme["error"]
                progress = random.randint(0, 100)
            else:  # Queued
                color = theme["disabled"]
                progress = 0
            
            # Create a unique key for each card
            card_key = f"crawler_{crawler.replace(' ', '_').lower()}"
            
            # Render card with status and progress
            def create_content_renderer(status, progress, color):
                def render_content():
                    render_status_indicator(
                        status.lower() if status in ["Running", "Completed", "Failed"] else "info",
                        status
                    )
                    
                    if status != "Queued":
                        render_progress(
                            value=progress,
                            height="6px",
                            color=color,
                            animate=(status == "Running")
                        )
                    
                    # Additional metrics
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Discovered", random.randint(10, 500))
                    with col2:
                        st.metric("Success Rate", f"{random.randint(70, 99)}%")
                
                return render_content
            
            # Render the card
            render_card(
                title=crawler,
                subtitle=f"Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}",
                content=create_content_renderer(status, progress, color),
                key=card_key,
                border_color=color
            )
        
        st.subheader("Theme Colors")
        
        # Display theme colors
        st.markdown("### Primary Colors")
        cols = st.columns(3)
        for i, (name, color) in enumerate([
            ("Primary", theme["primary"]),
            ("Primary Light", theme["primary_light"]),
            ("Primary Dark", theme["primary_dark"])
        ]):
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="background-color: {color}; color: white; padding: 1rem; border-radius: 4px; text-align: center;">
                        {name}<br>
                        <code>{color}</code>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        
        st.markdown("### Status Colors")
        cols = st.columns(4)
        for i, (name, color) in enumerate([
            ("Success", theme["success"]),
            ("Warning", theme["warning"]),
            ("Error", theme["error"]),
            ("Info", theme["info"])
        ]):
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="background-color: {color}; color: white; padding: 1rem; border-radius: 4px; text-align: center;">
                        {name}<br>
                        <code>{color}</code>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


if __name__ == "__main__":
    # For testing
    import sys
    import os
    
    # Add parent directory to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Initialize adapter
    adapter = StreamlitAdapter()
    if not adapter.initialize():
        st.error("Failed to initialize adapter")
    
    # Render page
    render_component_demo()

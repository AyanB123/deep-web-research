"""
Settings page for the Dark Web Discovery System Streamlit app.
"""

import os
import datetime
import json
import streamlit as st
from pathlib import Path

def render_settings():
    """
    Render the settings page for system configuration.
    """
    st.title("⚙️ Settings")
    st.markdown("Configure system settings and preferences")
    
    # Create tabs for different settings categories
    tab1, tab2, tab3, tab4 = st.tabs([
        "General Settings", 
        "Crawling Settings",
        "API Keys",
        "Advanced Settings"
    ])
    
    with tab1:
        render_general_settings()
    
    with tab2:
        render_crawling_settings()
    
    with tab3:
        render_api_keys()
    
    with tab4:
        render_advanced_settings()
    
    # System information at the bottom
    with st.expander("System Information", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Database Stats")
            if st.session_state.link_db:
                stats = st.session_state.link_db.get_database_stats()
                st.markdown(f"Total Links: **{stats.get('total_links', 0):,}**")
                st.markdown(f"Active Links: **{stats.get('active_links', 0):,}**")
                st.markdown(f"Database Size: **{stats.get('db_size', 0):.2f} MB**")
                st.markdown(f"Last Updated: **{stats.get('last_updated', 'Unknown')}**")
            else:
                st.warning("Database not initialized")
        
        with col2:
            st.markdown("#### Version Information")
            st.markdown(f"System Version: **{st.session_state.version}**")
            st.markdown(f"Last Updated: **{st.session_state.last_updated}**")
            
            # Check for updates button
            if st.button("Check for Updates"):
                st.info("Checking for updates... This feature is not yet implemented.")

def render_general_settings():
    """Render general settings tab."""
    st.markdown("### General Settings")
    
    # Load current configuration
    config = st.session_state.config
    
    # Create a form for settings
    with st.form("general_settings_form"):
        # Base directories
        st.markdown("#### Directories")
        
        data_dir = st.text_input(
            "Data Directory",
            value=config.DATA_DIR,
            help="Directory where data files are stored"
        )
        
        export_dir = st.text_input(
            "Export Directory",
            value=config.EXPORT_DIR,
            help="Directory where exports are saved"
        )
        
        db_path = st.text_input(
            "Database Path",
            value=config.ONION_DB_PATH,
            help="Path to the SQLite database file"
        )
        
        # Tor settings
        st.markdown("#### Tor Settings")
        
        tor_proxy = st.text_input(
            "Tor Proxy",
            value=config.TOR_PROXY,
            help="Tor SOCKS proxy address (e.g., socks5h://127.0.0.1:9050)"
        )
        
        use_clearnet_fallback = st.checkbox(
            "Use Clearnet Fallback",
            value=config.USE_CLEARNET_FALLBACK,
            help="Use clearnet searches if Tor fails"
        )
        
        # Interface settings
        st.markdown("#### Interface Settings")
        
        theme = st.selectbox(
            "Theme",
            ["dark", "light"],
            index=0 if config.DARK_MODE else 1,
            help="UI theme preference"
        )
        
        language = st.selectbox(
            "Language",
            ["English", "Spanish", "French", "German"],
            index=0,
            help="Interface language (English only for now)"
        )
        
        # Submit button
        save_general = st.form_submit_button("Save General Settings")
        
        if save_general:
            try:
                # Update configuration
                st.session_state.config.DATA_DIR = data_dir
                st.session_state.config.EXPORT_DIR = export_dir
                st.session_state.config.ONION_DB_PATH = db_path
                st.session_state.config.TOR_PROXY = tor_proxy
                st.session_state.config.USE_CLEARNET_FALLBACK = use_clearnet_fallback
                st.session_state.config.DARK_MODE = (theme == "dark")
                
                # Save to config file
                save_config(st.session_state.config)
                
                st.success("General settings saved successfully!")
                
                # Refresh required components
                if st.session_state.export_manager:
                    st.session_state.export_manager.export_dir = export_dir
                
                # Show restart recommendation
                st.warning("Some settings require a restart to take effect.")
            except Exception as e:
                st.error(f"Error saving settings: {str(e)}")

def render_crawling_settings():
    """Render crawling settings tab."""
    st.markdown("### Crawling Settings")
    
    # Load current configuration
    config = st.session_state.config
    
    # Create a form for settings
    with st.form("crawling_settings_form"):
        # Basic crawling settings
        st.markdown("#### Basic Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            max_depth = st.number_input(
                "Maximum Crawl Depth",
                min_value=0,
                max_value=5,
                value=config.MAX_DEPTH,
                help="Maximum depth for crawling (0-5)"
            )
        
        with col2:
            max_links = st.number_input(
                "Maximum Links per Page",
                min_value=5,
                max_value=1000,
                value=config.MAX_LINKS_PER_PAGE,
                help="Maximum number of links to extract from each page"
            )
        
        # Request settings
        st.markdown("#### Request Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            timeout = st.number_input(
                "Request Timeout (seconds)",
                min_value=5,
                max_value=180,
                value=config.REQUEST_TIMEOUT,
                help="Timeout for HTTP requests in seconds"
            )
        
        with col2:
            retry_count = st.number_input(
                "Retry Count",
                min_value=0,
                max_value=10,
                value=config.RETRY_COUNT,
                help="Number of times to retry failed requests"
            )
        
        # Circuit settings
        st.markdown("#### Tor Circuit Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            rotate_circuits = st.checkbox(
                "Rotate Tor Circuits",
                value=config.ROTATE_CIRCUITS,
                help="Rotate Tor circuits to avoid detection"
            )
        
        with col2:
            circuit_retries = st.number_input(
                "Circuit Retry Attempts",
                min_value=1,
                max_value=10,
                value=config.CIRCUIT_RETRIES,
                help="Number of circuit rotation attempts"
            )
        
        # Throttling settings
        st.markdown("#### Throttling Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            request_delay = st.number_input(
                "Request Delay (seconds)",
                min_value=0.0,
                max_value=30.0,
                value=config.REQUEST_DELAY,
                step=0.5,
                help="Delay between requests in seconds"
            )
        
        with col2:
            domain_throttling = st.checkbox(
                "Domain Throttling",
                value=config.DOMAIN_THROTTLING,
                help="Apply stricter throttling per domain"
            )
        
        # Submit button
        save_crawling = st.form_submit_button("Save Crawling Settings")
        
        if save_crawling:
            try:
                # Update configuration
                st.session_state.config.MAX_DEPTH = max_depth
                st.session_state.config.MAX_LINKS_PER_PAGE = max_links
                st.session_state.config.REQUEST_TIMEOUT = timeout
                st.session_state.config.RETRY_COUNT = retry_count
                st.session_state.config.ROTATE_CIRCUITS = rotate_circuits
                st.session_state.config.CIRCUIT_RETRIES = circuit_retries
                st.session_state.config.REQUEST_DELAY = request_delay
                st.session_state.config.DOMAIN_THROTTLING = domain_throttling
                
                # Save to config file
                save_config(st.session_state.config)
                
                st.success("Crawling settings saved successfully!")
                
                # Apply new settings to crawler
                if st.session_state.crawler:
                    st.session_state.crawler.request_timeout = timeout
                    st.session_state.crawler.retry_count = retry_count
                    st.session_state.crawler.max_depth = max_depth
                    st.session_state.crawler.max_links = max_links
                    st.session_state.crawler.request_delay = request_delay
                    st.session_state.crawler.rotate_circuits = rotate_circuits
                    
                    st.info("New settings applied to active crawler.")
            except Exception as e:
                st.error(f"Error saving settings: {str(e)}")

def render_api_keys():
    """Render API keys tab."""
    st.markdown("### API Keys")
    st.markdown("Configure API keys for external services")
    
    # Load current configuration
    config = st.session_state.config
    
    # Create a form for API keys
    with st.form("api_keys_form"):
        # Gemini API
        st.markdown("#### Gemini AI API")
        
        gemini_api_key = st.text_input(
            "Gemini API Key",
            value=config.GEMINI_API_KEY if config.GEMINI_API_KEY else "",
            type="password",
            help="API key for Google Gemini AI"
        )
        
        # Groq API
        st.markdown("#### Groq API (Optional)")
        
        groq_api_key = st.text_input(
            "Groq API Key",
            value=config.GROQ_API_KEY if config.GROQ_API_KEY else "",
            type="password",
            help="API key for Groq (optional)"
        )
        
        # Tavily API
        st.markdown("#### Tavily API (Clearnet Search)")
        
        tavily_api_key = st.text_input(
            "Tavily API Key",
            value=config.TAVILY_API_KEY if config.TAVILY_API_KEY else "",
            type="password",
            help="API key for Tavily search"
        )
        
        # Submit button
        save_api_keys = st.form_submit_button("Save API Keys")
        
        if save_api_keys:
            try:
                # Update configuration
                st.session_state.config.GEMINI_API_KEY = gemini_api_key
                st.session_state.config.GROQ_API_KEY = groq_api_key
                st.session_state.config.TAVILY_API_KEY = tavily_api_key
                
                # Save to config file
                save_config(st.session_state.config)
                
                st.success("API keys saved successfully!")
                
                # Refresh required components
                if st.session_state.content_analyzer:
                    st.session_state.content_analyzer.api_key = gemini_api_key
                    if groq_api_key:
                        st.session_state.content_analyzer.groq_api_key = groq_api_key
                
                if st.session_state.tavily_search:
                    st.session_state.tavily_search.api_key = tavily_api_key
            except Exception as e:
                st.error(f"Error saving API keys: {str(e)}")

def render_advanced_settings():
    """Render advanced settings tab."""
    st.markdown("### Advanced Settings")
    st.markdown("⚠️ **Warning**: These settings are for advanced users only.")
    
    # Load current configuration
    config = st.session_state.config
    
    # Create a form for advanced settings
    with st.form("advanced_settings_form"):
        # Feature flags
        st.markdown("#### Feature Flags")
        
        col1, col2 = st.columns(2)
        
        with col1:
            analytics_enabled = st.checkbox(
                "Enable Advanced Analytics",
                value=config.ANALYTICS_ENABLED,
                help="Enable content and trend analysis"
            )
        
        with col2:
            websocket_enabled = st.checkbox(
                "Enable WebSockets",
                value=config.WEBSOCKET_ENABLED,
                help="Enable real-time updates"
            )
        
        parallel_processing = st.checkbox(
            "Enable Parallel Processing",
            value=config.PARALLEL_PROCESSING,
            help="Enable parallel crawling and processing"
        )
        
        # Memory management
        st.markdown("#### Memory Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            memory_monitoring = st.checkbox(
                "Enable Memory Monitoring",
                value=config.MEMORY_MONITORING,
                help="Monitor memory usage during crawls"
            )
        
        with col2:
            memory_limit = st.number_input(
                "Memory Limit (MB)",
                min_value=100,
                max_value=8000,
                value=config.MEMORY_LIMIT,
                help="Memory limit for crawling operations"
            )
        
        # Database settings
        st.markdown("#### Database Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            db_cache_enabled = st.checkbox(
                "Enable Query Cache",
                value=config.DB_CACHE_ENABLED,
                help="Cache database queries for performance"
            )
        
        with col2:
            db_optimize_interval = st.number_input(
                "DB Optimization Interval (hours)",
                min_value=1,
                max_value=168,
                value=config.DB_OPTIMIZE_INTERVAL,
                help="How often to optimize the database"
            )
        
        # Debug options
        st.markdown("#### Debug Options")
        
        debug_mode = st.checkbox(
            "Enable Debug Mode",
            value=config.DEBUG_MODE,
            help="Enable detailed logging and debugging"
        )
        
        log_level = st.selectbox(
            "Log Level",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=1 if config.LOG_LEVEL == "INFO" else 0,
            help="Logging verbosity level"
        )
        
        # Submit button
        save_advanced = st.form_submit_button("Save Advanced Settings")
        
        if save_advanced:
            try:
                # Update configuration
                st.session_state.config.ANALYTICS_ENABLED = analytics_enabled
                st.session_state.config.WEBSOCKET_ENABLED = websocket_enabled
                st.session_state.config.PARALLEL_PROCESSING = parallel_processing
                st.session_state.config.MEMORY_MONITORING = memory_monitoring
                st.session_state.config.MEMORY_LIMIT = memory_limit
                st.session_state.config.DB_CACHE_ENABLED = db_cache_enabled
                st.session_state.config.DB_OPTIMIZE_INTERVAL = db_optimize_interval
                st.session_state.config.DEBUG_MODE = debug_mode
                st.session_state.config.LOG_LEVEL = log_level
                
                # Save to config file
                save_config(st.session_state.config)
                
                st.success("Advanced settings saved successfully!")
                st.warning("Some advanced settings require a restart to take effect.")
            except Exception as e:
                st.error(f"Error saving settings: {str(e)}")

def save_config(config):
    """
    Save the configuration to a file.
    
    Args:
        config: The configuration object to save
    """
    try:
        # Get config as dictionary
        config_dict = {key: getattr(config, key) for key in dir(config) 
                      if not key.startswith('__') and not callable(getattr(config, key))}
        
        # Convert to JSON
        config_json = json.dumps(config_dict, indent=4)
        
        # Determine config file path
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        
        # Save to file
        with open(config_path, 'w') as f:
            f.write(config_json)
        
        return True
    except Exception as e:
        st.error(f"Error saving configuration: {str(e)}")
        return False

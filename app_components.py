"""
Component manager for the Dark Web Discovery System.
Handles initialization, dependency resolution, and lifecycle management.
"""

import logging
from typing import Dict, Optional, Any
import time

from config import Config
from onion_database import OnionLinkDatabase
from enhanced_crawler import EnhancedTorCrawler
from connection_manager import ConnectionManager
from websocket_manager import WebSocketManager
from network_visualization import NetworkVisualizer
from export_manager import ExportManager
from content_safety import ContentSafetyClassifier
from advanced_analytics import ContentAnalyzer, TrendAnalyzer
from database_utils import DatabaseManager
from tavily_search import TavilySearch

class AppComponents:
    """
    Centralized component manager for the Dark Web Discovery System.
    Handles initialization, dependency resolution, and lifecycle management.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the component manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.initialized = False
        self._components = {}
        self._init_order = []
        self._init_status = {}
        self._component_dependencies = self._build_dependency_graph()
        self.logger = logging.getLogger("AppComponents")
    
    def _build_dependency_graph(self) -> Dict[str, list]:
        """
        Build the dependency graph for component initialization.
        
        Returns:
            Dict mapping component names to their dependencies
        """
        # Define component dependencies (what each component needs)
        return {
            "db_manager": [],  # No dependencies
            "link_db": ["db_manager"],
            "connection_manager": [],  # No dependencies
            "content_safety": [],  # No dependencies
            "websocket_manager": [],  # No dependencies
            "crawler": ["link_db", "connection_manager"],
            "network_visualizer": ["link_db"],
            "export_manager": ["link_db", "network_visualizer"],
            "content_analyzer": [],  # No dependencies
            "trend_analyzer": ["link_db"],
            "tavily_search": []  # No dependencies
        }
    
    def get(self, component_name: str) -> Any:
        """
        Get a component by name, initializing it if necessary.
        
        Args:
            component_name: Name of the component to get
            
        Returns:
            The requested component
        
        Raises:
            KeyError: If the component is not registered
            RuntimeError: If initialization fails
        """
        if component_name not in self._components:
            self._init_component(component_name)
        
        return self._components.get(component_name)
    
    def _check_dependencies(self, component_name: str) -> bool:
        """
        Check if all dependencies for a component are initialized.
        
        Args:
            component_name: Component to check
            
        Returns:
            True if all dependencies are initialized, False otherwise
        """
        dependencies = self._component_dependencies.get(component_name, [])
        
        for dep in dependencies:
            if dep not in self._components:
                self._init_component(dep)
                
        return True
    
    def _init_component(self, component_name: str) -> None:
        """
        Initialize a specific component and its dependencies.
        
        Args:
            component_name: Name of the component to initialize
            
        Raises:
            RuntimeError: If initialization fails
        """
        # Prevent circular dependencies
        if self._init_status.get(component_name) == "in_progress":
            raise RuntimeError(f"Circular dependency detected for {component_name}")
        
        # Skip if already initialized
        if component_name in self._components:
            return
            
        # Mark as in progress
        self._init_status[component_name] = "in_progress"
        self.logger.info(f"Initializing component: {component_name}")
        
        # Check dependencies
        self._check_dependencies(component_name)
        
        # Initialize the component
        try:
            if component_name == "db_manager":
                self._components[component_name] = DatabaseManager(self.config.ONION_DB_PATH)
                
            elif component_name == "link_db":
                db_manager = self.get("db_manager")
                self._components[component_name] = OnionLinkDatabase(
                    db_path=self.config.ONION_DB_PATH,
                    db_manager=db_manager
                )
                
            elif component_name == "connection_manager":
                self._components[component_name] = ConnectionManager(
                    tor_proxy=self.config.TOR_PROXY,
                    clearnet_fallback=self.config.USE_CLEARNET_FALLBACK
                )
                
            elif component_name == "content_safety":
                if self.config.NSFW_CONTENT_FILTERING:
                    self._components[component_name] = ContentSafetyClassifier(
                        api_key=self.config.GEMINI_API_KEY,
                        groq_api_key=self.config.GROQ_API_KEY
                    )
                else:
                    self._components[component_name] = None
                    
            elif component_name == "websocket_manager":
                if self.config.WEBSOCKET_ENABLED:
                    websocket_manager = WebSocketManager()
                    websocket_manager.start_server()
                    self._components[component_name] = websocket_manager
                else:
                    self._components[component_name] = None
                    
            elif component_name == "crawler":
                link_db = self.get("link_db")
                connection_manager = self.get("connection_manager")
                self._components[component_name] = EnhancedTorCrawler(
                    proxy=self.config.TOR_PROXY,
                    link_db=link_db,
                    connection_manager=connection_manager
                )
                
            elif component_name == "network_visualizer":
                link_db = self.get("link_db")
                self._components[component_name] = NetworkVisualizer(link_db)
                
            elif component_name == "export_manager":
                link_db = self.get("link_db")
                network_visualizer = self.get("network_visualizer")
                self._components[component_name] = ExportManager(
                    link_db,
                    network_visualizer,
                    export_dir=self.config.EXPORT_DIR
                )
                
            elif component_name == "content_analyzer":
                if self.config.ANALYTICS_ENABLED:
                    self._components[component_name] = ContentAnalyzer(
                        api_key=self.config.GEMINI_API_KEY,
                        groq_api_key=self.config.GROQ_API_KEY
                    )
                else:
                    self._components[component_name] = None
                    
            elif component_name == "trend_analyzer":
                if self.config.ANALYTICS_ENABLED:
                    link_db = self.get("link_db")
                    self._components[component_name] = TrendAnalyzer(link_db)
                else:
                    self._components[component_name] = None
                    
            elif component_name == "tavily_search":
                if self.config.USE_CLEARNET_FALLBACK and self.config.TAVILY_API_KEY:
                    self._components[component_name] = TavilySearch(self.config.TAVILY_API_KEY)
                else:
                    self._components[component_name] = None
                    
            else:
                raise KeyError(f"Unknown component: {component_name}")
                
            # Mark as initialized
            self._init_status[component_name] = "initialized"
            self._init_order.append(component_name)
            self.logger.info(f"Component initialized: {component_name}")
            
        except Exception as e:
            self._init_status[component_name] = "failed"
            self.logger.error(f"Error initializing {component_name}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to initialize {component_name}: {str(e)}")
    
    def initialize_all(self) -> None:
        """
        Initialize all components in the correct order.
        """
        if self.initialized:
            return
            
        try:
            # Create necessary directories
            self.config.init_directories()
            
            # Initialize components in dependency order
            components_to_init = list(self._component_dependencies.keys())
            for component in components_to_init:
                if component not in self._components:
                    self._init_component(component)
                    
            self.initialized = True
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error during initialization: {str(e)}", exc_info=True)
            raise
    
    def shutdown(self) -> None:
        """
        Shutdown all components in reverse initialization order.
        """
        if not self.initialized:
            return
            
        # Shutdown in reverse order of initialization
        for component_name in reversed(self._init_order):
            try:
                component = self._components.get(component_name)
                if hasattr(component, 'shutdown'):
                    component.shutdown()
                self.logger.info(f"Component shutdown: {component_name}")
            except Exception as e:
                self.logger.error(f"Error shutting down {component_name}: {str(e)}", exc_info=True)
                
        self._components.clear()
        self._init_order.clear()
        self._init_status.clear()
        self.initialized = False

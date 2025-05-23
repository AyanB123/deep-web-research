"""
Search service for the Dark Web Discovery System.
Provides advanced search capabilities using the query builder.
"""

import json
import logging
import datetime
import sqlite3
from typing import Dict, List, Any, Optional, Union, Tuple, Set

from query_builder import QueryBuilder, FilterGroup, FilterCondition, FilterOperator, LogicalOperator
from query_executor import QueryExecutor

class SearchService:
    """
    Service for searching onion links with advanced filtering.
    Integrates with the query builder and database.
    """
    
    def __init__(self, db_connection):
        """
        Initialize the search service.
        
        Args:
            db_connection: Database connection
        """
        self.db_connection = db_connection
        self.query_executor = QueryExecutor(db_connection)
        self.logger = logging.getLogger("SearchService")
        
        # Cache for saved searches
        self.saved_searches: Dict[str, Dict[str, Any]] = {}
        
        # Search history
        self.search_history: List[Dict[str, Any]] = []
        self.max_history_items = 50
    
    def search(self, query_builder: QueryBuilder) -> Dict[str, Any]:
        """
        Execute a search query.
        
        Args:
            query_builder: Query builder object
            
        Returns:
            Search results with metadata
        """
        # Log the search
        self._add_to_history(query_builder)
        
        try:
            # Execute query
            results = self.query_executor.execute(query_builder)
            
            # Get total count (without pagination)
            total_count = self.query_executor.count(query_builder)
            
            # Calculate pagination info
            limit = query_builder.limit or len(results)
            offset = query_builder.offset or 0
            
            # Return results with metadata
            return {
                "success": True,
                "results": results,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "page": (offset // limit) + 1 if limit > 0 else 1,
                "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
                "timestamp": datetime.datetime.now().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error executing search: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    def search_by_text(self, text: str, fields: Optional[List[str]] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Simplified search by text.
        
        Args:
            text: Search text
            fields: Fields to search in (defaults to title, content, url)
            limit: Maximum results
            offset: Result offset
            
        Returns:
            Search results
        """
        # Default fields if not provided
        if not fields:
            fields = ["title", "content", "url"]
        
        # Create query builder
        query = QueryBuilder()
        
        # Split text into terms
        terms = text.strip().split()
        
        if len(terms) == 1:
            # Single term - search across all fields
            term_group = FilterGroup(LogicalOperator.OR)
            
            for field in fields:
                term_group.add_condition(
                    FilterCondition(field, FilterOperator.CONTAINS, terms[0])
                )
            
            query.filter_group.add_group(term_group)
        
        else:
            # Multiple terms - each term must appear in at least one field
            for term in terms:
                term_group = FilterGroup(LogicalOperator.OR)
                
                for field in fields:
                    term_group.add_condition(
                        FilterCondition(field, FilterOperator.CONTAINS, term)
                    )
                
                query.filter_group.add_group(term_group)
        
        # Add pagination
        query.paginate(limit, offset)
        
        # Execute search
        return self.search(query)
    
    def save_search(self, name: str, query_builder: QueryBuilder, description: Optional[str] = None, overwrite: bool = False) -> bool:
        """
        Save a search for later use.
        
        Args:
            name: Unique name for the saved search
            query_builder: Query builder object
            description: Optional description
            overwrite: Whether to overwrite if name exists
            
        Returns:
            True if saved successfully
        """
        # Check if name exists
        if name in self.saved_searches and not overwrite:
            return False
        
        # Save the search
        self.saved_searches[name] = {
            "name": name,
            "description": description or "",
            "query": query_builder.build(),
            "created": datetime.datetime.now().isoformat(),
            "last_used": None
        }
        
        return True
    
    def get_saved_search(self, name: str) -> Optional[QueryBuilder]:
        """
        Get a saved search.
        
        Args:
            name: Saved search name
            
        Returns:
            Query builder object or None if not found
        """
        if name not in self.saved_searches:
            return None
        
        # Update last used
        self.saved_searches[name]["last_used"] = datetime.datetime.now().isoformat()
        
        # Create query builder from saved query
        query_data = self.saved_searches[name]["query"]
        return self._create_query_from_dict(query_data)
    
    def list_saved_searches(self) -> List[Dict[str, Any]]:
        """
        List all saved searches.
        
        Returns:
            List of saved search metadata
        """
        return list(self.saved_searches.values())
    
    def delete_saved_search(self, name: str) -> bool:
        """
        Delete a saved search.
        
        Args:
            name: Saved search name
            
        Returns:
            True if deleted successfully
        """
        if name in self.saved_searches:
            del self.saved_searches[name]
            return True
        return False
    
    def get_search_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent search history.
        
        Args:
            limit: Maximum number of items to return
            
        Returns:
            List of search history items
        """
        return self.search_history[:limit]
    
    def clear_search_history(self) -> None:
        """Clear the search history."""
        self.search_history.clear()
    
    def _add_to_history(self, query_builder: QueryBuilder) -> None:
        """
        Add a query to search history.
        
        Args:
            query_builder: Query builder object
        """
        # Create history item
        history_item = {
            "query": query_builder.build(),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add to history
        self.search_history.insert(0, history_item)
        
        # Limit history size
        if len(self.search_history) > self.max_history_items:
            self.search_history = self.search_history[:self.max_history_items]
    
    def _create_query_from_dict(self, query_data: Dict[str, Any]) -> QueryBuilder:
        """
        Create a query builder from a dictionary.
        
        Args:
            query_data: Query data dictionary
            
        Returns:
            Query builder object
        """
        query = QueryBuilder()
        
        # Set filter group
        if "filter" in query_data:
            query.filter_group = FilterGroup.from_dict(query_data["filter"])
        
        # Set sort fields
        if "sort" in query_data:
            for sort_item in query_data["sort"]:
                query.sort(sort_item["field"], sort_item["direction"])
        
        # Set pagination
        if "limit" in query_data:
            limit = query_data["limit"]
            offset = query_data.get("offset", 0)
            query.paginate(limit, offset)
        
        # Set fields
        if "fields" in query_data:
            query.select(query_data["fields"])
        
        return query


class SearchTemplate:
    """
    Template for common search patterns.
    Provides pre-defined searches with customizable parameters.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize a search template.
        
        Args:
            name: Template name
            description: Template description
        """
        self.name = name
        self.description = description
        self.parameters: Dict[str, Dict[str, Any]] = {}
    
    def add_parameter(self, name: str, type_: str, default_value: Any = None, description: str = None) -> 'SearchTemplate':
        """
        Add a parameter to the template.
        
        Args:
            name: Parameter name
            type_: Parameter type (string, number, date, etc.)
            default_value: Default parameter value
            description: Parameter description
            
        Returns:
            Self for chaining
        """
        self.parameters[name] = {
            "name": name,
            "type": type_,
            "default": default_value,
            "description": description or ""
        }
        
        return self
    
    def build_query(self, parameters: Dict[str, Any]) -> QueryBuilder:
        """
        Build a query from the template.
        
        Args:
            parameters: Parameter values
            
        Returns:
            Query builder object
        """
        # Template-specific implementation in subclasses
        raise NotImplementedError("Subclasses must implement build_query")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class RecentLinksTemplate(SearchTemplate):
    """Template for searching recent links."""
    
    def __init__(self):
        """Initialize the recent links template."""
        super().__init__(
            name="Recent Links",
            description="Find links discovered in the recent past"
        )
        
        self.add_parameter(
            name="days",
            type_="number",
            default_value=7,
            description="Number of days to look back"
        )
        
        self.add_parameter(
            name="limit",
            type_="number",
            default_value=50,
            description="Maximum number of results"
        )
    
    def build_query(self, parameters: Dict[str, Any]) -> QueryBuilder:
        """Build a query for recent links."""
        # Get parameters
        days = parameters.get("days", 7)
        limit = parameters.get("limit", 50)
        
        # Calculate date threshold
        today = datetime.datetime.now()
        threshold = today - datetime.timedelta(days=days)
        threshold_str = threshold.isoformat()
        
        # Create query
        query = QueryBuilder()
        query.filter("discovery_date", FilterOperator.GREATER_THAN, threshold_str)
        query.sort("discovery_date", "desc")
        query.paginate(limit)
        
        return query


class HighStatusLinksTemplate(SearchTemplate):
    """Template for searching high HTTP status links."""
    
    def __init__(self):
        """Initialize the high status links template."""
        super().__init__(
            name="High Status Links",
            description="Find links with successful HTTP status codes"
        )
        
        self.add_parameter(
            name="min_status",
            type_="number",
            default_value=200,
            description="Minimum HTTP status code"
        )
        
        self.add_parameter(
            name="max_status",
            type_="number",
            default_value=299,
            description="Maximum HTTP status code"
        )
        
        self.add_parameter(
            name="limit",
            type_="number",
            default_value=50,
            description="Maximum number of results"
        )
    
    def build_query(self, parameters: Dict[str, Any]) -> QueryBuilder:
        """Build a query for high status links."""
        # Get parameters
        min_status = parameters.get("min_status", 200)
        max_status = parameters.get("max_status", 299)
        limit = parameters.get("limit", 50)
        
        # Create query
        query = QueryBuilder()
        query.filter("http_status", FilterOperator.BETWEEN, min_status, max_status)
        query.filter("is_active", FilterOperator.EQUALS, 1)
        query.sort("last_crawled", "desc")
        query.paginate(limit)
        
        return query


class SearchTemplateRegistry:
    """Registry of available search templates."""
    
    def __init__(self):
        """Initialize the template registry."""
        self.templates: Dict[str, SearchTemplate] = {}
        
        # Register default templates
        self.register(RecentLinksTemplate())
        self.register(HighStatusLinksTemplate())
    
    def register(self, template: SearchTemplate) -> None:
        """
        Register a template.
        
        Args:
            template: Search template
        """
        self.templates[template.name] = template
    
    def get_template(self, name: str) -> Optional[SearchTemplate]:
        """
        Get a template by name.
        
        Args:
            name: Template name
            
        Returns:
            Search template or None if not found
        """
        return self.templates.get(name)
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """
        List all available templates.
        
        Returns:
            List of template metadata
        """
        return [template.to_dict() for template in self.templates.values()]

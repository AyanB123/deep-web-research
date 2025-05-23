"""
Query executor for the Dark Web Discovery System.
Translates QueryBuilder objects into SQL queries and executes them.
"""

import json
import logging
import sqlite3
import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, Set

from query_builder import QueryBuilder, FilterGroup, FilterCondition, FilterOperator, LogicalOperator

class SQLTranslator:
    """
    Translates a query builder object into an SQL query.
    Handles filter conditions, sorting, and pagination.
    """
    
    def __init__(self, table_name: str):
        """
        Initialize the SQL translator.
        
        Args:
            table_name: Database table name
        """
        self.table_name = table_name
        self.logger = logging.getLogger("SQLTranslator")
        
        # Field mapping (QueryBuilder field name -> SQL column name)
        self.field_mapping = {
            # Default mappings - can be extended
            "url": "url",
            "title": "title",
            "content": "content",
            "status": "status",
            "discovery_date": "discovery_date",
            "last_crawled": "last_crawled",
            "category": "category",
            "is_active": "is_active",
            "http_status": "http_status"
        }
        
        # Type mapping for proper value formatting
        self.type_mapping = {
            # Default type mappings - can be extended
            "url": "text",
            "title": "text",
            "content": "text",
            "status": "text",
            "discovery_date": "datetime",
            "last_crawled": "datetime",
            "category": "text",
            "is_active": "integer",
            "http_status": "integer"
        }
    
    def get_sql_field(self, field: str) -> str:
        """
        Get the SQL column name for a field.
        
        Args:
            field: Field name from QueryBuilder
            
        Returns:
            SQL column name
        """
        return self.field_mapping.get(field, field)
    
    def format_value(self, field: str, value: Any) -> Any:
        """
        Format a value for SQL based on its field type.
        
        Args:
            field: Field name
            value: Value to format
            
        Returns:
            Formatted value
        """
        field_type = self.type_mapping.get(field, "text")
        
        if value is None:
            return None
        
        if field_type == "datetime":
            if isinstance(value, datetime.datetime):
                return value.isoformat()
            elif isinstance(value, str):
                # Attempt to parse if it's not already a datetime
                try:
                    dt = datetime.datetime.fromisoformat(value)
                    return value  # Already in ISO format
                except ValueError:
                    # If parsing fails, pass it through
                    return value
            return str(value)
        
        elif field_type == "integer":
            try:
                return int(value)
            except (ValueError, TypeError):
                return value
        
        elif field_type == "real":
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        
        else:  # text or other
            return str(value)
    
    def translate_condition(self, condition: FilterCondition) -> Tuple[str, List[Any]]:
        """
        Translate a filter condition to SQL.
        
        Args:
            condition: Filter condition
            
        Returns:
            (sql_fragment, parameters) tuple
        """
        field = self.get_sql_field(condition.field)
        params = []
        
        # Handle different operators
        if condition.operator == FilterOperator.EQUALS:
            if condition.value is None:
                sql = f"{field} IS NULL"
            else:
                sql = f"{field} = ?"
                params.append(self.format_value(condition.field, condition.value))
        
        elif condition.operator == FilterOperator.NOT_EQUALS:
            if condition.value is None:
                sql = f"{field} IS NOT NULL"
            else:
                sql = f"{field} != ?"
                params.append(self.format_value(condition.field, condition.value))
        
        elif condition.operator == FilterOperator.CONTAINS:
            sql = f"{field} LIKE ?"
            params.append(f"%{self.format_value(condition.field, condition.value)}%")
        
        elif condition.operator == FilterOperator.NOT_CONTAINS:
            sql = f"{field} NOT LIKE ?"
            params.append(f"%{self.format_value(condition.field, condition.value)}%")
        
        elif condition.operator == FilterOperator.STARTS_WITH:
            sql = f"{field} LIKE ?"
            params.append(f"{self.format_value(condition.field, condition.value)}%")
        
        elif condition.operator == FilterOperator.ENDS_WITH:
            sql = f"{field} LIKE ?"
            params.append(f"%{self.format_value(condition.field, condition.value)}")
        
        elif condition.operator == FilterOperator.GREATER_THAN:
            sql = f"{field} > ?"
            params.append(self.format_value(condition.field, condition.value))
        
        elif condition.operator == FilterOperator.LESS_THAN:
            sql = f"{field} < ?"
            params.append(self.format_value(condition.field, condition.value))
        
        elif condition.operator == FilterOperator.BETWEEN:
            sql = f"{field} BETWEEN ? AND ?"
            params.append(self.format_value(condition.field, condition.value))
            params.append(self.format_value(condition.field, condition.value2))
        
        elif condition.operator == FilterOperator.IN_LIST:
            placeholders = ", ".join(["?"] * len(condition.value))
            sql = f"{field} IN ({placeholders})"
            for val in condition.value:
                params.append(self.format_value(condition.field, val))
        
        elif condition.operator == FilterOperator.NOT_IN_LIST:
            placeholders = ", ".join(["?"] * len(condition.value))
            sql = f"{field} NOT IN ({placeholders})"
            for val in condition.value:
                params.append(self.format_value(condition.field, val))
        
        elif condition.operator == FilterOperator.IS_NULL:
            sql = f"{field} IS NULL"
        
        elif condition.operator == FilterOperator.IS_NOT_NULL:
            sql = f"{field} IS NOT NULL"
        
        elif condition.operator == FilterOperator.REGEX:
            # SQLite supports REGEXP but requires an extension
            # Fallback to LIKE with % as a partial match
            self.logger.warning("REGEX operator not fully supported in SQLite, using LIKE")
            sql = f"{field} LIKE ?"
            params.append(f"%{self.format_value(condition.field, condition.value)}%")
        
        else:
            raise ValueError(f"Unsupported operator: {condition.operator}")
        
        return sql, params
    
    def translate_group(self, group: FilterGroup) -> Tuple[str, List[Any]]:
        """
        Translate a filter group to SQL.
        
        Args:
            group: Filter group
            
        Returns:
            (sql_fragment, parameters) tuple
        """
        parts = []
        params = []
        
        # Process conditions
        for condition in group.conditions:
            sql, condition_params = self.translate_condition(condition)
            parts.append(sql)
            params.extend(condition_params)
        
        # Process nested groups
        for nested_group in group.groups:
            sql, group_params = self.translate_group(nested_group)
            parts.append(f"({sql})")
            params.extend(group_params)
        
        # Join with appropriate operator
        if group.operator == LogicalOperator.AND:
            sql = " AND ".join(parts)
        elif group.operator == LogicalOperator.OR:
            sql = " OR ".join(parts)
        elif group.operator == LogicalOperator.NOT:
            # NOT applies to the whole group
            if len(parts) == 1:
                sql = f"NOT ({parts[0]})"
            else:
                # If multiple conditions, AND them together
                sql = f"NOT ({' AND '.join(parts)})"
        else:
            raise ValueError(f"Unsupported logical operator: {group.operator}")
        
        return sql, params
    
    def translate_query(self, query_builder: QueryBuilder) -> Tuple[str, List[Any]]:
        """
        Translate a query builder to an SQL query.
        
        Args:
            query_builder: Query builder object
            
        Returns:
            (sql_query, parameters) tuple
        """
        # Validate the query
        is_valid, error = query_builder.validate()
        if not is_valid:
            raise ValueError(f"Invalid query: {error}")
        
        # Start building the query
        fields = "*"
        if query_builder.fields:
            fields = ", ".join([self.get_sql_field(f) for f in query_builder.fields])
        
        sql = f"SELECT {fields} FROM {self.table_name}"
        params = []
        
        # Add WHERE clause
        if query_builder.filter_group.conditions or query_builder.filter_group.groups:
            where_sql, where_params = self.translate_group(query_builder.filter_group)
            sql += f" WHERE {where_sql}"
            params.extend(where_params)
        
        # Add ORDER BY clause
        if query_builder.sort_fields:
            sort_parts = []
            for sort_item in query_builder.sort_fields:
                field = self.get_sql_field(sort_item["field"])
                direction = sort_item["direction"].upper()
                sort_parts.append(f"{field} {direction}")
            
            sql += f" ORDER BY {', '.join(sort_parts)}"
        
        # Add LIMIT and OFFSET
        if query_builder.limit is not None:
            sql += f" LIMIT {query_builder.limit}"
            
            if query_builder.offset is not None:
                sql += f" OFFSET {query_builder.offset}"
        
        return sql, params

class QueryExecutor:
    """
    Executes queries against the database.
    Converts query builder objects to SQL and returns results.
    """
    
    def __init__(self, db_connection, table_name: str = "onion_links"):
        """
        Initialize the query executor.
        
        Args:
            db_connection: SQLite database connection
            table_name: Database table name
        """
        self.db_connection = db_connection
        self.table_name = table_name
        self.translator = SQLTranslator(table_name)
        self.logger = logging.getLogger("QueryExecutor")
    
    def execute(self, query_builder: QueryBuilder) -> List[Dict[str, Any]]:
        """
        Execute a query and return results.
        
        Args:
            query_builder: Query builder object
            
        Returns:
            List of result rows as dictionaries
        """
        # Translate the query
        sql, params = self.translator.translate_query(query_builder)
        self.logger.debug(f"Executing SQL: {sql} with params {params}")
        
        # Execute the query
        cursor = self.db_connection.cursor()
        cursor.execute(sql, params)
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        # Fetch and convert results
        results = []
        for row in cursor.fetchall():
            # Convert to dictionary
            result = {}
            for i, value in enumerate(row):
                result[column_names[i]] = value
            results.append(result)
        
        return results
    
    def count(self, query_builder: QueryBuilder) -> int:
        """
        Count results for a query.
        
        Args:
            query_builder: Query builder object
            
        Returns:
            Count of matching rows
        """
        # Clone the query builder and remove fields, limit, offset
        count_query = QueryBuilder()
        count_query.filter_group = query_builder.filter_group
        
        # Translate to SQL with COUNT(*)
        sql, params = self.translator.translate_group(count_query.filter_group)
        count_sql = f"SELECT COUNT(*) FROM {self.table_name}"
        if sql:
            count_sql += f" WHERE {sql}"
        
        # Execute
        cursor = self.db_connection.cursor()
        cursor.execute(count_sql, params)
        
        # Get count
        return cursor.fetchone()[0]

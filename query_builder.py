"""
Query builder for advanced searching in the Dark Web Discovery System.
Provides a flexible and powerful way to construct complex queries.
"""

import re
import datetime
import logging
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Tuple, Set

class FilterOperator(str, Enum):
    """Filter operators for query conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    BETWEEN = "between"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    REGEX = "regex"

class LogicalOperator(str, Enum):
    """Logical operators for combining conditions."""
    AND = "and"
    OR = "or"
    NOT = "not"

class FilterCondition:
    """
    A single filter condition in a query.
    Represents a field, operator, and value(s) to filter by.
    """
    
    def __init__(
        self,
        field: str,
        operator: FilterOperator,
        value: Any = None,
        value2: Any = None  # For operators like BETWEEN
    ):
        """
        Initialize a filter condition.
        
        Args:
            field: Field name to filter on
            operator: Filter operator
            value: Primary filter value
            value2: Secondary filter value (for operators like BETWEEN)
        """
        self.field = field
        self.operator = operator
        self.value = value
        self.value2 = value2
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert condition to dictionary for serialization."""
        result = {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value
        }
        
        if self.value2 is not None:
            result["value2"] = self.value2
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterCondition':
        """Create condition from dictionary."""
        return cls(
            field=data["field"],
            operator=FilterOperator(data["operator"]),
            value=data.get("value"),
            value2=data.get("value2")
        )
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate the filter condition.
        
        Returns:
            (is_valid, error_message) tuple
        """
        # Check field
        if not self.field or not isinstance(self.field, str):
            return False, "Field must be a non-empty string"
        
        # Check operator
        if not isinstance(self.operator, FilterOperator):
            return False, f"Invalid operator: {self.operator}"
        
        # Validate based on operator
        if self.operator in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]:
            # No value needed
            return True, None
        
        if self.operator == FilterOperator.BETWEEN:
            # Need both values
            if self.value is None or self.value2 is None:
                return False, "BETWEEN operator requires two values"
        elif self.operator in [FilterOperator.IN_LIST, FilterOperator.NOT_IN_LIST]:
            # Value must be a list
            if not isinstance(self.value, (list, tuple, set)):
                return False, f"{self.operator} operator requires a list value"
            if not self.value:
                return False, f"{self.operator} operator requires a non-empty list"
        else:
            # Most operators need a value
            if self.value is None:
                return False, f"{self.operator} operator requires a value"
        
        return True, None

class FilterGroup:
    """
    A group of filter conditions or other filter groups.
    Groups can be nested to create complex queries with different logical operators.
    """
    
    def __init__(self, operator: LogicalOperator = LogicalOperator.AND):
        """
        Initialize a filter group.
        
        Args:
            operator: Logical operator to combine conditions
        """
        self.operator = operator
        self.conditions: List[FilterCondition] = []
        self.groups: List[FilterGroup] = []
    
    def add_condition(self, condition: FilterCondition) -> 'FilterGroup':
        """
        Add a condition to the group.
        
        Args:
            condition: Filter condition
            
        Returns:
            Self for chaining
        """
        self.conditions.append(condition)
        return self
    
    def add_group(self, group: 'FilterGroup') -> 'FilterGroup':
        """
        Add a nested group.
        
        Args:
            group: Filter group
            
        Returns:
            Self for chaining
        """
        self.groups.append(group)
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert group to dictionary for serialization."""
        return {
            "operator": self.operator.value,
            "conditions": [cond.to_dict() for cond in self.conditions],
            "groups": [group.to_dict() for group in self.groups]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterGroup':
        """Create group from dictionary."""
        group = cls(operator=LogicalOperator(data["operator"]))
        
        # Add conditions
        for cond_data in data.get("conditions", []):
            group.add_condition(FilterCondition.from_dict(cond_data))
        
        # Add nested groups
        for group_data in data.get("groups", []):
            group.add_group(cls.from_dict(group_data))
        
        return group
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate the filter group.
        
        Returns:
            (is_valid, error_message) tuple
        """
        # Must have at least one condition or group
        if not self.conditions and not self.groups:
            return False, "Filter group must have at least one condition or nested group"
        
        # Validate conditions
        for condition in self.conditions:
            is_valid, error = condition.validate()
            if not is_valid:
                return False, error
        
        # Validate nested groups
        for group in self.groups:
            is_valid, error = group.validate()
            if not is_valid:
                return False, error
        
        return True, None

class QueryBuilder:
    """
    Builder for creating and executing advanced queries.
    Supports complex filtering, sorting, and pagination.
    """
    
    def __init__(self):
        """Initialize the query builder."""
        self.filter_group = FilterGroup()
        self.sort_fields: List[Dict[str, str]] = []  # [{"field": "name", "direction": "asc"}]
        self.limit: Optional[int] = None
        self.offset: Optional[int] = None
        self.fields: Optional[List[str]] = None  # Specific fields to return
    
    def filter(self, field: str, operator: Union[FilterOperator, str], value: Any = None, value2: Any = None) -> 'QueryBuilder':
        """
        Add a filter condition.
        
        Args:
            field: Field to filter on
            operator: Filter operator (as enum or string)
            value: Filter value
            value2: Secondary filter value
            
        Returns:
            Self for chaining
        """
        # Convert string operator to enum if needed
        if isinstance(operator, str):
            operator = FilterOperator(operator)
        
        # Create and add condition
        condition = FilterCondition(field, operator, value, value2)
        self.filter_group.add_condition(condition)
        
        return self
    
    def filter_group(self, operator: Union[LogicalOperator, str] = LogicalOperator.AND) -> FilterGroup:
        """
        Create a new filter group.
        
        Args:
            operator: Logical operator for the group
            
        Returns:
            New filter group
        """
        # Convert string operator to enum if needed
        if isinstance(operator, str):
            operator = LogicalOperator(operator)
        
        # Create new group
        group = FilterGroup(operator)
        self.filter_group.add_group(group)
        
        return group
    
    def sort(self, field: str, direction: str = "asc") -> 'QueryBuilder':
        """
        Add a sort field.
        
        Args:
            field: Field to sort by
            direction: Sort direction ("asc" or "desc")
            
        Returns:
            Self for chaining
        """
        # Validate direction
        if direction not in ["asc", "desc"]:
            raise ValueError(f"Invalid sort direction: {direction}")
        
        # Add sort field
        self.sort_fields.append({
            "field": field,
            "direction": direction
        })
        
        return self
    
    def paginate(self, limit: int, offset: int = 0) -> 'QueryBuilder':
        """
        Set pagination.
        
        Args:
            limit: Maximum number of results
            offset: Result offset
            
        Returns:
            Self for chaining
        """
        if limit < 1:
            raise ValueError("Limit must be positive")
        if offset < 0:
            raise ValueError("Offset must be non-negative")
        
        self.limit = limit
        self.offset = offset
        
        return self
    
    def select(self, fields: List[str]) -> 'QueryBuilder':
        """
        Specify fields to return.
        
        Args:
            fields: List of field names
            
        Returns:
            Self for chaining
        """
        self.fields = fields
        return self
    
    def build(self) -> Dict[str, Any]:
        """
        Build the query.
        
        Returns:
            Query dictionary
        """
        query = {
            "filter": self.filter_group.to_dict()
        }
        
        if self.sort_fields:
            query["sort"] = self.sort_fields
        
        if self.limit is not None:
            query["limit"] = self.limit
        
        if self.offset is not None:
            query["offset"] = self.offset
        
        if self.fields is not None:
            query["fields"] = self.fields
        
        return query
    
    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate the query.
        
        Returns:
            (is_valid, error_message) tuple
        """
        # Validate filter group
        is_valid, error = self.filter_group.validate()
        if not is_valid:
            return False, f"Invalid filter: {error}"
        
        return True, None

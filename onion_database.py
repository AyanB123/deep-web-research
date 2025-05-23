import sqlite3
import json
import datetime
import os
from utils import log_action
from config import Config

class OnionLinkDatabase:
    """
    Database for storing and managing onion links with metadata.
    Provides methods to add, update, and query onion links.
    """
    
    def __init__(self, db_path=None):
        """
        Initialize the onion link database.
        
        Args:
            db_path (str, optional): Path to the SQLite database file.
                                     Defaults to Config.ONION_DB_PATH.
        """
        self.db_path = db_path or Config.ONION_DB_PATH
        self.conn = None
        self.cursor = None
        self._init_db()
        
    def _init_db(self):
        """Initialize the database connection and create tables if they don't exist."""
        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            
            # Enable foreign keys
            self.cursor.execute("PRAGMA foreign_keys = ON")
            
            # Create the main onion_links table
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS onion_links (
                id INTEGER PRIMARY KEY,
                url TEXT UNIQUE,
                title TEXT,
                description TEXT,
                category TEXT,
                content_preview TEXT,
                last_checked TIMESTAMP,
                status TEXT,
                discovery_source TEXT,
                trust_score REAL DEFAULT 0.0,
                tags TEXT,
                metadata TEXT
            )
            ''')
            
            # Create indices for faster queries
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON onion_links(url)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON onion_links(category)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON onion_links(status)')
            
            # Create a table for tracking crawl history
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS crawl_history (
                id INTEGER PRIMARY KEY,
                onion_id INTEGER,
                crawl_date TIMESTAMP,
                status TEXT,
                response_time REAL,
                error_message TEXT,
                FOREIGN KEY (onion_id) REFERENCES onion_links(id)
            )
            ''')
            
            self.conn.commit()
            log_action(f"Initialized onion link database at {self.db_path}")
            
        except sqlite3.Error as e:
            log_action(f"Database initialization error: {str(e)}")
            if self.conn:
                self.conn.close()
            raise
    
    def add_link(self, url, title="", description="", category="", 
                 content_preview="", discovery_source="", tags=None, metadata=None):
        """
        Add a new onion link to the database.
        
        Args:
            url (str): The onion URL
            title (str, optional): Title of the site
            description (str, optional): Description of the site
            category (str, optional): Category of the site
            content_preview (str, optional): Preview of the site content
            discovery_source (str, optional): Where this link was discovered
            tags (list, optional): List of tags for the link
            metadata (dict, optional): Additional metadata
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        try:
            tags_json = json.dumps(tags or [])
            metadata_json = json.dumps(metadata or {})
            current_time = datetime.datetime.now().isoformat()
            
            self.cursor.execute(
                """
                INSERT OR IGNORE INTO onion_links 
                (url, title, description, category, content_preview, last_checked, 
                status, discovery_source, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (url, title, description, category, content_preview, current_time, 
                "new", discovery_source, tags_json, metadata_json)
            )
            self.conn.commit()
            
            if self.cursor.rowcount > 0:
                log_action(f"Added new onion link: {url}")
                return True
            else:
                log_action(f"Onion link already exists: {url}")
                return False
                
        except sqlite3.Error as e:
            log_action(f"Error adding link {url}: {str(e)}")
            return False
    
    def update_link(self, url, **kwargs):
        """
        Update an existing onion link in the database.
        
        Args:
            url (str): The onion URL to update
            **kwargs: Fields to update and their values
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            # Special handling for tags and metadata which are stored as JSON
            if 'tags' in kwargs and isinstance(kwargs['tags'], list):
                kwargs['tags'] = json.dumps(kwargs['tags'])
            if 'metadata' in kwargs and isinstance(kwargs['metadata'], dict):
                kwargs['metadata'] = json.dumps(kwargs['metadata'])
            
            # Always update last_checked timestamp
            kwargs['last_checked'] = datetime.datetime.now().isoformat()
            
            # Build the SET clause for the SQL query
            set_clause = ', '.join([f"{key}=?" for key in kwargs.keys()])
            values = list(kwargs.values()) + [url]  # Values for the SET clause + URL for WHERE clause
            
            query = f"UPDATE onion_links SET {set_clause} WHERE url=?"
            self.cursor.execute(query, values)
            self.conn.commit()
            
            if self.cursor.rowcount > 0:
                log_action(f"Updated onion link: {url}")
                return True
            else:
                log_action(f"No onion link to update with URL: {url}")
                return False
                
        except sqlite3.Error as e:
            log_action(f"Error updating link {url}: {str(e)}")
            return False
    
    def update_link_status(self, url, status, title=None, description=None, content_preview=None):
        """
        Update the status of an onion link, optionally updating other fields.
        
        Args:
            url (str): The onion URL to update
            status (str): New status ('active', 'inactive', 'error', etc.)
            title (str, optional): Updated title
            description (str, optional): Updated description
            content_preview (str, optional): Updated content preview
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        update_dict = {'status': status}
        if title is not None:
            update_dict['title'] = title
        if description is not None:
            update_dict['description'] = description
        if content_preview is not None:
            update_dict['content_preview'] = content_preview
            
        return self.update_link(url, **update_dict)
    
    def add_crawl_history(self, url, status, response_time=None, error_message=None):
        """
        Add a crawl history entry for an onion link.
        
        Args:
            url (str): The onion URL
            status (str): Status of the crawl ('success', 'error', etc.)
            response_time (float, optional): Response time in seconds
            error_message (str, optional): Error message if status is 'error'
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        try:
            # Get the onion link ID
            self.cursor.execute("SELECT id FROM onion_links WHERE url=?", (url,))
            result = self.cursor.fetchone()
            
            if not result:
                log_action(f"Cannot add crawl history for unknown URL: {url}")
                return False
                
            onion_id = result[0]
            current_time = datetime.datetime.now().isoformat()
            
            self.cursor.execute(
                """
                INSERT INTO crawl_history
                (onion_id, crawl_date, status, response_time, error_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (onion_id, current_time, status, response_time, error_message)
            )
            self.conn.commit()
            
            return True
                
        except sqlite3.Error as e:
            log_action(f"Error adding crawl history for {url}: {str(e)}")
            return False
    
    def get_links_by_category(self, category, limit=50, offset=0):
        """
        Get onion links by category.
        
        Args:
            category (str): Category to filter by
            limit (int, optional): Maximum number of results
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of dictionaries containing link data
        """
        try:
            self.cursor.execute(
                """
                SELECT url, title, description, status, last_checked, trust_score, tags, metadata
                FROM onion_links 
                WHERE category=? 
                ORDER BY trust_score DESC, last_checked DESC
                LIMIT ? OFFSET ?
                """, 
                (category, limit, offset)
            )
            
            columns = ['url', 'title', 'description', 'status', 'last_checked', 'trust_score', 'tags', 'metadata']
            results = []
            
            for row in self.cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse JSON fields
                try:
                    result['tags'] = json.loads(result['tags']) if result['tags'] else []
                    result['metadata'] = json.loads(result['metadata']) if result['metadata'] else {}
                except json.JSONDecodeError:
                    result['tags'] = []
                    result['metadata'] = {}
                results.append(result)
                
            return results
                
        except sqlite3.Error as e:
            log_action(f"Error getting links by category {category}: {str(e)}")
            return []
    
    def get_links_by_status(self, status, limit=50, offset=0):
        """
        Get onion links by status.
        
        Args:
            status (str): Status to filter by ('new', 'active', 'inactive', 'error')
            limit (int, optional): Maximum number of results
            offset (int, optional): Offset for pagination
            
        Returns:
            list: List of dictionaries containing link data
        """
        try:
            self.cursor.execute(
                """
                SELECT url, title, description, category, last_checked, trust_score
                FROM onion_links 
                WHERE status=? 
                ORDER BY trust_score DESC, last_checked ASC
                LIMIT ? OFFSET ?
                """, 
                (status, limit, offset)
            )
            
            columns = ['url', 'title', 'description', 'category', 'last_checked', 'trust_score']
            results = []
            
            for row in self.cursor.fetchall():
                result = dict(zip(columns, row))
                results.append(result)
                
            return results
                
        except sqlite3.Error as e:
            log_action(f"Error getting links by status {status}: {str(e)}")
            return []
    
    def get_unchecked_links(self, limit=20, older_than_hours=None):
        """
        Get unchecked or outdated onion links.
        
        Args:
            limit (int, optional): Maximum number of results
            older_than_hours (int, optional): Only return links not checked in X hours
            
        Returns:
            list: List of onion URLs
        """
        try:
            if older_than_hours:
                cutoff_time = (datetime.datetime.now() - datetime.timedelta(hours=older_than_hours)).isoformat()
                self.cursor.execute(
                    """
                    SELECT url FROM onion_links 
                    WHERE status='new' OR (last_checked < ? AND status != 'blacklisted')
                    ORDER BY last_checked ASC, trust_score DESC
                    LIMIT ?
                    """, 
                    (cutoff_time, limit)
                )
            else:
                self.cursor.execute(
                    """
                    SELECT url FROM onion_links 
                    WHERE status='new'
                    ORDER BY id DESC
                    LIMIT ?
                    """, 
                    (limit,)
                )
            
            return [row[0] for row in self.cursor.fetchall()]
                
        except sqlite3.Error as e:
            log_action(f"Error getting unchecked links: {str(e)}")
            return []
    
    def search_links(self, query, limit=50):
        """
        Search for onion links by keyword in title, description, or URL.
        
        Args:
            query (str): Search query
            limit (int, optional): Maximum number of results
            
        Returns:
            list: List of dictionaries containing link data
        """
        try:
            search_pattern = f"%{query}%"
            self.cursor.execute(
                """
                SELECT url, title, description, category, status, last_checked
                FROM onion_links 
                WHERE url LIKE ? OR title LIKE ? OR description LIKE ?
                ORDER BY trust_score DESC
                LIMIT ?
                """, 
                (search_pattern, search_pattern, search_pattern, limit)
            )
            
            columns = ['url', 'title', 'description', 'category', 'status', 'last_checked']
            results = []
            
            for row in self.cursor.fetchall():
                result = dict(zip(columns, row))
                results.append(result)
                
            return results
                
        except sqlite3.Error as e:
            log_action(f"Error searching links for '{query}': {str(e)}")
            return []
    
    def get_statistics(self):
        """
        Get statistics about the onion link database.
        
        Returns:
            dict: Database statistics
        """
        stats = {
            'total_links': 0,
            'status_counts': {},
            'category_counts': {},
            'discovery_sources': {},
            'newest_link': None,
            'newest_link_date': None
        }
        
        try:
            # Total links
            self.cursor.execute("SELECT COUNT(*) FROM onion_links")
            stats['total_links'] = self.cursor.fetchone()[0]
            
            # Status counts
            self.cursor.execute("SELECT status, COUNT(*) FROM onion_links GROUP BY status")
            stats['status_counts'] = dict(self.cursor.fetchall())
            
            # Category counts
            self.cursor.execute("SELECT category, COUNT(*) FROM onion_links GROUP BY category")
            stats['category_counts'] = dict(self.cursor.fetchall())
            
            # Discovery sources
            self.cursor.execute("SELECT discovery_source, COUNT(*) FROM onion_links GROUP BY discovery_source")
            stats['discovery_sources'] = dict(self.cursor.fetchall())
            
            # Newest link
            self.cursor.execute(
                """
                SELECT url, last_checked FROM onion_links 
                ORDER BY last_checked DESC LIMIT 1
                """
            )
            result = self.cursor.fetchone()
            if result:
                stats['newest_link'] = result[0]
                stats['newest_link_date'] = result[1]
                
            return stats
                
        except sqlite3.Error as e:
            log_action(f"Error getting database statistics: {str(e)}")
            return stats
    
    def export_links(self, filepath, category=None):
        """
        Export onion links to a JSON file.
        
        Args:
            filepath (str): Path to the output JSON file
            category (str, optional): Only export links in this category
            
        Returns:
            bool: True if exported successfully, False otherwise
        """
        try:
            if category:
                self.cursor.execute(
                    """
                    SELECT url, title, description, category, status, 
                           discovery_source, tags, metadata
                    FROM onion_links 
                    WHERE category=?
                    """, 
                    (category,)
                )
            else:
                self.cursor.execute(
                    """
                    SELECT url, title, description, category, status, 
                           discovery_source, tags, metadata
                    FROM onion_links
                    """
                )
            
            columns = ['url', 'title', 'description', 'category', 'status', 
                      'discovery_source', 'tags', 'metadata']
            results = []
            
            for row in self.cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse JSON fields
                try:
                    result['tags'] = json.loads(result['tags']) if result['tags'] else []
                    result['metadata'] = json.loads(result['metadata']) if result['metadata'] else {}
                except json.JSONDecodeError:
                    result['tags'] = []
                    result['metadata'] = {}
                results.append(result)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
                
            log_action(f"Exported {len(results)} onion links to {filepath}")
            return True
                
        except (sqlite3.Error, IOError) as e:
            log_action(f"Error exporting links: {str(e)}")
            return False
    
    def import_links(self, filepath):
        """
        Import onion links from a JSON file.
        
        Args:
            filepath (str): Path to the input JSON file
            
        Returns:
            int: Number of links imported
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                links = json.load(f)
            
            imported_count = 0
            for link in links:
                tags = json.dumps(link.get('tags', []))
                metadata = json.dumps(link.get('metadata', {}))
                
                self.cursor.execute(
                    """
                    INSERT OR IGNORE INTO onion_links
                    (url, title, description, category, status, discovery_source, tags, metadata, last_checked)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        link.get('url', ''),
                        link.get('title', ''),
                        link.get('description', ''),
                        link.get('category', ''),
                        link.get('status', 'new'),
                        link.get('discovery_source', 'import'),
                        tags,
                        metadata,
                        datetime.datetime.now().isoformat()
                    )
                )
                
                if self.cursor.rowcount > 0:
                    imported_count += 1
                    
            self.conn.commit()
            log_action(f"Imported {imported_count} onion links from {filepath}")
            return imported_count
                
        except (json.JSONDecodeError, IOError, sqlite3.Error) as e:
            log_action(f"Error importing links: {str(e)}")
            return 0
    
    def blacklist_link(self, url, reason=""):
        """
        Blacklist an onion link to prevent future crawling.
        
        Args:
            url (str): The onion URL to blacklist
            reason (str, optional): Reason for blacklisting
            
        Returns:
            bool: True if blacklisted successfully, False otherwise
        """
        metadata = {'blacklist_reason': reason, 'blacklist_date': datetime.datetime.now().isoformat()}
        return self.update_link(url, status='blacklisted', metadata=metadata)
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
            
    def __del__(self):
        """Ensure database connection is closed when object is deleted."""
        self.close()

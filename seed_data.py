"""
Seed data module for the OnionLinkDatabase.
This module contains functions to populate the database with initial directory sites,
search engines, and other seed data for onion link discovery.
"""

from onion_database import OnionLinkDatabase
from utils import log_action
from config import Config

# Ensure required directories exist
Config.init_directories()

def seed_initial_directories(db=None):
    """
    Populate database with known dark web directory sites and search engines.
    
    Args:
        db: OnionLinkDatabase instance (optional). If not provided, a new one will be created.
        
    Returns:
        int: Number of seed sites added
    """
    if db is None:
        db = OnionLinkDatabase()
    
    # List of seed sites grouped by category
    seed_sites = {
        "directory": [
            {
                "url": "http://darkfailllnkf4vf.onion",
                "title": "Dark.fail",
                "description": "Verified dark web market links, providing reliable status updates and URLs"
            },
            {
                "url": "http://s4k4ceiapwwgcm3mkb6e4diqecpo7kvdnfr5gg7sph7jjppqkvwwqtyd.onion",
                "title": "Hidden Wiki",
                "description": "The original Hidden Wiki - directory of onion sites organized by category"
            },
            {
                "url": "http://jaz45aabn5vkemy4jkg4mi4syheisqn2wn2n4fsuitpccdackjwxplad.onion",
                "title": "Onion Links",
                "description": "Community-maintained directory of dark web links with user ratings"
            },
            {
                "url": "http://tortaxi7axzl5jnj2an3wh3zqmfumpkxgkfz7kl7rwgtrfrygozsqd.onion",
                "title": "Tor Taxi",
                "description": "Directory service for verified onion sites"
            },
            {
                "url": "http://torlinkv7cft5zhegrokjrxj2st4hcrymbw2iqbwenptfft4cxfgyjyd.onion",
                "title": "TorLinks",
                "description": "Clean directory of active onion sites"
            }
        ],
        "search_engine": [
            {
                "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion",
                "title": "Ahmia",
                "description": "Search engine for Tor hidden services"
            },
            {
                "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion",
                "title": "Torch",
                "description": "One of the oldest Tor search engines"
            },
            {
                "url": "http://torchdeedp3i2jigzjdmfpn5ttjhthh5wbmda2rr3jvqjg5p77c54dqd.onion",
                "title": "Torch",
                "description": "Alternative URL for Torch search engine"
            },
            {
                "url": "http://srcdemonm74icqjvejew6fprssuolyoc2usjdwflevbdpqoetw4x3ead.onion",
                "title": "Demon",
                "description": "Search engine for the Tor network"
            },
            {
                "url": "http://haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion",
                "title": "Haystak",
                "description": "Dark web search engine with over 1.5 billion indexed pages"
            }
        ],
        "forum": [
            {
                "url": "http://dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion",
                "title": "Dread",
                "description": "Reddit-like forum for dark web discussions and marketplace reviews"
            },
            {
                "url": "http://germanyruvvy2tcw.onion",
                "title": "Deutschland im Deep Web",
                "description": "German-speaking dark web forum"
            }
        ],
        "news": [
            {
                "url": "http://darkzzx4avcsuofgfez5zq75cqc4mprjvfqywo45dfcaxrwqg6qrlfid.onion",
                "title": "Dark Matter",
                "description": "Dark web news and articles"
            },
            {
                "url": "http://protonmailrmez3lotccipshtkleegetolb73fuirgj7r4o4vfu7ozyd.onion",
                "title": "ProtonMail",
                "description": "Secure email service"
            }
        ]
    }
    
    # Add all seed sites to the database
    added_count = 0
    for category, sites in seed_sites.items():
        for site in sites:
            site["category"] = category
            site["discovery_source"] = "seed_data"
            site["tags"] = ["seed", category]
            
            # Add metadata to identify trusted seed sites
            site["metadata"] = {
                "seed_version": "1.0",
                "verified": True,
                "trust_score": 0.9
            }
            
            # Try to add the site to the database
            success = db.add_link(
                url=site["url"],
                title=site["title"],
                description=site["description"],
                category=site["category"],
                discovery_source=site["discovery_source"],
                tags=site["tags"],
                metadata=site["metadata"]
            )
            
            if success:
                added_count += 1
    
    log_action(f"Added {added_count} seed sites to the database")
    return added_count

def verify_seed_links(db=None):
    """
    Verify that seed links are accessible.
    This function attempts to connect to each seed link and updates its status.
    
    Args:
        db: OnionLinkDatabase instance (optional). If not provided, a new one will be created.
        
    Returns:
        dict: Statistics about verification results
    """
    if db is None:
        db = OnionLinkDatabase()
    
    # Get all seed links
    seed_links = []
    for category in ["directory", "search_engine", "forum", "news"]:
        links = db.get_links_by_category(category)
        seed_links.extend([link["url"] for link in links])
    
    # Import here to avoid circular imports
    from crawler import TorCrawler
    
    crawler = TorCrawler()
    crawler.start_tor_session()
    
    stats = {
        "total": len(seed_links),
        "successful": 0,
        "failed": 0
    }
    
    for url in seed_links:
        try:
            log_action(f"Verifying seed link: {url}")
            if crawler.check_onion_status(url):
                db.update_link_status(url, "active")
                stats["successful"] += 1
            else:
                db.update_link_status(url, "inactive")
                stats["failed"] += 1
        except Exception as e:
            log_action(f"Error verifying {url}: {str(e)}")
            db.update_link_status(url, "error")
            stats["failed"] += 1
    
    crawler.close()
    log_action(f"Verified {stats['total']} seed links: {stats['successful']} active, {stats['failed']} failed")
    return stats

if __name__ == "__main__":
    # Initialize the database and seed it with initial data
    db = OnionLinkDatabase()
    added = seed_initial_directories(db)
    
    # Only verify links if new ones were added
    if added > 0:
        verify_seed_links(db)
    
    # Print database statistics
    stats = db.get_statistics()
    log_action("Database statistics:")
    for key, value in stats.items():
        if isinstance(value, dict):
            log_action(f"  {key}:")
            for k, v in value.items():
                log_action(f"    {k}: {v}")
        else:
            log_action(f"  {key}: {value}")
    
    db.close()

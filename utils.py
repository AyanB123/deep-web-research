import logging
from rich.console import Console
import random
import time

console = Console()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="research_agent.log"
)

def log_action(message):
    logging.info(message)
    console.print(f"[bold blue]{message}[/bold blue]")

def randomize_delay(min_delay=2, max_delay=5):
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
    return delay

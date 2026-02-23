#!/usr/bin/env python3
"""
DrupalMind CLI - Command line tool to run migration with detailed debugging.
Usage: python run_migration.py <source_url>

This script runs the migration from the command line with full debug output.
"""
import asyncio
import sys
import os

# Fix Windows Unicode console issues
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add the agents directory to the path
agents_dir = os.path.join(os.path.dirname(__file__), 'agents')
sys.path.insert(0, agents_dir)

# Now import after path is set
from orchestrator import OrchestratorAgent
from memory import memory as shared_memory

# Enable debug logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <source_url>")
        print("Example: python run_migration.py http://192.168.6.149:9999/")
        sys.exit(1)
    
    source = sys.argv[1]
    print(f"Starting migration for: {source}")
    print("=" * 60)
    
    # Create a simple callback to print all events
    async def debug_callback(event):
        event_type = event.get("type", "unknown")
        agent = event.get("agent", "system")
        message = event.get("message", "")
        detail = event.get("detail", "")
        data = event.get("data", {})
        
        print(f"\n[{agent}] {event_type}: {message}")
        if detail:
            print(f"  Detail: {detail}")
        if data:
            # Pretty print the data
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    print(f"  {key}:")
                    import json
                    print(f"    {json.dumps(value, indent=2)[:500]}")
                else:
                    print(f"  {key}: {value}")
    
    # Create orchestrator with debug callback
    orchestrator = OrchestratorAgent(broadcast_cb=debug_callback)
    
    # Run the migration
    try:
        result = await orchestrator.run(source, mode="url")
        print("\n" + "=" * 60)
        print("Migration Result:")
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import sys
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seed import main

if __name__ == "__main__":
    asyncio.run(main())

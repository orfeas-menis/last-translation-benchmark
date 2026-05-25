import asyncio
import sys
import os

# Add parent directory to path to import server.db
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.db import get_submissions, save_submission

async def migrate_reject_to_return():
    print("Fetching submissions...")
    submissions = await get_submissions()
    
    updated_count = 0
    for sub in submissions:
        updated = False
        
        # 1. Migrate "reject" to "return" status
        if sub.get("status") == "reject":
            sub["status"] = "return"
            updated = True
            
        if updated:
            await save_submission(sub)
            updated_count += 1
            
    print(f"Migration completed. Updated {updated_count} submissions.")

if __name__ == "__main__":
    asyncio.run(migrate_reject_to_return())

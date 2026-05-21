import asyncio
import sys
import os

# Add project root to sys.path so we can import from server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.utils import send_email

if __name__ == "__main__":
    # Test call (sending to oneself for testing)
    asyncio.run(send_email(
        to_email="vilem.zouhar+ltb@gmail.com",
        subject="Last Translation Benchmark [registration]",
        body="Hello! This is a test email sent from the automated script using server.utils. <b>Testing html?</b>"
    ))

import os
import logging
from simple_bot import app # simple_bot.py se Flask app import kar rahe hain

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Starting Amazon Affiliate Bot on port {port}...")
    app.run(host='0.0.0.0', port=port)

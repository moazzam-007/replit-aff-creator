import os
import logging
import requests
import json
from flask import Flask, request, jsonify, render_template
import re

# Assuming these exist in your project in the same directory
from amazon_scraper import AmazonScraper
from url_shortener import URLShortener

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='templates') # templates folder specify kiya

# Bot configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Initialize services
amazon_scraper = AmazonScraper()
url_shortener = URLShortener()

def send_message(chat_id, text, parse_mode='Markdown'):
    """Send message to Telegram chat"""
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error sending message to chat {chat_id}: {e}")
        return False

def send_photo(chat_id, photo_url, caption, parse_mode='Markdown'):
    """Send photo with caption to Telegram chat"""
    try:
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        data = {
            'chat_id': chat_id,
            'photo': photo_url,
            'caption': caption,
            'parse_mode': parse_mode
        }
        response = requests.post(url, json=data, timeout=15)
        response.raise_for_status()
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error sending photo to chat {chat_id}: {e}")
        return False

def handle_start_command(chat_id, user_id):
    """Handle /start command"""
    welcome_message = """🛍️ **Welcome to Amazon Affiliate Bot!**

Mein aapka shopping assistant hun! 😊

✨ **Main kya kar sakta hun:**
• Amazon product links process karta hun
• Product ki image aur details nikalta hun
• Affiliate link banata hun (`budgetlooks08-21` tag ke saath)
• Shortened URL provide karta hun

📝 **Kaise use kare:**
Bas koi bhi Amazon product ka link bhej do!

Supported domains:
• amazon.com
• amazon.in
• amazon.co.uk
• aur bhi!

Type /help for more details! 🚀"""
    
    return send_message(chat_id, welcome_message)

def handle_help_command(chat_id, user_id):
    """Handle /help command"""
    help_message = """🔧 **Help & Instructions:**

**Supported Amazon domains:**
• amazon.com
• amazon.in
• amazon.co.uk
• amazon.ca
• amazon.de
• amazon.fr
• amazon.it
• amazon.es

**How to use:**
1️⃣ Copy any Amazon product URL
2️⃣ Send it to me in chat
3️⃣ I'll extract product info & image
4️⃣ Generate affiliate link with `budgetlooks08-21` tag
5️⃣ Provide shortened URL

**Example:**
Send: `https://amazon.in/dp/B08N5WRWNW`
Get: Product image + affiliate link

Need more help? Just ask! 💬"""
    
    return send_message(chat_id, help_message)

def handle_amazon_url(chat_id, user_id, url):
    """Handle Amazon product URL"""
    try:
        logger.info(f"🔗 Processing Amazon URL for user {user_id}: {url}")
        
        # Send processing message
        send_message(chat_id, "🔍 Processing kar raha hun... Wait karo! ⏳")
        
        # Extract product information
        logger.info("📊 Extracting product info...")
        product_info = amazon_scraper.extract_product_info(url)
        
        if not product_info or not product_info.get('title'):
            send_message(chat_id, 
                "😔 Sorry! Product information extract nahi kar paya.\n"
                "Kya aap sure hain ki ye valid Amazon product link hai? 🤔")
            return
        
        # Generate affiliate link
        logger.info("🔗 Generating affiliate link...")
        affiliate_url = amazon_scraper.generate_affiliate_link(url)
        
        # Shorten the affiliate link
        logger.info("✂️ Shortening URL...")
        shortened_url = url_shortener.shorten_url(affiliate_url)
        
        # Prepare response message
        title = product_info['title']
        # Truncate title if too long, and add "..."
        if len(title) > 100:
            title = title[:97] + "..."
        
        response_message = f"🛍️ **{title}**\n\n"
        
        if product_info.get('price'):
            response_message += f"💰 **Price:** {product_info['price']}\n\n"
        
        response_message += f"🔗 **Yahan hai aapka affiliate link:**\n`{shortened_url}`\n\n"
        response_message += "✨ Is link se purchase karne par mujhe commission milegi! Thank you! 😊"
        
        # Send product image if available
        if product_info.get('image_url'):
            success = send_photo(chat_id, product_info['image_url'], response_message)
            if not success:
                # If photo fails, send message as fallback
                logger.warning(f"Failed to send photo for {url}, sending as text message.")
                send_message(chat_id, response_message)
        else:
            logger.info(f"No image URL found for {url}, sending as text message.")
            send_message(chat_id, response_message)
            
        logger.info(f"✅ Successfully processed Amazon URL for user {user_id}")
            
    except Exception as e:
        logger.error(f"❌ Error handling Amazon URL for user {user_id}: {e}")
        send_message(chat_id, 
            "😞 Kuch technical problem aa gayi hai!\n"
            "Please thodi der baad try karo ya dusra link bhejo. 🔧")

def handle_general_message(chat_id, user_id, message):
    """Handle general conversation"""
    try:
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'namaste', 'hola']):
            response = "Hey there! 👋 Main Amazon affiliate bot hun!\nAmazon ka koi product link bhejo! 🛍️✨"
            
        elif any(word in message_lower for word in ['thanks', 'thank you', 'shukriya', 'dhanyawad']):
            response = "Welcome! Khushi hui help karke! 😊\nAur Amazon products chahiye toh link bhej dena! 🛒"
            
        elif any(word in message_lower for word in ['how', 'kaise', 'kya', 'help']):
            response = ("Main Amazon affiliate bot hun! 🤖\n\n"
                        "📝 **Kaise use kare:**\n"
                        "1. Amazon product link bhejo\n"
                        "2. Main image extract karunga\n"
                        "3. Affiliate link banaunga\n"
                        "4. Shortened URL dunga\n\n"
                        "Try karo! 🚀")
            
        elif 'amazon' in message_lower:
            response = ("Haan! Amazon ke liye hi bana hun! 🛍️\n"
                        "Koi bhi Amazon product ka link bhejo! ⚡\n\n"
                        "Example: amazon.in/dp/PRODUCT_ID")
            
        else:
            response = ("Main sirf Amazon product links handle karta hun! 🛒\n\n"
                        "Koi Amazon product ka link bhejo jaise:\n"
                        "• `amazon.in/dp/PRODUCT_ID`\n"
                        "• `amazon.com/dp/PRODUCT_ID`\n\n"
                        "Main image aur affiliate link banake dunga! 😊")
        
        send_message(chat_id, response)
        logger.info(f"✅ General message handled for user: {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error in handle_general_message for user {user_id}: {e}")
        send_message(chat_id, "Sorry! Reply nahi kar paya. Please try again! 🔧")

def is_amazon_url(text):
    """Check if text contains Amazon URL"""
    amazon_url_patterns = [
        # Standard product page URL
        r'https?://(?:www\.)?amazon\.[a-z.]{2,6}/(?:[^/]+/)?(?:dp|gp/product)/([A-Z0-9]{10})',
        # Shortened amzn.to links
        r'https?://amzn\.to/[a-zA-Z0-9]+',
        # Shortened a.co links
        r'https?://a\.co/[a-zA-Z0-9]+',
        # Amazon.tld/something/dp/ASIN (sometimes dp is nested)
        r'https?://(?:www\.)?amazon\.[a-z.]{2,6}/(?:[^/]+/)*dp/([A-Z0-9]{10})',
        # General amazon.tld/any_path that might contain ASIN
        r'https?://(?:www\.)?amazon\.[a-z.]{2,6}/[^\s]+', # Catch-all for any amazon link
        # Direct ASIN in some cases (less common but good to catch)
        r'([A-Z0-9]{10})' # If user just sends ASIN, though requires context
    ]
    
    for pattern in amazon_url_patterns:
        if re.search(pattern, text):
            # For pure ASINs, ensure it's not just random text that looks like an ASIN
            # This is a heuristic, can be improved
            if re.match(r'^[A-Z0-9]{10}$', text) and not re.match(r'[a-z]', text): # check if it's only caps/numbers
                return True # Assuming direct ASINs are product IDs
            elif re.match(r'https?://', text): # If it's a full URL, it's likely Amazon
                return True
    return False


@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook updates"""
    try:
        update_data = request.get_json()
        
        if not update_data:
            logger.warning("No data received in webhook.")
            return jsonify({"status": "error", "message": "No data"}), 400
        
        # Extract message info
        message = update_data.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        user_id = message.get('from', {}).get('id')
        text = message.get('text', '')
        
        if not chat_id or not user_id:
            logger.warning("Invalid message received (missing chat_id or user_id).")
            return jsonify({"status": "error", "message": "Invalid message"}), 400
        
        logger.info(f"📨 Processing message from user {user_id} (chat: {chat_id}): {text[:50]}...")
        
        # Handle commands
        if text.startswith('/start'):
            handle_start_command(chat_id, user_id)
        elif text.startswith('/help'):
            handle_help_command(chat_id, user_id)
        elif is_amazon_url(text):
            # Pass the original text, amazon_scraper will clean it
            handle_amazon_url(chat_id, user_id, text)
        else:
            handle_general_message(chat_id, user_id, text)
            
        return jsonify({"status": "ok"}), 200
            
    except Exception as e:
        logger.error(f"❌ Webhook general error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint for Render"""
    return jsonify({
        "status": "healthy",
        "message": "Amazon Affiliate Bot is running! 🤖",
        "bot_token_set": bool(BOT_TOKEN and BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE')
    })

@app.route('/')
def home():
    """Home page to show general information or a simple dashboard"""
    return render_template('index.html')

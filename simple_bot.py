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
CHANNEL_ID = os.getenv('CHANNEL_ID') # <-- Naya environment variable add kiya hai
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
• Har tarah ki Amazon links ko process karta hun (shortened, offer, page links)
• Product ki image aur details nikalta hun
• Affiliate link banata hun (`budgetlooks08-21` tag ke saath)
• Har link ko TinyURL se shorten karta hun

📝 **Kaise use kare:**
Bas koi bhi Amazon link bhej do! 🚀"""
    
    return send_message(chat_id, welcome_message)

def handle_help_command(chat_id, user_id):
    """Handle /help command"""
    help_message = """🔧 **Help & Instructions:**

**Supported Amazon links:**
• Product links: `amazon.in/dp/...`, `amzn.to/...`
• Offer & Page links: `amazon.in/h/rewards/...`, `amazon.in/amazonprime...`

**How to use:**
1️⃣ Copy any Amazon link
2️⃣ Send it to me in chat
3️⃣ I'll process the link and send you an affiliate link with details

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
        
        # Agar scraper ne kuch bhi info nahi nikali
        if not product_info:
            send_message(chat_id, 
                "😔 Sorry! Product information extract nahi kar paya.\n"
                "Kya aap sure hain ki ye valid Amazon link hai? 🤔")
            return

        # Generate affiliate link
        logger.info("🔗 Generating affiliate link...")
        affiliate_url = amazon_scraper.generate_affiliate_link(url)
        
        # Shorten the affiliate link
        logger.info("✂️ Shortening URL...")
        shortened_url = url_shortener.shorten_url(affiliate_url)
        
        # Check if it's a product link or a general page link
        is_product_link = product_info.get('is_product_link', False)
        
        if is_product_link:
            title = product_info['title']
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
                if CHANNEL_ID and success: # <-- Yahan check add kiya hai
                    send_photo(CHANNEL_ID, product_info['image_url'], response_message)
            else:
                send_message(chat_id, response_message)
                if CHANNEL_ID:
                    send_message(CHANNEL_ID, response_message)
        else:
            # Output format for page/offer links
            title = product_info.get('title', 'Amazon Offer/Page')
            response_message = f"🔗 **{title}**\n\n"
            response_message += f"**Yahan hai aapka affiliate link:**\n`{shortened_url}`\n\n"
            response_message += "✨ Is link se purchase karne par mujhe commission milegi! Thank you! 😊"
            send_message(chat_id, response_message)
            if CHANNEL_ID: # <-- Yahan check add kiya hai
                send_message(CHANNEL_ID, response_message)

        logger.info(f"✅ Successfully processed URL for user {user_id}")
            
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
                        "1. Amazon link bhejo\n"
                        "2. Main process karunga\n"
                        "3. Affiliate link banaunga\n"
                        "4. Shortened URL dunga\n\n"
                        "Try karo! 🚀")
            
        elif 'amazon' in message_lower:
            response = ("Haan! Amazon ke liye hi bana hun! 🛍️\n"
                        "Koi bhi Amazon link bhejo! ⚡\n\n"
                        "Example: `amazon.in/dp/PRODUCT_ID`")
            
        else:
            response = ("Main sirf Amazon links handle karta hun! 🛒\n\n"
                        "Koi Amazon link bhejo jaise:\n"
                        "• `amazon.in/dp/PRODUCT_ID`\n"
                        "• `amzn.to/PRODUCT_ID`\n\n"
                        "Main affiliate link banake dunga! 😊")
        
        send_message(chat_id, response)
        logger.info(f"✅ General message handled for user: {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error in handle_general_message for user {user_id}: {e}")
        send_message(chat_id, "Sorry! Reply nahi kar paya. Please try again! 🔧")

def is_amazon_url(text):
    """Check if text contains Amazon URL"""
    amazon_url_patterns = [
        r'https?://(?:www\.)?amazon\.[a-z.]{2,6}/', # All amazon.tld domains
        r'https?://(?:amzn\.to|a\.co)/', # Shortened URLs
        r'([A-Z0-9]{10})' # Direct ASIN as a fallback (less reliable)
    ]
    
    for pattern in amazon_url_patterns:
        if re.search(pattern, text):
            # A simple heuristic to avoid matching random 10-digit strings
            if 'dp/' in text or 'amzn.to' in text or 'a.co' in text:
                return True
            elif re.match(r'^[A-Z0-9]{10}$', text) and not re.match(r'[a-z]', text):
                return True
            elif re.search(r'amazon\.[a-z.]{2,6}', text):
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

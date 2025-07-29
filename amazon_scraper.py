import requests
from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import json

logger = logging.getLogger(__name__)

class AmazonScraper:
    def __init__(self, affiliate_tag="budgetlooks08-21"):
        self.affiliate_tag = affiliate_tag
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        }
        self.supported_domains = [
            'amazon.com', 'amazon.in', 'amazon.co.uk', 'amazon.ca',
            'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es',
            'amzn.to', 'a.co' # Shortened domains will be redirected
        ]

    def _get_asin_from_url(self, url):
        """Extracts ASIN (Product ID) from various Amazon URL formats."""
        parsed_url = urlparse(url)
        
        # Check for standard /dp/ASIN or /gp/product/ASIN patterns
        match = re.search(r'(?:dp|gp/product)/([A-Z0-9]{10})', parsed_url.path)
        if match:
            return match.group(1)

        # Check query parameters for ASIN (less common for product pages but possible)
        query_params = parse_qs(parsed_url.query)
        if 'ASIN' in query_params:
            return query_params['ASIN'][0]
        if 'asin' in query_params:
            return query_params['asin'][0]
        
        # If it's a shortened URL (amzn.to, a.co), we can't get ASIN directly from URL
        # The scraper will have to follow the redirect and get it from the final URL/page.
        return None

    def _clean_amazon_url(self, url):
        """Cleans and normalizes Amazon URLs to a standard format (e.g., .../dp/ASIN)."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        # Handle shortened URLs by attempting to get the final redirected URL
        if "amzn.to" in domain or "a.co" in domain:
            try:
                # Allow redirects to get the full Amazon URL
                response = requests.head(url, headers=self.headers, allow_redirects=True, timeout=5)
                response.raise_for_status()
                final_url = response.url
                logger.info(f"Shortened URL {url} redirected to: {final_url}")
                parsed_url = urlparse(final_url)
                domain = parsed_url.netloc # Update domain to the final one
            except requests.exceptions.RequestException as e:
                logger.warning(f"Could not resolve shortened URL {url}: {e}. Proceeding with original.")
        
        # Ensure it's a supported domain after potential redirect
        if not any(d in domain for d in self.supported_domains):
             logger.warning(f"URL domain {domain} not in supported domains. Returning original URL.")
             return url # Or raise an error, depending on desired strictness

        asin = self._get_asin_from_url(parsed_url.geturl()) # Get ASIN from the (potentially resolved) URL

        if asin:
            # Construct a clean URL with just the domain and /dp/ASIN
            cleaned_url = urlunparse(parsed_url._replace(path=f"/dp/{asin}", query='', fragment=''))
            logger.info(f"🔗 Cleaned URL: {cleaned_url}")
            return cleaned_url
        
        logger.warning(f"Could not extract ASIN from {url}. Using original URL for scraping.")
        return url # Fallback to original URL if ASIN extraction fails

    def extract_product_info(self, url):
        """
        Extracts product title, image URL, and price from an Amazon product page.
        This scraper is designed to be robust but may need updates if Amazon changes its page structure.
        """
        product_info = {
            'title': None,
            'image_url': None,
            'price': None
        }

        # First, clean the URL to get a standard product page URL
        effective_url = self._clean_amazon_url(url)
        
        try:
            logger.info(f"Attempting to scrape from: {effective_url}")
            response = requests.get(effective_url, headers=self.headers, timeout=20) # Increased timeout
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            
            soup = BeautifulSoup(response.content, 'lxml') # Using lxml parser for speed

            # Extract Title
            # Priority 1: productTitle (most common)
            title_tag = soup.find(id='productTitle')
            if title_tag:
                product_info['title'] = title_tag.get_text(strip=True)
            else:
                # Priority 2: title (some older/different pages)
                title_tag = soup.find(id='title')
                if title_tag:
                    product_info['title'] = title_tag.get_text(strip=True)
                else:
                    # Priority 3: meta title as a last resort
                    meta_title = soup.find('meta', {'property': 'og:title'})
                    if meta_title and meta_title.get('content'):
                        product_info['title'] = meta_title['content'].split(':', 1)[-1].strip() # Remove "Amazon.in: " prefix


            # Extract Image URL
            # Priority 1: landingImage data-a-dynamic-image (contains high-res images)
            image_tag = soup.find('img', {'id': 'landingImage'})
            if image_tag and image_tag.get('data-a-dynamic-image'):
                try:
                    img_json = json.loads(image_tag['data-a-dynamic-image'])
                    # Get the largest image URL (keys are URLs, values are [width, height])
                    product_info['image_url'] = sorted(img_json.keys(), key=lambda k: max(img_json[k]), reverse=True)[0]
                except (json.JSONDecodeError, IndexError) as e:
                    logger.warning(f"Error parsing data-a-dynamic-image: {e}. Falling back to src.")
                    product_info['image_url'] = image_tag.get('src') # Fallback to simple src
            elif image_tag: # Fallback if data-a-dynamic-image not present
                product_info['image_url'] = image_tag.get('src')
            else:
                # Priority 2: imgTagWrapperId (common for main image container)
                img_wrapper = soup.find(id='imgTagWrapperId')
                if img_wrapper:
                    img_tag_in_wrapper = img_wrapper.find('img')
                    if img_tag_in_wrapper:
                        product_info['image_url'] = img_tag_in_wrapper.get('src')
                # Priority 3: Other common image containers or meta tags
                if not product_info['image_url']:
                    meta_image = soup.find('meta', {'property': 'og:image'})
                    if meta_image and meta_image.get('content'):
                        product_info['image_url'] = meta_image['content']


            # Extract Price
            # Priority 1: Common price IDs/classes
            price_span = soup.find(id='priceblock_ourprice') or \
                         soup.find(id='priceblock_saleprice') or \
                         soup.find(class_='a-price-whole') or \
                         soup.find('span', {'class': 'a-offscreen'}) # Invisible price
            
            if price_span:
                price_text = price_span.get_text(strip=True)
                # For a-offscreen, currency symbol might be separate
                if soup.find('span', {'class': 'a-price-symbol'}) and 'a-offscreen' in price_span.get('class', []):
                    symbol = soup.find('span', {'class': 'a-price-symbol'}).get_text(strip=True)
                    product_info['price'] = f"{symbol}{price_text}"
                else:
                    product_info['price'] = price_text
            else:
                # Priority 2: Check for 'price' in JavaScript variables (more complex)
                # This often involves finding a script tag with 'jQuery.parseJSON' or similar
                # For now, keeping it simpler, relying on direct HTML elements.
                pass 

            if not product_info['title']:
                logger.warning(f"Could not extract title from {effective_url}")
            if not product_info['image_url']:
                logger.warning(f"Could not extract image from {effective_url}")
            if not product_info['price']:
                logger.warning(f"Could not extract price from {effective_url}")

            logger.info(f"Extracted info: Title='{product_info['title']}', Image='{product_info['image_url']}', Price='{product_info['price']}'")

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching URL {effective_url}: {e}")
        except Exception as e:
            logger.error(f"Error scraping product info from {effective_url}: {e}", exc_info=True) # exc_info=True for full traceback

        return product_info

    def generate_affiliate_link(self, original_url):
        """Generates an Amazon affiliate link."""
        parsed_url = urlparse(original_url)
        domain = parsed_url.netloc

        # Resolve shortened URLs first to get the actual Amazon domain and path
        if "amzn.to" in domain or "a.co" in domain:
            try:
                response = requests.head(original_url, headers=self.headers, allow_redirects=True, timeout=5)
                response.raise_for_status()
                original_url = response.url # Use the resolved URL
                parsed_url = urlparse(original_url)
                domain = parsed_url.netloc
                logger.info(f"Resolved shortened URL to: {original_url}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Could not resolve shortened URL {original_url}: {e}. Proceeding with original.")
                # Fallback: if resolution fails, try to use the original domain for tag, but might fail if not amazon.tld

        # Ensure it's a supported Amazon domain before adding tag
        if not any(d in domain for d in self.supported_domains if d not in ['amzn.to', 'a.co']): # Exclude shortened from this check
            logger.warning(f"Unsupported domain for affiliate link generation: {domain}. Returning original URL.")
            return original_url

        # Remove existing tags and common tracking parameters
        query_params = parse_qs(parsed_url.query)
        query_params.pop('tag', None)
        query_params.pop('ref_', None)
        query_params.pop('th', None) # another common tracking param

        # Add your affiliate tag
        query_params['tag'] = [self.affiliate_tag]

        # Reconstruct the URL, ensuring no double slashes or extra path segments
        # Keep only domain and ASIN part, then add query
        asin = self._get_asin_from_url(original_url)
        
        if asin:
            # Construct a clean base URL with just the domain and /dp/ASIN
            base_url = urlunparse(parsed_url._replace(path=f"/dp/{asin}", query='', fragment=''))
        else:
            # If ASIN can't be found, use the path from the parsed URL (might not be ideal but better than nothing)
            # This case means _clean_amazon_url also failed to find a standard ASIN path
            base_url = urlunparse(parsed_url._replace(query='', fragment=''))
            logger.warning(f"ASIN not found for {original_url}, using original path for affiliate link.")

        # Add new query parameters
        new_query = urlencode(query_params, doseq=True)
        affiliate_url = f"{base_url}?{new_query}" if new_query else base_url # Only add ? if query exists
        
        logger.info(f"Generated affiliate link: {affiliate_url}")
        return affiliate_url

import re
import requests
from bs4 import BeautifulSoup
import logging
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
            'amzn.to', 'a.co'
        ]

    def _resolve_url(self, url):
        """Resolves shortened URLs and redirects to get the final Amazon URL."""
        try:
            # Use GET request to resolve redirects, which is more reliable than HEAD
            response = requests.get(url, headers=self.headers, allow_redirects=True, timeout=10)
            response.raise_for_status()
            final_url = response.url
            logger.info(f"URL {url} resolved to: {final_url}")
            return final_url
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not resolve URL {url}: {e}. Proceeding with original.")
            return url

    def extract_product_info(self, url):
        """Extracts product info for both product pages and general pages."""
        product_info = {
            'title': None,
            'price': None,
            'image_url': None,
            'is_product_link': False
        }
        
        resolved_url = self._resolve_url(url)
        
        # Check if the resolved URL looks like a product page
        if '/dp/' in resolved_url or '/gp/product/' in resolved_url:
            return self._scrape_product_page(resolved_url)
        else:
            return self._scrape_general_page(resolved_url)

    def _scrape_product_page(self, url):
        """Scrapes a specific Amazon product page for details."""
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            # Extract Title
            title_tag = soup.find(id='productTitle')
            title = title_tag.get_text(strip=True) if title_tag else None

            # Extract Price
            price_span = soup.find(id='priceblock_ourprice') or soup.find(class_='a-price-whole') or soup.find('span', {'class': 'a-offscreen'})
            price = price_span.get_text(strip=True) if price_span else None

            # Extract Image
            image_tag = soup.find('img', {'id': 'landingImage'})
            image_url = image_tag.get('src') if image_tag else None

            product_info = {
                'title': title,
                'price': price,
                'image_url': image_url,
                'is_product_link': True
            }
            logger.info(f"Extracted product info for {url}: {product_info['title']}")
            return product_info
        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping product page {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting info from product page {url}: {e}", exc_info=True)
            return None

    def _scrape_general_page(self, url):
        """Scrapes a general Amazon page (e.g., offer or search results) for a title."""
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            # Try to get title from meta tags or page title
            title_tag = soup.find('meta', property='og:title')
            title = title_tag['content'] if title_tag and title_tag.get('content') else soup.title.string if soup.title else 'Amazon Offer/Page'
            
            # Clean up title
            if title and 'Amazon.in' in title:
                title = title.split('Amazon.in:', 1)[-1].strip()

            product_info = {
                'title': title,
                'price': None,
                'image_url': None,
                'is_product_link': False
            }
            logger.info(f"Extracted general page title for {url}: {product_info['title']}")
            return product_info
        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping general page {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting info from general page {url}: {e}", exc_info=True)
            return None

    def generate_affiliate_link(self, original_url):
        """Generates an Amazon affiliate link for any supported URL."""
        resolved_url = self._resolve_url(original_url)
        parsed_url = urlparse(resolved_url)
        
        if not any(d in parsed_url.netloc for d in self.supported_domains):
            logger.warning(f"Unsupported domain {parsed_url.netloc}. Returning original URL.")
            return original_url
        
        query_params = parse_qs(parsed_url.query)
        query_params.pop('tag', None)
        query_params.pop('ref_', None)
        query_params.pop('th', None)
        
        query_params['tag'] = [self.affiliate_tag]
        
        new_query = urlencode(query_params, doseq=True)
        affiliate_url = urlunparse(parsed_url._replace(query=new_query))
        
        logger.info(f"Generated affiliate link: {affiliate_url}")
        return affiliate_url

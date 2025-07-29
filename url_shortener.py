import requests
import logging

logger = logging.getLogger(__name__)

class URLShortener:
    def __init__(self):
        pass

    def shorten_url(self, long_url):
        """
        Shortens a given URL using TinyURL and is.gd.
        Falls back to original URL if shortening fails.
        """
        # Try TinyURL first
        tinyurl_api_url = f"http://tinyurl.com/api-create.php?url={long_url}"
        try:
            response = requests.get(tinyurl_api_url, timeout=5)
            response.raise_for_status()
            short_url = response.text.strip()
            if short_url.startswith('http'):
                logger.info(f"✅ TinyURL success: {short_url}")
                return short_url
            else:
                logger.warning(f"TinyURL returned non-URL: {short_url}. Trying is.gd.")
        except requests.exceptions.RequestException as e:
            logger.warning(f"TinyURL failed: {e}. Trying is.gd.")

        # If TinyURL fails, try is.gd
        isgd_api_url = f"https://is.gd/create.php?format=simple&url={long_url}"
        try:
            response = requests.get(isgd_api_url, timeout=5)
            response.raise_for_status()
            short_url = response.text.strip()
            if short_url.startswith('http'):
                logger.info(f"✅ is.gd success: {short_url}")
                return short_url
            else:
                logger.warning(f"is.gd returned non-URL: {short_url}. Falling back to original.")
        except requests.exceptions.RequestException as e:
            logger.warning(f"is.gd failed: {e}. Falling back to original URL.")

        logger.info("❌ All URL shorteners failed. Returning original URL.")
        return long_url

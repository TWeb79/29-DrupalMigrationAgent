"""
DrupalMind - Media Migrator
Handles media asset download and upload to Drupal.
"""
import logging
import requests
import os
import hashlib
from typing import List, Dict, Optional
from pathlib import Path
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


class MediaMigrator:
    """Handles media asset download and upload to Drupal."""
    
    def __init__(self, drupal_client, source_url: str, cache_dir: str = "/tmp/drupal_migration_media"):
        """
        Initialize the media migrator.
        
        Args:
            drupal_client: DrupalClient instance for uploading files
            source_url: Base URL of the source website
            cache_dir: Local directory for caching downloaded media
        """
        self.drupal_client = drupal_client
        self.source_url = source_url.rstrip('/')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure request session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DrupalMind MediaMigrator/1.0'
        })
        
        # Track migration progress
        self.media_map = {}  # Maps old URLs to new Drupal file IDs
    
    def migrate_media(self, content_list: List[Dict]) -> Dict:
        """
        Download and upload all media from content.
        
        Args:
            content_list: List of content items with potential media
            
        Returns:
            Dict with migration report:
                - total: Total media items found
                - successful: Successfully migrated
                - failed: Failed to migrate
                - failed_urls: List of failed URLs
                - media_map: Dict mapping old URLs to new Drupal file IDs
        """
        report = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'failed_urls': [],
            'media_map': {}
        }
        
        # Extract all media URLs from content
        all_media_urls = self._extract_media_urls(content_list)
        report['total'] = len(all_media_urls)
        
        logger.info(f"Found {len(all_media_urls)} media items to migrate")
        
        for old_url in all_media_urls:
            try:
                # Skip if already processed
                if old_url in report['media_map']:
                    continue
                    
                # Download media
                local_path = self._download_media(old_url)
                if not local_path:
                    report['failed'] += 1
                    report['failed_urls'].append(old_url)
                    logger.warning(f"✗ Failed to download: {old_url}")
                    continue
                
                # Upload to Drupal
                drupal_file_id = self._upload_to_drupal(local_path, old_url)
                if drupal_file_id:
                    report['successful'] += 1
                    report['media_map'][old_url] = drupal_file_id
                    logger.info(f"✓ Migrated media: {old_url} -> {drupal_file_id}")
                else:
                    report['failed'] += 1
                    report['failed_urls'].append(old_url)
                    logger.warning(f"✗ Failed to upload: {old_url}")
            
            except Exception as e:
                logger.error(f"Media migration error for {old_url}: {e}")
                report['failed'] += 1
                report['failed_urls'].append(old_url)
        
        report['success'] = report['failed'] == 0
        logger.info(f"Media migration complete: {report['successful']}/{report['total']} successful")
        
        # Update internal media map
        self.media_map.update(report['media_map'])
        
        return report
    
    def _extract_media_urls(self, content_list: List[Dict]) -> List[str]:
        """Extract all image/media URLs from content."""
        urls = set()
        
        for content in content_list:
            # Extract from media field
            if 'media' in content:
                for media in content['media']:
                    if 'url' in media:
                        urls.add(media['url'])
            
            # Extract from body content (img src)
            if 'body' in content:
                body = content['body']
                if isinstance(body, str):
                    img_urls = re.findall(r'src=["\'](.*?)["\']', body)
                    urls.update(img_urls)
            
            # Extract from summary
            if 'summary' in content:
                summary = content['summary']
                if isinstance(summary, str):
                    img_urls = re.findall(r'src=["\'](.*?)["\']', summary)
                    urls.update(img_urls)
            
            # Extract from custom image fields
            for field in ['image', 'images', 'featured_image', 'thumbnail']:
                if field in content:
                    val = content[field]
                    if isinstance(val, str):
                        urls.add(val)
                    elif isinstance(val, dict) and 'url' in val:
                        urls.add(val['url'])
        
        return list(urls)
    
    def _download_media(self, url: str) -> Optional[str]:
        """
        Download media file locally.
        
        Args:
            url: URL of the media file
            
        Returns:
            Local file path or None if failed
        """
        try:
            # Handle relative URLs
            if not url.startswith('http'):
                url = urljoin(self.source_url + '/', url)
            
            # Create safe filename
            parsed = urlparse(url)
            filename = Path(parsed.path).name or 'download'
            
            # Handle empty or dangerous filenames
            if not filename or filename in ['/', '']:
                filename = f'media_{hashlib.md5(url.encode()).hexdigest()[:8]}'
            
            # Check for file extension
            if '.' not in filename:
                filename += '.jpg'  # Default to jpg
            
            local_path = self.cache_dir / filename
            
            # Check if already cached
            if local_path.exists():
                logger.debug(f"Using cached: {url}")
                return str(local_path)
            
            # Download file
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Save to cache
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            logger.debug(f"Downloaded: {url} -> {local_path}")
            return str(local_path)
        
        except requests.exceptions.Timeout:
            logger.error(f"Timeout downloading {url}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error downloading {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None
    
    def _upload_to_drupal(self, local_path: str, original_url: str) -> Optional[str]:
        """
        Upload file to Drupal and return file ID.
        
        Args:
            local_path: Path to local file
            original_url: Original URL of the file
            
        Returns:
            Drupal file ID or None if failed
        """
        try:
            with open(local_path, 'rb') as f:
                file_content = f.read()
            
            filename = Path(local_path).name
            
            # Use Drupal JSON:API to upload
            if hasattr(self.drupal_client, 'upload_file'):
                response = self.drupal_client.upload_file(
                    filename=filename,
                    content=file_content
                )
                
                if response and 'data' in response:
                    file_id = response['data'].get('id')
                    logger.info(f"Uploaded to Drupal: {filename} (ID: {file_id})")
                    return file_id
            
            # Fallback: Use base64 encoding method
            import base64
            b64_content = base64.b64encode(file_content).decode('utf-8')
            
            # Try to create file entity
            payload = {
                "data": {
                    "type": "file--file",
                    "attributes": {
                        "filename": filename,
                        "uri": f"base64:{b64_content}"
                    }
                }
            }
            
            response = self.drupal_client._make_request(
                'POST',
                '/jsonapi/file/file',
                json=payload
            )
            
            if response and 'data' in response:
                file_id = response['data'].get('id')
                logger.info(f"Uploaded to Drupal (base64): {filename} (ID: {file_id})")
                return file_id
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to upload {original_url} to Drupal: {e}")
            return None
    
    def update_content_references(self, content_list: List[Dict]) -> List[Dict]:
        """
        Update content to use new Drupal media URLs instead of old source URLs.
        
        Args:
            content_list: List of content items
            
        Returns:
            Updated content list with new media references
        """
        updated_content = []
        
        for content in content_list:
            updated = content.copy()
            
            # Update body content
            if 'body' in updated and isinstance(updated['body'], str):
                for old_url, new_id in self.media_map.items():
                    # Replace old URLs with Drupal file references
                    updated['body'] = updated['body'].replace(old_url, f'/files/{new_id}')
            
            # Update media field
            if 'media' in updated:
                for media in updated['media']:
                    if 'url' in media and media['url'] in self.media_map:
                        media['drupal_id'] = self.media_map[media['url']]
                        media['url'] = f'/files/{self.media_map[media["url"]]}'
            
            updated_content.append(updated)
        
        return updated_content
    
    def cleanup_cache(self):
        """Clean up cached media files."""
        try:
            for file in self.cache_dir.iterdir():
                if file.is_file():
                    file.unlink()
            logger.info(f"Cleaned up cache directory: {self.cache_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup cache: {e}")


# Import re for regex
import re

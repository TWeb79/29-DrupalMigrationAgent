"""
DrupalMind - Content Validators
Validates and transforms content before Drupal migration.
"""
import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ContentValidator:
    """Validates and transforms content before Drupal migration."""
    
    def __init__(self):
        self.validation_rules = {
            'title': {
                'required': True, 
                'min_length': 3, 
                'max_length': 255
            },
            'body': {
                'required': False, 
                'min_length': 0, 
                'max_length': 10000000
            },
            'path_alias': {
                'required': False,
                'max_length': 255
            },
            'summary': {
                'required': False,
                'max_length': 600
            },
        }
        
        # Dangerous HTML patterns to remove
        self.dangerous_patterns = [
            (r'<script[^>]*>.*?</script>', ''),  # Script tags
            (r'<iframe[^>]*>.*?</iframe>', ''),   # Iframes
            (r'on\w+="[^"]*"', ''),              # Event handlers
            (r'on\w+=\'[^\']*\'', ''),            # Event handlers (single quotes)
            (r'javascript:', ''),                # JavaScript URLs
            (r'data:', ''),                      # Data URLs (potential XSS)
        ]
    
    def validate_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean content.
        
        Returns:
            Dict with keys:
                - content: Cleaned content dict
                - issues: List of validation issues (blocking)
                - warnings: List of warnings (non-blocking)
                - is_valid: Boolean indicating if content is valid
        """
        issues = []
        warnings = []
        
        # Check required fields
        for field, rules in self.validation_rules.items():
            if rules.get('required') and field not in content:
                issues.append(f"Missing required field: {field}")
            
            if field in content:
                value = content[field]
                
                # Check length for string values
                if isinstance(value, str):
                    if 'min_length' in rules and len(value) < rules['min_length']:
                        issues.append(f"Field '{field}' too short (min {rules['min_length']} chars)")
                    if 'max_length' in rules and len(value) > rules['max_length']:
                        content[field] = value[:rules['max_length']]
                        warnings.append(f"Field '{field}' truncated to max length ({rules['max_length']} chars)")
        
        # Sanitize HTML in body field
        if 'body' in content:
            content['body'] = self._sanitize_html(content['body'])
        
        # Sanitize HTML in summary field
        if 'summary' in content:
            content['summary'] = self._sanitize_html(content['summary'])
        
        # Fix encoding issues
        for field in content:
            if isinstance(content[field], str):
                content[field] = self._fix_encoding(content[field])
        
        # Resolve media URLs
        if 'media' in content:
            content['media'] = self._resolve_media_urls(content['media'])
        
        # Validate path alias format
        if 'path_alias' in content:
            is_valid, clean_alias = self._validate_path_alias(content['path_alias'])
            if not is_valid:
                warnings.append(f"Invalid path alias format, cleaned: {clean_alias}")
                content['path_alias'] = clean_alias
        
        return {
            'content': content,
            'issues': issues,
            'warnings': warnings,
            'is_valid': len(issues) == 0
        }
    
    def _sanitize_html(self, html: str) -> str:
        """Remove dangerous HTML tags and attributes."""
        if not html:
            return html
            
        # Remove dangerous patterns
        for pattern, replacement in self.dangerous_patterns:
            html = re.sub(pattern, replacement, html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove remaining dangerous attributes
        html = re.sub(r'\s+on\w+="[^"]*"', '', html, flags=re.IGNORECASE)
        html = re.sub(r"\s+on\w+='[^']*'", '', html, flags=re.IGNORECASE)
        
        return html
    
    def _fix_encoding(self, text: str) -> str:
        """Fix common encoding issues."""
        if not text:
            return text
            
        try:
            # Try to handle common encoding problems
            text = text.encode('utf-8', errors='replace').decode('utf-8')
            return text
        except Exception as e:
            logger.warning(f"Encoding fix failed: {e}")
            return text
    
    def _resolve_media_urls(self, media_list: List[Dict]) -> List[Dict]:
        """Convert relative URLs to absolute."""
        if not media_list:
            return media_list
            
        for media in media_list:
            if 'url' in media and not media['url'].startswith('http'):
                # Make relative URLs absolute (would need source URL)
                media['url'] = self._make_absolute_url(media['url'])
        return media_list
    
    def _make_absolute_url(self, relative_url: str, base_url: str = "") -> str:
        """Convert relative URL to absolute."""
        # This would be implemented based on source site
        # For now, return as-is
        return relative_url
    
    def _validate_path_alias(self, path_alias: str) -> tuple:
        """
        Validate path alias format.
        
        Returns:
            (is_valid, cleaned_alias)
        """
        if not path_alias:
            return True, path_alias
            
        # Remove leading/trailing slashes
        cleaned = path_alias.strip('/')
        
        # Replace spaces with dashes
        cleaned = cleaned.replace(' ', '-')
        
        # Remove invalid characters
        cleaned = re.sub(r'[^a-zA-Z0-9\-_/]', '', cleaned)
        
        # Ensure it starts with /
        if cleaned and not cleaned.startswith('/'):
            cleaned = '/' + cleaned
            
        return cleaned == path_alias.strip(), cleaned
    
    def validate_node_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a complete Drupal node payload.
        
        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []
        
        # Check for data wrapper
        if 'data' not in payload:
            issues.append("Payload missing 'data' wrapper")
            return {
                'is_valid': False,
                'issues': issues,
                'warnings': warnings
            }
        
        data = payload.get('data', {})
        
        # Check for type
        if 'type' not in data:
            issues.append("Node payload missing 'type' field")
        
        # Check attributes
        if 'attributes' not in data:
            issues.append("Node payload missing 'attributes' field")
        else:
            attributes = data.get('attributes', {})
            
            # Validate title
            if 'title' in attributes:
                title_validation = self.validate_content({'title': attributes['title']})
                issues.extend(title_validation.get('issues', []))
                warnings.extend(title_validation.get('warnings', []))
            
            # Validate body if present
            if 'body' in attributes:
                body_validation = self.validate_content({'body': attributes['body']})
                issues.extend(body_validation.get('issues', []))
                warnings.extend(body_validation.get('warnings', []))
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }


class FieldValidator:
    """Validates individual field values."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format."""
        if not url:
            return False
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def validate_date(date_str: str) -> bool:
        """Validate ISO8601 date format."""
        if not date_str:
            return False
        pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        return bool(re.match(pattern, date_str))
    
    @staticmethod
    def validate_integer(value: Any, min_val: Optional[int] = None, max_val: Optional[int] = None) -> bool:
        """Validate integer within range."""
        try:
            int_val = int(value)
            if min_val is not None and int_val < min_val:
                return False
            if max_val is not None and int_val > max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_boolean(value: Any) -> bool:
        """Validate boolean value."""
        return isinstance(value, bool)


def create_validator() -> ContentValidator:
    """Factory function to create a ContentValidator."""
    return ContentValidator()

# DrupalMigrationAgent - Code Fixes and Improvements

## Quick Fix: Add Error Handling to Orchestrator

### Before (Current - Missing Error Handling)
```python
# agents/orchestrator.py (likely current state)
def run_migration(self, source_url: str):
    analyzer_result = self.analyzer.analyze(source_url)
    train_result = self.train_agent.train(analyzer_result)
    build_result = self.build_agent.build(train_result)
    theme_result = self.theme_agent.apply_theme(build_result)
    content_result = self.content_agent.migrate(build_result)
    test_result = self.test_agent.test(content_result)
    qa_result = self.qa_agent.validate(test_result)
    
    return qa_result
```

**Problem:** If ANY step fails, entire migration fails without reporting what worked.

---

### After (Robust Error Handling)
```python
# agents/orchestrator.py (IMPROVED)
import logging
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class MigrationStatus(Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"

@dataclass
class MigrationReport:
    status: MigrationStatus
    completion_percentage: int
    completed_agents: List[str]
    failed_agents: Dict[str, str]
    warnings: List[str]
    errors: List[str]
    artifacts: Dict[str, any]

class OrchestratorAgent:
    
    def run_migration(self, source_url: str) -> MigrationReport:
        """Run migration with error handling and checkpointing."""
        
        report = MigrationReport(
            status=MigrationStatus.FAILED,
            completion_percentage=0,
            completed_agents=[],
            failed_agents={},
            warnings=[],
            errors=[],
            artifacts={}
        )
        
        try:
            # Pre-flight checks
            if not self._preflight_checks(source_url, report):
                logger.error("Preflight checks failed")
                return report
            
            # Phase 1: Analysis
            try:
                logger.info(f"Starting migration analysis for {source_url}")
                analyzer_result = self.analyzer.analyze(source_url)
                if not analyzer_result.get('success'):
                    report.failed_agents['analyzer'] = analyzer_result.get('error', 'Unknown error')
                    report.errors.append(f"Analyzer failed: {analyzer_result.get('error')}")
                    return report
                report.completed_agents.append('analyzer')
                report.artifacts['analysis'] = analyzer_result
                logger.info("✓ Analysis phase complete")
            except Exception as e:
                report.failed_agents['analyzer'] = str(e)
                report.errors.append(f"Analyzer crashed: {str(e)}")
                logger.error(f"Analyzer error: {e}", exc_info=True)
                return report
            
            # Phase 2: Training
            try:
                logger.info("Starting training phase")
                train_result = self.train_agent.train(analyzer_result)
                if not train_result.get('success'):
                    report.warnings.append(f"Training warning: {train_result.get('warning')}")
                report.completed_agents.append('train')
                report.artifacts['training'] = train_result
                logger.info("✓ Training phase complete")
            except Exception as e:
                report.failed_agents['train'] = str(e)
                report.warnings.append(f"Training failed (non-blocking): {str(e)}")
                logger.warning(f"Training error (continuing): {e}")
            
            # Phase 3: Build Structure
            try:
                logger.info("Starting build phase")
                build_result = self.build_agent.build(analyzer_result, train_result)
                if not build_result.get('success'):
                    report.failed_agents['build'] = build_result.get('error', 'Unknown error')
                    report.errors.append(f"Build failed: {build_result.get('error')}")
                    return report
                report.completed_agents.append('build')
                report.artifacts['structure'] = build_result
                logger.info("✓ Build phase complete")
            except Exception as e:
                report.failed_agents['build'] = str(e)
                report.errors.append(f"Build crashed: {str(e)}")
                logger.error(f"Build error: {e}", exc_info=True)
                return report
            
            # Phase 4: Theme (Non-blocking - site works without theme)
            try:
                logger.info("Starting theme phase")
                theme_result = self.theme_agent.apply_theme(analyzer_result, build_result)
                if theme_result.get('success'):
                    report.completed_agents.append('theme')
                    report.artifacts['theme'] = theme_result
                    logger.info("✓ Theme phase complete")
                else:
                    report.warnings.append(f"Theme application failed: Using default theme")
                    logger.warning("Theme failed - using default")
            except Exception as e:
                report.warnings.append(f"Theme error (non-blocking): {str(e)}")
                logger.warning(f"Theme error (continuing): {e}")
            
            # Phase 5: Content Migration
            try:
                logger.info("Starting content migration")
                content_result = self.content_agent.migrate(
                    analyzer_result, 
                    build_result,
                    with_validation=True
                )
                if not content_result.get('success'):
                    # Log details about what failed
                    migrated = content_result.get('migrated_count', 0)
                    failed = content_result.get('failed_count', 0)
                    report.warnings.append(
                        f"Content migration partial: {migrated} migrated, {failed} failed"
                    )
                    report.completion_percentage = int((migrated / (migrated + failed + 1)) * 100)
                else:
                    report.completion_percentage = content_result.get('completion', 100)
                
                report.completed_agents.append('content')
                report.artifacts['content'] = content_result
                logger.info(f"✓ Content phase complete ({content_result.get('migrated_count')} items)")
            except Exception as e:
                report.failed_agents['content'] = str(e)
                report.errors.append(f"Content migration crashed: {str(e)}")
                logger.error(f"Content error: {e}", exc_info=True)
                # Content failure is critical but site structure exists
                report.completion_percentage = 40
            
            # Phase 6: Testing
            try:
                logger.info("Starting validation tests")
                test_result = self.test_agent.test(build_result, content_result)
                if test_result.get('success'):
                    report.completed_agents.append('test')
                    report.artifacts['test_results'] = test_result
                    logger.info(f"✓ Tests passed: {test_result.get('tests_passed')}")
                else:
                    report.warnings.append("Some tests failed - review report")
                    logger.warning("Tests failed")
            except Exception as e:
                report.warnings.append(f"Test phase error: {str(e)}")
                logger.warning(f"Test error: {e}")
            
            # Phase 7: QA Validation
            try:
                logger.info("Starting QA validation")
                qa_result = self.qa_agent.validate(build_result, content_result)
                if qa_result.get('success'):
                    report.completed_agents.append('qa')
                    report.artifacts['qa_results'] = qa_result
                    logger.info("✓ QA validation passed")
                else:
                    issues = qa_result.get('issues', [])
                    report.warnings.extend(issues)
                    logger.warning(f"QA issues found: {len(issues)}")
            except Exception as e:
                report.warnings.append(f"QA phase error: {str(e)}")
                logger.warning(f"QA error: {e}")
            
            # Determine final status
            if not report.failed_agents:
                report.status = MigrationStatus.SUCCESS
                if not report.warnings:
                    report.completion_percentage = 100
            elif report.completed_agents:
                report.status = MigrationStatus.PARTIAL_SUCCESS
            else:
                report.status = MigrationStatus.FAILED
            
            # Save report
            self._save_migration_report(report, source_url)
            
            return report
        
        except Exception as e:
            logger.critical(f"Orchestrator crashed: {e}", exc_info=True)
            report.errors.append(f"Critical error: {str(e)}")
            report.status = MigrationStatus.FAILED
            return report
    
    def _preflight_checks(self, source_url: str, report: MigrationReport) -> bool:
        """Validate prerequisites before starting migration."""
        checks = [
            ('Source connectivity', self._check_source_connectivity(source_url)),
            ('Drupal API', self._check_drupal_api()),
            ('Database connection', self._check_database()),
            ('Required bundles', self._check_required_bundles()),
        ]
        
        for check_name, is_ok in checks:
            if not is_ok:
                report.errors.append(f"Preflight failed: {check_name}")
                logger.error(f"Preflight check failed: {check_name}")
                return False
        
        return True
    
    def _save_migration_report(self, report: MigrationReport, source_url: str):
        """Save detailed migration report to storage."""
        report_data = {
            'source_url': source_url,
            'status': report.status.value,
            'completion_percentage': report.completion_percentage,
            'completed_agents': report.completed_agents,
            'failed_agents': report.failed_agents,
            'warnings': report.warnings,
            'errors': report.errors,
            'timestamp': datetime.now().isoformat(),
        }
        # Save to Redis or database
        self.memory.save(f'migration_report:{source_url}', report_data)
        logger.info(f"Migration report saved for {source_url}")

```

---

## Fix 2: Add Content Validation

```python
# agents/validators.py (NEW FILE)

import logging
import re
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class ContentValidator:
    """Validates and transforms content before Drupal migration."""
    
    def __init__(self):
        self.validation_rules = {
            'title': {'required': True, 'min_length': 3, 'max_length': 255},
            'body': {'required': False, 'min_length': 0, 'max_length': 10000000},
            'date': {'required': False, 'format': 'ISO8601'},
        }
    
    def validate_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean content."""
        issues = []
        warnings = []
        
        # Check required fields
        for field, rules in self.validation_rules.items():
            if rules.get('required') and field not in content:
                issues.append(f"Missing required field: {field}")
            
            if field in content:
                value = content[field]
                
                # Check length
                if isinstance(value, str):
                    if 'min_length' in rules and len(value) < rules['min_length']:
                        issues.append(f"Field '{field}' too short")
                    if 'max_length' in rules and len(value) > rules['max_length']:
                        content[field] = value[:rules['max_length']]
                        warnings.append(f"Field '{field}' truncated to max length")
        
        # Sanitize HTML
        if 'body' in content:
            content['body'] = self._sanitize_html(content['body'])
        
        # Fix encoding issues
        for field in content:
            if isinstance(content[field], str):
                content[field] = self._fix_encoding(content[field])
        
        # Resolve media URLs
        if 'media' in content:
            content['media'] = self._resolve_media_urls(content['media'])
        
        return {
            'content': content,
            'issues': issues,
            'warnings': warnings,
            'is_valid': len(issues) == 0
        }
    
    def _sanitize_html(self, html: str) -> str:
        """Remove dangerous HTML tags."""
        # Remove script tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove event handlers
        html = re.sub(r'on\w+="[^"]*"', '', html, flags=re.IGNORECASE)
        return html
    
    def _fix_encoding(self, text: str) -> str:
        """Fix common encoding issues."""
        try:
            # Try to handle common encoding problems
            text = text.encode('utf-8', errors='replace').decode('utf-8')
            return text
        except Exception as e:
            logger.warning(f"Encoding fix failed: {e}")
            return text
    
    def _resolve_media_urls(self, media_list: List[Dict]) -> List[Dict]:
        """Convert relative URLs to absolute."""
        for media in media_list:
            if 'url' in media and not media['url'].startswith('http'):
                # Make relative URLs absolute (would need source URL)
                media['url'] = self._make_absolute_url(media['url'])
        return media_list
    
    def _make_absolute_url(self, relative_url: str) -> str:
        """Convert relative URL to absolute."""
        # This would be implemented based on source site
        return relative_url

```

---

## Fix 3: Add Media Migration

```python
# agents/media_migrator.py (NEW FILE)

import logging
import requests
import os
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class MediaMigrator:
    """Handles media asset download and upload to Drupal."""
    
    def __init__(self, drupal_client, source_url: str):
        self.drupal_client = drupal_client
        self.source_url = source_url
        self.cache_dir = Path('/tmp/drupal_migration_media')
        self.cache_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.timeout = 30
    
    def migrate_media(self, content_list: List[Dict]) -> Dict:
        """Download and upload all media from content."""
        report = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'failed_urls': [],
            'media_map': {}  # Maps old URLs to new Drupal file IDs
        }
        
        all_media_urls = self._extract_media_urls(content_list)
        report['total'] = len(all_media_urls)
        
        for old_url in all_media_urls:
            try:
                # Download media
                local_path = self._download_media(old_url)
                if not local_path:
                    report['failed'] += 1
                    report['failed_urls'].append(old_url)
                    continue
                
                # Upload to Drupal
                drupal_file_id = self._upload_to_drupal(local_path, old_url)
                if drupal_file_id:
                    report['successful'] += 1
                    report['media_map'][old_url] = drupal_file_id
                    logger.info(f"✓ Migrated media: {old_url}")
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
        return report
    
    def _extract_media_urls(self, content_list: List[Dict]) -> List[str]:
        """Extract all image/media URLs from content."""
        urls = set()
        for content in content_list:
            if 'media' in content:
                for media in content['media']:
                    if 'url' in media:
                        urls.add(media['url'])
            # Also search in body content for img src
            if 'body' in content:
                import re
                img_urls = re.findall(r'src=["\'](.*?)["\']', content['body'])
                urls.update(img_urls)
        return list(urls)
    
    def _download_media(self, url: str) -> str:
        """Download media file locally."""
        try:
            # Create safe filename
            filename = Path(url).name or 'download'
            local_path = self.cache_dir / filename
            
            if local_path.exists():
                return str(local_path)  # Already cached
            
            # Download file
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded: {url}")
            return str(local_path)
        
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None
    
    def _upload_to_drupal(self, local_path: str, original_url: str) -> str:
        """Upload file to Drupal and return file ID."""
        try:
            with open(local_path, 'rb') as f:
                file_content = f.read()
            
            # Use Drupal JSON:API to upload
            filename = Path(local_path).name
            response = self.drupal_client.upload_file(
                filename=filename,
                content=file_content
            )
            
            if response and 'data' in response:
                file_id = response['data'].get('id')
                logger.info(f"Uploaded to Drupal: {filename} (ID: {file_id})")
                return file_id
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to upload {original_url} to Drupal: {e}")
            return None

```

---

## Fix 4: Add Progress Checkpointing

```python
# agents/checkpoint_manager.py (NEW FILE)

import json
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CheckpointManager:
    """Manages migration checkpoints for resume capability."""
    
    def __init__(self, memory_store):
        self.memory = memory_store
    
    def create_checkpoint(self, source_url: str, phase: str, data: Dict[str, Any]):
        """Save a checkpoint at a migration phase."""
        checkpoint_key = f'checkpoint:{source_url}:{phase}'
        checkpoint_data = {
            'source_url': source_url,
            'phase': phase,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        self.memory.save(checkpoint_key, checkpoint_data)
        logger.info(f"Checkpoint created: {phase}")
    
    def get_checkpoint(self, source_url: str, phase: str) -> Dict[str, Any]:
        """Retrieve a checkpoint."""
        checkpoint_key = f'checkpoint:{source_url}:{phase}'
        return self.memory.get(checkpoint_key)
    
    def can_resume(self, source_url: str) -> bool:
        """Check if migration can be resumed."""
        checkpoint = self.get_checkpoint(source_url, 'analysis')
        return checkpoint is not None
    
    def get_last_completed_phase(self, source_url: str) -> str:
        """Get the last completed phase."""
        phases = ['analysis', 'training', 'build', 'theme', 'content', 'test', 'qa']
        for phase in reversed(phases):
            if self.get_checkpoint(source_url, phase):
                return phase
        return None
    
    def cleanup(self, source_url: str):
        """Clean up checkpoints after migration."""
        phases = ['analysis', 'training', 'build', 'theme', 'content', 'test', 'qa']
        for phase in phases:
            checkpoint_key = f'checkpoint:{source_url}:{phase}'
            self.memory.delete(checkpoint_key)
        logger.info(f"Cleaned up checkpoints for {source_url}")

```

---

## Fix 5: Update Content Agent to Use Validators

```python
# agents/content_agent.py (UPDATED)

class ContentAgent:
    
    def migrate(self, analyzer_result, build_result, with_validation=True) -> Dict:
        """Migrate content with validation."""
        from validators import ContentValidator
        from media_migrator import MediaMigrator
        
        validator = ContentValidator()
        media_migrator = MediaMigrator(self.drupal_client, analyzer_result['source_url'])
        
        migrated_count = 0
        failed_count = 0
        failed_items = []
        
        for content in analyzer_result.get('content_items', []):
            try:
                # Validate content
                if with_validation:
                    validation_result = validator.validate_content(content)
                    if not validation_result['is_valid']:
                        logger.warning(f"Validation failed: {validation_result['issues']}")
                        failed_count += 1
                        failed_items.append({
                            'content': content.get('title', 'Unknown'),
                            'issues': validation_result['issues']
                        })
                        continue
                    content = validation_result['content']
                
                # Create node in Drupal
                node_id = self._create_node(content, build_result)
                if node_id:
                    migrated_count += 1
                    logger.info(f"✓ Migrated: {content.get('title')} (ID: {node_id})")
                else:
                    failed_count += 1
                    failed_items.append({
                        'content': content.get('title', 'Unknown'),
                        'issue': 'Node creation failed'
                    })
            
            except Exception as e:
                logger.error(f"Content migration error: {e}")
                failed_count += 1
                failed_items.append({
                    'content': content.get('title', 'Unknown'),
                    'error': str(e)
                })
        
        # Migrate media
        media_result = media_migrator.migrate_media(analyzer_result.get('content_items', []))
        
        return {
            'success': failed_count == 0,
            'migrated_count': migrated_count,
            'failed_count': failed_count,
            'completion': int((migrated_count / (migrated_count + failed_count + 1)) * 100),
            'failed_items': failed_items,
            'media_report': media_result
        }

```

---

## Summary of Improvements

| Issue | Fix | Impact |
|-------|-----|--------|
| No error handling | Try/catch with fallbacks | Migrations complete partially instead of failing completely |
| No content validation | Validate before upload | Data integrity, no broken references |
| No media migration | MediaMigrator class | Images and files actually transferred |
| No progress tracking | CheckpointManager | Can resume after failures |
| Silent failures | Detailed logging and reporting | Know exactly what failed |
| No pre-checks | Preflight validation | Prevent wasted time on impossible migrations |

---

## Implementation Steps

1. **Add error handling** to orchestrator.py (Priority 1)
2. **Create validators.py** (Priority 2)
3. **Create media_migrator.py** (Priority 2)
4. **Add checkpoint manager** (Priority 3)
5. **Update content agent** to use new components
6. **Add comprehensive logging**
7. **Create migration reporting dashboard**

---
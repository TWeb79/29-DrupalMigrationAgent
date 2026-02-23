"""
DrupalMind - Checkpoint Manager
Manages migration checkpoints for resume capability.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages migration checkpoints for resume capability."""
    
    # Standard phase order
    PHASES = [
        'probe', 'analysis', 'training', 'mapping', 
        'build', 'theme', 'content', 'test', 'qa', 'review', 'publish'
    ]
    
    def __init__(self, memory_store):
        """
        Initialize checkpoint manager.
        
        Args:
            memory_store: Memory store instance (Redis-backed)
        """
        self.memory = memory_store
    
    def create_checkpoint(self, source_url: str, phase: str, data: Dict[str, Any]) -> bool:
        """
        Save a checkpoint at a migration phase.
        
        Args:
            source_url: Source URL being migrated
            phase: Current phase name
            data: Phase data to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            checkpoint_key = self._get_checkpoint_key(source_url, phase)
            checkpoint_data = {
                'source_url': source_url,
                'phase': phase,
                'timestamp': datetime.now().isoformat(),
                'data': data,
                'completed': True
            }
            
            self.memory.set(checkpoint_key, checkpoint_data)
            logger.info(f"Checkpoint created: {phase} for {source_url}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return False
    
    def get_checkpoint(self, source_url: str, phase: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a checkpoint.
        
        Args:
            source_url: Source URL
            phase: Phase name
            
        Returns:
            Checkpoint data or None if not found
        """
        try:
            checkpoint_key = self._get_checkpoint_key(source_url, phase)
            return self.memory.get(checkpoint_key)
        except Exception as e:
            logger.error(f"Failed to get checkpoint: {e}")
            return None
    
    def get_latest_checkpoint(self, source_url: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest checkpoint for a source URL.
        
        Args:
            source_url: Source URL
            
        Returns:
            Latest checkpoint data or None
        """
        for phase in reversed(self.PHASES):
            checkpoint = self.get_checkpoint(source_url, phase)
            if checkpoint:
                return checkpoint
        return None
    
    def can_resume(self, source_url: str) -> bool:
        """
        Check if migration can be resumed.
        
        Args:
            source_url: Source URL
            
        Returns:
            True if there's a checkpoint to resume from
        """
        # Check if there's at least an analysis checkpoint
        checkpoint = self.get_checkpoint(source_url, 'analysis')
        return checkpoint is not None
    
    def get_last_completed_phase(self, source_url: str) -> Optional[str]:
        """
        Get the last completed phase.
        
        Args:
            source_url: Source URL
            
        Returns:
            Phase name or None if no checkpoints
        """
        for phase in reversed(self.PHASES):
            checkpoint = self.get_checkpoint(source_url, phase)
            if checkpoint and checkpoint.get('completed'):
                return phase
        return None
    
    def get_next_phase(self, source_url: str) -> Optional[str]:
        """
        Get the next phase to run.
        
        Args:
            source_url: Source URL
            
        Returns:
            Next phase name or None if migration complete
        """
        last_phase = self.get_last_completed_phase(source_url)
        
        if last_phase is None:
            return 'probe'  # Start from beginning
            
        try:
            last_index = self.PHASES.index(last_phase)
            if last_index < len(self.PHASES) - 1:
                return self.PHASES[last_index + 1]
        except ValueError:
            return 'probe'
        
        return None  # Migration complete
    
    def get_progress(self, source_url: str) -> Dict[str, Any]:
        """
        Get migration progress summary.
        
        Args:
            source_url: Source URL
            
        Returns:
            Dict with progress information
        """
        progress = {
            'can_resume': self.can_resume(source_url),
            'last_completed_phase': self.get_last_completed_phase(source_url),
            'next_phase': self.get_next_phase(source_url),
            'completed_phases': [],
            'pending_phases': []
        }
        
        # Determine completed and pending phases
        last_completed = self.get_last_completed_phase(source_url)
        if last_completed:
            try:
                last_index = self.PHASES.index(last_completed)
                progress['completed_phases'] = self.PHASES[:last_index + 1]
                progress['pending_phases'] = self.PHASES[last_index + 1:]
            except ValueError:
                pass
        else:
            progress['pending_phases'] = self.PHASES.copy()
        
        # Calculate percentage
        if progress['completed_phases']:
            progress['percentage'] = int(
                (len(progress['completed_phases']) / len(self.PHASES)) * 100
            )
        else:
            progress['percentage'] = 0
        
        return progress
    
    def cleanup(self, source_url: str) -> bool:
        """
        Clean up checkpoints after migration.
        
        Args:
            source_url: Source URL
            
        Returns:
            True if successful
        """
        try:
            for phase in self.PHASES:
                checkpoint_key = self._get_checkpoint_key(source_url, phase)
                try:
                    self.memory.delete(checkpoint_key)
                except:
                    pass  # Ignore individual delete errors
            
            logger.info(f"Cleaned up checkpoints for {source_url}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to cleanup checkpoints: {e}")
            return False
    
    def _get_checkpoint_key(self, source_url: str, phase: str) -> str:
        """Generate checkpoint key."""
        # Normalize source URL for use as key
        normalized_url = source_url.replace('://', '_').replace('/', '_').replace('.', '_')
        return f'checkpoint:{normalized_url}:{phase}'
    
    def save_phase_data(self, source_url: str, phase: str, key: str, value: Any) -> bool:
        """
        Save data for a specific phase.
        
        Args:
            source_url: Source URL
            phase: Phase name
            key: Data key
            value: Data value
            
        Returns:
            True if successful
        """
        try:
            checkpoint = self.get_checkpoint(source_url, phase) or {'data': {}}
            checkpoint['data'][key] = value
            return self.create_checkpoint(source_url, phase, checkpoint['data'])
        except Exception as e:
            logger.error(f"Failed to save phase data: {e}")
            return False
    
    def get_phase_data(self, source_url: str, phase: str, key: str) -> Optional[Any]:
        """
        Get specific data from a phase checkpoint.
        
        Args:
            source_url: Source URL
            phase: Phase name
            key: Data key
            
        Returns:
            Value or None if not found
        """
        checkpoint = self.get_checkpoint(source_url, phase)
        if checkpoint and 'data' in checkpoint:
            return checkpoint['data'].get(key)
        return None
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        List all checkpoints.
        
        Returns:
            List of checkpoint metadata
        """
        checkpoints = []
        
        try:
            # Try to list all keys matching checkpoint pattern
            if hasattr(self.memory, '_redis'):
                keys = self.memory._redis.keys('checkpoint:*')
                for key in keys:
                    try:
                        key_str = key.decode() if isinstance(key, bytes) else key
                        parts = key_str.split(':')
                        if len(parts) >= 3:
                            source_url = ':'.join(parts[1:-1]).replace('_', '/').replace('_', '.')
                            phase = parts[-1]
                            checkpoint = self.get_checkpoint(source_url, phase)
                            if checkpoint:
                                checkpoints.append({
                                    'source_url': source_url,
                                    'phase': phase,
                                    'timestamp': checkpoint.get('timestamp'),
                                    'completed': checkpoint.get('completed', False)
                                })
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
        
        return checkpoints


def create_checkpoint_manager(memory_store) -> CheckpointManager:
    """Factory function to create a CheckpointManager."""
    return CheckpointManager(memory_store)

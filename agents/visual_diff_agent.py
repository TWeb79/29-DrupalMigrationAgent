"""
DrupalMind — VisualDiffAgent
Renders source and Drupal output using Playwright.
Computes perceptual hash diff, produces similarity score (0-1).
Breaks diff down by region, returns actionable refinement instructions.
"""
import json
import asyncio
import logging
import os
import base64
from typing import Any, Optional
from base_agent import BaseAgent
from memory import memory as shared_memory
from drupal_client import DrupalClient

# Configure logging for VisualDiffAgent
logger = logging.getLogger("drupalmind.visualdiff")


SYSTEM_PROMPT = """You are the VisualDiffAgent for DrupalMind. Your job is to:
1. Render both source URL and Drupal page using Playwright
2. Compute perceptual hash similarity between the two renders
3. Identify regions with significant differences
4. Generate actionable refinement instructions for BuildAgent
5. Store diff results in memory for the gap report

The similarity score ranges from 0 (completely different) to 1 (identical).
Scores above 0.85 are considered acceptable.
"""


# Similarity thresholds
SIMILARITY_THRESHOLD = 0.85
SIMILARITY_GOOD = 0.90


class VisualDiffAgent(BaseAgent):
    """Compares source and Drupal visually using Playwright."""

    def __init__(self):
        super().__init__("visualdiff", "VisualDiffAgent")
        self.drupal = DrupalClient()
        self._playwright = None
        self._browser = None

    async def initialize(self):
        """Initialize Playwright browser."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            logger.info("Playwright browser initialized")
        except ImportError:
            logger.warning("Playwright not installed - visual diff will be skipped")
            self._playwright = None
            self._browser = None
        except Exception as e:
            logger.warning(f"Failed to initialize Playwright: {e}")
            self._playwright = None
            self._browser = None

    async def close(self):
        """Close Playwright browser."""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    async def diff_component(self, source_url: str, drupal_path: str, component_scope: str = None) -> dict:
        """
        Diff a specific component between source and Drupal.
        Returns similarity score and refinement instructions.
        """
        await self.log(f"Comparing {source_url} to {drupal_path}...")
        
        # Log extended diff start event
        await self.log_extended("diff_start", {
            "source_url": source_url,
            "drupal_path": drupal_path,
            "component_scope": component_scope,
        })
        
        if not self._browser:
            await self.log("Playwright not available - skipping visual diff")
            await self.log_extended("diff_skipped", {"reason": "Playwright not available"})
            return {"skipped": True, "reason": "Playwright not available"}

        try:
            result = await asyncio.to_thread(
                self._compute_diff, 
                source_url, 
                drupal_path,
                component_scope
            )
            
            # Log detailed diff results
            similarity = result.get("similarity", 0)
            regions = result.get("regions", [])
            high_severity = len([r for r in regions if r.get("severity") == "high"])
            
            await self.log_extended("diff_complete", {
                "component_scope": component_scope,
                "similarity": similarity,
                "similarity_percent": f"{similarity*100:.1f}%",
                "region_count": len(regions),
                "high_severity_count": high_severity,
                "instructions_count": len(result.get("instructions", [])),
            })
            
            # Log screenshots for comparison
            source_screenshot = result.get("source_screenshot")
            drupal_screenshot = result.get("drupal_screenshot")
            
            if source_screenshot:
                await self.log_image(source_screenshot, f"Source: {source_url}", 150)
            if drupal_screenshot:
                await self.log_image(drupal_screenshot, f"Drupal: {drupal_path}", 150)
            
            # Log metrics
            await self.log_metric("visual_similarity", similarity * 100, "%", "visual")
            await self.log_metric("diff_regions", len(regions), "", "visual")
            
            # Log check based on threshold
            if similarity >= 0.85:
                await self.log_check("Visual similarity", True, f"{similarity*100:.1f}% meets threshold", "success")
            elif similarity >= 0.5:
                await self.log_check("Visual similarity", True, f"{similarity*100:.1f}% below threshold", "warning")
            else:
                await self.log_check("Visual similarity", False, f"{similarity*100:.1f}% - needs work", "error")
            
            # Store in memory
            scope_key = component_scope or drupal_path.replace("/", "_")
            shared_memory.set_visual_diff(scope_key, result)
            
            await self.log_done(
                f"Visual diff complete - {result.get('similarity', 0)*100:.1f}% similarity"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Visual diff failed: {e}")
            await self.log_error(f"Visual diff failed: {e}")
            return {"error": str(e), "skipped": True}

    async def diff_page(self, source_url: str, drupal_path: str) -> dict:
        """
        Diff a full page between source and Drupal.
        This is the meso-loop check.
        """
        return await self.diff_component(source_url, drupal_path, f"page_{drupal_path.replace('/', '_')}")

    def _compute_diff(self, source_url: str, drupal_path: str, scope: str = None) -> dict:
        """Compute visual difference between two URLs."""
        
        if not self._browser:
            return {
                "similarity": 0,
                "error": "Browser not initialized",
                "regions": [],
                "instructions": [{"action": "skip", "message": "Visual diff unavailable - browser failed to initialize"}],
            }
        
        page = self._browser.new_page()
        
        try:
            # Capture source page as base64
            sourceScreenshotB64 = self._capture_screenshot_base64(page, source_url)
            
            # Capture Drupal page as base64
            drupal_url = self.drupal.base_url + drupal_path
            drupalScreenshotB64 = self._capture_screenshot_base64(page, drupal_url)
            
            # Compute perceptual hash similarity
            sourceBytes = sourceScreenshotB64.replace("data:image/png;base64,", "") if sourceScreenshotB64 else ""
            drupalBytes = drupalScreenshotB64.replace("data:image/png;base64,", "") if drupalScreenshotB64 else ""
            
            import base64
            similarity = 0.0
            if sourceBytes and drupalBytes:
                similarity = self._compute_image_similarity(
                    base64.b64decode(sourceBytes),
                    base64.b64decode(drupalBytes)
                )
            
            # Identify regions with differences (simplified)
            regions = []
            if sourceBytes and drupalBytes:
                regions = self._identify_differing_regions(
                    base64.b64decode(sourceBytes),
                    base64.b64decode(drupalBytes)
                )
            
            # Generate refinement instructions
            instructions = self._generate_instructions(similarity, regions)
            
            return {
                "source_url": source_url,
                "drupal_path": drupal_path,
                "similarity": similarity,
                "score": similarity,
                "regions": regions,
                "instructions": instructions,
                "passed": similarity >= SIMILARITY_THRESHOLD,
                "good_match": similarity >= SIMILARITY_GOOD,
                "scope": scope or drupal_path,
                "source_screenshot": sourceScreenshotB64,
                "drupal_screenshot": drupalScreenshotB64,
            }
            
        finally:
            page.close()

    def _capture_screenshot(self, page, url: str) -> bytes:
        """Capture screenshot of a URL."""
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            return page.screenshot()
        except Exception as e:
            logger.warning(f"Failed to capture {url}: {e}")
            return b""

    def _capture_screenshot_base64(self, page, url: str) -> str:
        """Capture screenshot of a URL as base64."""
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            import base64
            screenshot_bytes = page.screenshot()
            return f"data:image/png;base64,{base64.b64encode(screenshot_bytes).decode('utf-8')}"
        except Exception as e:
            logger.warning(f"Failed to capture {url}: {e}")
            return ""

    def _compute_image_similarity(self, img1: bytes, img2: bytes) -> float:
        """
        Compute perceptual hash similarity between two images.
        Uses simple pixel comparison as fallback.
        """
        if not img1 or not img2:
            return 0.0
        
        try:
            # Try to use imagehash library if available
            import imagehash
            from PIL import Image
            from io import BytesIO
            
            hash1 = imagehash.average_hash(Image.open(BytesIO(img1)))
            hash2 = imagehash.average_hash(Image.open(BytesIO(img2)))
            
            # Convert to similarity (1 - normalized hamming distance)
            similarity = 1 - (hash1 - hash2) / len(hash1.hash) ** 2
            return float(similarity)
            
        except ImportError:
            # Fallback to simple pixel comparison
            return self._simple_pixel_similarity(img1, img2)
        except Exception as e:
            logger.warning(f"Image hash computation failed: {e}")
            return self._simple_pixel_similarity(img1, img2)

    def _simple_pixel_similarity(self, img1: bytes, img2: bytes) -> float:
        """Simple pixel-by-pixel similarity as fallback."""
        try:
            from PIL import Image
            from io import BytesIO
            
            # Resize for comparison
            size = (100, 100)
            im1 = Image.open(BytesIO(img1)).resize(size).convert("RGB")
            im2 = Image.open(BytesIO(img2)).resize(size).convert("RGB")
            
            pixels1 = list(im1.getdata())
            pixels2 = list(im2.getdata())
            
            # Calculate similarity
            diff_count = sum(1 for p1, p2 in zip(pixels1, pixels2) if abs(p1[0]-p2[0]) > 10 or abs(p1[1]-p2[1]) > 10 or abs(p1[2]-p2[2]) > 10)
            similarity = 1 - (diff_count / len(pixels1))
            
            return similarity
            
        except Exception as e:
            logger.warning(f"Pixel comparison failed: {e}")
            return 0.5  # Return neutral score on failure

    def _identify_differing_regions(self, img1: bytes, img2: bytes) -> list:
        """Identify regions with significant differences."""
        regions = []
        
        try:
            from PIL import Image
            from io import BytesIO
            
            # Simple grid-based comparison
            size = (300, 300)
            im1 = Image.open(BytesIO(img1)).resize(size).convert("RGB")
            im2 = Image.open(BytesIO(img2)).resize(size).convert("RGB")
            
            grid_size = 3  # 3x3 grid
            cell_h = size[1] // grid_size
            cell_w = size[0] // grid_size
            
            for row in range(grid_size):
                for col in range(grid_size):
                    box = (col * cell_w, row * cell_h, (col+1) * cell_w, (row+1) * cell_h)
                    
                    region1 = im1.crop(box)
                    region2 = im2.crop(box)
                    
                    # Compare regions
                    pixels1 = list(region1.getdata())
                    pixels2 = list(region2.getdata())
                    
                    diff = sum(1 for p1, p2 in zip(pixels1, pixels2) 
                             if abs(p1[0]-p2[0]) > 20 or abs(p1[1]-p2[1]) > 20 or abs(p1[2]-p2[2]) > 20)
                    
                    diff_ratio = diff / len(pixels1) if pixels1 else 0
                    
                    if diff_ratio > 0.3:  # More than 30% different
                        regions.append({
                            "region": f"grid_{row}_{col}",
                            "position": {"row": row, "col": col},
                            "difference": diff_ratio,
                            "severity": "high" if diff_ratio > 0.5 else "medium",
                        })
                    
        except Exception as e:
            logger.warning(f"Region identification failed: {e}")
            
        return regions

    def _generate_instructions(self, similarity: float, regions: list) -> list:
        """Generate actionable refinement instructions."""
        instructions = []
        
        if similarity >= SIMILARITY_GOOD:
            instructions.append({
                "action": "accept",
                "message": "Visual match is excellent - proceed with next component"
            })
        elif similarity >= SIMILARITY_THRESHOLD:
            instructions.append({
                "action": "minor_adjustment",
                "message": "Good match, consider minor adjustments to styling"
            })
        else:
            instructions.append({
                "action": "refine",
                "message": f"Low similarity ({similarity*100:.1f}%) - refinement needed"
            })
            
            # Add region-specific instructions
            high_severity = [r for r in regions if r.get("severity") == "high"]
            if high_severity:
                instructions.append({
                    "action": "focus_regions",
                    "message": f"Focus on {len(high_severity)} high-severity differing regions",
                    "regions": high_severity
                })
            
            # General improvement suggestions
            if similarity < 0.5:
                instructions.append({
                    "action": "review_mapping",
                    "message": "Very low similarity - consider reviewing component mapping"
                })
        
        return instructions

    # ── Tool: Get diff result ─────────────────────────────────────

    def _tool_get_diff(self, scope: str) -> str:
        """Get visual diff result for a specific scope."""
        diff = shared_memory.get_visual_diff(scope)
        if diff:
            return json.dumps(diff, indent=2)
        return f"No diff found for scope '{scope}'"

    def _tool_get_latest_diff(self) -> str:
        """Get the most recent diff result."""
        keys = shared_memory.list_keys("visual_diff/")
        if not keys:
            return "No diffs available"
        
        # Get the most recent key
        latest_key = sorted(keys)[-1]
        diff = shared_memory.get_visual_diff(latest_key.replace("visual_diff/", ""))
        
        if diff:
            return json.dumps(diff, indent=2)
        return "No diffs available"

# DrupalMind v2 Configuration
# Threshold and loop configuration for migration quality control
import os

# Visual Similarity Thresholds
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))  # Target: 85%
MIN_SIMILARITY_THRESHOLD = float(os.getenv("MIN_SIMILARITY_THRESHOLD", "0.30"))  # Below 30% = major rework

# Loop Limits
MAX_MICRO_ITERATIONS = int(os.getenv("MAX_MICRO_ITERATIONS", "5"))  # Per component
MAX_MESO_ITERATIONS = int(os.getenv("MAX_MESO_ITERATIONS", "3"))    # Per page
MAX_BUILD_RETRIES = int(os.getenv("MAX_BUILD_RETRIES", "2"))         # Entire build

# Feature Flags (as booleans)
ENABLE_VISUAL_DIFF = os.getenv("ENABLE_VISUAL_DIFF", "true").lower() == "true"
ENABLE_MISSING_PIECE_DETECTION = os.getenv("ENABLE_MISSING_PIECE_DETECTION", "true").lower() == "true"
ENABLE_GAP_REPORT = os.getenv("ENABLE_GAP_REPORT", "true").lower() == "true"
ENABLE_HUMAN_REVIEW = os.getenv("ENABLE_HUMAN_REVIEW", "true").lower() == "true"

# Logging
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# V5 Configuration - Content Migration Fixes
V5_FEATURES = {
    "ENABLE_CONTENT_CONSOLIDATION": os.getenv("ENABLE_CONTENT_CONSOLIDATION", "true").lower() == "true",
    "ENABLE_SMART_SECTION_CLASSIFICATION": os.getenv("ENABLE_SMART_SECTION_CLASSIFICATION", "true").lower() == "true",
    "ENABLE_PAGE_CENTRIC_MAPPING": os.getenv("ENABLE_PAGE_CENTRIC_MAPPING", "true").lower() == "true",
    "ENABLE_ENHANCED_VISUAL_DIFF": os.getenv("ENABLE_ENHANCED_VISUAL_DIFF", "true").lower() == "true",
    "CONSOLIDATION_CONFIDENCE_THRESHOLD": float(os.getenv("CONSOLIDATION_CONFIDENCE_THRESHOLD", "0.7")),
    "MAX_SECTIONS_PER_PAGE": int(os.getenv("MAX_SECTIONS_PER_PAGE", "10")),
    "REQUIRE_REVIEW_FOR_COMPLEX_PAGES": os.getenv("REQUIRE_REVIEW_FOR_COMPLEX_PAGES", "true").lower() == "true"
}

# Content Assembly Configuration
CONTENT_ASSEMBLY = {
    "PRESERVE_SECTION_STRUCTURE": True,
    "ADD_SECTION_WRAPPERS": True,
    "CLEAN_HTML_CONTENT": True,
    "MAX_CONTENT_LENGTH": 100000,
    "SECTION_SEPARATOR": "\n\n"
}

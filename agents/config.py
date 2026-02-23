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

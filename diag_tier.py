
import sys
import os
sys.path.append(os.getcwd())
from app.config.tier_config import TIER_LIMITS

print("--- TIER_LIMITS DIAGNOSTIC ---")
for tier, limits in TIER_LIMITS.items():
    print(f"Tier: {tier}")
    print(f"  Allowed Formats: {limits.get('allowed_export_formats')}")

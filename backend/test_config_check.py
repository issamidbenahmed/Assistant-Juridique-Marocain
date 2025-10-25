#!/usr/bin/env python3
"""Check what config the backend is actually using"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings

print("=" * 60)
print("BACKEND CONFIGURATION CHECK")
print("=" * 60)

print(f"CHROMA_DB_PATH: {settings.CHROMA_DB_PATH}")
print(f"CSV_DATA_PATH: {settings.CSV_DATA_PATH}")
print(f"SIMILARITY_THRESHOLD: {settings.SIMILARITY_THRESHOLD}")
print(f"OLLAMA_MODEL: {settings.OLLAMA_MODEL}")

# Test if the path exists
import os
db_path = settings.CHROMA_DB_PATH
print(f"\nDatabase path exists: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    print(f"Contents: {os.listdir(db_path)}")
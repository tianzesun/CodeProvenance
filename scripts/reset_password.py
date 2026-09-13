#!/usr/bin/env python3
"""Reset password for a seeded user to use proper PBKDF2 hashing."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "src/backend/.env.local")

from src.backend.config.database import SessionLocal
from src.backend.infrastructure.security import hash_password, verify_password
from src.backend.models.database import User

with SessionLocal() as db:
    user = db.query(User).filter_by(email='prof.cs@example.com').first()
    if user:
        print(f'Before: {user.password_hash[:50]}...')
        user.password_hash = hash_password('demo-password')
        db.commit()
        print(f'Verify: {verify_password("demo-password", user.password_hash)}')
        print('Password reset successfully')
    else:
        print('User not found')
"""
auth.py
Handles password hashing and verification.
We never store a plain-text password - only a hash - so that
even if someone got hold of the database file, they still
couldn't read anyone's actual password.
"""

import hashlib
import secrets


def hash_password(password, salt=None):
    """Turn a plain password into a salted hash.
    If no salt is given, generate a new random one (used when creating an account)."""
    if salt is None:
        salt = secrets.token_hex(16)  # a random string, different every time

    combined = (password + salt).encode()
    password_hash = hashlib.sha256(combined).hexdigest()

    return password_hash, salt


def verify_password(password, stored_hash, stored_salt):
    """Check a login attempt against what's stored in the database."""
    new_hash, _ = hash_password(password, stored_salt)
    return new_hash == stored_hash
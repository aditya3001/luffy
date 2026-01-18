# """
# Token encryption/decryption utility using Fernet (AES-128)
# """
# from cryptography.fernet import Fernet
# import os
# import logging
#
# logger = logging.getLogger(__name__)
#
# # Get encryption key from environment
# ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
#
# if not ENCRYPTION_KEY:
#     logger.warning("ENCRYPTION_KEY not set in environment. Generating temporary key (NOT FOR PRODUCTION!)")
#     ENCRYPTION_KEY = Fernet.generate_key().decode()
#     logger.warning(f"Temporary key: {ENCRYPTION_KEY}")
#     logger.warning("Set this in .env file: ENCRYPTION_KEY={key}")
#
# try:
#     cipher = Fernet(ENCRYPTION_KEY.encode())
# except Exception as e:
#     logger.error(f"Failed to initialize encryption cipher: {e}")
#     raise
#
#
# def encrypt_token(token: str) -> str:
#     """
#     Encrypt access token for secure storage.
#
#     Args:
#         token: Plain text access token (e.g., "ghp_xxxxxxxxxxxx")
#
#     Returns:
#         Encrypted token as base64 string
#
#     Example:
#         >>> encrypt_token("ghp_1234567890abcdef")
#         "gAAAAABhX..."
#     """
#     if not token:
#         raise ValueError("Token cannot be empty")
#
#     try:
#         encrypted = cipher.encrypt(token.encode())
#         return encrypted.decode()
#     except Exception as e:
#         logger.error(f"Token encryption failed: {e}")
#         raise ValueError("Failed to encrypt token")
#
#
# def decrypt_token(encrypted_token: str) -> str:
#     """
#     Decrypt access token for use in API calls.
#
#     Args:
#         encrypted_token: Encrypted token from database
#
#     Returns:
#         Plain text access token
#
#     Example:
#         >>> decrypt_token("gAAAAABhX...")
#         "ghp_1234567890abcdef"
#     """
#     if not encrypted_token:
#         raise ValueError("Encrypted token cannot be empty")
#
#     try:
#         decrypted = cipher.decrypt(encrypted_token.encode())
#         return decrypted.decode()
#     except Exception as e:
#         logger.error(f"Token decryption failed: {e}")
#         raise ValueError("Failed to decrypt token - token may be invalid or encryption key changed")
#
#
# def is_token_encrypted(token: str) -> bool:
#     """
#     Check if token is already encrypted.
#
#     Args:
#         token: Token string to check
#
#     Returns:
#         True if encrypted, False if plain text
#     """
#     try:
#         cipher.decrypt(token.encode())
#         return True
#     except:
#         return False

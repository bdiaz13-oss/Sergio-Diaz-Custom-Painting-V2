# storage.py - local/S3 storage helpers (boto3 optional)
# (Use the storage.py content provided earlier in the conversation; it contains:
#  save_local_file, upload_to_s3, get_presigned_url, delete_local_file, delete_s3_object)

import os

# Default upload folder (relative to app root)
BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
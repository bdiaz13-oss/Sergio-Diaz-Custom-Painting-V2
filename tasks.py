# tasks.py - enqueue and worker functions (email + media processing + cleanup)
# (Use the tasks.py file provided earlier in the conversation — it includes:
#  enqueue_send_email, send_email_sync, enqueue_process_media, process_media_job,
#  retry/backoff, cleanup_pending_job.)

def enqueue_send_email(to, subject, body_txt, body_html=None):
	"""
	Placeholder for sending email. In production, replace with background queue or real email sender.
	For now, just print the email details.
	"""
	print("[EMAIL SEND] To:", to)
	print("Subject:", subject)
	print("Text Body:\n", body_txt)
	if body_html:
		print("HTML Body:\n", body_html)
	print("--- End Email ---\n")



import os
import shutil
import json
import media
import storage
import uuid
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
EXAMPLES_FILE = os.path.join(DATA_DIR, "examples.json")
UPLOAD_FOLDER = storage.UPLOAD_FOLDER

def enqueue_process_media(pending_path, filename, example_id):
	"""
	Process uploaded media: generate thumbnail, get video duration, move to permanent storage, update example record.
	"""
	print(f"[MEDIA PROCESS] Processing: {filename} (ID: {example_id}) at {pending_path}")
	ext = filename.rsplit('.', 1)[-1].lower()
	is_video = ext == 'mp4'
	is_image = ext in ('jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp')
	# Set up paths
	new_file = f"{uuid.uuid4().hex}_{filename}"
	dest_path = os.path.join(UPLOAD_FOLDER, new_file)
	thumb_file = f"thumb_{new_file}.jpg"
	thumb_path = os.path.join(UPLOAD_FOLDER, thumb_file)
	# Move file to permanent location
	shutil.move(pending_path, dest_path)
	# Generate thumbnail and get video duration if needed
	duration = None
	try:
		if is_image:
			media.generate_image_thumbnails(dest_path, thumb_path)
		elif is_video:
			duration = media.get_video_duration_seconds(dest_path)
			media.extract_video_thumbnail(dest_path, thumb_path, time=1.0)
		else:
			raise Exception("Unsupported file type")
		# Update example record
		with open(EXAMPLES_FILE, "r", encoding="utf-8") as f:
			examples = json.load(f)
		for ex in examples:
			if ex["id"] == example_id:
				ex["file"] = new_file
				ex["thumb"] = thumb_file
				ex["processing"] = False
				ex["processing_error"] = None
				if duration:
					ex["duration"] = duration
				break
		with open(EXAMPLES_FILE, "w", encoding="utf-8") as f:
			json.dump(examples, f, indent=2)
		print(f"[MEDIA PROCESS] Success: {filename} processed.")
	except Exception as e:
		# On error, update example record with error
		with open(EXAMPLES_FILE, "r", encoding="utf-8") as f:
			examples = json.load(f)
		for ex in examples:
			if ex["id"] == example_id:
				ex["processing"] = False
				ex["processing_error"] = str(e)
				break
		with open(EXAMPLES_FILE, "w", encoding="utf-8") as f:
			json.dump(examples, f, indent=2)
		print(f"[MEDIA PROCESS] Error: {e}")

import os
from PIL import Image
import ffmpeg

def generate_image_thumbnails(image_path, thumb_path, size=(400, 400)):
	"""
	Generate a thumbnail for an image and save to thumb_path.
	"""
	with Image.open(image_path) as img:
		img.thumbnail(size)
		img.save(thumb_path)

def get_video_duration_seconds(video_path):
	"""
	Return the duration of the video in seconds.
	"""
	try:
		probe = ffmpeg.probe(video_path)
		return float(probe['format']['duration'])
	except Exception:
		return None

def extract_video_thumbnail(video_path, thumb_path, time=1.0, size=(400, 400)):
	"""
	Extract a thumbnail from the video at the given time (in seconds).
	"""
	(
		ffmpeg
		.input(video_path, ss=time)
		.filter('scale', size[0], size[1])
		.output(thumb_path, vframes=1)
		.run(overwrite_output=True, quiet=True)
	)

def transcode_video_to_mp4(input_path, output_path):
	"""
	Transcode a video to mp4 format for browser compatibility.
	"""
	(
		ffmpeg
		.input(input_path)
		.output(output_path, vcodec='libx264', acodec='aac', strict='experimental')
		.run(overwrite_output=True, quiet=True)
	)
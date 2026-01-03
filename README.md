```markdown
# Sergio Diaz Custom Painting

Sergio Diaz Custom Painting is a Flask-based web application that
focuses on referral-driven leads for house painting projects.

Key features:
- Dashboard with welcome message (personalized when logged in).
- User signup/login (optional); password hashing and session security.
- Referral codes (users generate codes, share them; referrals tracked).
- Request an Estimate form with contact info, budget, address, scope, referral code.
- Examples gallery (images and mp4 video uploads), with admin moderation.
- Testimonials (text + video links).
- Email notifications (SMTP) — signup, referral creation, admin notification on estimate, customer confirmations, referral-used notice.
- Asynchronous jobs with Redis + RQ for emails and media processing.
- Media processing: image thumbnails (Pillow), video validation/thumbnail extraction/transcoding (ffmpeg), optional S3 storage with presigned URLs.
- Data stored as JSON files under `data/` (can be migrated to a DB later).

Requirements
- Python 3.8+
- ffmpeg & ffprobe (for video processing)
- Redis (if you want background jobs via RQ)
- Optional: AWS S3 credentials for cloud uploads

Install
1. Clone locally or create a new GitHub repo and push.
2. Create virtualenv and install:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create .env from `.env.example` and set values (SMTP, ADMIN_EMAIL, SDCP_SECRET_KEY, REDIS_URL, AWS_* if used).
4. Ensure ffmpeg/ffprobe installed:
   - Debian/Ubuntu: `sudo apt-get install ffmpeg`
   - macOS (Homebrew): `brew install ffmpeg`
5. Create an admin user by signing up with the ADMIN_EMAIL address.

Run (development)
```
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
```

Run worker (background tasks)
```
# If using Redis (recommended)
REDIS_URL=redis://localhost:6379/0 rq worker
```

Create a public GitHub repository and push (example using gh CLI)
```
git init
git add .
git commit -m "Initial commit - Sergio Diaz Custom Painting"
gh repo create sergio-diaz-custom-painting --public --source=. --remote=origin --push
```

Or create manually on GitHub, then:
```
git remote add origin https://github.com/<your-username>/sergio-diaz-custom-painting.git
git push -u origin main
```

Production notes
- Set SDCP_SECRET_KEY in env (do not use default).
- Use HTTPS in production.
- Move from JSON files to a proper database for production (I can help migrate to SQLite/Postgres).
- Run RQ workers and use a process manager (systemd, supervisor) for reliability.
- For S3, ensure proper IAM policies and credentials management.

If you want, I can:
- Create the public repo for you (I will need owner/repo details and permission).
- Convert JSON storage to SQLite and add migrations.
- Add GitHub Actions CI for tests and deployment.

```
# app.py - main Flask application
# (This file wires together authentication, referrals, estimates, examples, admin pages,
#  and uses tasks.py, storage.py, media.py for background and media handling.)
import os
import json
import uuid
import secrets
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import tasks
import storage

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_FOLDER = storage.UPLOAD_FOLDER

# JSON files
USERS_FILE = os.path.join(DATA_DIR, "users.json")
REFERRALS_FILE = os.path.join(DATA_DIR, "referrals.json")
ESTIMATES_FILE = os.path.join(DATA_DIR, "estimates.json")
TESTIMONIALS_FILE = os.path.join(DATA_DIR, "testimonials.json")
EXAMPLES_FILE = os.path.join(DATA_DIR, "examples.json")

# App init and config
app = Flask(__name__)
app.secret_key = os.environ.get("SDCP_SECRET_KEY") or secrets.token_urlsafe(32)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH") or 40 * 1024 * 1024)

# Ensure data files exist
def ensure_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    defaults = {
        USERS_FILE: [],
        REFERRALS_FILE: [],
        ESTIMATES_FILE: [],
        TESTIMONIALS_FILE: [],
        EXAMPLES_FILE: []
    }
    for path, default in defaults.items():
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=2)

ensure_data_files()

# CSRF token
@app.before_request
def ensure_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(16)

def check_csrf():
    token = session.get("csrf_token")
    form_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    return bool(token and form_token and secrets.compare_digest(token, form_token))

# Helpers: load/save JSON
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

# Auth helpers
def find_user_by_email(email):
    users = load_json(USERS_FILE)
    for u in users:
        if u.get("email", "").lower() == email.lower():
            return u
    return None

def get_user_by_id(uid):
    users = load_json(USERS_FILE)
    for u in users:
        if u.get("id") == uid:
            return u
    return None

def get_current_user():
    if "user_id" not in session:
        return None
    return get_user_by_id(session["user_id"])

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapped

def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        admin_email = os.environ.get("ADMIN_EMAIL", "bendiaz620@gmail.com").lower()
        if not user or user.get("email","").lower() != admin_email:
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapped

# Context helpers for media URLs
@app.context_processor
def media_url_helpers():
    def get_media_url(example, expires=3600):
        if example.get("s3_key"):
            return storage.get_presigned_url(example["s3_key"], expires)
        if example.get("file"):
            return url_for("uploaded_file", filename=example["file"])
        return example.get("image_url") or ""
    def get_thumb_url(example, expires=3600):
        if example.get("s3_thumb_key"):
            return storage.get_presigned_url(example["s3_thumb_key"], expires)
        if example.get("thumb"):
            return url_for("uploaded_file", filename=example["thumb"])
        return example.get("image_url") or ""
    return dict(get_media_url=get_media_url, get_thumb_url=get_thumb_url, datetime=datetime, config=app.config, get_user_by_id=get_user_by_id)

# Routes
@app.route("/")
def index():
    user = get_current_user()
    examples = load_json(EXAMPLES_FILE)
    approved = [e for e in examples if e.get("approved")]
    testimonials = load_json(TESTIMONIALS_FILE)
    referrals = []
    if user:
        referrals = [r for r in load_json(REFERRALS_FILE) if r.get("owner_id")==user["id"]]
    return render_template("index.html", user=user, examples=approved, testimonials=testimonials, referrals=referrals, csrf_token=session.get("csrf_token"))

# Signup/Login/Logout/Profile
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        if not check_csrf():
            flash("Invalid CSRF token", "danger")
            return redirect(url_for("signup"))
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not name or not email or not password:
            flash("Name, email, and password required.", "danger")
            return redirect(url_for("signup"))
        if find_user_by_email(email):
            flash("Account already exists for that email.", "danger")
            return redirect(url_for("signup"))
        users = load_json(USERS_FILE)
        user = {"id": str(uuid.uuid4()), "name": name, "email": email, "password_hash": generate_password_hash(password), "created_at": datetime.utcnow().isoformat()}
        users.append(user)
        save_json(USERS_FILE, users)
        session["user_id"] = user["id"]
        flash("Account created.", "success")
        # enqueue welcome email
        subj = "Welcome to Sergio Diaz Custom Painting"
        body_txt = render_template("emails/welcome.txt", user=user)
        body_html = render_template("emails/welcome.html", user=user)
        tasks.enqueue_send_email(user["email"], subj, body_txt, body_html)
        return redirect(url_for("index"))
    return render_template("signup.html", csrf_token=session.get("csrf_token"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        if not check_csrf():
            flash("Invalid CSRF token", "danger")
            return redirect(url_for("login"))
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = find_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid credentials.", "danger")
            return redirect(url_for("login"))
        session["user_id"] = user["id"]
        flash("Logged in.", "success")
        return redirect(request.args.get("next") or url_for("index"))
    return render_template("login.html", csrf_token=session.get("csrf_token"))

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))

@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    user = get_current_user()
    if request.method=="POST":
        if not check_csrf():
            flash("Invalid CSRF token", "danger")
            return redirect(url_for("profile"))
        name = request.form.get("name","").strip()
        if name:
            users = load_json(USERS_FILE)
            for u in users:
                if u["id"] == user["id"]:
                    u["name"] = name
            save_json(USERS_FILE, users)
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
    referrals = [r for r in load_json(REFERRALS_FILE) if r.get("owner_id")==user["id"]]
    return render_template("profile.html", user=user, referrals=referrals, csrf_token=session.get("csrf_token"))

# Referral generation (AJAX)
@app.route("/generate_referral", methods=["POST"])
@login_required
def generate_referral():
    if not check_csrf():
        return jsonify({"error":"Invalid CSRF token"}), 400
    user = get_current_user()
    referrals = load_json(REFERRALS_FILE)
    user_referrals = [r for r in referrals if r.get("owner_id")==user["id"]]
    if len(user_referrals) >= 20:
        return jsonify({"error":"Referral limit reached"}), 400
    code = secrets.token_urlsafe(6)
    referral = {"id": str(uuid.uuid4()), "owner_id": user["id"], "code": code, "created_at": datetime.utcnow().isoformat(), "uses": 0, "max_uses": 10, "discount_percent": 10}
    referrals.append(referral)
    save_json(REFERRALS_FILE, referrals)
    subj = "Your referral code — Sergio Diaz Custom Painting"
    body_txt = render_template("emails/referral_created.txt", user=user, code=code)
    body_html = render_template("emails/referral_created.html", user=user, code=code)
    tasks.enqueue_send_email(user["email"], subj, body_txt, body_html)
    return jsonify({"code": code, "url": url_for("index", _external=True) + "?ref=" + code})

# Estimates
@app.route("/request_estimate", methods=["GET","POST"])
def request_estimate():
    if request.method=="POST":
        if not check_csrf():
            flash("Invalid CSRF token", "danger")
            return redirect(url_for("request_estimate"))
        form = request.form
        required = ["full_name","email","street","city","state","postal","description"]
        for f in required:
            if not form.get(f):
                flash("Please fill required fields.", "danger")
                return redirect(url_for("request_estimate"))
        full_name = form.get("full_name"); email = form.get("email"); phone = form.get("phone","")
        street = form.get("street"); city = form.get("city"); state = form.get("state"); postal = form.get("postal")
        budget = form.get("budget"); description = form.get("description"); preferred_date = form.get("preferred_date","")
        referral_code = form.get("referral_code","").strip()
        discount_applied = 0; referral_owner=None; owner_email=None
        if referral_code:
            referrals = load_json(REFERRALS_FILE)
            matched = next((r for r in referrals if r.get("code")==referral_code), None)
            if matched and matched.get("uses",0) < matched.get("max_uses",0):
                matched["uses"] = matched.get("uses",0)+1
                save_json(REFERRALS_FILE, referrals)
                discount_applied = matched.get("discount_percent",0)
                referral_owner = matched.get("owner_id")
                owner = get_user_by_id(referral_owner)
                if owner: owner_email = owner.get("email")
            else:
                flash("Referral code invalid or expired; continuing without discount.", "warning")
        estimates = load_json(ESTIMATES_FILE)
        estimate = {"id": str(uuid.uuid4()), "created_at": datetime.utcnow().isoformat(), "user_id": session.get("user_id"), "full_name": full_name, "email": email, "phone": phone, "address": {"street":street,"city":city,"state":state,"postal":postal}, "budget":budget, "description":description, "preferred_date":preferred_date, "referral_code":referral_code or "", "referral_owner":referral_owner, "discount_applied_percent":discount_applied, "status":"submitted", "processed": False}
        estimates.append(estimate)
        save_json(ESTIMATES_FILE, estimates)
        flash("Estimate request submitted. We'll contact you shortly.", "success")
        # email admin and customer and referral owner
        admin_email = os.environ.get("ADMIN_EMAIL")
        if admin_email:
            subj = f"New Estimate Request — {full_name}"
            body_txt = render_template("emails/estimate_admin.txt", estimate=estimate)
            body_html = render_template("emails/estimate_admin.html", estimate=estimate)
            tasks.enqueue_send_email(admin_email, subj, body_txt, body_html)
        subj_cust = "Estimate Request Received — Sergio Diaz Custom Painting"
        body_cust_txt = render_template("emails/estimate_customer.txt", estimate=estimate)
        body_cust_html = render_template("emails/estimate_customer.html", estimate=estimate)
        tasks.enqueue_send_email(email, subj_cust, body_cust_txt, body_cust_html)
        if owner_email:
            subj_owner="Your referral was used!"
            body_owner_txt = render_template("emails/referral_used.txt", ref_code=referral_code, customer_name=full_name)
            body_owner_html = render_template("emails/referral_used.html", ref_code=referral_code, customer_name=full_name)
            tasks.enqueue_send_email(owner_email, subj_owner, body_owner_txt, body_owner_html)
        return redirect(url_for("index"))
    prefill_ref = request.args.get("ref","")
    return render_template("estimate_form.html", csrf_token=session.get("csrf_token"), prefill_ref=prefill_ref)

# Testimonials
@app.route("/testimonials")
def testimonials():
    testimonials = load_json(TESTIMONIALS_FILE)
    user = get_current_user()
    return render_template("testimonials.html", testimonials=testimonials, user=user, csrf_token=session.get("csrf_token"))

@app.route("/add_testimonial", methods=["POST"])
@login_required
def add_testimonial():
    if not check_csrf():
        flash("Invalid CSRF token", "danger")
        return redirect(url_for("testimonials"))
    text = request.form.get("text","").strip()
    video_url = request.form.get("video_url","").strip()
    if not text and not video_url:
        flash("Provide a testimonial or a video URL.", "danger")
        return redirect(url_for("testimonials"))
    testimonials = load_json(TESTIMONIALS_FILE)
    t = {"id": str(uuid.uuid4()), "user_id": session["user_id"], "text": text, "video_url": video_url, "created_at": datetime.utcnow().isoformat()}
    testimonials.append(t)
    save_json(TESTIMONIALS_FILE, testimonials)
    flash("Thank you for your testimonial!", "success")
    return redirect(url_for("testimonials"))

# Examples (list, upload, serve uploads) - upload is enqueued for background processing
@app.route("/examples")
def examples():
    user = get_current_user()
    examples = load_json(EXAMPLES_FILE)
    approved = [e for e in examples if e.get("approved")]
    user_pending = []
    if user:
        user_pending = [e for e in examples if (not e.get("approved")) and e.get("uploaded_by")==user["id"]]
    return render_template("examples.html", examples=approved, user=user, user_pending=user_pending, csrf_token=session.get("csrf_token"))

# Upload endpoint (saves to uploads/pending and enqueues background processing)
@app.route("/examples/upload", methods=["POST"])
@login_required
def examples_upload():
    if not check_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("examples"))
    if "file" not in request.files:
        flash("No file part.", "danger")
        return redirect(url_for("examples"))
    file = request.files["file"]
    if file.filename=="":
        flash("No selected file.", "danger")
        return redirect(url_for("examples"))
    filename = secure_filename(file.filename)
    if "." not in filename:
        flash("Invalid filename.", "danger")
        return redirect(url_for("examples"))
    ext = filename.rsplit(".",1)[1].lower()
    if ext not in {"png","jpg","jpeg","gif","mp4"}:
        flash("Invalid file type.", "danger")
        return redirect(url_for("examples"))
    # save to pending
    pending_dir = os.path.join(app.config["UPLOAD_FOLDER"], "pending")
    os.makedirs(pending_dir, exist_ok=True)
    store_name = f"{uuid.uuid4().hex}_{filename}"
    pending_path = os.path.join(pending_dir, store_name)
    file.save(pending_path)
    # create example record with processing flag
    examples = load_json(EXAMPLES_FILE)
    example = {"id": str(uuid.uuid4()), "title": request.form.get("title") or filename, "description": request.form.get("description") or "", "uploaded_by": session.get("user_id"), "created_at": datetime.utcnow().isoformat(), "approved": False, "processing": True, "processing_error": None, "pending_file": store_name, "retry_count": 0}
    examples.append(example)
    save_json(EXAMPLES_FILE, examples)
    # enqueue background processing
    tasks.enqueue_process_media(pending_path, filename, example["id"])
    flash("Upload received. Processing and admin moderation will follow.", "success")
    return redirect(url_for("examples"))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

# Admin pages for estimates and examples
@app.route("/admin/estimates")
@login_required
@admin_required
def admin_estimates():
    q = request.args.get("q","")
    status = request.args.get("status","all")
    estimates = load_json(ESTIMATES_FILE)
    if q:
        estimates = [e for e in estimates if q.lower() in (e.get("full_name","").lower() + e.get("email","").lower())]
    if status == "submitted":
        estimates = [e for e in estimates if not e.get("processed")]
    elif status == "processed":
        estimates = [e for e in estimates if e.get("processed")]
    estimates = sorted(estimates, key=lambda e: e.get("created_at",""), reverse=True)
    return render_template("admin_estimates.html", estimates=estimates, csrf_token=session.get("csrf_token"))

@app.route("/admin/estimate/<eid>/process", methods=["POST"])
@login_required
@admin_required
def admin_process_estimate(eid):
    if not check_csrf():
        flash("Invalid CSRF token", "danger")
        return redirect(url_for("admin_estimates"))
    estimates = load_json(ESTIMATES_FILE)
    found = next((e for e in estimates if e["id"]==eid), None)
    if not found:
        flash("Estimate not found.", "danger")
        return redirect(url_for("admin_estimates"))
    found["processed"] = True
    found["processed_by"] = get_current_user().get("email")
    found["processed_at"] = datetime.utcnow().isoformat()
    if request.form.get("send_email"):
        subj = "Estimate Status Update — Sergio Diaz Custom Painting"
        body_txt = render_template("emails/estimate_processed_customer.txt", estimate=found)
        body_html = render_template("emails/estimate_processed_customer.html", estimate=found)
        tasks.enqueue_send_email(found["email"], subj, body_txt, body_html)
        found["email_sent"] = True
    save_json(ESTIMATES_FILE, estimates)
    flash("Estimate marked processed.", "success")
    return redirect(url_for("admin_estimates"))

@app.route("/admin/examples")
@login_required
@admin_required
def admin_examples():
    examples = load_json(EXAMPLES_FILE)
    examples = sorted(examples, key=lambda e: e.get("created_at",""), reverse=True)
    return render_template("admin_examples.html", examples=examples, csrf_token=session.get("csrf_token"))

@app.route("/admin/examples/<eid>/approve", methods=["POST"])
@login_required
@admin_required
def admin_examples_approve(eid):
    if not check_csrf():
        flash("Invalid CSRF token", "danger")
        return redirect(url_for("admin_examples"))
    examples = load_json(EXAMPLES_FILE)
    ex = next((e for e in examples if e["id"]==eid), None)
    if not ex:
        flash("Example not found", "danger")
        return redirect(url_for("admin_examples"))
    ex["approved"] = True
    ex["approved_at"] = datetime.utcnow().isoformat()
    save_json(EXAMPLES_FILE, examples)
    flash("Example approved.", "success")
    return redirect(url_for("admin_examples"))

@app.route("/admin/examples/<eid>/delete", methods=["POST"])
@login_required
@admin_required
def admin_examples_delete(eid):
    if not check_csrf():
        flash("Invalid CSRF token", "danger")
        return redirect(url_for("admin_examples"))
    examples = load_json(EXAMPLES_FILE)
    ex = next((e for e in examples if e["id"]==eid), None)
    if not ex:
        flash("Example not found", "danger")
        return redirect(url_for("admin_examples"))
    # delete stored files if local or S3
    if ex.get("file"):
        storage.delete_local_file(ex["file"])
    if ex.get("thumb"):
        storage.delete_local_file(ex["thumb"])
    if ex.get("s3_key"):
        storage.delete_s3_object(ex["s3_key"])
    examples = [e for e in examples if e["id"]!=eid]
    save_json(EXAMPLES_FILE, examples)
    flash("Example deleted.", "success")
    return redirect(url_for("admin_examples"))

@app.route("/admin/examples/<eid>/retry", methods=["POST"])
@login_required
@admin_required
def admin_examples_retry(eid):
    if not check_csrf():
        flash("Invalid CSRF token", "danger")
        return redirect(url_for("admin_examples"))
    examples = load_json(EXAMPLES_FILE)
    ex = next((e for e in examples if e["id"]==eid), None)
    if not ex:
        flash("Example not found", "danger")
        return redirect(url_for("admin_examples"))
    pending_file = ex.get("pending_file")
    if pending_file:
        pending_path = os.path.join(storage.UPLOAD_FOLDER, "pending", pending_file)
        if not os.path.exists(pending_path):
            flash("Pending file missing; cannot retry.", "danger")
            return redirect(url_for("admin_examples"))
        ex["retry_count"] = 0
        ex["processing"] = True
        ex["processing_error"] = None
        save_json(EXAMPLES_FILE, examples)
        tasks.enqueue_process_media(pending_path, pending_file.split("_",1)[-1], eid)
        flash("Retry enqueued.", "success")
        return redirect(url_for("admin_examples"))
    if ex.get("file"):
        local_path = os.path.join(storage.UPLOAD_FOLDER, ex.get("file"))
        if os.path.exists(local_path):
            ex["retry_count"] = 0
            ex["processing"] = True
            ex["processing_error"] = None
            save_json(EXAMPLES_FILE, examples)
            tasks.enqueue_process_media(local_path, ex.get("file"), eid)
            flash("Retry enqueued using stored file.", "success")
            return redirect(url_for("admin_examples"))
    flash("No available file to retry processing.", "danger")
    return redirect(url_for("admin_examples"))

if __name__ == "__main__":
    app.run(debug=True)
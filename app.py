import os
import shutil
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or os.getenv("WEBIDE_SECRET_KEY") or "dev-insecure-secret"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

AUTH_PASSWORD_HASH = os.getenv("WEBIDE_PASSWORD_HASH", "")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def is_api_request():
    if request.path.startswith("/auth/"):
        return True
    if request.path in {"/tree", "/open", "/save", "/create", "/rename", "/delete"}:
        return True
    if request.path.startswith("/api/"):
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept


def is_safe_redirect(target):
    if not target:
        return False
    parsed = urlparse(target)
    return parsed.scheme == "" and parsed.netloc == "" and target.startswith("/")


def get_next_path(default="/"):
    next_path = request.args.get("next") or request.form.get("next") or default
    return next_path if is_safe_redirect(next_path) else default


@app.before_request
def require_authentication():
    endpoint = request.endpoint
    if endpoint in {"login", "static"}:
        return None

    if session.get("authenticated"):
        return None

    if is_api_request():
        return jsonify({"error": "Authentication required"}), 401

    return redirect(url_for("login", next=request.path))

def normalize_client_path(path):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Path must be a non-empty string")

    normalized = path.replace("\\", "/").strip().lstrip("/")
    normalized = os.path.normpath(normalized).replace("\\", "/")

    if normalized in ("", "."):
        raise ValueError("Invalid path")

    return normalized

def safe_path(path):
    rel_path = normalize_client_path(path)
    full = os.path.abspath(os.path.join(BASE_DIR, rel_path))

    try:
        common = os.path.commonpath([BASE_DIR, full])
    except ValueError as exc:
        raise ValueError("Invalid path") from exc

    if common != BASE_DIR:
        raise ValueError("Invalid path")

    return full

def get_json_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object payload")
    return payload

def require_string(payload, key):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' is required")
    return value

def build_tree(root):
    tree = []
    for item in sorted(os.listdir(root)):
        path = os.path.join(root, item)
        rel = os.path.relpath(path, BASE_DIR).replace("\\", "/")

        if os.path.isdir(path):
            tree.append({
                "type": "folder",
                "name": item,
                "path": rel,
                "children": build_tree(path)
            })
        else:
            tree.append({
                "type": "file",
                "name": item,
                "path": rel
            })
    return tree


@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_PASSWORD_HASH:
        return (
            "WEBIDE_PASSWORD_HASH is not configured. "
            "Set it to a werkzeug password hash before starting the app.",
            500,
        )

    if session.get("authenticated"):
        return redirect(get_next_path("/"))

    if request.method == "GET":
        return render_template("login.html", error=None, next_path=get_next_path("/"))

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        password = (payload.get("password") or "").strip()
    else:
        password = request.form.get("password", "").strip()

    if check_password_hash(AUTH_PASSWORD_HASH, password):
        session["authenticated"] = True
        if request.is_json:
            return jsonify({"status": "ok", "redirect": get_next_path("/")})
        return redirect(get_next_path("/"))

    if request.is_json:
        return jsonify({"error": "Invalid password"}), 401

    return render_template("login.html", error="Invalid password", next_path=get_next_path("/")), 401


@app.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "logged_out"})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/tree")
def tree():
    return jsonify(build_tree(BASE_DIR))

@app.route("/open", methods=["POST"])
def open_file():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))

    if not os.path.isfile(path):
        raise FileNotFoundError("File not found")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return jsonify({"content": f.read()})

@app.route("/save", methods=["POST"])
def save_file():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))
    content = payload.get("content")

    if not isinstance(content, str):
        raise ValueError("'content' must be a string")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return jsonify({"status": "saved"})

@app.route("/create", methods=["POST"])
def create():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))
    type_ = require_string(payload, "type")

    if type_ not in {"file", "folder"}:
        raise ValueError("'type' must be 'file' or 'folder'")

    if type_ == "file":
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").close()
    else:
        os.makedirs(path, exist_ok=True)

    return jsonify({"status": "created"})

@app.route("/rename", methods=["POST"])
def rename():
    payload = get_json_payload()
    old = safe_path(require_string(payload, "old"))
    new = safe_path(require_string(payload, "new"))

    if not os.path.exists(old):
        raise FileNotFoundError("Source path not found")

    os.makedirs(os.path.dirname(new), exist_ok=True)
    os.rename(old, new)
    return jsonify({"status": "renamed"})

@app.route("/delete", methods=["POST"])
def delete():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))

    if not os.path.exists(path):
        raise FileNotFoundError("Path not found")

    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
    return jsonify({"status": "deleted"})

@app.errorhandler(ValueError)
def handle_value_error(error):
    return jsonify({"error": str(error)}), 400

@app.errorhandler(FileNotFoundError)
def handle_not_found_error(error):
    return jsonify({"error": str(error)}), 404

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=debug_enabled,
    )


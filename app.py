import os
import shutil
import argparse
import hashlib
import sys
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or os.getenv("WEBIDE_SECRET_KEY") or "dev-insecure-secret"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

AUTH_PASSWORD_HASH = (os.getenv("WEBIDE_PASSWORD_HASH") or "").strip().replace("\r", "").replace("\n", "")

if AUTH_PASSWORD_HASH and "$" not in AUTH_PASSWORD_HASH:
    raise RuntimeError(
        "WEBIDE_PASSWORD_HASH appears invalid. Ensure the full Werkzeug hash is set "
        "without truncation, extra quoting, or shell expansion."
    )

# WEBIDE_DISABLE_AUTH=1 bypasses all authentication — for local testing only.
AUTH_DISABLED = os.getenv("WEBIDE_DISABLE_AUTH", "0").strip() == "1"
if AUTH_DISABLED:
    print(
        "WARNING: Authentication is DISABLED (WEBIDE_DISABLE_AUTH=1). "
        "Do NOT run with this setting in any shared or production environment.",
        file=sys.stderr,
    )

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Configurable content root: CLI `--root` (when run as a script) overrides
# `ROOT_DIR` env var; otherwise fallback to the directory of this file.
ROOT_DIR = os.getenv("ROOT_DIR") or BASE_DIR
ROOT_DIR = os.path.abspath(os.path.normpath(ROOT_DIR))

API_PATHS = {"/tree", "/open", "/save", "/create", "/rename", "/delete", "/watch"}


def is_api_request():
    if request.path.startswith("/auth/"):
        return True
    if request.path in API_PATHS:
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
    if AUTH_DISABLED:
        return None

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
    full = os.path.abspath(os.path.join(ROOT_DIR, rel_path))

    try:
        common = os.path.commonpath([ROOT_DIR, full])
    except ValueError as exc:
        raise ValueError("Invalid path") from exc

    if common != ROOT_DIR:
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
        rel = os.path.relpath(path, ROOT_DIR).replace("\\", "/")

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


def read_text_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as file_handle:
        return file_handle.read()


def build_file_meta(path):
    if not os.path.isfile(path):
        return None

    stat_result = os.stat(path)
    return {
        "version": f"{stat_result.st_mtime_ns}:{stat_result.st_size}",
        "mtimeNs": stat_result.st_mtime_ns,
        "size": stat_result.st_size,
    }


def build_tree_version():
    entries = []
    for current_root, dirnames, filenames in os.walk(ROOT_DIR):
        dirnames.sort()
        filenames.sort()

        for dirname in dirnames:
            rel_path = os.path.relpath(os.path.join(current_root, dirname), ROOT_DIR).replace("\\", "/")
            entries.append(f"d:{rel_path}")

        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(current_root, filename), ROOT_DIR).replace("\\", "/")
            entries.append(f"f:{rel_path}")

    digest = hashlib.sha256("\n".join(entries).encode("utf-8"))
    return digest.hexdigest()


def build_open_file_response(path):
    return {
        "content": read_text_file(path),
        "meta": build_file_meta(path),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if AUTH_DISABLED:
        session["authenticated"] = True
        return redirect(get_next_path("/"))

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
    return jsonify({
        "tree": build_tree(ROOT_DIR),
        "treeVersion": build_tree_version(),
    })

@app.route("/open", methods=["POST"])
def open_file():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))

    if not os.path.isfile(path):
        raise FileNotFoundError("File not found")

    return jsonify(build_open_file_response(path))

@app.route("/save", methods=["POST"])
def save_file():
    payload = get_json_payload()
    path = safe_path(require_string(payload, "path"))
    content = payload.get("content")
    expected_version = payload.get("expectedVersion")
    force = bool(payload.get("force"))

    if not isinstance(content, str):
        raise ValueError("'content' must be a string")

    if expected_version is not None and not isinstance(expected_version, str):
        raise ValueError("'expectedVersion' must be a string when provided")

    if os.path.isdir(path):
        raise ValueError("Cannot save a directory path")

    current_meta = build_file_meta(path)
    current_version = current_meta["version"] if current_meta else None

    if not force and expected_version is not None and expected_version != current_version:
        return jsonify({
            "error": "File changed on disk",
            "code": "version_conflict",
            "currentMeta": current_meta,
            "currentContent": read_text_file(path) if current_meta else "",
        }), 409

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_handle:
        file_handle.write(content)

    return jsonify({
        "status": "saved",
        "meta": build_file_meta(path),
        "treeVersion": build_tree_version(),
    })

@app.route("/watch", methods=["POST"])
def watch_files():
    payload = get_json_payload()
    paths = payload.get("paths", [])
    known_tree_version = payload.get("knownTreeVersion")

    if not isinstance(paths, list):
        raise ValueError("'paths' must be an array")

    if known_tree_version is not None and not isinstance(known_tree_version, str):
        raise ValueError("'knownTreeVersion' must be a string when provided")

    watched_files = {}
    for item in paths:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Each watched path must be a non-empty string")

        rel_path = normalize_client_path(item)
        full_path = safe_path(rel_path)
        meta = build_file_meta(full_path)
        watched_files[rel_path] = {
            "exists": meta is not None,
            "meta": meta,
        }

    tree_version = build_tree_version()
    return jsonify({
        "files": watched_files,
        "treeVersion": tree_version,
        "treeChanged": known_tree_version != tree_version,
    })

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

    return jsonify({"status": "created", "treeVersion": build_tree_version()})

@app.route("/rename", methods=["POST"])
def rename():
    payload = get_json_payload()
    old = safe_path(require_string(payload, "old"))
    new = safe_path(require_string(payload, "new"))

    if not os.path.exists(old):
        raise FileNotFoundError("Source path not found")

    os.makedirs(os.path.dirname(new), exist_ok=True)
    os.rename(old, new)
    return jsonify({"status": "renamed", "treeVersion": build_tree_version()})

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
    return jsonify({"status": "deleted", "treeVersion": build_tree_version()})

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
    parser = argparse.ArgumentParser(description="Run web-ide app")
    parser.add_argument("--root", help="Override the content root directory")
    args = parser.parse_args()

    if args.root:
        ROOT_DIR = os.path.abspath(os.path.normpath(args.root))

    debug_enabled = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=debug_enabled,
    )


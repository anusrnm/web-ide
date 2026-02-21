# Web IDE

## Authentication setup (no user database)

This app uses a single shared password with Flask session cookies.

### 1) Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 2) Generate a password hash

Pick your password and run one of these:

**Recommended (helper script)**

```powershell
python scripts/generate_hash.py
```

Or pass password as an argument:

```powershell
python scripts/generate_hash.py "your-strong-password"
```

**PowerShell**

```powershell
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-strong-password'))"
```

**cmd.exe**

```bat
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-strong-password'))"
```

Copy the printed hash.

### 3) Set required environment variables

- `WEBIDE_PASSWORD_HASH`: hash from step 2
- `SECRET_KEY`: random secret for signing session cookies

**PowerShell**

```powershell
$env:WEBIDE_PASSWORD_HASH = "paste-generated-hash-here"
$env:SECRET_KEY = "replace-with-a-long-random-secret"
python app.py
```

**cmd.exe**

```bat
set WEBIDE_PASSWORD_HASH=paste-generated-hash-here
set SECRET_KEY=replace-with-a-long-random-secret
python app.py
```

Optional for HTTPS deployments:

- `SESSION_COOKIE_SECURE=1`

Then open `http://localhost:5000` and sign in with your shared password.

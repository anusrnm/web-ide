# Web IDE

## ROOT_DIR parameter

The `ROOT_DIR` parameter sets the root directory for file operations (tree, open, save, create, rename, delete). By default, it uses the project directory, but you can override it:

- **Environment variable:**
	- `ROOT_DIR=/path/to/your/content`
- **Command line argument:**
	- `python app.py --root /path/to/your/content`

**Example .env file:**
```env
ROOT_DIR=/home/pi/web-content
```

**Example PowerShell:**
```powershell
$env:ROOT_DIR = "/path/to/your/content"
python app.py
```

**Example cmd.exe:**
```bat
set ROOT_DIR=/path/to/your/content
python app.py
```

**Example bash/zsh:**
```bash
export ROOT_DIR="/path/to/your/content"
python app.py
```

If not set, the app defaults to the project directory.

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

**Linux/macOS (bash/zsh)**

```bash
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

**Linux/macOS (bash/zsh)**

```bash
export WEBIDE_PASSWORD_HASH='paste-generated-hash-here'
export SECRET_KEY='replace-with-a-long-random-secret'
python app.py
```

If you use a `.env` file on Linux/macOS:

- Keep the hash on a single line.
- Do not wrap the value in extra quotes that become part of the value.
- Use LF endings (not CRLF).

Example:

```env
WEBIDE_PASSWORD_HASH=pbkdf2:sha256:600000$...$...
SECRET_KEY=replace-with-a-long-random-secret
```

Optional for HTTPS deployments:

- `SESSION_COOKIE_SECURE=1`

Then open `http://localhost:5000` and sign in with your shared password.
## Running as a Service on Raspberry Pi Boot

To run Web IDE automatically at boot, use `systemd` for robust service management:

1. Create a unit file `/etc/systemd/system/webide.service`:
	```ini
	[Unit]
	Description=Web IDE Service
	After=network.target

	[Service]
	User=pi
	WorkingDirectory=/home/pi/web-ide
	Environment="WEBIDE_PASSWORD_HASH=..." "SECRET_KEY=..." "ROOT_DIR=/home/pi/web-content"
	ExecStart=/usr/bin/python3 app.py
	Restart=always

	[Install]
	WantedBy=multi-user.target
	```
2. Reload systemd:
	```bash
	sudo systemctl daemon-reload
	```
3. Enable the service:
	```bash
	sudo systemctl enable webide
	```
4. Start the service:
	```bash
	sudo systemctl start webide
	```

**Notes:**
- Update `WorkingDirectory` and environment variables as needed.
- Logs are managed by systemd (view with `journalctl -u webide`).
- For HTTPS, set `SESSION_COOKIE_SECURE=1` in the unit file.

**Alternative:** You can use `/etc/rc.local` to start the app, but `systemd` is recommended for reliability.

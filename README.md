# HTML Server & Explorer

A lightweight, high-performance static content server and file explorer built with Python and FastAPI. 

While designed specifically for serving flat HTML documents and landing pages with direct URL mapping, it can seamlessly host and deliver any static web assets (CSS, JavaScript, images, SVGs, JSON, and media files).

---

## 🌟 Key Features

- **Direct Route Serving**: Any file placed in the storage directory is instantly accessible at its direct URL path (e.g., `http://localhost:5000/reports/q1.html`).
- **Interactive Web Dashboard**: Built-in responsive, mobile-first management interface accessible at `/` or `/_manager` to browse, upload (via file picker or drag-and-drop), create folders, and organize files.
- **Live Preview & Code Inspector**: Slide-over drawer to test rendered web pages in real-time or inspect syntax-highlighted source code without leaving the manager.
- **Fast & Resource-Efficient**: Asynchronous I/O powered by Uvicorn and FastAPI with minimal memory footprint and instant startup.
- **Security-First**: Strict path traversal prevention, filename sanitization, and security headers out of the box.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10** or higher (compatible with Python 3.10, 3.11, 3.12, 3.13+)
- `pip` (Python package manager)

### Installation & Run

1. **Clone or download the repository:**
   ```bash
   git clone <repository-url>
   cd html-server
   ```

2. **Create and activate a Python virtual environment:**
   - **Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows:**
     ```cmd
     python -m venv .venv
     .venv\Scripts\activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the server:**
   ```bash
   python main.py
   ```

5. **Access the application:**
   - **Web Manager Dashboard:** [http://localhost:5000/](http://localhost:5000/) or [http://localhost:5000/_manager](http://localhost:5000/_manager)
   - **Direct File Access:** Uploaded files will be served directly at `http://localhost:5000/<path>/<filename>`

---

## ⚙️ Configuration & CLI Options

You can customize the server execution using command-line arguments or environment variables:

```bash
python main.py --port 8080 --host 0.0.0.0 --storage-dir ./my_html_files
```

| Flag | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `-p`, `--port` | `PORT` | `5000` | Port number to bind the web server |
| `-H`, `--host` | `HOST` | `0.0.0.0` | IP address to listen on (`0.0.0.0` for all interfaces) |
| `-d`, `--storage-dir` | `HTML_STORAGE_DIR` | `html_storage` | Directory path where static files are stored and served from |
| `--reload` | — | `False` | Enable auto-reload for local development |

---

## 📁 Project Structure

```text
html-server/
├── app/
│   ├── api/
│   │   └── explorer.py       # REST API endpoints (file tree, upload, create folder, rename, delete)
│   ├── services/
│   │   └── storage.py        # Secure filesystem service with path traversal protection
│   ├── static/
│   │   ├── css/styles.css    # Responsive & Mobile-First dark industrial UI stylesheet
│   │   └── js/app.js         # Client-side logic, drag & drop, and live preview modal
│   ├── templates/
│   │   └── index.html        # Main dashboard template
│   ├── config.py             # Centralized configuration & environment variable loader
│   └── server.py             # FastAPI web application & direct routing engine
├── html_storage/             # Storage root where uploaded static files and HTMLs are hosted
├── tests/
│   └── test_server.py        # Automated test suite (security, routing, file management)
├── main.py                   # CLI entrypoint supporting arguments & environment variables
├── requirements.txt          # Python dependencies (FastAPI, Uvicorn, Jinja2, etc.)
├── pyproject.toml            # Python project metadata
└── README.md
```

---

## 🧪 Running Tests

To run the automated test suite and verify system integrity:

```bash
pytest
```

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

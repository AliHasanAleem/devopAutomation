# DevOps Automation Python Backend

This project is a FastAPI backend for a DevOps automation platform, providing deployment pipeline APIs, WebSocket communication, and integration with MongoDB and GitHub authentication.

## Prerequisites

- **Python 3.10+** (Recommended: Python 3.13 as per `pyvenv.cfg`)
- **pip** (Python package manager)
- **MongoDB** (running locally or accessible remotely)
- **Git** (for cloning the repository, optional)

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd python_backend
```

### 2. Set Up a Virtual Environment

#### **Windows**
```cmd
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
venv\Scripts\activate
```

#### **Ubuntu/Linux**
```bash
# Install Python 3 venv module if not already installed
sudo apt update
sudo apt install python3-venv

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate
```

#### **macOS**
```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate
```

> **Note:** If you have multiple Python versions, use `python3.13` or the version matching your system and `pyvenv.cfg`.

### 3. Install Dependencies

With the virtual environment activated, run:
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (Optional)

- Update MongoDB connection string and secrets in `main.py` as needed for your environment.

### 5. Run the FastAPI Server

```bash
uvicorn main:app --reload
```

- The API will be available at: [http://localhost:8000](http://localhost:8000)
- Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Additional Notes

- **MongoDB:** Ensure MongoDB is running and accessible at the URI specified in `main.py` (`mongodb://localhost:27017/` by default).
- **.gitignore:** The project is set to ignore all files by default. You may want to update `.gitignore` to track source files.
- **Deactivation:** To deactivate the virtual environment, simply run:
  - `deactivate` (works on all platforms)

## Troubleshooting
- If you encounter issues with dependencies, ensure your Python version matches the one specified in `pyvenv.cfg`.
- For port conflicts, change the port in the `uvicorn` command (e.g., `--port 8080`).

---

Feel free to customize this README with more details about your project, API endpoints, or contribution guidelines as needed.

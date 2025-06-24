from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
import asyncio
import json
import uvicorn
from typing import List, Dict, Any
import time
import httpx
import paramiko
import subprocess
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Auth, MongoDB, and User Management Setup ---
GITHUB_CLIENT_ID = "Ov23li6cAni1XoTa0UGR"
GITHUB_CLIENT_SECRET =  "9e8b52cc184f48c1a9fa0d9ea396ecf816d1bcac"
MONGODB_URL = "mongodb://localhost:27017/"
SECRET_KEY = "secret"
DATABASE_NAME = "devops_automation"
GITHUB_REDIRECT_URI = "http://localhost:8000/github-auth"

# VM Configuration
VM_HOST = "15.235.184.251"
VM_USERNAME = "moz"
VM_PASSWORD = "sqeh3u8QWAAP"

app = FastAPI(title="Deployment Pipeline API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mongodb_client: AsyncIOMotorClient | None = None
database: Any = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.chat_history: List[Dict] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send chat history to new connection
        if self.chat_history:
            await websocket.send_text(json.dumps({
                "type": "chat_history",
                "data": self.chat_history
            }))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_step_update(self, step_data: dict):
        """Broadcast step updates to all connected clients"""
        message = json.dumps({"type": "step_update", "data": step_data})
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_log_message(self, log_data: dict):
        """Broadcast log messages to all connected clients"""
        message = json.dumps({"type": "log_message", "data": log_data})
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_chat_message(self, message_data: dict):
        """Broadcast chat messages to all connected clients"""
        self.chat_history.append(message_data)
        # Keep only last 50 messages
        if len(self.chat_history) > 50:
            self.chat_history = self.chat_history[-50:]
        
        message = json.dumps({"type": "chat_message", "data": message_data})
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

@app.on_event("startup")
async def startup_db_client():
    global mongodb_client, database
    mongodb_client = AsyncIOMotorClient(MONGODB_URL)
    database = mongodb_client[DATABASE_NAME]

@app.on_event("shutdown")
async def shutdown_db_client():
    if mongodb_client is not None:
        mongodb_client.close()

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    if database is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    user = await database.users.find_one({"github_username": username})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Models
class PipelineStep(BaseModel):
    id: str
    name: str
    status: str  # pending, running, completed, failed
    output: str
    duration: int  # in seconds

class ChatMessage(BaseModel):
    message: str
    timestamp: str
    user_id: str = "user"

class DeploymentRequest(BaseModel):
    owner: str
    repo_name: str

# Real pipeline steps configuration
PIPELINE_STEPS = [
    {
        "id": "init",
        "name": "Repository Analysis",
        "status": "pending",
        "output": "",
        "duration": 0,
        "color": "bg-blue-400"
    },
    {
        "id": "dockerfile",
        "name": "Dockerfile Generation",
        "status": "pending",
        "output": "",
        "duration": 0,
        "color": "bg-yellow-400"
    },
    {
        "id": "vm_access",
        "name": "VM Connection & Setup",
        "status": "pending",
        "output": "",
        "duration": 0,
        "color": "bg-green-400"
    },
    {
        "id": "build",
        "name": "Docker Build",
        "status": "pending", 
        "output": "",
        "duration": 0,
        "color": "bg-gray-600"
    },
    {
        "id": "deploy",
        "name": "Deployment",
        "status": "pending",
        "output": "",
        "duration": 0,
        "color": "bg-purple-400"
    }
]

# Pipeline context
pipeline_context = {}

async def log_message(message: str, level: str = "INFO"):
    """Send log message to all connected clients"""
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message
    }
    await manager.broadcast_log_message(log_data)
    logger.info(f"[{level}] {message}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                if message_data.get("type") == "chat_message":
                    # Handle chat message
                    await handle_chat_message_ws(message_data.get("data", {}))
                elif message_data.get("type") == "ping":
                    # Respond to ping
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                # Echo back non-JSON messages
                await websocket.send_text(json.dumps({"type": "echo", "data": data}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def handle_chat_message_ws(message_data: dict):
    """Handle chat messages from WebSocket"""
    user_message = {
        "id": str(int(time.time() * 1000)),
        "type": "user",
        "content": message_data.get("message", ""),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Broadcast user message
    await manager.broadcast_chat_message(user_message)
    
    # Generate AI response
    ai_response = await generate_ai_response(message_data.get("message", ""))
    
    ai_message = {
        "id": str(int(time.time() * 1000) + 1),
        "type": "ai",
        "content": ai_response,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Broadcast AI response
    await manager.broadcast_chat_message(ai_message)

async def generate_ai_response(user_message: str) -> str:
    """Generate contextual AI responses based on deployment state and user input"""
    user_message_lower = user_message.lower()
    
    # Check current pipeline state
    current_step = next((step for step in PIPELINE_STEPS if step["status"] == "running"), None)
    completed_steps = [step for step in PIPELINE_STEPS if step["status"] == "completed"]
    
    if "accept" in user_message_lower or "yes" in user_message_lower or "ok" in user_message_lower:
        if current_step and current_step["id"] == "dockerfile":
            return "Perfect! I'll proceed with generating the Dockerfile for your project. This will analyze your repository structure and create an optimized container configuration."
        elif current_step and current_step["id"] == "build":
            return "Great! Starting the build process. This will create your Docker image and may take a few minutes depending on your project size."
        else:
            return "Excellent! I'll continue with the next step in the deployment process."
    
    elif "reject" in user_message_lower or "no" in user_message_lower:
        return "I understand. Let me know what changes you'd like me to make before proceeding with the deployment."
    
    elif "status" in user_message_lower or "progress" in user_message_lower:
        if current_step:
            return f"Currently working on: {current_step['name']}. {len(completed_steps)} out of {len(PIPELINE_STEPS)} steps completed."
        else:
            return f"Pipeline status: {len(completed_steps)} out of {len(PIPELINE_STEPS)} steps completed."
    
    elif "help" in user_message_lower:
        return "I'm here to help with your deployment! You can ask me about the current status, accept/reject steps, or get help with any deployment questions."
    
    elif "docker" in user_message_lower or "container" in user_message_lower:
        return "I'll analyze your project structure and create an optimized Dockerfile that's tailored to your specific application requirements."
    
    elif "error" in user_message_lower or "problem" in user_message_lower:
        return "I can help troubleshoot any issues. Could you please provide more details about what specific problem you're encountering?"
    
    else:
        # Default contextual responses
        responses = [
            "I'm here to assist with your deployment process. What would you like to know?",
            "The deployment is progressing well. Is there anything specific you'd like me to explain?",
            "I can help you with any questions about the deployment steps or configuration.",
            "Everything looks good so far! Let me know if you need any clarification."
        ]
        import random
        return random.choice(responses)

@app.get("/api/pipeline/steps")
async def get_pipeline_steps():
    """Get all pipeline steps"""
    return {"steps": PIPELINE_STEPS}

@app.post("/api/pipeline/start")
async def start_pipeline(request: DeploymentRequest):
    global PIPELINE_STEPS, pipeline_context
    pipeline_context['owner'] = request.owner
    pipeline_context['repo_name'] = request.repo_name
    
    await log_message(f"Starting deployment pipeline for {request.owner}/{request.repo_name}")
    
    # Reset all steps
    for step in PIPELINE_STEPS:
        step["status"] = "pending"
        step["output"] = ""
        step["duration"] = 0
    
    # Broadcast initial state
    for step in PIPELINE_STEPS:
        await manager.broadcast_step_update(step)
    
    # Start pipeline execution
    asyncio.create_task(execute_pipeline())
    return {"message": "Pipeline started", "steps": PIPELINE_STEPS}

async def analyze_repo_structure(owner: str, repo_name: str) -> str:
    """Analyze repository structure and return analysis results"""
    await log_message(f"Analyzing repository structure for {owner}/{repo_name}")
    
    try:
        async with httpx.AsyncClient() as client:
            # Get repository contents
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo_name}/contents",
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            
            if response.status_code != 200:
                return f"Error: Could not access repository {owner}/{repo_name}"
            
            contents = response.json()
            
            # Analyze files
            files = [item['name'] for item in contents if item['type'] == 'file']
            directories = [item['name'] for item in contents if item['type'] == 'dir']
            
            analysis = f"Repository Analysis Results:\n"
            analysis += f"Repository: {owner}/{repo_name}\n"
            analysis += f"Files found: {len(files)}\n"
            analysis += f"Directories found: {len(directories)}\n\n"
            
            # Check for common files
            common_files = ['package.json', 'requirements.txt', 'Dockerfile', 'docker-compose.yml', 'pom.xml', 'build.gradle']
            found_files = [f for f in files if f in common_files]
            
            analysis += f"Key files detected: {', '.join(found_files) if found_files else 'None'}\n"
            
            if 'package.json' in files:
                analysis += "✓ Node.js project detected\n"
            if 'requirements.txt' in files:
                analysis += "✓ Python project detected\n"
            if 'pom.xml' in files:
                analysis += "✓ Java Maven project detected\n"
            if 'build.gradle' in files:
                analysis += "✓ Java Gradle project detected\n"
            
            await log_message(f"Repository analysis completed. Found {len(files)} files and {len(directories)} directories")
            return analysis
            
    except Exception as e:
        error_msg = f"Error analyzing repository: {str(e)}"
        await log_message(error_msg, "ERROR")
        return error_msg

async def generate_dockerfile(owner: str, repo_name: str) -> str:
    """Generate Dockerfile based on repository analysis"""
    await log_message(f"Generating Dockerfile for {owner}/{repo_name}")
    
    try:
        async with httpx.AsyncClient() as client:
            # Get repository contents
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo_name}/contents",
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            
            if response.status_code != 200:
                return f"Error: Could not access repository {owner}/{repo_name}"
            
            contents = response.json()
            files = [item['name'] for item in contents if item['type'] == 'file']
            
            # Determine project type and generate appropriate Dockerfile
            dockerfile_content = ""
            
            if 'package.json' in files:
                # Node.js project
                dockerfile_content = """# Node.js Application Dockerfile
FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Expose port (adjust if needed)
EXPOSE 3000

# Start the application
CMD ["npm", "start"]"""
                
            elif 'requirements.txt' in files:
                # Python project
                dockerfile_content = """# Python Application Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (adjust if needed)
EXPOSE 8000

# Start the application
CMD ["python", "app.py"]"""
                
            elif 'pom.xml' in files:
                # Java Maven project
                dockerfile_content = """# Java Maven Application Dockerfile
FROM openjdk:17-jdk-slim

# Set working directory
WORKDIR /app

# Copy pom.xml
COPY pom.xml .

# Copy source code
COPY src ./src

# Build the application
RUN apt-get update && apt-get install -y maven
RUN mvn clean package -DskipTests

# Expose port (adjust if needed)
EXPOSE 8080

# Start the application
CMD ["java", "-jar", "target/*.jar"]"""
                
            else:
                # Generic Dockerfile
                dockerfile_content = """# Generic Application Dockerfile
FROM ubuntu:20.04

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Install basic tools
RUN apt-get update && apt-get install -y curl

# Expose port (adjust if needed)
EXPOSE 8080

# Start the application (adjust command as needed)
CMD ["echo", "Application started"]"""
            
            await log_message(f"Dockerfile generated successfully for {owner}/{repo_name}")
            return dockerfile_content
            
    except Exception as e:
        error_msg = f"Error generating Dockerfile: {str(e)}"
        await log_message(error_msg, "ERROR")
        return error_msg

async def connect_to_vm() -> str:
    """Connect to VM and check environment"""
    await log_message("Connecting to deployment VM")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        await log_message(f"Establishing SSH connection to {VM_HOST}")
        ssh.connect(hostname=VM_HOST, username=VM_USERNAME, password=VM_PASSWORD, timeout=10)
        
        output_lines = [f"✓ Connected to {VM_HOST} as {VM_USERNAME}\n"]
        
        # Check system status
        commands = [
            ("docker_version", "docker --version"),
            ("docker_info", "docker info"),
            ("memory_info", "free -h"),
            ("disk_space", "df -h"),
            ("docker_images", "docker images"),
            ("docker_ps", "docker ps")
        ]
        
        for command_name, command in commands:
            try:
                await log_message(f"Running: {command}")
                stdin, stdout, stderr = ssh.exec_command(command)
                output = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                
                output_lines.append(f"$ {command}\n")
                if output:
                    output_lines.append(output + "\n")
                if error:
                    output_lines.append(f"[ERROR] {error}\n")
                    
            except Exception as cmd_error:
                error_msg = f"[FAILED] {command}: {cmd_error}"
                await log_message(error_msg, "ERROR")
                output_lines.append(error_msg + "\n")
        
        ssh.close()
        await log_message("VM connection and environment check completed")
        return "".join(output_lines)
        
    except Exception as e:
        error_msg = f"Failed to connect to VM: {str(e)}"
        await log_message(error_msg, "ERROR")
        return error_msg

async def build_docker_image(owner: str, repo_name: str) -> str:
    """Build Docker image on VM"""
    await log_message(f"Building Docker image for {owner}/{repo_name}")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=VM_HOST, username=VM_USERNAME, password=VM_PASSWORD, timeout=10)
        
        # Create project directory with lowercase names
        project_dir = f"/home/{VM_USERNAME}/{owner.lower()}-{repo_name.lower()}"
        image_name = f"{owner.lower()}-{repo_name.lower()}"
        await log_message(f"Creating project directory: {project_dir}")
        
        stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {project_dir}")
        if stderr.read():
            await log_message("Error creating project directory", "ERROR")
        
        # Clone repository
        await log_message(f"Cloning repository {owner}/{repo_name}")
        clone_cmd = f"cd {project_dir} && git clone https://github.com/{owner}/{repo_name}.git ."
        stdin, stdout, stderr = ssh.exec_command(clone_cmd)
        
        clone_output = stdout.read().decode()
        clone_error = stderr.read().decode()
        
        if clone_error and "already exists" not in clone_error:
            await log_message(f"Error cloning repository: {clone_error}", "ERROR")
            return f"Error cloning repository: {clone_error}"
        
        await log_message("Repository cloned successfully")
        
        # Check if Dockerfile exists, if not create one
        await log_message("Checking for existing Dockerfile")
        stdin, stdout, stderr = ssh.exec_command(f"cd {project_dir} && ls -la Dockerfile")
        dockerfile_exists = stdout.read().decode().strip()
        
        if not dockerfile_exists:
            await log_message("No Dockerfile found, creating one based on project type")
            
            # Determine project type and create appropriate Dockerfile
            stdin, stdout, stderr = ssh.exec_command(f"cd {project_dir} && ls -la")
            files = stdout.read().decode()
            
            dockerfile_content = ""
            if "package.json" in files:
                # Node.js project
                dockerfile_content = """# Node.js Application Dockerfile
FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Expose port (adjust if needed)
EXPOSE 3000

# Start the application
CMD ["npm", "start"]"""
            elif "requirements.txt" in files:
                # Python project
                dockerfile_content = """# Python Application Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (adjust if needed)
EXPOSE 8000

# Start the application
CMD ["python", "app.py"]"""
            elif "pom.xml" in files:
                # Java Maven project
                dockerfile_content = """# Java Maven Application Dockerfile
FROM openjdk:17-jdk-slim

# Set working directory
WORKDIR /app

# Copy pom.xml
COPY pom.xml .

# Copy source code
COPY src ./src

# Build the application
RUN apt-get update && apt-get install -y maven
RUN mvn clean package -DskipTests

# Expose port (adjust if needed)
EXPOSE 8080

# Start the application
CMD ["java", "-jar", "target/*.jar"]"""
            else:
                # Generic Dockerfile
                dockerfile_content = """# Generic Application Dockerfile
FROM ubuntu:20.04

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Install basic tools
RUN apt-get update && apt-get install -y curl

# Expose port (adjust if needed)
EXPOSE 8080

# Start the application (adjust command as needed)
CMD ["echo", "Application started"]"""
            
            # Create Dockerfile
            dockerfile_cmd = f"cd {project_dir} && echo '{dockerfile_content}' > Dockerfile"
            stdin, stdout, stderr = ssh.exec_command(dockerfile_cmd)
            await log_message("Dockerfile created successfully")
        
        # Build Docker image
        await log_message("Starting Docker build")
        build_cmd = f"cd {project_dir} && docker build -t {image_name}:latest ."
        stdin, stdout, stderr = ssh.exec_command(build_cmd)
        
        build_output = stdout.read().decode()
        build_error = stderr.read().decode()
        
        if build_error and "Successfully built" not in build_output:
            await log_message(f"Docker build error: {build_error}", "ERROR")
            return f"Docker build error: {build_error}"
        
        await log_message("Docker image built successfully")
        return f"Build completed successfully!\n{build_output}"
        
    except Exception as e:
        error_msg = f"Error building Docker image: {str(e)}"
        await log_message(error_msg, "ERROR")
        return error_msg

async def deploy_application(owner: str, repo_name: str) -> str:
    """Deploy the application on VM"""
    await log_message(f"Deploying application {owner}/{repo_name}")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=VM_HOST, username=VM_USERNAME, password=VM_PASSWORD, timeout=10)
        
        # Use lowercase names for Docker
        image_name = f"{owner.lower()}-{repo_name.lower()}"
        container_name = f"{owner.lower()}-{repo_name.lower()}-container"
        
        # Stop existing container if running
        await log_message("Stopping existing container if running")
        stop_cmd = f"docker stop {container_name} || true"
        ssh.exec_command(stop_cmd)
        
        # Remove existing container
        remove_cmd = f"docker rm {container_name} || true"
        ssh.exec_command(remove_cmd)
        
        # Check if image exists
        await log_message("Checking if Docker image exists")
        image_check_cmd = f"docker images {image_name}:latest"
        stdin, stdout, stderr = ssh.exec_command(image_check_cmd)
        image_exists = stdout.read().decode()
        
        if not image_exists or "REPOSITORY" not in image_exists:
            await log_message("Docker image not found, cannot deploy", "ERROR")
            return "Error: Docker image not found. Please ensure the build step completed successfully."
        
        # Run new container with dynamic port mapping
        await log_message("Starting new container")
        
        # Try different ports in case 8080 is busy
        ports = [8080, 3000, 8000, 5000]
        container_started = False
        
        for port in ports:
            try:
                run_cmd = f"docker run -d --name {container_name} -p {port}:{port} {image_name}:latest"
                stdin, stdout, stderr = ssh.exec_command(run_cmd)
                
                run_output = stdout.read().decode().strip()
                run_error = stderr.read().decode()
                
                if run_output and not run_error:
                    await log_message(f"Container started successfully on port {port}")
                    container_started = True
                    break
                else:
                    # Remove failed container
                    ssh.exec_command(f"docker rm {container_name} || true")
                    
            except Exception as e:
                await log_message(f"Failed to start container on port {port}: {str(e)}", "WARNING")
                continue
        
        if not container_started:
            await log_message("Failed to start container on any port", "ERROR")
            return "Error: Failed to start container. All ports may be in use."
        
        # Check container status
        await log_message("Checking container status")
        status_cmd = f"docker ps --filter name={container_name}"
        stdin, stdout, stderr = ssh.exec_command(status_cmd)
        status_output = stdout.read().decode()
        
        # Get container logs for debugging
        await log_message("Getting container logs")
        logs_cmd = f"docker logs {container_name} --tail 10"
        stdin, stdout, stderr = ssh.exec_command(logs_cmd)
        container_logs = stdout.read().decode()
        
        ssh.close()
        
        await log_message("Application deployed successfully")
        return f"Deployment completed!\nContainer Status:\n{status_output}\n\nContainer Logs:\n{container_logs}"
        
    except Exception as e:
        error_msg = f"Error deploying application: {str(e)}"
        await log_message(error_msg, "ERROR")
        return error_msg

async def execute_pipeline():
    """Execute the deployment pipeline with real-time logging"""
    global PIPELINE_STEPS, pipeline_context
    
    owner = pipeline_context.get('owner')
    repo_name = pipeline_context.get('repo_name')
    
    if not owner or not repo_name:
        await log_message("Missing repository information", "ERROR")
        return
    
    await log_message(f"Starting pipeline execution for {owner}/{repo_name}")
    
    for i, step in enumerate(PIPELINE_STEPS):
        step["status"] = "running"
        step["output"] = ""
        await manager.broadcast_step_update(step)
        
        start_time = time.time()
        
        try:
            if step["id"] == "init":
                await log_message("Step 1: Repository Analysis")
                step["output"] = await analyze_repo_structure(owner, repo_name)
                await asyncio.sleep(1)
                
            elif step["id"] == "dockerfile":
                await log_message("Step 2: Dockerfile Generation")
                step["output"] = await generate_dockerfile(owner, repo_name)
                await asyncio.sleep(1)
                
            elif step["id"] == "vm_access":
                await log_message("Step 3: VM Connection & Setup")
                step["output"] = await connect_to_vm()
                await asyncio.sleep(1)
                
            elif step["id"] == "build":
                await log_message("Step 4: Docker Build")
                step["output"] = await build_docker_image(owner, repo_name)
                await asyncio.sleep(1)
                
            elif step["id"] == "deploy":
                await log_message("Step 5: Application Deployment")
                step["output"] = await deploy_application(owner, repo_name)
                await asyncio.sleep(1)
            
            step["status"] = "completed"
            step["duration"] = int(time.time() - start_time)
            await log_message(f"Step {i+1} completed in {step['duration']} seconds")
            
        except Exception as e:
            step["status"] = "failed"
            step["output"] = f"Error: {str(e)}"
            await log_message(f"Step {i+1} failed: {str(e)}", "ERROR")
        
        await manager.broadcast_step_update(step)
        await asyncio.sleep(0.5)
    
    await log_message("Pipeline execution completed")

@app.get("/api/pipeline/step/{step_id}")
async def get_step_details(step_id: str):
    """Get details of a specific step"""
    step = next((s for s in PIPELINE_STEPS if s["id"] == step_id), None)
    if not step:
        return {"error": "Step not found"}
    return step

@app.post("/api/chat/message")
async def handle_chat_message(message: ChatMessage):
    """Handle chat messages from AI assistant (legacy endpoint)"""
    response = await generate_ai_response(message.message)
    
    return {
        "response": response,
        "timestamp": str(int(time.time() * 1000))
    }

@app.get("/auth/github")
async def github_login():
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={GITHUB_REDIRECT_URI}&scope=user:email,repo"
    return RedirectResponse(url=github_auth_url)

@app.get("/github-auth")
async def github_callback(code: str):
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"}
        )
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to get access token")
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"}
        )
        user_data = user_response.json()
        user_doc = {
            "github_id": user_data["id"],
            "github_username": user_data["login"],
            "name": user_data.get("name"),
            "avatar_url": user_data.get("avatar_url"),
            "github_access_token": access_token,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await database.users.update_one(
            {"github_id": user_data["id"]},
            {"$set": user_doc},
            upsert=True
        )
        jwt_token = create_access_token(data={"sub": user_data["login"]})
        response = RedirectResponse(url="/dashboard")
        response.set_cookie(key="access_token", value=jwt_token, httponly=True)
        return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(current_user: dict = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        repos_response = await client.get(
            "https://api.github.com/user/repos",
            headers={"Authorization": f"token {current_user['github_access_token']}"},
            params={"sort": "updated"}
        )
        repos = repos_response.json()
    repos_html = ""
    for repo in repos:
        repos_html += f"""
        <div style=\"border:1px solid #e1e4e8;padding:15px;margin:10px 0;border-radius:6px;cursor:pointer\" onclick=\"window.location.href='/repo/{repo['owner']['login']}/{repo['name']}'\">
            <h3 style=\"margin:0 0 5px 0\">{repo['name']}</h3>
        </div>
        """
    return f"""
    <html>
        <head><title>Dashboard</title>
        <style>body{{font-family:Arial,sans-serif;margin:20px;max-width:800px}}img{{border-radius:50%}}a{{color:#0969da;text-decoration:none}}</style>
        </head>
        <body>
            <div style=\"display:flex;align-items:center;gap:15px;margin-bottom:30px;border-bottom:1px solid #e1e4e8;padding-bottom:20px\">
                <img src=\"{current_user.get('avatar_url', '')}\" width=\"50\" height=\"50\">
                <div>
                    <h2 style=\"margin:0\">{current_user.get('name', current_user.get('github_username'))}</h2>
                    <p style=\"margin:0;color:#586069\">@{current_user.get('github_username')}</p>
                </div>
                <a href=\"/logout\" style=\"margin-left:auto;padding:8px 16px;background:#dc3545;color:white;border-radius:4px\">Logout</a>
            </div>
            <h3>Select Repository ({len(repos)} total)</h3>
            {repos_html}
        </body>
    </html>
         """

@app.get("/repo/{owner}/{repo_name}", response_class=HTMLResponse)
async def repo_details(owner: str, repo_name: str, current_user: dict = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        repo_response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo_name}",
            headers={"Authorization": f"token {current_user['github_access_token']}"}
        )
        repo_info = repo_response.json()
        contents_response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo_name}/contents",
            headers={"Authorization": f"token {current_user['github_access_token']}"}
        )
        contents = contents_response.json()
    files_html = ""
    for item in contents:
        icon = "📁" if item['type'] == 'dir' else "📄"
        files_html += f"""
        <div style=\"padding:8px;border-bottom:1px solid #f1f3f4;display:flex;align-items:center;gap:10px\">
            <span>{icon}</span>
            <span style=\"font-family:monospace\">{item['name']}</span>
            <small style=\"margin-left:auto;color:#586069\">{item['type']}</small>
        </div>
        """
    return f"""
    <html>
        <head><title>{repo_name} - Repository Details</title>
        <style>body{{font-family:Arial,sans-serif;margin:20px;max-width:800px}}a{{color:#0969da;text-decoration:none}}</style>
        </head>
        <body>
            <div style=\"margin-bottom:20px\">
                <a href=\"/dashboard\">← Back to Dashboard</a>
            </div>
            <div style=\"border:1px solid #e1e4e8;padding:20px;border-radius:6px;margin-bottom:20px\">
                <h2 style=\"margin:0 0 10px 0\">{repo_name}</h2>
                <p style=\"margin:0 0 15px 0;color:#586069\">{repo_info.get('description', 'No description')}</p>
                <div style=\"display:flex;gap:20px;font-size:14px;color:#586069\">
                    <span>🍴 {repo_info['forks_count']}</span>
                    <span>📝 {repo_info.get('language', 'N/A')}</span>
                    <span>🔗 <a href=\"{repo_info['html_url']}\" target=\"_blank\">View on GitHub</a></span>
                </div>
            </div>
            <div style=\"border:1px solid #e1e4e8;border-radius:6px\">
                 <div style=\"background:#f6f8fa;padding:15px;border-bottom:1px solid #e1e4e8;display:flex;justify-content:space-between;align-items:center\">
                     <h3 style=\"margin:0\">Files & Directories ({len(contents)} items)</h3>
                     <a href=\"/analyze/{owner}/{repo_name}\" style=\"background:#28a745;color:white;padding:8px 16px;border-radius:4px;text-decoration:none\">Proceed to Next →</a>
                 </div>
                 <div>
                     {files_html}
                 </div>
             </div>
         </body>
     </html>
     """

@app.get("/analyze/{owner}/{repo_name}")
async def analyze_repository(owner: str, repo_name: str, current_user: dict = Depends(get_current_user)):
    async def get_repo_structure(path=""):
        async with httpx.AsyncClient() as client:
            url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"
            response = await client.get(
                url,
                headers={"Authorization": f"token {current_user['github_access_token']}"}
            )
            if response.status_code != 200:
                return []
            items = response.json()
            structure = []
            for item in items:
                if item['type'] == 'file':
                    structure.append({
                        "name": item['name'],
                        "path": item['path'],
                        "type": "file"
                    })
                elif item['type'] == 'dir':
                    structure.append({
                        "name": item['name'],
                        "path": item['path'],
                        "type": "directory",
                        "children": await get_repo_structure(item['path'])
                    })
            return structure
    async def get_critical_file_contents():
        critical_files = [
            "package.json", "package-lock.json",
            "requirements.txt", "Pipfile", "poetry.lock", "pyproject.toml",
            "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
            ".env", ".env.example", "env.example",
            "app.py", "main.py", "index.js", "server.js", "app.js",
            "pom.xml", "build.gradle", "Gemfile",
            "tsconfig.json", "next.config.js", "nuxt.config.js",
            "nginx.conf", "apache.conf", ".htaccess",
            "README.md", "DEPLOYMENT.md", "INSTALL.md"
        ]
        file_contents = {}
        async with httpx.AsyncClient() as client:
            for file_name in critical_files:
                try:
                    url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_name}"
                    response = await client.get(
                        url,
                        headers={"Authorization": f"token {current_user['github_access_token']}"}
                    )
                    if response.status_code == 200:
                        file_data = response.json()
                        if file_data.get('content'):
                            import base64
                            content = base64.b64decode(file_data['content']).decode('utf-8')
                            file_contents[file_name] = {
                                "path": file_data['path'],
                                "content": content[:2000],
                                "size": file_data['size']
                            }
                except Exception:
                    continue
        return file_contents
    structure = await get_repo_structure()
    critical_files = await get_critical_file_contents()
    return {"structure": structure, "critical_files": critical_files}

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/logged-out")
    response.delete_cookie(
        key="access_token", 
        httponly=True,
        path="/",
        domain=None
    )
    response.set_cookie(
        key="access_token", 
        value="", 
        httponly=True,
        max_age=0,
        expires=0,
        path="/"
    )
    return response

@app.get("/logged-out", response_class=HTMLResponse)
async def logged_out():
    return f"""
    <html>
        <head><title>Logged Out</title>
        <style>
            body{{font-family:Arial,sans-serif;margin:20px;max-width:600px;margin:0 auto;padding:50px 20px;text-align:center}}
            .container{{border:1px solid #e1e4e8;padding:40px;border-radius:6px;background:#f6f8fa}}
            .success{{color:#28a745;font-size:18px;margin-bottom:20px}}
            .btn{{background:#0969da;color:white;padding:12px 24px;border:none;border-radius:4px;text-decoration:none;display:inline-block;margin:10px}}
            .btn:hover{{background:#0860ca}}
        </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅ Successfully Logged Out</div>
                <p>You have been logged out of the DevOps Automation Tool.</p>
                <p>To access the dashboard again, you'll need to log in.</p>
                <a href="/auth/github" class="btn">Login Again</a>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
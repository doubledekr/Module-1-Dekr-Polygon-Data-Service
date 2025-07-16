#!/usr/bin/env python3
"""
Simple script to run the FastAPI application with gunicorn using uvicorn workers
"""
import os
import sys
import subprocess

def main():
    # Use uvicorn directly for better ASGI support
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app:app",
        "--host", "0.0.0.0",
        "--port", "5000",
        "--reload",
        "--loop", "asyncio"
    ]
    
    print("Starting FastAPI application with uvicorn...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except subprocess.CalledProcessError as e:
        print(f"Error running uvicorn: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
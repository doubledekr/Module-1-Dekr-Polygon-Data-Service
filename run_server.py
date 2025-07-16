#!/usr/bin/env python3
"""
Simple script to run the FastAPI server with uvicorn
"""
import os
import sys
import subprocess

def main():
    # Change to the project directory
    os.chdir('/home/runner/workspace')
    
    # Run uvicorn with the correct settings
    cmd = [
        sys.executable, '-m', 'uvicorn',
        'main:app',
        '--host', '0.0.0.0',
        '--port', '5000',
        '--reload'
    ]
    
    # Execute the command
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error running server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
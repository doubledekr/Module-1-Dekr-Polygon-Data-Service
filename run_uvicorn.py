#!/usr/bin/env python3
"""
Run the FastAPI application with uvicorn directly
"""
import uvicorn
from app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)
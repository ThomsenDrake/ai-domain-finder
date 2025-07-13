#!/usr/bin/env python3
"""
Development server launcher for the Domain Enrichment API
Runs the FastAPI application with auto-reload for development
"""

import os
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Start the development server"""
    
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("⚠️  Warning: OPENROUTER_API_KEY not found in environment")
        print("Please copy .env.example to .env and add your API key")
        print("You can get a free API key from https://openrouter.ai/")
        print()
    
    print("🚀 Starting Domain Enrichment API Development Server")
    print("📍 Server will be available at: http://localhost:8000")
    print("📋 API docs available at: http://localhost:8000/docs")
    print("🧪 Test interface at: http://localhost:8000/test")
    print("🔄 Auto-reload enabled - server will restart on code changes")
    print("📊 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Main entry point for Railway deployment
This file serves as a backup entry point if railpack.toml doesn't work
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import and run the Flask app
from app import app

if __name__ == '__main__':
    # Get port from environment (Railway sets this)
    port = int(os.environ.get('PORT', 8000))
    
    print(f"Starting video automation pipeline on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

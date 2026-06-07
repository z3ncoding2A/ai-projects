#!/usr/bin/env python3
"""
Simple local server for the video grid.
The File System Access API requires an HTTP origin (not file://).
Run this, and it opens the grid in Chrome automatically.
"""
import http.server
import socketserver
import webbrowser
import os
import threading

PORT = 8888
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
FILE = "z3ncoding_videos_grid.html"

os.chdir(DIRECTORY)

Handler = http.server.SimpleHTTPRequestHandler

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    url = f"http://localhost:{PORT}/{FILE}"
    print(f"Serving at http://localhost:{PORT}")
    print(f"Opening {url}")
    print("Press Ctrl+C to stop.\n")

    # Open in google-chrome-stable after a short delay
    def open_browser():
        try:
            os.system(f'google-chrome-stable "{url}" 2>/dev/null &')
        except Exception:
            webbrowser.open(url)

    threading.Timer(0.5, open_browser).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

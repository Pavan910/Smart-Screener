from http.server import BaseHTTPRequestHandler
import json
import os
import hashlib

# Password is stored ONLY in Vercel environment variable
# Set it in Vercel Dashboard: Settings > Environment Variables
# Variable name: APP_PASSWORD
# If not set, authentication will fail

def get_password():
    return os.environ.get('APP_PASSWORD', '')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        submitted_password = data.get("password", "")
        correct_password = get_password()

        # Check if password is configured
        if not correct_password:
            response = json.dumps({
                "success": False,
                "error": "Password not configured. Set APP_PASSWORD in Vercel."
            })
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response.encode())
            return

        if submitted_password == correct_password:
            # Generate a simple session token
            token = hash_password(correct_password + "smart-screener-session")
            response = json.dumps({
                "success": True,
                "token": token
            })
            self.send_response(200)
        else:
            response = json.dumps({
                "success": False,
                "error": "Invalid password"
            })
            self.send_response(401)

        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response.encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

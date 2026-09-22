"""Mock Job Application Web Server for Step 7 Playwright Automation Tests.

Runs a lightweight HTTP server on localhost with 4 test endpoints:
1. /job/standard: Standard application form (inputs, CV upload, cover letter, submit).
2. /job/captcha: Application form containing CAPTCHA challenge elements (AUT-08).
3. /job/error: Malformed form without submit button (AUT-03).
4. /job/timeout: Slow endpoint to test timeout handling (AUT-11).
"""

import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

STANDARD_FORM_HTML = """<!DOCTYPE html>
<html>
<head><title>Job Application - Standard</title></head>
<body>
  <h1>Apply for Senior Engineer</h1>
  <form id="apply-form" action="/job/success" method="POST" enctype="multipart/form-data">
    <div>
      <label for="full_name">Full Name</label>
      <input type="text" id="full_name" name="full_name" placeholder="Full Name" required />
    </div>
    <div>
      <label for="email">Email</label>
      <input type="email" id="email" name="email" placeholder="Email Address" required />
    </div>
    <div>
      <label for="phone">Phone</label>
      <input type="tel" id="phone" name="phone" placeholder="Phone Number" />
    </div>
    <div>
      <label for="location">Location</label>
      <input type="text" id="location" name="location" placeholder="City, State" />
    </div>
    <div>
      <label for="linkedin">LinkedIn</label>
      <input type="url" id="linkedin" name="linkedin" placeholder="LinkedIn URL" />
    </div>
    <div>
      <label for="resume">Resume / CV</label>
      <input type="file" id="resume" name="resume" accept=".pdf,.docx" />
    </div>
    <div>
      <label for="cover_letter">Cover Letter</label>
      <textarea id="cover_letter" name="cover_letter" rows="6" placeholder="Paste your cover letter"></textarea>
    </div>
    <div>
      <button type="submit" id="submit-btn">Submit Application</button>
    </div>
  </form>
</body>
</html>
"""

CAPTCHA_FORM_HTML = """<!DOCTYPE html>
<html>
<head><title>Job Application - Protected</title></head>
<body>
  <h1>Security Check Required</h1>
  <form id="apply-form" action="/job/success" method="POST">
    <input type="text" id="full_name" name="full_name" placeholder="Full Name" />
    <input type="email" id="email" name="email" placeholder="Email" />
    <div class="g-recaptcha" data-sitekey="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-">
      <iframe src="https://www.google.com/recaptcha/api2/anchor?k=6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-" width="300" height="78" style="display:block;"></iframe>
    </div>
    <button type="submit">Submit Application</button>
  </form>
</body>
</html>
"""

ERROR_FORM_HTML = """<!DOCTYPE html>
<html>
<head><title>Job Application - Broken</title></head>
<body>
  <h1>Malformed Application Page</h1>
  <p>This page has no accessible form or submission action.</p>
  <div>Contact us at jobs@example.com instead.</div>
</body>
</html>
"""

SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head><title>Application Submitted</title></head>
<body>
  <h1>Thank You!</h1>
  <p id="success-msg">Your application has been received successfully.</p>
</body>
</html>
"""


class MockJobRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/job/standard":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(STANDARD_FORM_HTML.encode("utf-8"))
        elif self.path == "/job/captcha":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(CAPTCHA_FORM_HTML.encode("utf-8"))
        elif self.path == "/job/error":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(ERROR_FORM_HTML.encode("utf-8"))
        elif self.path == "/job/timeout":
            # Sleep 10 seconds to simulate timeout
            time.sleep(10)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path in ("/job/success", "/job/standard"):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(SUCCESS_HTML.encode("utf-8"))
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(SUCCESS_HTML.encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress HTTP server output in test logs
        pass


def start_mock_server(port: int = 8899) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), MockJobRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

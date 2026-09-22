import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./autoapply.db")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@autoapply.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "720"))

# Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Automation / Playwright
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
AUTOMATION_TIMEOUT_SECONDS = int(os.getenv("AUTOMATION_TIMEOUT_SECONDS", "120"))
BROWSER_NAME = os.getenv("BROWSER_NAME", "brave").lower()
LINKEDIN_COOKIE_LI_AT = os.getenv("LINKEDIN_COOKIE_LI_AT", "")



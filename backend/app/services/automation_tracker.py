"""Automation Error Handling & Diagnostics Tracker.

Implements requirements:
  AUT-19: Record current automation phase for every application attempt.
  AUT-20: Classify automation failures using predefined error types.
  AUT-21: Preserve original technical exception/error message.
  AUT-22: Maintain ordered action log for every attempt.
  AUT-23: Record last successful action before failure.
  AUT-24: Capture current URL and automation state when error occurs.
  AUT-25: Capture screenshot when critical automation error occurs.
  AUT-26: Assign unique execution ID to every automation attempt.
  AUT-27: Distinguish retryable from non-retryable errors.
  AUT-28: Retry eligible transient errors a maximum of 2 times.
  AUT-29: Provide human-readable failure summary.
  AUT-30: Preserve detailed technical debugging information.
  AUT-31: Never silently swallow automation exceptions.
  AUT-32: Store sufficient execution context to diagnose failed attempts.
"""

import os
import json
import uuid
import logging
import traceback
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AutomationPhase(str, Enum):
    PRE_FLIGHT = "PRE_FLIGHT"
    BROWSER_LAUNCH = "BROWSER_LAUNCH"
    NAVIGATION = "NAVIGATION"
    CAPTCHA_CHECK = "CAPTCHA_CHECK"
    FORM_DETECTION = "FORM_DETECTION"
    APPLICATION_DISCOVERY = "APPLICATION_DISCOVERY"
    BUTTON_DETECTION = "BUTTON_DETECTION"
    BUTTON_CLICK = "BUTTON_CLICK"
    FORM_FILLING = "FORM_FILLING"
    FILE_UPLOAD = "FILE_UPLOAD"
    MULTI_STEP_NAVIGATION = "MULTI_STEP_NAVIGATION"
    SUBMISSION = "SUBMISSION"
    SUBMISSION_VERIFICATION = "SUBMISSION_VERIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Predefined Error Types
class ErrorType:
    # Browser Errors
    BROWSER_LAUNCH_FAILED = "BROWSER_LAUNCH_FAILED"
    PROFILE_IN_USE = "PROFILE_IN_USE"
    BROWSER_CRASHED = "BROWSER_CRASHED"
    PAGE_CRASHED = "PAGE_CRASHED"
    BROWSER_CONTEXT_FAILED = "BROWSER_CONTEXT_FAILED"

    # Navigation Errors
    NAVIGATION_TIMEOUT = "NAVIGATION_TIMEOUT"
    NAVIGATION_FAILED = "NAVIGATION_FAILED"
    INVALID_URL = "INVALID_URL"
    NETWORK_ERROR = "NETWORK_ERROR"
    DNS_ERROR = "DNS_ERROR"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    TOO_MANY_REDIRECTS = "TOO_MANY_REDIRECTS"

    # Access / Blocking Errors
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    CLOUDFLARE_CHALLENGE = "CLOUDFLARE_CHALLENGE"
    ACCESS_DENIED = "ACCESS_DENIED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    REGISTRATION_REQUIRED = "REGISTRATION_REQUIRED"
    GEO_BLOCKED = "GEO_BLOCKED"
    APPLICATION_CLOSED = "APPLICATION_CLOSED"

    # Discovery Errors
    FORM_NOT_FOUND = "FORM_NOT_FOUND"
    APPLY_BUTTON_NOT_FOUND = "APPLY_BUTTON_NOT_FOUND"
    APPLY_BUTTON_CLICK_FAILED = "APPLY_BUTTON_CLICK_FAILED"
    APPLICATION_NOT_REACHABLE = "APPLICATION_NOT_REACHABLE"
    DISCOVERY_DEPTH_EXCEEDED = "DISCOVERY_DEPTH_EXCEEDED"
    UNSUPPORTED_APPLICATION_FLOW = "UNSUPPORTED_APPLICATION_FLOW"

    # Form Errors
    FORM_DETECTION_FAILED = "FORM_DETECTION_FAILED"
    FIELD_NOT_FOUND = "FIELD_NOT_FOUND"
    FIELD_FILL_FAILED = "FIELD_FILL_FAILED"
    DROPDOWN_SELECTION_FAILED = "DROPDOWN_SELECTION_FAILED"
    CHECKBOX_FAILED = "CHECKBOX_FAILED"
    RADIO_BUTTON_FAILED = "RADIO_BUTTON_FAILED"
    FILE_UPLOAD_FAILED = "FILE_UPLOAD_FAILED"
    MULTI_STEP_NAVIGATION_FAILED = "MULTI_STEP_NAVIGATION_FAILED"

    # Submission Errors
    SUBMIT_BUTTON_NOT_FOUND = "SUBMIT_BUTTON_NOT_FOUND"
    SUBMIT_CLICK_FAILED = "SUBMIT_CLICK_FAILED"
    SUBMISSION_TIMEOUT = "SUBMISSION_TIMEOUT"
    SUBMISSION_REJECTED = "SUBMISSION_REJECTED"
    SUBMISSION_VERIFICATION_FAILED = "SUBMISSION_VERIFICATION_FAILED"

    # System Errors
    DATABASE_ERROR = "DATABASE_ERROR"
    CV_FILE_NOT_FOUND = "CV_FILE_NOT_FOUND"
    COVER_LETTER_NOT_FOUND = "COVER_LETTER_NOT_FOUND"
    PROFILE_DATA_MISSING = "PROFILE_DATA_MISSING"
    AI_ERROR = "AI_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Transient error types eligible for auto-retry (AUT-27, AUT-28)
RETRYABLE_ERROR_TYPES = {
    ErrorType.NAVIGATION_TIMEOUT,
    ErrorType.NETWORK_ERROR,
    ErrorType.DNS_ERROR,
    ErrorType.CONNECTION_REFUSED,
    ErrorType.BROWSER_CONTEXT_FAILED,
}

MAX_TRANSIENT_RETRIES = 2


def generate_execution_id(application_id: int) -> str:
    """Generate unique execution ID: AUT-YYYYMMDD-APPID-XXXX (AUT-26)."""
    date_str = datetime.utcnow().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"AUT-{date_str}-{application_id:04d}-{unique_suffix}"


class AutomationTracker:
    """Tracks state, phases, action logs, browser artifacts, and diagnostics for an automation run."""

    def __init__(self, application_id: int, user_id: int | None = None):
        self.application_id = application_id
        self.user_id = user_id
        self.execution_id = generate_execution_id(application_id)
        self.current_phase = AutomationPhase.PRE_FLIGHT
        self.current_url: str | None = None
        self.discovery_step: int = 0
        self.last_successful_action: str | None = None
        self.current_action: str | None = None
        self.action_log: list[dict[str, Any]] = []
        self.screenshot_path: str | None = None
        self.html_snapshot_path: str | None = None
        self.structured_error: dict[str, Any] | None = None
        self.retry_counts: dict[str, int] = {}
        self.started_at = datetime.utcnow()

        # Prepare log directory
        base_backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.artifacts_dir = os.path.join(base_backend, "automation_logs", f"app_{application_id}")
        os.makedirs(self.artifacts_dir, exist_ok=True)

        self.log_action(
            phase=AutomationPhase.PRE_FLIGHT,
            action="Initialization",
            status="SUCCESS",
            details=f"Automation execution {self.execution_id} initialized for Application #{application_id}.",
        )

    def set_phase(self, phase: AutomationPhase) -> None:
        """Update current automation phase (AUT-19)."""
        self.current_phase = phase
        logger.info(
            "[%s] Phase -> %s (step: %d, url: %s)",
            self.execution_id,
            phase.value,
            self.discovery_step,
            self.current_url or "N/A",
        )

    def set_url(self, url: str) -> None:
        """Update current browser URL."""
        self.current_url = url

    def set_discovery_step(self, step: int) -> None:
        """Update current discovery step number."""
        self.discovery_step = step

    def log_action(
        self,
        phase: AutomationPhase,
        action: str,
        status: str = "SUCCESS",
        details: str | None = None,
        url: str | None = None,
        mark_successful: bool = False,
    ) -> None:
        """
        Record an ordered action log entry (AUT-22).
        If mark_successful is True, records this action as last_successful_action (AUT-23).
        """
        self.current_phase = phase
        self.current_action = action
        entry_url = url or self.current_url

        if mark_successful or status == "SUCCESS":
            self.last_successful_action = action

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "phase": phase.value,
            "action": action,
            "status": status,
            "details": details or "",
            "url": entry_url,
            "discovery_step": self.discovery_step,
        }
        self.action_log.append(entry)
        logger.info(
            "[%s] [%s] [%s] %s %s",
            self.execution_id,
            phase.value,
            status,
            action,
            f"({details})" if details else "",
        )

    def is_retryable(self, error_type: str) -> bool:
        """Check if an error type can be retried and retries remain (AUT-27, AUT-28)."""
        if error_type not in RETRYABLE_ERROR_TYPES:
            return False
        count = self.retry_counts.get(error_type, 0)
        return count < MAX_TRANSIENT_RETRIES

    def record_retry(self, error_type: str) -> int:
        """Increment and return retry count for an error type."""
        count = self.retry_counts.get(error_type, 0) + 1
        self.retry_counts[error_type] = count
        return count

    async def capture_state_on_error(
        self,
        page: Any,
        phase: AutomationPhase,
        error_type: str,
        technical_error: str,
        action: str | None = None,
        selector: str | None = None,
        element_text: str | None = None,
        manual_intervention_required: bool = False,
    ) -> dict[str, Any]:
        """
        Capture browser screenshot, HTML snapshot, and build structured error object (AUT-24, AUT-25, AUT-30).
        """
        self.current_phase = AutomationPhase.FAILED
        page_title = "Unknown"
        page_url = self.current_url or "Unknown"

        # Capture screenshot and HTML if page is active
        if page:
            try:
                page_url = page.url or page_url
                self.current_url = page_url
            except Exception:
                pass

            try:
                page_title = await page.title()
            except Exception:
                pass

            # Screenshot
            try:
                scr_filename = f"{self.execution_id}_error.png"
                scr_path = os.path.join(self.artifacts_dir, scr_filename)
                await page.screenshot(path=scr_path, full_page=False)
                self.screenshot_path = scr_path
                logger.info("[%s] Captured failure screenshot at %s", self.execution_id, scr_path)
            except Exception as scr_err:
                logger.warning("[%s] Failed to capture screenshot: %s", self.execution_id, scr_err)

            # HTML Snapshot
            try:
                html_filename = f"{self.execution_id}_page.html"
                html_path = os.path.join(self.artifacts_dir, html_filename)
                content = await page.content()
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.html_snapshot_path = html_path
                logger.info("[%s] Captured HTML snapshot at %s", self.execution_id, html_path)
            except Exception as html_err:
                logger.warning("[%s] Failed to capture HTML snapshot: %s", self.execution_id, html_err)

        # Human-readable failure explanation
        human_reason = self.generate_human_message(
            phase=phase,
            error_type=error_type,
            action=action or self.current_action or "Unknown action",
            url=page_url,
            technical_error=technical_error,
            element_text=element_text,
        )

        # Structured error object (AUT-11.3)
        self.structured_error = {
            "execution_id": self.execution_id,
            "phase": phase.value,
            "error_type": error_type,
            "message": human_reason,
            "technical_error": technical_error,
            "url": page_url,
            "page_title": page_title,
            "discovery_step": self.discovery_step,
            "action": action or self.current_action or "",
            "last_successful_action": self.last_successful_action or "None",
            "element_text": element_text,
            "selector": selector,
            "recoverable": self.is_retryable(error_type),
            "manual_intervention_required": manual_intervention_required,
            "screenshot_path": self.screenshot_path,
            "html_snapshot_path": self.html_snapshot_path,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Save error.json
        try:
            error_json_path = os.path.join(self.artifacts_dir, f"{self.execution_id}_error.json")
            with open(error_json_path, "w", encoding="utf-8") as f:
                json.dump(self.structured_error, f, indent=2)
        except Exception as json_err:
            logger.warning("[%s] Failed to write error.json: %s", self.execution_id, json_err)

        # Log final FAILED action entry
        self.log_action(
            phase=AutomationPhase.FAILED,
            action=action or self.current_action or "Automation failure",
            status="FAILED",
            details=f"[{error_type}] {human_reason}",
            url=page_url,
        )

        return self.structured_error

    def generate_human_message(
        self,
        phase: AutomationPhase,
        error_type: str,
        action: str,
        url: str,
        technical_error: str,
        element_text: str | None = None,
    ) -> str:
        """
        Generate a clear, human-readable failure explanation (AUT-29, Section 11.5).
        """
        if error_type == ErrorType.CAPTCHA_DETECTED:
            return (
                "A CAPTCHA or security verification challenge appeared on the page. "
                "Automated submission cannot bypass security challenges. Please complete the application manually."
            )
        if error_type == ErrorType.LOGIN_REQUIRED:
            return (
                "The application page requires an active account login or registration to proceed. "
                "Please log in to this portal in your browser or submit the application manually."
            )
        if error_type == ErrorType.FORM_NOT_FOUND:
            return (
                "The automation navigated to the job posting but could not locate an application form "
                "or an Apply button on the page."
            )
        if error_type == ErrorType.APPLICATION_NOT_REACHABLE:
            return (
                f"The system clicked '{element_text or 'Apply'}' but the application form did not become "
                f"available after navigation (Step {self.discovery_step} of 5)."
            )
        if error_type == ErrorType.DISCOVERY_DEPTH_EXCEEDED:
            return (
                "Exceeded maximum discovery depth (5 steps). The website required multiple nested pages "
                "or external redirects without presenting a standard form."
            )
        if error_type == ErrorType.APPLY_BUTTON_CLICK_FAILED:
            return (
                f"Found the '{element_text or 'Apply'}' button, but it could not be clicked. "
                f"The button may be disabled, obscured by an overlay, or navigated away unexpectedly."
            )
        if error_type == ErrorType.SUBMIT_BUTTON_NOT_FOUND:
            return "Filled the application form fields, but could not locate a visible Submit button to send the application."
        if error_type == ErrorType.SUBMIT_CLICK_FAILED:
            return "Located the form Submit button, but clicking it failed or was blocked by the website."
        if error_type == ErrorType.NAVIGATION_TIMEOUT:
            return f"The page at {url} took too long to respond and timed out."
        if error_type == ErrorType.NETWORK_ERROR:
            return f"A network connection error occurred while loading {url}."
        if error_type == ErrorType.BROWSER_LAUNCH_FAILED:
            return "Failed to launch the browser automation engine. System environment or browser executable issue."
        if error_type == ErrorType.PROFILE_IN_USE:
            return "Browser profile is currently in use. Please close the AutoApply login browser and retry."

        # Default human-readable composition
        phase_label = phase.value.replace("_", " ").title()
        return f"Application stopped during {phase_label} while attempting to {action}."

    def get_serialized_action_log(self) -> str:
        """Return action log serialized as JSON string."""
        return json.dumps(self.action_log)

    def get_serialized_error_details(self) -> str | None:
        """Return structured error object serialized as JSON string."""
        return json.dumps(self.structured_error) if self.structured_error else None


def classify_exception(exc: Exception, current_phase: AutomationPhase) -> tuple[str, bool]:
    """
    Classify an arbitrary exception into (error_type, manual_intervention_required).
    """
    msg = str(exc).lower()
    exc_type = type(exc).__name__

    if "profile" in msg and ("in use" in msg or "locked" in msg or "already" in msg):
        return ErrorType.PROFILE_IN_USE, True

    if exc_type == "ProfileInUseError":
        return ErrorType.PROFILE_IN_USE, True

    if "captcha" in msg or "cloudflare" in msg or "turnstile" in msg or "human verification" in msg:
        return ErrorType.CAPTCHA_DETECTED, True

    if "login" in msg or "sign in" in msg or "authentication" in msg:
        return ErrorType.LOGIN_REQUIRED, True

    if "timeout" in msg or exc_type == "TimeoutError":
        if current_phase in (AutomationPhase.NAVIGATION, AutomationPhase.PRE_FLIGHT):
            return ErrorType.NAVIGATION_TIMEOUT, False
        if current_phase in (AutomationPhase.BUTTON_CLICK, AutomationPhase.APPLICATION_DISCOVERY):
            return ErrorType.APPLY_BUTTON_CLICK_FAILED, False
        if current_phase in (AutomationPhase.SUBMISSION, AutomationPhase.SUBMISSION_VERIFICATION):
            return ErrorType.SUBMISSION_TIMEOUT, False
        return ErrorType.NAVIGATION_TIMEOUT, False

    if "net::err" in msg or "connection refused" in msg:
        return ErrorType.NETWORK_ERROR, False

    if "dns" in msg or "getaddrinfo" in msg:
        return ErrorType.DNS_ERROR, False

    if "target closed" in msg or "browser has been closed" in msg or "crash" in msg:
        return ErrorType.BROWSER_CRASHED, False

    if "no apply button" in msg or "not found" in msg and current_phase == AutomationPhase.FORM_DETECTION:
        return ErrorType.FORM_NOT_FOUND, False

    if "could not be reached" in msg:
        return ErrorType.APPLICATION_NOT_REACHABLE, False

    if current_phase == AutomationPhase.BUTTON_CLICK:
        return ErrorType.APPLY_BUTTON_CLICK_FAILED, False

    if current_phase == AutomationPhase.SUBMISSION:
        return ErrorType.SUBMIT_CLICK_FAILED, False

    if current_phase in (AutomationPhase.FORM_FILLING, AutomationPhase.FILE_UPLOAD):
        return ErrorType.FIELD_FILL_FAILED, False

    return ErrorType.INTERNAL_ERROR, False

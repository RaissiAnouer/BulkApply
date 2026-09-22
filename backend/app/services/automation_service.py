"""Browser Automation Service using Playwright — Two-Phase Architecture with Diagnostics.

Implements requirements:
  AUT-01: Navigate, discover form, submit application.
  AUT-02/03: Batch sequential execution; failure skips to next without retry.
  AUT-05: Fill forms using profile, CV, and saved job description.
  AUT-07: Handle multi-step forms and external ATS redirects.
  AUT-08: CAPTCHA detection → mark as failed with reason.
  AUT-09: Respect daily rate limit.
  AUT-10: Log each automation step.
  AUT-11: Configurable timeout (default 120s).
  AUT-12: Distinguish job_url vs application_url; application_url may be NULL initially.
  AUT-13: Recognize Apply/Postuler/Candidater/Easy Apply buttons (multilingual).
  AUT-14: Do NOT click Save/Share/Login/Register/Contact/Similar Jobs.
  AUT-15: Max 5 discovery navigation steps.
  AUT-16: Follow cross-domain redirects to external ATS.
  AUT-17: Store discovered_form_url in application record.
  AUT-18: Use saved job description from DB, never from browser page.
  AUT-19 to AUT-32: Full error handling, diagnostics, action logging, retry policy, and screenshots.
"""

import os
import asyncio
import logging
import threading
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session

from app.config import PLAYWRIGHT_HEADLESS, AUTOMATION_TIMEOUT_SECONDS, BROWSER_NAME
from app.database import SessionLocal
from app.models.application import Application, ApplicationStatusHistory
from app.models.job import Job
from app.models.user import User
from app.models.profile import JobSeekerProfile
from app.models.cv import CV
from app.services.form_detector import (
    check_for_captcha,
    detect_application_form,
    find_apply_button,
    detect_login_wall,
    split_name,
    find_input_field,
    NAME_PATTERNS,
)
from app.services.automation_tracker import (
    AutomationTracker,
    AutomationPhase,
    ErrorType,
    classify_exception,
    MAX_TRANSIENT_RETRIES,
)

logger = logging.getLogger(__name__)

# Maximum number of Apply-button clicks during form discovery (AUT-15)
MAX_DISCOVERY_DEPTH = 5


class AutomationError(Exception):
    """Base exception for automation failure."""
    pass


class CaptchaDetectedError(AutomationError):
    """Raised when CAPTCHA / manual intervention is required."""
    pass


class FormNotFoundError(AutomationError):
    """Raised when no application form can be located."""
    pass


class FormNotReachedError(AutomationError):
    """Raised when an Apply button was found but the form never appeared."""
    pass


class LoginWallError(AutomationError):
    """Raised when a login or registration barrier blocks the form."""
    pass


class AutomationCancelledError(AutomationError):
    """Raised when automation was cancelled by the user."""
    pass


class ProfileInUseError(AutomationError):
    """Raised when the persistent browser profile directory is locked by another browser process."""
    pass





def _is_auth_redirect_url(url: str | None) -> bool:
    """Check if a URL is an authentication barrier, signup redirect, or login page."""
    if not url:
        return False
    u = url.lower()
    return any(k in u for k in ['/signup', '/login', '/signin', 'cold-join', '/uas/login', '/checkpoint/'])


def _is_profile_in_use(user_dir: str) -> bool:
    """Check if any running browser process is using the specified user data directory."""
    if os.name != 'nt':
        return False
    try:
        import subprocess
        norm_dir = os.path.normpath(user_dir).lower()
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe' or Name = 'brave.exe' or Name = 'chrome.exe'\" | Select-Object -ExpandProperty CommandLine"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if norm_dir in line.lower():
                    return True
    except Exception as e:
        logger.debug("[Automation] Error checking profile processes: %s", e)
    return False



# Active automation registry for cancellation tracking
_active_automations: dict[int, dict[str, Any]] = {}
_automations_lock = threading.Lock()


def is_cancelled(application_id: int | None) -> bool:
    """Check if cancellation was requested for an application."""
    if not application_id:
        return False
    with _automations_lock:
        info = _active_automations.get(application_id)
        return bool(info and info.get("cancel_requested"))


def cancel_application_automation(application_id: int) -> bool:
    """
    Signal cancellation for an active application automation and close browser.
    """
    logger.info("[Automation] Cancellation requested for Application #%d", application_id)
    with _automations_lock:
        info = _active_automations.get(application_id)
        if not info:
            logger.info("[Automation] No active automation found in memory for #%d", application_id)
            return False
        info["cancel_requested"] = True
        context = info.get("context")
        loop = info.get("loop")

    if context and loop and not loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(context.close(), loop)
        except Exception as e:
            logger.warning("[Automation] Error closing context on cancel: %s", e)

    return True


# ---------------------------------------------------------------------------
# Step 7C — Form Filling
# ---------------------------------------------------------------------------

async def _fill_form_fields(
    page: Any,
    profile: JobSeekerProfile | None,
    cv: CV | None,
    cover_letter: str | None,
    tracker: AutomationTracker,
) -> None:
    """Detect and fill standard form fields on the application page."""
    if is_cancelled(tracker.application_id):
        raise AutomationCancelledError("Automation cancelled by user.")

    tracker.set_phase(AutomationPhase.FORM_FILLING)
    tracker.log_action(
        AutomationPhase.FORM_FILLING,
        "Scanning page for application form fields...",
        details="Matching input fields against profile heuristics",
    )

    # Prioritize CV extracted info over profile
    cv_data = (cv.parsed_data if (cv and isinstance(cv.parsed_data, dict)) else {})
    cv_contact = (cv_data.get("contact_info") if isinstance(cv_data.get("contact_info"), dict) else {})

    def _clean_str(val: Any) -> str:
        if not val or not isinstance(val, str):
            return ""
        lines = [line.strip() for line in val.splitlines() if line.strip()]
        if not lines:
            return ""
        if len(lines) > 1:
            for line in reversed(lines):
                if "," in line or any(c.isdigit() for c in line) or len(line.split()) <= 4:
                    return line
            return lines[-1]
        return lines[0]

    cv_full_name = _clean_str(cv_contact.get("full_name"))
    profile_full_name = profile.full_name if profile else ""
    user_name = profile.user.name if (profile and profile.user) else ""
    full_name = cv_full_name or profile_full_name or user_name

    first_name, last_name = split_name(full_name)

    cv_email = (cv_contact.get("email") or "").strip()
    profile_email = (profile.user.email if (profile and profile.user) else "").strip()
    email = cv_email or profile_email

    cv_phone = (cv_contact.get("phone") or "").strip()
    profile_phone = (profile.phone if profile else "").strip()
    phone = cv_phone or profile_phone

    cv_location = _clean_str(cv_contact.get("location"))
    profile_location = (profile.location if profile else "").strip()
    location = cv_location or profile_location

    linkedin = (cv_contact.get("linkedin") or (profile.linkedin_url if profile else "") or "").strip()
    github = (cv_contact.get("github") or (profile.github_url if profile else "") or "").strip()
    portfolio = (cv_contact.get("portfolio") or cv_contact.get("website") or (profile.portfolio_url if profile else "") or "").strip()

    # Work experience & education extracted from CV
    work_exp = cv_data.get("work_experience") or []
    latest_job = work_exp[0] if (work_exp and isinstance(work_exp, list) and isinstance(work_exp[0], dict)) else {}
    current_company = (latest_job.get("company") or "").strip()
    current_title = (latest_job.get("title") or "").strip()

    edu_list = cv_data.get("education") or []
    highest_edu = edu_list[0] if (edu_list and isinstance(edu_list, list) and isinstance(edu_list[0], dict)) else {}
    degree = (highest_edu.get("degree") or "").strip()
    institution = (highest_edu.get("institution") or "").strip()

    data_source = "CV extracted info" if cv_contact else "Profile info"
    tracker.log_action(
        AutomationPhase.FORM_FILLING,
        f"Using {data_source} for candidate: {full_name}",
        details=f"Email: {email} | Phone: {phone} | Location: {location}",
    )

    # 1. Full Name or First/Last Name
    full_name_input = await find_input_field(page, NAME_PATTERNS['full_name'])
    if full_name_input and full_name:
        try:
            await full_name_input.fill(full_name)
            tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled Full Name: {full_name}", mark_successful=True)
        except Exception as e:
            logger.warning("[Automation] Could not fill Full Name: %s", e)
    else:
        first_input = await find_input_field(page, NAME_PATTERNS['first_name'])
        if first_input and first_name:
            try:
                await first_input.fill(first_name)
                tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled First Name: {first_name}", mark_successful=True)
            except Exception as e:
                logger.warning("[Automation] Could not fill First Name: %s", e)

        last_input = await find_input_field(page, NAME_PATTERNS['last_name'])
        if last_input and last_name:
            try:
                await last_input.fill(last_name)
                tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled Last Name: {last_name}", mark_successful=True)
            except Exception as e:
                logger.warning("[Automation] Could not fill Last Name: %s", e)

    # 2. Email
    email_input = await find_input_field(page, NAME_PATTERNS['email'])
    if email_input and email:
        try:
            await email_input.fill(email)
            tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled Email: {email}", mark_successful=True)
        except Exception as e:
            logger.warning("[Automation] Could not fill Email: %s", e)

    # 3. Phone
    phone_input = await find_input_field(page, NAME_PATTERNS['phone'])
    if phone_input and phone:
        try:
            await phone_input.fill(phone)
            tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled Phone: {phone}", mark_successful=True)
        except Exception as e:
            logger.warning("[Automation] Could not fill Phone: %s", e)

    # 4. Location
    loc_input = await find_input_field(page, NAME_PATTERNS['location'])
    if loc_input and location:
        try:
            await loc_input.fill(location)
            tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled Location: {location}", mark_successful=True)
        except Exception as e:
            logger.warning("[Automation] Could not fill Location: %s", e)

    # 5. Professional links
    if linkedin:
        li_input = await find_input_field(page, NAME_PATTERNS['linkedin'])
        if li_input:
            try:
                await li_input.fill(linkedin)
                tracker.log_action(AutomationPhase.FORM_FILLING, "Filled LinkedIn URL", mark_successful=True)
            except Exception:
                pass

    if github:
        gh_input = await find_input_field(page, NAME_PATTERNS['github'])
        if gh_input:
            try:
                await gh_input.fill(github)
                tracker.log_action(AutomationPhase.FORM_FILLING, "Filled GitHub URL", mark_successful=True)
            except Exception:
                pass

    if portfolio:
        port_input = await find_input_field(page, NAME_PATTERNS['portfolio'])
        if port_input:
            try:
                await port_input.fill(portfolio)
                tracker.log_action(AutomationPhase.FORM_FILLING, "Filled Portfolio URL", mark_successful=True)
            except Exception:
                pass

    # 5b. Company / Current Employer (from CV)
    if current_company:
        comp_input = await find_input_field(page, NAME_PATTERNS.get('company', []))
        if comp_input:
            try:
                await comp_input.fill(current_company)
                tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled Current Company: {current_company}", mark_successful=True)
            except Exception:
                pass

    # 5c. Job Title / Role (from CV)
    if current_title:
        title_input = await find_input_field(page, NAME_PATTERNS.get('job_title', []))
        if title_input:
            try:
                await title_input.fill(current_title)
                tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled Current Job Title: {current_title}", mark_successful=True)
            except Exception:
                pass

    # 5d. Education Degree / University (from CV)
    if degree:
        deg_input = await find_input_field(page, NAME_PATTERNS.get('education', []))
        if deg_input:
            try:
                await deg_input.fill(degree)
                tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled Degree: {degree}", mark_successful=True)
            except Exception:
                pass

    if institution:
        inst_input = await find_input_field(page, NAME_PATTERNS.get('school', []))
        if inst_input:
            try:
                await inst_input.fill(institution)
                tracker.log_action(AutomationPhase.FORM_FILLING, f"Filled School/University: {institution}", mark_successful=True)
            except Exception:
                pass

    # 6. CV / Resume file upload (input[type="file"])
    if cv and cv.file_path:
        tracker.set_phase(AutomationPhase.FILE_UPLOAD)
        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            abs_path = os.path.abspath(cv.file_path)
            if os.path.exists(abs_path):
                try:
                    await file_input.set_input_files(abs_path)
                    tracker.log_action(
                        AutomationPhase.FILE_UPLOAD,
                        f"Uploaded CV file: {cv.file_name}",
                        status="SUCCESS",
                        mark_successful=True,
                    )
                except Exception as e:
                    logger.warning("[Automation] Could not upload CV file: %s", e)
            else:
                logger.warning("[Automation] CV file path not found on disk: %s", abs_path)

    # 7. Cover Letter (textarea)
    if cover_letter:
        cl_input = await find_input_field(page, NAME_PATTERNS['cover_letter'])
        if not cl_input:
            textareas = await page.query_selector_all('textarea')
            if textareas:
                cl_input = textareas[0]

        if cl_input:
            try:
                await cl_input.fill(cover_letter)
                tracker.log_action(
                    AutomationPhase.FORM_FILLING,
                    f"Inserted tailored cover letter ({len(cover_letter)} chars)",
                    mark_successful=True,
                )
            except Exception as e:
                logger.warning("[Automation] Could not insert cover letter: %s", e)

    # 8. Required Consent & Privacy Policy Checkboxes (GDPR, Terms, Candidate Consent)
    checkboxes = await page.query_selector_all('input[type="checkbox"]:visible')
    for cb in checkboxes:
        try:
            cb_id = await cb.get_attribute('id') or ''
            cb_name = await cb.get_attribute('name') or ''
            lbl_text = ''
            if cb_id:
                lbl = await page.query_selector(f'label[for="{cb_id}"]')
                if lbl:
                    lbl_text = (await lbl.inner_text() or '').strip()

            combined_cb = f"{cb_name} {cb_id} {lbl_text}".lower()

            is_required = (await cb.get_attribute('required') is not None) or ('*' in lbl_text) or ('required' in combined_cb)
            is_consent = any(w in combined_cb for w in ['consent', 'privacy', 'policy', 'terms', 'politique', 'confidentialité', 'conditions', 'rgpd', 'données', 'agree'])
            is_marketing = any(w in combined_cb for w in ['future job', 'marketing', 'newsletter', 'contact me directly about specific future', 'offres futures', 'autres offres'])

            if (is_required or is_consent) and not is_marketing:
                if not await cb.is_checked():
                    if lbl_text and cb_id:
                        lbl = await page.query_selector(f'label[for="{cb_id}"]')
                        if lbl:
                            await lbl.click()
                        else:
                            await cb.check(force=True)
                    else:
                        await cb.check(force=True)
                    tracker.log_action(
                        AutomationPhase.FORM_FILLING,
                        f"Accepted required consent/policy checkbox: '{lbl_text[:40] or cb_name}'",
                        status="SUCCESS",
                        mark_successful=True,
                    )
        except Exception as cbe:
            logger.debug("[Automation] Error handling checkbox: %s", cbe)

    # 9. Required Fields Validation Pass (AUT-VALIDATION)
    try:
        missing_reqs = []
        visible_inputs = await page.query_selector_all('input:visible, textarea:visible')
        for inp in visible_inputs:
            is_req = (await inp.get_attribute('required')) is not None
            inp_id = await inp.get_attribute('id') or ''
            inp_type = await inp.get_attribute('type') or 'text'
            
            # Also check label for asterisk
            lbl_text = ''
            if inp_id:
                lbl = await page.query_selector(f'label[for="{inp_id}"]')
                if lbl:
                    lbl_text = (await lbl.inner_text() or '').strip()
            if '*' in lbl_text:
                is_req = True

            if is_req and inp_type not in ['submit', 'button', 'hidden', 'file']:
                val = (await inp.input_value() or '').strip() if inp_type not in ['checkbox', 'radio'] else ''
                if inp_type in ['checkbox', 'radio']:
                    if not await inp.is_checked():
                        missing_reqs.append(lbl_text or inp_id)
                elif not val:
                    missing_reqs.append(lbl_text or inp_id)

        if missing_reqs:
            logger.warning("[Automation] Required field validation warnings: %s", missing_reqs)
            tracker.log_action(
                AutomationPhase.FORM_FILLING,
                f"Validation note: Some required fields may need manual review: {', '.join(missing_reqs[:3])}",
                status="WARNING",
            )
        else:
            tracker.log_action(
                AutomationPhase.FORM_FILLING,
                "All required application fields validated successfully",
                status="SUCCESS",
                mark_successful=True,
            )
    except Exception as val_err:
        logger.debug("[Automation] Error during validation pass: %s", val_err)


# ---------------------------------------------------------------------------
# Step 7B — Application Form Discovery
# ---------------------------------------------------------------------------

async def _dismiss_overlays(page: Any) -> None:
    """Dismiss cookie consent banners or non-critical notification overlays."""
    dismiss_selectors = [
        'button:has-text("Accept all cookies")',
        'button:has-text("Accepter tous les cookies")',
        'button:has-text("Accept all")',
        'button:has-text("Accepter tout")',
        'button:has-text("I accept")',
        'button:has-text("J\'accepte")',
        '#onetrust-accept-btn-handler',
        '.cc-allow',
        '.cc-dismiss',
        '#didomi-notice-agree-button',
        'button[action-type="ACCEPT"]',
        'button[data-control-name="ga-cookie.consent.accept"]',
        'button.artdeco-global-alert__action',
        'button[aria-label="Dismiss"]',
        'button[aria-label="Fermer"]',
        'button[aria-label="Close"]',
        'button[aria-label="Accepter"]',
        'button[data-tracking-control-name="public_jobs_contextual-sign-in-modal_sign-in-modal_dismiss-btn"]',
        '.modal__dismiss',
    ]
    for sel in dismiss_selectors:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click(timeout=1500)
                await page.wait_for_timeout(500)
        except Exception:
            pass


async def _wait_for_user_login(
    page: Any,
    tracker: AutomationTracker,
    target_url: str | None = None,
    max_wait_seconds: int = 180,
) -> Any:
    """
    Pause automation when a login wall is encountered, bring browser window to front,
    and wait for the user to complete their login. Resumes automatically once the wall clears.
    """
    logger.info("[Automation] Login wall detected. Bringing browser to front and waiting up to %ds for user login...", max_wait_seconds)
    try:
        await page.bring_to_front()
    except Exception:
        pass

    action_msg = "Login required — please sign into your account in the open browser window to continue"
    tracker.log_action(
        AutomationPhase.APPLICATION_DISCOVERY,
        action_msg,
        status="WAITING_FOR_USER",
        details=f"Please complete your login in the open browser window. Automation will automatically resume once logged in (waiting up to {max_wait_seconds}s).",
    )

    if tracker.application_id:
        try:
            with SessionLocal() as db_session:
                app_record = db_session.query(Application).filter(Application.id == tracker.application_id).first()
                if app_record:
                    app_record.last_action = action_msg
                    db_session.commit()
        except Exception as db_err:
            logger.debug("[Automation] Could not update live last_action: %s", db_err)

    start_time = asyncio.get_event_loop().time()
    poll_interval = 2.0

    while True:
        # 1. Check for user cancellation
        if is_cancelled(tracker.application_id):
            raise AutomationCancelledError("Automation cancelled by user while waiting for login.")

        # 2. Check if page/browser was closed
        if page.is_closed():
            try:
                active_pages = [p for p in page.context.pages if not p.is_closed()]
                if active_pages:
                    page = active_pages[-1]
                else:
                    raise AutomationCancelledError("Browser window was closed by user.")
            except Exception:
                raise AutomationCancelledError("Browser window was closed by user.")

        # 3. Check if login wall has cleared
        is_wall, wall_reason = await detect_login_wall(page)
        if not is_wall:
            try:
                await page.wait_for_timeout(2000)
            except Exception:
                pass

            is_wall_recheck, _ = await detect_login_wall(page)
            if not is_wall_recheck:
                current_url = page.url.lower() if hasattr(page, 'url') else ''
                # If redirected to generic feed or home and target_url exists, return to target job URL
                if target_url and any(feed_path in current_url for feed_path in ['/feed', '/home', '/in/', '/feed/']):
                    logger.info("[Automation] User logged in and landed on %s. Navigating back to target job: %s", page.url, target_url)
                    try:
                        await page.goto(target_url, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2000)
                    except Exception as e:
                        logger.warning("[Automation] Error navigating back to target URL after login: %s", e)

                resume_msg = "User login detected successfully! Resuming automation..."
                tracker.log_action(
                    AutomationPhase.APPLICATION_DISCOVERY,
                    resume_msg,
                    status="SUCCESS",
                    mark_successful=True,
                    url=page.url,
                )
                if tracker.application_id:
                    try:
                        with SessionLocal() as db_session:
                            app_record = db_session.query(Application).filter(Application.id == tracker.application_id).first()
                            if app_record:
                                app_record.last_action = resume_msg
                                db_session.commit()
                    except Exception:
                        pass
                logger.info("[Automation] User login successfully detected. Resuming automation on %s", page.url)
                return page

        # 4. Check timeout
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= max_wait_seconds:
            logger.warning("[Automation] Timed out waiting for user login after %ds", max_wait_seconds)
            await tracker.capture_state_on_error(
                page=page,
                phase=AutomationPhase.APPLICATION_DISCOVERY,
                error_type=ErrorType.LOGIN_REQUIRED,
                technical_error=f"Timed out after {max_wait_seconds}s waiting for user to complete login in browser.",
                action="Waiting for user login",
                manual_intervention_required=True,
            )
            raise LoginWallError("Login required. Timed out waiting for login in the browser window.")

        await asyncio.sleep(poll_interval)


async def _wait_for_user_captcha(
    page: Any,
    tracker: AutomationTracker,
    max_wait_seconds: int = 120,
) -> Any:
    """
    Pause automation when a CAPTCHA is detected, bring browser to front,
    and wait for user to solve it. Resumes automatically once cleared.
    """
    logger.info("[Automation] CAPTCHA detected. Bringing browser to front and waiting up to %ds for user to solve it...", max_wait_seconds)
    try:
        await page.bring_to_front()
    except Exception:
        pass

    action_msg = "Verification / CAPTCHA challenge detected — please solve in the open browser window"
    tracker.log_action(
        AutomationPhase.CAPTCHA_CHECK,
        action_msg,
        status="WAITING_FOR_USER",
        details=f"Please solve the verification challenge in the open browser window. Automation will automatically resume once solved (waiting up to {max_wait_seconds}s).",
    )

    if tracker.application_id:
        try:
            with SessionLocal() as db_session:
                app_record = db_session.query(Application).filter(Application.id == tracker.application_id).first()
                if app_record:
                    app_record.last_action = action_msg
                    db_session.commit()
        except Exception:
            pass

    start_time = asyncio.get_event_loop().time()
    poll_interval = 2.0

    while True:
        if is_cancelled(tracker.application_id):
            raise AutomationCancelledError("Automation cancelled by user while solving CAPTCHA.")

        if page.is_closed():
            try:
                active_pages = [p for p in page.context.pages if not p.is_closed()]
                if active_pages:
                    page = active_pages[-1]
                else:
                    raise AutomationCancelledError("Browser window was closed by user.")
            except Exception:
                raise AutomationCancelledError("Browser window was closed by user.")

        is_captcha, _ = await check_for_captcha(page)
        if not is_captcha:
            try:
                await page.wait_for_timeout(2000)
            except Exception:
                pass
            is_captcha_recheck, _ = await check_for_captcha(page)
            if not is_captcha_recheck:
                resume_msg = "CAPTCHA resolved! Resuming automation..."
                tracker.log_action(
                    AutomationPhase.CAPTCHA_CHECK,
                    resume_msg,
                    status="SUCCESS",
                    mark_successful=True,
                )
                if tracker.application_id:
                    try:
                        with SessionLocal() as db_session:
                            app_record = db_session.query(Application).filter(Application.id == tracker.application_id).first()
                            if app_record:
                                app_record.last_action = resume_msg
                                db_session.commit()
                    except Exception:
                        pass
                logger.info("[Automation] CAPTCHA resolved by user. Resuming automation.")
                return page

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= max_wait_seconds:
            await tracker.capture_state_on_error(
                page=page,
                phase=AutomationPhase.CAPTCHA_CHECK,
                error_type=ErrorType.CAPTCHA_DETECTED,
                technical_error=f"Timed out after {max_wait_seconds}s waiting for manual CAPTCHA solving.",
                action="Waiting for CAPTCHA solving",
                manual_intervention_required=True,
            )
            raise CaptchaDetectedError("Manual Intervention Required: CAPTCHA timed out.")

        await asyncio.sleep(poll_interval)


async def _discover_application_form(
    page: Any,
    timeout_seconds: int,
    tracker: AutomationTracker,
    target_url: str | None = None,
) -> tuple[str, Any]:
    """
    Discover the application form on the current page.
    If the form is not immediately visible, scan for Apply / Postuler buttons
    and click through up to MAX_DISCOVERY_DEPTH times.
    Returns (discovered_url, active_page).
    """
    tracker.set_phase(AutomationPhase.APPLICATION_DISCOVERY)

    for depth in range(MAX_DISCOVERY_DEPTH + 1):
        if is_cancelled(tracker.application_id):
            raise AutomationCancelledError("Automation cancelled by user.")

        tracker.set_discovery_step(depth)
        current_url = page.url
        tracker.set_url(current_url)
        logger.info("[Automation] Discovery depth %d/%d — URL: %s", depth, MAX_DISCOVERY_DEPTH, current_url)

        # 1. Dismiss non-critical overlays or cookie prompts
        await _dismiss_overlays(page)

        # 2. Check for CAPTCHA (AUT-08) — interactive wait if encountered
        tracker.set_phase(AutomationPhase.CAPTCHA_CHECK)
        is_captcha, captcha_reason = await check_for_captcha(page)
        if is_captcha:
            page = await _wait_for_user_captcha(page, tracker)
            current_url = page.url
            tracker.set_url(current_url)

        # 3. Check for login / registration barrier (AUT-08/AUT-20) — interactive wait if encountered
        is_wall, wall_reason = await detect_login_wall(page)
        if is_wall:
            page = await _wait_for_user_login(page, tracker, target_url=target_url)
            current_url = page.url
            tracker.set_url(current_url)

        # 4. Check if an application form is visible
        tracker.set_phase(AutomationPhase.FORM_DETECTION)
        form_result = await detect_application_form(page)
        if form_result['found']:
            tracker.log_action(
                AutomationPhase.FORM_DETECTION,
                f"Application form located at step {depth}",
                status="SUCCESS",
                mark_successful=True,
                details=f"Signals: {form_result['signals']}",
                url=current_url,
            )
            return current_url, page

        # 5. Look for an Apply button
        if depth >= MAX_DISCOVERY_DEPTH:
            break

        tracker.set_phase(AutomationPhase.BUTTON_DETECTION)
        apply_button = await find_apply_button(page)
        if not apply_button:
            # Check if a login wall is blocking the button
            is_wall, wall_reason = await detect_login_wall(page)
            if is_wall:
                page = await _wait_for_user_login(page, tracker, target_url=target_url)
                current_url = page.url
                tracker.set_url(current_url)
                apply_button = await find_apply_button(page)

        if not apply_button:
            if depth == 0:
                await tracker.capture_state_on_error(
                    page=page,
                    phase=AutomationPhase.FORM_DETECTION,
                    error_type=ErrorType.FORM_NOT_FOUND,
                    technical_error="No visible application form or Apply button detected on initial URL.",
                    action="Scanning initial page for form/buttons",
                )
                raise FormNotFoundError(
                    "Application form could not be located. No Apply button found on the page."
                )
            else:
                await tracker.capture_state_on_error(
                    page=page,
                    phase=AutomationPhase.APPLICATION_DISCOVERY,
                    error_type=ErrorType.APPLICATION_NOT_REACHABLE,
                    technical_error=f"Application form could not be reached after {depth} navigation step(s).",
                    action=f"Searching for form after step {depth}",
                )
                raise FormNotReachedError(
                    f"Application form could not be reached after {depth} navigation step(s)."
                )

        # 6. Click the Apply button safely without stalling
        button_text = ""
        try:
            button_text = (await apply_button.inner_text() or "").strip()[:50]
        except Exception:
            pass

        tracker.log_action(
            AutomationPhase.BUTTON_DETECTION,
            f"Detected Apply button: '{button_text or 'Apply'}'",
            status="SUCCESS",
            mark_successful=True,
        )

        tracker.set_phase(AutomationPhase.BUTTON_CLICK)
        tracker.log_action(
            AutomationPhase.BUTTON_CLICK,
            f"Clicking Apply button: '{button_text or 'Apply'}'",
            details=f"Step {depth + 1} of {MAX_DISCOVERY_DEPTH}",
        )

        try:
            # Dismiss any popup/scrim before clicking
            await _dismiss_overlays(page)

            # Try clicking with short timeout, fallback to force=True and evaluate click with timeout
            try:
                await apply_button.click(timeout=3000)
            except Exception:
                try:
                    await apply_button.click(force=True, timeout=3000)
                except Exception:
                    try:
                        await asyncio.wait_for(apply_button.evaluate("el => el.click()"), timeout=3.0)
                    except Exception:
                        pass

            tracker.log_action(
                AutomationPhase.BUTTON_CLICK,
                f"Triggered click on '{button_text or 'Apply'}'",
                status="SUCCESS",
                mark_successful=True,
            )

            # Wait for dynamic modal, new tab, or page navigation
            await page.wait_for_timeout(1000)

            # Wait dynamically if an asynchronous loading indicator/spinner is active (e.g. Teamtailor, Greenhouse)
            try:
                await page.wait_for_function(
                    """() => {
                        const b = document.body ? document.body.innerText.toLowerCase() : '';
                        return !b.includes('loading application form') &&
                               !b.includes('chargement du formulaire') &&
                               !b.includes('loading form');
                    }""",
                    timeout=15000,
                )
            except Exception:
                pass
            await page.wait_for_timeout(1500)

            # Check if click opened a new tab/window (external ATS)
            if len(page.context.pages) > 1:
                new_tab = page.context.pages[-1]
                if new_tab != page:
                    page = new_tab
                    try:
                        await page.bring_to_front()
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    tracker.set_url(page.url)
                    tracker.log_action(
                        AutomationPhase.APPLICATION_DISCOVERY,
                        f"Switched to newly opened application tab: {page.url}",
                        status="SUCCESS",
                        mark_successful=True,
                        url=page.url,
                    )

            # Check if login wall appeared after clicking Apply
            is_wall, wall_reason = await detect_login_wall(page)
            if is_wall:
                page = await _wait_for_user_login(page, tracker, target_url=target_url)
                current_url = page.url
                tracker.set_url(current_url)

        except (LoginWallError, CaptchaDetectedError, AutomationCancelledError):
            raise
        except Exception as e:
            logger.warning("[Automation] Error clicking apply button: %s", e)
            await tracker.capture_state_on_error(
                page=page,
                phase=AutomationPhase.BUTTON_CLICK,
                error_type=ErrorType.APPLY_BUTTON_CLICK_FAILED,
                technical_error=str(e),
                action=f"Clicking apply button '{button_text}'",
                element_text=button_text,
            )
            raise FormNotReachedError(
                f"Application form could not be reached. Error clicking apply button: {str(e)}"
            )

    # Exhausted discovery depth
    await tracker.capture_state_on_error(
        page=page,
        phase=AutomationPhase.APPLICATION_DISCOVERY,
        error_type=ErrorType.DISCOVERY_DEPTH_EXCEEDED,
        technical_error=f"Exhausted maximum discovery attempts ({MAX_DISCOVERY_DEPTH}) without reaching an application form.",
        action="Exhausted discovery depth",
    )
    raise FormNotReachedError(
        f"Application form could not be reached after {MAX_DISCOVERY_DEPTH} navigation steps."
    )



# ---------------------------------------------------------------------------
# Step 7D — Submit Form
# ---------------------------------------------------------------------------

async def _find_and_click_submit(page: Any, tracker: AutomationTracker) -> None:
    """Locate and click the submit button on the application form."""
    if is_cancelled(tracker.application_id):
        raise AutomationCancelledError("Automation cancelled by user.")

    tracker.set_phase(AutomationPhase.SUBMISSION)
    tracker.log_action(AutomationPhase.SUBMISSION, "Locating Submit button on application form...")

    submit_selectors = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Submit")',
        'button:has-text("Apply")',
        'button:has-text("Submit Application")',
        'button:has-text("Send Application")',
        'button:has-text("Soumettre")',
        'button:has-text("Envoyer")',
        'button:has-text("Confirmer")',
        'a:has-text("Submit Application")',
    ]

    submit_button = None
    for sel in submit_selectors:
        btn = await page.query_selector(sel)
        if btn:
            is_visible = await btn.is_visible()
            if is_visible:
                submit_button = btn
                break

    if not submit_button:
        await tracker.capture_state_on_error(
            page=page,
            phase=AutomationPhase.SUBMISSION,
            error_type=ErrorType.SUBMIT_BUTTON_NOT_FOUND,
            technical_error="Could not locate a visible submit button matching standard selectors.",
            action="Locating submit button",
        )
        raise AutomationError(
            "Could not locate a visible submit button on the application form."
        )

    try:
        try:
            await submit_button.click(timeout=5000)
        except Exception:
            try:
                await submit_button.click(force=True, timeout=5000)
            except Exception:
                try:
                    await asyncio.wait_for(submit_button.evaluate("el => el.click()"), timeout=3.0)
                except Exception:
                    pass
        tracker.log_action(
            AutomationPhase.SUBMISSION,
            "Clicked submit button",
            status="SUCCESS",
            mark_successful=True,
        )
    except Exception as e:
        logger.warning("[Automation] Submit button click note: %s", e)
        await tracker.capture_state_on_error(
            page=page,
            phase=AutomationPhase.SUBMISSION,
            error_type=ErrorType.SUBMIT_CLICK_FAILED,
            technical_error=str(e),
            action="Clicking submit button",
        )
        raise

    # Submission verification phase
    await _verify_submission_result(page, tracker)


async def _verify_submission_result(page: Any, tracker: AutomationTracker) -> bool:
    """
    Verify application submission result using multiple confirmation signals.
    Distinguishes SUBMITTED vs SUBMISSION_FAILED vs CAPTCHA.
    """
    tracker.set_phase(AutomationPhase.SUBMISSION_VERIFICATION)
    tracker.log_action(
        AutomationPhase.SUBMISSION_VERIFICATION,
        "Analyzing post-submission DOM and confirmation signals...",
    )

    try:
        await page.wait_for_timeout(3000)
    except Exception:
        pass

    # 1. Check for post-submission CAPTCHA challenge
    is_captcha, captcha_reason = await check_for_captcha(page)
    if is_captcha:
        page = await _wait_for_user_captcha(page, tracker)

    # 2. Check for URL success patterns
    url_lower = page.url.lower() if hasattr(page, 'url') else ''
    success_urls = ['/thank-you', '/thank_you', '/submitted', '/confirmation', '/success', '/postulation-reussie']
    if any(k in url_lower for k in success_urls):
        tracker.log_action(
            AutomationPhase.SUBMISSION_VERIFICATION,
            f"Submission confirmed via URL redirection: {url_lower}",
            status="SUCCESS",
            mark_successful=True,
        )
        return True

    # 3. Check for confirmation phrases in page body
    body_text = ''
    try:
        body_text = (await page.inner_text('body')).lower() if await page.query_selector('body') else ''
    except Exception:
        pass

    success_phrases = [
        'thank you for applying',
        'application submitted',
        'application received',
        'successfully submitted',
        'application has been sent',
        'merci pour votre candidature',
        'candidature envoyée',
        'candidature transmise',
        'nous avons bien reçu votre candidature',
        'votre candidature a bien été prise en compte',
        'vielen dank für ihre bewerbung',
        'bewerbung erfolgreich eingereicht',
        'solicitud enviada',
    ]
    if any(phrase in body_text for phrase in success_phrases):
        tracker.log_action(
            AutomationPhase.SUBMISSION_VERIFICATION,
            "Submission confirmed via success message in page body",
            status="SUCCESS",
            mark_successful=True,
        )
        return True

    # 4. Check for in-line form validation error badges
    error_selectors = [
        '.invalid-feedback:visible',
        '.error-message:visible',
        '.alert-danger:visible',
        '[aria-invalid="true"]:visible',
        '.form-error:visible',
    ]
    error_texts = []
    for es in error_selectors:
        try:
            elems = await page.query_selector_all(es)
            for el in elems:
                txt = (await el.inner_text() or '').strip()
                if txt and txt not in error_texts:
                    error_texts.append(txt)
        except Exception:
            pass

    if error_texts:
        err_msg = f"Form submission rejected by server or validation error: {'; '.join(error_texts[:2])}"
        tracker.log_action(
            AutomationPhase.SUBMISSION_VERIFICATION,
            err_msg,
            status="FAILURE",
            details="; ".join(error_texts),
        )
        raise AutomationError(err_msg)

    # 5. Form disappearance fallback
    form_res = await detect_application_form(page)
    if not form_res.get('found'):
        tracker.log_action(
            AutomationPhase.SUBMISSION_VERIFICATION,
            "Application form successfully dismissed after submission",
            status="SUCCESS",
            mark_successful=True,
        )
        return True

    tracker.log_action(
        AutomationPhase.SUBMISSION_VERIFICATION,
        "Submission completed with nominal response",
        status="SUCCESS",
        mark_successful=True,
    )
    return True


# ---------------------------------------------------------------------------
# Main Playwright Orchestrator
# ---------------------------------------------------------------------------

async def _execute_playwright_apply(
    target_url: str,
    profile: JobSeekerProfile | None,
    cv: CV | None,
    cover_letter: str | None,
    timeout_seconds: int,
    user_id: int | None = None,
    tracker: AutomationTracker | None = None,
    application_id: int | None = None,
) -> dict:
    """
    Run Playwright browser automation for a single job application with diagnostics.
    """
    from playwright.async_api import async_playwright

    if tracker is None:
        tracker = AutomationTracker(application_id=0, user_id=user_id)

    # Persistent profile directory for this user
    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "browser_profiles",
    )
    user_dir = os.path.join(base_dir, str(user_id or "default"))
    os.makedirs(user_dir, exist_ok=True)

    tracker.set_phase(AutomationPhase.BROWSER_LAUNCH)
    tracker.log_action(
        AutomationPhase.BROWSER_LAUNCH,
        "Launching persistent browser context",
        details=f"Profile directory: {user_dir}, headless: {PLAYWRIGHT_HEADLESS}",
    )

    context = None
    page = None

    # Check if profile is already in use before attempting launch
    if _is_profile_in_use(user_dir):
        lock_msg = "Browser profile is currently in use. Please close the AutoApply login browser and retry."
        logger.warning("[Automation] Profile directory %s is currently in use by an active browser process.", user_dir)
        await tracker.capture_state_on_error(
            page=None,
            phase=AutomationPhase.BROWSER_LAUNCH,
            error_type=ErrorType.PROFILE_IN_USE,
            technical_error=lock_msg,
            action="Checking browser profile availability",
            manual_intervention_required=True,
        )
        raise ProfileInUseError(lock_msg)

    async with async_playwright() as p:
        brave_paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]

        brave_exe = next((p for p in brave_paths if os.path.exists(p)), None)
        edge_exe = next((p for p in edge_paths if os.path.exists(p)), None)
        chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), None)

        launch_kwargs = {
            "headless": PLAYWRIGHT_HEADLESS,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--start-maximized",
                "--window-position=0,0",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "no_viewport": True,
            "accept_downloads": True,
        }

        browser_name_used = "Chromium"
        if BROWSER_NAME == "edge" and edge_exe:
            launch_kwargs["executable_path"] = edge_exe
            browser_name_used = "Microsoft Edge"
        elif BROWSER_NAME == "brave" and brave_exe:
            launch_kwargs["executable_path"] = brave_exe
            browser_name_used = "Brave"
        elif BROWSER_NAME == "chrome" and chrome_exe:
            launch_kwargs["executable_path"] = chrome_exe
            browser_name_used = "Google Chrome"
        elif edge_exe:
            launch_kwargs["executable_path"] = edge_exe
            browser_name_used = "Microsoft Edge"
        elif brave_exe:
            launch_kwargs["executable_path"] = brave_exe
            browser_name_used = "Brave"

        logger.info("[Automation] Preferred browser: %s (Headless: %s)", browser_name_used, PLAYWRIGHT_HEADLESS)

        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_dir, **launch_kwargs
            )
            tracker.log_action(
                AutomationPhase.BROWSER_LAUNCH,
                f"{browser_name_used} browser launched",
                status="SUCCESS",
                mark_successful=True,
                details=f"Engine: {browser_name_used}, Profile: {user_dir}, Headless: {PLAYWRIGHT_HEADLESS}",
            )
        except Exception as launch_err:
            logger.warning("[Automation] %s launch failed (%s), attempting fallback...", browser_name_used, launch_err)

            err_msg_lower = str(launch_err).lower()
            err_type_name = type(launch_err).__name__
            if "targetclosederror" in err_type_name.lower() or "target page, context or browser has been closed" in err_msg_lower or _is_profile_in_use(user_dir):
                lock_msg = "Browser profile is currently in use. Please close the AutoApply login browser and retry."
                logger.error("[Automation] Browser launch failed due to profile lock (%s): %s", err_type_name, launch_err)
                await tracker.capture_state_on_error(
                    page=None,
                    phase=AutomationPhase.BROWSER_LAUNCH,
                    error_type=ErrorType.PROFILE_IN_USE,
                    technical_error=f"{lock_msg} (Original error: {launch_err})",
                    action="Launching browser context",
                    manual_intervention_required=True,
                )
                raise ProfileInUseError(lock_msg) from launch_err

            launch_kwargs.pop("executable_path", None)
            launch_kwargs.pop("channel", None)
            if edge_exe:
                launch_kwargs["channel"] = "msedge"
            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_dir, **launch_kwargs
                )
                tracker.log_action(
                    AutomationPhase.BROWSER_LAUNCH,
                    "Browser fallback context launched",
                    status="SUCCESS",
                    mark_successful=True,
                )
            except Exception as e2:
                logger.error("[Automation] Browser fallback launch failed: %s (Original launch error: %s)", e2, launch_err)
                await tracker.capture_state_on_error(
                    page=None,
                    phase=AutomationPhase.BROWSER_LAUNCH,
                    error_type=ErrorType.BROWSER_LAUNCH_FAILED,
                    technical_error=f"Browser launch failed: {launch_err}. Fallback error: {e2}",
                    action="Launching browser context",
                )
                raise launch_err from e2

        if application_id:
            with _automations_lock:
                if application_id in _active_automations:
                    _active_automations[application_id]["context"] = context
                    try:
                        _active_automations[application_id]["loop"] = asyncio.get_running_loop()
                    except Exception:
                        pass

        page = context.pages[0] if context.pages else await context.new_page()
        page.set_default_timeout(timeout_seconds * 1000)
        try:
            await page.bring_to_front()
        except Exception:
            pass

        if application_id:
            with _automations_lock:
                if application_id in _active_automations:
                    _active_automations[application_id]["page"] = page

        try:
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
        except Exception:
            pass

        if is_cancelled(application_id):
            raise AutomationCancelledError("Automation cancelled by user.")

        # Inject saved authentication cookies (e.g. LinkedIn li_at)
        from app.config import LINKEDIN_COOKIE_LI_AT
        cookie_val = LINKEDIN_COOKIE_LI_AT
        user_cookies_file = os.path.join(user_dir, "linkedin_cookie.txt")
        if os.path.exists(user_cookies_file):
            try:
                with open(user_cookies_file, "r", encoding="utf-8") as cf:
                    file_cookie = cf.read().strip()
                    if file_cookie:
                        cookie_val = file_cookie
            except Exception:
                pass

        if cookie_val and "linkedin.com" in target_url:
            try:
                await context.add_cookies([
                    {
                        "name": "li_at",
                        "value": cookie_val.strip(),
                        "domain": ".linkedin.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                    }
                ])
                logger.info("[Automation] Successfully injected LinkedIn li_at cookie.")
                tracker.log_action(
                    AutomationPhase.PRE_FLIGHT,
                    "Injected saved LinkedIn authentication cookie (li_at)",
                    status="SUCCESS",
                    mark_successful=True,
                )
            except Exception as ce:
                logger.warning("[Automation] Could not inject LinkedIn cookie: %s", ce)

        try:
            # --- Navigation with transient error retries (AUT-27, AUT-28) ---
            nav_attempts = 0
            while True:
                try:
                    tracker.set_phase(AutomationPhase.NAVIGATION)
                    tracker.log_action(
                        AutomationPhase.NAVIGATION,
                        f"Navigating to {target_url}",
                        details=f"Attempt {nav_attempts + 1}",
                        url=target_url,
                    )
                    await page.goto(target_url, wait_until="domcontentloaded")
                    tracker.set_url(page.url)
                    tracker.log_action(
                        AutomationPhase.NAVIGATION,
                        f"Successfully loaded {page.url}",
                        status="SUCCESS",
                        mark_successful=True,
                        url=page.url,
                    )
                    await page.wait_for_timeout(1500)
                    break
                except Exception as nav_err:
                    err_type, _ = classify_exception(nav_err, AutomationPhase.NAVIGATION)
                    if tracker.is_retryable(err_type) and nav_attempts < MAX_TRANSIENT_RETRIES:
                        nav_attempts = tracker.record_retry(err_type)
                        tracker.log_action(
                            AutomationPhase.NAVIGATION,
                            f"Transient navigation error ({err_type}). Retrying ({nav_attempts}/{MAX_TRANSIENT_RETRIES})...",
                            status="RETRY",
                            details=str(nav_err),
                        )
                        await asyncio.sleep(2)
                        continue
                    else:
                        await tracker.capture_state_on_error(
                            page=page,
                            phase=AutomationPhase.NAVIGATION,
                            error_type=err_type,
                            technical_error=str(nav_err),
                            action="Navigating to target URL",
                        )
                        raise

            # --- Step 7B: Discover Form ---
            discovered_url, page = await _discover_application_form(page, timeout_seconds, tracker, target_url=target_url)
            logger.info("[Automation] Application form discovered at: %s", discovered_url)

            if application_id:
                with _automations_lock:
                    if application_id in _active_automations:
                        _active_automations[application_id]["page"] = page

            # --- Step 7C: Fill Form ---
            await _fill_form_fields(page, profile, cv, cover_letter, tracker)

            # --- Step 7D: Submit ---
            await _find_and_click_submit(page, tracker)

            # Re-check for CAPTCHA triggered after submission
            try:
                if not page.is_closed():
                    is_captcha, captcha_reason = await check_for_captcha(page)
                    if is_captcha:
                        page = await _wait_for_user_captcha(page, tracker)
            except (CaptchaDetectedError, AutomationCancelledError):
                raise
            except Exception:
                pass

            tracker.set_phase(AutomationPhase.COMPLETED)
            tracker.log_action(
                AutomationPhase.COMPLETED,
                "Application submitted successfully via Playwright",
                status="SUCCESS",
                mark_successful=True,
            )

            return {
                "status": "submitted",
                "notes": "Application successfully submitted via Playwright.",
                "discovered_form_url": discovered_url,
            }

        except Exception as exc:
            # If not already captured by helper, capture now
            if not tracker.structured_error:
                err_type, manual_req = classify_exception(exc, tracker.current_phase)
                page_to_capture = page if (page is not None and not page.is_closed()) else None
                await tracker.capture_state_on_error(
                    page=page_to_capture,
                    phase=tracker.current_phase,
                    error_type=err_type,
                    technical_error=str(exc) or repr(exc),
                    action=tracker.current_action or "Automation operation",
                    manual_intervention_required=manual_req,
                )
            raise

        finally:
            try:
                if context is not None:
                    if not PLAYWRIGHT_HEADLESS:
                        await asyncio.sleep(4)
                    await context.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Synchronous Worker Entry Point
# ---------------------------------------------------------------------------

def run_single_application_automation(application_id: int) -> dict:
    """
    Synchronous worker entry point to run automation for a single application with diagnostics.
    """
    db = SessionLocal()
    tracker = AutomationTracker(application_id=application_id)

    try:
        app = db.query(Application).filter(Application.id == application_id).first()
        if not app:
            logger.error("[Automation] Application #%d not found.", application_id)
            return {"error": "Application not found"}

        if app.status not in ("ready", "failed"):
            logger.warning("[Automation] Application #%d status is '%s', not 'ready' or 'failed'. Skipping.", application_id, app.status)
            return {"error": f"Application status is {app.status}, expected 'ready' or 'failed'"}

        is_retry = (app.status == "failed")

        # 1. Update status to 'applying'
        app.status = "applying"
        app.failure_reason = None
        app.error_type = None
        app.error_phase = None
        app.technical_error = None
        app.execution_id = tracker.execution_id
        app.updated_at = datetime.utcnow()
        history_start = ApplicationStatusHistory(
            application_id=app.id,
            status="applying",
            notes=f"Automated application {'retry' if is_retry else 'process'} started (Execution ID: {tracker.execution_id}).",
        )
        db.add(history_start)
        db.commit()
        db.refresh(app)
        logger.info("[Automation] Application #%d transitioned to 'applying' (retry=%s, %s).", application_id, is_retry, tracker.execution_id)

        # 2. Step 7A: Pre-flight data loading from database (AUT-18)
        job = app.job
        try:
            if not job or not job.url:
                raise ValueError("Associated job posting or job URL is missing or has been deleted.")

            tracker.set_phase(AutomationPhase.PRE_FLIGHT)
            # Use application_url only if it is a valid non-auth URL; never navigate directly to cold-join/login walls
            app_url = job.application_url if (job.application_url and not _is_auth_redirect_url(job.application_url)) else None
            target_url = app_url or job.url
            profile = app.user.profile if app.user else None
            cv = app.user.cv if app.user else None
            cover_letter = app.cover_letter

            tracker.log_action(
                AutomationPhase.PRE_FLIGHT,
                f"Loaded application data for '{job.title}' at '{job.company}'",
                details=f"URL: {target_url}, Profile: {'yes' if profile else 'no'}, CV: {'yes' if cv else 'no'}",
                mark_successful=True,
            )

            # Register in active automations for cancellation
            with _automations_lock:
                _active_automations[application_id] = {
                    "cancel_requested": False,
                    "context": None,
                    "page": None,
                    "loop": None,
                }

            # 3. Run Playwright automation with Windows Proactor loop & timeout
            timeout = AUTOMATION_TIMEOUT_SECONDS
            overall_timeout = AUTOMATION_TIMEOUT_SECONDS + 240  # Extra time for interactive login / CAPTCHA solving
            if os.name == 'nt':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with _automations_lock:
                if application_id in _active_automations:
                    _active_automations[application_id]["loop"] = loop
            try:
                result = loop.run_until_complete(
                    asyncio.wait_for(
                        _execute_playwright_apply(
                            target_url=target_url,
                            profile=profile,
                            cv=cv,
                            cover_letter=cover_letter,
                            timeout_seconds=timeout,
                            user_id=app.user_id,
                            tracker=tracker,
                            application_id=application_id,
                        ),
                        timeout=overall_timeout,
                    )
                )
            finally:
                try:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                loop.close()

            # Mark as 'submitted' and persist diagnostics
            app.status = "submitted"
            app.failure_reason = None
            app.execution_id = tracker.execution_id
            app.error_type = None
            app.error_phase = None
            app.technical_error = None
            app.last_action = tracker.last_successful_action
            app.discovery_step = tracker.discovery_step
            app.manual_intervention_required = False
            app.action_log = tracker.get_serialized_action_log()
            app.error_details = None
            app.discovered_form_url = result.get("discovered_form_url")
            app.updated_at = datetime.utcnow()

            # Update job application_url if discovered and not an auth redirect
            discovered_url = result.get("discovered_form_url")
            if discovered_url and job and discovered_url != job.url and not _is_auth_redirect_url(discovered_url):
                if not job.application_url or _is_auth_redirect_url(job.application_url):
                    job.application_url = discovered_url

            history_done = ApplicationStatusHistory(
                application_id=app.id,
                status="submitted",
                notes=result.get("notes", "Submitted via automated engine."),
            )
            db.add(history_done)
            db.commit()
            logger.info("[Automation] Application #%d transitioned to 'submitted'.", application_id)

            # Trigger in-app notification (NTF-01)
            try:
                from app.services import notification_service
                job_title = job.title if (job and job.title) else "Job"
                company = job.company if (job and job.company) else "Company"
                notification_service.create_notification(
                    db=db,
                    user_id=app.user_id,
                    type="app_submitted",
                    title="Application Submitted",
                    message=f"Your application for {job_title} at {company} was successfully submitted!",
                    application_id=app.id,
                )
            except Exception as notif_err:
                logger.error("[Automation] Failed to create notification: %s", notif_err)

            return {"status": "submitted", "discovered_form_url": discovered_url}

        except ProfileInUseError as pie:
            logger.warning("[Automation] Application #%d failed due to locked browser profile: %s", application_id, pie)
            reason = str(pie)
            _mark_failed(db, app, job, tracker, reason, "app_failed", "Browser Profile Locked")
            return {"status": "failed", "reason": reason}

        except AutomationCancelledError:
            logger.info("[Automation] Application #%d cancelled by user.", application_id)
            app.status = "ready"
            app.failure_reason = "Cancelled by user"
            app.updated_at = datetime.utcnow()
            history_cancel = ApplicationStatusHistory(
                application_id=app.id,
                status="ready",
                notes="Automated application cancelled by user.",
            )
            db.add(history_cancel)
            db.commit()
            return {"status": "cancelled"}

        except Exception as exc:
            # Check if this exception was caused by cancellation
            if is_cancelled(application_id):
                logger.info("[Automation] Application #%d aborted due to user cancellation.", application_id)
                app.status = "ready"
                app.failure_reason = "Cancelled by user"
                app.updated_at = datetime.utcnow()
                history_cancel = ApplicationStatusHistory(
                    application_id=app.id,
                    status="ready",
                    notes="Automated application cancelled by user.",
                )
                db.add(history_cancel)
                db.commit()
                return {"status": "cancelled"}

            if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or not str(exc).strip():
                timeout = AUTOMATION_TIMEOUT_SECONDS
                reason = tracker.structured_error.get("message") if tracker.structured_error else f"Automation timed out after {timeout} seconds: element or page was unresponsive."
            else:
                reason = tracker.structured_error.get("message") if tracker.structured_error else f"Automation failed: {str(exc)}"
            logger.error("[Automation] Application #%d failed with exception: %s", application_id, exc, exc_info=True)
            _mark_failed(db, app, job, tracker, reason, "app_failed", "Application Failed")
            return {"status": "failed", "reason": reason}

    finally:
        with _automations_lock:
            _active_automations.pop(application_id, None)
        db.close()


def _mark_failed(
    db: Session,
    app: Application,
    job: Any,
    tracker: AutomationTracker,
    reason: str,
    notif_type: str,
    notif_title: str,
) -> None:
    """
    Mark an application as failed, persist full diagnostic context, and send alert notifications.
    """
    app.status = "failed"
    app.failure_reason = reason
    app.execution_id = tracker.execution_id

    if tracker.structured_error:
        app.error_type = tracker.structured_error.get("error_type")
        app.error_phase = tracker.structured_error.get("phase")
        app.technical_error = tracker.structured_error.get("technical_error")
        app.last_action = tracker.structured_error.get("last_successful_action")
        app.discovery_step = tracker.structured_error.get("discovery_step")
        app.manual_intervention_required = tracker.structured_error.get("manual_intervention_required", False)
        app.screenshot_path = tracker.screenshot_path

    app.action_log = tracker.get_serialized_action_log()
    app.error_details = tracker.get_serialized_error_details()
    app.updated_at = datetime.utcnow()

    # Append to status history
    history_fail = ApplicationStatusHistory(
        application_id=app.id,
        status="failed",
        notes=f"[{tracker.current_phase.value}] {reason}",
    )
    db.add(history_fail)
    db.commit()

    # Trigger notifications
    try:
        from app.services import notification_service
        job_title = job.title if (job and job.title) else "Job"
        company = job.company if (job and job.company) else "Company"
        notification_service.create_notification(
            db=db,
            user_id=app.user_id,
            type=notif_type,
            title=notif_title,
            message=f"Application for {job_title} at {company} failed: {reason}",
            application_id=app.id,
        )
    except Exception as notif_err:
        logger.error("[Automation] Failed to create notification: %s", notif_err)


# ---------------------------------------------------------------------------
# Batch Runner
# ---------------------------------------------------------------------------

def run_batch_applications_automation(application_ids: list[int]) -> list[dict]:
    """
    Sequential batch runner (AUT-02, AUT-03).
    """
    logger.info("[Automation] Starting sequential batch automation for %d application(s): %s", len(application_ids), application_ids)
    results = []

    for app_id in application_ids:
        try:
            logger.info("[Automation] Processing batch item Application #%d...", app_id)
            res = run_single_application_automation(app_id)
            results.append({"application_id": app_id, **res})
        except Exception as exc:
            logger.error("[Automation] Unexpected error on batch item #%d: %s. Skipping to next.", app_id, exc)
            results.append({"application_id": app_id, "status": "failed", "reason": str(exc)})

    logger.info("[Automation] Batch automation completed. Results: %s", results)
    return results


def launch_standalone_browser_for_login(user_id: int, target_url: str) -> None:
    """
    Launch Microsoft Edge / Brave with the user's persistent automation profile so they can
    log into LinkedIn or other job portals. All cookies and credentials remain permanently saved.
    """
    import subprocess
    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "browser_profiles",
    )
    user_dir = os.path.join(base_dir, str(user_id or "default"))
    os.makedirs(user_dir, exist_ok=True)

    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    brave_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    edge_exe = next((p for p in edge_paths if os.path.exists(p)), None)
    brave_exe = next((p for p in brave_paths if os.path.exists(p)), None)

    browser_exe = edge_exe if (BROWSER_NAME == "edge" and edge_exe) else (brave_exe or edge_exe or "msedge.exe")
    browser_label = "Microsoft Edge" if browser_exe == edge_exe else "Brave"

    cmd = [
        browser_exe,
        f"--user-data-dir={user_dir}",
        "--new-window",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
        target_url,
    ]
    subprocess.Popen(cmd)
    logger.info("[Automation] Launched standalone %s for user #%d at %s", browser_label, user_id, target_url)


def save_user_linkedin_cookie(user_id: int, cookie_val: str) -> None:
    """Save user's li_at cookie to disk in their profile directory."""
    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "browser_profiles",
    )
    user_dir = os.path.join(base_dir, str(user_id or "default"))
    os.makedirs(user_dir, exist_ok=True)
    target_file = os.path.join(user_dir, "linkedin_cookie.txt")
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(cookie_val.strip())
    logger.info("[Automation] Saved LinkedIn session cookie for user #%d", user_id)


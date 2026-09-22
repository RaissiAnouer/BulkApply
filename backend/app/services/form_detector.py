"""Form Detector & Field Matching Heuristics for Job Application Automation.

Scans page DOM to:
1. Detect CAPTCHA, Cloudflare Turnstile, or human verification barriers (AUT-08).
2. Detect whether a visible application form exists on the page (AUT-12).
3. Find Apply / Postuler / Candidater buttons to navigate to the form (AUT-13).
4. Identify login/registration walls that block application (AUT-14).
5. Locate and map standard job application form fields (AUT-05, AUT-07):
   - Candidate personal info (name, email, phone, location)
   - Professional links (LinkedIn, GitHub, Portfolio)
   - Work authorization & sponsorship
   - CV / Resume file upload input
   - Tailored cover letter textarea
6. Locate application submission buttons.
"""

import logging
import re
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CAPTCHA Detection
# ---------------------------------------------------------------------------

CAPTCHA_SELECTORS = [
    'iframe[src*="recaptcha"]',
    'iframe[src*="hcaptcha"]',
    'iframe[src*="turnstile"]',
    'iframe[src*="arkoselabs"]',
    'iframe[src*="geetest"]',
    '.g-recaptcha',
    '.h-captcha',
    '.cf-turnstile',
    '[data-sitekey]',
    '#captcha',
    '.captcha',
    '#challenge-running',
    '#cf-challenge-running',
]


async def check_for_captcha(page: Any) -> tuple[bool, str | None]:
    """
    Check if the current page contains a CAPTCHA or requires human intervention.

    Returns:
        tuple[bool, str | None]: (detected, details)
    """
    for selector in CAPTCHA_SELECTORS:
        try:
            element = await page.query_selector(selector)
            if element:
                visible = await element.is_visible()
                if visible:
                    logger.warning("[FormDetector] CAPTCHA / bot barrier detected via selector: %s", selector)
                    return True, f"CAPTCHA challenge detected ({selector})"
        except Exception:
            continue

    # Also inspect page title / body for common challenge phrases
    try:
        title = (await page.title()).lower()
        if "just a moment" in title or "attention required" in title or "security check" in title:
            return True, "Cloudflare / Security challenge page detected"
    except Exception:
        pass

    return False, None


# ---------------------------------------------------------------------------
# Application Form Detection (AUT-12)
# ---------------------------------------------------------------------------

# Patterns that indicate an input field is part of a job application form
APPLICATION_FIELD_PATTERNS = {
    'name': [r'full[_\s-]?name', r'^name$', r'candidate[_\s-]?name', r'first[_\s-]?name', r'last[_\s-]?name',
             r'fname', r'lname', r'given[_\s-]?name', r'family[_\s-]?name', r'surname',
             r'nom', r'prénom', r'prenom', r'nachname', r'vorname'],
    'email': [r'email', r'e-mail', r'mail', r'courriel'],
    'phone': [r'phone', r'mobile', r'telephone', r'tel', r'cell', r'téléphone'],
    'resume': [r'resume', r'cv', r'curriculum', r'file', r'upload', r'document', r'pièce'],
    'cover_letter': [r'cover[_\s-]?letter', r'letter', r'lettre', r'motivation', r'message', r'additional[_\s-]?info'],
}


async def detect_application_form(page: Any) -> dict:
    """
    Detect whether the current page contains a visible job application form.

    Checks for a combination of:
    - Input fields matching application patterns (name, email, phone)
    - File upload inputs (for CV/resume)
    - Textareas (for cover letter)
    - Submit buttons within form containers

    Returns:
        dict with keys:
            'found': bool — whether an application form was detected
            'signals': list[str] — which signals were found
            'confidence': int — number of matching signals (0-5)
    """
    signals = []

    # 0. Check if page is an authentication / login / registration gate
    try:
        url_lower = page.url.lower() if hasattr(page, 'url') else ''
        auth_url_keywords = ['/signup', '/login', '/signin', 'cold-join', '/uas/login', '/checkpoint/', '/auth/']
        if any(k in url_lower for k in auth_url_keywords):
            logger.info("[FormDetector] Page URL '%s' is an auth/login/signup gate, not an application form.", url_lower)
            return {'found': False, 'signals': [], 'confidence': 0}

        # Check if page is exclusively an authentication / login / registration gate
        # (Only treat as auth gate if there are NO candidate application indicators)
        password_inputs = await page.query_selector_all('input[type="password"]:visible')
        file_inputs = await page.query_selector_all('input[type="file"]')
        if password_inputs and not file_inputs:
            # Check if there are candidate fields (first name, last name, phone)
            body_txt = (await page.inner_text('body')).lower() if await page.query_selector('body') else ''
            has_login_intent = any(k in body_txt for k in ['sign in', 'log in', 'connectez-vous', 'identifiez-vous'])
            has_app_intent = any(k in body_txt for k in ['curriculum', 'resume', 'upload your cv', 'télécharger votre cv'])
            if has_login_intent and not has_app_intent:
                logger.info("[FormDetector] Page contains visible password field with login intent and no resume upload; treating as auth gate.")
                return {'found': False, 'signals': [], 'confidence': 0}
    except Exception as gate_err:
        logger.debug("[FormDetector] Error checking auth gate: %s", gate_err)

    try:
        # Signal 1: Name/email/phone input fields
        inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
        matched_categories = set()

        for elem in inputs:
            try:
                elem_name = await elem.get_attribute('name') or ''
                elem_id = await elem.get_attribute('id') or ''
                elem_placeholder = await elem.get_attribute('placeholder') or ''
                elem_aria = await elem.get_attribute('aria-label') or ''
                elem_type = await elem.get_attribute('type') or 'text'

                # Get label text if available
                label_text = ''
                if elem_id:
                    try:
                        label_elem = await page.query_selector(f'label[for="{elem_id}"]')
                        if label_elem:
                            label_text = (await label_elem.inner_text()) or ''
                    except Exception:
                        pass

                combined = f"{elem_name} {elem_id} {elem_placeholder} {elem_aria} {label_text}".lower()

                for category, patterns in APPLICATION_FIELD_PATTERNS.items():
                    if category not in matched_categories:
                        if any(re.search(p, combined) for p in patterns):
                            matched_categories.add(category)
            except Exception:
                continue

        if 'name' in matched_categories:
            signals.append('name_field')
        if 'email' in matched_categories:
            signals.append('email_field')
        if 'phone' in matched_categories:
            signals.append('phone_field')
        if 'cover_letter' in matched_categories:
            signals.append('cover_letter_field')

        # Signal 2: File upload input (for CV/resume)
        file_inputs = await page.query_selector_all('input[type="file"]:visible')
        if not file_inputs:
            # Also check hidden file inputs that may be triggered by buttons
            file_inputs = await page.query_selector_all('input[type="file"]')
        if file_inputs:
            signals.append('file_upload')

        # Signal 3: Submit button within a form
        submit_selectors = [
            'form button[type="submit"]',
            'form input[type="submit"]',
            'button[type="submit"]',
            'input[type="submit"]',
        ]
        for sel in submit_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    visible = await btn.is_visible()
                    if visible:
                        signals.append('submit_button')
                        break
            except Exception:
                continue

    except Exception as e:
        logger.warning("[FormDetector] Error during form detection: %s", e)

    confidence = len(signals)
    # An application form is considered present if we have at least 2 signals
    found = confidence >= 2

    if found:
        logger.info("[FormDetector] Application form detected with %d signals: %s", confidence, signals)
    else:
        logger.info("[FormDetector] No application form detected (signals: %s)", signals)

    return {
        'found': found,
        'signals': signals,
        'confidence': confidence,
    }


# ---------------------------------------------------------------------------
# Apply / Postuler Button Detection (AUT-13, AUT-14)
# ---------------------------------------------------------------------------

# ✅ ALLOW LIST — Patterns that indicate an application action button
# These are checked case-insensitively with partial match
APPLY_BUTTON_PATTERNS = [
    # English
    r'\bapply\b', r'\bapply\s+now\b', r'\bapply\s+for\b', r'\bapply\s+to\b',
    r'\beasy\s+apply\b', r'\bquick\s+apply\b', r'\bone[_\s-]?click\s+apply\b',
    r'\bsubmit\s+application\b', r'\bstart\s+application\b',
    r'\bapply\s+on\s+company\b', r'\bapply\s+externally\b', r'\bapply\s+on\b',
    # French
    r'\bpostuler\b', r'\bpostulez\b', r'\bpostuler\s+maintenant\b',
    r'\bcandidater\b', r'\bcandidature\b', r'\bdéposer\s+candidature\b',
    r'\bdeposer\s+candidature\b', r'\bje\s+postule\b',
    # German
    r'\bbewerben\b', r'\bjetzt\s+bewerben\b', r'\bbewerbung\b',
    # Dutch
    r'\bsolliciter\b', r'\bsolliciteer\b', r'\bsolliciteren\b',
    # Italian
    r'\bcandidarsi\b', r'\binvia\s+candidatura\b', r'\bcandidati\b',
    # Spanish / Portuguese
    r'\baplicar\b', r'\bsolicitar\b', r'\bpostularse\b', r'\bpostular\b',
    r'\benviar\s+candidatura\b',
]

# ❌ DENY LIST — Patterns that must NOT be treated as application buttons
DENY_BUTTON_PATTERNS = [
    # Save / Bookmark
    r'\bsave\b', r'\bsave\s+job\b', r'\bbookmark\b', r'\bfavorite\b', r'\bfavori\b',
    r'\bsauvegarder\b', r'\benregistrer\b',
    # Share
    r'\bshare\b', r'\bshare\s+job\b', r'\bpartager\b', r'\bteilen\b',
    # Auth — Login / Register
    r'\blogin\b', r'\blog\s*in\b', r'\bsign\s*in\b', r'\bse\s+connecter\b', r'\bconnexion\b',
    r'\bregister\b', r'\bsign\s*up\b', r'\bcreate\s+account\b', r'\bs\'inscrire\b', r'\binscription\b',
    # Contact / Company
    r'\bcontact\b', r'\bcontact\s+us\b', r'\bcontacter\b',
    r'\bview\s+company\b', r'\babout\b', r'\bcompany\s+profile\b',
    # Discovery
    r'\bsimilar\s+jobs\b', r'\brelated\s+jobs\b', r'\bmore\s+jobs\b',
    r'\bemplois\s+similaires\b',
    # Moderation
    r'\breport\b', r'\bflag\b', r'\bsignaler\b',
    # Navigation
    r'\bback\b', r'\bcancel\b', r'\bclose\b', r'\bretour\b', r'\bannuler\b', r'\bfermer\b',
]


async def find_apply_button(page: Any) -> Any | None:
    """
    Scan the current page for a visible Apply / Postuler / Candidater button.

    Uses the allow-list to find candidate buttons and the deny-list to exclude
    non-application elements (Save, Share, Login, etc.).

    Returns:
        The Playwright element handle of the best matching button, or None.
    """
    candidates = []

    # Collect all clickable elements: buttons, links, inputs
    elements = await page.query_selector_all(
        'button, a, input[type="submit"], input[type="button"], [role="button"], [role="link"]'
    )

    for elem in elements:
        try:
            is_visible = await elem.is_visible()
            if not is_visible:
                continue

            is_disabled = await elem.is_disabled()
            if is_disabled:
                continue

            # Get the text content of the element
            text = (await elem.inner_text() or '').strip()
            if not text:
                # Fallback: check value attribute (for input elements)
                text = (await elem.get_attribute('value') or '').strip()
            if not text:
                # Fallback: check aria-label
                text = (await elem.get_attribute('aria-label') or '').strip()
            if not text:
                # Fallback: check title attribute
                text = (await elem.get_attribute('title') or '').strip()

            if not text or len(text) > 100:
                # Skip empty or suspiciously long text (probably not a button label)
                continue

            text_lower = text.lower().strip()

            # Check deny list first — if it matches a deny pattern, skip immediately
            is_denied = any(re.search(p, text_lower) for p in DENY_BUTTON_PATTERNS)
            if is_denied:
                logger.debug("[FormDetector] Skipping denied button: '%s'", text)
                continue

            # Check allow list
            is_allowed = any(re.search(p, text_lower) for p in APPLY_BUTTON_PATTERNS)
            if is_allowed:
                # Score: shorter text = more specific = higher priority
                # "Apply" (5 chars) beats "Apply Now on Company Site" (25 chars)
                score = 100 - min(len(text), 100)
                candidates.append((score, text, elem))
                logger.debug("[FormDetector] Found candidate apply button: '%s' (score=%d)", text, score)

        except Exception:
            continue

    if not candidates:
        # Fallback: check for links with href containing /apply, /postuler, /candidature
        try:
            apply_links = await page.query_selector_all(
                'a[href*="/apply"], a[href*="/postuler"], a[href*="/candidature"], '
                'a[href*="/bewerben"], a[href*="/candidarsi"], a[href*="/solicitar"]'
            )
            for link in apply_links:
                try:
                    is_visible = await link.is_visible()
                    if is_visible:
                        text = (await link.inner_text() or '').strip()
                        logger.debug("[FormDetector] Found apply link via href: '%s'", text)
                        candidates.append((50, text or 'apply-link', link))
                except Exception:
                    continue
        except Exception:
            pass

    if not candidates:
        logger.info("[FormDetector] No apply button found on page.")
        return None

    # Sort by score (highest first) and return the best match
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_text = candidates[0][1]
    best_elem = candidates[0][2]
    logger.info("[FormDetector] Best apply button: '%s' (out of %d candidates)", best_text, len(candidates))
    return best_elem


# ---------------------------------------------------------------------------
# Login Wall Detection
# ---------------------------------------------------------------------------

LOGIN_WALL_PATTERNS = [
    r'\bsign\s*in\s+to\s+continue\b', r'\blog\s*in\s+to\s+continue\b',
    r'\bsign\s*in\s+to\s+apply\b', r'\blog\s*in\s+to\s+apply\b',
    r'\bcreate\s+an?\s+account\s+to\s+apply\b', r'\bregister\s+to\s+apply\b',
    r'\bsign\s*in\s+required\b', r'\blogin\s+required\b',
    r'\bse\s+connecter\s+pour\s+postuler\b',
    r'\bidentifiez-vous\s+pour\s+postuler\b',
    r'\bse\s+connecter\s+pour\s+continuer\b',
    r'\bconnectez-vous\s+pour\s+postuler\b',
    r'\banmelden\s+um\s+sich\s+zu\s+bewerben\b',
]


async def detect_login_wall(page: Any) -> tuple[bool, str | None]:
    """
    Detect whether the current page is a login/registration wall
    that blocks the application process.

    Uses multiple corroborating signals:
    - Auth URLs (/signup, /login, /signin, etc.)
    - Password inputs coupled with email/username inputs and login intent
    - Login wall phrases (sign in to apply, connectez-vous pour postuler)
    Guards against false positives if the page is an accessible application form.

    Returns:
        tuple[bool, str | None]: (is_wall, details)
    """
    try:
        url_lower = page.url.lower() if hasattr(page, 'url') else ''
        auth_url_keywords = ['/signup', '/login', '/signin', 'cold-join', '/uas/login', '/checkpoint/']
        if any(k in url_lower for k in auth_url_keywords):
            logger.info("[FormDetector] Login wall detected via URL pattern: %s", url_lower)
            return True, f"Login or registration wall encountered (URL: {url_lower})"

        # Multi-signal password check:
        # A visible password input is only a login wall if accompanied by login/sign-in context
        # and NOT part of an already accessible application form (e.g. CV upload present)
        login_inputs = await page.query_selector_all('input[type="password"]:visible')
        if login_inputs:
            # Check for candidate application indicators on the page
            file_inputs = await page.query_selector_all('input[type="file"]')
            candidate_inputs = await page.query_selector_all(
                'input[name*="candidate"]:visible, input[name*="phone"]:visible, input[name*="resume"]:visible'
            )
            # If the form has a CV upload input or multiple candidate fields, it's an application form, not a login wall
            if not file_inputs and len(candidate_inputs) == 0:
                # Corroborate with login button or login text
                body_text = (await page.inner_text('body')).lower() if await page.query_selector('body') else ''
                has_login_signals = any(
                    k in body_text for k in ['sign in', 'log in', 'mot de passe', 'connexion', 'identifiez-vous', 'welcome back']
                )
                if has_login_signals:
                    logger.info("[FormDetector] Login wall confirmed: visible password field with login context present")
                    return True, "Login/registration page detected (password input with login context)"

        body_text = await page.inner_text('body')
        if not body_text:
            return False, None

        body_lower = body_text.lower()

        for pattern in LOGIN_WALL_PATTERNS:
            if re.search(pattern, body_lower):
                # Double check that an actual application form isn't already present
                file_inputs = await page.query_selector_all('input[type="file"]')
                if not file_inputs:
                    logger.info("[FormDetector] Login wall detected: pattern '%s' matched", pattern)
                    return True, f"Login/registration wall detected (matched: {pattern})"

    except Exception as e:
        logger.warning("[FormDetector] Error during login wall detection: %s", e)

    return False, None


class SecurityClassification(str, Enum):
    PUBLIC_APPLICATION_FORM = "PUBLIC_APPLICATION_FORM"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    CAPTCHA_CHALLENGE = "CAPTCHA_CHALLENGE"
    OPEN_PAGE = "OPEN_PAGE"


async def classify_page_security(page: Any) -> tuple[SecurityClassification, str | None]:
    """
    Categorize the current page state into:
    - CAPTCHA_CHALLENGE
    - AUTHENTICATION_REQUIRED
    - PUBLIC_APPLICATION_FORM
    - OPEN_PAGE
    """
    is_captcha, captcha_reason = await check_for_captcha(page)
    if is_captcha:
        return SecurityClassification.CAPTCHA_CHALLENGE, captcha_reason

    is_wall, wall_reason = await detect_login_wall(page)
    if is_wall:
        return SecurityClassification.AUTHENTICATION_REQUIRED, wall_reason

    form_res = await detect_application_form(page)
    if form_res.get("found"):
        return SecurityClassification.PUBLIC_APPLICATION_FORM, f"Application form detected ({form_res.get('confidence')} signals)"

    return SecurityClassification.OPEN_PAGE, None


# ---------------------------------------------------------------------------
# Field Matching (existing logic, preserved)
# ---------------------------------------------------------------------------

# Field name / attribute patterns for form filling
NAME_PATTERNS = {
    'full_name': [r'full[_\s-]?name', r'^name$', r'candidate[_\s-]?name', r'nom\s+complet'],
    'first_name': [r'first[_\s-]?name', r'fname', r'given[_\s-]?name', r'prénom', r'prenom', r'vorname'],
    'last_name': [r'last[_\s-]?name', r'lname', r'family[_\s-]?name', r'surname', r'\bnom\b', r'nachname'],
    'email': [r'email', r'e-mail', r'mail', r'courriel'],
    'phone': [r'phone', r'mobile', r'telephone', r'tel', r'cell', r'téléphone', r'telephone', r'numéro'],
    'location': [r'location', r'city', r'address', r'residence', r'adresse', r'ville'],
    'linkedin': [r'linkedin', r'linked[_\s-]?in'],
    'github': [r'github', r'git'],
    'portfolio': [r'portfolio', r'website', r'personal[_\s-]?site', r'blog'],
    'work_auth': [r'authorized', r'authorization', r'legally[_\s-]?authorized', r'eligible'],
    'sponsorship': [r'sponsor', r'sponsorship', r'visa'],
    'cover_letter': [r'cover[_\s-]?letter', r'letter', r'message', r'additional[_\s-]?info', r'note'],
    'company': [r'current[_\s-]?company', r'most[_\s-]?recent[_\s-]?company', r'employer', r'entreprise'],
    'job_title': [r'current[_\s-]?title', r'job[_\s-]?title', r'current[_\s-]?role', r'headline', r'poste[_\s-]?actuel'],
    'education': [r'highest[_\s-]?degree', r'degree', r'diploma', r'diplôme', r'level[_\s-]?of[_\s-]?education'],
    'school': [r'university', r'school', r'college', r'institution', r'école', r'université'],
    'skills': [r'skills', r'key[_\s-]?skills', r'technical[_\s-]?skills', r'compétences'],
}


def split_name(full_name: str) -> tuple[str, str]:
    """Split a full name into first and last name."""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def matches_any_pattern(text: str, patterns: list[str]) -> bool:
    """Check if text matches any regex pattern in list."""
    if not text:
        return False
    lower = text.lower().strip()
    return any(re.search(p, lower) for p in patterns)


async def find_input_field(page: Any, patterns: list[str], input_types: list[str] | None = None) -> Any | None:
    """Find an input matching given attribute patterns."""
    types = input_types or ["text", "email", "tel", "url", "number"]

    inputs = await page.query_selector_all('input, textarea, select')
    for elem in inputs:
        try:
            is_visible = await elem.is_visible()
            if not is_visible:
                continue

            # Check attributes: name, id, placeholder, aria-label
            elem_name = await elem.get_attribute('name') or ''
            elem_id = await elem.get_attribute('id') or ''
            elem_placeholder = await elem.get_attribute('placeholder') or ''
            elem_aria = await elem.get_attribute('aria-label') or ''
            elem_type = await elem.get_attribute('type') or 'text'

            # Label text
            label_text = ''
            if elem_id:
                label_elem = await page.query_selector(f'label[for="{elem_id}"]')
                if label_elem:
                    label_text = (await label_elem.inner_text()) or ''

            combined = f"{elem_name} {elem_id} {elem_placeholder} {elem_aria} {label_text}"
            if matches_any_pattern(combined, patterns):
                return elem
        except Exception:
            continue

    return None

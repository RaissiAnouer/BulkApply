"""Text extraction and heuristic parsing service for PDF and DOCX CVs."""

import re
from pathlib import Path
from pypdf import PdfReader
from docx import Document


COMMON_SKILLS = [
    "Python", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI", "Django", "Flask",
    "SQL", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Git", "GitHub", "CI/CD",
    "Linux", "HTML", "CSS", "REST", "GraphQL", "Java", "C++", "C#", "Go", "Rust",
    "Agile", "Scrum", "TDD", "Microservices", "Terraform", "Kafka", "Pandas", "NumPy"
]


def extract_text(file_path: str, file_type: str) -> str:
    """Extract raw text from PDF or DOCX file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    text = ""
    if file_type == "pdf":
        reader = PdfReader(str(path))
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    elif file_type == "docx":
        doc = Document(str(path))
        for para in doc.paragraphs:
            if para.text.strip():
                text += para.text + "\n"
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text += cell.text + " "
                text += "\n"
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    return text.strip()


def parse_cv_text(raw_text: str) -> dict:
    """
    Parse raw CV text into structured JSON.
    Attempts Google Gemini AI semantic parsing first. If Gemini is unavailable,
    times out, quota is exceeded, or returns invalid data, seamlessly falls back
    to the local heuristic parser with explicit logging.
    """
    try:
        from app.services import ai_service
        result = ai_service.parse_cv_with_gemini(raw_text)
        print("[PARSER] Successfully parsed CV using Google Gemini.")
        return result
    except Exception as e:
        print(f"[PARSER] Gemini unavailable/failed ({str(e)}). Using local fallback parser.")
        return parse_cv_text_local(raw_text)


def parse_cv_text_local(raw_text: str) -> dict:
    """Heuristic rule-based parser that structures raw CV text into JSON."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # 1. Contact Info
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_text)
    phone_match = re.search(r"(\+?\d{1,3}[\s-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}", raw_text)

    # Name: Typically the first line or prominent header
    full_name = None
    if lines:
        for candidate_line in lines[:5]:
            # Skip lines that are clearly emails or phone numbers
            if "@" not in candidate_line and not re.search(r"\d", candidate_line) and len(candidate_line) <= 50:
                full_name = candidate_line
                break

    # Location heuristic (e.g., "City, State" or "City, Country")
    location = None
    loc_match = re.search(r"([A-Z][a-zA-Z\s]+,\s*[A-Z]{2}|[A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z]+)", raw_text)
    if loc_match:
        location = loc_match.group(0).strip()

    contact_info = {
        "full_name": full_name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "location": location,
    }

    # 2. Skills
    matched_skills = set()
    raw_text_lower = raw_text.lower()
    for skill in COMMON_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, raw_text_lower):
            matched_skills.add(skill)

    # Also parse skills from an explicit "Skills:" line if present
    skills_section_match = re.search(
        r"(?:skills|technologies|technical skills|competencies)[:\s]+([^\n]+)",
        raw_text,
        re.IGNORECASE,
    )
    if skills_section_match:
        custom_skills = [s.strip() for s in re.split(r"[,;|•]", skills_section_match.group(1)) if s.strip()]
        for cs in custom_skills:
            if len(cs) < 30:
                matched_skills.add(cs.title())

    # 3. Work Experience
    experience_list = []
    # Search for blocks with date patterns: e.g. "2020 - 2023" or "Jan 2021 - Present"
    date_pattern = re.compile(
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|[0-9]{4})\s*[-–—to]+\s*(?:Present|[0-9]{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*[0-9]{4}))",
        re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        match = date_pattern.search(line)
        if match:
            date_range = match.group(0).strip()
            # Surrounding lines often have company and title
            company_or_title = date_pattern.sub("", line).strip(" |-,")
            prev_line = lines[i - 1] if i > 0 else None
            next_line = lines[i + 1] if i + 1 < len(lines) else None

            title = company_or_title if company_or_title else (prev_line or "Role")
            company = prev_line if (company_or_title and prev_line) else "Company"

            # Grab next lines as description until another date or short header
            desc = next_line or ""

            experience_list.append({
                "company": company,
                "title": title,
                "start_date": date_range.split("-")[0].strip() if "-" in date_range else date_range,
                "end_date": date_range.split("-")[1].strip() if "-" in date_range else "Present",
                "description": desc,
            })

    # 4. Education
    education_list = []
    degree_pattern = re.compile(
        r"(Bachelor|Master|Doctor|Ph\.?D|B\.?S\.?|M\.?S\.?|B\.?A\.?|Associate|Degree|Diploma)\s*(?:of|in)?\s*([A-Za-z\s]+)?",
        re.IGNORECASE,
    )
    inst_pattern = re.compile(r"(University|College|Institute|School|Academy)[\w\s]*", re.IGNORECASE)
    year_pattern = re.compile(r"\b(19\d\d|20\d\d)\b")

    for line in lines:
        deg_match = degree_pattern.search(line)
        inst_match = inst_pattern.search(line)
        if deg_match or inst_match:
            year_match = year_pattern.search(line)
            education_list.append({
                "institution": inst_match.group(0).strip() if inst_match else "University / Institution",
                "degree": deg_match.group(0).strip() if deg_match else "Degree",
                "graduation_year": year_match.group(0) if year_match else None,
            })

    # Limit to reasonable counts to keep data clean
    return {
        "contact_info": contact_info,
        "skills": sorted(list(matched_skills)),
        "work_experience": experience_list[:5],
        "education": education_list[:3],
    }

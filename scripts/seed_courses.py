#!/usr/bin/env python3
"""
Seed script: adds UofT Computer Science courses + demo assignments to the DB.
Run from project root: source venv/bin/activate && python scripts/seed_courses.py

This is an additive, idempotent demo seed. It skips courses/assignments that
already exist (matched by code + year).
"""
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "src/backend/.env.local")

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise SystemExit("DATABASE_URL not set in src/backend/.env.local")
os.environ.setdefault("DATABASE_URL", DB_URL)

from src.backend.config.database import SessionLocal
from src.backend.models.database import Assignment, Course, Organization, User

COURSES = [
    ("CSC108", "Introduction to Computer Science", 1),
    ("CSC148", "Introduction to Data Structures and Algorithms", 1),
    ("CSC161", "Computer Systems and Programming", 2),
    ("CSC209", "Software Design", 2),
    ("CSC236", "Introduction to Formal Reasoning", 2),
    ("CSC258", "Computer Organization", 2),
    ("CSC343", "Introduction to Databases", 3),
    ("CSC369", "Operating Systems", 3),
    ("CSC411", "Machine Learning", 4),
    ("CSC453", "Web Applications", 4),
]

TERM = "Fall"
YEAR = 2026

ASSIGNMENTS = [
    ("Assignment 1: Foundations", "programming", "Weekly practice with basic syntax and functions."),
    ("Assignment 2: Data Structures", "programming", "Implement core data structures covered in class."),
    ("Assignment 3: Algorithms", "programming", "Algorithmic problem set emphasizing efficiency."),
    ("Midterm Project", "project", "Individual project applying course concepts."),
    ("Final Project", "project", "Capstone project with peer review and demo."),
]

EMAIL = "prof.cs@example.com"
NAME = "Dr. T. Instructor"


def get_org(db):
    org = db.query(Organization).filter_by(name="University of Toronto").first()
    if org:
        return org
    org = Organization(name="University of Toronto")
    db.add(org)
    return org


def get_prof(db, org):
    user = db.query(User).filter_by(email=EMAIL).first()
    if user:
        return user
    import hashlib
    user = User(
        email=EMAIL,
        full_name=NAME,
        password_hash=hashlib.sha256(b"demo-password").hexdigest(),
        role="professor",
        organization_id=org.id,
        tenant_id=None,
    )
    db.add(user)
    return user


def seed():
    with SessionLocal() as db:
        org = get_org(db)
        prof = get_prof(db, org)
        db.flush()

        added_courses = 0
        for code, name, yr in COURSES:
            course = db.query(Course).filter_by(code=code, year=yr).first()
            if course:
                continue
            course = Course(
                code=code,
                name=name,
                year=yr,
                term=TERM,
                organization_id=org.id,
                department="Computer Science",
            )
            db.add(course)
            added_courses += 1

        db.flush()

        added_assignments = 0
        for code, _n, _y in COURSES:
            course = db.query(Course).filter_by(code=code, year=YEAR, term=TERM).first()
            if not course:
                course = db.query(Course).filter_by(code=code, year=_y).first()
                if not course:
                    continue
            for a_name, a_type, a_desc in ASSIGNMENTS:
                existing = db.query(Assignment).filter(
                    Assignment.course_id == course.id,
                    Assignment.name == a_name,
                ).first()
                if existing:
                    continue
                assignment = Assignment(
                    name=a_name,
                    description=a_desc,
                    assignment_type=a_type,
                    course_id=course.id,
                    due_at=datetime(YEAR, 12 if a_type == "project" else 10, 5 + (len(a_name) % 3), 23, 59),
                    max_score=100,
                    team_mode="individual",
                    open_book=True,
                    time_limited=False,
                    allowed_resources=["textbook", "lecture notes"],
                )
                db.add(assignment)
                added_assignments += 1

        db.commit()

        cc = db.query(Course).filter_by(term=TERM, year=YEAR).count()
        ac = db.query(Assignment).count()
        print(f"Organization: {org.name} (id={org.id})")
        print(f"Professor: {prof.email} (id={prof.id})")
        print(f"Added courses: {added_courses}")
        print(f"Courses in {TERM} {YEAR}: {cc}")
        print(f"Added assignments: {added_assignments}")
        print(f"Total assignments in DB: {ac}")


if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print("Seed failed:", e, file=sys.stderr)
        sys.exit(1)

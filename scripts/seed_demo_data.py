#!/usr/bin/env python3
"""
Seed demo data for development.

Creates:
- 1 Organization
- 3 Courses under that organization
- Links the first available professor/admin user to the organization
- Assigns that user as instructor to all courses

Run with:
    source venv/bin/activate
    python scripts/seed_demo_data.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.config.database import SessionLocal
from src.backend.models.database import Organization, Course, User, CourseInstructor
from sqlalchemy.orm import joinedload

def seed_demo_data():
    db = SessionLocal()

    try:
        # Check if we already have organizations
        existing_org = db.query(Organization).first()
        if existing_org:
            print(f"✓ Organization already exists: {existing_org.name} ({existing_org.id})")
            org = existing_org
        else:
            org = Organization(name="Demo University")
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"✓ Created Organization: {org.name} ({org.id})")

        # Create demo courses if none exist for this org
        existing_courses = db.query(Course).filter(Course.organization_id == org.id).count()
        if existing_courses > 0:
            print(f"✓ {existing_courses} courses already exist for this organization.")
        else:
            courses_data = [
                ("CS 101 - Introduction to Programming", "CS101"),
                ("CS 201 - Data Structures", "CS201"),
                ("CS 301 - Algorithms", "CS301"),
            ]

            for name, code in courses_data:
                course = Course(
                    organization_id=org.id,
                    name=name,
                    code=code,
                )
                db.add(course)
                print(f"  + Created course: {name}")

            db.commit()
            print("✓ Created 3 demo courses")

        # Find a suitable user (prefer professor or admin)
        user = (
            db.query(User)
            .filter(User.role.in_(["professor", "admin"]))
            .order_by(User.created_at)
            .first()
        )

        if not user:
            print("⚠ No professor or admin user found. Please create one first via the Admin page.")
            return

        # Assign user to the organization if not already set
        if not user.organization_id:
            user.organization_id = org.id
            db.commit()
            print(f"✓ Assigned user {user.email} to organization")

        # Assign user as instructor to all courses in the org
        courses = db.query(Course).filter(Course.organization_id == org.id).all()

        for course in courses:
            existing = (
                db.query(CourseInstructor)
                .filter(
                    CourseInstructor.course_id == course.id,
                    CourseInstructor.user_id == user.id,
                )
                .first()
            )
            if not existing:
                assignment = CourseInstructor(
                    course_id=course.id,
                    user_id=user.id,
                    role="instructor",
                )
                db.add(assignment)
                print(f"  + Assigned {user.email} as instructor to {course.name}")
            else:
                print(f"  ✓ {user.email} already instructor for {course.name}")

        db.commit()

        print("\n✅ Demo data seeded successfully!")
        print(f"   Organization: {org.name}")
        print(f"   User: {user.email} ({user.role})")
        print(f"   Courses: {len(courses)}")
        print("\nYou can now test the Upload page and Admin → Course Instructor Assignments section.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding demo data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()

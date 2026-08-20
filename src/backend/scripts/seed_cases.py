"""Seed database with demo case data for development."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.backend.config.database import Base, SessionLocal, engine
from src.backend.models.database import (
    Assignment,
    Case,
    CaseComment,
    Organization,
    User,
)


def create_seed_data(db: Session) -> None:
    """Create demo case data in the database."""

    # Check if we already have cases
    existing_cases = db.query(Case).count()
    if existing_cases > 0:
        print(f"Found {existing_cases} existing cases. Skipping seed.")
        return

    # Create demo organization if not exists
    org = db.query(Organization).first()
    if not org:
        org = Organization(id=uuid.uuid4(), name="Demo University")
        db.add(org)
        db.flush()

    # Create demo users if not exist
    users = db.query(User).all()
    if not users:
        users = [
            User(
                id=uuid.uuid4(),
                email="professor@example.edu",
                full_name="Dr. Smith",
                role="professor",
                tenant_id=org.id,
            ),
            User(
                id=uuid.uuid4(),
                email="ta@example.edu",
                full_name="TA Morgan",
                role="ta",
                tenant_id=org.id,
            ),
        ]
        for u in users:
            db.add(u)
        db.flush()

    professor = db.query(User).filter(User.role == "professor").first()
    ta = db.query(User).filter(User.role == "ta").first()

    # Create demo assignments
    assignments = db.query(Assignment).all()
    if not assignments:
        assignments = [
            Assignment(
                id=uuid.uuid4(),
                course_code="CSC108",
                title="A2 Recursion",
                description="Recursive tree traversal implementation",
                tenant_id=org.id,
            ),
            Assignment(
                id=uuid.uuid4(),
                course_code="CSC148",
                title="BST Lab",
                description="Binary Search Tree implementation",
                tenant_id=org.id,
            ),
        ]
        for a in assignments:
            db.add(a)
        db.flush()

    assignment1 = (
        db.query(Assignment).filter(Assignment.course_code == "CSC108").first()
    )
    assignment2 = (
        db.query(Assignment).filter(Assignment.course_code == "CSC148").first()
    )

    # Create demo cases
    cases = [
        Case(
            id=uuid.uuid4(),
            organization_id=org.id,
            assignment_id=assignment1.id,
            title="A2 Recursion - Potential AI Assistance",
            status="OPEN",
            priority="HIGH",
            created_by_id=professor.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        Case(
            id=uuid.uuid4(),
            organization_id=org.id,
            assignment_id=assignment2.id,
            title="BST Lab - Similar Submissions",
            status="UNDER_REVIEW",
            priority="MEDIUM",
            investigator_id=ta.id,
            created_by_id=professor.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        Case(
            id=uuid.uuid4(),
            organization_id=org.id,
            assignment_id=assignment1.id,
            title="A2 Recursion - Review Needed",
            status="OPEN",
            priority="LOW",
            created_by_id=professor.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    ]

    for c in cases:
        db.add(c)

    db.flush()

    # Add comments to cases
    comments = [
        CaseComment(
            id=uuid.uuid4(),
            case_id=cases[0].id,
            user_id=professor.id,
            body="Initial review suggests potential AI assistance. Recommend manual verification.",
            created_at=datetime.now(timezone.utc),
        ),
        CaseComment(
            id=uuid.uuid4(),
            case_id=cases[1].id,
            user_id=ta.id,
            body="Both students worked in the same tutorial section. Similarity may be explained by shared instruction.",
            created_at=datetime.now(timezone.utc),
        ),
    ]

    for comment in comments:
        db.add(comment)

    db.commit()
    print(f"Created {len(cases)} demo cases with {len(comments)} comments.")


if __name__ == "__main__":
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    print("Seeding demo data...")
    with SessionLocal() as db:
        create_seed_data(db)

    print("Done!")

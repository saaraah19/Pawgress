"""
init_db.py

Run once to create all tables in the database. Since every module's models
inherit from the same shared Base (shared/database.py), importing all model
modules and calling create_all() creates every table in one step.

Usage: python init_db.py
"""

from shared.database import Base, engine

# Importing these registers their tables on Base.metadata — required even
# though the names aren't used directly below.
from identity.models import User  # noqa: F401
from productivity.models import Capture, Task, Goal, FieldCorrectionRecord  # noqa: F401

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully.")

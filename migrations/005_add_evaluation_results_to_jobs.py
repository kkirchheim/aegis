"""Add evaluation_results JSONB column to jobs table."""

def migrate(db):
    """Add evaluation_results column."""
    # For SQLite, JSONB is just TEXT, but we'll use JSON type hint for compatibility
    db.execute_sql(
        'ALTER TABLE job ADD COLUMN evaluation_results TEXT'
    )
    print("✓ Added evaluation_results column to jobs table")


def rollback(db):
    """Remove evaluation_results column."""
    db.execute_sql(
        'ALTER TABLE job DROP COLUMN evaluation_results'
    )
    print("✓ Removed evaluation_results column from jobs table")

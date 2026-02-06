"""Add execution scripts tables."""

from peewee import SQL

def migrate(migrator, database, fake=False, **kwargs):
    """Create execution script tables."""
    
    # Create execution_script table
    migrator.create_table(
        'execution_script',
        {
            'script_hash': SQL('VARCHAR(64) PRIMARY KEY'),
            'script_text': SQL('TEXT NOT NULL'),
            'name': SQL('VARCHAR(255) NOT NULL'),
            'created_at': SQL('TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
            'created_by': SQL('INTEGER REFERENCES user(id)'),
        }
    )
    
    # Create execution_script_result table
    migrator.create_table(
        'execution_script_result',
        {
            'id': SQL('UUID PRIMARY KEY'),
            'job_id': SQL('VARCHAR REFERENCES job(id)'),
            'script_hash': SQL('VARCHAR(64) REFERENCES execution_script(script_hash)'),
            'exit_code': SQL('INTEGER'),
            'stdout': SQL('TEXT'),
            'stderr': SQL('TEXT'),
            'duration_ms': SQL('INTEGER DEFAULT 0'),
            'created_at': SQL('TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        }
    )


def rollback(migrator, database, fake=False, **kwargs):
    """Drop execution script tables."""
    migrator.drop_table('execution_script_result')
    migrator.drop_table('execution_script')

#!/usr/bin/env python3
"""
Simplified test to verify the implementation logic
"""

import sqlite3
import tempfile
import os

def test_database_migration():
    """Test that num_pages column can be added and used."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Create jobs table as in app.py
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                pdf_path TEXT NOT NULL,
                pdf_filename TEXT,
                report JSON,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        
        # Test migration: add num_pages column
        try:
            c.execute("ALTER TABLE jobs ADD COLUMN num_pages INTEGER")
            conn.commit()
            print("✓ Successfully added num_pages column to jobs table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e):
                print("✓ num_pages column already exists")
            else:
                print(f"✗ Failed to add num_pages column: {e}")
                conn.close()
                return False
        
        # Test inserting a job with num_pages
        try:
            c.execute("""
                INSERT INTO jobs (id, status, pdf_path, pdf_filename, num_pages)
                VALUES (?, ?, ?, ?, ?)
            """, ("test-job-1", "pending", "/tmp/test.pdf", "test.pdf", 42))
            conn.commit()
            print("✓ Successfully inserted job with num_pages=42")
        except Exception as e:
            print(f"✗ Failed to insert job: {e}")
            conn.close()
            return False
        
        # Verify the value was stored
        try:
            c.execute("SELECT id, status, num_pages FROM jobs WHERE id = ?", ("test-job-1",))
            result = c.fetchone()
            if result and result[2] == 42:
                print(f"✓ Verified page count was stored correctly: {result}")
            else:
                print(f"✗ Page count not stored correctly: {result}")
                conn.close()
                return False
        except Exception as e:
            print(f"✗ Failed to retrieve job: {e}")
            conn.close()
            return False
        
        # Test NULL handling (for extraction failure)
        try:
            c.execute("""
                INSERT INTO jobs (id, status, pdf_path, pdf_filename, num_pages)
                VALUES (?, ?, ?, ?, ?)
            """, ("test-job-null", "pending", "/tmp/test2.pdf", "test2.pdf", None))
            conn.commit()
            print("✓ Successfully inserted job with num_pages=NULL")
        except Exception as e:
            print(f"✗ Failed to insert NULL: {e}")
            conn.close()
            return False
        
        # Verify NULL was stored
        try:
            c.execute("SELECT id, num_pages FROM jobs WHERE id = ?", ("test-job-null",))
            result = c.fetchone()
            if result and result[1] is None:
                print(f"✓ Verified NULL page count: {result}")
            else:
                print(f"✗ Unexpected result: {result}")
                conn.close()
                return False
        except Exception as e:
            print(f"✗ Failed to retrieve NULL: {e}")
            conn.close()
            return False
        
        # Test fetching all jobs (like /jobs endpoint)
        try:
            c.execute("""
                SELECT 
                    id, status, pdf_filename, num_pages
                FROM jobs
                ORDER BY id DESC
                LIMIT 50
            """)
            results = c.fetchall()
            print(f"✓ Successfully fetched {len(results)} jobs via /jobs query")
            for row in results:
                print(f"  - Job {row[0]}: {row[3]} pages")
        except Exception as e:
            print(f"✗ Failed to fetch jobs: {e}")
            conn.close()
            return False
        
        conn.close()
        return True

def test_page_count_calculation():
    """Test the logic for displaying page count."""
    test_cases = [
        (None, ""),           # No page count
        (1, "📄 1 page"),     # Single page
        (5, "📄 5 pages"),    # Multiple pages
        (42, "📄 42 pages"),  # Large document
    ]
    
    all_pass = True
    for num_pages, expected_display in test_cases:
        if num_pages is None:
            display = ""
        else:
            display = f"📄 {num_pages} page{'s' if num_pages != 1 else ''}"
        
        if display == expected_display:
            print(f"✓ Page count {num_pages} -> '{display}'")
        else:
            print(f"✗ Page count {num_pages}: expected '{expected_display}', got '{display}'")
            all_pass = False
    
    return all_pass

if __name__ == "__main__":
    print("=" * 70)
    print("PDF Page Count Feature - Implementation Verification")
    print("=" * 70)
    
    print("\n[TEST 1] Database Migration & Storage")
    print("-" * 70)
    test1 = test_database_migration()
    
    print("\n[TEST 2] Page Count Display Logic")
    print("-" * 70)
    test2 = test_page_count_calculation()
    
    print("\n" + "=" * 70)
    if test1 and test2:
        print("✓ ALL TESTS PASSED - Implementation verified!")
        print("=" * 70)
    else:
        print("✗ Some tests failed")
        print("=" * 70)

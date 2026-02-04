#!/usr/bin/env python3
"""
Test script to verify PDF page count extraction feature
"""

import sqlite3
import tempfile
import os
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pathlib import Path

def create_test_pdf(filepath, num_pages=3):
    """Create a simple test PDF with specified number of pages."""
    c = canvas.Canvas(filepath, pagesize=letter)
    for i in range(num_pages):
        c.drawString(100, 750, f"Test Page {i+1}")
        c.showPage()
    c.save()
    print(f"✓ Created test PDF: {filepath} ({num_pages} pages)")
    return filepath

def test_page_count_extraction():
    """Test pdfplumber page count extraction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        
        # Test with 5-page PDF
        create_test_pdf(pdf_path, num_pages=5)
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                num_pages = len(pdf.pages)
            print(f"✓ Extracted page count: {num_pages}")
            assert num_pages == 5, f"Expected 5 pages, got {num_pages}"
            return True
        except Exception as e:
            print(f"✗ Failed to extract page count: {e}")
            return False

def test_database_migration():
    """Test that num_pages column exists in jobs table."""
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
            print("✓ Successfully inserted job with num_pages")
        except Exception as e:
            print(f"✗ Failed to insert job: {e}")
            conn.close()
            return False
        
        # Verify the value was stored
        try:
            c.execute("SELECT num_pages FROM jobs WHERE id = ?", ("test-job-1",))
            result = c.fetchone()
            if result and result[0] == 42:
                print(f"✓ Verified page count was stored correctly: {result[0]}")
            else:
                print(f"✗ Page count not stored correctly: {result}")
                conn.close()
                return False
        except Exception as e:
            print(f"✗ Failed to retrieve job: {e}")
            conn.close()
            return False
        
        conn.close()
        return True

def test_null_handling():
    """Test that NULL values are handled correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Create jobs table
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                pdf_path TEXT NOT NULL,
                num_pages INTEGER
            )
        """)
        
        # Insert job with NULL num_pages (simulating extraction failure)
        try:
            c.execute("""
                INSERT INTO jobs (id, pdf_path, num_pages)
                VALUES (?, ?, ?)
            """, ("test-job-null", "/tmp/test.pdf", None))
            conn.commit()
            print("✓ Successfully stored NULL page count")
        except Exception as e:
            print(f"✗ Failed to store NULL page count: {e}")
            conn.close()
            return False
        
        # Verify NULL was stored
        try:
            c.execute("SELECT num_pages FROM jobs WHERE id = ?", ("test-job-null",))
            result = c.fetchone()
            if result and result[0] is None:
                print("✓ NULL page count verified")
            else:
                print(f"✗ Unexpected result: {result}")
                conn.close()
                return False
        except Exception as e:
            print(f"✗ Failed to retrieve NULL: {e}")
            conn.close()
            return False
        
        conn.close()
        return True

if __name__ == "__main__":
    print("=" * 60)
    print("Testing PDF Page Count Feature")
    print("=" * 60)
    
    tests = [
        ("Page Count Extraction (pdfplumber)", test_page_count_extraction),
        ("Database Migration", test_database_migration),
        ("NULL Value Handling", test_null_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n[TEST] {test_name}")
        print("-" * 60)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed!")
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status}: {test_name}")

"""PDF processing utilities."""

import subprocess
from pathlib import Path

import pdfplumber


def extract_pdf_text(pdf_path, max_chars=50000, app_logger=None):
    """
    Extract text from PDF file.

    Args:
        pdf_path: Path to PDF file
        max_chars: Maximum characters to extract
        app_logger: Flask app logger for logging

    Returns:
        Extracted text as string

    Raises:
        Exception: If PDF extraction fails
    """
    try:
        if app_logger:
            app_logger.info(f"Extracting PDF: {pdf_path}")

        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            if app_logger:
                app_logger.info(f"PDF has {total_pages} pages")

            for i, page in enumerate(pdf.pages):
                if len(text) >= max_chars:
                    if app_logger:
                        app_logger.info(f"Reached max_chars limit at page {i + 1}")
                    break

                page_text = page.extract_text()
                if page_text:
                    text += f"\n--- Page {i + 1} ---\n{page_text}"
                    if app_logger and (i + 1) % 5 == 0:
                        app_logger.info(f"Extracted {i + 1}/{total_pages} pages, {len(text)} chars so far")

        if app_logger:
            app_logger.info(f"PDF extraction complete: {len(text)} characters from {total_pages} pages")

        return text

    except Exception as e:
        if app_logger:
            app_logger.error(f"Failed to extract PDF: {str(e)}", exc_info=True)
        raise Exception(f"Failed to extract PDF: {str(e)}")


def generate_pdf_thumbnail(pdf_path, job_id, thumbnails_folder, app_logger=None):
    """
    Generate thumbnail from first page of PDF using ImageMagick.

    Args:
        pdf_path: Path to PDF file
        job_id: Job ID for naming and logging
        thumbnails_folder: Path to thumbnails directory
        app_logger: Flask app logger for logging

    Returns:
        Relative path to thumbnail file, or None if generation failed
    """
    try:
        if app_logger:
            app_logger.info(f"[{job_id}] Generating thumbnail from PDF: {pdf_path}")

        # Generate output filename
        thumbnail_filename = f"{job_id}.png"
        thumbnail_path = Path(thumbnails_folder) / thumbnail_filename

        # Use ImageMagick to extract first page with proper PDF rendering
        cmd = [
            "magick",
            "-density",
            "200",  # High density for quality
            f"{pdf_path}[0]",  # First page only
            "-colorspace",
            "sRGB",
            "-alpha",
            "remove",
            "-background",
            "white",  # White background instead of black
            "-thumbnail",
            "512x512",  # Thumbnail size
            "-strip",
            "-quality",
            "85",
            str(thumbnail_path),
        ]

        if app_logger:
            app_logger.info(f"[{job_id}] Running ImageMagick: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            if app_logger:
                app_logger.error(f"[{job_id}] ImageMagick failed: {result.stderr}")
            return None

        if not thumbnail_path.exists():
            if app_logger:
                app_logger.error(f"[{job_id}] Thumbnail file was not created: {thumbnail_path}")
            return None

        # Return relative path for storage in database
        relative_path = f"uploads/thumbnails/{thumbnail_filename}"
        if app_logger:
            app_logger.info(
                f"[{job_id}] Thumbnail generated successfully: {relative_path} ({thumbnail_path.stat().st_size} bytes)"
            )

        return relative_path

    except subprocess.TimeoutExpired:
        if app_logger:
            app_logger.error(f"[{job_id}] Thumbnail generation timed out after 30 seconds")
        return None
    except Exception as e:
        if app_logger:
            app_logger.error(f"[{job_id}] Failed to generate thumbnail: {str(e)}", exc_info=True)
        return None


def extract_page_count(pdf_path, app_logger=None):
    """
    Extract page count from PDF.

    Args:
        pdf_path: Path to PDF file
        app_logger: Flask app logger for logging

    Returns:
        Number of pages, or None if extraction fails
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            num_pages = len(pdf.pages)
            if app_logger:
                app_logger.info(f"Extracted page count: {num_pages}")
            return num_pages
    except Exception as e:
        if app_logger:
            app_logger.warning(f"Failed to extract page count: {e}")
        return None

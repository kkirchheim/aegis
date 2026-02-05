"""
Common Marshmallow schemas for API responses.

This module contains reusable schemas for standardized API response formats
including error responses, pagination metadata, and success messages.
"""

from marshmallow import Schema, fields, validate


class ErrorSchema(Schema):
    """
    Schema for error responses.
    
    Attributes:
        error (str): Error type or code (optional).
        message (str): Detailed error message (optional).
        status_code (int): HTTP status code (optional).
    """
    
    error = fields.Str(required=False, allow_none=True)
    message = fields.Str(required=False, allow_none=True)
    status_code = fields.Int(required=False, allow_none=True)


class PaginationSchema(Schema):
    """
    Schema for pagination metadata in API responses.
    
    Attributes:
        page (int): Current page number (optional).
        per_page (int): Number of items per page (optional).
        total (int): Total number of items (optional).
        pages (int): Total number of pages (optional).
    """
    
    page = fields.Int(required=False, allow_none=True)
    per_page = fields.Int(required=False, allow_none=True)
    total = fields.Int(required=False, allow_none=True)
    pages = fields.Int(required=False, allow_none=True)


class SuccessMessageSchema(Schema):
    """
    Schema for success message responses.
    
    Attributes:
        ok (bool): Success indicator (required). Must be True to indicate success.
        message (str): Optional message describing the result (optional).
    """
    
    ok = fields.Bool(required=True)
    message = fields.Str(required=False, allow_none=True)

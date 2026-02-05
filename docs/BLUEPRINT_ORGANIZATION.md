# Blueprint Organization

## Overview

The Paper Reproducibility Checker API is organized into multiple **Flask blueprints**, each handling a distinct domain of functionality. This document provides a quick reference for which blueprint handles which routes.

We use multiple blueprints to maintain separation of concerns, improve code organization, and make the codebase easier to navigate and maintain. Each blueprint focuses on a specific area: authentication, core API features, job management, and administrative functions.

## Table of Contents

- [auth.py - Authentication](#authpy---authentication)
- [api.py - Core API](#apipy---core-api)
- [jobs.py - Job Management](#jobspy---job-management)
- [admin.py - Administration](#adminpy---administration)
- [Full Route Map](#full-route-map)

---

## auth.py - Authentication

Handles user registration, login, logout, and password management. **Page routes only** (GET) - API endpoints are in `api.py`.

| Route | Method | Purpose |
|-------|--------|---------|
| `/register` | GET | User registration page |
| `/login` | GET | User login page |
| `/logout` | GET, POST | Clears session and redirects to login |
| `/profile` | GET | Display user profile with account information |
| `/change-password` | GET | Change password page |
| `/api/change-password` | POST | Change password endpoint |

**Auth Required:** All routes except `/register` and `/login`

**Note:** User registration and login are handled by REST API endpoints in `api.py` at `/api/auth/register` and `/api/auth/login`.

---

## api.py - Core API

Provides REST API endpoints for authentication, health checks, cache management, chat interactions, agent communication, and LLM integration.

### Authentication (REST API)

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/auth/login` | POST | User login (REST API) |
| `/api/auth/register` | POST | User registration (REST API) |

### Health & Cache

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/health` | GET | Health check endpoint; returns database and service status |
| `/api/cache/stats` | GET | Get cache statistics (admin only) |
| `/api/cache/clear` | DELETE | Clear all cached PDF files (admin only) |

### Chat

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/job/<job_id>/chat` | POST | Chat with paper analysis results |
| `/api/job/<job_id>/chat/history` | GET | Retrieve chat history for a job |
| `/api/job/<job_id>/chat/history` | DELETE | Clear chat history for a job |

### Agent Communication

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/agent/think` | POST | Agent requests next action decision from backend |
| `/api/agent/log` | POST | Agent logs progress messages |
| `/api/agent/execution` | POST | Agent stores execution details and results |
| `/api/agent/complete` | POST | Agent reports completion status |

**Auth Required:** All except `/api/health` and `/api/agent/*`

---

## jobs.py - Job Management

Handles PDF upload, job history, job details, and job lifecycle management.

| Route | Method | Purpose |
|-------|--------|---------|
| `/upload` | POST | Upload PDF for analysis |
| `/` | GET | Home page; redirects to login if not authenticated |
| `/history` | GET | Browse past analyses |
| `/job/<job_id>` | GET | Get job status and report |
| `/job/<job_id>` | DELETE | Delete a job and related data |
| `/jobs` | GET | List all jobs for current user |
| `/api/job/<job_id>/full` | GET | Get complete job data including events, artifacts, analysis |
| `/reports/<job_id>` | GET | Serve job detail/report page |
| `/results/<job_id>` | GET | Serve job results page |

**Auth Required:** All except `/`

---

## admin.py - Administration

Provides administrative functions for user management and system oversight.

| Route | Method | Purpose |
|-------|--------|---------|
| `/admin` | GET | Admin panel page listing all users |
| `/api/admin/users` | GET | Get list of all users (JSON) |
| `/api/admin/users/<user_id>` | PATCH | Update user status (activate/deactivate) |
| `/api/admin/users/<user_id>` | DELETE | Delete a user and related jobs |

**Auth Required:** All (admin only)

---

## Full Route Map

Complete reference of all routes with HTTP methods, authentication requirements, and purposes.

| HTTP Method | Endpoint | Blueprint | Auth Required | Purpose |
|-------------|----------|-----------|----------------|---------|
| GET | `/register` | auth | No | User registration page |
| GET | `/login` | auth | No | User login page |
| POST | `/api/auth/register` | api | No | User registration (REST API) |
| POST | `/api/auth/login` | api | No | User login (REST API) |
| GET, POST | `/logout` | auth | Yes | User logout |
| GET | `/profile` | auth | Yes | User profile page |
| GET | `/change-password` | auth | Yes | Change password form |
| POST | `/api/change-password` | auth | Yes | Update password |
| GET | `/api/health` | api | No | Health check |
| GET | `/api/cache/stats` | api | Yes (Admin) | Cache statistics |
| DELETE | `/api/cache/clear` | api | Yes (Admin) | Clear cache |
| POST | `/api/job/<job_id>/chat` | api | Yes | Chat with paper |
| GET | `/api/job/<job_id>/chat/history` | api | Yes | Get chat history |
| DELETE | `/api/job/<job_id>/chat/history` | api | Yes | Clear chat history |
| POST | `/api/agent/think` | api | No | Agent decision request |
| POST | `/api/agent/log` | api | No | Agent progress log |
| POST | `/api/agent/execution` | api | No | Agent execution details |
| POST | `/api/agent/complete` | api | No | Agent completion report |
| POST | `/upload` | jobs | Yes | Upload PDF for analysis |
| GET | `/` | jobs | No | Home page |
| GET | `/history` | jobs | Yes | View job history |
| GET | `/job/<job_id>` | jobs | Yes | Get job status |
| DELETE | `/job/<job_id>` | jobs | Yes | Delete job |
| GET | `/jobs` | jobs | Yes | List user jobs |
| GET | `/api/job/<job_id>/full` | jobs | Yes | Get complete job data |
| GET | `/reports/<job_id>` | jobs | Yes | View job report |
| GET | `/results/<job_id>` | jobs | Yes | View job results |
| GET | `/admin` | admin | Yes (Admin) | Admin panel |
| GET | `/api/admin/users` | admin | Yes (Admin) | List all users |
| PATCH | `/api/admin/users/<user_id>` | admin | Yes (Admin) | Update user status (activate/deactivate) |
| DELETE | `/api/admin/users/<user_id>` | admin | Yes (Admin) | Delete user |

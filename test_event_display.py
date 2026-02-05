#!/usr/bin/env python3
"""Test the event display functionality of the CLI."""

from datetime import datetime, timedelta

def print_new_events(job_data, last_event_index):
    """
    Print any new events that have arrived.
    (Copied from repro-cli.py for testing)
    """
    events = job_data.get('events', [])
    
    if not events:
        return last_event_index
    
    # Print new events
    for i in range(last_event_index, len(events)):
        event = events[i]
        
        # Format event display
        step = event.get('step', 'unknown')
        timestamp = event.get('created_at', '')
        
        # Try to format timestamp nicely
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_str = dt.strftime('%H:%M:%S')
            except:
                timestamp_str = timestamp
        else:
            timestamp_str = '??:??:??'
        
        # Get event message/content
        message = event.get('message') or event.get('content') or ''
        
        # Color-code based on step/status
        if 'error' in step.lower() or 'failed' in step.lower():
            emoji = '❌'
        elif 'success' in step.lower() or 'completed' in step.lower():
            emoji = '✅'
        elif 'starting' in step.lower() or 'started' in step.lower():
            emoji = '🚀'
        else:
            emoji = '📝'
        
        # Print with formatting
        if message:
            print(f"  {emoji} [{timestamp_str}] {step}: {message}")
        else:
            print(f"  {emoji} [{timestamp_str}] {step}")
    
    return len(events)

print("=== EVENT DISPLAY TEST ===\n")

# Create mock job data with events
now = datetime.now()
events = [
    {
        "step": "starting",
        "message": "Job started",
        "created_at": now.isoformat()
    },
    {
        "step": "stage_1_starting",
        "message": "Paper analysis begun",
        "created_at": (now + timedelta(seconds=1)).isoformat()
    },
    {
        "step": "paper_analysis",
        "message": "Extracting metadata and citations",
        "created_at": (now + timedelta(seconds=5)).isoformat()
    },
    {
        "step": "paper_analysis",
        "message": "Analysis complete: 42 citations found",
        "created_at": (now + timedelta(seconds=15)).isoformat()
    },
    {
        "step": "stage_1_complete",
        "message": "Paper analysis completed successfully",
        "created_at": (now + timedelta(seconds=16)).isoformat()
    },
    {
        "step": "stage_2_starting",
        "message": "Code execution starting",
        "created_at": (now + timedelta(seconds=17)).isoformat()
    },
]

# Test 1: Show first 3 events
print("BATCH 1: First 3 events")
print("-" * 60)
job_data = {
    "status": "processing",
    "progress": 0.2,
    "current_stage": "paper_analysis",
    "events": events[:3]
}
last_index = print_new_events(job_data, 0)
print(f"Processed {last_index} events\n")

# Test 2: Show next 2 events (simulating polling with new events)
print("\nBATCH 2: Next 2 events (polling interval)")
print("-" * 60)
job_data = {
    "status": "processing",
    "progress": 0.4,
    "current_stage": "paper_analysis",
    "events": events[:5]
}
last_index = print_new_events(job_data, last_index)
print(f"Processed {last_index} events total\n")

# Test 3: Show final event
print("\nBATCH 3: Final event")
print("-" * 60)
job_data = {
    "status": "processing",
    "progress": 0.5,
    "current_stage": "code_execution",
    "events": events  # All 6 events
}
last_index = print_new_events(job_data, last_index)
print(f"Processed {last_index} events total\n")

# Test 4: No new events
print("\nBATCH 4: No new events (polling continues)")
print("-" * 60)
print("(No events to display)")
last_index = print_new_events(job_data, last_index)
print(f"Processed {last_index} events total (no change)\n")

print("=== ALL TESTS COMPLETED ===")

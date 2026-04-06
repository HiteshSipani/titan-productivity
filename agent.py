import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
model_name = os.getenv("MODEL", "gemini-2.0-flash")

DB_PATH = Path(__file__).parent / "titan.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            due_date TEXT,
            project TEXT,
            estimated_minutes INTEGER DEFAULT 60,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY,
            title TEXT,
            content TEXT NOT NULL,
            category TEXT,
            tags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reminders (
            reminder_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            remind_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            linked_task_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS day_plans (
            plan_id TEXT PRIMARY KEY,
            plan_date TEXT NOT NULL,
            summary TEXT,
            focus_score INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS behavior_patterns (
            pattern_id TEXT PRIMARY KEY,
            pattern_type TEXT,
            pattern_data TEXT,
            observed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

import uuid

def create_task(title: str, priority: str = "medium", due_date: str = None, description: str = None, project: str = None, estimated_minutes: int = 60) -> dict:
    """Creates a new task. Priority: low/medium/high. due_date format: YYYY-MM-DD HH:MM"""
    conn = get_db()
    task_id = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO tasks (task_id, title, description, priority, due_date, project, estimated_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)", (task_id, title, description, priority, due_date, project, estimated_minutes))
    conn.commit()
    conn.close()
    return {"status": "success", "task_id": task_id, "message": f"Task '{title}' created with {priority} priority", "due_date": due_date, "estimated_minutes": estimated_minutes}

def get_tasks(status: str = "pending", priority: str = None) -> dict:
    """Get tasks. Status: pending/in-progress/done. Priority: low/medium/high"""
    conn = get_db()
    if priority:
        rows = conn.execute("SELECT * FROM tasks WHERE status=? AND priority=? ORDER BY due_date ASC", (status, priority)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tasks WHERE status=? ORDER BY due_date ASC", (status,)).fetchall()
    conn.close()
    return {"status": "success", "count": len(rows), "tasks": [dict(row) for row in rows]}

def update_task_status(task_id: str, new_status: str) -> dict:
    """Update task status. Status: pending/in-progress/done"""
    conn = get_db()
    conn.execute("UPDATE tasks SET status=? WHERE task_id=?", (new_status, task_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Task {task_id} marked as {new_status}"}

def get_tasks_due_today() -> dict:
    """Get all tasks due today"""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks WHERE due_date LIKE ? AND status != 'done' ORDER BY priority DESC", (f"{today}%",)).fetchall()
    conn.close()
    return {"status": "success", "date": today, "count": len(rows), "tasks": [dict(row) for row in rows]}

def save_note(title: str, content: str, category: str = "general", tags: str = None) -> dict:
    """Save a note with title, content, category and optional tags"""
    conn = get_db()
    note_id = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO notes (note_id, title, content, category, tags) VALUES (?, ?, ?, ?, ?)", (note_id, title, content, category, tags))
    conn.commit()
    conn.close()
    return {"status": "success", "note_id": note_id, "message": f"Note '{title}' saved under {category}"}

def search_notes(query: str) -> dict:
    """Search notes by keyword in title or content"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? ORDER BY created_at DESC", (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()
    conn.close()
    return {"status": "success", "query": query, "count": len(rows), "notes": [dict(row) for row in rows]}

def get_recent_notes(limit: int = 5) -> dict:
    """Get most recent notes"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return {"status": "success", "notes": [dict(row) for row in rows]}

def create_reminder(title: str, remind_at: str, linked_task_id: str = None) -> dict:
    """Create a reminder. remind_at format: YYYY-MM-DD HH:MM"""
    conn = get_db()
    reminder_id = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO reminders (reminder_id, title, remind_at, linked_task_id) VALUES (?, ?, ?, ?)", (reminder_id, title, remind_at, linked_task_id))
    conn.commit()
    conn.close()
    return {"status": "success", "reminder_id": reminder_id, "message": f"Reminder '{title}' set for {remind_at}"}

def get_upcoming_reminders() -> dict:
    """Get all upcoming pending reminders"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_db()
    rows = conn.execute("SELECT * FROM reminders WHERE status='pending' AND remind_at >= ? ORDER BY remind_at ASC", (now,)).fetchall()
    conn.close()
    return {"status": "success", "reminders": [dict(row) for row in rows]}

def detect_scheduling_conflicts(tasks_json: str, calendar_events_json: str) -> dict:
    """Detect conflicts between task due dates and calendar events"""
    try:
        tasks = json.loads(tasks_json) if tasks_json else []
        events = json.loads(calendar_events_json) if calendar_events_json else []
    except:
        tasks = []
        events = []
    conflicts = []
    suggestions = []
    for task in tasks:
        due = task.get("due_date", "")
        title = task.get("title", "")
        estimated = task.get("estimated_minutes", 60)
        if due:
            for event in events:
                if due[:10] == event.get("start", "")[:10]:
                    conflicts.append({"task": title, "due": due, "conflict_with": event.get("title", "Meeting"), "risk": "high"})
                    suggestions.append(f"Task '{title}' is due on a busy day. Suggest blocking {estimated} mins in the morning.")
    return {"status": "success", "conflicts_found": len(conflicts), "conflicts": conflicts, "suggestions": suggestions}

def suggest_focus_blocks(available_slots_json: str, tasks_json: str) -> dict:
    """Suggest optimal focus blocks based on available slots and pending tasks"""
    try:
        slots = json.loads(available_slots_json) if available_slots_json else []
        tasks = json.loads(tasks_json) if tasks_json else []
    except:
        slots = []
        tasks = []
    blocks = []
    ordered_tasks = sorted(tasks, key=lambda x: 0 if x.get("priority") == "high" else 1 if x.get("priority") == "medium" else 2)
    for i, slot in enumerate(slots[:len(ordered_tasks)]):
        if i < len(ordered_tasks):
            task = ordered_tasks[i]
            blocks.append({"time_slot": slot, "task": task.get("title"), "priority": task.get("priority"), "estimated_minutes": task.get("estimated_minutes", 60), "calendar_event_title": f"[FOCUS] {task.get('title')}", "add_to_calendar": True})
    return {"status": "success", "focus_blocks": blocks, "message": f"Suggested {len(blocks)} focus blocks"}

def get_morning_briefing_data() -> dict:
    """Gather all data needed for morning briefing"""
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_db()
    tasks_today = [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE due_date LIKE ? AND status != 'done'", (f"{today}%",)).fetchall()]
    tasks_tomorrow = [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE due_date LIKE ? AND status != 'done'", (f"{tomorrow}%",)).fetchall()]
    reminders = [dict(r) for r in conn.execute("SELECT * FROM reminders WHERE remind_at LIKE ? AND status='pending'", (f"{today}%",)).fetchall()]
    overdue = [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE due_date < ? AND status != 'done'", (today,)).fetchall()]
    conn.close()
    high_priority_count = sum(1 for t in tasks_today if t["priority"] == "high")
    focus_score = max(1, min(10, 10 - len(tasks_today) - (high_priority_count * 2)))
    return {"status": "success", "date": today, "focus_score": focus_score, "tasks_due_today": tasks_today, "tasks_due_tomorrow": tasks_tomorrow, "reminders_today": reminders, "overdue_tasks": overdue, "summary": {"total_due_today": len(tasks_today), "high_priority_today": high_priority_count, "overdue_count": len(overdue), "reminders_count": len(reminders)}}

def update_task_due_date(task_id: str, new_due_date: str) -> dict:
    """Update a task's due date. Format: YYYY-MM-DD HH:MM"""
    conn = get_db()
    conn.execute(
        "UPDATE tasks SET due_date=? WHERE task_id=?",
        (new_due_date, task_id)
    )
    conn.commit()
    conn.close()
    return {
        "status": "success",
        "message": f"Task {task_id} due date updated to {new_due_date}"
    }
    
def analyze_weekly_patterns() -> dict:
    """Analyze task completion patterns for the past week"""
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = get_db()
    completed = conn.execute("SELECT COUNT(*) as count FROM tasks WHERE status='done' AND created_at >= ?", (week_ago,)).fetchone()
    pending = conn.execute("SELECT COUNT(*) as count FROM tasks WHERE status='pending' AND due_date < ?", (datetime.now().strftime("%Y-%m-%d"),)).fetchone()
    total = conn.execute("SELECT COUNT(*) as count FROM tasks WHERE created_at >= ?", (week_ago,)).fetchone()
    conn.close()
    total_count = dict(total)["count"]
    completed_count = dict(completed)["count"]
    completion_rate = round((completed_count / total_count * 100) if total_count > 0 else 0)
    return {"status": "success", "week_summary": {"total_tasks": total_count, "completed": completed_count, "completion_rate_percent": completion_rate, "overdue_tasks": dict(pending)["count"]}, "insight": "Great week!" if completion_rate >= 80 else "Good progress, room to improve" if completion_rate >= 50 else "Many tasks incomplete — consider reducing commitments"}

task_agent = Agent(
    name="task_agent",
    model=model_name,
    description="Manages tasks — create, update, list, and track to-dos and deadlines.",
    instruction="""
    You are the Task Manager for Titan Productivity.
    Use tools to create, update and retrieve tasks.
    Always confirm the action taken clearly.
    Mention the task_id when creating so user can reference it.
    If a task has high priority, acknowledge it with urgency.
    """,
    tools=[create_task, get_tasks, update_task_status, get_tasks_due_today,update_task_due_date]
)

notes_agent = Agent(
    name="notes_agent",
    model=model_name,
    description="Saves and retrieves notes, meeting notes, ideas, and reference material.",
    instruction="""
    You are the Notes Manager for Titan Productivity.
    Use tools to save and search notes.
    Suggest good categories: meeting, idea, reference, personal, work, learning.
    When saving meeting notes, always use the meeting name as the title.
    """,
    tools=[save_note, search_notes, get_recent_notes]
)

reminder_agent = Agent(
    name="reminder_agent",
    model=model_name,
    description="Creates and manages time-based reminders.",
    instruction="""
    You are the Reminder Manager for Titan Productivity.
    Use tools to create and retrieve reminders.
    Always confirm the exact time the reminder is set for.
    Current time: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """
    If user says "in 30 minutes", calculate the actual datetime.
    """,
    tools=[create_reminder, get_upcoming_reminders]
)

# GOOGLE CALENDAR TOOLS (via API)
# ============================================================

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDS_PATH = Path(__file__).parent / "token.pickle"
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"

def get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = None
    if CREDS_PATH.exists():
        with open(CREDS_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(CREDS_PATH, 'wb') as token:
                pickle.dump(creds, token)
        else:
            return None
    return build('calendar', 'v3', credentials=creds)

def get_todays_calendar_events() -> dict:
    """Get all calendar events for today from Google Calendar."""
    service = get_calendar_service()
    if not service:
        return {"status": "not_authenticated", "message": "Calendar not connected. Please authenticate first.", "events": []}
    
    now = datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
    end = now.replace(hour=23, minute=59, second=59).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary',
        timeMin=start,
        timeMax=end,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    formatted = []
    for e in events:
        start_time = e['start'].get('dateTime', e['start'].get('date', ''))
        end_time = e['end'].get('dateTime', e['end'].get('date', ''))
        formatted.append({
            "title": e.get('summary', 'Untitled'),
            "start": start_time,
            "end": end_time,
            "id": e.get('id')
        })
    
    return {"status": "success", "date": now.strftime("%Y-%m-%d"), "events": formatted, "count": len(formatted)}

def create_calendar_event(title: str, start_time: str, end_time: str, description: str = None) -> dict:
    """Create an event in Google Calendar. Times format: YYYY-MM-DDTHH:MM:SS"""
    service = get_calendar_service()
    if not service:
        return {"status": "not_authenticated", "message": "Calendar not connected. Please authenticate first."}
    
    event = {
        'summary': title,
        'description': description or '',
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Kolkata'},
    }
    
    created = service.events().insert(calendarId='primary', body=event).execute()
    return {
        "status": "success",
        "message": f"Event '{title}' created in Google Calendar",
        "event_id": created.get('id'),
        "link": created.get('htmlLink')
    }

def get_free_slots_today() -> dict:
    """Find free time slots in today's calendar."""
    service = get_calendar_service()
    if not service:
        return {"status": "not_authenticated", "message": "Calendar not connected.", "free_slots": []}
    
    now = datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
    end = now.replace(hour=23, minute=59, second=59).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary',
        timeMin=start,
        timeMax=end,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    work_start = now.replace(hour=9, minute=0, second=0)
    work_end = now.replace(hour=18, minute=0, second=0)
    
    busy = []
    for e in events:
        s = e['start'].get('dateTime', '')
        en = e['end'].get('dateTime', '')
        if s and en:
            busy.append((s[:16], en[:16]))
    
    free_slots = []
    if not busy:
        free_slots.append({
            "start": work_start.strftime("%Y-%m-%dT%H:%M"),
            "end": work_end.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": 540
        })
    
    return {"status": "success", "free_slots": free_slots, "busy_count": len(busy)}
# TASK-CALENDAR LINKING TOOLS
# ============================================================

def find_matching_tasks(keyword: str) -> dict:
    """Search for tasks that might match a calendar event by keyword."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM tasks 
           WHERE (title LIKE ? OR description LIKE ?) 
           AND status != 'done'
           ORDER BY priority DESC""",
        (f"%{keyword}%", f"%{keyword}%")
    ).fetchall()
    conn.close()
    return {
        "status": "success",
        "matches": [dict(r) for r in rows],
        "count": len(rows)
    }

def link_event_to_task(task_id: str, calendar_event_id: str, calendar_event_title: str) -> dict:
    """Link a Google Calendar event to an existing task for tracking."""
    conn = get_db()
    conn.execute(
        """UPDATE tasks 
           SET description = COALESCE(description, '') || ' [Calendar: ' || ? || ' | Event ID: ' || ? || ']'
           WHERE task_id = ?""",
        (calendar_event_title, calendar_event_id, task_id)
    )
    conn.commit()
    conn.close()
    return {
        "status": "success",
        "message": f"Calendar event '{calendar_event_title}' linked to task {task_id}",
        "task_id": task_id,
        "event_id": calendar_event_id
    }

def create_task_from_event(calendar_event_title: str, calendar_event_id: str, event_time: str, priority: str = "medium") -> dict:
    """Create a new task linked to a calendar event."""
    conn = get_db()
    task_id = str(uuid.uuid4())[:8]
    description = f"[Calendar: {calendar_event_title} | Event ID: {calendar_event_id}]"
    conn.execute(
        """INSERT INTO tasks 
           (task_id, title, description, priority, due_date, estimated_minutes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (task_id, calendar_event_title, description, priority, event_time, 120)
    )
    conn.commit()
    conn.close()
    return {
        "status": "success",
        "task_id": task_id,
        "message": f"New task '{calendar_event_title}' created and linked to calendar event"
    }

def delete_calendar_event(event_id: str) -> dict:
    """Delete a Google Calendar event by its event ID."""
    service = get_calendar_service()
    if not service:
        return {"status": "not_authenticated", "message": "Calendar not connected."}
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"status": "success", "message": f"Calendar event {event_id} deleted successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def update_calendar_event(event_id: str, new_title: str = None, new_start: str = None, new_end: str = None) -> dict:
    """Update an existing Google Calendar event. Times format: YYYY-MM-DDTHH:MM:SS"""
    service = get_calendar_service()
    if not service:
        return {"status": "not_authenticated", "message": "Calendar not connected."}
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        if new_title:
            event['summary'] = new_title
        if new_start:
            event['start'] = {'dateTime': new_start, 'timeZone': 'Asia/Kolkata'}
        if new_end:
            event['end'] = {'dateTime': new_end, 'timeZone': 'Asia/Kolkata'}
        updated = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return {
            "status": "success",
            "message": f"Calendar event updated successfully",
            "event_id": updated.get('id'),
            "link": updated.get('htmlLink')
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


planner_agent = Agent(
    name="planner_agent",
    model=model_name,
    description="Creates intelligent day plans, detects conflicts, suggests focus blocks, and provides morning briefings.",
    instruction="""
    You are the Intelligence Planner for Titan — the most powerful agent.

    MORNING BRIEFING (triggered by "good morning" or "plan my day"):
    - Call get_morning_briefing_data for tasks and reminders
    - Call get_todays_calendar_events for real calendar events
    - Present: Focus Score, calendar events, tasks due today, overdue items, reminders
    - Detect conflicts between tasks and calendar events
    - Offer to schedule focus blocks

    CONFLICT DETECTION:
    - Call get_todays_calendar_events to get real calendar
    - Call get_tasks_due_today to get tasks
    - Call detect_scheduling_conflicts with both
    - Warn about risks proactively

    FOCUS BLOCKS:
    - Call get_free_slots_today to find real free time
    - Call suggest_focus_blocks with free slots and pending tasks
    - Call create_calendar_event to actually add focus blocks to Google Calendar
    - High priority tasks → morning slots
    - Always leave lunch 1-2pm free
    - Max 3 hours deep work without break

    WEEKLY REVIEW:
    - Call analyze_weekly_patterns
    - Give honest assessment and improvement tips

    SCHEDULING:
    - When user asks to schedule something → call create_calendar_event
    - Always confirm event was created with the calendar link

    WHEN TASK DATE CHANGES:
    - After update_task_due_date is called, call get_todays_calendar_events
    - Check if any event title contains the task title
    - If yes: ask "I also see '[event title]' on your calendar. Should I move that focus block to the new date too?"
    - If yes: call update_calendar_event with the new datetime
    - This keeps tasks and calendar in perfect sync

    TASK-CALENDAR LINKING (after creating any calendar event):
    - Call find_matching_tasks with keywords from the event title
    - If matches found (count > 0):
      Ask user: "I found [count] matching task(s): '[task title]'. 
      Should I: (1) Link this event to it, (2) Create a new task, or (3) Leave unlinked?"
    - If user says link → call link_event_to_task
    - If user says new task → call create_task_from_event  
    - If user says leave/no → confirm event was created, move on
    - If no matches found:
      Ask user: "No matching tasks found. Should I create a new task to track this?"
    - If yes → call create_task_from_event

    Be proactive. Speak like a brilliant chief of staff.
    Direct, smart, caring. Flag problems before user notices.
    """,
    tools=[
        get_morning_briefing_data,
        detect_scheduling_conflicts,
        suggest_focus_blocks,
        analyze_weekly_patterns,
        get_tasks_due_today,
        get_upcoming_reminders,
        get_todays_calendar_events,
        create_calendar_event,
        get_free_slots_today,
        find_matching_tasks,
        link_event_to_task,
        create_task_from_event,
        delete_calendar_event,
        update_calendar_event
    ]
)

root_agent = Agent(
    name="titan_orchestrator",
    model=model_name,
    description="Titan — your personal AI productivity operating system.",
    instruction="""
    You are Titan, an intelligent personal productivity assistant.
    Calm, direct, smart, proactive — like a brilliant chief of staff.

    ROUTING RULES:
    → task_agent: tasks, todos, deadlines, projects
    → notes_agent: saving or finding notes and information
    → reminder_agent: time-based reminders and alerts
    → planner_agent: day planning, morning briefing, conflicts, focus time, weekly review

    IMPORTANT:
    - "good morning" or "plan my day" → planner_agent immediately
    - task + time mentioned → task first, then reminder
    - "what should I work on" → planner_agent
    - Always be concise — max 3 sentences in your own responses
    - Never say "I can't" — always find a way

    You are Titan. Make their day effortless.
    """,
    sub_agents=[task_agent, notes_agent, reminder_agent, planner_agent]
)

# ============================================================



# ============================================================





import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams, StdioServerParameters
from google.adk.tools.tool_context import ToolContext
from google.genai.types import SpeechConfig, VoiceConfig, PrebuiltVoiceConfig, GenerateContentConfig

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
        CREATE TABLE IF NOT EXISTS people (
            person_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            relationship TEXT DEFAULT 'contact',
            company TEXT,
            last_interaction TEXT,
            notes TEXT,
            follow_up TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS habits (
            habit_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            frequency TEXT DEFAULT 'daily',
            last_done TEXT,
            streak INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS weekly_goals (
            goal_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            week_start TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ============================================================
# DEMO SEED DATA — runs on every fresh container
# ============================================================

def seed_demo_data():
    """Seed realistic demo data if database is empty."""
    conn = get_db()
    task_count = dict(conn.execute("SELECT COUNT(*) as c FROM tasks").fetchone())["c"]
    if task_count > 0:
        conn.close()
        return

    now = datetime.now()

    tasks = [
        ("t001", "Prepare Q2 strategy presentation", "Slides for leadership review", "high",
         now.strftime("%Y-%m-%d") + " 17:00", "Strategy", 120),
        ("t002", "Review product roadmap with team", None, "high",
         now.strftime("%Y-%m-%d") + " 15:00", "Product", 60),
        ("t003", "Send weekly status update to manager", None, "medium",
         now.strftime("%Y-%m-%d") + " 18:00", "Communication", 30),
        ("t004", "Follow up with Rahul on API integration", None, "medium",
         (now + timedelta(days=1)).strftime("%Y-%m-%d") + " 12:00", "Engineering", 45),
        ("t005", "Review Q1 OKR completion report", None, "low",
         (now + timedelta(days=2)).strftime("%Y-%m-%d") + " 17:00", "Planning", 90),
    ]
    for t in tasks:
        conn.execute("INSERT OR IGNORE INTO tasks (task_id, title, description, priority, due_date, project, estimated_minutes) VALUES (?,?,?,?,?,?,?)", t)

    notes = [
        ("n001", "Q2 Strategy Meeting Notes",
         "Discussed expansion into APAC market. Key decision: prioritize Singapore and Australia. Rahul to lead technical assessment. Budget approved: $500K. Next review in 2 weeks.",
         "meeting", "strategy,Q2,APAC"),
        ("n002", "Product Roadmap Ideas",
         "Voice interface for mobile app. AI-powered conflict detection. AlloyDB integration for semantic search. Real-time collaboration features.",
         "idea", "product,roadmap"),
        ("n003", "1:1 with Manager - Key Takeaways",
         "Focus on delivery speed this quarter. Manager wants weekly updates every Friday. Stretch goal: ship 3 features by end of month. Promotion review in Q3.",
         "meeting", "manager,career"),
        ("n004", "System Architecture Reference",
         "ADK multi-agent pattern: orchestrator routes to sub-agents. Each agent has specific tools. MCP for external integrations. SQLite for local, AlloyDB for production.",
         "reference", "architecture,ADK"),
        ("n005", "Personal Goals This Quarter",
         "Read 2 books on system design. Exercise 4x per week. Call parents every Sunday. Learn Spanish 15 mins daily.",
         "personal", "goals,personal"),
    ]
    for n in notes:
        conn.execute("INSERT OR IGNORE INTO notes (note_id, title, content, category, tags) VALUES (?,?,?,?,?)", n)

    people = [
        ("p001", "Rahul Sharma", "work", "TechCorp",
         (now - timedelta(days=3)).strftime("%Y-%m-%d"),
         "Engineering lead. Prefers concise technical updates. Working on API integration.",
         "Follow up on API integration timeline"),
        ("p002", "Priya Mehta", "work", "TechCorp",
         (now - timedelta(days=1)).strftime("%Y-%m-%d"),
         "Product manager. Very detail-oriented. Likes visual roadmaps.",
         None),
        ("p003", "Arjun Kapoor", "personal", None,
         (now - timedelta(days=21)).strftime("%Y-%m-%d"),
         "College friend. Lives in Mumbai. Been meaning to catch up.",
         "Call this weekend"),
        ("p004", "Sarah Chen", "work", "PartnerCo",
         (now - timedelta(days=7)).strftime("%Y-%m-%d"),
         "Business development contact. Interested in partnership proposal.",
         "Send partnership deck by end of week"),
    ]
    for p in people:
        conn.execute("INSERT OR IGNORE INTO people (person_id, name, relationship, company, last_interaction, notes, follow_up) VALUES (?,?,?,?,?,?,?)", p)

    habits = [
        ("h001", "Drink water", "daily", None, 0),
        ("h002", "Exercise", "daily", None, 0),
        ("h003", "Read for 20 mins", "daily",
         (now - timedelta(days=1)).strftime("%Y-%m-%d"), 3),
        ("h004", "Call parents", "weekly", None, 0),
    ]
    for h in habits:
        conn.execute("INSERT OR IGNORE INTO habits (habit_id, name, frequency, last_done, streak) VALUES (?,?,?,?,?)", h)

    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    goals = [
        ("g001", "Ship Q2 strategy presentation", "active", week_start),
        ("g002", "Complete API integration review with Rahul", "active", week_start),
        ("g003", "Exercise at least 3 times", "active", week_start),
    ]
    for g in goals:
        conn.execute("INSERT OR IGNORE INTO weekly_goals (goal_id, title, status, week_start) VALUES (?,?,?,?)", g)

    conn.commit()
    conn.close()



def get_current_time_str():
    """Returns current IST time dynamically."""
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    return now.strftime("%A, %B %d, %Y at %I:%M %p IST")

def get_current_datetime() -> dict:
    """Get the real current date and time in IST. Always call this when user asks about time or current date."""
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    return {
        "current_time": now.strftime("%I:%M %p"),
        "current_date": now.strftime("%A, %B %d, %Y"),
        "timezone": "IST (UTC+5:30)",
        "iso": now.isoformat()
    }

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

import uuid

seed_demo_data()

def create_task(title: str, priority: str = "medium", due_date: str = None, description: str = None, project: str = None, estimated_minutes: int = 60, force_create: bool = False) -> dict:
    """Creates a new task. Priority: low/medium/high. due_date format: YYYY-MM-DD HH:MM. Set force_create=True to skip duplicate check."""
    conn = get_db()
    if not force_create:
        words = [w for w in title.lower().split() if len(w) > 3]
        similar = []
        for word in words:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE LOWER(title) LIKE ? AND status != 'done'",
                (f"%{word}%",)
            ).fetchall()
            for row in rows:
                d = dict(row)
                if d['task_id'] not in [s['task_id'] for s in similar]:
                    similar.append(d)
        if similar:
            conn.close()
            options = []
            for i, t in enumerate(similar[:3]):
                options.append(f"SIMILAR_{chr(65+i)} — '{t['title']}' ({t['priority']} priority, due: {t['due_date'] or 'no date'})")
            return {
                "status": "duplicate_check",
                "message": f"I found {len(similar)} similar task(s) already:",
                "similar_tasks": similar[:3],
                "options": options,
                "instructions": "Reply with: " + " | ".join([f"SIMILAR_{chr(65+i)} to link/view" for i in range(len(similar[:3]))]) + " | NEW to create anyway | CANCEL to abort"
            }
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

VALID_CATEGORIES = ["meeting", "task", "idea", "reference", "personal", "work", "learning", "general"]

def infer_category(title: str, content: str) -> str:
    """Infer note category from content."""
    text = (title + " " + content).lower()
    if any(w in text for w in ["meeting", "call", "discussed", "attendees", "agenda"]): return "meeting"
    if any(w in text for w in ["learn", "study", "codelab", "course", "tutorial"]): return "learning"
    if any(w in text for w in ["idea", "what if", "maybe", "concept", "brainstorm"]): return "idea"
    if any(w in text for w in ["reference", "docs", "link", "resource", "guide"]): return "reference"
    if any(w in text for w in ["personal", "family", "health", "gym", "finance"]): return "personal"
    if any(w in text for w in ["work", "project", "client", "deadline", "team"]): return "work"
    return "general"

def save_note(title: str, content: str, category: str = None, tags: str = None, force_create: bool = False) -> dict:
    """Save a note with title, content, optional category and tags. Set force_create=True to skip duplicate check."""
    conn = get_db()
    if not force_create and title:
        existing = conn.execute(
            "SELECT * FROM notes WHERE LOWER(title) LIKE ? ORDER BY created_at DESC LIMIT 3",
            (f"%{title.lower()[:15]}%",)
        ).fetchall()
        if existing:
            similar = [dict(r) for r in existing]
            conn.close()
            options = []
            for i, n in enumerate(similar[:3]):
                options.append(f"SIMILAR_{chr(65+i)} — '{n['title']}' (saved {n['created_at'][:10]})")
            return {
                "status": "duplicate_check",
                "message": f"I found {len(similar)} similar note(s):",
                "similar_notes": similar[:3],
                "options": options,
                "instructions": "Reply with: " + " | ".join([f"SIMILAR_{chr(65+i)} to view existing" for i in range(len(similar[:3]))]) + " | NEW to save anyway | CANCEL to abort"
            }
    if not category or category not in VALID_CATEGORIES:
        category = infer_category(title or "", content)
    note_id = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO notes (note_id, title, content, category, tags) VALUES (?, ?, ?, ?, ?)", (note_id, title, content, category, tags))
    conn.commit()
    conn.close()
    return {"status": "success", "note_id": note_id, "message": f"Note '{title}' saved under category: {category}"}

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
    instruction=f"""
    Today is {datetime.now().strftime("%A, %B %d, %Y")}. Current time: {datetime.now().strftime("%I:%M %p")} IST.
    You are the Task Manager for Titan Productivity.

    CRITICAL: When calling create_task, ALWAYS pass the task name as the 'title' parameter.
    NEVER put the task name in 'description'. Description is optional extra detail only.
    Example: "add task to finish report" → title="finish report", description=None

    When create_task returns status "duplicate_check":
    - Show the similar items clearly
    - Show options EXACTLY using SIMILAR_A/NEW/CANCEL labels
    - If SIMILAR_A → confirm existing task, do not create new
    - If NEW → call create_task again with force_create=True
    - If CANCEL → confirm cancelled

    Always confirm action and mention task_id when creating.
    If high priority, acknowledge with urgency.
    """,
    tools=[create_task, get_tasks, update_task_status, get_tasks_due_today, update_task_due_date,get_current_datetime]
)

notes_agent = Agent(
    name="notes_agent",
    model=model_name,
    description="Saves and retrieves notes, meeting notes, ideas, and reference material.",
    instruction="""
    Today's date is {datetime.now().strftime("%A, %B %d, %Y")}. Current time is {datetime.now().strftime("%I:%M %p")} IST.
    You are the Notes Manager for Titan Productivity.
    Use tools to save and search notes.
    Suggest good categories: meeting, idea, reference, personal, work, learning.
    When saving meeting notes, always use the meeting name as the title.
    """,
    tools=[save_note, search_notes, get_recent_notes,get_current_datetime]
)

reminder_agent = Agent(
    name="reminder_agent",
    model=model_name,
    description="Creates and manages time-based reminders.",
    instruction="""
    Today's date is {datetime.now().strftime("%A, %B %d, %Y")}. Current time is {datetime.now().strftime("%I:%M %p")} IST.
    You are the Reminder Manager for Titan Productivity.
    Use tools to create and retrieve reminders.
    Always confirm the exact time the reminder is set for.
    Current time: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """
    If user says "in 30 minutes", calculate the actual datetime.
    """,
    tools=[create_reminder, get_upcoming_reminders,get_current_datetime]
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

def create_calendar_event(title: str, start_time: str, end_time: str, description: str = None, is_tracking: bool = False) -> dict:
    """Create an event in Google Calendar. Times format: YYYY-MM-DDTHH:MM:SS. Set is_tracking=True for past events added for tracking only."""
    service = get_calendar_service()
    if not service:
        return {"status": "not_authenticated", "message": "Calendar not connected. Please authenticate first."}
    
    try:
        event_start = datetime.fromisoformat(start_time.replace("Z", ""))
        now = datetime.now()
        if event_start < now and not is_tracking:
            return {
                "status": "past_time_error",
                "requested_time": start_time,
                "current_time": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "message": f"The time {event_start.strftime('%I:%M %p')} has already passed today.",
                "options": [
                    f"TOMORROW — Schedule for tomorrow at {event_start.strftime('%I:%M %p')}",
                    "TRACKING — Add as a past tracking event (for reference only)",
                    "DIFFERENT — Choose a different time"
                ],
                "instructions": "Reply with TOMORROW, TRACKING, or DIFFERENT to proceed"
            }
        if is_tracking:
            title = f"[TRACKED] {title}"
            description = (description or "") + "\n\n[Added for tracking — this event occurred in the past]"
    except Exception as e:
        pass

    event = {
        'summary': title,
        'description': description or '',
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Kolkata'},
    }
    
    created = service.events().insert(calendarId='primary', body=event).execute()
    tracking_note = " (added as tracking event)" if is_tracking else ""
    return {
        "status": "success",
        "message": f"Event '{title}' created in Google Calendar{tracking_note}",
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
    """Search for tasks matching a calendar event keyword. Returns fixed label options to avoid numbering ambiguity."""
    conn = get_db()
    keywords = keyword.lower().split()
    all_matches = {}
    for kw in keywords:
        if len(kw) > 3:
            rows = conn.execute(
                """SELECT * FROM tasks 
                   WHERE (LOWER(title) LIKE ? OR LOWER(description) LIKE ?) 
                   AND status != 'done'""",
                (f"%{kw}%", f"%{kw}%")
            ).fetchall()
            for row in rows:
                d = dict(row)
                all_matches[d['task_id']] = d
    conn.close()
    matches = list(all_matches.values())
    matches.sort(key=lambda x: 0 if x['priority'] == 'high' else 1)
    
    options = []
    for i, t in enumerate(matches[:3]):
        label = chr(65 + i)
        options.append(f"LINK {label} — link to '{t['title']}' ({t['priority']} priority)")
    options.append("NEW — create a new task for this event")
    options.append("SKIP — leave event unlinked")
    
    return {
        "status": "success",
        "matches": matches[:3],
        "count": len(matches),
        "options": options,
        "instructions": ("Reply with: " + " | ".join([f"LINK {chr(65+i)}" for i in range(min(len(matches),3))]) + " | NEW | SKIP") if matches else "Reply with: NEW | SKIP"
    }

def link_event_to_task(task_id: str, calendar_event_id: str, calendar_event_title: str) -> dict:
    """Link a Google Calendar event to an existing task. Stores the calendar event reference in the task so both are trackable together."""
    conn = get_db()
    conn.execute(
        """UPDATE tasks 
           SET description = COALESCE(description, '') || ' [Linked Calendar: ' || ? || ' | ID: ' || ? || ']'
           WHERE task_id = ?""",
        (calendar_event_title, calendar_event_id, task_id)
    )
    conn.commit()
    task = conn.execute("SELECT title FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    conn.close()
    return {
        "status": "success",
        "message": f"Linked! The calendar event is now connected to your task. This means the calendar event ID is stored in the task — when you view the task you can see which calendar block is dedicated to it.",
        "task_id": task_id,
        "task_title": dict(task)["title"] if task else "unknown",
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
    instruction=f"""
    Today is {datetime.now().strftime("%A, %B %d, %Y")}. Current time: {datetime.now().strftime("%I:%M %p")} IST.
    Tomorrow is {(datetime.now() + timedelta(days=1)).strftime("%A, %B %d, %Y")}.
    Current year: {datetime.now().year}. Today's date string: {datetime.now().strftime("%Y-%m-%d")}.

    CRITICAL DATE RULE: When creating calendar events:
    - "today at 5pm" = {datetime.now().strftime("%Y-%m-%d")}T17:00:00
    - "tomorrow at 9am" = {(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")}T09:00:00
    - NEVER use years 2023 or 2024 — always use {datetime.now().year}
    - Always double-check the year before calling create_calendar_event

    You are the Intelligence Planner for Titan — the most powerful agent.

    MORNING BRIEFING (triggered by "good morning" or "plan my day"):
    ALWAYS call ALL of these in sequence:
    1. get_morning_briefing_data — tasks, reminders, focus score
    2. get_todays_calendar_events — real calendar
    3. get_relationship_health — who needs attention
    4. get_wellness_summary — habit status and nudges
    5. get_pending_followups — outstanding commitments
    6. detect_scheduling_conflicts — proactive conflict warning

    THEN present a complete briefing:
    - Focus Score with explanation
    - Calendar events for today
    - Tasks due today (HIGH priority first)
    - Overdue items with urgency
    - PROACTIVE RELATIONSHIP ALERT: "You haven't contacted [name] in [X] days — want me to add a reminder?"
    - PROACTIVE FOLLOW-UP ALERT: "You have [X] pending follow-ups — [name]: [what]"
    - PROACTIVE HABIT ALERT: "Your [habit] streak is at risk today"
    - 1 specific wellness nudge based on time of day
    - If meetings today → offer meeting prep brief
    - Offer to schedule focus blocks for high priority tasks

    BE PROACTIVE — don't wait to be asked. Surface insights the user didn't know to ask for.
    FLAG RISKS before they become problems.
    CONNECT THE DOTS — if Rahul has a follow-up AND a task about API integration, mention both together.

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
    - Show the user the options EXACTLY as returned in the "options" field
    - Wait for user response using the FIXED LABELS (LINK A, LINK B, NEW, SKIP)
    - If user says "LINK A" → call link_event_to_task with the first match task_id
    - If user says "LINK B" → call link_event_to_task with the second match task_id
    - If user says "NEW" → call create_task_from_event
    - If user says "SKIP" or "leave" or "no" → confirm event created, move on
    - NEVER use numbered options (1/2/3) — always use the label system (LINK A/B/NEW/SKIP)
    - If no matches found: ask "No matching tasks found. Reply NEW to create a tracking task or SKIP to leave unlinked"

    CALENDAR PAST EVENT HANDLING:
    - If create_calendar_event returns status "past_time_error":
      Show the user the options EXACTLY as returned in "options" field
      Wait for: TOMORROW / TRACKING / DIFFERENT
      - TOMORROW: recalculate start/end times for next day, call create_calendar_event again
      - TRACKING: call create_calendar_event again with is_tracking=True
      - DIFFERENT: ask user what time they prefer

    DUPLICATE HANDLING:
    - If create_task or save_note returns status "duplicate_check":
      Show similar items found and the options field EXACTLY
      Wait for: SIMILAR_A / SIMILAR_B / NEW / CANCEL
      - SIMILAR_A/B: inform user of existing item details, ask if they want to update it
      - NEW: call the function again with force_create=True
      - CANCEL: confirm cancelled, move on

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
        update_calendar_event,
        get_current_datetime
    ]
)


# ============================================================
# PEOPLE & RELATIONSHIP TOOLS
# ============================================================

def add_person(name: str, relationship: str = "contact", company: str = None, notes: str = None) -> dict:
    """Add or update a person in the relationship tracker."""
    conn = get_db()
    existing = conn.execute("SELECT * FROM people WHERE LOWER(name) LIKE ?", (f"%{name.lower()}%",)).fetchone()
    if existing:
        conn.execute("UPDATE people SET relationship=?, company=?, notes=?, last_interaction=? WHERE person_id=?",
            (relationship, company or dict(existing)["company"], notes or dict(existing)["notes"],
             datetime.now().strftime("%Y-%m-%d"), dict(existing)["person_id"]))
        conn.commit()
        conn.close()
        return {"status": "updated", "message": f"Updated {name} in your network"}
    person_id = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO people (person_id, name, relationship, company, notes, last_interaction) VALUES (?,?,?,?,?,?)",
        (person_id, name, relationship, company, notes, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    return {"status": "success", "person_id": person_id, "message": f"{name} added to your network as {relationship}"}

def get_person(name: str) -> dict:
    """Get information about a person from your network."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM people WHERE LOWER(name) LIKE ?", (f"%{name.lower()}%",)).fetchall()
    conn.close()
    if not rows:
        return {"status": "not_found", "message": f"No one named {name} found in your network"}
    people = [dict(r) for r in rows]
    return {"status": "success", "people": people, "count": len(people)}

def log_interaction(name: str, interaction_notes: str, follow_up: str = None) -> dict:
    """Log an interaction with someone and optionally set a follow-up."""
    conn = get_db()
    existing = conn.execute("SELECT * FROM people WHERE LOWER(name) LIKE ?", (f"%{name.lower()}%",)).fetchone()
    if not existing:
        conn.close()
        return {"status": "not_found", "message": f"Add {name} to your network first"}
    p = dict(existing)
    updated_notes = (p["notes"] or "") + f"\n[{datetime.now().strftime('%Y-%m-%d')}] {interaction_notes}"
    conn.execute("UPDATE people SET last_interaction=?, notes=?, follow_up=? WHERE person_id=?",
        (datetime.now().strftime("%Y-%m-%d"), updated_notes, follow_up, p["person_id"]))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Interaction with {name} logged", "follow_up": follow_up}

def get_relationship_health() -> dict:
    """Check relationship health — who you haven't talked to recently."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM people ORDER BY last_interaction ASC").fetchall()
    conn.close()
    people = [dict(r) for r in rows]
    now = datetime.now()
    neglected = []
    healthy = []
    for p in people:
        if p["last_interaction"]:
            last = datetime.strptime(p["last_interaction"], "%Y-%m-%d")
            days_ago = (now - last).days
            p["days_since_contact"] = days_ago
            if days_ago > 14:
                neglected.append(p)
            else:
                healthy.append(p)
    return {
        "status": "success",
        "neglected_relationships": neglected[:5],
        "healthy_relationships": healthy[:5],
        "total_in_network": len(people),
        "nudge": f"You have {len(neglected)} relationship(s) that need attention" if neglected else "Your relationships are healthy!"
    }

def get_pending_followups() -> dict:
    """Get all pending follow-ups with people."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM people WHERE follow_up IS NOT NULL AND follow_up != ''").fetchall()
    conn.close()
    return {"status": "success", "follow_ups": [dict(r) for r in rows], "count": len(rows)}

# ============================================================
# WELLNESS & HABIT TOOLS
# ============================================================

def add_habit(name: str, frequency: str = "daily") -> dict:
    """Add a new habit to track."""
    conn = get_db()
    existing = conn.execute("SELECT * FROM habits WHERE LOWER(name) LIKE ?", (f"%{name.lower()}%",)).fetchone()
    if existing:
        conn.close()
        return {"status": "exists", "message": f"Habit '{name}' already being tracked"}
    habit_id = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO habits (habit_id, name, frequency) VALUES (?,?,?)", (habit_id, name, frequency))
    conn.commit()
    conn.close()
    return {"status": "success", "habit_id": habit_id, "message": f"Now tracking habit: {name} ({frequency})"}

def log_habit(name: str) -> dict:
    """Mark a habit as done today."""
    conn = get_db()
    existing = conn.execute("SELECT * FROM habits WHERE LOWER(name) LIKE ?", (f"%{name.lower()}%",)).fetchone()
    if not existing:
        conn.close()
        return {"status": "not_found", "message": f"Habit '{name}' not found. Add it first."}
    h = dict(existing)
    today = datetime.now().strftime("%Y-%m-%d")
    new_streak = h["streak"] + 1 if h["last_done"] == (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d") else 1
    conn.execute("UPDATE habits SET last_done=?, streak=? WHERE habit_id=?", (today, new_streak, h["habit_id"]))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Habit '{name}' logged! Streak: {new_streak} day(s) 🔥"}

def get_wellness_summary() -> dict:
    """Get today's wellness summary — habits, streaks, and nudges."""
    conn = get_db()
    habits = [dict(r) for r in conn.execute("SELECT * FROM habits").fetchall()]
    conn.close()
    today = datetime.now().strftime("%Y-%m-%d")
    done_today = [h for h in habits if h["last_done"] == today]
    pending = [h for h in habits if h["last_done"] != today]
    hour = datetime.now().hour
    nudges = []
    if hour >= 13 and hour <= 15:
        nudges.append("🍽️ Have you had lunch? Don't skip meals!")
    if hour >= 10:
        nudges.append("💧 Time to drink water — stay hydrated!")
    if hour >= 20:
        nudges.append("📵 Consider winding down screens before bed")
    if datetime.now().weekday() == 6:
        nudges.append("👨‍👩‍👧 It's Sunday — great time to call family!")
    if datetime.now().weekday() == 4 and hour >= 17:
        nudges.append("🧹 Friday evening — good time to clean up your digital workspace!")
    return {
        "status": "success",
        "habits_done_today": done_today,
        "habits_pending": pending,
        "nudges": nudges,
        "wellness_score": int((len(done_today) / max(len(habits), 1)) * 100) if habits else 100
    }

# ============================================================
# WEEKLY & MONTHLY INTELLIGENCE TOOLS
# ============================================================

def get_weeks_calendar_events() -> dict:
    """Get all calendar events for the current week grouped by day."""
    service = get_calendar_service()
    if not service:
        return {"status": "not_authenticated", "message": "Calendar not connected.", "events_by_day": {}}
    now = datetime.now()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=7)
    events_result = service.events().list(
        calendarId="primary",
        timeMin=week_start.isoformat() + "+05:30",
        timeMax=week_end.isoformat() + "+05:30",
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])
    by_day = {}
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        end = e["end"].get("dateTime", e["end"].get("date", ""))
        day = datetime.fromisoformat(start[:10]).strftime("%A %b %d") if start else "Unknown"
        if day not in by_day:
            by_day[day] = []
        by_day[day].append({"title": e.get("summary", "Untitled"), "start": start, "end": end, "id": e.get("id")})
    return {
        "status": "success",
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
        "events_by_day": by_day,
        "total_events": len(events),
        "busiest_day": max(by_day, key=lambda d: len(by_day[d])) if by_day else "No events",
        "free_days": [d for d in ["Monday","Tuesday","Wednesday","Thursday","Friday"] if not any(d in k for k in by_day)]
    }

def get_meeting_prep_brief(meeting_title: str) -> dict:
    """Get a preparation brief for an upcoming meeting — pulls related notes and people."""
    conn = get_db()
    keywords = [w for w in meeting_title.lower().split() if len(w) > 3]
    related_notes = []
    related_people = []
    for kw in keywords:
        notes = conn.execute("SELECT * FROM notes WHERE LOWER(title) LIKE ? OR LOWER(content) LIKE ? ORDER BY created_at DESC LIMIT 3",
            (f"%{kw}%", f"%{kw}%")).fetchall()
        people = conn.execute("SELECT * FROM people WHERE LOWER(name) LIKE ? OR LOWER(notes) LIKE ?",
            (f"%{kw}%", f"%{kw}%")).fetchall()
        for n in notes:
            d = dict(n)
            if d["note_id"] not in [x["note_id"] for x in related_notes]:
                related_notes.append(d)
        for p in people:
            d = dict(p)
            if d["person_id"] not in [x["person_id"] for x in related_people]:
                related_people.append(d)
    conn.close()
    return {
        "status": "success",
        "meeting": meeting_title,
        "related_notes": related_notes[:3],
        "related_people": related_people[:3],
        "prep_summary": f"Found {len(related_notes)} related note(s) and {len(related_people)} known attendee(s)",
        "tip": "Review your notes before the meeting and check any pending follow-ups with attendees"
    }

def set_weekly_goal(title: str) -> dict:
    """Set a goal for this week."""
    conn = get_db()
    goal_id = str(uuid.uuid4())[:8]
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    conn.execute("INSERT INTO weekly_goals (goal_id, title, week_start) VALUES (?,?,?)", (goal_id, title, week_start))
    conn.commit()
    conn.close()
    return {"status": "success", "goal_id": goal_id, "message": f"Weekly goal set: {title}"}

def get_weekly_goals() -> dict:
    """Get this week's goals."""
    conn = get_db()
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    rows = conn.execute("SELECT * FROM weekly_goals WHERE week_start = ?", (week_start,)).fetchall()
    conn.close()
    return {"status": "success", "goals": [dict(r) for r in rows], "count": len(rows)}

# ============================================================
# WELLNESS AGENT
# ============================================================
wellness_agent = Agent(
    name="wellness_agent",
    model=model_name,
    description="Tracks habits, wellness nudges, hydration, food, digital hygiene, and work-life balance.",
    instruction=f"""
    Today is {datetime.now().strftime("%A, %B %d, %Y")}. Time: {datetime.now().strftime("%I:%M %p")} IST.
    You are Titan's Wellness Guardian.

    HABIT TRACKING:
    - Add habits: add_habit (name, frequency)
    - Log completion: log_habit (name)
    - Review: get_wellness_summary

    NUDGE PHILOSOPHY:
    - Be warm, not preachy. One nudge at a time.
    - Celebrate streaks enthusiastically
    - Suggest specific actions: "Drink a glass of water now" not "stay hydrated"
    - Digital hygiene suggestions: clear downloads, empty trash, unsubscribe emails, delete old screenshots
    - Social health: suggest calling family on weekends, checking in with friends
    - Physical health: lunch reminders, water, stretching after long work sessions

    Always get_wellness_summary first to know what's already done today.
    """,
    tools=[add_habit, log_habit, get_wellness_summary, create_reminder,get_current_datetime]
)

# ============================================================
# PEOPLE AGENT
# ============================================================
people_agent = Agent(
    name="people_agent",
    model=model_name,
    description="Tracks relationships, logs interactions, manages follow-ups, and monitors relationship health.",
    instruction=f"""
    Today is {datetime.now().strftime("%A, %B %d, %Y")}. Time: {datetime.now().strftime("%I:%M %p")} IST.
    You are Titan's Relationship Intelligence layer.

    PEOPLE TRACKING:
    - Add someone: add_person (name, relationship, company, notes)
    - Get info: get_person (name)
    - Log interaction: log_interaction (name, notes, follow_up)
    - Health check: get_relationship_health
    - Follow-ups: get_pending_followups

    RELATIONSHIP TYPES: work, personal, family, mentor, client, friend, acquaintance

    PROACTIVE BEHAVIOR:
    - When user mentions a name in any context, check if they're in the network
    - After logging interactions, always ask if there are follow-up commitments
    - Surface neglected relationships proactively during morning briefings
    - Track promises made: "I'll send you the report by Friday"
    - Map org relationships: who reports to whom, who influences whom

    Always be specific about relationship context — not just "contact" but "client at Acme Corp, met at conference".
    """,
    tools=[add_person, get_person, log_interaction, get_relationship_health, get_pending_followups, search_notes,get_current_datetime]
)

# ============================================================
# BRIEF AGENT
# ============================================================
brief_agent = Agent(
    name="brief_agent",
    model=model_name,
    description="Generates meeting prep briefs, weekly summaries, monthly reviews, and manager updates.",
    instruction=f"""
    Today is {datetime.now().strftime("%A, %B %d, %Y")}. Time: {datetime.now().strftime("%I:%M %p")} IST.
    You are Titan's Intelligence Briefing system.

    MEETING PREP (triggered by "prepare for", "brief me on", "what do I know about [meeting]"):
    - Call get_meeting_prep_brief with meeting title
    - Pull related notes, people, previous decisions
    - Format as: Context, Key People, Previous Discussions, Action Items to Review, Suggested talking points

    WEEKLY SUMMARY (triggered by "how was my week", "weekly review"):
    - Call get_weeks_calendar_events for meeting overview
    - Call analyze_weekly_patterns for task completion
    - Call get_relationship_health for people check
    - Call get_wellness_summary for habits
    - Format as: Wins, Misses, Relationships, Wellness, Next Week Focus

    MONTHLY REVIEW (triggered by "monthly review", "how was this month"):
    - Analyze patterns across tasks, meetings, relationships
    - Identify recurring blockers and wins
    - Suggest one habit to add and one commitment to drop

    MANAGER UPDATE (triggered by "write my weekly update", "status update"):
    - Pull completed tasks from get_tasks
    - Pull meetings from get_weeks_calendar_events
    - Format as professional bullet-point update

    NEXT WEEK PLANNING (triggered by "how does next week look", "plan next week"):
    - Call get_weeks_calendar_events
    - Identify free slots and busy days
    - Suggest optimal times for deep work, meetings, and rest
    - Flag any overcommitment risks

    Always synthesize across multiple data sources for rich, contextual briefs.
    """,
    tools=[get_meeting_prep_brief, get_weeks_calendar_events, analyze_weekly_patterns,
           get_relationship_health, get_wellness_summary, get_tasks, search_notes,
           get_weekly_goals, set_weekly_goal,get_current_datetime]
)


# MCP Toolset — Notes server exposed via MCP protocol
notes_mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="python3",
            args=[str(Path(__file__).parent / "notes_mcp_server.py")]
        )
    )
)

root_agent = Agent(
    name="titan_orchestrator",
    model="gemini-2.5-flash",
    description="Titan — your personal AI productivity operating system.",
    instruction="""
    Today\'s date is {datetime.now().strftime("%A, %B %d, %Y")}. Current time is {datetime.now().strftime("%I:%M %p")} IST.

    You are Titan, an intelligent personal productivity assistant.
    Calm, direct, smart, proactive — like a brilliant chief of staff.

    ROUTING RULES:
    → task_agent: tasks, todos, deadlines, projects
    → notes_agent: saving or finding notes and information
    → reminder_agent: time-based reminders and alerts
    → planner_agent: day planning, morning briefing, conflicts, focus time, calendar events
    → wellness_agent: habits, water, food, exercise, digital hygiene, work-life balance, streaks
    → people_agent: relationships, contacts, interactions, follow-ups, network health
    → brief_agent: meeting prep, weekly summary, monthly review, manager updates, next week planning

    WHEN ASKED "what can you do" or "how can you help" or similar capability questions:
    ALWAYS respond with EXACTLY this text — each feature on its own line:
    Hello! I am Titan, your personal AI productivity operating system.

    Here is what I can do for you:

    📅 Calendar and Planning — Check your schedule, detect conflicts, create focus blocks, and give you a smart morning briefing

    ✅ Task Management — Create, track, and update tasks with priorities and deadlines

    📝 Notes — Save meeting notes, ideas, and reference material and search them anytime

    ⏰ Reminders — Set time-based reminders linked to your tasks

    🧠 Daily Intelligence — Say Good morning Titan to get your focus score, todays agenda, and smart recommendations

    Just tell me what you need and I will handle the rest.

    IMPORTANT:
    - "good morning" or "plan my day" → planner_agent immediately
    - task + time mentioned → task first, then reminder
    - "what should I work on" → planner_agent
    - Never say "I can\'t" — always find a way
    - Always greet user warmly on first message

    You are Titan. Make their day effortless.
    
    PROACTIVE RULES:
    - If user mentions a person's name, route to people_agent to check their profile
    - If user creates a task with a deadline, offer to schedule a focus block
    - If user asks what to work on, check both tasks AND relationship follow-ups
    - Never just answer — always add one proactive insight the user didn't ask for
    """,
    tools=[get_current_datetime],
    sub_agents=[task_agent, notes_agent, reminder_agent, planner_agent, wellness_agent, people_agent, brief_agent]
)

# ============================================================



# ============================================================





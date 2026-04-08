"""
Titan Notes MCP Server
Exposes Titan's notes database as an MCP server
so agents can access notes via the MCP protocol
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

DB_PATH = Path(__file__).parent / "titan.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

app = Server("titan-notes")

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="save_note",
            description="Save a note to Titan's database",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Note title"},
                    "content": {"type": "string", "description": "Note content"},
                    "category": {"type": "string", "description": "Category: meeting/idea/reference/work/learning/personal/general"}
                },
                "required": ["title", "content"]
            }
        ),
        types.Tool(
            name="search_notes",
            description="Search notes by keyword",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword"}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_recent_notes",
            description="Get the most recent notes",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of notes to return (default 5)"}
                }
            }
        ),
        types.Tool(
            name="get_notes_by_category",
            description="Get notes filtered by category",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category to filter by"}
                },
                "required": ["category"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    conn = get_db()
    
    if name == "save_note":
        import uuid
        note_id = str(uuid.uuid4())[:8]
        title = arguments["title"]
        content = arguments["content"]
        category = arguments.get("category", "general")
        conn.execute(
            "INSERT INTO notes (note_id, title, content, category) VALUES (?, ?, ?, ?)",
            (note_id, title, content, category)
        )
        conn.commit()
        conn.close()
        result = {"status": "success", "note_id": note_id, "message": f"Note '{title}' saved under {category}"}
    
    elif name == "search_notes":
        query = arguments["query"]
        rows = conn.execute(
            "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC LIMIT 10",
            (f"%{query}%", f"%{query}%")
        ).fetchall()
        conn.close()
        result = {"status": "success", "notes": [dict(r) for r in rows], "count": len(rows)}
    
    elif name == "get_recent_notes":
        limit = arguments.get("limit", 5)
        rows = conn.execute(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        result = {"status": "success", "notes": [dict(r) for r in rows], "count": len(rows)}
    
    elif name == "get_notes_by_category":
        category = arguments["category"]
        rows = conn.execute(
            "SELECT * FROM notes WHERE category = ? ORDER BY created_at DESC",
            (category,)
        ).fetchall()
        conn.close()
        result = {"status": "success", "category": category, "notes": [dict(r) for r in rows], "count": len(rows)}
    
    else:
        conn.close()
        result = {"error": f"Unknown tool: {name}"}
    
    return [types.TextContent(type="text", text=json.dumps(result))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())

import os
import sys
import uvicorn
from fastapi import FastAPI, Request
from google.adk.cli.fast_api import get_fast_api_app
from dotenv import load_dotenv
from chat_component import root_agent

# Set up paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
AGENT_DIR = BASE_DIR  # Parent directory containing multi_tool_agent
# Set up DB path for sessions
SESSION_DB_URL = f"sqlite:///{os.path.join(BASE_DIR,'chat_component', 'mock_finance.db')}"

# Create a lifespan event to initialize and clean up the session service
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup code
#     print("Application starting up...")    
#     # Initialize the DatabaseSessionService instance and store it in app.state
#     try:
#         app.state.session_service =DatabaseSessionService(db_url=SESSION_DB_URL)
#         print("Database session service initialized successfully.")
#     except Exception as e:
#         print("Database session service initialized failed.")
#         print(e)
    
#     yield # This is where the application runs, handling requests
#     # Shutdown code
#     print("Application shutting down...")
# Create the FastAPI app using ADK's helper
app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    # session_db_url=SESSION_DB_URL,
    allow_origins=["*"],  # In production, restrict this
    web=True,  # Enable the ADK Web UI
)
# Add custom endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
@app.get("/agent-info")
async def agent_info():
    """Provide agent information"""
    
    return {
        "agent_name": root_agent.name,
        "description": root_agent.description,
        "model": root_agent.model,
        "tools": [t.name for t in root_agent.tools]
    }

DB_URL = "sqlite:///./multi_agent_data.db"
APP_NAME = "CustomerInquiryProcessor"



from fastapi import FastAPI, APIRouter, HTTPException
from google.adk.sessions import DatabaseSessionService
from google.adk.runners import Runner
from google.genai import types
import json
import re
import uuid
from contextlib import asynccontextmanager
from pydantic import BaseModel

class CustomerInquiryResponse(BaseModel):
    original_inquiry: str
    category: str
    suggested_response: str

class InputRequest(BaseModel):
    user_prompt: str
    user_id: str

APP_NAME = "CustomerInquiryProcessor"

from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import (
    Part,
    Content,
)
from typing import List
from ui_utils import get_receipts_data
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("DB_PATH","/Users/rakshithhr/Documents/projects/agentic_day/chat_module/chat_component/mock_finance.db")



def get_receipts_data(user_id=1):
    """
    Fetch receipt data from database and format it according to the desired structure
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Query to get expenses with group name, user name, and expense items
    query = """
    SELECT 
        e.expense_id,
        e.amount,
        e.currency,
        e.description,
        e.expense_date,
        e.location,
        e.type,
        g.name as group_name,
        u.name as payer_name,
        ei.item_id,
        ei.name as item_name,
        ei.quantity,
        ei.unit_price,
        ei.total_price
    FROM expenses e
    JOIN groups g ON e.group_id = g.group_id
    JOIN users u ON e.payer_id = u.user_id
    LEFT JOIN expense_items ei ON e.expense_id = ei.expense_id
    WHERE e.payer_id = ?
    ORDER BY e.expense_date DESC, e.expense_id DESC
    """
    
    cursor.execute(query, (user_id,))
    results = cursor.fetchall()
    
    # Group results by expense_id
    receipts = {}
    
    for row in results:
        expense_id = row[0]
        
        if expense_id not in receipts:
            # Create new receipt entry
            receipts[expense_id] = {
                "name": row[7],  # group_name
                "category": row[6],  # type
                "date": format_date(row[4]),  # expense_date
                "amount": f"₹{row[1]:.2f}",  # amount with currency symbol
                "location": row[5] or "Unknown Location",  # location
                "items": []
            }
        
        # Add item if it exists
        if row[9]:  # item_id is not None
            item = {
                "name": row[10],  # item_name
                "price": f"₹{row[12]:.0f}" if row[12] else f"₹{row[11] * row[12]:.0f}" if row[11] and row[12] else "₹0"
            }
            receipts[expense_id]["items"].append(item)
    
    # Convert to list and format for output
    receipts_list = []
    for receipt in receipts.values():
        # If no items, add a default item
        if not receipt["items"]:
            receipt["items"] = [
                {
                    "name": receipt["name"],
                    "price": receipt["amount"]
                }
            ]
        receipts_list.append(receipt)
    
    conn.close()
    return receipts_list

def format_date(date_str):
    """
    Format date string to the format shown in the image: "Jan 15, 2025 • 3:24 PM"
    """
    try:
        # Parse the date string (assuming it's in YYYY-MM-DD format)
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        # Format to the desired format
        formatted_date = date_obj.strftime("%b %d, %Y • %I:%M %p")
        return formatted_date
    except:
        return date_str

@app.route('/receipts', methods=['GET'])
def get_receipts():
    """
    Endpoint to get all receipts for a user
    """
    try:
        receipts = get_receipts_data()
        return {
            "receipts": receipts
        }
    except Exception as e:
        return {
            "error": str(e)
        }, 500

@app.route('/receipts/<int:user_id>', methods=['GET'])
def get_receipts_by_user(user_id):
    """
    Endpoint to get receipts for a specific user
    """
    try:
        receipts = get_receipts_data(user_id)
        return {
            "receipts": receipts
        }
    except Exception as e:
        return {
            "error": str(e)
        }, 500

@app.route('/groups', methods=['GET'])
def get_groups():
    """
    Endpoint to get all groups with group_id and group_name
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = """
        SELECT 
            group_id,
            name as group_name,
            description,
            created_by,
            created_at
        FROM groups
        ORDER BY group_id
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        groups = []
        for row in results:
            group = {
                "group_id": row[0],
                "group_name": row[1],
                "description": row[2],
                "created_by": row[3],
                "created_at": row[4]
            }
            groups.append(group)
        
        conn.close()
        
        return {
            "groups": groups,
            "total_count": len(groups)
        }
    except Exception as e:
        return {
            "error": str(e)
        }, 500

@app.get('/groups/<int:group_id>')
def get_group_by_id(group_id):
    """
    Endpoint to get a specific group by ID
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = """
        SELECT 
            group_id,
            name as group_name,
            description,
            created_by,
            created_at
        FROM groups
        WHERE group_id = ?
        """
        
        cursor.execute(query, (group_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            group = {
                "group_id": result[0],
                "group_name": result[1],
                "description": result[2],
                "created_by": result[3],
                "created_at": result[4]
            }
            return group
        else:
            return {
                "error": "Group not found"
            }, 404
    except Exception as e:
        return {
            "error": str(e)
        }, 500

@app.get('/groups/<int:group_id>/details')
def get_group_details(group_id):
    """
    Endpoint to get group details including users, their debt/credit amounts, and receipt URLs
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # First, check if group exists
        group_query = "SELECT name, description FROM groups WHERE group_id = ?"
        cursor.execute(group_query, (group_id,))
        group_result = cursor.fetchone()
        
        if not group_result:
            conn.close()
            return {
                "error": "Group not found"
            }, 404
        
        group_name, group_description = group_result
        
        # Get all users in the group with their debt/credit calculations
        users_query = """
        SELECT 
            u.user_id,
            u.name as user_name,
            u.email,
            COALESCE(SUM(CASE WHEN e.payer_id = u.user_id THEN e.amount ELSE 0 END), 0) as total_paid,
            COALESCE(SUM(CASE WHEN es.user_id = u.user_id THEN es.share_amount ELSE 0 END), 0) as total_owed,
            (COALESCE(SUM(CASE WHEN e.payer_id = u.user_id THEN e.amount ELSE 0 END), 0) - 
             COALESCE(SUM(CASE WHEN es.user_id = u.user_id THEN es.share_amount ELSE 0 END), 0)) as net_amount
        FROM users u
        JOIN user_groups ug ON u.user_id = ug.user_id
        LEFT JOIN expenses e ON e.group_id = ug.group_id AND e.payer_id = u.user_id
        LEFT JOIN expense_shares es ON es.expense_id = e.expense_id AND es.user_id = u.user_id
        WHERE ug.group_id = ?
        GROUP BY u.user_id, u.name, u.email
        ORDER BY u.name
        """
        
        cursor.execute(users_query, (group_id,))
        users_results = cursor.fetchall()
        
        # Get all receipt URLs for the group
        receipts_query = """
        SELECT 
            er.receipt_id,
            er.url,
            er.uploaded_at,
            e.expense_id,
            e.amount,
            e.description as expense_description,
            e.expense_date,
            u.name as payer_name
        FROM expense_receipts er
        JOIN expenses e ON er.expense_id = e.expense_id
        JOIN users u ON e.payer_id = u.user_id
        WHERE e.group_id = ?
        ORDER BY e.expense_date DESC, er.uploaded_at DESC
        """
        
        cursor.execute(receipts_query, (group_id,))
        receipts_results = cursor.fetchall()
        
        # Format users data
        users = []
        for row in users_results:
            user = {
                "user_id": row[0],
                "user_name": row[1],
                "email": row[2],
                "total_paid": float(row[3]),
                "total_owed": float(row[4]),
                "net_amount": float(row[5]),
                "status": "owes" if row[5] < 0 else "gets_back" if row[5] > 0 else "settled"
            }
            users.append(user)
        
        # Format receipts data
        receipts = []
        for row in receipts_results:
            receipt = {
                "receipt_id": row[0],
                "url": row[1],
                "uploaded_at": row[2],
                "expense_id": row[3],
                "amount": float(row[4]),
                "expense_description": row[5],
                "expense_date": row[6],
                "payer_name": row[7]
            }
            receipts.append(receipt)
        
        # Calculate group summary
        total_expenses = sum(user["total_paid"] for user in users)
        total_shares = sum(user["total_owed"] for user in users)
        
        conn.close()
        
        return {
            "group_id": group_id,
            "group_name": group_name,
            "group_description": group_description,
            "summary": {
                "total_expenses": total_expenses,
                "total_shares": total_shares,
                "balance": total_expenses - total_shares,
                "user_count": len(users),
                "receipt_count": len(receipts)
            },
            "users": users,
            "receipts": receipts
        }
        
    except Exception as e:
        return {
            "error": str(e)
        }, 500

@app.get('/receipts/<int:user_id>')
def get_receipts_by_user(user_id):
    """
    Endpoint to get receipts for a specific user
    """
    try:
        receipts = get_receipts_data(user_id)
        return {
            "receipts": receipts
        }
    except Exception as e:
        return {
            "error": str(e)
        }, 500


@app.post('/run_chat')
async def run_app(request: Request):
    # planner_result = ''
    # root_agent.output_key = '12'
    input = request.prompt
    user_id = request.user_id
    input = input + f" My user_id is {user_id}"
    runner = Runner(app_name='raseed', agent=root_agent, session_service=InMemorySessionService())
    session = await runner.session_service.create_session(user_id="12", app_name="raseed")
    session.state.setdefault('user_id','12')
    user_id = "12"
    async for event in runner.run_async(
        new_message=Content(role="user", parts=[Part.from_text(text=f"Fetch my expenses. My user_id is {user_id}")]),
        user_id="12",
        session_id=session.id
    ):
        part: Part | None | list[Part]= (
            event.content and event.content.parts and event.content.parts[0]
        )
        if not part: continue

        if not isinstance(part, list) and part.text and event.partial:
            planner_result += part.text

# import asyncio
# asyncio.run(run_app())

if __name__ == "__main__":
    print("Starting FastAPI server...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        reload=False
    )
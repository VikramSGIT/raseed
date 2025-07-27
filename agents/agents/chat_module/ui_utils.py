import os
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



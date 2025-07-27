import base64
from typing import Dict, List, Tuple
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import google.auth
import requests
import json
import os
from cryptography.hazmat.primitives import serialization
import jwt
import datetime
from decimal import Decimal

# tool/google_wallet_tool.py
# Load credentials from environment
GOOGLE_WALLET_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_WALLET_SERVICE_ACCOUNT_FILE","/Users/rakshithhr/Downloads/wallet-integration-466509-e4057ed46eeb.json")
GOOGLE_WALLET_ISSUER_ID = os.getenv("GOOGLE_WALLET_ISSUER_ID","3388000000022966378")

# Set proper scopes
SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]

# Load credentials
credentials = service_account.Credentials.from_service_account_file(
    GOOGLE_WALLET_SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
session = requests.Session()
credentials.refresh(Request())

class WalletRequest(BaseModel):
    user_id: str
    receipt_summary: str
    transaction_amount: float

def create_save_url_with_jwt(object_id: str):
    claims = {
        'iss': credentials.service_account_email,
        'aud': 'google',
        'typ': 'savetowallet',
        'iat': int(datetime.datetime.utcnow().timestamp()),
        'payload': {
            'genericObjects': [{
                'id': object_id
            }]
        }
    }

    private_key = credentials._signer._key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    token = jwt.encode(claims, private_key, algorithm='RS256')
    return f'https://pay.google.com/gp/v/save/{token}'

from google.adk.tools import ToolContext
import os
DB_PATH = os.environ.get("DB_URL",'/Users/rakshithhr/Documents/projects/agentic_day/chat_module/chat_component/mock_finance.db')
import sqlite3
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

def create_google_wallet_pass_groups(group_id):

    expense_shares = calculate_group_expense_shares(group_id)
    GENERIC_CLASS_ID = f"{GOOGLE_WALLET_ISSUER_ID}.group_pass"  # Make sure this class exists in Google Wallet Console
    all_urls = []
    for user in expense_shares:
        sanitized_user_id = str(user['user_id']).replace('@', '_').replace('.', '_')
        generic_object_id = f"{GOOGLE_WALLET_ISSUER_ID}.{sanitized_user_id+user['group_name']}"
        generic_object_id = generic_object_id.replace(' ', '_')
        # Check if object already exists to avoid 404 or 409
        object_url = f"https://walletobjects.googleapis.com/walletobjects/v1/genericObject/{generic_object_id}"
        headers = {"Authorization": f"Bearer {credentials.token}"}

        existing_check = session.get(object_url, headers=headers)
        object_payload ={ 
            "textModulesData": [
                    {
                    "id": "owed",
                    "header": "OWED",
                    "body": user['owed_amount']
                    },
                    {
                    "id": "get_back",
                    "header": "GET_BACK",
                    "body": user['get_back_amount']
                    }
                ],
                "barcode": {
                    "type": "QR_CODE",
                    "value": user['user_id'],  # use total or last value
                    "alternateText": "Receipt Details"
                }
                }
        if existing_check.status_code == 200:
            # Object exists -> PATCH to update
            update_response = session.patch(
                object_url,
                headers=headers,
                json=object_payload
            )
            if update_response.status_code >= 400:
                raise HTTPException(status_code=update_response.status_code, detail=update_response.text)
        else:
            object_payload.update({
                "id": generic_object_id,
                "classId": GENERIC_CLASS_ID,
                "logo": {
                    "sourceUri": {
                    "uri": "https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/pass_google_logo.jpg"
                    },
                    "contentDescription": {
                    "defaultValue": {
                        "language": "en-US",
                        "value": "LOGO_IMAGE_DESCRIPTION"
                    }
                    }
                },
                "state": "ACTIVE",
                "cardTitle": {
                    "defaultValue": {"language": "en-US", "value": user['group_name']}
                },
                "header": {
                    "defaultValue": {"language": "en-US", "value": user['user_name']}
                },
                "hexBackgroundColor": "#4285f4",
                "heroImage": {
                    "sourceUri": {
                    "uri": "https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/google-io-hero-demo-only.png"
                }
                },
            
                "linksModuleData": {
                    "uris": [
                        {"uri": "https://simple.com", "description": "View Details"}
                    ]
                }
            })
            #TODO: Add the objectID to the receipts table.
            object_response = session.post(
                        "https://walletobjects.googleapis.com/walletobjects/v1/genericObject",
                        headers=headers,
                        json=object_payload
                    )

            if object_response.status_code >= 400:
                raise HTTPException(status_code=object_response.status_code, detail=object_response.text)
            save_url = create_save_url_with_jwt(generic_object_id)
            print(f"**************\n{save_url}\n******")
            all_urls[sanitized_user_id] = save_url
            #TODO: SAVE OBJECT_ID TO DB
            #TODO SEND URL TO USER_ID
    return all_urls or None
    
            

def calculate_group_expense_shares(group_id: int) -> List[Dict]:
    """
    Calculate expense shares for all users in a group.
    
    Returns a list of dictionaries with:
    - group_name: Name of the group
    - user_id: User ID
    - owed_amount: Amount the user owes to others
    - get_back_amount: Amount the user should get back from others
    """
    
    # Get group name
    cursor.execute("""
        SELECT name FROM groups WHERE group_id = ?
    """, (group_id,))
    group_result = cursor.fetchone()
    if not group_result:
        raise HTTPException(status_code=404, detail=f"Group with ID {group_id} not found")
    
    group_name = group_result[0]
    
    # Get all users in the group
    cursor.execute("""
        SELECT DISTINCT ug.user_id, u.name, u.email
        FROM user_groups ug
        JOIN users u ON ug.user_id = u.user_id
        WHERE ug.group_id = ?
    """, (group_id,))
    group_users = cursor.fetchall()
    
    if not group_users:
        raise HTTPException(status_code=404, detail=f"No users found in group {group_id}")
    
    # Calculate total expenses in the group
    cursor.execute("""
        SELECT SUM(amount) FROM expenses WHERE group_id = ?
    """, (group_id,))
    total_group_expenses = cursor.fetchone()[0] or Decimal('0')
    
    # Calculate how much each user paid (as payer)
    cursor.execute("""
        SELECT payer_id, SUM(amount) as total_paid
        FROM expenses 
        WHERE group_id = ?
        GROUP BY payer_id
    """, (group_id,))
    user_payments = dict(cursor.fetchall())
    
    # Calculate how much each user should pay (based on shares)
    cursor.execute("""
        SELECT es.user_id, SUM(es.share_amount) as total_share
        FROM expense_shares es
        JOIN expenses e ON es.expense_id = e.expense_id
        WHERE e.group_id = ?
        GROUP BY es.user_id
    """, (group_id,))
    user_shares = dict(cursor.fetchall())
    
    results = []
    
    for user_id, name, email in group_users:
        # How much this user paid
        paid_amount = user_payments.get(user_id, Decimal('0'))
        
        # How much this user should pay (their share)
        share_amount = user_shares.get(user_id, Decimal('0'))
        
        # Calculate net position
        net_amount = paid_amount - share_amount
        
        # Determine owed_amount and get_back_amount
        if net_amount > 0:
            # User paid more than their share - they should get money back
            owed_amount = Decimal('0')
            get_back_amount = net_amount
        else:
            # User paid less than their share - they owe money
            owed_amount = abs(net_amount)
            get_back_amount = Decimal('0')
        
        results.append({
            "group_name": group_name,
            "user_id": user_id,
            "user_name": name,
            "user_email": email,
            "paid_amount": float(paid_amount),
            "share_amount": float(share_amount),
            "owed_amount": float(owed_amount),
            "get_back_amount": float(get_back_amount),
            "net_position": float(net_amount)
        })
    
    return results

def get_group_expense_summary(group_id: int) -> Dict:
    """
    Get a comprehensive summary of group expenses including:
    - Total group expenses
    - Per-user breakdown
    - Settlement recommendations
    """
    
    user_shares = calculate_group_expense_shares(group_id)
    
    # Calculate totals
    total_expenses = sum(user["share_amount"] for user in user_shares)
    total_owed = sum(user["owed_amount"] for user in user_shares)
    total_get_back = sum(user["get_back_amount"] for user in user_shares)
    
    # Find users who owe money and users who should get money back
    users_who_owe = [user for user in user_shares if user["owed_amount"] > 0]
    users_who_get_back = [user for user in user_shares if user["get_back_amount"] > 0]
    
    return {
        "group_id": group_id,
        "group_name": user_shares[0]["group_name"] if user_shares else "",
        "total_group_expenses": total_expenses,
        "total_amount_owed": total_owed,
        "total_amount_to_get_back": total_get_back,
        "user_breakdown": user_shares,
        "users_who_owe": users_who_owe,
        "users_who_get_back": users_who_get_back,
        "settlement_balanced": abs(total_owed - total_get_back) < 0.01  # Check if amounts balance
    }


create_google_wallet_pass_groups(13)

# FastAPI app setup
# app = FastAPI(title="Group Wallet API", description="API for managing group expenses and Google Wallet integration")

# @app.get("/group/{group_id}/expense-shares")
# def get_group_expense_shares(group_id: int):
#     """
#     Get expense shares for all users in a group.
    
#     Returns:
#     - group_name: Name of the group
#     - user_id: User ID
#     - owed_amount: Amount the user owes to others
#     - get_back_amount: Amount the user should get back from others
#     """
#     try:
#         return calculate_group_expense_shares(group_id)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# @app.get("/group/{group_id}/expense-summary")
# async def get_group_expense_summary_endpoint(group_id: int):
#     """
#     Get a comprehensive summary of group expenses including:
#     - Total group expenses
#     - Per-user breakdown
#     - Settlement recommendations
#     """
#     try:
#         return get_group_expense_summary(group_id)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# @app.post("/wallet/create-group-pass")
# async def create_group_wallet_pass(wallet_request: WalletRequest):
#     """
#     Create a Google Wallet pass for group expenses
#     """
#     # This would integrate with the existing wallet creation logic
#     # For now, returning a placeholder
#     return {"message": "Wallet pass creation endpoint - integrate with existing logic"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)

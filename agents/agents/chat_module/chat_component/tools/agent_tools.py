"""
Agent-compatible tool wrappers for Google ADK integration
"""
from typing import Any
from chat_component.tools.sql_execution import execute_query

# Import utility functions directly to avoid complex type issues
from chat_component.tools.utils import round_to_cents
import json
from datetime import datetime
from chat_component.tools.group_wallet import create_google_wallet_pass_groups



def get_group_info(group_name: str, user_id: int) -> str:
    """
    Get group information by name for a specific user
    Args:
        group_name: Name of the group to find
        user_id: ID of the user requesting the information
    Returns:
        JSON string with group details and members
    """
    try:
        # Find group by name that the user belongs to (case-insensitive)
        query = f"""
            SELECT g.group_id, g.name, g.description, g.group_type, g.created_at
            FROM groups g
            JOIN user_groups ug ON g.group_id = ug.group_id
            WHERE LOWER(g.name) = LOWER('{group_name}') AND ug.user_id = {user_id}
        """
        result = execute_query(query)

        if not result:
            return json.dumps({"error": f"Group '{group_name}' not found or user {user_id} is not a member"})

        group_data = result[0]
        group_id = group_data[0]

        # Get group members
        members_query = f"""
            SELECT u.user_id, u.name, u.email
            FROM users u
            JOIN user_groups ug ON u.user_id = ug.user_id
            WHERE ug.group_id = {group_id}
        """
        members_result = execute_query(members_query)
        members = [{'user_id': row[0], 'name': row[1], 'email': row[2]} for row in members_result]

        # Get group details and members
        group_details = {
            "group_id": group_id,
            "name": group_data[1],
            "description": group_data[2],
            "group_type": group_data[3],
            "created_at": group_data[4],
            "members": members
        }

        return json.dumps(group_details)
    except Exception as e:
        return json.dumps({"error": str(e)})


def validate_user_and_group(user_id: int, group_name: str):
    """
    Validate that user exists and belongs to the specified group
    Returns group_id if valid, error message otherwise
    """
    try:
        # Check if user exists
        user_query = f"SELECT user_id, name FROM users WHERE user_id = {user_id}"
        user_result = execute_query(user_query)

        if not user_result:
            return {"error": f"User with ID {user_id} not found"}

        # Check if group exists and user is a member (case-insensitive)
        group_query = f"""
            SELECT g.group_id, g.name
            FROM groups g
            JOIN user_groups ug ON g.group_id = ug.group_id
            WHERE LOWER(g.name) = LOWER('{group_name}') AND ug.user_id = {user_id}
        """
        group_result = execute_query(group_query)

        if not group_result:
            return {"error": f"Group '{group_name}' not found or user {user_id} is not a member"}

        return {
            "valid": True,
            "group_id": group_result[0][0],
            "user_name": user_result[0][1],
            "group_name": group_result[0][1]
        }
    except Exception as e:
        return {"error": str(e)}


def split_bill_equal(user_id: int, group_name: str, total_amount: float, description: str) -> str:
    """
    Split bill equally among all group members
    Args:
        user_id: ID of the user requesting the split
        group_name: Name of the group
        total_amount: Total amount to split
        description: Optional description of the expense
    Returns:
        JSON string with split results
    """
    try:
        # Validate user and group
        validation = validate_user_and_group(user_id, group_name)
        print(f"-----------------{validation}-------------")
        if "error" in validation:
            return json.dumps(validation)
        
        group_id = validation["group_id"]
        
        # Get group members
        members_query = f"""
            SELECT u.user_id, u.name, u.email
            FROM users u
            JOIN user_groups ug ON u.user_id = ug.user_id
            WHERE ug.group_id = {group_id}
        """
        members_result = execute_query(members_query)
        members = [{'user_id': row[0], 'name': row[1], 'email': row[2]} for row in members_result]
        
        # Perform equal split calculation
        num_members = len(members)
        equal_share = round_to_cents(total_amount / num_members)

        # Handle rounding differences
        remaining_amount = total_amount - (equal_share * num_members)

        splits = {}
        for i, member in enumerate(members):
            share = equal_share
            # Add remaining cents to first member
            if i == 0 and remaining_amount != 0:
                share += round_to_cents(remaining_amount)

            splits[member['user_id']] = {
                'user_name': member['name'],
                'share_amount': share,
                'percentage': round((share / total_amount) * 100, 2)
            }
        
        # Persist to database
        group_id = validation["group_id"]
        URL = persist_expense_and_shares(
            group_id=group_id,
            payer_id=user_id,
            total_amount=total_amount,
            description=description,
            splits=splits,
            split_type="equal"
        )

        result = {
            "group_name": group_name,
            "split_type": "equal",
            "total_amount": total_amount,
            "description": description,
            "URL_TO_DISPLAY_WALLET_URL": URL,
            "split_summary": {}
        }

        # Convert to the expected format
        for user_id_split, split_data in splits.items():
            result["split_summary"][split_data["user_name"]] = split_data["share_amount"]

        return json.dumps(result)
    except Exception as e:
        print(f"ERROR: {e}")
        return json.dumps({"error": str(e)})


def split_bill_percentage(user_id: int, group_name: str, total_amount: float,
                         percentage_data: str, description: str) -> str:
    """
    Split bill by custom percentages
    Args:
        user_id: ID of the user requesting the split
        group_name: Name of the group
        total_amount: Total amount to split
        percentage_data: JSON string mapping user names to percentages, e.g. '{"Alice Johnson": 50.0, "Bob Smith": 30.0, "Charlie Brown": 20.0}'
        description: Optional description of the expense
    Returns:
        JSON string with split results
    """
    try:
        # Validate user and group
        validation = validate_user_and_group(user_id, group_name)
        if "error" in validation:
            return json.dumps(validation)

        group_id = validation["group_id"]

        # Parse percentage data - handle both JSON and natural language formats
        try:
            percentage_map = json.loads(percentage_data)
        except json.JSONDecodeError:
            # Try to parse natural language format like "Alice 50%, Bob 30%, Charlie 20%"
            try:
                percentage_map = {}
                # Remove common words and clean the data
                clean_data = percentage_data.replace("Split", "").strip()
                # Remove dollar amounts (like $300:) but keep the colon for name:percentage pairs
                import re
                clean_data = re.sub(r'\$\d+(?:\.\d+)?:?', '', clean_data).strip()

                # Use regex to find all name-percentage pairs
                # Pattern to match "Name 50%" or "Name: 50%" or "Name 50"
                matches = re.findall(r'([A-Za-z]+)\s*:?\s*(\d+(?:\.\d+)?)%?', clean_data)

                for match in matches:
                    name = match[0].strip()
                    percentage = float(match[1])
                    percentage_map[name] = percentage

                if not percentage_map:
                    return json.dumps({"error": "Could not parse percentage data. Expected format: 'Alice 50%, Bob 30%' or JSON string."})

            except Exception as e:
                return json.dumps({"error": f"Invalid percentage_data format. Expected JSON string or 'Name percentage%' format. Error: {str(e)}"})

        # Convert user names to user IDs with flexible matching
        user_id_percentage_map = {}
        for user_name, percentage in percentage_map.items():
            # First try exact match
            user_query = f"SELECT user_id FROM users WHERE name = '{user_name}'"
            user_result = execute_query(user_query)

            # If no exact match, try partial match (case-insensitive)
            if not user_result:
                user_query = f"SELECT user_id FROM users WHERE LOWER(name) LIKE LOWER('%{user_name}%')"
                user_result = execute_query(user_query)

            if user_result:
                user_id_percentage_map[user_result[0][0]] = percentage
            else:
                return json.dumps({"error": f"User '{user_name}' not found in the group"})
        
        # Validate percentages sum to 100
        total_percentage = sum(user_id_percentage_map.values())
        if abs(total_percentage - 100.0) > 0.01:
            return json.dumps({"error": f"Percentages must sum to 100%, got {total_percentage}%"})

        # Perform percentage split calculation
        splits = {}
        total_assigned = 0

        for user_id_split, percentage in user_id_percentage_map.items():
            share_amount = round_to_cents((total_amount * percentage) / 100)
            total_assigned += share_amount

            # Get user name from database
            user_query = f"SELECT name FROM users WHERE user_id = {user_id_split}"
            user_result = execute_query(user_query)
            user_name = user_result[0][0] if user_result else f"User {user_id_split}"

            splits[user_id_split] = {
                'user_name': user_name,
                'share_amount': share_amount,
                'percentage': percentage
            }

        # Handle rounding differences
        difference = round_to_cents(total_amount - total_assigned)
        if difference != 0:
            # Add difference to the first user
            first_user = list(user_id_percentage_map.keys())[0]
            splits[first_user]['share_amount'] += difference
        
        # Persist to database
        group_id = validation["group_id"]
        URL = persist_expense_and_shares(
            group_id=group_id,
            payer_id=user_id,
            total_amount=total_amount,
            description=description,
            splits=splits,
            split_type="percentage"
        )

        result = {
            "group_name": group_name,
            "split_type": "percentage",
            "total_amount": total_amount,
            "description": description,
            "split_summary": {},
            "URL_TO_DISPLAY_WALLET_URL": URL
        }

        # Convert to the expected format
        for user_id_split, split_data in splits.items():
            result["split_summary"][split_data["user_name"]] = split_data["share_amount"]

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def split_bill_custom_amounts(user_id: int, group_name: str, total_amount: float,
                             amount_data: str, description: str) -> str:
    """
    Split bill with custom amounts for each person
    Args:
        user_id: ID of the user requesting the split
        group_name: Name of the group
        total_amount: Total amount to split
        amount_data: JSON string mapping user names to custom amounts, e.g. '{"Alice Johnson": 80.0, "Bob Smith": 70.0, "Charlie Brown": 50.0}'
        description: Optional description of the expense
    Returns:
        JSON string with split results
    """
    try:
        # Validate user and group
        validation = validate_user_and_group(user_id, group_name)
        if "error" in validation:
            return json.dumps(validation)

        group_id = validation["group_id"]

        # Parse amount data from JSON string
        try:
            amount_map = json.loads(amount_data)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid amount_data format. Expected JSON string."})

        # Convert user names to user IDs with flexible matching
        user_id_amount_map = {}
        for user_name, amount in amount_map.items():
            # First try exact match
            user_query = f"SELECT user_id FROM users WHERE name = '{user_name}'"
            user_result = execute_query(user_query)

            # If no exact match, try partial match (case-insensitive)
            if not user_result:
                user_query = f"SELECT user_id FROM users WHERE LOWER(name) LIKE LOWER('%{user_name}%')"
                user_result = execute_query(user_query)

            if user_result:
                user_id_amount_map[user_result[0][0]] = amount
            else:
                return json.dumps({"error": f"User '{user_name}' not found in the group"})
        
        # Validate amounts sum to total
        total_assigned = sum(user_id_amount_map.values())
        if abs(total_assigned - total_amount) > 0.01:
            return json.dumps({"error": f"Custom amounts ({total_assigned}) don't match total ({total_amount})"})

        # Perform custom amount split calculation
        splits = {}
        for user_id_split, amount in user_id_amount_map.items():
            share_amount = round_to_cents(amount)
            percentage = round((share_amount / total_amount) * 100, 2)

            # Get user name from database
            user_query = f"SELECT name FROM users WHERE user_id = {user_id_split}"
            user_result = execute_query(user_query)
            user_name = user_result[0][0] if user_result else f"User {user_id_split}"

            splits[user_id_split] = {
                'user_name': user_name,
                'share_amount': share_amount,
                'percentage': percentage
            }
        
        # Persist to database
        group_id = validation["group_id"]
        URL = persist_expense_and_shares(
            group_id=group_id,
            payer_id=user_id,
            total_amount=total_amount,
            description=description,
            splits=splits,
            split_type="custom_amounts"
        )

        result = {
            "group_name": group_name,
            "split_type": "custom_amounts",
            "total_amount": total_amount,
            "description": description,
            "split_summary": {},
            "URL_TO_DISPLAY_WALLET_URL": URL
        }

        # Convert to the expected format
        for user_id_split, split_data in splits.items():
            result["split_summary"][split_data["user_name"]] = split_data["share_amount"]

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_user_groups_info(user_id: int) -> str:
    """
    Get all groups for a user
    Args:
        user_id: ID of the user
    Returns:
        JSON string with user's groups
    """
    try:
        query = f"""
            SELECT g.group_id, g.name, g.description, g.group_type,
                    ug.role, g.created_at
            FROM groups g
            JOIN user_groups ug ON g.group_id = ug.group_id
            WHERE ug.user_id = {user_id}
            ORDER BY g.created_at DESC
        """
        results = execute_query(query)

        groups = []
        for row in results:
            groups.append({
                'group_id': row[0],
                'name': row[1],
                'description': row[2],
                'group_type': row[3],
                'role': row[4],
                'created_at': row[5]
            })

        return json.dumps({"user_id": user_id, "groups": groups})
    except Exception as e:
        return json.dumps({"error": str(e)})


def split_bill_itemized(user_id: int, group_name: str, items_data: str,
                       default_split: str, description: str) -> str:
    """
    Split bill based on itemized purchases
    Args:
        user_id: ID of the user requesting the split
        group_name: Name of the group
        items_data: JSON string with items list, e.g. '[{"name": "Pizza", "price": 25.00, "assigned_users": ["Alice Johnson", "Bob Smith"]}, {"name": "Salad", "price": 15.00, "assigned_users": ["Diana Prince"]}]'
        default_split: How to split unassigned items ('equal' is default)
        description: Optional description of the expense
    Returns:
        JSON string with split results
    """
    try:
        # Validate user and group
        validation = validate_user_and_group(user_id, group_name)
        if "error" in validation:
            return json.dumps(validation)

        group_id = validation["group_id"]

        # Parse items data from JSON string
        try:
            items = json.loads(items_data)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid items_data format. Expected JSON string."})

        # Convert user names to user IDs in items
        processed_items = []
        for item in items:
            processed_item = {
                'name': item['name'],
                'price': item['price'],
                'assigned_users': []
            }

            if 'assigned_users' in item:
                for user_name in item['assigned_users']:
                    # First try exact match
                    user_query = f"SELECT user_id FROM users WHERE name = '{user_name}'"
                    user_result = execute_query(user_query)

                    # If no exact match, try partial match (case-insensitive)
                    if not user_result:
                        user_query = f"SELECT user_id FROM users WHERE LOWER(name) LIKE LOWER('%{user_name}%')"
                        user_result = execute_query(user_query)

                    if user_result:
                        processed_item['assigned_users'].append(user_result[0][0])
                    else:
                        return json.dumps({"error": f"User '{user_name}' not found in the group"})

            processed_items.append(processed_item)

        # Perform itemized split calculation
        user_totals = {}
        total_amount_calc = 0

        for item in processed_items:
            item_price = item['price']
            assigned_users = item.get('assigned_users', [])

            if assigned_users:
                # Split among assigned users
                per_person = round_to_cents(item_price / len(assigned_users))
                for user_id_item in assigned_users:
                    user_totals[user_id_item] = user_totals.get(user_id_item, 0) + per_person
            else:
                # Will be split according to default_split method
                total_amount_calc += item_price

        # Handle items without specific assignment
        if total_amount_calc > 0:
            if default_split == 'equal':
                members_result = execute_query(f"""
                    SELECT u.user_id, u.name
                    FROM users u
                    JOIN user_groups ug ON u.user_id = ug.user_id
                    WHERE ug.group_id = {group_id}
                """)
                members_list = [{'user_id': row[0], 'name': row[1]} for row in members_result]
                per_person = round_to_cents(total_amount_calc / len(members_list))
                for member in members_list:
                    user_totals[member['user_id']] = user_totals.get(member['user_id'], 0) + per_person

        # Convert to splits format
        splits = {}
        grand_total = sum(user_totals.values())

        for user_id_item, amount in user_totals.items():
            # Get user name from database
            user_query = f"SELECT name FROM users WHERE user_id = {user_id_item}"
            user_result = execute_query(user_query)
            user_name = user_result[0][0] if user_result else f"User {user_id_item}"

            percentage = round((amount / grand_total) * 100, 2) if grand_total > 0 else 0

            splits[user_id_item] = {
                'user_name': user_name,
                'share_amount': round_to_cents(amount),
                'percentage': percentage
            }

        # Calculate total amount for persistence
        total_amount = sum(item['price'] for item in items)

        # Persist to database
        group_id = validation["group_id"]
        URL = persist_expense_and_shares(
            group_id=group_id,
            payer_id=user_id,
            total_amount=total_amount,
            description=description,
            splits=splits,
            split_type="itemized"
        )

        result = {
            "group_name": group_name,
            "split_type": "itemized",
            "total_amount": total_amount,
            "description": description,
            "items": items,
            "split_summary": {},
            "URL_TO_DISPLAY_WALLET_URL": URL
        }

        # Convert to the expected format
        for user_id_split, split_data in splits.items():
            result["split_summary"][split_data["user_name"]] = split_data["share_amount"]

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_group_balance_info(user_id: int, group_name: str) -> str:
    """
    Get balance information for a group
    Args:
        user_id: ID of the user requesting the information
        group_name: Name of the group
    Returns:
        JSON string with group balance information
    """
    try:
        # Validate user and group
        validation = validate_user_and_group(user_id, group_name)
        if "error" in validation:
            return json.dumps(validation)

        group_id = validation["group_id"]

        # Get group balances directly
        query = f"""
            SELECT
                u.user_id,
                u.name,
                COALESCE(SUM(CASE WHEN e.payer_id = u.user_id THEN e.amount ELSE 0 END), 0) as paid,
                COALESCE(SUM(es.share_amount), 0) as owes
            FROM users u
            JOIN user_groups ug ON u.user_id = ug.user_id
            LEFT JOIN expenses e ON e.group_id = ug.group_id
            LEFT JOIN expense_shares es ON es.user_id = u.user_id AND es.expense_id = e.expense_id
            WHERE ug.group_id = {group_id}
            GROUP BY u.user_id, u.name
            ORDER BY u.name
        """

        results = execute_query(query)

        balances = {}
        for row in results:
            user_id_bal, name, paid, owes = row
            balance = round_to_cents(paid - owes)

            balances[user_id_bal] = {
                'name': name,
                'paid': round_to_cents(paid),
                'owes': round_to_cents(owes),
                'balance': balance,
                'status': 'owes_money' if balance < 0 else 'owed_money' if balance > 0 else 'settled'
            }

        return json.dumps({
            "group_name": group_name,
            "balances": balances
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def query_database(sql_query: str) -> str:
    """
    Execute a custom SQL query against the database
    Args:
        sql_query: SQL query to execute (SELECT statements only for safety)
    Returns:
        JSON string with query results
    """
    try:
        # Only allow SELECT queries for safety
        if not sql_query.strip().upper().startswith('SELECT'):
            return json.dumps({"error": "Only SELECT queries are allowed"})

        results = execute_query(sql_query)
        return json.dumps({"results": results})
    except Exception as e:
        return json.dumps({"error": str(e)})


def persist_expense_and_shares(group_id: int, payer_id: int, total_amount: float,
                              description: str, splits: dict, split_type: str) -> bool:
    """
    Internal tool to persist expense and expense_shares to database
    Args:
        group_id: ID of the group
        payer_id: ID of the user who paid (requesting user)
        total_amount: Total amount of the expense
        description: Description of the expense
        splits: Dictionary mapping user_id to share data
        split_type: Type of split (equal, percentage, custom_amounts, itemized)
    Returns:
        bool: True if successful, False otherwise
    """
    import sqlite3
    import os

    try:
        # Use a single connection for the entire transaction
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'database', 'mock_finance.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Insert into expenses table
        expense_date = datetime.now().strftime('%Y-%m-%d')
        expense_type = 'general'  # Default type
        currency = 'USD'  # Default currency

        expense_insert = f"""
            INSERT INTO expenses (group_id, payer_id, amount, currency, description, expense_date, type)
            VALUES ({group_id}, {payer_id}, {total_amount}, '{currency}', '{description}', '{expense_date}', '{expense_type}')
        """
        cursor.execute(expense_insert)

        # Get the expense_id of the inserted expense (in same connection)
        expense_id = cursor.lastrowid
        print(f"Inserted expense with ID: {expense_id}")

        # Insert into expense_shares table
        for user_id, split_data in splits.items():
            share_amount = split_data['share_amount']
            share_insert = f"""
                INSERT INTO expense_shares (expense_id, user_id, share_amount)
                VALUES ({expense_id}, {user_id}, {share_amount})
            """
            cursor.execute(share_insert)
            print(f"Inserted share: expense_id={expense_id}, user_id={user_id}, amount={share_amount}")
        #TODO: GROUP WALLET
        urls = create_google_wallet_pass_groups(group_id=group_id)
        # Commit all changes
        conn.commit()
        conn.close()

        return urls[user_id]
    except Exception as e:
        print(f"Error persisting expense: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

from datetime import datetime
from typing import List, Dict
from sql_execution import execute_query
from utils import round_to_cents


def get_group_members(group_id: int) -> List[Dict]:
    """Get all members of a group"""
    query = f"""
        SELECT u.user_id, u.name, u.email, ug.role, ug.joined_at
        FROM users u
        JOIN user_groups ug ON u.user_id = ug.user_id
        WHERE ug.group_id = {group_id}
        ORDER BY ug.joined_at
    """
    results = execute_query(query)
    
    members = []
    for row in results:
        members.append({
            'user_id': row[0],
            'name': row[1],
            'email': row[2],
            'role': row[3],
            'joined_at': row[4]
        })
    
    return members

def get_user_groups(user_id: int) -> List[Dict]:
    """Get all groups for a user"""
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
    
    return groups

def get_group_details(group_id: int) -> Dict:
    """Get detailed information about a group"""
    query = f"""
        SELECT g.group_id, g.name, g.description, g.group_type,
                g.created_at, u.name as creator_name
        FROM groups g
        JOIN users u ON g.created_by = u.user_id
        WHERE g.group_id = {group_id}
    """
    result = execute_query(query)
    
    if not result:
        return None
    
    row = result[0]
    group_details = {
        'group_id': row[0],
        'name': row[1],
        'description': row[2],
        'group_type': row[3],
        'created_at': row[4],
        'creator_name': row[5],
        'members': get_group_members(group_id)
    }
    
    return group_details

def get_user_name(user_id: int) -> str:
    """Get user name by ID"""
    query = "SELECT name FROM users WHERE user_id = ?"
    result = execute_query(query, (user_id,))
    return result[0][0] if result else f"User_{user_id}"

def get_group_name(group_id: int) -> str:
    """Get group name by ID"""
    query = "SELECT name FROM groups WHERE group_id = ?"
    result = execute_query(query, (group_id,))
    return result[0][0] if result else f"Group_{group_id}"

def list_all_groups(self) -> List[Dict]:
    """List all groups in the system"""
    query = """
        SELECT g.group_id, g.name, g.description, g.group_type, 
                u.name as creator, COUNT(ug.user_id) as member_count
        FROM groups g
        JOIN users u ON g.created_by = u.user_id
        LEFT JOIN user_groups ug ON g.group_id = ug.group_id
        GROUP BY g.group_id
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
            'creator': row[4],
            'member_count': row[5]
        })
    
    return groups


def get_group_balances(group_id: int) -> Dict:
    """Calculate who owes what in a group"""
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
        user_id, name, paid, owes = row
        balance = round_to_cents(paid - owes)
        
        balances[user_id] = {
            'name': name,
            'paid': round_to_cents(paid),
            'owes': round_to_cents(owes),
            'balance': balance,
            'status': 'owes_money' if balance < 0 else 'owed_money' if balance > 0 else 'settled'
        }
    
    return balances


def get_group_members_simple(group_id: int) -> List[Dict]:
    """Get group members (simplified version)"""
    query = f"""
        SELECT u.user_id, u.name, u.email
        FROM users u
        JOIN user_groups ug ON u.user_id = ug.user_id
        WHERE ug.group_id = {group_id}
    """
    results = execute_query(query)
    
    return [{'user_id': row[0], 'name': row[1], 'email': row[2]} for row in results]

def get_user_name(user_id: int) -> str:
    """Get user name by ID"""
    query = "SELECT name FROM users WHERE user_id = ?"
    result = execute_query(query, (user_id,))
    return result[0][0] if result else f"User_{user_id}"
import os
import threading
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from typing import Union
from fastapi import FastAPI

class BlockingConnectionPool(pool.SimpleConnectionPool):
    def __init__(self, minconn: int, maxconn: int, *args, **kwargs):
        super().__init__(minconn, maxconn, *args, **kwargs)
        # semaphore count = how many connections total we can hand out
        self._sem = threading.BoundedSemaphore(maxconn)

    def getconn(self, *args, **kwargs):
        # block here if no tokens available
        self._sem.acquire()
        try:
            return super().getconn(*args, **kwargs)
        except Exception:
            # if something goes wrong, release our semaphore slot
            self._sem.release()
            raise

    def putconn(self, conn, *args, **kwargs):
        try:
            super().putconn(conn, *args, **kwargs)
        finally:
            # always release our slot so others can acquire
            self._sem.release()

async def init_db(app: FastAPI):
    app.state.db_pool = BlockingConnectionPool(
        minconn=1,
        maxconn=10,
        database=os.getenv('DB_NAME', 'notfound'), 
        user=os.getenv('DB_SUPER_USER', 'notfound'), 
        password=os.getenv('DB_PASSWORD', 'notfound'), 
        host=os.getenv('DB_HOST', 'localhost'), 
        port=os.getenv('DB_PORT', 5432)
    )

async def shutdown_db(app: FastAPI):
    app.state.db_pool.closeall()

def create_user(
    db_pool: BlockingConnectionPool,
    user_name: str,
    user_email: str,
    access_token: str,
    google_wallet_cred: str = 'dummy-creds'
) -> str:
    """
    Inserts a new user and a “Personal Group” for them, in one atomic transaction.
    
    Args:
      user_name:    full name of the user
      user_email:   their email address
      access_token: the OAuth token (we're storing this as password_hash here)
      google_wallet_cred:  Wallet credential string
      
    Returns:
      dict with 'user_id' and 'group_id' of the newly created records.
    """
    conn = db_pool.getconn()
    try:
        # psycopg2 will automatically start a transaction on first execute
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) Insert user, returning user_id
            cur.execute(
                """
                INSERT INTO users (name, email, password_hash, google_wallet_cred)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id
                """,
                (user_name, user_email, access_token, google_wallet_cred)
            )
            fetchone = cur.fetchone()
            if fetchone != None: user_id = fetchone['user_id']

            # 2) Insert the personal group for them
            cur.execute(
                """
                INSERT INTO groups (name, description, created_by)
                VALUES (%s, %s, %s)
                RETURNING group_id
                """,
                ("Personal Group",
                 "Auto-created personal workspace",
                 user_id)
            )
            fetchone = cur.fetchone()
            if fetchone != None: group_id = fetchone['group_id']

            # 3) Update user.personal_group_id
            cur.execute(
                """
                UPDATE users
                SET personal_group_id = %s
                WHERE user_id = %s
                """,
                (group_id, user_id)
            )

        # commit if all went well
        conn.commit()
        return user_id

    except Exception:
        conn.rollback()
        raise
    finally:
        db_pool.putconn(conn)

def get_user_by_email(
    db_pool: BlockingConnectionPool,
    user_email: str
) -> Union[str, None]:
    """
    Fetches a user record by email. Returns a dict of user fields or None if not found.
    """
    conn = db_pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                """,
                (user_email,)
            )
            user = cur.fetchone()
            return user['user_id'] if user else None
    finally:
        db_pool.putconn(conn)
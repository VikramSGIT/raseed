import os
from google.adk.agents import Agent
import psycopg2
from psycopg2 import OperationalError, ProgrammingError

def sql_tool(sql_statement: str):
    """
    Connects to a PostgreSQL database, executes a single SQL statement,
    and returns the result and status.

    Args: sql_statement (str): The single line SQL statement to execute.

    Returns:
        dict: A dictionary containing:
              - 'status' (str): 'success' or 'error'.
              - 'data' (list or None): The fetched data for SELECT queries, or None.
              - 'error' (str or None): A description of the error if one occurred.
    """

    conn = None
    response = {
        'status': 'error',
        'data': None,
        'error': None
    }
        
    try:
        conn = psycopg2.connect(database=os.getenv('DB_NAME', 'notfound'), 
                        user=os.getenv('DB_USER', 'notfound'), 
                        password=os.getenv('DB_PASSWORD', 'notfound'), 
                        host=os.getenv('DB_HOST', 'localhost'), 
                        port=os.getenv('DB_PORT', 5432))
        
        with conn.cursor() as cur:
            cur.execute(sql_statement)
            if cur.description:
                response['data'] = cur.fetchall()
            else:
                conn.commit()

            response['status'] = 'success'

    except (OperationalError, ProgrammingError) as e:
        response['error'] = f"Database Error: {e}"
        if conn:
            conn.rollback()
    except Exception as e:
        response['error'] = f"An unexpected error occurred: {e}"
    finally:
        if conn is not None:
            conn.close()
            
    return response

file_path = '../db.sql'
file_content_as_string = None
try:
    with open(file_path, 'r', encoding='utf-8') as file:
        file_content_as_string = file.read()
except FileNotFoundError:
    print(f"Error: The file at '{file_path}' was not found.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

text_to_sql_agent = Agent(
    name="text_to_sql",
    model="gemini-2.5-flash",
    description=(
        "You are an expert PostgreSQL AI assistant. Your role is to convert natural language questions into precise and efficient SQL queries based on the database schema provided below."
    ),
    instruction=(
        f"""
        You already have complete undertanding of the tables and it uses. You can process complex queries from natural language
        to sql which is ran within sql_tool and replied back in natural language based on the result of sql_tool.
        1. Analyze the User's Question: Carefully read the user's question to understand the information they are requesting.
        2. Generate SQL Query: Write a single, executable SQL query that retrieves the requested information.
        3. Run the query against sql_tool and show the output in natural language.
        4. Strictly Adhere to the Schema: 
            - Use only the table and column names defined in the schema. Do not invent new names.
            - Pay close attention to the relationships between tables (foreign keys) to construct correct JOIN clauses.
            - Ensure data types in your query match the schema.
        5. ALWAYS RUN THE QUERY, DO NOT OR SQL QUERY TO THE USER. ONLY OUTPUT IS THE RESULT OF sql_tool parsed in natural language.
        Assumptions:
            - The SQL dialect is PostgreSQL.
            - now() can be used to get the current timestamp.
        Database schema:
            {file_content_as_string}
        NOTE: Ground your knowledge with the database schema given. Have a absolute understanding of why and what perpose a table serves.
        This will give you confidence on ambiqous quries.
        """
    ),
    tools=[sql_tool],
)
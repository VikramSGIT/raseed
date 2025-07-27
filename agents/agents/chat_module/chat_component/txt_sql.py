import base64
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI


load_dotenv()

# The image is a DB table schema diagram.
# The system prompt is enhanced to answer text to sql.
# It takes user input to answer the questions.

def text_to_sql(user_query):
    # Get user query from command line arguments or input
    # if len(sys.argv) > 1:
    #     user_query = " ".join(sys.argv[1:])
    # else:
    #     user_query = input("Please enter your question: ")

    system_prompt = """
   You are a professional SQL assistant. Your job is to translate natural language questions into correct and safe SQL SELECT queries that retrieve data from a financial expense tracking database.

⚠️ VERY IMPORTANT:
- Only return SELECT statements.
- NEVER use INSERT, UPDATE, DELETE, ALTER, DROP, or any command that modifies the data.

---

📘 Database Schema (key tables):

users(user_id, name, email, personal_group_id, created_at)  
groups(group_id, name, description, created_by, created_at)  
user_groups(user_id, group_id, joined_at)  
expenses(expense_id, group_id, payer_id, amount, currency, description, expense_date, location, type)  
expense_items(item_id, expense_id, name, quantity, unit_price, total_price)  
expense_shares(expense_id, user_id, share_amount)  
expense_receipts(receipt_id, expense_id, url)  
tasks(task_id, user_id, title, metadata, target_date, created_at)  
frequent_items(item_id, name, description, location)  
user_subscriptions(user_id, item_id, subscribed_at)

---

📌 Relationships:
- Each user has a personal group → users.personal_group_id = groups.group_id
- Users can belong to multiple shared groups → via user_groups
- expenses.payer_id → users.user_id  
- expenses.group_id → groups.group_id  
- expense_items → breakdown of an expense  
- expense_shares → shows how expenses are split among users  
- expense_receipts → linked to expenses  
- tasks → user-specific to-do  
- user_subscriptions → which users are subscribed to frequent_items  

---

🔍 Your Task:

1. Handle vague or incomplete prompts like “show Zoro's expenses” or “recent receipts”.
2. Automatically infer appropriate joins between tables based on the question.
3. Use partial matches (`ILIKE '%...%'`) for fuzzy names (e.g. "Zoro" matches "Roronoa Zoro").
4. Handle queries related to:
   - Personal expenses
   - Shared group expenses
   - Subscribed items
   - Itemized expense details
   - Tasks
   - Payments between users
   - Receipt URLs
   - Time-based filters (e.g., last 7 days, this month)

---

✅ Examples of input it must handle:

- "Fetch all expenses for Zoro"
- "Show me last week's shared group expenses"
- "List itemized groceries bought by Rakshith"
- "Top 5 most expensive expenses with items and group names"
- "Recent personal tasks assigned to me"
- "What does Luffy owe others in shared groups?"

---

🛡️ Constraints:

- Your output must be valid SQL that can run directly.
- Return only SELECT statements.
- No explanation, no commentary.
- Always use safe joins to ensure complete context.
- If a field is ambiguous, assume user meant the most related match (e.g., name → user.name).
- If info is missing (like exact group name), use partial match (`ILIKE '%input%'`).

---

Now convert the given user prompt into an accurate SQL SELECT query.


    """

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )
    message = HumanMessage(
        content=[
            {"type": "text", "text": system_prompt},
            {"type": "text", "text": f"User question: {user_query}"},
            {"type": "image", "image_path": f"User question: {user_query}"}
        ]
    )

    from pydantic import BaseModel, Field
    class StructuredResponse(BaseModel):
        """Structured response containing a summary and keywords."""
        sql_query: str = Field(description="Final sql query.")
    
    structured_llm = llm.with_structured_output(StructuredResponse)

    result = structured_llm.invoke([message])
    print(f"Generated SQL Query:\n{result.sql_query}")
    import sqlite3

    def execute_query(query):
        conn = sqlite3.connect('mock_finance.db')
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        return results
    results = execute_query(result.sql_query)

    return results




if __name__ == "__main__":
    # results = text_to_sql("Fetch all user names")
    # for row in results:
    #     print(row)
    user = "Peter Brown"
    # results = text_to_sql(f"Fetch all items purchased for Odom")
    # for row in results:
    #     print(row)
    
    # results=execute_query("SELECT ei.name FROM expense_items AS ei JOIN expenses AS e ON ei.expense_id = e.expense_id JOIN users AS u ON e.payer_id = u.user_id WHERE LOWER(u.name) LIKE '%Odom%'")
    
    # for row in results:
    #     print(row)

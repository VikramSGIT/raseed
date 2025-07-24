-- This custom data type defines the nature of a financial transaction.
-- 'expense' represents a transaction made by the user.
-- 'payment' represents a transaction to settle a debt between users.
CREATE TYPE expense_type AS ENUM ('expense', 'payment');

--
-- Table: users
-- YOU ARE RESTRICTED ACCESS FROM THIS SKIP TO LINE 31.
-- 
-- This is the central table for storing all user information. Every person who signs up
-- for the application will have a record here. It holds authentication details, personal
-- information, and a link to the user's personal expense group.
--
CREATE TABLE users (
    -- user_id: A unique number that serves as the primary identifier for each user.
    user_id            BIGSERIAL PRIMARY KEY,
    -- name: The full name of the user.
    name               TEXT NOT NULL,
    -- google_wallet_cred: Google Wallet integration. Unique to each user.
    google_wallet_cred TEXT UNIQUE,
    -- email: The user's email address, used for login and communication. Must be unique.
    email              TEXT NOT NULL UNIQUE,
    -- password_hash: The user's password, stored in a secure, hashed format.
    password_hash      TEXT NOT NULL,
    -- created_at: A timestamp that records when the user account was created.
    created_at         TIMESTAMP DEFAULT now(),
    -- personal_group_id: A reference to a unique group in the `groups` table that is the user's
    -- personal space. The `UNIQUE` constraint enforces a one-to-one relationship.
    personal_group_id  BIGINT UNIQUE
);

--
-- View: safe_users_view
--
-- Contains all AI safe information about users.
CREATE VIEW safe_users_view AS
SELECT
    -- user_id: A unique number that serves as the primary identifier for each user.
    user_id,
    -- name: The full name of the user.
    name,
    -- created_at: A timestamp that records when the user account was created.
    created_at,
    -- personal_group_id: A reference to a unique group in the `groups` table that is the user's
    -- personal space. The `UNIQUE` constraint enforces a one-to-one relationship.
    personal_group_id
FROM
    -- The table which you had restricted access from.
    users;

--
-- Table: groups
--
-- This table stores information about expense groups. A group can be a collection of
-- users for a shared purpose (e.g., a trip, a household) or a personal space for an
-- individual's expenses. The intent of the group can be understood by studying the
-- description.
--
CREATE TABLE groups (
    -- group_id: A unique number identifying each group.
    group_id    BIGSERIAL PRIMARY KEY,
    -- name: The name of the group (e.g., "Goa Trip", "Monthly Household Bills").
    name        TEXT NOT NULL,
    -- description: More detailed description of the group's purpose.
    description TEXT,
    -- created_by: A reference to the user_id of the user who originally created the group.
    created_by  BIGINT NOT NULL REFERENCES users(user_id),
    -- created_at: A timestamp recording when the group was created.
    created_at  TIMESTAMP DEFAULT now()
);

--
-- Foreign Key Constraint: fk_users_personal_group
--
-- This constraint is added after both `users` and `groups` tables are created to resolve
-- a circular dependency. It formally links a user's personal_group_id to a valid group_id,
-- completing the one-to-one relationship.
--
ALTER TABLE users
ADD CONSTRAINT fk_users_personal_group
FOREIGN KEY (personal_group_id)
REFERENCES groups(group_id);

--
-- Table: user_groups
--
-- This is a junction table that manages the many-to-many relationship between users and
-- groups. It allows a user to be a member of multiple groups and a group to have multiple
-- members. This table is primarily for non-personal, shared groups.
--
CREATE TABLE user_groups (
    -- user_id: A reference to the user.
    user_id   BIGINT NOT NULL REFERENCES users(user_id),
    -- group_id: A reference to the group.
    group_id  BIGINT NOT NULL REFERENCES groups(group_id),
    -- joined_at: A timestamp that records when the user became a member of the group.
    joined_at TIMESTAMP DEFAULT now(),
    -- The composite primary key prevents a user from being added to the same group more than once.
    PRIMARY KEY (user_id, group_id)
);

--
-- Table: expenses
--
-- This is the core table for logging all financial transactions. It records who paid,
-- how much was paid, for what group, and whether it was a shared expense or a payment.
-- This table is also used to log personal transactions, by have `personal_group_id` from
-- `users` table as the `group_id` of the expense.
--
CREATE TABLE expenses (
    -- expense_id: A unique number identifying each expense record.
    expense_id    BIGSERIAL PRIMARY KEY,
    -- group_id: A reference linking the expense to a specific group.
    group_id      BIGINT NOT NULL REFERENCES groups(group_id),
    -- payer_id: A reference to the user_id of the person who paid for the expense.
    payer_id      BIGINT NOT NULL REFERENCES users(user_id),
    -- amount: The total monetary value of the expense.
    amount        NUMERIC(12,2) NOT NULL,
    -- currency: The three-letter currency code (e.g., 'INR').
    currency      CHAR(3) NOT NULL DEFAULT 'INR',
    -- description: A text description of the expense.
    description   TEXT,
    -- expense_date: The date on which the expense was incurred.
    expense_date  DATE NOT NULL,
    -- location: Text field for where the expense occurred. Which is tracked using coordinates.
    location      TEXT,
    -- type: Specifies if the transaction is an 'expense' or a 'payment'.
    type          expense_type NOT NULL DEFAULT 'expense',
    -- created_at: A timestamp for when the expense was logged in the system.
    created_at    TIMESTAMP DEFAULT now()
);

--
-- Table: expense_shares
--
-- This table is crucial for splitting costs. It defines how a single expense from the
-- `expenses` table is divided among different users, specifying each person's share.
--
CREATE TABLE expense_shares (
    -- expense_id: A reference to the specific expense being shared.
    expense_id   BIGINT NOT NULL REFERENCES expenses(expense_id),
    -- user_id: A reference to the user who is responsible for a portion of the expense.
    user_id      BIGINT NOT NULL REFERENCES users(user_id),
    -- share_amount: The exact amount of money that the specified user owes.
    share_amount NUMERIC(12,2) NOT NULL,
    -- The composite primary key ensures each user has only one share per expense.
    PRIMARY KEY (expense_id, user_id)
);

--
-- Table: expense_receipts
--
-- This table stores links to receipt images or files associated with an expense,
-- providing a verifiable proof of purchase. This can be used for later retreival
-- of past reciepts.
--
CREATE TABLE expense_receipts (
    -- receipt_id: A unique number for each receipt record.
    receipt_id    BIGSERIAL PRIMARY KEY,
    -- expense_id: A reference linking the receipt back to its corresponding expense.
    expense_id    BIGINT NOT NULL REFERENCES expenses(expense_id),
    -- url: The URL where the receipt image or file is stored.
    url           TEXT NOT NULL,
    -- uploaded_at: A timestamp recording when the receipt was uploaded.
    uploaded_at   TIMESTAMP DEFAULT now()
);

--
-- Table: expense_items
--
-- This table allows for an itemized breakdown of a single expense. For example, a grocery
-- bill can be broken down into individual items with their own quantity and price.
--
CREATE TABLE expense_items (
    -- item_id: A unique number for each item record.
    item_id      BIGSERIAL PRIMARY KEY,
    -- expense_id: A reference linking this item to its parent expense record.
    expense_id   BIGINT NOT NULL REFERENCES expenses(expense_id),
    -- name: The name of the individual item (e.g., "Organic Milk").
    name         TEXT NOT NULL,
    -- quantity: The quantity of the item purchased.
    quantity     NUMERIC(12,2) DEFAULT 1,
    -- unit_price: The price of a single unit of the item.
    unit_price   NUMERIC(12,2) NOT NULL,
    -- total_price: A generated column that is automatically calculated as (quantity * unit_price).
    total_price  NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED
);

--
-- Table: tasks
--
-- A simple table for creating a to-do list feature within the application, allowing
-- users to create, assign, and track tasks.
--
CREATE TABLE tasks (
    -- task_id: A unique number identifying each task.
    task_id     BIGSERIAL PRIMARY KEY,
    -- user_id: A reference to the user to whom the task is assigned or who created it.
    user_id     BIGINT NOT NULL REFERENCES users(user_id),
    -- title: A short, descriptive title for the task.
    title       TEXT NOT NULL,
    -- metadata: A field where a prompt can be stored, which can be used to check if the
    -- had completed the task or not.
    metadata    TEXT,
    -- target_date: An optional due date for the task.
    target_date DATE,
    -- created_at: A timestamp recording when the task was created.
    created_at  TIMESTAMP DEFAULT now()
);

--
-- Table: frequent_items
--
-- This table improves user experience by storing items that users purchase regularly
-- within a certian location, this table helps users to know common item prices within
-- thier locality. Helps is triggering price drop alerts.
--
CREATE TABLE frequent_items (
    -- item_id: A unique identifier for the frequent item.
    item_id     BIGSERIAL PRIMARY KEY,
    -- name: The name of the frequently purchased item (e.g., "Tomato", "Potato").
    name        TEXT NOT NULL,
    -- description: An optional description of the item.
    description TEXT,
    -- location: An optional field for the common location of purchase, in coordinates.
    location    TEXT,
    -- created_at: A timestamp for when this frequent item was first saved.
    created_at  TIMESTAMP DEFAULT now()
);

--
-- Table: user_subscriptions
--
-- This junction table links users to items in the `frequent_items` table. It represents
-- a user's personal list of "subscribed" items so the user can recieve alert if there is
-- any price drop.
--
CREATE TABLE user_subscriptions (
    -- user_id: A reference to the user.
    user_id       BIGINT NOT NULL REFERENCES users(user_id),
    -- item_id: A reference to the frequent item.
    item_id       BIGINT NOT NULL REFERENCES frequent_items(item_id),
    -- subscribed_at: A timestamp for when the user added this item to their list.
    subscribed_at TIMESTAMP DEFAULT now(),
    -- The composite primary key prevents a user from subscribing to the same item more than once.
    PRIMARY KEY (user_id, item_id)
);
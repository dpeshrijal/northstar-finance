import os
import psycopg2
from faker import Faker
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def seed_database():
    # 1. Connect to Azure Postgres
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        sslmode="require"
    )
    cur = conn.cursor()
    print("Connected to Azure PostgreSQL...")

    # 2. Enable pgvector extension (Standard for AI apps)
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # 3. Create Tables
    print("Creating tables...")
    cur.execute("""
        DROP TABLE IF EXISTS transactions;
        DROP TABLE IF EXISTS gl_accounts;
        DROP TABLE IF EXISTS cost_centers;

        CREATE TABLE gl_accounts (
            id VARCHAR(10) PRIMARY KEY,
            name VARCHAR(100),
            category VARCHAR(50)
        );

        CREATE TABLE cost_centers (
            id VARCHAR(10) PRIMARY KEY,
            name VARCHAR(100),
            region VARCHAR(50)
        );

        CREATE TABLE transactions (
            id SERIAL PRIMARY KEY,
            date DATE,
            amount DECIMAL(12, 2),
            currency VARCHAR(3) DEFAULT 'EUR',
            description TEXT,
            gl_account_id VARCHAR(10) REFERENCES gl_accounts(id),
            cost_center_id VARCHAR(10) REFERENCES cost_centers(id),
            is_budget BOOLEAN DEFAULT FALSE
        );
    """)

    # 4. Insert Master Data (Accounts and Cost Centers)
    gl_data = [
        ('REV100', 'Product Revenue', 'Revenue'),
        ('EXP200', 'Travel & Entertainment', 'Expense'),
        ('EXP300', 'Marketing Spend', 'Expense'),
        ('EXP400', 'Office Supplies', 'Expense'),
        ('EXP500', 'Salaries & Wages', 'Expense')
    ]
    cur.executemany("INSERT INTO gl_accounts VALUES (%s, %s, %s)", gl_data)

    cc_data = [
        ('CC_DACH', 'Sales DACH', 'DACH'),
        ('CC_USA', 'Sales North America', 'USA'),
        ('CC_APAC', 'Sales Asia-Pacific', 'APAC'),
        ('CC_HQ', 'Corporate Headquarters', 'Global')
    ]
    cur.executemany("INSERT INTO cost_centers VALUES (%s, %s, %s)", cc_data)

    # 5. Generate 1000 Transactions using Faker
    fake = Faker()
    print("Generating 1000 transactions...")
    
    transactions = []
    # Start date 1 year ago
    start_date = datetime.now() - timedelta(days=365)

    for _ in range(1000):
        # Decide if this is a "Budget" entry or an "Actual" transaction
        is_budget = random.choice([True, False, False, False]) # 25% budget entries
        
        gl_id = random.choice([g[0] for g in gl_data])
        cc_id = random.choice([c[0] for c in cc_data])
        
        # Make revenue positive and expenses negative (Standard Accounting)
        base_amount = fake.pydecimal(left_digits=5, right_digits=2, positive=True)
        amount = base_amount if gl_id == 'REV100' else -base_amount

        # Policy Violation Hook: Create a client dinner over 500 EUR in Munich (DACH)
        # This gives our AI something specific to "find" later
        if _ == 500: 
            desc = "Client Dinner Munich - VIP Event"
            amount = -1200.00
            gl_id = 'EXP200'
            cc_id = 'CC_DACH'
        else:
            desc = fake.sentence(nb_words=5)

        transactions.append((
            fake.date_between(start_date=start_date, end_date='now'),
            amount,
            desc,
            gl_id,
            cc_id,
            is_budget
        ))

    cur.executemany(
        "INSERT INTO transactions (date, amount, description, gl_account_id, cost_center_id, is_budget) VALUES (%s, %s, %s, %s, %s, %s)",
        transactions
    )

    conn.commit()
    cur.close()
    conn.close()
    print("Database successfully seeded with Mock SAP data!")

if __name__ == "__main__":
    seed_database()
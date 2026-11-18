import sys
import os

# Add parent dir to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import init_db, engine
from database.models import Base

def main():
    print("Creating tables in PostgreSQL database 'xauusd_assistant'...")
    init_db()
    print("Tables created successfully:")
    for table_name in Base.metadata.tables.keys():
        print(f" - {table_name}")

if __name__ == "__main__":
    main()

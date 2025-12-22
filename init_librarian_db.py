"""
Initialize Librarian database tables
Run this once on Railway to set up conversation management
"""

import os
from librarian_schema import init_db, seed_initial_data

if __name__ == '__main__':
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        exit(1)
    
    print(f"Initializing database...")
    engine = init_db(database_url)
    print("Tables created!")
    
    print("Seeding initial data...")
    seed_initial_data(engine)
    print("Done! Librarian database ready.")
    
    print("\nCreated:")
    print("- Users: thom, karen")
    print("- Topics: Patents, ForgedOS, Haku, Heritage, MOA, Governance, Valuation, General")

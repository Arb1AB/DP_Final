import sqlite3
import sys

def view_database(db_file):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("Tables in the database:")
        for table in tables:
            print(f"- {table[0]}")
        
        print("\n" + "="*50)
        
        # Show data from each table
        for table in tables:
            table_name = table[0]
            print(f"\nData from {table_name} table:")
            
            try:
                # Get column names
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [column[1] for column in cursor.fetchall()]
                print("Columns:", columns)
                
                # Get all data
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                
                # Print rows
                for row in rows:
                    print(row)
                    
            except sqlite3.Error as e:
                print(f"Error reading table {table_name}: {e}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    db_file = "attendance.db"
    if len(sys.argv) > 1:
        db_file = sys.argv[1]
    view_database(db_file)

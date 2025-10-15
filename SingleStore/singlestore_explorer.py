# singlestore_explorer.py
from singlestore_simple_manager import SingleStoreManager

def interactive_explorer():
    """Interactive explorer for SingleStore database"""
    db = SingleStoreManager()
    
    print("🔍 SingleStore Interactive Explorer")
    print("=" * 50)
    
    while True:
        print("\nOptions:")
        print("1. Show database info")
        print("2. List all tables")
        print("3. Show table structure")
        print("4. Run custom query")
        print("5. Property market insights")
        print("6. Export data")
        print("7. Exit")
        
        choice = input("\nEnter your choice (1-7): ").strip()
        
        if choice == '1':
            # Database info
            info = db.execute_query("SELECT DATABASE() as db, CURRENT_USER() as user, NOW() as time")
            if info:
                print(f"\n💾 Database Info:")
                print(f"  Database: {info[0]['db']}")
                print(f"  User: {info[0]['user']}")
                print(f"  Time: {info[0]['time']}")
        
        elif choice == '2':
            # List tables
            tables = db.execute_query("SHOW TABLES")
            if tables:
                print(f"\n📊 Tables in database:")
                for table in tables:
                    table_name = list(table.values())[0]
                    # Get row count for each table
                    count_result = db.execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
                    if count_result:
                        print(f"  {table_name}: {count_result[0]['count']:,} rows")
        
        elif choice == '3':
            # Show table structure
            table_name = input("Enter table name: ").strip()
            if table_name:
                structure = db.execute_query(f"DESCRIBE {table_name}")
                if structure:
                    print(f"\n📋 Structure of {table_name}:")
                    for col in structure:
                        print(f"  {col['Field']:20} {col['Type']:20} {col['Null']:10}")
                else:
                    print("❌ Table not found or error occurred")
        
        elif choice == '4':
            # Custom query
            query = input("Enter your SQL query: ").strip()
            if query.upper().startswith('SELECT'):
                try:
                    results = db.execute_query(query)
                    if results:
                        print(f"\n📊 Query Results ({len(results)} rows):")
                        for i, row in enumerate(results[:10], 1):  # Show first 10 rows
                            print(f"  Row {i}: {row}")
                        if len(results) > 10:
                            print(f"  ... and {len(results) - 10} more rows")
                    else:
                        print("✅ Query executed successfully (no results)")
                except Exception as e:
                    print(f"❌ Query failed: {e}")
            else:
                print("❌ Only SELECT queries are allowed for safety")
        
        elif choice == '5':
            # Property insights
            print("\n🏠 Property Market Insights:")
            
            # Total properties by year
            yearly = db.execute_query("""
                SELECT YEAR(date) as year, COUNT(*) as count
                FROM uk_price_paid 
                WHERE date IS NOT NULL
                GROUP BY YEAR(date)
                ORDER BY year DESC
                LIMIT 5
            """)
            if yearly:
                print("\n📅 Recent Transaction Volumes:")
                for row in yearly:
                    print(f"  {row['year']}: {row['count']:,} transactions")
            
            # Average price by property type
            prices_by_type = db.execute_query("""
                SELECT type, AVG(price) as avg_price
                FROM uk_price_paid 
                WHERE type IS NOT NULL
                GROUP BY type
                ORDER BY avg_price DESC
            """)
            if prices_by_type:
                print("\n💰 Average Prices by Property Type:")
                for row in prices_by_type:
                    print(f"  {row['type']}: £{row['avg_price']:,.0f}")
        
        elif choice == '6':
            # Export data
            table_name = input("Enter table name to export: ").strip()
            if table_name:
                limit = input("Enter row limit (default 1000): ").strip()
                limit = int(limit) if limit.isdigit() else 1000
                
                data = db.execute_query(f"SELECT * FROM {table_name} LIMIT {limit}")
                if data:
                    import pandas as pd
                    df = pd.DataFrame(data)
                    filename = f"{table_name}_export.csv"
                    df.to_csv(filename, index=False)
                    print(f"✅ Exported {len(data)} rows to {filename}")
                else:
                    print("❌ No data found or table doesn't exist")
        
        elif choice == '7':
            print("👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    interactive_explorer()
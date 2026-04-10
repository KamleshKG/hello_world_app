# singlestore_manager.py
import pymysql
import pandas as pd
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SingleStoreManager:
    def __init__(self):
        self.connection_config = {
            'host': os.getenv('SINGLESTORE_HOST'),
            'port': int(os.getenv('SINGLESTORE_PORT', 3333)),
            'user': os.getenv('SINGLESTORE_USER'),
            'password': os.getenv('SINGLESTORE_PASSWORD'),
            'database': os.getenv('SINGLESTORE_DATABASE'),
            'ssl': {'ssl_disabled': False},
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor,
            'autocommit': True
        }
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        connection = None
        try:
            connection = pymysql.connect(**self.connection_config)
            yield connection
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise
        finally:
            if connection:
                connection.close()
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    result = cursor.fetchall()
                    return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return []
    
    def execute_command(self, command: str, params: Optional[tuple] = None) -> int:
        """Execute INSERT, UPDATE, DELETE commands"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(command, params)
                    return cursor.rowcount
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return 0
    
    def get_dataframe(self, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """Execute query and return results as pandas DataFrame"""
        try:
            with self.get_connection() as conn:
                df = pd.read_sql(query, conn, params=params)
                return df
        except Exception as e:
            logger.error(f"DataFrame creation failed: {e}")
            return pd.DataFrame()
    
    def analyze_uk_price_paid(self):
        """Analyze the existing uk_price_paid table"""
        print("🏠 Analyzing UK Price Paid Table")
        print("=" * 50)
        
        # Get table structure
        structure = self.execute_query("DESCRIBE uk_price_paid")
        if structure:
            print("\n📋 Table Structure:")
            for col in structure:
                print(f"  {col['Field']:20} {col['Type']:20} {col['Null']:10} {col['Key']:10}")
        
        # Get sample data
        sample_data = self.execute_query("SELECT * FROM uk_price_paid LIMIT 5")
        if sample_data:
            print(f"\n📊 Sample Data (first 5 rows):")
            for i, row in enumerate(sample_data, 1):
                print(f"  Row {i}: {row}")
        
        # Get basic statistics
        stats = self.execute_query("""
            SELECT 
                COUNT(*) as total_rows,
                MIN(date) as earliest_date,
                MAX(date) as latest_date,
                AVG(price) as avg_price,
                MIN(price) as min_price,
                MAX(price) as max_price
            FROM uk_price_paid
        """)
        
        if stats:
            stats_row = stats[0]
            print(f"\n📈 Basic Statistics:")
            print(f"  Total Rows: {stats_row['total_rows']:,}")
            print(f"  Date Range: {stats_row['earliest_date']} to {stats_row['latest_date']}")
            print(f"  Price Stats: Avg £{stats_row['avg_price']:,.2f}, Min £{stats_row['min_price']:,}, Max £{stats_row['max_price']:,}")
        
        # Get price distribution by year
        yearly_stats = self.execute_query("""
            SELECT 
                YEAR(date) as year,
                COUNT(*) as transactions,
                AVG(price) as avg_price,
                MIN(price) as min_price,
                MAX(price) as max_price
            FROM uk_price_paid 
            GROUP BY YEAR(date)
            ORDER BY year
        """)
        
        if yearly_stats:
            print(f"\n📅 Yearly Price Statistics:")
            for row in yearly_stats:
                print(f"  {row['year']}: {row['transactions']:,} transactions, Avg £{row['avg_price']:,.0f}")
    
    def create_sample_tables(self):
        """Create some sample tables for testing"""
        print("\n🛠️ Creating Sample Tables")
        print("=" * 50)
        
        # Create users table
        users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            full_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE
        )
        """
        self.execute_command(users_table)
        print("✅ Created 'users' table")
        
        # Create products table
        products_table = """
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            price DECIMAL(10,2),
            category VARCHAR(100),
            stock_quantity INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
        self.execute_command(products_table)
        print("✅ Created 'products' table")
        
        # Insert sample data
        sample_users = [
            ('john_doe', 'john@example.com', 'John Doe'),
            ('jane_smith', 'jane@example.com', 'Jane Smith'),
            ('bob_wilson', 'bob@example.com', 'Bob Wilson')
        ]
        
        for user in sample_users:
            self.execute_command(
                "INSERT IGNORE INTO users (username, email, full_name) VALUES (%s, %s, %s)",
                user
            )
        print("✅ Added sample users")
        
        sample_products = [
            ('Laptop', 'High-performance laptop', 999.99, 'Electronics', 10),
            ('Desk Chair', 'Ergonomic office chair', 249.99, 'Furniture', 15),
            ('Coffee Mug', 'Ceramic coffee mug', 12.99, 'Kitchen', 50)
        ]
        
        for product in sample_products:
            self.execute_command(
                "INSERT IGNORE INTO products (name, description, price, category, stock_quantity) VALUES (%s, %s, %s, %s, %s)",
                product
            )
        print("✅ Added sample products")
    
    def run_analytics_queries(self):
        """Run some analytical queries"""
        print("\n📊 Running Analytical Queries")
        print("=" * 50)
        
        # Get all tables
        tables = self.execute_query("SHOW TABLES")
        table_names = [list(table.values())[0] for table in tables]
        print(f"📋 Database Tables: {table_names}")
        
        # Analyze each table
        for table_name in table_names:
            print(f"\n🔍 Analyzing table: {table_name}")
            
            # Get row count
            count_result = self.execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
            if count_result:
                print(f"  Rows: {count_result[0]['count']:,}")
            
            # Get column info
            columns = self.execute_query(f"DESCRIBE {table_name}")
            if columns:
                print(f"  Columns: {[col['Field'] for col in columns]}")
    
    def export_uk_data_to_csv(self, limit: int = 1000):
        """Export UK price paid data to CSV"""
        print(f"\n💾 Exporting UK Price Paid Data (first {limit} rows)")
        
        df = self.get_dataframe(f"SELECT * FROM uk_price_paid LIMIT {limit}")
        if not df.empty:
            filename = f"uk_price_paid_sample_{limit}.csv"
            df.to_csv(filename, index=False)
            print(f"✅ Exported {len(df)} rows to {filename}")
            print(f"📊 DataFrame shape: {df.shape}")
            print(f"📝 Columns: {list(df.columns)}")
            return df
        else:
            print("❌ No data to export")
            return pd.DataFrame()

def main():
    db = SingleStoreManager()
    
    print("🚀 SingleStore Database Manager")
    print("=" * 60)
    
    # Test connection
    test_result = db.execute_query("SELECT 1 as test, NOW() as time, @@version as version")
    if test_result:
        print("✅ Connection successful!")
        print(f"   SingleStore Version: {test_result[0]['version']}")
        print(f"   Current Time: {test_result[0]['time']}")
    else:
        print("❌ Connection failed!")
        return
    
    # Analyze existing UK price paid data
    db.analyze_uk_price_paid()
    
    # Create sample tables
    db.create_sample_tables()
    
    # Run analytics
    db.run_analytics_queries()
    
    # Export data to CSV
    sample_data = db.export_uk_data_to_csv(1000)
    
    # Show some advanced queries
    print("\n🔬 Advanced Queries")
    print("=" * 50)
    
    # Top 10 most expensive properties
    expensive_properties = db.execute_query("""
        SELECT * FROM uk_price_paid 
        ORDER BY price DESC 
        LIMIT 10
    """)
    
    if expensive_properties:
        print("\n💰 Top 10 Most Expensive Properties:")
        for i, prop in enumerate(expensive_properties, 1):
            print(f"  {i}. £{prop['price']:,} - {prop.get('date', 'N/A')}")
    
    # Property count by type (if the column exists)
    try:
        property_types = db.execute_query("""
            SELECT type, COUNT(*) as count 
            FROM uk_price_paid 
            WHERE type IS NOT NULL
            GROUP BY type 
            ORDER BY count DESC
            LIMIT 10
        """)
        
        if property_types:
            print(f"\n🏘️  Property Types Distribution:")
            for pt in property_types:
                print(f"  {pt['type']}: {pt['count']:,} properties")
    except:
        print("ℹ️  'type' column not found in uk_price_paid table")

if __name__ == "__main__":
    main()
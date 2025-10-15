# singlestore_manager_fixed.py
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
        """Execute query and return results as pandas DataFrame - FIXED VERSION"""
        try:
            # First get the data as dictionaries
            data = self.execute_query(query, params)
            if data:
                # Convert to DataFrame
                df = pd.DataFrame(data)
                return df
            else:
                return pd.DataFrame()
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
    
    def create_sample_tables_singlestore(self):
        """Create sample tables compatible with SingleStore unique key restrictions"""
        print("\n🛠️ Creating SingleStore Compatible Tables")
        print("=" * 50)
        
        # Drop existing tables if they exist
        self.execute_command("DROP TABLE IF EXISTS users")
        self.execute_command("DROP TABLE IF EXISTS products")
        
        # Create users table with SingleStore compatible unique constraints
        users_table = """
        CREATE TABLE users (
            id INT AUTO_INCREMENT,
            username VARCHAR(50) NOT NULL,
            email VARCHAR(100) NOT NULL,
            full_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (id, username),  -- Include unique column in primary key
            UNIQUE KEY (username, id)    -- Include shard key in unique constraint
        )
        """
        self.execute_command(users_table)
        print("✅ Created 'users' table with SingleStore compatible constraints")
        
        # Create products table (no unique constraints needed)
        products_table = """
        CREATE TABLE products (
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
            (1, 'john_doe', 'john@example.com', 'John Doe'),
            (2, 'jane_smith', 'jane@example.com', 'Jane Smith'),
            (3, 'bob_wilson', 'bob@example.com', 'Bob Wilson')
        ]
        
        for user in sample_users:
            self.execute_command(
                "INSERT INTO users (id, username, email, full_name) VALUES (%s, %s, %s, %s)",
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
                "INSERT INTO products (name, description, price, category, stock_quantity) VALUES (%s, %s, %s, %s, %s)",
                product
            )
        print("✅ Added sample products")
    
    def run_advanced_analytics(self):
        """Run advanced analytical queries on UK price data"""
        print("\n🔬 Advanced Analytics on UK Price Data")
        print("=" * 50)
        
        # Property type analysis
        type_analysis = self.execute_query("""
            SELECT 
                type,
                COUNT(*) as count,
                AVG(price) as avg_price,
                MIN(price) as min_price,
                MAX(price) as max_price,
                COUNT(*) * 100.0 / (SELECT COUNT(*) FROM uk_price_paid) as percentage
            FROM uk_price_paid 
            GROUP BY type 
            ORDER BY count DESC
        """)
        
        if type_analysis:
            print("\n🏘️ Property Type Analysis:")
            for row in type_analysis:
                print(f"  {row['type']:15} {row['count']:>6,} properties ({row['percentage']:.1f}%) - Avg £{row['avg_price']:,.0f}")
        
        # Price distribution by county (top 10)
        county_analysis = self.execute_query("""
            SELECT 
                county,
                COUNT(*) as transactions,
                AVG(price) as avg_price,
                MAX(price) as max_price
            FROM uk_price_paid 
            WHERE county IS NOT NULL AND county != ''
            GROUP BY county
            ORDER BY avg_price DESC
            LIMIT 10
        """)
        
        if county_analysis:
            print("\n🏛️ Top 10 Counties by Average Price:")
            for i, row in enumerate(county_analysis, 1):
                print(f"  {i:2}. {row['county']:30} £{row['avg_price']:>10,.0f} (max: £{row['max_price']:>10,})")
        
        # Monthly trends for current year
        monthly_trends = self.execute_query("""
            SELECT 
                YEAR(date) as year,
                MONTH(date) as month,
                COUNT(*) as transactions,
                AVG(price) as avg_price
            FROM uk_price_paid 
            WHERE YEAR(date) = 2024
            GROUP BY YEAR(date), MONTH(date)
            ORDER BY year, month
        """)
        
        if monthly_trends:
            print(f"\n📈 2024 Monthly Trends:")
            for row in monthly_trends:
                print(f"  {row['year']}-{row['month']:02d}: {row['transactions']:>5,} transactions, Avg £{row['avg_price']:,.0f}")
    
    def export_data_properly(self, limit: int = 1000):
        """Export data properly without pandas warnings"""
        print(f"\n💾 Exporting UK Price Paid Data (first {limit} rows)")
        
        # Get data using our fixed method
        data = self.execute_query(f"SELECT * FROM uk_price_paid LIMIT {limit}")
        
        if data:
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Fix data types
            numeric_columns = ['price', 'is_new']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            date_columns = ['date']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            filename = f"uk_price_paid_sample_{limit}.csv"
            df.to_csv(filename, index=False)
            print(f"✅ Exported {len(df)} rows to {filename}")
            print(f"📊 DataFrame shape: {df.shape}")
            print(f"📝 Columns: {list(df.columns)}")
            print(f"🔢 Data types:")
            print(df.dtypes)
            
            return df
        else:
            print("❌ No data to export")
            return pd.DataFrame()

def main():
    db = SingleStoreManager()
    
    print("🚀 SingleStore Database Manager - FIXED VERSION")
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
    
    # Create sample tables with SingleStore compatible syntax
    db.create_sample_tables_singlestore()
    
    # Run advanced analytics
    db.run_advanced_analytics()
    
    # Export data properly
    sample_data = db.export_data_properly(1000)
    
    # Show expensive properties analysis
    expensive_properties = db.execute_query("""
        SELECT 
            date, price, type, town, county
        FROM uk_price_paid 
        ORDER BY price DESC 
        LIMIT 5
    """)
    
    if expensive_properties:
        print(f"\n💰 Top 5 Most Expensive Properties:")
        for i, prop in enumerate(expensive_properties, 1):
            print(f"  {i}. £{prop['price']:>,} - {prop['type']} in {prop['town']}, {prop['county']} ({prop['date']})")

if __name__ == "__main__":
    main()
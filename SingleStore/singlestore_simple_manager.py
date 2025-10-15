# singlestore_simple_manager.py
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
            data = self.execute_query(query, params)
            if data:
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
                print(f"  Row {i}: Price £{row['price']:,} - {row['type']} in {row['town']}")
        
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
    
    def create_simple_tables(self):
        """Create simple tables without complex constraints for SingleStore"""
        print("\n🛠️ Creating Simple Tables (No Unique Constraints)")
        print("=" * 50)
        
        # Create simple users table without unique constraints
        users_table = """
        CREATE TABLE IF NOT EXISTS simple_users (
            id INT,
            username VARCHAR(50),
            email VARCHAR(100),
            full_name VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
        self.execute_command(users_table)
        print("✅ Created 'simple_users' table")
        
        # Create simple products table
        products_table = """
        CREATE TABLE IF NOT EXISTS simple_products (
            id INT,
            name VARCHAR(200),
            price DECIMAL(10,2),
            category VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
        self.execute_command(products_table)
        print("✅ Created 'simple_products' table")
        
        # Insert sample data
        sample_users = [
            (1, 'john_doe', 'john@example.com', 'John Doe'),
            (2, 'jane_smith', 'jane@example.com', 'Jane Smith'),
            (3, 'bob_wilson', 'bob@example.com', 'Bob Wilson')
        ]
        
        for user in sample_users:
            self.execute_command(
                "INSERT INTO simple_users (id, username, email, full_name) VALUES (%s, %s, %s, %s)",
                user
            )
        print("✅ Added sample users")
        
        sample_products = [
            (1, 'Laptop', 999.99, 'Electronics'),
            (2, 'Desk Chair', 249.99, 'Furniture'),
            (3, 'Coffee Mug', 12.99, 'Kitchen')
        ]
        
        for product in sample_products:
            self.execute_command(
                "INSERT INTO simple_products (id, name, price, category) VALUES (%s, %s, %s, %s)",
                product
            )
        print("✅ Added sample products")
    
    def run_property_analysis(self):
        """Run comprehensive property analysis"""
        print("\n🔬 Property Market Analysis")
        print("=" * 50)
        
        # Property type distribution
        type_analysis = self.execute_query("""
            SELECT 
                type,
                COUNT(*) as count,
                AVG(price) as avg_price,
                COUNT(*) * 100.0 / (SELECT COUNT(*) FROM uk_price_paid) as percentage
            FROM uk_price_paid 
            WHERE type IS NOT NULL
            GROUP BY type 
            ORDER BY count DESC
        """)
        
        if type_analysis:
            print("\n🏘️ Property Type Distribution:")
            for row in type_analysis:
                print(f"  {row['type']:15} {row['count']:>6,} properties ({row['percentage']:.1f}%) - Avg £{row['avg_price']:,.0f}")
        
        # Top locations by average price
        location_analysis = self.execute_query("""
            SELECT 
                town,
                county,
                COUNT(*) as transactions,
                AVG(price) as avg_price
            FROM uk_price_paid 
            WHERE town IS NOT NULL AND town != ''
            GROUP BY town, county
            HAVING COUNT(*) >= 10
            ORDER BY avg_price DESC
            LIMIT 10
        """)
        
        if location_analysis:
            print("\n🏛️ Top 10 Locations by Average Price (min 10 transactions):")
            for i, row in enumerate(location_analysis, 1):
                print(f"  {i:2}. {row['town']} ({row['county']}): £{row['avg_price']:,.0f} ({row['transactions']} transactions)")
        
        # Price trends by year
        yearly_trends = self.execute_query("""
            SELECT 
                YEAR(date) as year,
                COUNT(*) as transactions,
                AVG(price) as avg_price,
                MIN(price) as min_price,
                MAX(price) as max_price
            FROM uk_price_paid 
            WHERE date IS NOT NULL
            GROUP BY YEAR(date)
            ORDER BY year DESC
            LIMIT 10
        """)
        
        if yearly_trends:
            print("\n📈 Price Trends (Last 10 Years):")
            for row in yearly_trends:
                print(f"  {row['year']}: {row['transactions']:>6,} transactions, Avg £{row['avg_price']:,.0f}")
    
    def export_analysis_results(self):
        """Export analysis results to CSV files"""
        print("\n💾 Exporting Analysis Results")
        print("=" * 50)
        
        # Export property type analysis
        type_data = self.execute_query("""
            SELECT type, COUNT(*) as count, AVG(price) as avg_price
            FROM uk_price_paid 
            WHERE type IS NOT NULL
            GROUP BY type 
            ORDER BY count DESC
        """)
        
        if type_data:
            df_types = pd.DataFrame(type_data)
            df_types.to_csv('property_types_analysis.csv', index=False)
            print("✅ Exported property types analysis to property_types_analysis.csv")
        
        # Export yearly trends
        yearly_data = self.execute_query("""
            SELECT 
                YEAR(date) as year,
                COUNT(*) as transactions,
                AVG(price) as avg_price
            FROM uk_price_paid 
            WHERE date IS NOT NULL
            GROUP BY YEAR(date)
            ORDER BY year
        """)
        
        if yearly_data:
            df_yearly = pd.DataFrame(yearly_data)
            df_yearly.to_csv('yearly_trends.csv', index=False)
            print("✅ Exported yearly trends to yearly_trends.csv")
        
        # Export sample data for further analysis
        sample_data = self.execute_query("""
            SELECT * FROM uk_price_paid 
            WHERE date >= '2024-01-01'
            LIMIT 1000
        """)
        
        if sample_data:
            df_sample = pd.DataFrame(sample_data)
            df_sample.to_csv('recent_properties_sample.csv', index=False)
            print("✅ Exported recent properties sample to recent_properties_sample.csv")

def main():
    db = SingleStoreManager()
    
    print("🚀 SingleStore Property Data Analyzer")
    print("=" * 60)
    
    # Test connection
    test_result = db.execute_query("SELECT 1 as test, NOW() as time")
    if test_result:
        print("✅ Connection successful!")
        print(f"   Current Time: {test_result[0]['time']}")
    else:
        print("❌ Connection failed!")
        return
    
    # Analyze UK price paid data
    db.analyze_uk_price_paid()
    
    # Create simple tables (no complex constraints)
    db.create_simple_tables()
    
    # Run property market analysis
    db.run_property_analysis()
    
    # Export results
    db.export_analysis_results()
    
    # Show some interesting insights
    print("\n💡 Interesting Insights")
    print("=" * 50)
    
    # Most expensive property this year
    expensive = db.execute_query("""
        SELECT price, date, type, town, county 
        FROM uk_price_paid 
        WHERE YEAR(date) = 2024
        ORDER BY price DESC 
        LIMIT 1
    """)
    
    if expensive:
        prop = expensive[0]
        print(f"🏆 Most expensive property in 2024:")
        print(f"   £{prop['price']:,} - {prop['type']} in {prop['town']}, {prop['county']}")
    
    # Cheapest property this year (excluding obvious errors)
    cheapest = db.execute_query("""
        SELECT price, date, type, town, county 
        FROM uk_price_paid 
        WHERE YEAR(date) = 2024 AND price > 10000
        ORDER BY price ASC 
        LIMIT 1
    """)
    
    if cheapest:
        prop = cheapest[0]
        print(f"💰 Most affordable property in 2024:")
        print(f"   £{prop['price']:,} - {prop['type']} in {prop['town']}, {prop['county']}")

if __name__ == "__main__":
    main()
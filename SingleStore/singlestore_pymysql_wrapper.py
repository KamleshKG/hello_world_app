# singlestore_pymysql_wrapper_fixed.py
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

class SingleStoreDB:
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
                    logger.info(f"Query executed successfully. Rows returned: {len(result)}")
                    return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query was: {query}")
            logger.error(f"Params were: {params}")
            return []
    
    def execute_command(self, command: str, params: Optional[tuple] = None) -> int:
        """Execute INSERT, UPDATE, DELETE commands"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(command, params)
                    rows_affected = cursor.rowcount
                    logger.info(f"Command executed successfully. Rows affected: {rows_affected}")
                    return rows_affected
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            logger.error(f"Command was: {command}")
            logger.error(f"Params were: {params}")
            return 0
    
    def get_dataframe(self, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """Execute query and return results as pandas DataFrame"""
        try:
            with self.get_connection() as conn:
                df = pd.read_sql(query, conn, params=params)
                logger.info(f"DataFrame created with {len(df)} rows")
                return df
        except Exception as e:
            logger.error(f"DataFrame creation failed: {e}")
            return pd.DataFrame()
    
    def batch_insert_dataframe(self, df: pd.DataFrame, table_name: str) -> bool:
        """Batch insert DataFrame into database table"""
        try:
            if df.empty:
                logger.warning("DataFrame is empty, nothing to insert")
                return True
            
            # Create placeholders for the insert query
            columns = ', '.join(df.columns)
            placeholders = ', '.join(['%s'] * len(df.columns))
            
            insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Convert DataFrame to list of tuples
                    data_tuples = [tuple(row) for row in df.to_numpy()]
                    cursor.executemany(insert_query, data_tuples)
                    logger.info(f"Successfully inserted {len(df)} rows into {table_name}")
                    return True
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test the database connection with SingleStore compatible SQL"""
        try:
            # SingleStore compatible test query
            result = self.execute_query("SELECT 1 as test_value, NOW() as current_time")
            if result:
                row = result[0]
                logger.info(f"✅ Connection test successful:")
                logger.info(f"   Test Value: {row['test_value']}")
                logger.info(f"   Current Time: {row['current_time']}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def get_version(self) -> str:
        """Get SingleStore version"""
        try:
            result = self.execute_query("SELECT @@version as version")
            if result:
                return result[0]['version']
            return "Unknown"
        except Exception as e:
            logger.error(f"Failed to get version: {e}")
            return "Error"

# Usage examples
def main():
    db = SingleStoreDB()
    
    # Test connection
    if db.test_connection():
        print("✅ Database connection successful!")
        
        # Get SingleStore version
        version = db.get_version()
        print(f"🔧 SingleStore Version: {version}")
        
        # List all tables
        tables = db.execute_query("SHOW TABLES")
        if tables:
            print("\n📊 Tables in database:")
            for table in tables:
                table_name = list(table.values())[0]
                print(f"  - {table_name}")
                
                # Show table structure
                try:
                    structure = db.execute_query(f"DESCRIBE {table_name}")
                    if structure:
                        print(f"    Columns: {[col['Field'] for col in structure]}")
                except Exception as e:
                    print(f"    Could not describe table: {e}")
        else:
            print("ℹ️  No tables found in database")
        
        # Create a sample table with SingleStore compatible syntax
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS sample_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150),
            age INT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
        try:
            db.execute_command(create_table_sql)
            print("✅ Sample table created/verified")
        except Exception as e:
            print(f"❌ Table creation failed: {e}")
        
        # Insert sample data
        insert_sql = """
        INSERT INTO sample_data (name, email, age) 
        VALUES (%s, %s, %s)
        """
        sample_records = [
            ('John Doe', 'john.doe@example.com', 30),
            ('Jane Smith', 'jane.smith@example.com', 25),
            ('Bob Johnson', 'bob.johnson@example.com', 35)
        ]
        
        try:
            for record in sample_records:
                db.execute_command(insert_sql, record)
            print("✅ Sample data inserted")
        except Exception as e:
            print(f"❌ Data insertion failed: {e}")
        
        # Query data as DataFrame
        try:
            df = db.get_dataframe("SELECT * FROM sample_data ORDER BY created_at DESC")
            if not df.empty:
                print("\n📋 Sample Data:")
                print(df)
            else:
                print("ℹ️  No data found in sample_data table")
        except Exception as e:
            print(f"❌ Query failed: {e}")
        
        # Show database information
        try:
            db_info = db.execute_query("""
                SELECT 
                    DATABASE() as current_database,
                    CURRENT_USER() as current_user
            """)
            if db_info:
                print(f"\n💾 Database Info: {db_info[0]}")
        except Exception as e:
            print(f"❌ Database info query failed: {e}")

if __name__ == "__main__":
    main()
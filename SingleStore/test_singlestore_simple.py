# test_singlestore_simple.py
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def test_basic_queries():
    """Test basic SingleStore queries"""
    
    config = {
        'host': os.getenv('SINGLESTORE_HOST'),
        'port': int(os.getenv('SINGLESTORE_PORT', 3333)),
        'user': os.getenv('SINGLESTORE_USER'),
        'password': os.getenv('SINGLESTORE_PASSWORD'),
        'database': os.getenv('SINGLESTORE_DATABASE'),
        'ssl': {'ssl_disabled': False},
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }
    
    connection = pymysql.connect(**config)
    
    try:
        with connection.cursor() as cursor:
            print("🔍 Testing SingleStore Queries:")
            print("-" * 40)
            
            # Test 1: Basic connection
            cursor.execute("SELECT 1 as test, NOW() as time")
            result = cursor.fetchone()
            print(f"✅ Basic query: {result}")
            
            # Test 2: Version
            cursor.execute("SELECT @@version as version")
            result = cursor.fetchone()
            print(f"✅ Version: {result['version']}")
            
            # Test 3: Show databases
            cursor.execute("SHOW DATABASES")
            databases = [row['Database'] for row in cursor.fetchall()]
            print(f"✅ Databases: {databases}")
            
            # Test 4: Show tables
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
            print(f"✅ Tables: {tables}")
            
            # Test 5: Current database info
            cursor.execute("SELECT DATABASE() as db, CURRENT_USER() as user")
            result = cursor.fetchone()
            print(f"✅ Current: DB={result['db']}, User={result['user']}")
            
    finally:
        connection.close()

if __name__ == "__main__":
    test_basic_queries()
# singlestore_sqlalchemy_ssl.py
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, DateTime, Float, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
import pandas as pd
import os
from dotenv import load_dotenv
import logging
from typing import Optional, List, Dict, Any
import ssl
import pymysql

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLAlchemy Base
Base = declarative_base()

class SingleStoreDB:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.metadata = MetaData()
        self._setup_engine()
    
    def _get_ssl_context(self):
        """Create SSL context for SingleStore Cloud connection"""
        try:
            # SingleStore requires SSL but often works with the system's default certs
            ssl_context = ssl.create_default_context()
            # You can also download the SingleStore CA bundle if needed
            # ssl_context.load_verify_locations(cafile="path/to/singlestore_bundle.pem")
            return ssl_context
        except Exception as e:
            logger.warning(f"SSL context creation warning: {e}")
            return None
    
    def _setup_engine(self):
        """Setup SQLAlchemy engine with SSL configuration"""
        try:
            # Get configuration from environment
            host = os.getenv('SINGLESTORE_HOST')
            port = os.getenv('SINGLESTORE_PORT', 3333)
            user = os.getenv('SINGLESTORE_USER')
            password = os.getenv('SINGLESTORE_PASSWORD')
            database = os.getenv('SINGLESTORE_DATABASE')
            use_ssl = os.getenv('SINGLESTORE_USE_SSL', 'true').lower() == 'true'
            
            # Build connection URL
            connection_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
            
            # SSL configuration for SingleStore Cloud
            connect_args = {}
            if use_ssl:
                ssl_context = self._get_ssl_context()
                if ssl_context:
                    connect_args['ssl'] = ssl_context
                else:
                    # Fallback: use basic SSL without certificate verification
                    connect_args['ssl'] = {'ssl_disabled': False}
                
                # Alternative SSL approach for pymysql
                connect_args['ssl_verify_cert'] = os.getenv('SINGLESTORE_SSL_VERIFY_CERT', 'true').lower() == 'true'
                connect_args['ssl_verify_identity'] = False
            
            logger.info(f"🔐 SSL enabled: {use_ssl}")
            
            # Create engine with connection pooling
            self.engine = create_engine(
                connection_url,
                pool_size=int(os.getenv('SINGLESTORE_POOL_SIZE', 5)),
                max_overflow=int(os.getenv('SINGLESTORE_MAX_OVERFLOW', 10)),
                pool_recycle=int(os.getenv('SINGLESTORE_POOL_RECYCLE', 3600)),
                echo=False,
                connect_args=connect_args,
                pool_pre_ping=True
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            logger.info("✅ SQLAlchemy engine configured successfully with SSL")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup engine: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test_value, NOW() as current_time, VERSION() as db_version"))
                row = result.fetchone()
                logger.info(f"✅ Connection test successful:")
                logger.info(f"   Test Value: {row['test_value']}")
                logger.info(f"   Current Time: {row['current_time']}")
                logger.info(f"   DB Version: {row['db_version']}")
                return True
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False

    # ... [rest of the methods remain the same as previous example]
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Session error: {e}")
            raise
        finally:
            session.close()
    
    def execute_query(self, query: str, params: Dict = None) -> List[Dict[str, Any]]:
        """Execute a raw SQL query and return results"""
        try:
            with self.engine.connect() as conn:
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))
                
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as e:
            logger.error(f"❌ Query execution failed: {e}")
            return []
    
    def execute_command(self, command: str, params: Dict = None) -> int:
        """Execute DML commands (INSERT, UPDATE, DELETE)"""
        try:
            with self.engine.connect() as conn:
                if params:
                    result = conn.execute(text(command), params)
                else:
                    result = conn.execute(text(command))
                conn.commit()
                logger.info(f"✅ Command executed. Rows affected: {result.rowcount}")
                return result.rowcount
        except SQLAlchemyError as e:
            logger.error(f"❌ Command execution failed: {e}")
            return 0
    
    def get_dataframe(self, query: str, params: Dict = None) -> pd.DataFrame:
        """Execute query and return results as pandas DataFrame"""
        try:
            df = pd.read_sql(text(query), self.engine, params=params)
            logger.info(f"✅ DataFrame created with {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"❌ DataFrame creation failed: {e}")
            return pd.DataFrame()
    
    def close(self):
        """Close database connections"""
        if self.engine:
            self.engine.dispose()
            logger.info("🔌 Database connections closed")

# Alternative approach using direct PyMySQL with SSL
def test_direct_pymysql_connection():
    """Test direct PyMySQL connection with SSL"""
    try:
        connection = pymysql.connect(
            host=os.getenv('SINGLESTORE_HOST'),
            port=int(os.getenv('SINGLESTORE_PORT', 3333)),
            user=os.getenv('SINGLESTORE_USER'),
            password=os.getenv('SINGLESTORE_PASSWORD'),
            database=os.getenv('SINGLESTORE_DATABASE'),
            ssl={'ssl_disabled': False},  # Enable SSL
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 as test, NOW() as time")
            result = cursor.fetchone()
            print(f"✅ Direct PyMySQL connection successful: {result}")
        
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ Direct PyMySQL connection failed: {e}")
        return False

# Download SingleStore CA certificate (run this once)
def download_singlestore_ca_bundle():
    """Download SingleStore CA bundle if needed"""
    import urllib.request
    ca_url = "https://portal.singlestore.com/static/ca/singlestore_bundle.pem"
    ca_file = "singlestore_bundle.pem"
    
    if not os.path.exists(ca_file):
        try:
            urllib.request.urlretrieve(ca_url, ca_file)
            print(f"✅ Downloaded SingleStore CA bundle to {ca_file}")
        except Exception as e:
            print(f"❌ Failed to download CA bundle: {e}")
    
    return ca_file

def main():
    # Option 1: Download CA bundle if needed
    # ca_file = download_singlestore_ca_bundle()
    
    # Option 2: Test direct connection first
    print("Testing direct PyMySQL connection...")
    if test_direct_pymysql_connection():
        print("Direct connection successful! Proceeding with SQLAlchemy...")
    
    # Initialize database connection with SQLAlchemy
    db = SingleStoreDB()
    
    try:
        # Test connection
        if db.test_connection():
            print("✅ SQLAlchemy connection successful!")
            
            # Example: List tables
            tables = db.execute_query("SHOW TABLES")
            if tables:
                print("\n📊 Tables in database:")
                for table in tables:
                    print(f"  - {list(table.values())[0]}")
            
            # Example: Create a simple table
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS test_connection (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            db.execute_command(create_table_sql)
            
            # Insert test data
            db.execute_command(
                "INSERT INTO test_connection (message) VALUES (%s)",
                {"message": "Hello from SQLAlchemy with SSL!"}
            )
            
            # Query test data
            results = db.execute_query("SELECT * FROM test_connection ORDER BY created_at DESC")
            if results:
                print("\n📝 Test data:")
                for row in results:
                    print(f"  ID: {row['id']}, Message: {row['message']}, Created: {row['created_at']}")
        
    except Exception as e:
        logger.error(f"❌ Main execution failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
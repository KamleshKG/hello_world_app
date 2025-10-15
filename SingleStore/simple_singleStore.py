# singlestore_simple_ssl.py
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_engine_with_ssl():
    """Create SQLAlchemy engine with SSL for SingleStore"""
    
    host = os.getenv('SINGLESTORE_HOST')
    port = os.getenv('SINGLESTORE_PORT', 3333)
    user = os.getenv('SINGLESTORE_USER')
    password = os.getenv('SINGLESTORE_PASSWORD')
    database = os.getenv('SINGLESTORE_DATABASE')
    
    # Connection URL
    connection_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    
    # SSL configuration that works with SingleStore Cloud
    connect_args = {
        'ssl': {'ssl_disabled': False},  # Enable SSL
        'ssl_verify_cert': False,        # Disable certificate verification (if having CA issues)
        'ssl_verify_identity': False
    }
    
    engine = create_engine(
        connection_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=True  # Set to True to see SQL queries
    )
    
    return engine

def main():
    try:
        engine = create_engine_with_ssl()
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test, NOW() as time, VERSION() as version"))
            row = result.fetchone()
            print(f"✅ Connection successful!")
            print(f"   Test: {row['test']}")
            print(f"   Time: {row['time']}")
            print(f"   Version: {row['version']}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    main()
# data_explorer.py
import pandas as pd
from singlestore_manager import SingleStoreManager

def explore_uk_data():
    """Quick exploration of UK price paid data"""
    db = SingleStoreManager()
    
    # Get basic info
    df = db.get_dataframe("SELECT * FROM uk_price_paid LIMIT 100")
    
    if not df.empty:
        print("🏠 UK Price Paid Data Overview")
        print("=" * 40)
        print(f"Shape: {df.shape}")
        print(f"\nColumns: {list(df.columns)}")
        print(f"\nFirst 5 rows:")
        print(df.head())
        print(f"\nData types:")
        print(df.dtypes)
        print(f"\nBasic statistics:")
        print(df.describe())
        
        # Check for missing values
        print(f"\nMissing values:")
        print(df.isnull().sum())
        
        return df
    return pd.DataFrame()

def create_custom_query():
    """Run custom queries on the data"""
    db = SingleStoreManager()
    
    # Example: Price trends over time
    query = """
    SELECT 
        YEAR(date) as year,
        MONTH(date) as month,
        COUNT(*) as transaction_count,
        AVG(price) as average_price,
        SUM(price) as total_volume
    FROM uk_price_paid 
    WHERE date IS NOT NULL
    GROUP BY YEAR(date), MONTH(date)
    ORDER BY year, month
    LIMIT 24
    """
    
    try:
        result = db.get_dataframe(query)
        if not result.empty:
            print("\n📈 Monthly Price Trends (Last 24 months):")
            print(result)
            
            # Save to CSV
            result.to_csv('monthly_price_trends.csv', index=False)
            print("💾 Saved to monthly_price_trends.csv")
    except Exception as e:
        print(f"Query failed: {e}")

if __name__ == "__main__":
    df = explore_uk_data()
    create_custom_query()
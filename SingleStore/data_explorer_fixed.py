# data_explorer_fixed.py
import pandas as pd
from singlestore_manager_fixed import SingleStoreManager

def explore_uk_data_properly():
    """Quick exploration of UK price paid data - FIXED VERSION"""
    db = SingleStoreManager()
    
    # Get basic info using fixed method
    data = db.execute_query("SELECT * FROM uk_price_paid LIMIT 100")
    
    if data:
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
        
        print("🏠 UK Price Paid Data Overview - FIXED")
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

def create_custom_queries_fixed():
    """Run custom queries on the data - FIXED VERSION"""
    db = SingleStoreManager()
    
    # Example: Price trends over time
    query = """
    SELECT 
        YEAR(date) as year,
        MONTH(date) as month,
        COUNT(*) as transaction_count,
        AVG(price) as average_price
    FROM uk_price_paid 
    WHERE date IS NOT NULL AND YEAR(date) >= 2020
    GROUP BY YEAR(date), MONTH(date)
    ORDER BY year, month
    """
    
    try:
        data = db.execute_query(query)
        if data:
            df = pd.DataFrame(data)
            print("\n📈 Price Trends Since 2020:")
            print(df.head(12))  # Show first 12 months
            
            # Save to CSV
            df.to_csv('monthly_price_trends_fixed.csv', index=False)
            print("💾 Saved to monthly_price_trends_fixed.csv")
            
            # Create a simple visualization
            try:
                import matplotlib.pyplot as plt
                
                plt.figure(figsize=(12, 6))
                plt.plot(df['average_price'])
                plt.title('Average Property Price Over Time')
                plt.xlabel('Month Index')
                plt.ylabel('Average Price (£)')
                plt.grid(True)
                plt.savefig('price_trends.png')
                print("📊 Saved visualization to price_trends.png")
            except ImportError:
                print("ℹ️  Install matplotlib for visualizations: pip install matplotlib")
    except Exception as e:
        print(f"Query failed: {e}")

def analyze_property_types():
    """Analyze property types distribution"""
    db = SingleStoreManager()
    
    query = """
    SELECT 
        type,
        COUNT(*) as count,
        AVG(price) as avg_price,
        MIN(price) as min_price,
        MAX(price) as max_price
    FROM uk_price_paid
    WHERE type IS NOT NULL
    GROUP BY type
    ORDER BY count DESC
    """
    
    data = db.execute_query(query)
    if data:
        df = pd.DataFrame(data)
        print("\n🏠 Property Types Analysis:")
        print(df)
        
        # Create a bar chart
        try:
            import matplotlib.pyplot as plt
            
            plt.figure(figsize=(10, 6))
            plt.bar(df['type'], df['count'])
            plt.title('Property Types Distribution')
            plt.xlabel('Property Type')
            plt.ylabel('Number of Properties')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig('property_types.png')
            print("📊 Saved property types chart to property_types.png")
        except ImportError:
            pass

if __name__ == "__main__":
    df = explore_uk_data_properly()
    create_custom_queries_fixed()
    analyze_property_types()
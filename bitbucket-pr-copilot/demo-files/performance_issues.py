"""
Demo file with performance issues for optimization suggestions
"""
import time
import requests
from typing import List

class DataProcessor:
    def __init__(self):
        self.data_cache = {}
    
    # Inefficient string concatenation in loop
    def build_large_report(self, items: List[str]) -> str:
        report = ""
        for item in items:
            report += f"Item: {item}\n"  # Inefficient
        return report
    
    # N+1 query problem simulation
    def get_user_details(self, user_ids: List[int]) -> List[dict]:
        details = []
        for user_id in user_ids:
            # Simulate database call for each user
            user_data = self._fetch_user_from_db(user_id)
            details.append(user_data)
        return details
    
    def _fetch_user_from_db(self, user_id: int) -> dict:
        time.sleep(0.1)  # Simulate DB call latency
        return {"id": user_id, "name": f"User {user_id}"}
    
    # Unnecessary computations in loop
    def calculate_statistics(self, numbers: List[float]) -> dict:
        results = {}
        for i in range(len(numbers)):
            # Recalculating sum multiple times
            total = sum(numbers)
            avg = total / len(numbers)
            results[i] = {
                "value": numbers[i],
                "is_above_avg": numbers[i] > avg
            }
        return results
    
    # Memory inefficiency with large lists
    def process_large_dataset(self):
        massive_list = []
        for i in range(1000000):
            massive_list.append(i * 2)  # Building huge list in memory
        
        return [x for x in massive_list if x % 3 == 0]  # Inefficient filtering

# Synchronous network calls in loop
def fetch_multiple_urls(urls: List[str]) -> List[str]:
    responses = []
    for url in urls:
        response = requests.get(url)  # Blocking call
        responses.append(response.text)
    return responses

# Recursive function without base case optimization
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)  # Exponential time complexity
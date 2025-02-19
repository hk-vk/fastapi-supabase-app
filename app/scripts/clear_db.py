import sqlite3

def clear_analysis_cache_db(db_path: str = "analysis_cache.db"):
    """Clear the entire analysis cache database"""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM analysis_cache")
            conn.commit()
        print("Analysis cache database cleared.")
        
    except Exception as e:
        print(f"Cache clear error: {e}")

if __name__ == "__main__":
    clear_analysis_cache_db()

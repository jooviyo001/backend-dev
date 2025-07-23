import sys
sys.path.append('.')

from models.database import get_db
from models.models import Organization

def test_simple_query():
    """测试简单的组织查询"""
    db = next(get_db())
    try:
        # 最简单的查询
        print("Testing basic Organization query...")
        orgs = db.query(Organization).all()
        print(f"Found {len(orgs)} organizations")
        
        for org in orgs:
            print(f"ID: {org.id}, Name: {org.name}, Code: {org.code}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_simple_query()
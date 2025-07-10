import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from src.models.model import Base
from src.database.database import SQLALCHEMY_DATABASE_URL


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("create_tables")

def create_tables():
    """Create all tables in the database"""
    
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        Base.metadata.create_all(engine)
        logger.info("Tables created successfully!")
        return True
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

if __name__ == "__main__":
    success = create_tables()
    sys.exit(0 if success else 1)
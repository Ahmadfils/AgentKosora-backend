from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Créer l'engine SQLAlchemy pour Supabase PostgreSQL
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.DEBUG
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base pour les modèles
Base = declarative_base()

@contextmanager
def get_db() -> Session:
    """Dépendance pour obtenir une session de base de données"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    """Initialiser la base de données (créer les tables)"""
    try:
        # Importer tous les modèles ici
        from app.models.user import User
        from app.models.exam import Exam
        from app.models.question import Question
        from app.models.correction import CorrectionResult
        
        # Créer les tables
        Base.metadata.create_all(bind=engine)
        logger.info("Base de données initialisée")
        
    except Exception as e:
        logger.error(f"Erreur initialisation base de données: {str(e)}")
        raise

def test_connection():
    """Tester la connexion à la base de données"""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Connexion à Supabase PostgreSQL réussie")
        return True
    except Exception as e:
        logger.error(f"Erreur connexion à Supabase: {str(e)}")
        return False
from sqlalchemy import Column, String, Float, Text, DateTime, JSON, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base

class CorrectionResult(Base):
    __tablename__ = "correction_results"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(String, nullable=False, index=True)
    student_id = Column(String, nullable=False, index=True)
    student_name = Column(String)
    
    # Données d'entrée
    extracted_text = Column(Text)
    exam_context = Column(JSON)
    
    # Résultats de correction
    corrections = Column(JSON)  # Liste de QuestionCorrection en JSON
    total_score = Column(Float)
    max_score = Column(Float)
    percentage = Column(Float)
    feedback = Column(Text)
    
    # Métadonnées
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    processing_time = Column(Float)  # en secondes
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    
    def to_dict(self):
        return {
            "id": self.id,
            "exam_id": self.exam_id,
            "student_id": self.student_id,
            "student_name": self.student_name,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "percentage": self.percentage,
            "status": self.status,
            "processing_time": self.processing_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
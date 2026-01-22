from sqlalchemy import Column, String, Text, Float, DateTime, JSON, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.db.base import Base

class Exam(Base):
    __tablename__ = "exams"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    description = Column(Text)
    total_points = Column(Float, default=0)
    created_by = Column(String, nullable=False)  # ID enseignant
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    question_type = Column(String, default="essay")  # essay, multiple_choice, etc.
    correct_answer = Column(Text)
    max_points = Column(Float, default=1.0)
    keywords = Column(JSON)  # Mots-clés pour l'évaluation
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    exam = relationship("Exam", back_populates="questions")
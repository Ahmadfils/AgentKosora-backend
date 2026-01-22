from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class QuestionType(str, Enum):
    ESSAY = "essay"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    CALCULATION = "calculation"

# ==================== REQUÊTES ====================

class MobileCorrectionRequest(BaseModel):
    """Requête pour corriger une copie"""
    exam_id: str = Field(..., description="ID de l'examen")
    student_id: str = Field(..., description="ID de l'étudiant")
    student_name: str = Field(..., description="Nom de l'étudiant")
    extracted_text: str = Field(..., description="Texte extrait par OCR")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Métadonnées additionnelles"
    )

class ScanRequest(BaseModel):
    """Requête pour scanner une copie"""
    exam_id: Optional[str] = Field(None, description="ID de l'examen (optionnel)")
    auto_correct: bool = Field(
        default=True,
        description="Corriger automatiquement après scan"
    )

class BulkCorrectionRequest(BaseModel):
    """Requête pour corriger plusieurs copies"""
    exam_id: str = Field(..., description="ID de l'examen")
    student_copies: List['StudentCopyRequest'] = Field(
        ...,
        description="Liste des copies étudiantes"
    )

class StudentCopyRequest(BaseModel):
    """Copie d'un étudiant pour batch"""
    student_id: Optional[str] = Field(None, description="ID étudiant")
    student_name: str = Field(..., description="Nom étudiant")
    extracted_text: str = Field(..., description="Texte OCR")

class ExamCreateRequest(BaseModel):
    """Requête pour créer un examen"""
    title: str = Field(..., description="Titre de l'examen")
    subject: str = Field(..., description="Matière")
    description: Optional[str] = Field(None, description="Description")
    questions: List['QuestionCreate'] = Field(..., description="Questions")
    teacher_id: str = Field(..., description="ID de l'enseignant")

class QuestionCreate(BaseModel):
    """Question pour création d'examen"""
    question_number: Optional[int] = Field(None, description="Numéro de question")
    text: str = Field(..., description="Texte de la question")
    type: QuestionType = Field(default=QuestionType.ESSAY, description="Type de question")
    correct_answer: str = Field(..., description="Réponse correcte")
    max_points: float = Field(default=1.0, ge=0.1, description="Points maximum")
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Mots-clés pour l'évaluation"
    )

# ==================== RÉPONSES ====================

class ScanResponse(BaseModel):
    """Réponse de scan OCR"""
    scan_id: str = Field(..., description="ID unique du scan")
    success: bool = Field(..., description="Succès de l'extraction")
    extracted_text: str = Field(..., description="Texte extrait (tronqué)")
    text_length: int = Field(..., description="Longueur totale du texte")
    question_count: int = Field(..., description="Nombre de questions détectées")
    exam_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Informations sur l'examen"
    )
    timestamp: str = Field(..., description="Timestamp ISO")

class MobileCorrectionResponse(BaseModel):
    """Réponse de correction mobile"""
    success: bool = Field(..., description="Succès de la correction")
    correction_id: str = Field(..., description="ID unique de la correction")
    exam_id: str = Field(..., description="ID de l'examen")
    student_id: str = Field(..., description="ID de l'étudiant")
    student_name: str = Field(..., description="Nom de l'étudiant")
    
    # Scores
    total_score: float = Field(..., description="Score total")
    max_score: float = Field(..., description="Score maximum possible")
    percentage: float = Field(..., ge=0, le=100, description="Pourcentage")
    grade: str = Field(..., description="Note lettre (A, B, C, D, F)")
    
    # Corrections détaillées
    corrections: List[Dict[str, Any]] = Field(
        ...,
        description="Corrections par question"
    )
    
    # Feedback
    overall_feedback: str = Field(..., description="Feedback global")
    strengths: List[str] = Field(..., description="Points forts")
    areas_to_improve: List[str] = Field(..., description="Points à améliorer")
    
    # Métadonnées
    timestamp: str = Field(..., description="Timestamp ISO")
    processing_time: Optional[float] = Field(
        None,
        description="Temps de traitement en secondes"
    )

class ExamResponse(BaseModel):
    """Réponse avec détails d'un examen"""
    id: str = Field(..., description="ID de l'examen")
    title: str = Field(..., description="Titre")
    subject: str = Field(..., description="Matière")
    description: Optional[str] = Field(None, description="Description")
    total_points: float = Field(..., description="Points totaux")
    question_count: int = Field(..., description="Nombre de questions")
    created_at: Optional[str] = Field(None, description="Date de création")
    questions: List[Dict[str, Any]] = Field(
        ...,
        description="Questions de l'examen"
    )

class StudentCorrectionHistory(BaseModel):
    """Historique de corrections d'un étudiant"""
    correction_id: str = Field(..., description="ID de la correction")
    exam_id: str = Field(..., description="ID de l'examen")
    exam_title: str = Field(..., description="Titre de l'examen")
    total_score: float = Field(..., description="Score total")
    max_score: float = Field(..., description="Score maximum")
    percentage: float = Field(..., description="Pourcentage")
    grade: str = Field(..., description="Note")
    feedback: Optional[str] = Field(None, description="Feedback")
    corrected_at: Optional[str] = Field(None, description="Date de correction")

# Mettre à jour les références circulaires
BulkCorrectionRequest.update_forward_refs()
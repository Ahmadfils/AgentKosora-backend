from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import json
import logging

from app.core.ocr_parser import extract_text_from_image
from app.core.rag import get_exam_context, add_exam_to_rag
from app.core.llm import LLMProcessor
from app.core.scoring import calculate_score
from app.mcp.server import MCPServer
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.exam import Exam, Question
from app.models.correction import CorrectionResult
from app.schemas.mobile import (
    MobileCorrectionRequest,
    MobileCorrectionResponse,
    ExamCreateRequest,
    ExamResponse,
    ScanRequest,
    ScanResponse,
    StudentCorrectionHistory,
    BulkCorrectionRequest
)

router = APIRouter(prefix="/mobile", tags=["Mobile API"])
logger = logging.getLogger(__name__)

# Instances globales
llm_processor = LLMProcessor()
mcp_server = MCPServer()

# ==================== ENDPOINTS PRINCIPAUX ====================

@router.post("/scan/ocr", response_model=ScanResponse)
async def scan_and_extract_text(
    file: UploadFile = File(...),
    exam_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Endpoint 1: Scanner une copie et extraire le texte avec OCR
    
    Scénario: L'application mobile envoie une photo/scan
    Retourne: Le texte extrait et des métadonnées
    """
    try:
        logger.info(f"Reçu fichier: {file.filename}, Type: {file.content_type}")
        
        # 1. Extraction OCR
        extracted_text = await extract_text_from_image(file)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Texte insuffisant extrait. Vérifiez la qualité de l'image."
                }
            )
        
        # 2. Si un exam_id est fourni, récupérer les infos de l'examen
        exam_info = None
        if exam_id:
            exam = db.query(Exam).filter(Exam.id == exam_id).first()
            if exam:
                exam_info = {
                    "id": exam.id,
                    "title": exam.title,
                    "subject": exam.subject,
                    "total_points": exam.total_points
                }
        
        # 3. Analyser le texte extrait (détecter nombre de questions)
        question_count = _detect_question_count(extracted_text)
        
        # 4. Sauvegarder temporairement le scan
        scan_id = str(uuid.uuid4())
        
        return ScanResponse(
            scan_id=scan_id,
            success=True,
            extracted_text=extracted_text[:5000],  # Limité pour la réponse
            text_length=len(extracted_text),
            question_count=question_count,
            exam_info=exam_info,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Erreur OCR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur d'extraction OCR: {str(e)}")

@router.post("/correct/single", response_model=MobileCorrectionResponse)
async def correct_single_copy(
    request: MobileCorrectionRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint 2: Corriger une copie unique avec IA
    
    Scénario: Le texte OCR est déjà extrait, on veut la correction
    Retourne: Feedback, points, corrections détaillées
    """
    try:
        logger.info(f"Correction pour étudiant: {request.student_name}, Examen: {request.exam_id}")
        
        # 1. Vérifier l'examen existe
        exam = db.query(Exam).filter(Exam.id == request.exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Examen non trouvé")
        
        # 2. Vérifier si l'examen a des questions dans RAG
        exam_context = await get_exam_context(request.exam_id, request.extracted_text)
        
        if not exam_context.get("questions"):
            # Si pas de questions dans RAG, utiliser les questions de la base
            questions = db.query(Question).filter(Question.exam_id == request.exam_id).all()
            if questions:
                # Ajouter les questions au RAG
                await add_exam_to_rag(
                    exam_id=request.exam_id,
                    questions=[
                        {
                            "text": q.text,
                            "type": q.question_type,
                            "max_points": q.max_points,
                            "correct_answer": q.correct_answer,
                            "keywords": q.keywords
                        }
                        for q in questions
                    ]
                )
                # Recharger le contexte
                exam_context = await get_exam_context(request.exam_id, request.extracted_text)
        
        # 3. Corriger avec le système MCP
        correction_result = await mcp_server.process_correction(
            correction_id=str(uuid.uuid4()),
            exam_id=request.exam_id,
            student_id=request.student_id,
            student_name=request.student_name,
            extracted_text=request.extracted_text,
            exam_context=exam_context
        )
        
        # 4. Enrichir avec LLM pour des feedbacks personnalisés
        enhanced_feedback = await llm_processor.enhance_feedback(
            corrections=correction_result.corrections,
            student_name=request.student_name,
            total_score=correction_result.total_score,
            max_score=correction_result.max_score
        )
        
        # 5. Sauvegarder le résultat
        db_correction = CorrectionResult(
            id=correction_result.correction_id,
            exam_id=request.exam_id,
            student_id=request.student_id,
            student_name=request.student_name,
            extracted_text=request.extracted_text[:5000],
            corrections=json.dumps([c.dict() for c in correction_result.corrections]),
            total_score=correction_result.total_score,
            max_score=correction_result.max_score,
            percentage=correction_result.percentage,
            feedback=enhanced_feedback,
            status="completed",
            processing_time=correction_result.processing_time,
            created_at=datetime.utcnow()
        )
        
        db.add(db_correction)
        db.commit()
        
        # 6. Préparer la réponse mobile
        response = MobileCorrectionResponse(
            success=True,
            correction_id=correction_result.correction_id,
            exam_id=request.exam_id,
            student_id=request.student_id,
            student_name=request.student_name,
            total_score=correction_result.total_score,
            max_score=correction_result.max_score,
            percentage=correction_result.percentage,
            grade=_calculate_grade(correction_result.percentage),
            corrections=[
                {
                    "question_number": c.question_number,
                    "question_text": c.question_text[:100] + "..." if len(c.question_text) > 100 else c.question_text,
                    "student_answer": c.student_answer[:200] + "..." if len(c.student_answer) > 200 else c.student_answer,
                    "points_awarded": c.points_awarded,
                    "max_points": c.max_points,
                    "feedback": c.feedback
                }
                for c in correction_result.corrections
            ],
            overall_feedback=enhanced_feedback,
            strengths=_extract_strengths(correction_result.corrections),
            areas_to_improve=_extract_improvements(correction_result.corrections),
            timestamp=datetime.utcnow().isoformat(),
            processing_time=correction_result.processing_time
        )
        
        logger.info(f"Correction réussie: {correction_result.total_score}/{correction_result.max_score}")
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur de correction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur de correction IA: {str(e)}")

@router.post("/correct/bulk", response_model=Dict[str, Any])
async def correct_bulk_copies(
    request: BulkCorrectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Endpoint 3: Corriger plusieurs copies en batch (pour un prof)
    
    Scénario: L'enseignant upload plusieurs copies d'un même examen
    Retourne: ID de batch et statut
    """
    batch_id = str(uuid.uuid4())
    
    # Lancer la correction en arrière-plan
    background_tasks.add_task(
        _process_bulk_correction,
        batch_id=batch_id,
        request=request,
        db=db
    )
    
    return {
        "success": True,
        "batch_id": batch_id,
        "message": f"Correction de {len(request.student_copies)} copies lancée en arrière-plan",
        "status": "processing",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/exam/{exam_id}", response_model=ExamResponse)
async def get_exam_details(
    exam_id: str,
    db: Session = Depends(get_db)
):
    """
    Endpoint 4: Récupérer les détails d'un examen
    """
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Examen non trouvé")
    
    questions = db.query(Question).filter(Question.exam_id == exam_id).all()
    
    return ExamResponse(
        id=exam.id,
        title=exam.title,
        subject=exam.subject,
        description=exam.description,
        total_points=exam.total_points,
        question_count=len(questions),
        created_at=exam.created_at.isoformat() if exam.created_at else None,
        questions=[
            {
                "id": q.id,
                "question_number": q.question_number,
                "text": q.text,
                "type": q.question_type,
                "max_points": q.max_points,
                "keywords": q.keywords
            }
            for q in questions
        ]
    )

@router.post("/exam/create", response_model=ExamResponse)
async def create_exam(
    request: ExamCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Endpoint 5: Créer un nouvel examen avec questions
    """
    try:
        # Créer l'examen
        exam = Exam(
            id=str(uuid.uuid4()),
            title=request.title,
            subject=request.subject,
            description=request.description,
            total_points=sum(q.max_points for q in request.questions),
            created_by=request.teacher_id,
            created_at=datetime.utcnow()
        )
        db.add(exam)
        db.flush()  # Pour obtenir l'ID
        
        # Créer les questions
        questions_data = []
        for i, q_data in enumerate(request.questions):
            question = Question(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                question_number=q_data.question_number or (i + 1),
                text=q_data.text,
                question_type=q_data.type,
                correct_answer=q_data.correct_answer,
                max_points=q_data.max_points,
                keywords=q_data.keywords or [],
                created_at=datetime.utcnow()
            )
            db.add(question)
            questions_data.append({
                "text": q_data.text,
                "type": q_data.type,
                "max_points": q_data.max_points,
                "correct_answer": q_data.correct_answer,
                "keywords": q_data.keywords or []
            })
        
        # Ajouter au système RAG
        await add_exam_to_rag(
            exam_id=exam.id,
            questions=questions_data
        )
        
        db.commit()
        
        return ExamResponse(
            id=exam.id,
            title=exam.title,
            subject=exam.subject,
            description=exam.description,
            total_points=exam.total_points,
            question_count=len(request.questions),
            created_at=exam.created_at.isoformat(),
            questions=[
                {
                    "id": q.id,
                    "question_number": q.question_number,
                    "text": q.text,
                    "type": q.question_type,
                    "max_points": q.max_points,
                    "keywords": q.keywords
                }
                for q in db.query(Question).filter(Question.exam_id == exam.id).all()
            ]
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur création examen: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur création examen: {str(e)}")

@router.get("/history/{student_id}", response_model=List[StudentCorrectionHistory])
async def get_student_history(
    student_id: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Endpoint 6: Historique des corrections d'un étudiant
    """
    corrections = db.query(CorrectionResult).filter(
        CorrectionResult.student_id == student_id
    ).order_by(CorrectionResult.created_at.desc()).limit(limit).all()
    
    return [
        StudentCorrectionHistory(
            correction_id=c.id,
            exam_id=c.exam_id,
            exam_title=_get_exam_title(c.exam_id, db),
            total_score=c.total_score,
            max_score=c.max_score,
            percentage=c.percentage,
            grade=_calculate_grade(c.percentage) if c.percentage else "N/A",
            feedback=c.feedback[:200] + "..." if c.feedback and len(c.feedback) > 200 else c.feedback,
            corrected_at=c.created_at.isoformat() if c.created_at else None
        )
        for c in corrections
    ]

@router.get("/results/{exam_id}", response_model=Dict[str, Any])
async def get_exam_results(
    exam_id: str,
    db: Session = Depends(get_db)
):
    """
    Endpoint 7: Résultats statistiques d'un examen (pour prof)
    """
    corrections = db.query(CorrectionResult).filter(
        CorrectionResult.exam_id == exam_id,
        CorrectionResult.status == "completed"
    ).all()
    
    if not corrections:
        return {
            "exam_id": exam_id,
            "total_copies": 0,
            "average_score": 0,
            "stats": {}
        }
    
    scores = [c.percentage for c in corrections if c.percentage]
    
    return {
        "exam_id": exam_id,
        "total_copies": len(corrections),
        "average_score": sum(scores) / len(scores) if scores else 0,
        "highest_score": max(scores) if scores else 0,
        "lowest_score": min(scores) if scores else 0,
        "stats": {
            "A": len([s for s in scores if s >= 85]),
            "B": len([s for s in scores if 70 <= s < 85]),
            "C": len([s for s in scores if 55 <= s < 70]),
            "D": len([s for s in scores if 40 <= s < 55]),
            "F": len([s for s in scores if s < 40])
        }
    }

# ==================== FONCTIONS UTILITAIRES ====================

def _detect_question_count(text: str) -> int:
    """Détecter le nombre de questions dans le texte"""
    patterns = [
        r'Question\s*\d+',
        r'Q\.?\s*\d+',
        r'\d+\.\s*[A-Z]',
        r'\(\d+\)'
    ]
    
    max_count = 0
    for pattern in patterns:
        import re
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Extraire les numéros
            numbers = []
            for match in matches:
                numbers_match = re.findall(r'\d+', match)
                if numbers_match:
                    numbers.extend([int(n) for n in numbers_match])
            
            if numbers:
                max_count = max(max_count, max(numbers))
    
    return max_count if max_count > 0 else 1

def _calculate_grade(percentage: float) -> str:
    """Convertir pourcentage en note"""
    if percentage >= 85:
        return "A"
    elif percentage >= 70:
        return "B"
    elif percentage >= 55:
        return "C"
    elif percentage >= 40:
        return "D"
    else:
        return "F"

def _extract_strengths(corrections: List[Any]) -> List[str]:
    """Extraire les points forts de l'étudiant"""
    strengths = []
    for corr in corrections:
        if corr.points_awarded / corr.max_points >= 0.8:
            strengths.append(f"Question {corr.question_number}: {corr.feedback[:100]}...")
            if len(strengths) >= 3:
                break
    return strengths[:3]

def _extract_improvements(corrections: List[Any]) -> List[str]:
    """Extraire les points à améliorer"""
    improvements = []
    for corr in corrections:
        if corr.points_awarded / corr.max_points <= 0.5:
            improvements.append(f"Question {corr.question_number}: {corr.feedback[:100]}...")
            if len(improvements) >= 3:
                break
    return improvements[:3]

def _get_exam_title(exam_id: str, db: Session) -> str:
    """Récupérer le titre d'un examen"""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    return exam.title if exam else "Examen inconnu"

async def _process_bulk_correction(batch_id: str, request: BulkCorrectionRequest, db: Session):
    """Traiter les corrections en batch en arrière-plan"""
    try:
        logger.info(f"Début traitement batch {batch_id} pour {len(request.student_copies)} copies")
        
        results = []
        for i, student_copy in enumerate(request.student_copies):
            try:
                # Simuler un ID étudiant si non fourni
                student_id = student_copy.student_id or f"student_{i+1}"
                
                # Corriger la copie
                correction_result = await mcp_server.process_correction(
                    correction_id=str(uuid.uuid4()),
                    exam_id=request.exam_id,
                    student_id=student_id,
                    student_name=student_copy.student_name,
                    extracted_text=student_copy.extracted_text,
                    exam_context=await get_exam_context(request.exam_id, student_copy.extracted_text)
                )
                
                # Sauvegarder
                db_correction = CorrectionResult(
                    id=correction_result.correction_id,
                    exam_id=request.exam_id,
                    student_id=student_id,
                    student_name=student_copy.student_name,
                    extracted_text=student_copy.extracted_text[:5000],
                    corrections=json.dumps([c.dict() for c in correction_result.corrections]),
                    total_score=correction_result.total_score,
                    max_score=correction_result.max_score,
                    percentage=correction_result.percentage,
                    feedback=correction_result.feedback,
                    status="completed",
                    processing_time=correction_result.processing_time,
                    created_at=datetime.utcnow()
                )
                
                db.add(db_correction)
                results.append({
                    "student_name": student_copy.student_name,
                    "score": correction_result.total_score,
                    "percentage": correction_result.percentage,
                    "status": "success"
                })
                
                # Commit périodiquement
                if i % 10 == 0:
                    db.commit()
                
            except Exception as e:
                logger.error(f"Erreur pour copie {i}: {str(e)}")
                results.append({
                    "student_name": student_copy.student_name,
                    "score": 0,
                    "percentage": 0,
                    "status": "error",
                    "error": str(e)
                })
        
        db.commit()
        logger.info(f"Batch {batch_id} terminé: {len(results)} résultats")
        
    except Exception as e:
        logger.error(f"Erreur batch {batch_id}: {str(e)}")
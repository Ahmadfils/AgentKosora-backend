import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import time
import logging

from app.mcp.agents.question_parser import QuestionParserAgent
from app.mcp.agents.answer_evaluator import AnswerEvaluatorAgent
from app.mcp.agents.consistency_agent import ConsistencyAgent
from app.mcp.agents.feedback_agent import FeedbackAgent
from app.schemas.correction import (
    MCPCorrectionResult,
    QuestionCorrection,
    MCPAgentResult
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPServer:
    """
    Serveur MCP (Multi-Correction Protocol) pour orchestrer
    les agents de correction
    """
    
    def __init__(self):
        self.agents = {
            "question_parser": QuestionParserAgent(),
            "answer_evaluator": AnswerEvaluatorAgent(),
            "consistency_checker": ConsistencyAgent(),
            "feedback_generator": FeedbackAgent()
        }
        
        logger.info("Serveur MCP initialisé avec %d agents", len(self.agents))
    
    async def process_correction(
        self,
        correction_id: str,
        exam_id: str,
        student_id: str,
        student_name: str,
        extracted_text: str,
        exam_context: Dict[str, Any]
    ) -> MCPCorrectionResult:
        """
        Traiter une correction en utilisant tous les agents MCP
        """
        start_time = time.time()
        logger.info("[%s] Début du traitement MCP pour l'examen %s", 
                   correction_id, exam_id)
        
        agent_results = []
        all_corrections = []
        
        try:
            # 1. Parser les questions depuis le contexte de l'examen
            logger.info("[%s] Étape 1: Parsing des questions", correction_id)
            parsing_result = await self.agents["question_parser"].process(
                correction_id=correction_id,
                exam_context=exam_context,
                extracted_text=extracted_text
            )
            
            agent_results.append(MCPAgentResult(
                agent_name="question_parser",
                question_number=-1,
                evaluation=parsing_result,
                confidence=parsing_result.get("confidence", 0.8),
                processing_time=parsing_result.get("processing_time", 0.0)
            ))
            
            questions = parsing_result.get("parsed_questions", [])
            logger.info("[%s] %d questions parsées", correction_id, len(questions))
            
            # 2. Évaluer chaque question avec l'agent d'évaluation
            logger.info("[%s] Étape 2: Évaluation des réponses", correction_id)
            evaluation_tasks = []
            
            for i, question in enumerate(questions):
                task = self._evaluate_question(
                    correction_id=correction_id,
                    question=question,
                    student_answers=extracted_text,
                    exam_context=exam_context,
                    question_number=i+1
                )
                evaluation_tasks.append(task)
            
            evaluation_results = await asyncio.gather(*evaluation_tasks)
            
            # 3. Vérifier la cohérence des corrections
            logger.info("[%s] Étape 3: Vérification de cohérence", correction_id)
            consistency_result = await self.agents["consistency_checker"].process(
                correction_id=correction_id,
                question_corrections=evaluation_results,
                exam_context=exam_context
            )
            
            agent_results.append(MCPAgentResult(
                agent_name="consistency_checker",
                question_number=-1,
                evaluation=consistency_result,
                confidence=consistency_result.get("confidence", 0.9),
                processing_time=consistency_result.get("processing_time", 0.0)
            ))
            
            # Ajuster les corrections basées sur la cohérence
            adjusted_corrections = consistency_result.get("adjusted_corrections", [])
            
            # 4. Générer les feedbacks
            logger.info("[%s] Étape 4: Génération des feedbacks", correction_id)
            feedback_result = await self.agents["feedback_generator"].process(
                correction_id=correction_id,
                question_corrections=adjusted_corrections,
                student_info={
                    "student_id": student_id,
                    "student_name": student_name
                },
                exam_context=exam_context
            )
            
            agent_results.append(MCPAgentResult(
                agent_name="feedback_generator",
                question_number=-1,
                evaluation=feedback_result,
                confidence=feedback_result.get("confidence", 0.85),
                processing_time=feedback_result.get("processing_time", 0.0)
            ))
            
            # 5. Calculer les scores totaux
            total_score = sum(c.points_awarded for c in adjusted_corrections)
            max_score = sum(c.max_points for c in adjusted_corrections)
            percentage = (total_score / max_score * 100) if max_score > 0 else 0
            
            # 6. Créer le résultat final
            processing_time = time.time() - start_time
            
            result = MCPCorrectionResult(
                correction_id=correction_id,
                exam_id=exam_id,
                student_id=student_id,
                corrections=adjusted_corrections,
                total_score=total_score,
                max_score=max_score,
                percentage=percentage,
                feedback=feedback_result.get("overall_feedback", ""),
                agent_results=agent_results,
                processing_time=processing_time
            )
            
            logger.info("[%s] Traitement MCP terminé en %.2f secondes", 
                       correction_id, processing_time)
            logger.info("[%s] Score: %.1f/%.1f (%.1f%%)", 
                       correction_id, total_score, max_score, percentage)
            
            return result
            
        except Exception as e:
            logger.error("[%s] Erreur dans le traitement MCP: %s", 
                        correction_id, str(e))
            raise
    
    async def _evaluate_question(
        self,
        correction_id: str,
        question: Dict[str, Any],
        student_answers: str,
        exam_context: Dict[str, Any],
        question_number: int
    ) -> QuestionCorrection:
        """
        Évaluer une question spécifique
        """
        try:
            # Utiliser l'agent d'évaluation pour cette question
            evaluation_result = await self.agents["answer_evaluator"].process(
                correction_id=correction_id,
                question=question,
                student_answer_text=student_answers,
                exam_context=exam_context,
                question_number=question_number
            )
            
            # Créer l'objet QuestionCorrection
            correction = QuestionCorrection(
                question_number=question_number,
                question_text=question.get("text", ""),
                student_answer=evaluation_result.get("extracted_answer", ""),
                correct_answer=question.get("correct_answer", ""),
                points_awarded=evaluation_result.get("points_awarded", 0),
                max_points=question.get("max_points", 1),
                feedback=evaluation_result.get("feedback", ""),
                confidence_score=evaluation_result.get("confidence", 0.5),
                correction_details=evaluation_result
            )
            
            return correction
            
        except Exception as e:
            logger.error("[%s] Erreur d'évaluation pour la question %d: %s",
                        correction_id, question_number, str(e))
            
            # Retourner une correction par défaut en cas d'erreur
            return QuestionCorrection(
                question_number=question_number,
                question_text=question.get("text", "Erreur d'évaluation"),
                student_answer="",
                correct_answer=question.get("correct_answer", ""),
                points_awarded=0,
                max_points=question.get("max_points", 1),
                feedback=f"Erreur lors de l'évaluation: {str(e)}",
                confidence_score=0.0,
                correction_details={"error": str(e)}
            )
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """
        Obtenir le statut de tous les agents
        """
        status = {}
        
        for agent_name, agent in self.agents.items():
            try:
                agent_status = await agent.get_status()
                status[agent_name] = agent_status
            except Exception as e:
                status[agent_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return {
            "server_status": "running",
            "total_agents": len(self.agents),
            "agents": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def shutdown(self):
        """
        Arrêter proprement tous les agents
        """
        logger.info("Arrêt du serveur MCP...")
        
        for agent_name, agent in self.agents.items():
            try:
                if hasattr(agent, 'shutdown'):
                    await agent.shutdown()
                logger.info("Agent %s arrêté", agent_name)
            except Exception as e:
                logger.error("Erreur lors de l'arrêt de l'agent %s: %s", 
                            agent_name, str(e))
        
        logger.info("Serveur MCP arrêté")
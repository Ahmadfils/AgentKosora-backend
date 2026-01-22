import re
import json
from typing import Dict, Any, List
import time
import logging

logger = logging.getLogger(__name__)

class QuestionParserAgent:
    """
    Agent MCP pour parser les questions depuis le texte extrait
    """
    
    def __init__(self):
        self.name = "QuestionParserAgent"
        self.version = "1.0.0"
        
    async def process(
        self,
        correction_id: str,
        exam_context: Dict[str, Any],
        extracted_text: str
    ) -> Dict[str, Any]:
        """
        Parser les questions depuis le contexte de l'examen et le texte extrait
        """
        start_time = time.time()
        logger.info("[%s] QuestionParserAgent: Début du parsing", correction_id)
        
        try:
            # Récupérer les questions du contexte RAG
            questions = exam_context.get("questions", [])
            
            if not questions:
                # Tentative d'extraction depuis le texte
                questions = self._extract_questions_from_text(extracted_text)
            
            # Parser chaque question
            parsed_questions = []
            
            for i, question_data in enumerate(questions):
                parsed_question = self._parse_question(
                    question_data=question_data,
                    question_number=i+1
                )
                parsed_questions.append(parsed_question)
            
            processing_time = time.time() - start_time
            
            result = {
                "parsed_questions": parsed_questions,
                "total_questions": len(parsed_questions),
                "parsing_method": "rag_context" if exam_context.get("questions") else "text_extraction",
                "confidence": 0.9 if parsed_questions else 0.5,
                "processing_time": processing_time,
                "status": "success"
            }
            
            logger.info("[%s] QuestionParserAgent: %d questions parsées en %.2fs",
                       correction_id, len(parsed_questions), processing_time)
            
            return result
            
        except Exception as e:
            logger.error("[%s] QuestionParserAgent erreur: %s", correction_id, str(e))
            return {
                "parsed_questions": [],
                "error": str(e),
                "status": "error",
                "processing_time": time.time() - start_time
            }
    
    def _extract_questions_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extraire les questions depuis le texte (méthode fallback)
        """
        questions = []
        
        # Recherche des motifs de questions (ex: "Question 1:", "Q1.", etc.)
        patterns = [
            r'Question\s*(\d+)[:.]\s*(.*?)(?=(?:Question\s*\d+[:.]|$))',
            r'Q\s*(\d+)[:.]\s*(.*?)(?=(?:Q\s*\d+[:.]|$))',
            r'(\d+)[).]\s*(.*?)(?=(?:\d+[).]|$))'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            
            for match in matches:
                question_num = match.group(1)
                question_text = match.group(2).strip()
                
                if question_text and len(question_text) > 10:  # Minimum de caractères
                    questions.append({
                        "number": int(question_num),
                        "text": question_text[:500],  # Limiter la longueur
                        "type": "unknown",
                        "max_points": 1,  # Valeur par défaut
                        "extracted": True
                    })
        
        return questions
    
    def _parse_question(
        self,
        question_data: Dict[str, Any],
        question_number: int
    ) -> Dict[str, Any]:
        """
        Parser une question individuelle
        """
        # Si c'est déjà un objet parsé, le retourner
        if isinstance(question_data, dict) and "text" in question_data:
            return {
                "number": question_data.get("number", question_number),
                "text": question_data.get("text", ""),
                "type": question_data.get("type", "essay"),
                "correct_answer": question_data.get("correct_answer", ""),
                "max_points": float(question_data.get("max_points", 1)),
                "rubric": question_data.get("rubric", {}),
                "keywords": question_data.get("keywords", []),
                "metadata": question_data.get("metadata", {})
            }
        
        # Sinon, essayer de parser depuis une chaîne
        question_text = str(question_data)
        
        return {
            "number": question_number,
            "text": question_text[:500],
            "type": self._detect_question_type(question_text),
            "correct_answer": "",
            "max_points": 1.0,
            "rubric": {},
            "keywords": [],
            "metadata": {"source": "text_extraction"}
        }
    
    def _detect_question_type(self, text: str) -> str:
        """
        Détecter le type de question basé sur le texte
        """
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["explique", "décris", "définis", "analyse"]):
            return "essay"
        elif any(word in text_lower for word in ["calcule", "résous", "trouve", "détermine"]):
            return "calculation"
        elif any(word in text_lower for word in ["compare", "contraste", "différence"]):
            return "comparison"
        elif any(word in text_lower for word in ["vrai ou faux", "vrai/faux"]):
            return "true_false"
        elif any(word in text_lower for word in ["choix multiples", "qcm"]):
            return "multiple_choice"
        else:
            return "essay"
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Obtenir le statut de l'agent
        """
        return {
            "name": self.name,
            "version": self.version,
            "status": "ready",
            "capabilities": ["question_parsing", "type_detection", "text_extraction"]
        }
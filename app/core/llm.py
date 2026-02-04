import google.generativeai as genai
from typing import List, Dict, Any, Optional
import json
import logging
import asyncio
from datetime import datetime
import os

from app.config import settings

logger = logging.getLogger(__name__)

class GeminiProcessor:
    """Processeur LLM avec Google Gemini"""
    
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY non configurée, LLM désactivé")
            self.enabled = False
            return
            
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
            self.enabled = True
            logger.info(f"Gemini LLM initialisé avec modèle: {settings.GEMINI_MODEL}")
        except Exception as e:
            logger.error(f"Erreur d'initialisation Gemini: {str(e)}")
            self.enabled = False
    
    async def correct_answer(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
        max_points: float,
        rubric: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Corriger une réponse d'étudiant avec Gemini
        
        Args:
            question: Texte de la question
            student_answer: Réponse de l'étudiant
            correct_answer: Réponse correcte
            max_points: Points maximum
            rubric: Barème de correction
        
        Returns:
            Dictionnaire avec correction
        """
        if not self.enabled:
            return self._generate_basic_correction(student_answer, max_points)
        
        try:
            prompt = self._build_correction_prompt(
                question, student_answer, correct_answer, max_points, rubric
            )
            
            # Appeler Gemini de manière asynchrone
            response = await self._async_generate_content(prompt)
            
            # Parser la réponse
            return self._parse_gemini_response(response, max_points)
            
        except Exception as e:
            logger.error(f"Erreur Gemini correction: {str(e)}")
            return self._generate_basic_correction(student_answer, max_points)
    
    async def enhance_feedback(
        self,
        corrections: List[Dict[str, Any]],
        student_name: str,
        total_score: float,
        max_score: float,
        language: str = "french"
    ) -> str:
        """
        Améliorer le feedback avec Gemini
        
        Args:
            corrections: Liste des corrections
            student_name: Nom de l'étudiant
            total_score: Score total
            max_score: Score maximum
            language: Langue du feedback
        
        Returns:
            Feedback amélioré
        """
        if not self.enabled or not corrections:
            return self._generate_basic_feedback(total_score, max_score)
        
        try:
            prompt = f"""
            Tu es un assistant pédagogique qui donne des retours constructifs sur des copies d'examen.
            
            Étudiant: {student_name}
            Score: {total_score}/{max_score} ({total_score/max_score*100:.1f}%)
            
            Corrections par question:
            {json.dumps(corrections[:5], ensure_ascii=False, indent=2)}
            
            Génère un feedback en {language} avec:
            1. Une introduction encourageante
            2. 2-3 points forts spécifiques
            3. 2-3 points à améliorer avec suggestions concrètes
            4. Des conseils pour les prochaines révisions
            5. Une conclusion motivante
            
            Format: Texte fluide, maximum 300 mots.
            Style: Professionnel mais chaleureux.
            """
            
            response = await self._async_generate_content(prompt)
            return response.strip()
            
        except Exception as e:
            logger.error(f"Erreur Gemini feedback: {str(e)}")
            return self._generate_basic_feedback(total_score, max_score)
    
    async def extract_questions_from_text(
        self,
        exam_text: str,
        subject: str = "general"
    ) -> List[Dict[str, Any]]:
        """
        Extraire et structurer les questions d'un texte d'examen
        
        Args:
            exam_text: Texte complet de l'examen
            subject: Matière de l'examen
        
        Returns:
            Liste de questions structurées
        """
        if not self.enabled:
            return []
        
        try:
            prompt = f"""
            Extrait et structure les questions d'un examen de {subject}.
            
            Texte de l'examen:
            {exam_text[:3000]}
            
            Retourne un JSON avec la structure:
            [
              {{
                "question_number": 1,
                "text": "texte de la question",
                "type": "essay|multiple_choice|short_answer|calculation",
                "correct_answer": "réponse attendue",
                "max_points": 1.0,
                "keywords": ["mot-clé1", "mot-clé2"]
              }}
            ]
            
            Règles:
            - Identifie toutes les questions numérotées
            - Détecte le type de question
            - Extrait la réponse attendue si disponible
            - Points par défaut: 1.0
            - Génère 2-4 mots-clés par question
            """
            
            response = await self._async_generate_content(prompt)
            
            # Essayer de parser le JSON
            try:
                # Chercher le JSON dans la réponse
                import re
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    questions = json.loads(json_match.group())
                    return questions
            except:
                pass
            
            return []
            
        except Exception as e:
            logger.error(f"Erreur extraction questions: {str(e)}")
            return []
    
    def _build_correction_prompt(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
        max_points: float,
        rubric: Optional[Dict[str, Any]] = None
    ) -> str:
        """Construire le prompt de correction"""
        
        rubric_text = ""
        if rubric:
            rubric_text = f"\nBarème de correction:\n{json.dumps(rubric, indent=2)}"
        
        return f"""
        Tu es un correcteur d'examen expert.
        
        QUESTION:
        {question}
        
        RÉPONSE ATTENDUE:
        {correct_answer}
        
        RÉPONSE DE L'ÉTUDIANT:
        {student_answer}
        
        {rubric_text}
        
        Instructions:
        1. Évalue la réponse de l'étudiant sur {max_points} points
        2. Donne un score entre 0 et {max_points}
        3. Fournis un feedback constructif
        4. Identifie les points forts et faiblesses
        5. Note la confiance de ton évaluation (0-1)
        
        Format de réponse (JSON):
        {{
          "points_awarded": 3.5,
          "max_points": {max_points},
          "feedback": "Feedback détaillé...",
          "confidence": 0.85,
          "strengths": ["point fort 1", "point fort 2"],
          "weaknesses": ["point faible 1", "point faible 2"],
          "suggestions": ["suggestion 1", "suggestion 2"]
        }}
        """
    
    async def _async_generate_content(self, prompt: str) -> str:
        """Générer du contenu de manière asynchrone avec Gemini"""
        try:
            # Utiliser run_in_executor pour éviter de bloquer
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(prompt)
            )
            
            if response and hasattr(response, 'text'):
                return response.text
            else:
                raise ValueError("Réponse Gemini vide")
                
        except Exception as e:
            logger.error(f"Erreur génération Gemini: {str(e)}")
            raise
    
    def _parse_gemini_response(self, response: str, max_points: float) -> Dict[str, Any]:
        """Parser la réponse de Gemini"""
        try:
            # Essayer d'extraire le JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                
                # Validation des points
                points = float(result.get("points_awarded", 0))
                points = max(0, min(points, max_points))
                
                return {
                    "points_awarded": points,
                    "max_points": max_points,
                    "feedback": result.get("feedback", ""),
                    "confidence": float(result.get("confidence", 0.5)),
                    "strengths": result.get("strengths", []),
                    "weaknesses": result.get("weaknesses", []),
                    "suggestions": result.get("suggestions", []),
                    "raw_response": response
                }
        except Exception as e:
            logger.error(f"Erreur parsing réponse Gemini: {str(e)}")
        
        # Fallback
        return self._generate_basic_correction("", max_points)
    
    def _generate_basic_correction(self, student_answer: str, max_points: float) -> Dict[str, Any]:
        """Générer une correction basique sans LLM"""
        # Logique simple basée sur la longueur
        length = len(student_answer.strip())
        
        if length > 100:
            points = max_points * 0.8
        elif length > 50:
            points = max_points * 0.5
        else:
            points = max_points * 0.2
        
        return {
            "points_awarded": points,
            "max_points": max_points,
            "feedback": "Correction automatique basique.",
            "confidence": 0.3,
            "strengths": [],
            "weaknesses": [],
            "suggestions": ["Développer davantage votre réponse"],
            "raw_response": ""
        }
    
    def _generate_basic_feedback(self, total_score: float, max_score: float) -> str:
        """Générer un feedback basique"""
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        if percentage >= 85:
            return f"Excellent travail ! Score: {total_score}/{max_score}"
        elif percentage >= 70:
            return f"Bon travail. Score: {total_score}/{max_score}"
        elif percentage >= 50:
            return f"Résultat acceptable. Score: {total_score}/{max_score}"
        else:
            return f"Des révisions sont nécessaires. Score: {total_score}/{max_score}"
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Obtenir des informations sur le modèle Gemini"""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            # Tester une requête simple
            test_prompt = "Test de connexion. Réponds simplement par 'OK'."
            response = await self._async_generate_content(test_prompt)
            
            return {
                "enabled": True,
                "model": settings.GEMINI_MODEL,
                "status": "connected",
                "test_response": response[:100] if response else "no response"
            }
        except Exception as e:
            return {
                "enabled": True,
                "model": settings.GEMINI_MODEL,
                "status": "error",
                "error": str(e)
            }

# Instance globale
gemini_processor = GeminiProcessor()
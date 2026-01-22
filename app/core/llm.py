import openai
import os
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

class LLMProcessor:
    """Processeur LLM pour améliorer les feedbacks"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY non configurée, LLM désactivé")
            self.enabled = False
        else:
            openai.api_key = self.api_key
            self.enabled = True
    
    async def enhance_feedback(
        self,
        corrections: List[Dict[str, Any]],
        student_name: str,
        total_score: float,
        max_score: float
    ) -> str:
        """
        Améliorer le feedback avec LLM pour le rendre plus personnel
        """
        if not self.enabled or not corrections:
            return self._generate_basic_feedback(corrections, total_score, max_score)
        
        try:
            # Préparer le contexte
            context = {
                "student_name": student_name,
                "total_score": total_score,
                "max_score": max_score,
                "percentage": (total_score / max_score * 100) if max_score > 0 else 0,
                "corrections": corrections[:5]  # Limiter pour le contexte
            }
            
            # Appeler l'API OpenAI
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """Tu es un assistant pédagogique qui aide à donner des feedbacks 
                        constructifs sur des copies d'examens. Sois encourageant, précis et utile."""
                    },
                    {
                        "role": "user",
                        "content": f"""Génère un feedback personnalisé pour {student_name} qui a obtenu 
                        {total_score}/{max_score} points ({context['percentage']:.1f}%).
                        
                        Corrections:
                        {json.dumps(corrections, ensure_ascii=False)}
                        
                        Format:
                        1. Félicitations pour les points forts
                        2. Suggestions d'amélioration spécifiques
                        3. Conseils pour les prochains examens
                        4. Encouragement final
                        
                        En français, maximum 300 mots."""
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            feedback = response.choices[0].message.content.strip()
            return feedback
            
        except Exception as e:
            logger.error(f"Erreur LLM: {str(e)}")
            return self._generate_basic_feedback(corrections, total_score, max_score)
    
    def _generate_basic_feedback(
        self,
        corrections: List[Dict[str, Any]],
        total_score: float,
        max_score: float
    ) -> str:
        """Générer un feedback basique sans LLM"""
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        if percentage >= 85:
            return f"Excellent travail ! Vous avez obtenu {total_score}/{max_score} points ({percentage:.1f}%). Continuez comme ça !"
        elif percentage >= 70:
            return f"Bon travail avec {total_score}/{max_score} points ({percentage:.1f}%). Quelques améliorations possibles pour atteindre l'excellence."
        elif percentage >= 55:
            return f"Résultat satisfaisant : {total_score}/{max_score} points ({percentage:.1f}%). Concentrez-vous sur les points faibles identifiés."
        else:
            return f"{total_score}/{max_score} points ({percentage:.1f}%). Des révisions sont nécessaires. Consultez les corrections détaillées."
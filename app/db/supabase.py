from supabase import create_client, Client
import logging
from typing import Dict, Any, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

class SupabaseClient:
    """Client Supabase pour les opérations directes"""
    
    def __init__(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            logger.warning("Configuration Supabase manquante")
            self.client = None
            return
            
        try:
            self.client: Client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
            logger.info("Client Supabase initialisé")
        except Exception as e:
            logger.error(f"Erreur d'initialisation Supabase: {str(e)}")
            self.client = None
    
    async def create_user(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Créer un utilisateur via Supabase Auth"""
        if not self.client:
            return None
            
        try:
            response = self.client.auth.sign_up({
                "email": user_data["email"],
                "password": user_data["password"],
                "options": {
                    "data": {
                        "full_name": user_data.get("full_name", ""),
                        "role": user_data.get("role", "student")
                    }
                }
            })
            
            return response.user.dict() if response.user else None
            
        except Exception as e:
            logger.error(f"Erreur création utilisateur: {str(e)}")
            return None
    
    async def login_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Connexion utilisateur"""
        if not self.client:
            return None
            
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            return {
                "user": response.user.dict() if response.user else None,
                "session": response.session.dict() if response.session else None
            }
            
        except Exception as e:
            logger.error(f"Erreur connexion: {str(e)}")
            return None
    
    async def upload_file(self, bucket: str, file_path: str, file_content: bytes) -> Optional[str]:
        """Uploader un fichier vers Supabase Storage"""
        if not self.client:
            return None
            
        try:
            response = self.client.storage.from_(bucket).upload(
                file_path,
                file_content
            )
            
            # Générer l'URL signée
            url = self.client.storage.from_(bucket).get_public_url(file_path)
            return url
            
        except Exception as e:
            logger.error(f"Erreur upload fichier: {str(e)}")
            return None
    
    async def insert_correction_result(self, correction_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insérer un résultat de correction"""
        if not self.client:
            return None
            
        try:
            response = self.client.table("correction_results").insert(correction_data).execute()
            
            if response.data:
                return response.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Erreur insertion correction: {str(e)}")
            return None
    
    async def get_student_history(self, student_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Récupérer l'historique d'un étudiant"""
        if not self.client:
            return []
            
        try:
            response = self.client.table("correction_results") \
                .select("*, exams(title, subject)") \
                .eq("student_id", student_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Erreur récupération historique: {str(e)}")
            return []
    
    async def get_exam_results(self, exam_id: str) -> Dict[str, Any]:
        """Récupérer les résultats d'un examen"""
        if not self.client:
            return {}
            
        try:
            response = self.client.table("correction_results") \
                .select("total_score, max_score, percentage, student_name") \
                .eq("exam_id", exam_id) \
                .eq("status", "completed") \
                .execute()
            
            if not response.data:
                return {"total_copies": 0, "average_score": 0}
            
            scores = [r["percentage"] for r in response.data if r.get("percentage")]
            
            return {
                "total_copies": len(response.data),
                "average_score": sum(scores) / len(scores) if scores else 0,
                "highest_score": max(scores) if scores else 0,
                "lowest_score": min(scores) if scores else 0,
                "results": response.data
            }
            
        except Exception as e:
            logger.error(f"Erreur récupération résultats: {str(e)}")
            return {}

# Instance globale
supabase_client = SupabaseClient()
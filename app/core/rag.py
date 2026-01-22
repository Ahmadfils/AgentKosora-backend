import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any, Optional
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RAGSystem:
    """
    Système RAG (Retrieval Augmented Generation) pour les examens
    Utilise ChromaDB pour le stockage vectoriel et la recherche
    """
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
        
        self._initialize()
    
    def _initialize(self):
        """Initialiser le système RAG"""
        try:
            # Initialiser le client ChromaDB
            self.chroma_client = chromadb.Client(
                Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=self.persist_directory
                )
            )
            
            # Charger le modèle d'embedding
            logger.info("Chargement du modèle d'embedding...")
            self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            
            # Créer ou récupérer la collection
            self._setup_collection()
            
            logger.info("Système RAG initialisé avec succès")
            
        except Exception as e:
            logger.error(f"Erreur d'initialisation RAG: {str(e)}")
            raise
    
    def _setup_collection(self):
        """Configurer la collection ChromaDB"""
        try:
            # Essayer de récupérer la collection existante
            self.collection = self.chroma_client.get_collection(name="exams")
            logger.info(f"Collection existante chargée: {self.collection.count()} documents")
            
        except Exception:
            # Créer une nouvelle collection
            self.collection = self.chroma_client.create_collection(
                name="exams",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Nouvelle collection créée")
    
    def _create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Créer des embeddings pour les textes"""
        if not self.embedding_model:
            raise ValueError("Modèle d'embedding non initialisé")
        
        embeddings = self.embedding_model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        
        return embeddings.tolist()
    
    async def add_exam_documents(
        self,
        exam_id: str,
        documents: List[Dict[str, Any]]
    ):
        """
        Ajouter des documents d'examen au système RAG
        
        Args:
            exam_id: ID de l'examen
            documents: Liste de documents avec texte et métadonnées
        """
        try:
            texts = []
            metadatas = []
            ids = []
            
            for i, doc in enumerate(documents):
                text = doc.get("text", "")
                metadata = doc.get("metadata", {})
                metadata["exam_id"] = exam_id
                metadata["document_type"] = doc.get("type", "question")
                metadata["timestamp"] = datetime.utcnow().isoformat()
                
                # Générer un ID unique
                doc_id = f"{exam_id}_{doc.get('type', 'doc')}_{i}"
                
                texts.append(text)
                metadatas.append(metadata)
                ids.append(doc_id)
            
            # Créer les embeddings
            embeddings = self._create_embeddings(texts)
            
            # Ajouter à la collection
            self.collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            
            # Persister les données
            self.chroma_client.persist()
            
            logger.info(f"Ajouté {len(documents)} documents pour l'examen {exam_id}")
            
            return {
                "success": True,
                "exam_id": exam_id,
                "documents_added": len(documents),
                "total_documents": self.collection.count()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de documents: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_exam_context(
        self,
        exam_id: str,
        query: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rechercher dans le contexte d'un examen spécifique
        
        Args:
            exam_id: ID de l'examen
            query: Texte de recherche
            n_results: Nombre de résultats à retourner
            
        Returns:
            Liste de documents pertinents
        """
        try:
            # Créer l'embedding pour la requête
            query_embedding = self._create_embeddings([query])[0]
            
            # Rechercher dans la collection avec filtre par exam_id
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where={"exam_id": exam_id}
            )
            
            # Formater les résultats
            formatted_results = []
            
            if results["documents"]:
                for i in range(len(results["documents"][0])):
                    formatted_results.append({
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                        "id": results["ids"][0][i]
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche RAG: {str(e)}")
            return []
    
    async def get_exam_structure(
        self,
        exam_id: str
    ) -> Dict[str, Any]:
        """
        Récupérer la structure d'un examen
        
        Args:
            exam_id: ID de l'examen
            
        Returns:
            Structure de l'examen avec questions, barèmes, etc.
        """
        try:
            # Rechercher tous les documents de l'examen
            all_docs = self.collection.get(
                where={"exam_id": exam_id}
            )
            
            # Organiser par type de document
            exam_structure = {
                "exam_id": exam_id,
                "questions": [],
                "rubrics": [],
                "instructions": [],
                "solutions": [],
                "metadata": {}
            }
            
            for i, doc_id in enumerate(all_docs["ids"]):
                doc_type = all_docs["metadatas"][i].get("document_type", "unknown")
                text = all_docs["documents"][i]
                metadata = all_docs["metadatas"][i]
                
                if doc_type == "question":
                    exam_structure["questions"].append({
                        "text": text,
                        "metadata": metadata
                    })
                elif doc_type == "rubric":
                    exam_structure["rubrics"].append({
                        "text": text,
                        "metadata": metadata
                    })
                elif doc_type == "instruction":
                    exam_structure["instructions"].append({
                        "text": text,
                        "metadata": metadata
                    })
                elif doc_type == "solution":
                    exam_structure["solutions"].append({
                        "text": text,
                        "metadata": metadata
                    })
                elif doc_type == "metadata":
                    exam_structure["metadata"] = metadata
            
            return exam_structure
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la structure: {str(e)}")
            return {
                "exam_id": exam_id,
                "error": str(e)
            }
    
    async def delete_exam_documents(self, exam_id: str):
        """
        Supprimer tous les documents d'un examen
        
        Args:
            exam_id: ID de l'examen à supprimer
        """
        try:
            # Récupérer tous les IDs de l'examen
            docs = self.collection.get(
                where={"exam_id": exam_id}
            )
            
            if docs["ids"]:
                self.collection.delete(ids=docs["ids"])
                self.chroma_client.persist()
                logger.info(f"Supprimé {len(docs['ids'])} documents pour l'examen {exam_id}")
            
            return {
                "success": True,
                "exam_id": exam_id,
                "documents_deleted": len(docs["ids"]) if docs["ids"] else 0
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtenir les statistiques du système RAG
        """
        try:
            count = self.collection.count()
            
            # Compter par exam_id
            all_metadata = self.collection.get()["metadatas"]
            exam_counts = {}
            
            for metadata in all_metadata:
                exam_id = metadata.get("exam_id", "unknown")
                exam_counts[exam_id] = exam_counts.get(exam_id, 0) + 1
            
            return {
                "total_documents": count,
                "exams": exam_counts,
                "collection_name": "exams",
                "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2"
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
            return {
                "error": str(e)
            }

# Instance globale du système RAG
rag_system = RAGSystem()

async def get_exam_context(exam_id: str, query_text: str) -> Dict[str, Any]:
    """
    Fonction principale pour obtenir le contexte d'un examen via RAG
    """
    try:
        logger.info(f"Récupération du contexte RAG pour l'examen: {exam_id}")
        
        # 1. Obtenir la structure de l'examen
        exam_structure = await rag_system.get_exam_structure(exam_id)
        
        # 2. Rechercher des documents pertinents
        relevant_docs = await rag_system.search_exam_context(
            exam_id=exam_id,
            query=query_text,
            n_results=10
        )
        
        # 3. Organiser le contexte
        context = {
            "exam_id": exam_id,
            "structure": exam_structure,
            "relevant_documents": relevant_docs,
            "query_text": query_text,
            "timestamp": datetime.utcnow().isoformat(),
            "rag_system": "chromadb_multilingual"
        }
        
        # 4. Extraire les questions si disponibles
        if exam_structure.get("questions"):
            context["questions"] = [
                {
                    "number": i + 1,
                    "text": q["text"],
                    "type": q["metadata"].get("question_type", "essay"),
                    "max_points": float(q["metadata"].get("max_points", 1)),
                    "metadata": q["metadata"]
                }
                for i, q in enumerate(exam_structure["questions"])
            ]
        
        logger.info(f"Contexte RAG récupéré: {len(relevant_docs)} documents pertinents")
        
        return context
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du contexte RAG: {str(e)}")
        
        # Retourner un contexte minimal en cas d'erreur
        return {
            "exam_id": exam_id,
            "query_text": query_text,
            "error": str(e),
            "questions": [],
            "relevant_documents": [],
            "timestamp": datetime.utcnow().isoformat()
        }

async def add_exam_to_rag(
    exam_id: str,
    questions: List[Dict[str, Any]],
    rubrics: Optional[List[Dict[str, Any]]] = None,
    solutions: Optional[List[Dict[str, Any]]] = None
):
    """
    Ajouter un examen au système RAG
    
    Args:
        exam_id: ID de l'examen
        questions: Liste des questions
        rubrics: Liste des barèmes (optionnel)
        solutions: Liste des solutions (optionnel)
    """
    try:
        documents = []
        
        # Ajouter les questions
        for i, question in enumerate(questions):
            documents.append({
                "text": question.get("text", ""),
                "type": "question",
                "metadata": {
                    "question_number": i + 1,
                    "question_type": question.get("type", "essay"),
                    "max_points": float(question.get("max_points", 1)),
                    "difficulty": question.get("difficulty", "medium"),
                    "subject": question.get("subject", "general")
                }
            })
        
        # Ajouter les barèmes
        if rubrics:
            for rubric in rubrics:
                documents.append({
                    "text": rubric.get("text", ""),
                    "type": "rubric",
                    "metadata": rubric.get("metadata", {})
                })
        
        # Ajouter les solutions
        if solutions:
            for solution in solutions:
                documents.append({
                    "text": solution.get("text", ""),
                    "type": "solution",
                    "metadata": solution.get("metadata", {})
                })
        
        # Ajouter les documents au système RAG
        result = await rag_system.add_exam_documents(exam_id, documents)
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de l'examen au RAG: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
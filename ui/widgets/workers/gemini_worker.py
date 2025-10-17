import os
import time
try:
    from google import genai
except ImportError:
    logger.error("Package 'google-genai' non installé. Installez-le avec: pip install google-genai")
    raise
from PyQt5.QtCore import QThread, pyqtSignal
from utils.logger import logger


class GeminiWorker(QThread):
    """Worker pour effectuer des requêtes à l'API Gemini (version gratuite)"""
    
    # Signaux
    test_completed = pyqtSignal(bool, str, float, str)  # success, message, duration, response
    step_update = pyqtSignal(str, str)  # step_name, message
    debug_info = pyqtSignal(str)  # debug message
    
    def __init__(self, context, perimeter_data, api_key=None):
        super().__init__()
        self.context = context
        self.perimeter_data = perimeter_data
        self.api_key = api_key
        self.platform_name = "Gemini"
        self.platform_index = 0
        
    def run(self):
        """Exécute la requête Gemini"""
        start_time = time.time()
        
        try:
            # Étape 1: Configuration de l'API
            self.step_update.emit("config", "Configuration de l'API Gemini...")
            
            if not self.api_key:
                raise ValueError("Clé API Gemini non configurée")
            
            # Utiliser le client Gemini (API gratuite)
            client = genai.Client(api_key=self.api_key)
            
            # Étape 2: Construction du prompt
            self.step_update.emit("prompt", "Construction du prompt avec périmètre...")
            prompt = self._build_prompt()
            
            self.debug_info.emit(f"Prompt construit: {len(prompt)} caractères")
            
            # Étape 3: Envoi de la requête
            self.step_update.emit("request", "Envoi de la requête à Gemini...")
            
            # Utiliser gemini-2.5-flash (modèle actuel pour API gratuite)
            response = client.models.generate_content(
                model=" ",
                contents=prompt,
            )
            
            if not response or not response.text:
                raise ValueError("Réponse vide de Gemini")
            
            # Étape 4: Traitement de la réponse
            self.step_update.emit("processing", "Traitement de la réponse...")
            
            duration = time.time() - start_time
            response_text = response.text
            
            self.debug_info.emit(f"Réponse reçue: {len(response_text)} caractères")
            
            # Succès
            self.test_completed.emit(
                True,
                "Code généré avec succès",
                duration,
                response_text
            )
            logger.info(f"Gemini request completed successfully in {duration:.2f}s")
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Erreur Gemini: {str(e)}"
            logger.error(error_msg)
            
            self.test_completed.emit(
                False,
                error_msg,
                duration,
                f"Erreur: {str(e)}"
            )
    
    def _build_prompt(self):
        """Construit le prompt complet avec contexte et périmètre"""
        
        prompt_parts = []
        
        # En-tête
        prompt_parts.append("# GÉNÉRATION DE CODE - CONTEXTE ET PÉRIMÈTRE")
        prompt_parts.append("\n" + "=" * 80 + "\n")
        
        # Contexte principal
        prompt_parts.append("## CONTEXTE DE LA FONCTIONNALITÉ")
        prompt_parts.append(self.context)
        prompt_parts.append("\n" + "-" * 80 + "\n")
        
        # Périmètre d'implémentation
        if self.perimeter_data:
            prompt_parts.append("## PÉRIMÈTRE D'IMPLÉMENTATION")
            prompt_parts.append("\n### Éléments sélectionnés:\n")
            
            for idx, item in enumerate(self.perimeter_data, 1):
                name = item.get('name', 'N/A')
                node_type = item.get('type', 'unknown')
                level = item.get('level', 0)
                search_depth = item.get('search_depth', 1)
                
                prompt_parts.append(f"\n**{idx}. {name}** (Type: {node_type}, Niveau: {level})")
                
                # Description du fichier si disponible
                data = item.get('data', {})
                description = data.get('description', '')
                file_path = data.get('path', '')
                
                if description:
                    prompt_parts.append(f"   📄 Description: {description}")
                if file_path:
                    prompt_parts.append(f"   📁 Chemin: {file_path}")
                
                # Relations
                relations = item.get('relations', [])
                if relations:
                    prompt_parts.append(f"\n   🔗 Relations ({len(relations)}):")
                    
                    # Grouper par type de relation
                    relations_by_type = {}
                    for rel in relations:
                        rel_type = rel.get('relation_type', 'unknown')
                        if rel_type not in relations_by_type:
                            relations_by_type[rel_type] = []
                        relations_by_type[rel_type].append(rel)
                    
                    # Afficher par type
                    for rel_type, rels in relations_by_type.items():
                        prompt_parts.append(f"\n   • {rel_type} ({len(rels)}):")
                        for rel in rels[:10]:  # Limiter à 10 par type
                            source = rel.get('source', 'N/A')
                            target = rel.get('target', 'N/A')
                            prompt_parts.append(f"     - {source} → {target}")
                        
                        if len(rels) > 10:
                            prompt_parts.append(f"     ... et {len(rels) - 10} autre(s)")
                
                # Éléments liés
                related = item.get('related', [])
                if related:
                    prompt_parts.append(f"\n   📦 Éléments liés ({len(related)}):")
                    for rel_item in related[:5]:
                        rel_name = rel_item.get('name', 'N/A')
                        rel_type = rel_item.get('type', 'unknown')
                        rel_desc = rel_item.get('data', {}).get('description', '')
                        
                        prompt_parts.append(f"     - {rel_name} ({rel_type})")
                        if rel_desc:
                            prompt_parts.append(f"       Description: {rel_desc[:100]}...")
                    
                    if len(related) > 5:
                        prompt_parts.append(f"     ... et {len(related) - 5} autre(s)")
                
                prompt_parts.append("\n   " + "-" * 70)
            
            # Statistiques du périmètre
            total_relations = sum(len(item.get('relations', [])) for item in self.perimeter_data)
            total_related = sum(len(item.get('related', [])) for item in self.perimeter_data)
            
            prompt_parts.append(f"\n### Statistiques du périmètre:")
            prompt_parts.append(f"- **Éléments principaux**: {len(self.perimeter_data)}")
            prompt_parts.append(f"- **Relations totales**: {total_relations}")
            prompt_parts.append(f"- **Éléments liés**: {total_related}")
            prompt_parts.append(f"- **Profondeur**: Niveau {self.perimeter_data[0].get('search_depth', 1)}")
        
        prompt_parts.append("\n" + "=" * 80 + "\n")
        
        # Instructions de génération
        prompt_parts.append("## INSTRUCTIONS DE GÉNÉRATION")
        prompt_parts.append("""
Veuillez générer le code nécessaire pour implémenter la fonctionnalité décrite dans le contexte.

**Considérations importantes:**

1. **Cohérence avec le périmètre**: Le code doit interagir correctement avec les éléments listés ci-dessus
2. **Respect des relations**: Prenez en compte les relations existantes entre les composants
3. **Types et interfaces**: Respectez les types et interfaces des éléments référencés
4. **Documentation**: Incluez des commentaires explicatifs
5. **Bonnes pratiques**: Suivez les conventions de codage appropriées
6. **Gestion d'erreurs**: Ajoutez une gestion d'erreurs robuste
7. **Tests**: Suggérez des cas de test si pertinent

**Format de la réponse:**

Fournissez le code complet, bien structuré et commenté. Si plusieurs fichiers sont nécessaires, 
séparez-les clairement avec des en-têtes.
""")
        
        return "\n".join(prompt_parts)
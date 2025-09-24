import pydgraph
import json
import logging
import importlib.util
import sys
import os
import google.generativeai as genai
from datetime import datetime
from typing import List, Dict, Optional, Any
import glob
import ast
import re

# --- Configuration logger ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration Dgraph
DGRAPH_ADDR = 'localhost:9080'
USER_ID = "47ea051e-8cce-4bee-bfe8-76489dd98b60"
WORKSPACE_ID = "e8bfa5a1-512d-46e3-a4cc-69aecbb9cad9"

# Configuration des chemins
LIRIS_BASE_PATH = r"C:/Users/Oracle/Documents/liris"
SCRIPTS_PATH = os.path.join(LIRIS_BASE_PATH, "scripts")

# Configuration Gemini
GEMINI_API_KEY = "AIzaSyDs4JLCHS1kF4see-p2m97d1AlH0Tn9iAs"  # À remplacer par votre clé API
genai.configure(api_key=GEMINI_API_KEY)


def normalize_path(path: str) -> str:
    """Retourne un chemin normalisé et absolu."""
    return os.path.normpath(os.path.abspath(path))


class ProjectDataLoader:
    """Classe pour charger les données de projet depuis les fichiers Python."""

    @staticmethod
    def find_dgraph_files(base_path: str) -> List[str]:
        """Trouve tous les fichiers dgraph_*.py dans le dossier liris."""
        base_path = normalize_path(base_path)
        pattern = os.path.join(base_path, "dgraph_*.py")
        files = glob.glob(pattern)
        files = [normalize_path(f) for f in files]
        logger.info(f"Fichiers dgraph trouvés: {files}")
        return files

    @staticmethod
    def load_project_data_from_file(file_path: str) -> Dict:
        """Charge PROJECT_DATA depuis un fichier Python spécifique, même si défini dans main()."""
        file_path = normalize_path(file_path)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fichier non trouvé : {file_path}")

        try:
            module_name = f"project_module_{os.path.basename(file_path).replace('.py', '').replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            project_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = project_module
            spec.loader.exec_module(project_module)

            # Cas 1 : PROJECT_DATA existe en global
            if hasattr(project_module, "PROJECT_DATA"):
                logger.info(f"Données chargées depuis: {file_path} (global)")
                return project_module.PROJECT_DATA

            # Cas 2 : PROJECT_DATA défini à l'intérieur (ex: dans main())
            # Lire le fichier et analyser le code
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # Chercher PROJECT_DATA dans le code source

            # Méthode 1: Recherche par regex pour extraire la définition complète
            project_data_pattern = r'PROJECT_DATA\s*=\s*\{.*?\n\s*\}'
            match = re.search(project_data_pattern, source_code, re.DOTALL | re.MULTILINE)

            if match:
                try:
                    # Extraire juste la partie assignation
                    project_data_assignment = match.group(0)

                    # Créer un environnement d'exécution
                    local_vars = {}
                    global_vars = {
                        'datetime': __import__('datetime'),
                        'uuid': __import__('uuid')
                    }

                    # Exécuter juste l'assignation PROJECT_DATA
                    exec(project_data_assignment, global_vars, local_vars)

                    if "PROJECT_DATA" in local_vars:
                        logger.info(f"Données extraites depuis {file_path} (via regex + exec)")
                        return local_vars["PROJECT_DATA"]

                except Exception as regex_exec_error:
                    logger.warning(f"Erreur lors de l'extraction regex: {regex_exec_error}")

            # Méthode 2: Analyse AST pour trouver PROJECT_DATA
            try:
                tree = ast.parse(source_code)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == "PROJECT_DATA":
                                # Trouver la valeur assignée et l'évaluer
                                try:
                                    # Compiler juste cette assignation
                                    assign_code = compile(ast.Module(body=[node], type_ignores=[]),
                                                          filename=file_path, mode='exec')

                                    local_vars = {}
                                    global_vars = {
                                        'datetime': __import__('datetime'),
                                        'uuid': __import__('uuid')
                                    }

                                    exec(assign_code, global_vars, local_vars)

                                    if "PROJECT_DATA" in local_vars:
                                        logger.info(f"Données extraites depuis {file_path} (via AST)")
                                        return local_vars["PROJECT_DATA"]

                                except Exception as ast_exec_error:
                                    logger.warning(f"Erreur lors de l'exécution AST: {ast_exec_error}")
                                    continue

            except Exception as ast_error:
                logger.warning(f"Erreur lors de l'analyse AST: {ast_error}")

            # Méthode 3: Fallback - exécution complète du code et recherche dans les locals
            try:
                # Créer un environnement complet
                complete_globals = {
                    '__name__': '__main__',
                    '__file__': file_path,
                    'datetime': __import__('datetime'),
                    'uuid': __import__('uuid'),
                    'pydgraph': None,  # Mock pour éviter les erreurs d'import
                    'json': __import__('json'),
                    'logging': __import__('logging'),
                }

                complete_locals = {}

                # Exécuter tout le code
                exec(source_code, complete_globals, complete_locals)

                # Chercher PROJECT_DATA dans les variables locales
                if "PROJECT_DATA" in complete_locals:
                    logger.info(f"Données trouvées depuis {file_path} (via exec complète)")
                    return complete_locals["PROJECT_DATA"]

                # Si PROJECT_DATA n'est pas dans locals, vérifier dans globals
                if "PROJECT_DATA" in complete_globals:
                    logger.info(f"Données trouvées depuis {file_path} (via exec complète - globals)")
                    return complete_globals["PROJECT_DATA"]

            except Exception as complete_exec_error:
                logger.warning(f"Erreur lors de l'exécution complète: {complete_exec_error}")

            raise AttributeError(f"Le fichier {file_path} n'a pas de variable PROJECT_DATA accessible")

        except Exception as e:
            logger.error(f"Erreur lors du chargement de {file_path}: {e}")
            return {}

    @staticmethod
    def load_all_projects(base_path: str = LIRIS_BASE_PATH) -> Dict[str, Dict]:
        """Charge tous les projets depuis les fichiers dgraph_*.py."""
        base_path = normalize_path(base_path)
        dgraph_files = ProjectDataLoader.find_dgraph_files(base_path)
        projects_data = {}

        for file_path in dgraph_files:
            try:
                filename = os.path.basename(file_path)
                project_data = ProjectDataLoader.load_project_data_from_file(file_path)
                if project_data:
                    projects_data[filename] = {
                        'file_path': file_path,
                        'data': project_data,
                        'loaded_at': datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"Impossible de charger {file_path}: {e}")

        logger.info(f"Total de {len(projects_data)} projets chargés")
        return projects_data


class FileBasedContextRetriever:
    """Récupérateur de contexte basé sur les fichiers de données plutôt que Dgraph."""

    def __init__(self, projects_data: Dict[str, Dict]):
        self.projects_data = projects_data

    def get_available_projects(self) -> List[str]:
        """Retourne la liste des projets disponibles."""
        return list(self.projects_data.keys())

    def retrieve_project_context(self, project_name: str = None) -> Dict:
        """Récupère le contexte d'un projet spécifique."""
        if project_name and project_name in self.projects_data:
            return self.projects_data[project_name]['data']

        # Si pas de projet spécifique, prendre le premier disponible
        if self.projects_data:
            first_project = list(self.projects_data.keys())[0]
            logger.info(f"Aucun projet spécifié, utilisation de: {first_project}")
            return self.projects_data[first_project]['data']

        return {}

    def search_clusters_by_keywords(self, keywords: List[str], project_name: str = None) -> List[Dict]:
        """Recherche des clusters par mots-clés."""
        project_data = self.retrieve_project_context(project_name)
        matching_clusters = []

        turing_ontology = project_data.get("turing_ontology", {})
        clusters_detailed = turing_ontology.get("clusters_detailed", [])

        for cluster in clusters_detailed:
            cluster_name = cluster.get("name", "").lower()

            # Recherche dans le nom du cluster
            if any(keyword.lower() in cluster_name for keyword in keywords):
                matching_clusters.append(cluster)
                continue

            # Recherche dans les labels du cluster
            root_labels = cluster.get("root_labels", [])
            if self._search_in_labels(root_labels, keywords):
                matching_clusters.append(cluster)

        return matching_clusters

    def _search_in_labels(self, labels: List[Dict], keywords: List[str]) -> bool:
        """Recherche récursive dans les labels."""
        for label in labels:
            label_name = label.get("name", "").lower()
            label_type = label.get("type", "").lower()
            full_path = label.get("full_path", "").lower()
            categories = [cat.lower() for cat in label.get("category", [])]

            # Recherche dans les attributs du label
            searchable_content = [label_name, label_type, full_path] + categories
            if any(keyword.lower() in content for keyword in keywords for content in searchable_content):
                return True

            # Recherche récursive dans les sous-labels selon la vraie structure
            if self._search_in_labels(label.get("parent_labels", []), keywords):
                return True
            if self._search_in_labels(label.get("child_labels", []), keywords):
                return True

        return False


class FileBasedContextProcessor:
    """Traite et structure le contexte récupéré depuis les fichiers."""

    @staticmethod
    def extract_relevant_context(project_data: Dict, keywords: List[str] = None,
                                 project_filename: str = None) -> Dict:
        """Extrait et structure le contexte pertinent depuis les données de fichier."""
        processed_context = {
            "project_info": {
                "name": project_data.get("name", "Projet sans nom"),
                "source_file": project_filename,
                "loaded_at": datetime.now().isoformat()
            },
            "clusters": [],
            "labels_hierarchy": {},
            "keyword_matches": [],
            "statistics": {
                "total_clusters": 0,
                "total_labels": 0,
                "matched_items": 0
            }
        }

        turing_ontology = project_data.get("turing_ontology", {})
        clusters_detailed = turing_ontology.get("clusters_detailed", [])

        processed_context["statistics"]["total_clusters"] = len(clusters_detailed)

        for cluster in clusters_detailed:
            cluster_info = {
                "id": cluster.get("id"),
                "name": cluster.get("name"),
                "labels": [],
                "label_count": 0
            }

            root_labels = cluster.get("root_labels", [])

            for root_label in root_labels:
                label_tree = FileBasedContextProcessor._process_label_tree(
                    root_label, keywords, level=0, cluster_name=cluster.get("name")
                )

                if label_tree:
                    cluster_info["labels"].append(label_tree)
                    # Compter récursivement tous les labels dans l'arbre
                    cluster_info["label_count"] += FileBasedContextProcessor._count_labels_in_tree(label_tree)

                    if keywords and FileBasedContextProcessor._tree_matches_keywords(label_tree, keywords):
                        processed_context["keyword_matches"].append({
                            "cluster": cluster.get("name"),
                            "label_tree": label_tree
                        })

            processed_context["statistics"]["total_labels"] += cluster_info["label_count"]

            if cluster_info["labels"] or not keywords:  # Inclure tous les clusters si pas de mots-clés
                processed_context["clusters"].append(cluster_info)

        processed_context["statistics"]["matched_items"] = len(processed_context["keyword_matches"])

        return processed_context

    @staticmethod
    def _process_label_tree(label_data: Dict, keywords: List[str] = None,
                            level: int = 0, cluster_name: str = None) -> Dict:
        """Traite récursivement un arbre de labels."""
        label_info = {
            "id": label_data.get("id"),
            "name": label_data.get("name"),
            "type": label_data.get("type"),
            "full_path": label_data.get("full_path"),
            "category": label_data.get("category", []),
            "level": level,
            "cluster": cluster_name,
            "parent_labels": [],
            "child_labels": [],
            "matches_keywords": False
        }

        # Vérification des mots-clés pour ce label
        if keywords:
            label_info["matches_keywords"] = FileBasedContextProcessor._label_matches_keywords(
                label_info, keywords
            )

        # Traitement récursif selon la vraie hiérarchie
        # Dans votre structure, parent_labels sont en fait les enfants du label racine
        for parent_label in label_data.get("parent_labels", []):
            parent_processed = FileBasedContextProcessor._process_label_tree(
                parent_label, keywords, level + 1, cluster_name
            )
            if parent_processed:
                label_info["parent_labels"].append(parent_processed)

        # child_labels sont les enfants des parents
        for child_label in label_data.get("child_labels", []):
            child_processed = FileBasedContextProcessor._process_label_tree(
                child_label, keywords, level + 1, cluster_name
            )
            if child_processed:
                label_info["child_labels"].append(child_processed)

        # Si des mots-clés sont spécifiés, ne retourner que si correspondance trouvée
        if keywords:
            has_match = (label_info["matches_keywords"] or
                         any(child.get("matches_keywords") for child in label_info["child_labels"]) or
                         any(parent.get("matches_keywords") for parent in label_info["parent_labels"]))
            return label_info if has_match else None

        return label_info

    @staticmethod
    def _label_matches_keywords(label_info: Dict, keywords: List[str]) -> bool:
        """Vérifie si un label correspond aux mots-clés."""
        searchable_content = " ".join([
            label_info.get("name", ""),
            label_info.get("type", ""),
            label_info.get("full_path", ""),
            " ".join(label_info.get("category", []))
        ]).lower()

        return any(keyword.lower() in searchable_content for keyword in keywords)

    @staticmethod
    def _tree_matches_keywords(tree: Dict, keywords: List[str]) -> bool:
        """Vérifie récursivement si un arbre de labels contient des correspondances."""
        if tree.get("matches_keywords", False):
            return True

        # Vérification récursive dans tous les sous-arbres
        for child in tree.get("child_labels", []):
            if FileBasedContextProcessor._tree_matches_keywords(child, keywords):
                return True

        for parent in tree.get("parent_labels", []):
            if FileBasedContextProcessor._tree_matches_keywords(parent, keywords):
                return True

        return False

    @staticmethod
    def _count_labels_in_tree(tree: Dict) -> int:
        """Compte récursivement le nombre de labels dans un arbre."""
        count = 1  # Le label actuel
        count += sum(FileBasedContextProcessor._count_labels_in_tree(child)
                     for child in tree.get("child_labels", []))
        count += sum(FileBasedContextProcessor._count_labels_in_tree(parent)
                     for parent in tree.get("parent_labels", []))
        return count


class EnhancedPromptGenerator:
    """Génère des prompts améliorés pour Gemini basés sur les données de fichiers."""

    @staticmethod
    def build_comprehensive_prompt(context: Dict, user_request: str) -> str:
        """Construit un prompt complet à partir du contexte de fichier."""
        prompt_parts = [
            "# Analyse de Projet - Système Liris",
            "",
            "## Projet ciblé par l'utilisateur",
            f"**Projet sélectionné**: {context.get('project_info', {}).get('name', 'N/A')}",
            "",
            "## Informations du Projet",
            f"**Nom interne**: {context.get('project_info', {}).get('name', 'N/A')}",
            f"**Fichier source**: {context.get('project_info', {}).get('source_file', 'N/A')}",
            f"**Date de chargement**: {context.get('project_info', {}).get('loaded_at', 'N/A')}",
            "",
        ]

        # Ajout détaillé des clusters et leur hiérarchie
        for cluster in context.get('clusters', []):
            prompt_parts.extend([
                f"### Cluster: {cluster['name']}",
                f"- **ID**: {cluster.get('id', 'N/A')}",
                f"- **Nombre de labels**: {cluster.get('label_count', 0)}",
                ""
            ])

            # Ne pas afficher les clusters vides dans le prompt
            if cluster.get('label_count', 0) > 0:
                for label_tree in cluster.get('labels', []):
                    prompt_parts.extend(
                        EnhancedPromptGenerator._format_label_tree(label_tree, indent=1)
                    )
            else:
                prompt_parts.append("  (Cluster vide - aucun label)")
                prompt_parts.append("")

        # Section des correspondances spécifiques
        if context.get('keyword_matches'):
            prompt_parts.extend([
                "",
                "## Éléments Pertinents Identifiés",
                ""
            ])

            for match in context['keyword_matches']:
                prompt_parts.extend([
                    f"### Dans le cluster '{match['cluster']}':",
                    ""
                ])
                prompt_parts.extend(
                    EnhancedPromptGenerator._format_label_tree(match['label_tree'], indent=1, highlight=True)
                )

        # Section de la demande utilisateur et instructions
        prompt_parts.extend([
            "",
            "---",
            "",
            "## Demande de l'Utilisateur",
            "",
            f"**Requête**: {user_request}",
            "",
            "## Instructions pour la Réponse",
            "",
            "En tant qu'assistant spécialisé dans l'analyse de projets Liris, veuillez:",
            "",
            "1. **Analyser** la structure hiérarchique du projet présentée",
            "2. **Identifier** les éléments pertinents à la demande utilisateur",
            "3. **Utiliser** les informations de contexte (chemins, types, catégories)",
            "4. **Respecter** la hiérarchie: Cluster -> Root Labels -> Parent Labels -> Child Labels",
            "5. **Proposer** une solution pratique et détaillée",
            "6. **Inclure** du code ou des exemples si approprié",
            "",
            "**Format attendu**:",
            "- Réponse structurée et claire",
            "- Utilisation des informations spécifiques du projet",
            "- Exemples concrets basés sur la structure réelle",
            "- Conseils pratiques d'implémentation",
            "",
            "---",
            "",
            "**Contexte technique**: Ce projet utilise une structure ontologique avec des clusters contenant des labels hiérarchiques. La hiérarchie est: Cluster > Root Labels > Parent Labels > Child Labels. Chaque niveau peut contenir des fichiers ou des dossiers."
        ])

        return "\n".join(prompt_parts)

    @staticmethod
    def _format_label_tree(tree: Dict, indent: int = 0, highlight: bool = False) -> List[str]:
        """Formate récursivement un arbre de labels."""
        prefix = "  " * indent
        marker = "🔍 " if highlight and tree.get("matches_keywords") else ""

        # Affichage du type et de l'icône appropriée
        type_icon = "📁" if tree.get('type') == 'directory' else "📄"

        lines = [
            f"{prefix}{marker}{type_icon} **{tree.get('name', 'Sans nom')}**"
        ]

        # Informations détaillées du label
        details = []
        if tree.get('type'):
            details.append(f"Type: {tree['type']}")
        if tree.get('id'):
            details.append(f"ID: {tree['id'][:8]}...")
        if tree.get('category'):
            details.append(f"Catégories: {', '.join(tree['category'])}")

        if details:
            lines.append(f"{prefix}  _{' | '.join(details)}_")

        if tree.get('full_path'):
            lines.append(f"{prefix}  📍 `{tree['full_path']}`")

        # Traitement correct de la hiérarchie
        # parent_labels sont les enfants directs dans votre structure
        if tree.get('parent_labels'):
            lines.append(f"{prefix}  📂 **Contenu**:")
            for parent in tree['parent_labels']:
                lines.extend(EnhancedPromptGenerator._format_label_tree(
                    parent, indent + 2, highlight
                ))

        # child_labels sont les sous-enfants
        if tree.get('child_labels'):
            lines.append(f"{prefix}  📂 **Sous-éléments**:")
            for child in tree['child_labels']:
                lines.extend(EnhancedPromptGenerator._format_label_tree(
                    child, indent + 2, highlight
                ))

        lines.append("")  # Ligne vide pour la lisibilité
        return lines


class GeminiService:
    """Service pour interagir avec l'API Gemini."""

    def __init__(self, model_name: str = "gemini-pro"):
        self.model = genai.GenerativeModel(model_name)

    def generate_response(self, prompt: str, max_tokens: int = 4096) -> str:
        """Génère une réponse avec Gemini."""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Erreur lors de la génération avec Gemini: {e}")
            return f"Erreur lors de la génération: {str(e)}"


class LirisProjectAssistant:
    """Assistant principal pour les projets Liris basé sur les fichiers."""

    def __init__(self, base_path: str = LIRIS_BASE_PATH):
        self.base_path = base_path
        self.projects_data = {}
        self.context_retriever = None
        self.context_processor = FileBasedContextProcessor()
        self.prompt_generator = EnhancedPromptGenerator()
        self.gemini_service = GeminiService()

        # Chargement initial des projets
        self.reload_projects()

    def reload_projects(self):
        """Recharge tous les projets depuis les fichiers."""
        logger.info("Rechargement des données de projet...")
        self.projects_data = ProjectDataLoader.load_all_projects(self.base_path)
        self.context_retriever = FileBasedContextRetriever(self.projects_data)
        logger.info(f"Projets chargés: {list(self.projects_data.keys())}")

    def list_available_projects(self) -> List[str]:
        """Liste les projets disponibles."""
        return list(self.projects_data.keys())

    def process_user_request(self, user_request: str, project_name: str = None,
                             keywords: List[str] = None) -> Dict:
        """Traite une demande utilisateur complète."""
        try:
            # 1. Validation et préparation
            if not self.projects_data:
                return {
                    "success": False,
                    "error": "Aucun projet chargé",
                    "user_request": user_request
                }

            # 2. Extraction automatique des mots-clés si non fournis
            if keywords is None:
                keywords = self._extract_keywords(user_request)

            logger.info(f"Traitement de la demande avec mots-clés: {keywords}")
            if project_name:
                logger.info(f"Projet spécifié: {project_name}")

            # 3. Récupération du contexte
            project_data = self.context_retriever.retrieve_project_context(project_name)

            if not project_data:
                return {
                    "success": False,
                    "error": f"Projet '{project_name}' non trouvé",
                    "available_projects": self.list_available_projects(),
                    "user_request": user_request
                }

            # 4. Traitement du contexte
            used_project_name = project_name or self.list_available_projects()[0]
            processed_context = self.context_processor.extract_relevant_context(
                project_data, keywords, used_project_name
            )

            # 5. Génération du prompt
            prompt = self.prompt_generator.build_comprehensive_prompt(
                processed_context, user_request
            )

            # 6. Génération de la réponse avec Gemini
            gemini_response = self.gemini_service.generate_response(prompt)

            return {
                "success": True,
                "user_request": user_request,
                "project_used": used_project_name,
                "keywords": keywords,
                "context": processed_context,
                "prompt": prompt,
                "response": gemini_response,
                "timestamp": datetime.now().isoformat(),
                "available_projects": self.list_available_projects()
            }

        except Exception as e:
            logger.error(f"Erreur lors du traitement de la demande: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_request": user_request,
                "timestamp": datetime.now().isoformat()
            }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extrait automatiquement les mots-clés d'un texte."""
        stop_words = {
            'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'ou', 'mais',
            'pour', 'avec', 'dans', 'sur', 'par', 'à', 'au', 'aux', 'ce', 'ces',
            'cette', 'son', 'sa', 'ses', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes',
            'comment', 'quoi', 'quand', 'où', 'pourquoi', 'how', 'what', 'when',
            'where', 'why', 'the', 'a', 'an', 'and', 'or', 'but', 'for', 'with',
            'in', 'on', 'by', 'to', 'at', 'this', 'that', 'créer', 'faire',
            'système', 'code', 'script'
        }

        # Nettoyage et extraction des mots
        clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = clean_text.split()

        keywords = [
            word.strip() for word in words
            if len(word) > 2 and word not in stop_words and word.isalpha()
        ]

        return list(set(keywords))  # Suppression des doublons


def main():
    """Fonction principale pour le script de récupération."""
    try:
        # Vérification de l'existence du dossier liris
        if not os.path.exists(LIRIS_BASE_PATH):
            logger.error(f"Dossier liris non trouvé: {LIRIS_BASE_PATH}")
            return

        # Initialisation de l'assistant
        assistant = LirisProjectAssistant()

        if not assistant.list_available_projects():
            logger.error("Aucun fichier dgraph_*.py trouvé dans le dossier liris")
            return

        print("=== Assistant de Projet Liris ===")
        print(f"Dossier de base: {LIRIS_BASE_PATH}")
        print(f"Projets disponibles: {', '.join(assistant.list_available_projects())}")
        print("\nCommandes spéciales:")
        print("- 'list': Afficher les projets disponibles")
        print("- 'reload': Recharger les projets")
        print("- 'quit' ou 'q': Quitter")
        print("=" * 50)

        while True:
            user_input = input("\nEntrez votre demande: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            elif user_input.lower() == 'list':
                print(f"Projets disponibles: {', '.join(assistant.list_available_projects())}")
                continue
            elif user_input.lower() == 'reload':
                assistant.reload_projects()
                print("Projets rechargés!")
                continue

            if not user_input:
                continue

            # Demande optionnelle du projet spécifique
            project_choice = input("Projet spécifique (ou Entrée pour auto): ").strip()
            project_name = project_choice if project_choice else None

            print("\nTraitement en cours...")

            # Traitement de la demande
            result = assistant.process_user_request(user_input, project_name)

            if result["success"]:
                context = result["context"]
                print(f"\n**Analyse terminée**")
                print(f"Projet utilisé: {result['project_used']}")
                print(f"Mots-clés: {', '.join(result.get('keywords', []))}")
                print(f"Clusters: {context['statistics']['total_clusters']}")
                print(f"Labels: {context['statistics']['total_labels']}")
                print(f"Correspondances: {context['statistics']['matched_items']}")

                print("\n" + "=" * 50)
                print("**Réponse Gemini**")
                print("=" * 50)
                print(result["response"])

                # Option d'afficher le prompt complet
                show_details = input("\nAfficher les détails (prompt, contexte)? (y/n): ").lower() == 'y'
                if show_details:
                    print("\n" + "=" * 50)
                    print("**Prompt Complet**")
                    print("=" * 50)
                    print(result["prompt"])

                    print("\n" + "=" * 50)
                    print("**Contexte Structuré**")
                    print("=" * 50)
                    print(json.dumps(context, indent=2, ensure_ascii=False))
            else:
                print(f"\n**Erreur**: {result['error']}")
                if 'available_projects' in result:
                    print(f"Projets disponibles: {', '.join(result['available_projects'])}")

            print("\n" + "=" * 60 + "\n")

    except KeyboardInterrupt:
        print("\n\nArrêt demandé par l'utilisateur.")
    except Exception as e:
        logger.error(f"Erreur dans le programme principal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Au revoir!")


if __name__ == "__main__":
    main()
from typing import Dict, List

class EnhancedPromptGenerator:
    """Génère des prompts améliorés pour Gemini basés sur les données de fichiers."""

    @staticmethod
    def build_comprehensive_prompt(context: Dict, user_request: str) -> str:
        """Construit un prompt complet à partir du contexte de fichier."""
        prompt_parts = [
            "# Analyse de Projet - Système Liris",
            "",
            "## Informations du Projet",
            f"**Nom du projet**: {context.get('project_info', {}).get('name', 'N/A')}",
            f"**Fichier source**: {context.get('project_info', {}).get('source_file', 'N/A')}",
            f"**Date de chargement**: {context.get('project_info', {}).get('loaded_at', 'N/A')}",
            "",
            "## Statistiques",
            f"- **Clusters totaux**: {context.get('statistics', {}).get('total_clusters', 0)}",
            f"- **Labels totaux**: {context.get('statistics', {}).get('total_labels', 0)}",
            f"- **Éléments correspondants**: {context.get('statistics', {}).get('matched_items', 0)}",
            "",
            "## Structure Hiérarchique du Projet",
            ""
        ]

        for cluster in context.get('clusters', []):
            prompt_parts.extend([
                f"### Cluster: {cluster['name']}",
                f"- **ID**: {cluster.get('id', 'N/A')}",
                f"- **Nombre de labels**: {cluster.get('label_count', 0)}",
                ""
            ])

            if cluster.get('label_count', 0) > 0:
                for label_tree in cluster.get('labels', []):
                    prompt_parts.extend(
                        EnhancedPromptGenerator._format_label_tree(label_tree, indent=1)
                    )
            else:
                prompt_parts.append("  (Cluster vide - aucun label)")
                prompt_parts.append("")

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
            "**Contexte technique**: Ce projet utilise une structure ontologique avec des clusters contenant des labels hiérarchiques. La hiérarchie est: Cluster > Root Labels > Parent Labels > Child Labels."
        ])

        return "\n".join(prompt_parts)

    @staticmethod
    def _format_label_tree(tree: Dict, indent: int = 0, highlight: bool = False) -> List[str]:
        """Formate récursivement un arbre de labels."""
        prefix = "  " * indent
        marker = "🔍 " if highlight and tree.get("matches_keywords") else ""
        type_icon = "📁" if tree.get('type') == 'directory' else "📄"

        lines = [f"{prefix}{marker}{type_icon} **{tree.get('name', 'Sans nom')}**"]

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
            lines.append(f"{prefix}   `{tree['full_path']}`")

        if tree.get('parent_labels'):
            lines.append(f"{prefix}   **Contenu**:")
            for parent in tree['parent_labels']:
                lines.extend(EnhancedPromptGenerator._format_label_tree(parent, indent + 2, highlight))

        if tree.get('child_labels'):
            lines.append(f"{prefix}   **Sous-éléments**:")
            for child in tree['child_labels']:
                lines.extend(EnhancedPromptGenerator._format_label_tree(child, indent + 2, highlight))

        lines.append("")
        return lines

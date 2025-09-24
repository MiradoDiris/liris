# ui/widgets/visualization.py

import os
import json
import plotly.graph_objects as go
import plotly.offline as pyo
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime
from pathlib import Path

class DatasetVisualization:
    """Classe pour générer des visualisations de données de vérification de dataset"""
    
    def __init__(self, output_dir="templates/visualizations"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Couleurs personnalisées pour les graphiques
        self.color_palette = {
            'excellent': '#2E8B57',  # Sea Green
            'good': '#3CB371',       # Medium Sea Green
            'average': '#FFA500',    # Orange
            'poor': '#FF6347',       # Tomato
            'critical': '#DC143C',   # Crimson
            'gemini': '#4285F4',     # Google Blue
            'gpt': '#10A37F',        # ChatGPT Green
            'claude': '#FF6B35',     # Anthropic Orange
            'other': '#6C757D'       # Gray
        }
    
    def generate_verification_pie_chart(self, verification_data, title="Score de Qualité du Dataset"):
        """
        Génère un camembert pour visualiser le score de qualité
        
        Args:
            verification_data (dict): Données de vérification
            title (str): Titre du graphique
            
        Returns:
            str: Chemin vers le fichier HTML généré
        """
        try:
            quality_score = verification_data.get('quality_score', 0)
            issues = verification_data.get('issues_found', [])
            stats = verification_data.get('statistics', {})
            
            # Créer les données pour le camembert
            labels = []
            values = []
            colors = []
            
            # Score de qualité principal
            labels.append(f"Score: {quality_score}%")
            values.append(quality_score)
            colors.append(self._get_quality_color(quality_score))
            
            # Problèmes par sévérité
            severity_counts = {'high': 0, 'medium': 0, 'low': 0}
            for issue in issues:
                severity = issue.get('severity', 'medium')
                count = issue.get('count', 1)
                severity_counts[severity] += count
            
            # Ajouter les problèmes au camembert
            for severity, count in severity_counts.items():
                if count > 0:
                    labels.append(f"Problèmes {severity}")
                    values.append(count)
                    colors.append(self._get_severity_color(severity))
            
            # Créer le graphique
            fig = go.Figure()
            
            fig.add_trace(go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker=dict(colors=colors),
                textinfo='label+percent',
                textposition='inside',
                hoverinfo='label+value+percent',
                pull=[0.1] + [0] * (len(values) - 1)  # Mettre en évidence le score principal
            ))
            
            # Mise en forme
            fig.update_layout(
                title={
                    'text': title,
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 20, 'color': '#A23B2D'}
                },
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=1.05
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12),
                margin=dict(t=50, b=50, l=50, r=150)
            )
            
            # Sauvegarder le graphique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"verification_pie_{timestamp}.html"
            filepath = self.output_dir / filename
            
            pyo.plot(fig, filename=str(filepath), auto_open=False)
            
            return str(filepath)
            
        except Exception as e:
            print(f"Erreur lors de la génération du camembert: {str(e)}")
            return None
    
    def generate_comparison_chart(self, datasets_by_theme):
        """
        Génère un graphique comparatif des datasets par thématique et modèle IA
        
        Args:
            datasets_by_theme (dict): Données groupées par thématique
            
        Returns:
            str: Chemin vers le fichier HTML généré
        """
        try:
            # Préparer les données pour la comparaison
            themes = []
            models = set()
            scores_data = {}
            
            for theme, theme_data in datasets_by_theme.items():
                themes.append(theme)
                for model, datasets in theme_data.items():
                    models.add(model)
                    if theme not in scores_data:
                        scores_data[theme] = {}
                    
                    # Calculer le score moyen pour cette combinaison thème/modèle
                    scores = [d.get('quality_score', 0) for d in datasets]
                    avg_score = sum(scores) / len(scores) if scores else 0
                    scores_data[theme][model] = avg_score
            
            models = sorted(list(models))
            
            # Créer le graphique à barres groupées
            fig = go.Figure()
            
            for i, model in enumerate(models):
                model_scores = [scores_data.get(theme, {}).get(model, 0) for theme in themes]
                
                fig.add_trace(go.Bar(
                    name=model,
                    x=themes,
                    y=model_scores,
                    marker_color=self._get_model_color(model),
                    text=model_scores,
                    texttemplate='%{text:.1f}',
                    textposition='auto',
                ))
            
            fig.update_layout(
                title={
                    'text': 'Comparaison des Scores par Thématique et Modèle IA',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 18, 'color': '#A23B2D'}
                },
                xaxis_title="Thématiques",
                yaxis_title="Score de Qualité Moyen",
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Sauvegarder le graphique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comparison_chart_{timestamp}.html"
            filepath = self.output_dir / filename
            
            pyo.plot(fig, filename=str(filepath), auto_open=False)
            
            return str(filepath)
            
        except Exception as e:
            print(f"Erreur lors de la génération du graphique comparatif: {str(e)}")
            return None
    
    def generate_detailed_analysis_chart(self, verification_data):
        """
        Génère un graphique détaillé avec plusieurs métriques
        
        Args:
            verification_data (dict): Données de vérification complètes
            
        Returns:
            str: Chemin vers le fichier HTML généré
        """
        try:
            # Créer un subplot avec plusieurs graphiques
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Score de Qualité', 'Répartition des Problèmes', 
                              'Statistiques des Items', 'Détail par Type de Problème'),
                specs=[[{"type": "pie"}, {"type": "bar"}],
                       [{"type": "bar"}, {"type": "bar"}]]
            )
            
            # Graphique 1: Score de qualité (camembert)
            quality_score = verification_data.get('quality_score', 0)
            remaining_score = 100 - quality_score
            
            fig.add_trace(go.Pie(
                labels=[f'Score: {quality_score}%', 'Restant'],
                values=[quality_score, remaining_score],
                hole=0.6,
                marker=dict(colors=[self._get_quality_color(quality_score), '#E0E0E0'])
            ), 1, 1)
            
            # Graphique 2: Répartition des problèmes par sévérité (barres)
            issues = verification_data.get('issues_found', [])
            severity_counts = {'Élevée': 0, 'Moyenne': 0, 'Faible': 0}
            
            for issue in issues:
                severity = issue.get('severity', 'medium')
                count = issue.get('count', 1)
                if severity == 'high':
                    severity_counts['Élevée'] += count
                elif severity == 'medium':
                    severity_counts['Moyenne'] += count
                else:
                    severity_counts['Faible'] += count
            
            fig.add_trace(go.Bar(
                x=list(severity_counts.keys()),
                y=list(severity_counts.values()),
                marker_color=['#DC143C', '#FFA500', '#3CB371']
            ), 1, 2)
            
            # Graphique 3: Statistiques des items
            stats = verification_data.get('statistics', {})
            fig.add_trace(go.Bar(
                x=['Total', 'Valides', 'Invalides'],
                y=[stats.get('total_items', 0), stats.get('valid_items', 0), stats.get('invalid_items', 0)],
                marker_color=['#4285F4', '#2E8B57', '#DC143C']
            ), 2, 1)
            
            # Graphique 4: Détail par type de problème
            issue_types = {}
            for issue in issues:
                issue_type = issue.get('type', 'Autre')
                count = issue.get('count', 1)
                issue_types[issue_type] = issue_types.get(issue_type, 0) + count
            
            fig.add_trace(go.Bar(
                x=list(issue_types.keys()),
                y=list(issue_types.values()),
                marker_color=px.colors.qualitative.Set3
            ), 2, 2)
            
            # Mise en forme
            fig.update_layout(
                title={
                    'text': 'Analyse Détaillée de la Vérification',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 20, 'color': '#A23B2D'}
                },
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(size=10),
                height=800,
                showlegend=False
            )
            
            # Sauvegarder le graphique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"detailed_analysis_{timestamp}.html"
            filepath = self.output_dir / filename
            
            pyo.plot(fig, filename=str(filepath), auto_open=False)
            
            return str(filepath)
            
        except Exception as e:
            print(f"Erreur lors de la génération de l'analyse détaillée: {str(e)}")
            return None
    
    def _get_quality_color(self, score):
        """Retourne la couleur correspondant au score de qualité"""
        if score >= 80:
            return self.color_palette['excellent']
        elif score >= 60:
            return self.color_palette['good']
        elif score >= 40:
            return self.color_palette['average']
        elif score >= 20:
            return self.color_palette['poor']
        else:
            return self.color_palette['critical']
    
    def _get_severity_color(self, severity):
        """Retourne la couleur correspondant à la sévérité"""
        color_map = {
            'high': self.color_palette['critical'],
            'medium': self.color_palette['poor'],
            'low': self.color_palette['average']
        }
        return color_map.get(severity, self.color_palette['other'])
    
    def _get_model_color(self, model_name):
        """Retourne la couleur correspondant au modèle IA"""
        model_lower = model_name.lower()
        if 'gemini' in model_lower:
            return self.color_palette['gemini']
        elif 'gpt' in model_lower or 'chatgpt' in model_lower:
            return self.color_palette['gpt']
        elif 'claude' in model_lower:
            return self.color_palette['claude']
        else:
            return self.color_palette['other']
    
    def cleanup_old_files(self, max_files=10):
        """Nettoie les anciens fichiers de visualisation"""
        try:
            visualization_files = list(self.output_dir.glob("*.html"))
            if len(visualization_files) > max_files:
                # Trier par date de modification
                visualization_files.sort(key=os.path.getmtime)
                # Supprimer les plus anciens
                for file in visualization_files[:-max_files]:
                    file.unlink()
        except Exception as e:
            print(f"Erreur lors du nettoyage des fichiers: {str(e)}")


# Fonction utilitaire pour intégration avec dataset_verification_tab.py
def generate_verification_pie_chart(verification_data, title="Score de Qualité du Dataset"):
    """
    Fonction simplifiée pour générer un camembert de vérification
    
    Args:
        verification_data (dict): Données de vérification
        title (str): Titre du graphique
        
    Returns:
        str: Chemin vers le fichier HTML généré ou None en cas d'erreur
    """
    viz = DatasetVisualization()
    return viz.generate_verification_pie_chart(verification_data, title)


def generate_comparison_visualization(datasets_by_theme):
    """
    Fonction simplifiée pour générer une visualisation comparative
    
    Args:
        datasets_by_theme (dict): Données groupées par thématique
        
    Returns:
        str: Chemin vers le fichier HTML généré ou None en cas d'erreur
    """
    viz = DatasetVisualization()
    return viz.generate_comparison_chart(datasets_by_theme)


# Exemple d'utilisation
if __name__ == "__main__":
    # Données d'exemple pour tester
    sample_data = {
        "quality_score": 75,
        "issues_found": [
            {
                "type": "format_inconsistent",
                "description": "Format de date incohérent",
                "severity": "medium",
                "count": 3
            },
            {
                "type": "missing_data",
                "description": "Données manquantes",
                "severity": "high",
                "count": 1
            }
        ],
        "statistics": {
            "total_items": 100,
            "valid_items": 85,
            "invalid_items": 15
        }
    }
    
    # Générer un camembert
    viz = DatasetVisualization()
    chart_path = viz.generate_verification_pie_chart(sample_data)
    print(f"Graphique généré: {chart_path}")
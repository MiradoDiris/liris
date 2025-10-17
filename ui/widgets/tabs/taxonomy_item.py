# taxonomy_item.py - Version étendue pour intégration avec GraphWidget
# Ajout : Utilisation des niveaux pour moduler les icônes/couleurs dans le graphe,
# et intégration des types pour _get_color_for_type dans GraphWidget.

import qtawesome as qta

from PyQt5 import QtWidgets


class TaxonomyItem(QtWidgets.QTreeWidgetItem):
    """Item pour l'arbre de taxonomie avec métadonnées.
    Étendu : Niveaux utilisés pour modulation couleurs dans graphe (via level)."""
    
    def __init__(self, parent, text, item_type="folder", data=None, level=0):
        super().__init__(parent, [text])
        self.item_type = item_type
        self.item_data = data or {}
        self.level = level  # Niveau utilisé dans GraphWidget pour couleurs/labels
        
        # Palette monochrome professionnelle (gris et rouge thème uniquement)
        primary = '#A23B2D'  # Rouge thème
        dark_gray = '#424242'
        medium_gray = '#666666'
        strong_gray = '#555555'
        
        # Modulation couleur par niveau (pour intégration graphe)
        def modulate_color(base_color, level):
            # Exemple : plus clair pour niveaux supérieurs (simplifié)
            if level > 1:
                if base_color == primary:
                    return '#D35A4A'  # Plus clair
                elif base_color == dark_gray:
                    return medium_gray
            return base_color
        
        modulated_primary = modulate_color(primary, level)
        modulated_dark = modulate_color(dark_gray, level)
        
        # Icônes professionnelles avec couleurs sobres (modulées)
        if item_type == "folder":
            self.setIcon(0, qta.icon('fa5s.folder', color=strong_gray))
        elif item_type == "file":
            self.setIcon(0, qta.icon('fa5s.file-code', color=strong_gray))
        elif item_type == "function":
            self.setIcon(0, qta.icon('fa5s.cube', color=modulated_primary))
        elif item_type == "dependency":
            self.setIcon(0, qta.icon('fa5s.link', color=strong_gray))
        elif item_type == "class":
            self.setIcon(0, qta.icon('fa5s.cubes', color=modulated_dark))
        elif item_type == "variable":
            self.setIcon(0, qta.icon('fa5s.tag', color=medium_gray))
        
        # Méthode utilitaire pour graphe (appelable depuis GraphWidget)
        self.graph_color = self._get_graph_color()
    
    def _get_graph_color(self):
        """Retourne couleur pour graphe basée sur type et niveau."""
        color_map = {
            "folder": '#424242',
            "file": '#555555',
            "function": '#A23B2D',
            "dependency": '#555555',
            "class": '#424242',
            "variable": '#999999',
        }
        base_color = color_map.get(self.item_type, '#607D8B')
        # Modulation par niveau (utilisée dans _get_color_for_type)
        if self.level > 1:
            # Logique de modulation (ex: alpha ou teinte)
            pass  # Implémentée dans GraphWidget
        return base_color
    
    def update_level(self, new_level):
        """Met à jour le niveau et rafraîchit l'icône/couleur pour graphe."""
        self.level = new_level
        modulated_primary = '#D35A4A' if new_level > 1 else '#A23B2D'
        if self.item_type == "function":
            self.setIcon(0, qta.icon('fa5s.cube', color=modulated_primary))
        self.graph_color = self._get_graph_color()
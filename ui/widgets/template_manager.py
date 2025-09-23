"""
Gestionnaire de templates pour les formats de sortie des datasets
"""

import json
import csv
import xml.etree.ElementTree as ET
import yaml
from io import StringIO
from datetime import datetime
from typing import Dict, Any, List, Optional


class TemplateManager:
    """
    Gère les différents formats de sortie pour les datasets générés
    """
    
    def __init__(self):
        self.formatters = {
            'JSON': self._format_json,
            'CSV': self._format_csv,
            'XML': self._format_xml,
            'YAML': self._format_yaml,
            'Texte': self._format_text
        }
        
        # Templates par défaut pour chaque format
        self.default_templates = {
            'JSON': {
                'pretty_print': True,
                'include_metadata': True,
                'structure': 'nested'
            },
            'CSV': {
                'delimiter': ',',
                'include_headers': True,
                'encoding': 'utf-8'
            },
            'XML': {
                'root_element': 'datasets',
                'item_element': 'dataset',
                'pretty_print': True
            },
            'YAML': {
                'default_flow_style': False,
                'include_metadata': True
            },
            'Texte': {
                'separator': '\n' + '='*50 + '\n',
                'include_timestamp': True
            }
        }
    
    def format_dataset(self, dataset: Dict[str, Any], format_type: str, 
                      template_config: Optional[Dict] = None) -> str:
        """
        Formate un dataset selon le format spécifié
        
        Args:
            dataset: Le dataset à formater
            format_type: Le format de sortie (JSON, CSV, XML, YAML, Texte)
            template_config: Configuration spécifique du template
            
        Returns:
            str: Le dataset formaté
        """
        if format_type not in self.formatters:
            raise ValueError(f"Format non supporté: {format_type}")
        
        # Fusionner la configuration avec les valeurs par défaut
        config = self.default_templates.get(format_type, {}).copy()
        if template_config:
            config.update(template_config)
        
        try:
            return self.formatters[format_type](dataset, config)
        except Exception as e:
            raise ValueError(f"Erreur lors du formatage {format_type}: {str(e)}")
    
    def _format_json(self, dataset: Dict[str, Any], config: Dict) -> str:
        """Format JSON avec indentation"""
        output_data = self._prepare_data_structure(dataset, config)
        
        if config.get('pretty_print', True):
            return json.dumps(output_data, indent=2, ensure_ascii=False)
        else:
            return json.dumps(output_data, ensure_ascii=False)
    
    def _format_csv(self, dataset: Dict[str, Any], config: Dict) -> str:
        """Format CSV avec gestion des données structurées"""
        # Préparer les données pour CSV (aplanissement si nécessaire)
        flattened_data = self._flatten_data_for_csv(dataset)
        
        if not flattened_data:
            return ""
            
        output = StringIO()
        delimiter = config.get('delimiter', ',')
        writer = csv.writer(output, delimiter=delimiter)
        
        if config.get('include_headers', True) and flattened_data:
            writer.writerow(flattened_data[0].keys())
        
        for row in flattened_data:
            writer.writerow([str(value) for value in row.values()])
        
        return output.getvalue()
    
    def _format_xml(self, dataset: Dict[str, Any], config: Dict) -> str:
        """Format XML avec structure hiérarchique"""
        root_element_name = config.get('root_element', 'datasets')
        item_element_name = config.get('item_element', 'dataset')
        
        root_element = ET.Element(root_element_name)
        item_element = ET.SubElement(root_element, item_element_name)
        
        self._dict_to_xml(dataset, item_element)
        
        # Formater avec indentation
        if config.get('pretty_print', True):
            self._indent_xml(root_element)
        
        return ET.tostring(root_element, encoding='unicode', method='xml')
    
    def _format_yaml(self, dataset: Dict[str, Any], config: Dict) -> str:
        """Format YAML avec structure claire"""
        output_data = self._prepare_data_structure(dataset, config)
        return yaml.dump(output_data, 
                        default_flow_style=config.get('default_flow_style', False),
                        allow_unicode=True, 
                        encoding=None)
    
    def _format_text(self, dataset: Dict[str, Any], config: Dict) -> str:
        """Format texte lisible"""
        lines = []
        
        if config.get('include_timestamp', True):
            lines.append(f"Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
        
        # Convertir le dataset en texte structuré
        self._dict_to_text(dataset, lines, 0)
        
        separator = config.get('separator', '\n' + '='*50 + '\n')
        return separator.join([str(line) for line in lines])
    
    def _prepare_data_structure(self, dataset: Dict[str, Any], config: Dict) -> Dict[str, Any]:
        """Prépare la structure des données selon la configuration"""
        output_data = dataset.copy()
        
        # Inclure ou exclure les métadonnées selon la configuration
        if not config.get('include_metadata', True):
            metadata_keys = ['id', 'timestamp', 'config', 'context', 'metadata']
            for key in metadata_keys:
                output_data.pop(key, None)
        
        return output_data
    
    def _flatten_data_for_csv(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Aplatit les données complexes pour le format CSV
        Retourne une liste de dictionnaires plats
        """
        flattened = []
        
        def flatten_dict(d, parent_key='', sep='.'):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                elif isinstance(v, list):
                    # Pour les listes, on crée une entrée par élément
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            items.extend(flatten_dict(item, f"{new_key}[{i}]", sep=sep).items())
                        else:
                            items.append((f"{new_key}[{i}]", item))
                else:
                    items.append((new_key, v))
            return dict(items)
        
        # Si le dataset contient une liste d'items, créer une ligne par item
        if 'content' in data and isinstance(data['content'], list):
            for item in data['content']:
                if isinstance(item, dict):
                    base_data = {k: v for k, v in data.items() if k != 'content'}
                    item_flat = flatten_dict(item)
                    # Fusionner les données de base avec l'item
                    merged_data = {**flatten_dict(base_data), **item_flat}
                    flattened.append(merged_data)
        else:
            flattened.append(flatten_dict(data))
        
        return flattened if flattened else [flatten_dict(data)]
    
    def _dict_to_xml(self, data: Dict[str, Any], parent_element: ET.Element):
        """Convertit un dictionnaire en structure XML"""
        for key, value in data.items():
            # Nettoyer le nom de la clé pour XML
            clean_key = key.replace(' ', '_').lower()
            
            if isinstance(value, dict):
                child_element = ET.SubElement(parent_element, clean_key)
                self._dict_to_xml(value, child_element)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        item_element = ET.SubElement(parent_element, clean_key)
                        self._dict_to_xml(item, item_element)
                    else:
                        ET.SubElement(parent_element, clean_key).text = str(item)
            else:
                ET.SubElement(parent_element, clean_key).text = str(value)
    
    def _indent_xml(self, elem: ET.Element, level: int = 0):
        """Indente l'XML pour une meilleure lisibilité"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self._indent_xml(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
    
    def _dict_to_text(self, data: Dict[str, Any], lines: List[str], indent: int):
        """Convertit un dictionnaire en texte formaté"""
        indent_str = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{indent_str}{key}:")
                self._dict_to_text(value, lines, indent + 1)
            elif isinstance(value, list):
                lines.append(f"{indent_str}{key}:")
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        lines.append(f"{indent_str}  - Item {i + 1}:")
                        self._dict_to_text(item, lines, indent + 2)
                    else:
                        lines.append(f"{indent_str}  - {item}")
            else:
                lines.append(f"{indent_str}{key}: {value}")
    
    def get_supported_formats(self) -> List[str]:
        """Retourne la liste des formats supportés"""
        return list(self.formatters.keys())
    
    def validate_template_config(self, format_type: str, config: Dict) -> bool:
        """Valide la configuration d'un template"""
        if format_type not in self.formatters:
            return False
        
        default_config = self.default_templates.get(format_type, {})
        
        # Vérifier que toutes les clés de config sont valides
        for key in config.keys():
            if key not in default_config:
                return False
        
        return True
    
    def generate_example(self, format_type: str, config: Optional[Dict] = None) -> str:
        """Génère un exemple de dataset formaté"""
        example_data = {
            "id": 12345,
            "name": "Example Dataset",
            "timestamp": datetime.now().isoformat(),
            "context": ["Géographie", "Culture générale"],
            "prompt": "Générer des questions sur la France",
            "content": {
                "question": "Quelle est la capitale de la France ?",
                "answer": "Paris",
                "category": "Géographie",
                "difficulty": "Facile",
                "explications": "Paris est la capitale de la France depuis le 6ème siècle"
            },
            "metadata": {
                "generation_platform": "OpenAI GPT-4",
                "batch_id": 1,
                "version": "1.0",
                "typology": "Q&A"
            }
        }
        
        template_config = config or self.default_templates.get(format_type, {})
        return self.format_dataset(example_data, format_type, template_config)


# Instance singleton pour une utilisation globale
template_manager = TemplateManager()
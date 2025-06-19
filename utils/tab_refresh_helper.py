#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
utils/tab_refresh_helper.py - Helper pour rafraîchir automatiquement les widgets lors du changement d'onglet
"""

from PyQt5 import QtWidgets, QtCore
from utils.logger import logger


class TabRefreshHelper:
    """
    Helper pour gérer le rafraîchissement automatique des widgets lors du changement d'onglet
    """
    
    def __init__(self, tab_widget, config_provider, conductor, database=None):
        """
        Initialise le helper de rafraîchissement
        
        Args:
            tab_widget (QTabWidget): Le widget d'onglets à surveiller
            config_provider: Le fournisseur de configuration
            conductor: Le conducteur principal
            database: La base de données (optionnel)
        """
        self.tab_widget = tab_widget
        self.config_provider = config_provider
        self.conductor = conductor
        self.database = database
        
        # Dictionnaire pour stocker les widgets et leurs méthodes de rafraîchissement
        self.refreshable_widgets = {}
        
        # Connecter le signal de changement d'onglet
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
        logger.info("TabRefreshHelper initialisé")

    def register_widget(self, index, widget, label):
        """
        Enregistre un widget pour le rafraîchissement automatique
        
        Args:
            index (int): Index de l'onglet
            widget: Le widget à enregistrer
            label (str): Libellé de l'onglet
        """
        refresh_methods = []
        
        # Détecter les méthodes de rafraîchissement disponibles
        if hasattr(widget, 'refresh'):
            refresh_methods.append('refresh')
        if hasattr(widget, 'set_profiles'):
            refresh_methods.append('set_profiles')
        if hasattr(widget, 'reload_data'):
            refresh_methods.append('reload_data')
        if hasattr(widget, 'update_data'):
            refresh_methods.append('update_data')
            
        if refresh_methods:
            self.refreshable_widgets[index] = {
                'widget': widget,
                'methods': refresh_methods,
                'label': label,
                'last_refresh': 0
            }
            logger.debug(f"Widget '{label}' enregistré pour rafraîchissement avec méthodes: {refresh_methods}")
        else:
            logger.debug(f"Widget '{label}' n'a pas de méthodes de rafraîchissement")

    def _on_tab_changed(self, index):
        """
        Gestionnaire appelé lors du changement d'onglet
        
        Args:
            index (int): Index de l'onglet nouvellement sélectionné
        """
        if index < 0:
            return
            
        try:
            tab_label = self.tab_widget.tabText(index)
            logger.debug(f"Changement vers l'onglet {index}: '{tab_label}'")
            
            # Rafraîchir le widget de l'onglet sélectionné
            self._refresh_widget(index)
            
        except Exception as e:
            logger.error(f"Erreur lors du changement d'onglet {index}: {str(e)}")

    def _refresh_widget(self, index):
        """
        Rafraîchit un widget spécifique
        
        Args:
            index (int): Index de l'onglet à rafraîchir
        """
        if index not in self.refreshable_widgets:
            return
            
        widget_info = self.refreshable_widgets[index]
        widget = widget_info['widget']
        methods = widget_info['methods']
        label = widget_info['label']
        
        try:
            logger.debug(f"Rafraîchissement du widget '{label}'...")
            
            # 1. Récupérer les profils mis à jour depuis la base de données
            updated_profiles = self._get_updated_profiles()
            
            # 2. Appeler les méthodes de rafraîchissement dans l'ordre de priorité
            refresh_success = False
            
            if 'set_profiles' in methods and updated_profiles:
                logger.debug(f"Appel de set_profiles pour '{label}'")
                widget.set_profiles(updated_profiles)
                refresh_success = True
                
            if 'refresh' in methods:
                logger.debug(f"Appel de refresh pour '{label}'")
                widget.refresh()
                refresh_success = True
                
            if 'reload_data' in methods:
                logger.debug(f"Appel de reload_data pour '{label}'")
                widget.reload_data()
                refresh_success = True
                
            if 'update_data' in methods:
                logger.debug(f"Appel de update_data pour '{label}'")
                widget.update_data()
                refresh_success = True
            
            if refresh_success:
                widget_info['last_refresh'] = QtCore.QDateTime.currentMSecsSinceEpoch()
                logger.info(f"Widget '{label}' rafraîchi avec succès")
            else:
                logger.warning(f"Aucune méthode de rafraîchissement appelée pour '{label}'")
                
        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement du widget '{label}': {str(e)}")

    def _get_updated_profiles(self):
        """
        Récupère les profils mis à jour depuis la base de données
        
        Returns:
            dict: Profils mis à jour ou None si erreur
        """
        try:
            # Essayer d'abord avec la base de données
            if self.database and hasattr(self.database, 'get_all_platforms'):
                db_profiles = self.database.get_all_platforms()
                if db_profiles:
                    logger.debug(f"Profils récupérés depuis la base de données: {len(db_profiles)} plateformes")
                    return db_profiles
            
            # Fallback sur le config_provider
            if self.config_provider and hasattr(self.config_provider, 'get_profiles'):
                config_profiles = self.config_provider.get_profiles()
                if config_profiles:
                    logger.debug(f"Profils récupérés depuis config_provider: {len(config_profiles)} plateformes")
                    return config_profiles
            
            # Fallback sur le conductor
            if self.conductor and hasattr(self.conductor, 'config_provider'):
                conductor_profiles = self.conductor.config_provider.get_profiles()
                if conductor_profiles:
                    logger.debug(f"Profils récupérés depuis conductor: {len(conductor_profiles)} plateformes")
                    return conductor_profiles
            
            logger.warning("Aucune source de profils disponible")
            return {}
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des profils: {str(e)}")
            return {}

    def force_refresh_all(self):
        """
        Force le rafraîchissement de tous les widgets enregistrés
        """
        logger.info("Rafraîchissement forcé de tous les widgets")
        
        for index in self.refreshable_widgets:
            self._refresh_widget(index)

    def force_refresh_widget(self, index):
        """
        Force le rafraîchissement d'un widget spécifique
        
        Args:
            index (int): Index de l'onglet à rafraîchir
        """
        if index in self.refreshable_widgets:
            label = self.refreshable_widgets[index]['label']
            logger.info(f"Rafraîchissement forcé du widget '{label}'")
            self._refresh_widget(index)
        else:
            logger.warning(f"Widget à l'index {index} non trouvé pour rafraîchissement forcé")

    def get_registered_widgets(self):
        """
        Retourne la liste des widgets enregistrés
        
        Returns:
            dict: Informations sur les widgets enregistrés
        """
        return {
            index: {
                'label': info['label'],
                'methods': info['methods'],
                'last_refresh': info['last_refresh']
            }
            for index, info in self.refreshable_widgets.items()
        }


class AutoRefreshTabWidget(QtWidgets.QTabWidget):
    """
    QTabWidget avec rafraîchissement automatique intégré
    """
    
    def __init__(self, config_provider, conductor, database=None, parent=None):
        super().__init__(parent)
        
        # Initialiser le helper de rafraîchissement
        self.refresh_helper = TabRefreshHelper(self, config_provider, conductor, database)
        
        logger.info("AutoRefreshTabWidget initialisé")

    def addTab(self, widget, label):
        """
        Ajoute un onglet avec enregistrement automatique pour le rafraîchissement
        
        Args:
            widget: Le widget à ajouter
            label: Le libellé de l'onglet
            
        Returns:
            int: Index de l'onglet ajouté
        """
        index = super().addTab(widget, label)
        
        # Enregistrer le widget pour le rafraîchissement
        self.refresh_helper.register_widget(index, widget, label)
        
        return index

    def force_refresh_all(self):
        """
        Force le rafraîchissement de tous les onglets
        """
        self.refresh_helper.force_refresh_all()

    def force_refresh_current(self):
        """
        Force le rafraîchissement de l'onglet actuellement sélectionné
        """
        current_index = self.currentIndex()
        self.refresh_helper.force_refresh_widget(current_index)


def add_refresh_to_existing_tabs(tab_widget, config_provider, conductor, database=None):
    """
    Fonction utilitaire pour ajouter le rafraîchissement à des onglets existants
    
    Args:
        tab_widget (QTabWidget): Widget d'onglets existant
        config_provider: Fournisseur de configuration  
        conductor: Conducteur principal
        database: Base de données (optionnel)
    
    Returns:
        TabRefreshHelper: Le helper créé
    """
    # Créer et configurer le helper
    refresh_helper = TabRefreshHelper(tab_widget, config_provider, conductor, database)
    
    # Enregistrer tous les widgets existants
    for i in range(tab_widget.count()):
        widget = tab_widget.widget(i)
        label = tab_widget.tabText(i)
        refresh_helper.register_widget(i, widget, label)
    
    logger.info(f"Rafraîchissement automatique ajouté à {tab_widget.count()} onglets")
    return refresh_helper
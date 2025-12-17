#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fichier d'intégration de base de données pour Dataset Manager
À placer dans utils/ à côté de dataset_database.py
Usage: from utils.database_integration import setup_database_for_application
"""

import logging
import os
import sys
import shutil
from datetime import datetime

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_database(db_path="data/liris.db"):
    """
    Initialise la base de données
    
    Args:
        db_path: Chemin vers le fichier de base de données
        
    Returns:
        DatasetDatabase: Instance initialisée ou None
    """
    try:
        from utils.dataset_database import DatasetDatabase
        
        logger.info(f"Initialisation de la base de données: {db_path}")
        
        # Créer le répertoire data
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else "data", exist_ok=True)
        
        # Initialiser
        database = DatasetDatabase(db_path)
        
        # Tester la connexion
        if database.test_connection():
            logger.info("✓ Connexion réussie")
            return database
        else:
            logger.error("✗ Échec de connexion")
            return None
            
    except Exception as e:
        logger.error(f"Erreur initialisation: {str(e)}")
        return None


def migrate_database(database):
    """
    Effectue les migrations nécessaires
    
    Args:
        database: Instance de DatasetDatabase
        
    Returns:
        bool: True si succès
    """
    try:
        logger.info("Vérification des migrations...")
        
        cursor = database.connection.cursor()
        cursor.execute("PRAGMA table_info(projects)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        expected_columns = ['id', 'name', 'description', 'data', 'created_at', 'updated_at']
        missing_columns = [col for col in expected_columns if col not in column_names]
        
        if missing_columns:
            logger.warning(f"Colonnes manquantes: {missing_columns}")
            logger.info("Recréation de la table...")
            
            # Sauvegarder données
            cursor.execute("SELECT * FROM projects")
            existing_data = cursor.fetchall()
            
            # Recréer table
            cursor.execute("DROP TABLE IF EXISTS projects")
            cursor.execute('''
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Restaurer données
            if existing_data:
                logger.info(f"Restauration de {len(existing_data)} projets...")
                for row in existing_data:
                    try:
                        cursor.execute(
                            "INSERT INTO projects (name, description, data) VALUES (?, ?, ?)",
                            (row[1] if len(row) > 1 else '', 
                             row[2] if len(row) > 2 else '', 
                             row[3] if len(row) > 3 else '{}')
                        )
                    except:
                        pass
            
            database.connection.commit()
            logger.info("✓ Migration terminée")
        else:
            logger.info("✓ Structure à jour")
            
        return True
        
    except Exception as e:
        logger.error(f"Erreur migration: {str(e)}")
        return False


def verify_database_integrity(self):
    """
    ✅ NOUVEAU: Vérifie l'intégrité de la base de données
    Retourne un rapport de diagnostic
    """
    report = {
        'status': 'ok',
        'issues': [],
        'statistics': {}
    }
    
    try:
        cursor = self.connection.cursor()
        
        # 1. Vérifier le nombre de générations
        cursor.execute("SELECT COUNT(*) as count FROM dataset_generations")
        total = cursor.fetchone()['count']
        report['statistics']['total_generations'] = total
        
        # 2. Vérifier les projets orphelins
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM dataset_generations 
            WHERE project_id NOT IN (SELECT id FROM projects)
        """)
        orphans = cursor.fetchone()['count']
        if orphans > 0:
            report['issues'].append(f"{orphans} génération(s) avec projet inexistant")
            report['status'] = 'warning'
        
        # 3. Vérifier les métadonnées invalides
        cursor.execute("SELECT id, metadata FROM dataset_generations")
        invalid_metadata = 0
        for row in cursor.fetchall():
            if row['metadata']:
                try:
                    json.loads(row['metadata'])
                except json.JSONDecodeError:
                    invalid_metadata += 1
        
        if invalid_metadata > 0:
            report['issues'].append(f"{invalid_metadata} métadonnées JSON invalides")
            report['status'] = 'warning'
        
        report['statistics']['invalid_metadata'] = invalid_metadata
        
        # 4. Statistiques par statut
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM dataset_generations 
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        report['statistics']['by_status'] = status_counts
        
        # 5. Vérifier les champs NULL importants
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM dataset_generations 
            WHERE project_name IS NULL OR project_name = ''
        """)
        null_projects = cursor.fetchone()['count']
        if null_projects > 0:
            report['issues'].append(f"{null_projects} génération(s) sans nom de projet")
            report['status'] = 'error'
        
        logger.info("\n" + "="*80)
        logger.info("🔍 DIAGNOSTIC BASE DE DONNÉES")
        logger.info("="*80)
        logger.info(f"Statut: {report['status'].upper()}")
        logger.info(f"\n📊 Statistiques:")
        logger.info(f"  • Total générations: {total}")
        logger.info(f"  • Métadonnées invalides: {invalid_metadata}")
        logger.info(f"  • Projets orphelins: {orphans}")
        logger.info(f"  • Projets NULL: {null_projects}")
        
        if status_counts:
            logger.info(f"\n📈 Par statut:")
            for status, count in status_counts.items():
                logger.info(f"  • {status}: {count}")
        
        if report['issues']:
            logger.warning(f"\n⚠️  Problèmes détectés:")
            for issue in report['issues']:
                logger.warning(f"  • {issue}")
        else:
            logger.info("\n✅ Aucun problème détecté")
        
        logger.info("="*80 + "\n")
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Erreur diagnostic: {e}")
        logger.error(traceback.format_exc())
        report['status'] = 'error'
        report['issues'].append(f"Erreur diagnostic: {str(e)}")
        return report


def get_database_statistics(database):
    """
    Récupère les statistiques
    
    Args:
        database: Instance de DatasetDatabase
        
    Returns:
        dict: Statistiques
    """
    try:
        cursor = database.connection.cursor()
        
        stats = {}
        
        # Nombre de projets
        cursor.execute("SELECT COUNT(*) FROM projects")
        stats['total_projects'] = cursor.fetchone()[0]
        
        # Nombre de plateformes
        try:
            cursor.execute("SELECT COUNT(*) FROM platforms")
            stats['total_platforms'] = cursor.fetchone()[0]
        except:
            stats['total_platforms'] = 0
        
        # Taille
        db_size = os.path.getsize(database.db_path) if os.path.exists(database.db_path) else 0
        stats['database_size_mb'] = round(db_size / (1024 * 1024), 2)
        
        # Projet récent
        cursor.execute("SELECT name, created_at FROM projects ORDER BY created_at DESC LIMIT 1")
        recent = cursor.fetchone()
        if recent:
            stats['most_recent_project'] = {
                'name': recent[0],
                'created_at': recent[1]
            }
        
        logger.info(f"Statistiques: {stats['total_projects']} projets, "
                   f"{stats['total_platforms']} plateformes, "
                   f"{stats['database_size_mb']} MB")
        
        return stats
        
    except Exception as e:
        logger.error(f"Erreur statistiques: {str(e)}")
        return {}


def backup_database(database, backup_dir="backups"):
    """
    Crée une sauvegarde
    
    Args:
        database: Instance de DatasetDatabase
        backup_dir: Répertoire de sauvegarde
        
    Returns:
        str: Chemin de la sauvegarde ou None
    """
    try:
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"liris_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        shutil.copy2(database.db_path, backup_path)
        
        logger.info(f"✓ Sauvegarde créée: {backup_path}")
        return backup_path
        
    except Exception as e:
        logger.error(f"Erreur sauvegarde: {str(e)}")
        return None


def restore_database(database, backup_path):
    """
    Restaure depuis une sauvegarde
    
    Args:
        database: Instance de DatasetDatabase
        backup_path: Chemin vers la sauvegarde
        
    Returns:
        bool: True si succès
    """
    try:
        if not os.path.exists(backup_path):
            logger.error(f"Sauvegarde introuvable: {backup_path}")
            return False
        
        # Fermer connexion
        database.close()
        
        # Créer backup préventif
        current_backup = backup_database(database, "backups/before_restore")
        if current_backup:
            logger.info(f"Backup préventif: {current_backup}")
        
        # Restaurer
        shutil.copy2(backup_path, database.db_path)
        
        # Réinitialiser connexion
        database._init_connection()
        
        logger.info(f"✓ Base restaurée depuis: {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Erreur restauration: {str(e)}")
        return False


def cleanup_old_backups(backup_dir="backups", keep_last=10):
    """
    Nettoie les anciennes sauvegardes
    
    Args:
        backup_dir: Répertoire des sauvegardes
        keep_last: Nombre à conserver
        
    Returns:
        int: Nombre de fichiers supprimés
    """
    try:
        if not os.path.exists(backup_dir):
            return 0
        
        backups = [f for f in os.listdir(backup_dir) 
                   if f.startswith("liris_backup_") and f.endswith(".db")]
        
        if len(backups) <= keep_last:
            logger.info(f"Aucun nettoyage nécessaire ({len(backups)} sauvegardes)")
            return 0
        
        backups.sort(reverse=True)
        
        deleted = 0
        for backup in backups[keep_last:]:
            backup_path = os.path.join(backup_dir, backup)
            os.remove(backup_path)
            deleted += 1
            logger.info(f"Sauvegarde supprimée: {backup}")
        
        logger.info(f"✓ {deleted} anciennes sauvegardes supprimées")
        return deleted
        
    except Exception as e:
        logger.error(f"Erreur nettoyage: {str(e)}")
        return 0


def setup_database_for_application():
    """
    Configuration complète de la base de données
    À appeler au démarrage de l'application
    
    Returns:
        DatasetDatabase: Instance configurée ou None
    """
    logger.info("=" * 60)
    logger.info("INITIALISATION DE LA BASE DE DONNÉES")
    logger.info("=" * 60)
    
    # 1. Initialiser
    database = initialize_database()
    if not database:
        logger.error("Impossible d'initialiser la base de données")
        return None
    
    # 2. Migrer
    if not migrate_database(database):
        logger.warning("Les migrations ont échoué")
    
    # 3. Vérifier intégrité
    if not verify_database_integrity(database):
        logger.warning("Problème d'intégrité détecté")
        
        # Tenter recréation
        logger.info("Tentative de recréation...")
        if database.force_recreate_database():
            logger.info("✓ Base recréée")
        else:
            logger.error("✗ Échec recréation")
    
    # 4. Statistiques
    stats = get_database_statistics(database)
    
    # 5. Sauvegarde auto
    backup_path = backup_database(database)
    if backup_path:
        logger.info(f"Sauvegarde auto créée: {backup_path}")
    
    # 6. Nettoyage
    cleanup_old_backups()
    
    logger.info("=" * 60)
    logger.info("BASE DE DONNÉES PRÊTE")
    logger.info("=" * 60)
    
    return database


# Point d'entrée pour tests
if __name__ == "__main__":
    print("Test d'intégration de la base de données\n")
    
    db = setup_database_for_application()
    
    if db:
        print("\n✓ Base de données configurée avec succès")
        
        stats = get_database_statistics(db)
        print("\nStatistiques:")
        for key, value in stats.items():
            print(f"  - {key}: {value}")
        
        db.close()
        print("\n✓ Connexion fermée")
    else:
        print("\n✗ Échec de la configuration")
        sys.exit(1)
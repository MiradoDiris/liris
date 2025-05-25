import threading
import time
import queue
import os
import json
import pyautogui
from datetime import datetime
from utils.logger import logger
from utils.exceptions import OrchestrationError, SchedulingError
from core.vision.detector import InterfaceDetector


class AIConductor:
    """
    Chef d'orchestre pour coordonner les interactions avec les IA
    """

    def __init__(self, config_provider, scheduler, database=None):
        """
        Initialise le chef d'orchestre

        Args:
            config_provider: Fournisseur de configuration
            scheduler: Planificateur d'IA
            database (Database, optional): Connexion à la base de données
        """
        self.config_provider = config_provider
        self.scheduler = scheduler
        self.database = database

        # Initialiser le détecteur d'interface
        self.detector = InterfaceDetector()

        # Registre des tâches en cours
        self.active_tasks = {}
        self.task_counter = 0

        # File d'attente des tâches
        self.task_queue = queue.Queue()

        # Verrous pour l'accès concurrent
        self.lock = threading.RLock()

        # Flag d'arrêt
        self._shutdown = False

        # Worker thread
        self.worker_thread = None

        logger.info("Chef d'orchestre initialisé")

    def initialize(self):
        """Initialise le système"""
        try:
            # Démarrer le worker thread
            self.worker_thread = threading.Thread(target=self._worker_loop)
            self.worker_thread.daemon = True
            self.worker_thread.start()

            logger.info("Système d'orchestration initialisé")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation: {str(e)}")
            raise OrchestrationError(f"Échec de l'initialisation: {str(e)}")

    def get_available_platforms(self):
        """
        Récupère les plateformes d'IA disponibles

        Returns:
            list: Noms des plateformes disponibles
        """
        try:
            profiles = self.config_provider.get_profiles()
            available = []

            for platform_name in profiles.keys():
                can_use, _ = self.scheduler.can_use_platform(platform_name)
                if can_use:
                    available.append(platform_name)

            logger.debug(f"Plateformes disponibles: {available}")
            return available
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des plateformes: {str(e)}")
            return []

    def detect_platform_elements(self, platform_name, browser_type='Chrome', browser_path='', url='', fullscreen=False):
        """
        Détecte les éléments d'interface d'une plateforme IA dans un navigateur

        Args:
            platform_name (str): Nom de la plateforme
            browser_type (str): Type de navigateur (Chrome, Firefox, etc.)
            browser_path (str): Chemin vers l'exécutable du navigateur
            url (str): URL à ouvrir
            fullscreen (bool): Mettre en plein écran

        Returns:
            dict: Résultat de la détection
        """
        try:
            logger.info(f"Détection des éléments pour {platform_name} avec {browser_type}")

            # Récupérer le profil de la plateforme
            profile = self._get_platform_profile(platform_name)
            if not profile:
                return {
                    'success': False,
                    'error': 'platform_not_found',
                    'message': f"La plateforme {platform_name} n'existe pas"
                }

            # Lancer ou activer le navigateur
            if not self._activate_browser(browser_type, browser_path, url, fullscreen):
                return {
                    'success': False,
                    'error': 'browser_activation_failed',
                    'message': "Impossible d'activer le navigateur"
                }

            # Attendre que la page se charge
            time.sleep(3)

            # Capturer l'écran via le détecteur
            screenshot = self.detector.capture_screen()

            # Détecter les éléments d'interface via le détecteur
            interface_config = profile.get('interface', {})
            positions = self.detector.detect_interface_elements(screenshot, interface_config)

            # Valider que tous les éléments requis ont été détectés
            is_valid, missing_elements = self.detector.validate_detection(positions)

            if not is_valid:
                # Si des éléments requis sont manquants, retourner une erreur avec les positions partielles
                return {
                    'success': False,
                    'error': 'elements_not_detected',
                    'message': f"Les éléments suivants n'ont pas été détectés: {', '.join(missing_elements)}",
                    'positions': positions  # Renvoyer quand même les positions partielles
                }

            # Sauvegarder les positions détectées
            self._save_positions(platform_name, positions)

            return {
                'success': True,
                'message': "Les éléments d'interface ont été détectés avec succès",
                'positions': positions
            }

        except Exception as e:
            logger.error(f"Erreur lors de la détection des éléments: {str(e)}")
            return {
                'success': False,
                'error': 'detection_error',
                'message': str(e)
            }

    def test_platform_connection(self, platform_name, force_detection=False, browser_type='Chrome',
                                 browser_path='', url='', fullscreen=False, timeout=30):
        """
        Teste la connexion à une plateforme IA en utilisant un navigateur réel

        Args:
            platform_name (str): Nom de la plateforme
            force_detection (bool): Force la détection même si des positions sont déjà sauvegardées
            browser_type (str): Type de navigateur
            browser_path (str): Chemin vers l'exécutable du navigateur
            url (str): URL à ouvrir
            fullscreen (bool): Mettre en plein écran
            timeout (int): Délai d'attente maximum

        Returns:
            dict: Résultat du test
        """
        try:
            logger.info(f"Test de connexion pour {platform_name} avec {browser_type}")

            # Récupérer le profil de la plateforme
            profile = self._get_platform_profile(platform_name)
            if not profile:
                return {
                    'success': False,
                    'error': 'platform_not_found',
                    'message': f"La plateforme {platform_name} n'existe pas"
                }

            # Si la détection n'est pas forcée, vérifier si on a déjà les positions
            positions = None
            if not force_detection:
                positions = self._get_saved_positions(platform_name)

            # Si pas de positions ou force_detection est True, détecter les éléments
            if not positions:
                detection_result = self.detect_platform_elements(
                    platform_name,
                    browser_type=browser_type,
                    browser_path=browser_path,
                    url=url,
                    fullscreen=fullscreen
                )

                if not detection_result['success']:
                    return detection_result

                positions = detection_result['positions']

            # Si on est ici, on a les positions, tester l'interaction
            return self._test_interaction(platform_name, positions, profile, timeout)

        except Exception as e:
            logger.error(f"Erreur lors du test de connexion: {str(e)}")
            return {
                'success': False,
                'error': 'test_error',
                'message': str(e)
            }

    def _get_platform_profile(self, platform_name):
        """
        Récupère le profil complet d'une plateforme

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            dict: Profil de la plateforme ou None si non trouvée
        """
        # Essayer d'abord avec la base de données si disponible
        if self.database and hasattr(self.database, 'get_platform'):
            profile = self.database.get_platform(platform_name)
            if profile:
                return profile

        # Sinon utiliser le ConfigProvider
        profiles = self.config_provider.get_profiles()
        return profiles.get(platform_name)

    def _get_saved_positions(self, platform_name):
        """
        Récupère les positions sauvegardées pour une plateforme

        Args:
            platform_name (str): Nom de la plateforme

        Returns:
            dict: Positions sauvegardées ou None si non trouvées
        """
        # Récupérer depuis la base de données si disponible
        if self.database and hasattr(self.database, 'get_platform_positions'):
            return self.database.get_platform_positions(platform_name)

        # Sinon récupérer depuis le profil
        profile = self._get_platform_profile(platform_name)
        if profile:
            return profile.get('interface_positions')

        return None

    def _save_positions(self, platform_name, positions):
        """
        Sauvegarde les positions détectées pour une plateforme

        Args:
            platform_name (str): Nom de la plateforme
            positions (dict): Positions des éléments d'interface

        Returns:
            bool: True si la sauvegarde est réussie
        """
        # Sauvegarder dans la base de données si disponible
        if self.database and hasattr(self.database, 'save_platform_positions'):
            return self.database.save_platform_positions(platform_name, positions)

        # Sinon, ajouter au profil et sauvegarder
        profile = self._get_platform_profile(platform_name)
        if profile:
            profile['interface_positions'] = positions

            # Sauvegarder dans la base de données si disponible
            if self.database and hasattr(self.database, 'save_platform'):
                return self.database.save_platform(platform_name, profile)

            # Sinon, sauvegarder dans un fichier
            try:
                profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
                filepath = os.path.join(profiles_dir, f"{platform_name}.json")

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(profile, f, indent=2, ensure_ascii=False)

                return True
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde du profil: {str(e)}")
                return False

        return False

    def _activate_browser(self, browser_type, browser_path, url, fullscreen=False):
        """
        Active le navigateur pour la plateforme spécifiée
        """
        logger.info(f"Activation du navigateur {browser_type} pour {url}")

        try:
            # Méthode simple: utiliser os.system pour ouvrir le navigateur
            if browser_type == "Chrome":
                cmd = f"start chrome \"{url}\""
            elif browser_type == "Firefox":
                cmd = f"start firefox \"{url}\""
            elif browser_type == "Edge":
                cmd = f"start msedge \"{url}\""
            else:
                if browser_path:
                    cmd = f"start \"{browser_path}\" \"{url}\""
                else:
                    cmd = f"start {url}"

            # Exécuter la commande
            os.system(cmd)

            # Attendre que le navigateur s'ouvre
            time.sleep(3)

            # CORRECTION: Méthode plus sûre pour maximiser la fenêtre
            try:
                import pygetwindow as gw

                # Trouver la fenêtre du navigateur
                windows = gw.getWindowsWithTitle(browser_type)
                if not windows:
                    # Essayer avec des titres partiels
                    all_windows = gw.getAllWindows()
                    for window in all_windows:
                        if any(keyword in window.title.lower() for keyword in ['chrome', 'firefox', 'edge', 'mozilla']):
                            windows = [window]
                            break

                if windows:
                    browser_window = windows[0]

                    # Vérifier l'état actuel et maximiser proprement
                    if not browser_window.isMaximized:
                        browser_window.maximize()
                        time.sleep(1)
                    else:
                        # Si déjà maximisée, s'assurer qu'elle est active
                        browser_window.activate()
                        time.sleep(0.5)
                else:
                    # Fallback: utiliser Alt+Space puis X pour maximiser
                    pyautogui.hotkey('alt', 'space')
                    time.sleep(0.2)
                    pyautogui.press('x')  # Maximiser dans le menu
                    time.sleep(1)

            except ImportError:
                # Si pygetwindow n'est pas installé, utiliser la méthode fallback
                print("DEBUG: pygetwindow non disponible, utilisation de la méthode alternative")

                # Alternative plus sûre: Alt+Space puis X
                pyautogui.hotkey('alt', 'space')
                time.sleep(0.2)
                pyautogui.press('x')  # Maximiser
                time.sleep(1)

            except Exception as e:
                print(f"DEBUG: Erreur lors de la maximisation: {str(e)}")
                # En dernier recours, ne pas maximiser plutôt que de casser
                pass

            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'activation du navigateur: {str(e)}")
            return False

    def _test_interaction(self, platform_name, positions, profile, timeout):
        """
        Teste l'interaction avec la plateforme en utilisant les positions détectées

        Args:
            platform_name (str): Nom de la plateforme
            positions (dict): Positions des éléments d'interface
            profile (dict): Profil de la plateforme
            timeout (int): Délai d'attente maximum

        Returns:
            dict: Résultat du test
        """
        logger.info(f"Test d'interaction pour {platform_name}")

        try:
            # Vérifier si on doit démarrer un nouveau chat
            if 'new_chat_button' in positions:
                # Cliquer sur le bouton "Nouveau chat"
                new_chat = positions['new_chat_button']
                pyautogui.click(new_chat['center_x'], new_chat['center_y'])
                time.sleep(1)

            # Cliquer dans le champ de prompt
            prompt_field = positions['prompt_field']
            pyautogui.click(prompt_field['center_x'], prompt_field['center_y'])
            time.sleep(0.5)

            # Taper le message de test
            test_prompt = f"Ceci est un test de connexion. Veuillez répondre avec 'OK'. [Timestamp: {datetime.now().strftime('%H:%M:%S')}]"
            pyautogui.write(test_prompt)
            time.sleep(0.5)

            # Cliquer sur le bouton d'envoi
            submit_button = positions['submit_button']
            pyautogui.click(submit_button['center_x'], submit_button['center_y'])

            # Attendre et vérifier la réponse
            start_time = time.time()
            response_detected = False

            # Attendre que la réponse apparaisse
            while time.time() - start_time < timeout:
                # Attendre un peu
                time.sleep(2)

                # Vérifier si la réponse est visible (implémentation simplifiée)
                # Une vérification plus robuste utiliserait la détection d'images ou OCR
                response_detected = True
                break

            if response_detected:
                # Enregistrer le test réussi en base de données
                if self.database:
                    try:
                        session_id = self.database.create_session(platform_name)
                        prompt_id = self.database.record_prompt(session_id, test_prompt, len(test_prompt.split()),
                                                                "connection_test")
                        self.database.record_response(prompt_id, "Test de connexion réussi", "success")
                    except Exception as e:
                        logger.error(f"Erreur lors de l'enregistrement du test: {str(e)}")

                return {
                    'success': True,
                    'positions': positions,
                    'message': f"Test de connexion réussi pour {platform_name}",
                    'response_time': time.time() - start_time
                }
            else:
                return {
                    'success': False,
                    'error': 'no_response',
                    'message': f"Aucune réponse détectée dans le délai imparti",
                    'positions': positions
                }

        except Exception as e:
            logger.error(f"Erreur lors du test d'interaction: {str(e)}")
            return {
                'success': False,
                'error': 'interaction_error',
                'message': str(e),
                'positions': positions
            }

    def send_prompt(self, platform, prompt, mode="standard", priority=0, sync=False, timeout=None):
        """
        Envoie un prompt à une plateforme d'IA

        Args:
            platform (str): Nom de la plateforme
            prompt (str): Texte du prompt
            mode (str): Mode d'opération (standard, brainstorm, analyze)
            priority (int): Priorité de la tâche
            sync (bool): Mode synchrone
            timeout (float, optional): Délai maximum d'attente en mode synchrone

        Returns:
            int/dict: ID de tâche (async) ou résultat (sync)
        """
        try:
            # Vérifier la disponibilité
            can_use, reason = self.scheduler.can_use_platform(platform)
            if not can_use:
                raise SchedulingError(reason)

            # Récupérer les positions sauvegardées
            positions = self._get_saved_positions(platform)
            if not positions:
                raise OrchestrationError(f"Positions d'interface non disponibles pour {platform}")

            # Créer la tâche
            with self.lock:
                self.task_counter += 1
                task_id = self.task_counter

            task = {
                'id': task_id,
                'platform': platform,
                'prompt': prompt,
                'mode': mode,
                'priority': priority,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'timeout': timeout,
                'positions': positions
            }

            # Enregistrer la tâche
            with self.lock:
                self.active_tasks[task_id] = task

            # Mettre la tâche dans la file
            self.task_queue.put((priority, task_id))

            # Mode synchrone : attendre le résultat
            if sync:
                # Envoyer le prompt directement
                result = self._send_prompt_interactive(platform, prompt, positions, timeout)

                # Mettre à jour la tâche
                task['status'] = 'completed'
                task['result'] = result
                task['end_time'] = datetime.now().isoformat()

                return {
                    'id': task_id,
                    'status': 'completed',
                    'result': result
                }

            logger.info(f"Tâche {task_id} créée pour {platform}")
            return task_id

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du prompt: {str(e)}")
            raise OrchestrationError(f"Échec de l'envoi: {str(e)}")

    def _send_prompt_interactive(self, platform, prompt, positions, timeout=None):
        """
        Envoie un prompt à une plateforme d'IA en utilisant les interactions clavier/souris

        Args:
            platform (str): Nom de la plateforme
            prompt (str): Texte du prompt
            positions (dict): Positions des éléments d'interface
            timeout (float, optional): Délai maximum d'attente

        Returns:
            dict: Résultat de l'envoi
        """
        try:
            # Cliquer dans le champ de prompt
            prompt_field = positions['prompt_field']
            pyautogui.click(prompt_field['center_x'], prompt_field['center_y'])
            time.sleep(0.5)

            # Taper le message
            pyautogui.write(prompt)
            time.sleep(0.5)

            # Cliquer sur le bouton d'envoi
            submit_button = positions['submit_button']
            pyautogui.click(submit_button['center_x'], submit_button['center_y'])

            # Attendre et capturer la réponse
            start_time = time.time()
            max_wait = timeout if timeout else 30

            # Attendre que la réponse apparaisse
            time.sleep(2)  # Attente initiale

            # Dans une implémentation réelle, on utiliserait OCR pour lire la réponse
            # Pour cette version simplifiée, on simule une réponse
            response = f"Ceci est une réponse simulée. OK. [Timestamp: {datetime.now().strftime('%H:%M:%S')}]"

            return {
                'response': response,
                'token_count': len(prompt.split()) * 1.5,
                'duration': time.time() - start_time
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi interactif: {str(e)}")
            raise OrchestrationError(f"Échec de l'envoi interactif: {str(e)}")

    def compare_responses(self, prompt, platforms=None, mode="standard", timeout=60):
        """
        Compare les réponses de plusieurs plateformes

        Args:
            prompt (str): Prompt à envoyer
            platforms (list, optional): Liste des plateformes
            mode (str): Mode d'opération
            timeout (float): Délai maximum

        Returns:
            dict: Résultats par plateforme
        """
        try:
            if platforms is None:
                platforms = self.get_available_platforms()

            results = {}
            threads = []

            def get_response(platform):
                try:
                    # Récupérer les positions
                    positions = self._get_saved_positions(platform)
                    if not positions:
                        results[platform] = {
                            'status': 'failed',
                            'error': 'Positions non disponibles'
                        }
                        return

                    # Envoyer le prompt
                    start_time = datetime.now()
                    result = self._send_prompt_interactive(platform, prompt, positions, timeout)

                    duration = (datetime.now() - start_time).total_seconds()

                    results[platform] = {
                        'status': 'completed',
                        'duration': duration,
                        'token_count': result.get('token_count', 0),
                        'result': result
                    }
                except Exception as e:
                    results[platform] = {
                        'status': 'failed',
                        'error': str(e)
                    }

            # Créer un thread par plateforme
            for platform in platforms:
                thread = threading.Thread(target=get_response, args=(platform,))
                threads.append(thread)
                thread.start()

            # Attendre tous les threads
            for thread in threads:
                thread.join(timeout=timeout)

            return results

        except Exception as e:
            logger.error(f"Erreur lors de la comparaison: {str(e)}")
            raise OrchestrationError(f"Échec de la comparaison: {str(e)}")

    def wait_for_task(self, task_id, timeout=None):
        """
        Attend qu'une tâche soit terminée

        Args:
            task_id (int): ID de la tâche
            timeout (float, optional): Délai maximum d'attente

        Returns:
            dict: Résultat de la tâche ou None si timeout
        """
        start_time = time.time()

        while True:
            with self.lock:
                task = self.active_tasks.get(task_id)

                if not task:
                    return None

                if task['status'] in ['completed', 'failed']:
                    return task

            # Vérifier le timeout
            if timeout is not None and time.time() - start_time > timeout:
                return None

            # Attendre un peu
            time.sleep(0.1)

    def shutdown(self):
        """Arrêt propre du chef d'orchestre"""
        try:
            self._shutdown = True

            # Attendre la fin des tâches en cours
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=5)

            logger.info("Chef d'orchestre arrêté")
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt: {str(e)}")

    def _worker_loop(self):
        """Boucle du worker pour traiter les tâches"""
        while not self._shutdown:
            try:
                # Récupérer la tâche la plus prioritaire
                priority, task_id = self.task_queue.get(timeout=1)

                with self.lock:
                    task = self.active_tasks.get(task_id)

                    if not task:
                        continue

                # Traiter la tâche
                logger.debug(f"Traitement de la tâche {task_id}")

                try:
                    # Récupérer les informations nécessaires
                    platform = task['platform']
                    prompt = task['prompt']
                    positions = task.get('positions') or self._get_saved_positions(platform)

                    if not positions:
                        raise OrchestrationError(f"Positions non disponibles pour {platform}")

                    # Envoyer le prompt
                    result = self._send_prompt_interactive(platform, prompt, positions, task.get('timeout'))

                    # Mettre à jour la tâche
                    with self.lock:
                        task['status'] = 'completed'
                        task['end_time'] = datetime.now().isoformat()
                        task['result'] = result

                    # Enregistrer l'utilisation
                    self.scheduler.register_usage(platform)

                except Exception as e:
                    logger.error(f"Erreur lors du traitement de la tâche {task_id}: {str(e)}")

                    with self.lock:
                        task['status'] = 'failed'
                        task['error'] = str(e)
                        task['end_time'] = datetime.now().isoformat()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erreur dans le worker: {str(e)}")
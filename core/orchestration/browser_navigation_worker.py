from PyQt5.QtCore import QThread, pyqtSignal,  QMutex
import time
from utils.logger import logger


class BrowserNavigationWorker(QThread):
    
    # Signaux
    step_update = pyqtSignal(str, str)
    test_completed = pyqtSignal(bool, str, float, dict)
    debug_info = pyqtSignal(str)
    snippet_generated = pyqtSignal(dict)
    extraction_method = pyqtSignal(str)  # ✅ NOUVEAU: méthode utilisée
    
    def __init__(
        self, 
        platform_name: str,
        context: str,
        perimeter_data: list,
        parent=None,
        # ✅ NOUVELLES OPTIONS OPTIMISÉES
        try_clipboard: bool = True,           # Priorité clipboard
        use_playwright: bool = True,           # Fallback Playwright
        repair_code: bool = False,             # Désactivé par défaut (inutile avec clipboard)
        aggressive_repair: bool = False,       # Seulement si DOM échoue
        auto_format: bool = True              # Formatage final toujours actif
    ):
        super().__init__(parent)
        self.platform_name = platform_name
        self.context = context
        self.perimeter_data = perimeter_data
        self.start_time = None
        self.handler = None

        self._stop_requested = False
        self._mutex = QMutex()
        
        # Configuration d'extraction
        self.try_clipboard = try_clipboard
        self.use_playwright = use_playwright
        self.repair_code = repair_code
        self.aggressive_repair = aggressive_repair
        self.auto_format = auto_format
        
        # Statistiques
        self.extraction_stats = {
            'method_used': 'none',
            'clipboard_attempts': 0,
            'clipboard_success': False,
            'fallback_used': False,
            'repair_triggered': False
        }

    def is_stop_requested(self) -> bool:
        """Vérifie si l'arrêt a été demandé (thread-safe)"""
        self._mutex.lock()
        stop = self._stop_requested
        self._mutex.unlock()
        return stop
    
    def stop(self):
        """Demande l'arrêt du worker (thread-safe)"""
        logger.info("🛑 Arrêt demandé au worker")
        
        self._mutex.lock()
        self._stop_requested = True
        self._mutex.unlock()
        
        if self.handler:
            try:
                logger.info("🔌 Fermeture du handler browser...")
                self.handler.close()
            except Exception as e:
                logger.error(f"⚠️ Erreur fermeture handler: {e}")
        
        self.quit()
    
    def run(self):
        """Exécute la navigation et récupération multi-stratégies"""
        self.start_time = time.time()
        
        try:
            # ✅ CHECK 1: Avant initialisation
            if self.is_stop_requested():
                logger.info("🛑 Arrêt avant initialisation")
                self._emit_stopped()
                return
            
            self._emit_step(
                "Initialisation", 
                f"🌐 Préparation connexion à {self.platform_name}"
            )
            
            # Importer le handler
            from core.orchestration.universal_browser_handler import UniversalBrowserHandler
            
            config_msg = self._build_config_message()
            self.debug_info.emit(config_msg)
            
            # ✅ CHECK 2: Avant création handler
            if self.is_stop_requested():
                logger.info("🛑 Arrêt avant création handler")
                self._emit_stopped()
                return
            
            # Créer le handler avec configuration optimale
            self.handler = UniversalBrowserHandler(
                platform_name=self.platform_name.lower(),
                try_clipboard=self.try_clipboard,
                use_playwright=self.use_playwright,
                repair_code=self.repair_code,
                aggressive_repair=self.aggressive_repair,
                auto_format=self.auto_format
            )
            
            # ✅ CHECK 3: Avant navigation
            if self.is_stop_requested():
                logger.info("🛑 Arrêt avant navigation")
                self._emit_stopped()
                return
            
            self._emit_step(
                "Navigation", 
                f"🚀 Ouverture de {self.platform_name}"
            )
            
            # Callback de statut avec vérification stop
            def status_callback(message, progress):
                if self.is_stop_requested():
                    logger.info("🛑 Stop détecté pendant callback")
                    raise InterruptedError("Génération arrêtée par l'utilisateur")
                self._handle_status_update(message, progress)
            
            # ✅ CHECK 4: Avant envoi prompt
            if self.is_stop_requested():
                logger.info("🛑 Arrêt avant envoi prompt")
                self._emit_stopped()
                return
            
            # Envoyer le prompt (extraction automatique multi-stratégies)
            result = self.handler.send_to_platform(
                context=self.context,
                perimeter_data=self.perimeter_data,
                status_callback=status_callback
            )
            
            # ✅ CHECK 5: Après récupération résultats
            if self.is_stop_requested():
                logger.info("🛑 Arrêt après récupération résultats")
                self._emit_stopped()
                return
            
            # Analyser les résultats
            self._process_results(result)
            
        except InterruptedError as e:
            logger.info(f"🛑 Génération interrompue: {e}")
            self._emit_stopped()
            
        except ImportError as e:
            self._handle_import_error(e)
            
        except Exception as e:
            if self.is_stop_requested():
                logger.info("🛑 Exception pendant arrêt (normal)")
                self._emit_stopped()
            else:
                self._handle_error(e)

    def _emit_stopped(self):
        """Émet le signal d'arrêt"""
        duration = time.time() - self.start_time if self.start_time else 0
        self.test_completed.emit(
            False, 
            "🛑 Génération arrêtée par l'utilisateur", 
            duration, 
            {
                'stopped': True,
                'stats': self.extraction_stats
            }
        )
    
    def _build_config_message(self) -> str:
        """Construit le message de configuration"""
        config_parts = []
        
        if self.try_clipboard:
            config_parts.append("📋 Clipboard: ✅ ACTIVÉ (priorité)")
        else:
            config_parts.append("📋 Clipboard: ❌ Désactivé")
        
        if self.use_playwright:
            config_parts.append("🎭 Playwright: ✅ Fallback actif")
        else:
            config_parts.append("🎭 Playwright: ❌ Désactivé")
        
        if self.repair_code:
            mode = "AGGRESSIVE" if self.aggressive_repair else "SAFE"
            config_parts.append(f"🔧 Réparation: ✅ {mode}")
        else:
            config_parts.append("🔧 Réparation: ❌ Désactivée")
        
        if self.auto_format:
            config_parts.append("🎨 Formatage: ✅ Activé")
        
        return "🔧 Configuration: " + " | ".join(config_parts)
    
    def _handle_status_update(self, message: str, progress: int):
        """Gère les mises à jour de statut avec détection de méthode"""
        
        # ✅ Vérifier stop à chaque update
        if self.is_stop_requested():
            raise InterruptedError("Stop requested")
        
        # Détecter la méthode d'extraction utilisée
        if "CLIPBOARD" in message.upper():
            self.extraction_stats['clipboard_attempts'] += 1
            self._emit_step("📋 Extraction Clipboard", message)
            self.extraction_method.emit("clipboard")
        
        elif "PLAYWRIGHT" in message.upper():
            self.extraction_stats['fallback_used'] = True
            self._emit_step("🎭 Extraction Playwright", message)
            self.extraction_method.emit("playwright")
        
        elif "RÉPARATION" in message.upper() or "REPAIR" in message.upper():
            self.extraction_stats['repair_triggered'] = True
            self._emit_step("🔧 Réparation du code", message)
        
        elif "FORMATAGE" in message.upper():
            self._emit_step("🎨 Formatage", message)
        
        else:
            self._emit_step("Progression", f"{message} ({progress}%)")
        
        self.debug_info.emit(f"[{progress}%] {message}")
    
    def _process_results(self, result: dict):
        """Traite les résultats de l'extraction"""
        success = result['success']
        message = result['message']
        snippets = result.get('snippets', [])
        extraction_method = result.get('extraction_method', 'unknown')
        
        # Mettre à jour les stats
        self.extraction_stats['method_used'] = extraction_method
        if extraction_method == 'clipboard':
            self.extraction_stats['clipboard_success'] = True
        
        # Logger les résultats
        if snippets:
            self._log_snippets_success(snippets, extraction_method)
            
            # Émettre chaque snippet individuellement
            for idx, snippet in enumerate(snippets, 1):
                # ✅ Vérifier stop entre chaque snippet
                if self.is_stop_requested():
                    logger.info("🛑 Arrêt pendant émission snippets")
                    self._emit_stopped()
                    return
                
                self._emit_snippet_info(snippet, idx, len(snippets))
                self.snippet_generated.emit(snippet)
                time.sleep(0.2)
        else:
            self._log_snippets_failure()
        
        duration = time.time() - self.start_time
        
        # Réponse enrichie
        response = {
            'snippets': snippets,
            'platform': self.platform_name,
            'success': success,
            'raw_response': result.get('raw_response', ''),
            'extraction_method': extraction_method,
            'stats': self.extraction_stats,
            'quality_metrics': self._calculate_quality_metrics(snippets, extraction_method)
        }
        
        self.test_completed.emit(success, message, duration, response)
    
    def _log_snippets_success(self, snippets: list, method: str):
        """Log le succès de l'extraction"""
        method_emoji = {
            'clipboard': '📋',
            'playwright': '🎭',
            'playwright_clipboard': '📋🎭',
            'browseros': '🌐',
            'dom': '📄'
        }
        
        emoji = method_emoji.get(method, '✅')
        
        self.debug_info.emit(f"\n{'='*60}")
        self.debug_info.emit(f"{emoji} EXTRACTION RÉUSSIE VIA {method.upper()}")
        self.debug_info.emit(f"{'='*60}")
        self.debug_info.emit(f"✅ {len(snippets)} snippet(s) récupéré(s)")
        
        if method == 'clipboard':
            self.debug_info.emit("🏆 QUALITÉ OPTIMALE (code intact, aucune pollution DOM)")
        elif method == 'playwright':
            self.debug_info.emit("⭐ BONNE QUALITÉ (extraction DOM propre)")
        else:
            self.debug_info.emit("⚠️ QUALITÉ MOYENNE (nécessite vérification)")
        
        if self.extraction_stats['repair_triggered']:
            self.debug_info.emit("🔧 Réparation automatique appliquée")
        
        self.debug_info.emit(f"{'='*60}\n")
    
    def _log_snippets_failure(self):
        """Log l'échec de l'extraction"""
        self.debug_info.emit("\n⚠️ AUCUN SNIPPET RÉCUPÉRÉ")
        self.debug_info.emit("Suggestions:")
        
        if not self.try_clipboard:
            self.debug_info.emit("  - Activer try_clipboard=True pour améliorer l'extraction")
        
        if not self.use_playwright:
            self.debug_info.emit("  - Activer use_playwright=True pour fallback")
        
        if not self.repair_code:
            self.debug_info.emit("  - Activer repair_code=True pour récupérer code corrompu")
    
    def _emit_snippet_info(self, snippet: dict, idx: int, total: int):
        """Émet les informations d'un snippet"""
        file_name = snippet.get('file', 'N/A')
        code_length = len(snippet.get('code', ''))
        syntax_valid = snippet.get('syntax_valid', False)
        quality_score = snippet.get('quality_score', 0)
        
        status = "✅" if syntax_valid else "⚠️"
        
        self.debug_info.emit(
            f"{status} Snippet {idx}/{total}: {file_name} "
            f"({code_length} chars, qualité: {quality_score}/100)"
        )
    
    def _calculate_quality_metrics(self, snippets: list, method: str) -> dict:
        """Calcule les métriques de qualité"""
        if not snippets:
            return {
                'avg_quality': 0,
                'valid_count': 0,
                'total_count': 0,
                'success_rate': 0
            }
        
        valid_count = sum(1 for s in snippets if s.get('syntax_valid', False))
        avg_quality = sum(s.get('quality_score', 0) for s in snippets) / len(snippets)
        
        # Bonus selon la méthode
        method_bonus = {
            'clipboard': 10,
            'playwright': 5,
            'dom': 0
        }
        
        avg_quality = min(100, avg_quality + method_bonus.get(method, 0))
        
        return {
            'avg_quality': round(avg_quality, 1),
            'valid_count': valid_count,
            'total_count': len(snippets),
            'success_rate': round(100 * valid_count / len(snippets), 1)
        }
    
    def _emit_step(self, step_name: str, message: str):
        """Émet une mise à jour d'étape"""
        self.step_update.emit(step_name, message)
    
    def _handle_import_error(self, e: Exception):
        """Gère les erreurs d'import"""
        logger.error(f"❌ Handler non disponible: {e}")
        
        duration = time.time() - self.start_time
        self.test_completed.emit(
            False, 
            f"❌ Module 'universal_browser_handler' introuvable: {str(e)}", 
            duration, 
            {'stats': self.extraction_stats}
        )
    
    def _handle_error(self, e: Exception):
        """Gère les erreurs générales"""
        logger.error(f"❌ Erreur navigation: {e}")
        import traceback
        traceback.print_exc()
        
        duration = time.time() - self.start_time
        self.test_completed.emit(
            False, 
            f"❌ Erreur: {str(e)}", 
            duration, 
            {'stats': self.extraction_stats}
        )
    
    def stop(self):
        """Arrête le worker proprement"""
        if self.handler:
            try:
                self.handler.close()
            except:
                pass
        
        self.quit()
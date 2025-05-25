import cv2
import numpy as np
import pyautogui
import pytesseract
import pyperclip
import time
import os
from difflib import SequenceMatcher
from utils.logger import logger
from utils.exceptions import InterfaceDetectionError

try:
    import pygetwindow as gw

    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False
    logger.warning("pygetwindow non disponible - capture d'écran complète uniquement")


class InterfaceDetector:
    """
    Classe pour détecter les éléments d'interface utilisateur à l'aide d'OpenCV
    """

    def __init__(self, tesseract_path=None):
        """
        Initialise le détecteur d'interface

        Args:
            tesseract_path (str, optional): Chemin vers l'exécutable Tesseract OCR
        """
        logger.info("Initialisation du détecteur d'interface")

        # Configurer Tesseract si un chemin est fourni
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # Cache pour les templates
        self.template_cache = {}

        # Dernier screenshot pour éviter des captures redondantes
        self.last_screenshot = None
        self.last_screenshot_time = None
        self.last_window_title = None

    def capture_screen(self, force=False, window_title=None, browser_type=None):
        """
        Capture l'écran actuel ou une fenêtre spécifique

        Args:
            force (bool): Force une nouvelle capture même si une récente existe
            window_title (str, optional): Titre de la fenêtre à capturer
            browser_type (str, optional): Type de navigateur ('Chrome', 'Firefox', 'Edge')

        Returns:
            numpy.ndarray: Image capturée au format BGR
        """
        try:
            # Vérifier si on peut réutiliser la dernière capture
            current_time = time.time()
            if (not force and self.last_screenshot is not None and
                    self.last_screenshot_time is not None and
                    current_time - self.last_screenshot_time < 0.5 and
                    self.last_window_title == window_title):
                return self.last_screenshot

            screenshot = None

            # Essayer de capturer une fenêtre spécifique si demandé
            if (window_title or browser_type) and HAS_PYGETWINDOW:
                screenshot = self._capture_window(window_title, browser_type)

            # Fallback vers capture d'écran complète
            if screenshot is None:
                logger.info("Capture d'écran complète (fenêtre spécifique non trouvée)")
                screenshot = pyautogui.screenshot()
                screenshot = np.array(screenshot)

            # Convertir en format OpenCV
            if len(screenshot.shape) == 3 and screenshot.shape[2] == 3:
                # Déjà en BGR
                pass
            else:
                # RGB vers BGR
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)

            # Mettre en cache
            self.last_screenshot = screenshot
            self.last_screenshot_time = current_time
            self.last_window_title = window_title

            return screenshot

        except Exception as e:
            logger.error(f"Erreur lors de la capture d'écran: {str(e)}")
            raise InterfaceDetectionError(f"Échec de la capture d'écran: {str(e)}")

    def _capture_window(self, window_title=None, browser_type=None):
        """
        Capture une fenêtre spécifique

        Args:
            window_title (str, optional): Titre exact de la fenêtre
            browser_type (str, optional): Type de navigateur à chercher

        Returns:
            numpy.ndarray: Image de la fenêtre ou None si non trouvée
        """
        if not HAS_PYGETWINDOW:
            return None

        try:
            target_window = None

            # Chercher par titre exact
            if window_title:
                windows = gw.getWindowsWithTitle(window_title)
                if windows:
                    target_window = windows[0]

            # Chercher par type de navigateur
            elif browser_type:
                browser_keywords = {
                    'Chrome': ['chrome', 'google chrome'],
                    'Firefox': ['firefox', 'mozilla firefox'],
                    'Edge': ['edge', 'microsoft edge']
                }

                keywords = browser_keywords.get(browser_type, [browser_type.lower()])

                # Chercher avec mots-clés
                for keyword in keywords:
                    windows = gw.getWindowsWithTitle(keyword)
                    if windows:
                        target_window = windows[0]
                        break

                # Fallback: chercher dans toutes les fenêtres
                if not target_window:
                    all_windows = gw.getAllWindows()
                    for window in all_windows:
                        if any(keyword in window.title.lower() for keyword in keywords):
                            target_window = window
                            break

            if not target_window:
                logger.warning(f"Fenêtre non trouvée: {window_title or browser_type}")
                return None

            # Vérifier que la fenêtre est visible
            if target_window.isMinimized:
                logger.warning("La fenêtre cible est minimisée")
                return None

            # Activer la fenêtre et attendre
            target_window.activate()
            time.sleep(0.5)

            # Capturer la fenêtre
            left = target_window.left
            top = target_window.top
            width = target_window.width
            height = target_window.height

            # Vérifier les coordonnées
            if width <= 0 or height <= 0:
                logger.warning(f"Taille de fenêtre invalide: {width}x{height}")
                return None

            # Capturer la région spécifique
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            screenshot = np.array(screenshot)

            logger.info(f"Fenêtre capturée: {target_window.title} ({width}x{height})")
            return screenshot

        except Exception as e:
            logger.error(f"Erreur capture fenêtre: {str(e)}")
            return None

    def prepare_browser_capture(self, browser_type, minimize_liris=True):
        """
        Prépare la capture en s'assurant que le navigateur est visible

        Args:
            browser_type (str): Type de navigateur
            minimize_liris (bool): Minimiser Liris pour éviter les interférences

        Returns:
            bool: True si la préparation a réussi
        """
        try:
            # Minimiser Liris si demandé
            if minimize_liris and HAS_PYGETWINDOW:
                liris_windows = gw.getWindowsWithTitle("Liris")
                for window in liris_windows:
                    if not window.isMinimized:
                        window.minimize()
                        logger.info("Liris minimisé pour éviter les interférences")
                        time.sleep(0.3)

            # Activer le navigateur
            if HAS_PYGETWINDOW:
                browser_keywords = {
                    'Chrome': ['chrome', 'google chrome'],
                    'Firefox': ['firefox', 'mozilla firefox'],
                    'Edge': ['edge', 'microsoft edge']
                }

                keywords = browser_keywords.get(browser_type, [browser_type.lower()])

                for keyword in keywords:
                    windows = gw.getWindowsWithTitle(keyword)
                    if windows:
                        target_window = windows[0]
                        if target_window.isMinimized:
                            target_window.restore()
                            time.sleep(0.5)
                        target_window.activate()
                        time.sleep(0.5)
                        logger.info(f"Navigateur {browser_type} activé pour la capture")
                        return True

            logger.warning(f"Impossible d'activer le navigateur {browser_type}")
            return False

        except Exception as e:
            logger.error(f"Erreur préparation capture: {str(e)}")
            return False

    # ... [Reste des méthodes inchangées: detect_interface_elements, _detect_by_contour, etc.]

    def detect_interface_elements(self, screenshot, interface_config):
        """
        Détecte tous les éléments d'interface définis dans la configuration

        Args:
            screenshot (numpy.ndarray): Image capturée de l'écran
            interface_config (dict): Configuration des éléments d'interface

        Returns:
            dict: Positions détectées de chaque élément d'interface
        """
        positions = {}

        for element_name, element_config in interface_config.items():
            if element_name in ['prompt_field', 'submit_button', 'response_area', 'new_chat_button']:
                detection_config = element_config.get('detection', {})
                detection_method = detection_config.get('method')

                logger.debug(f"Détection de l'élément {element_name} avec la méthode {detection_method}")

                if detection_method == 'findContour':
                    contours = self._detect_by_contour(screenshot, element_config)
                    best_match = self._get_best_match(contours, element_config.get('type'))

                    if best_match:
                        positions[element_name] = {
                            'x': int(best_match['x']),
                            'y': int(best_match['y']),
                            'width': int(best_match['width']),
                            'height': int(best_match['height']),
                            'center_x': int(best_match['center_x']),
                            'center_y': int(best_match['center_y'])
                        }
                        logger.debug(f"Élément {element_name} détecté: {positions[element_name]}")
                    else:
                        logger.warning(f"Aucun contour trouvé pour l'élément {element_name}")

                elif detection_method == 'templateMatching':
                    match = self._detect_by_template(screenshot, element_config)
                    if match:
                        positions[element_name] = match
                        logger.debug(f"Élément {element_name} détecté par template: {match}")
                    else:
                        logger.warning(f"Aucune correspondance de template trouvée pour {element_name}")

                elif detection_method == 'textRecognition':
                    match = self._detect_by_text(screenshot, element_config)
                    if match:
                        positions[element_name] = match
                        logger.debug(f"Élément {element_name} détecté par texte: {match}")
                    else:
                        logger.warning(f"Aucun texte correspondant trouvé pour {element_name}")

        return positions

    def _detect_by_contour(self, image, element_config):
        """
        Détecte les éléments en utilisant la méthode findContour d'OpenCV

        Args:
            image (numpy.ndarray): Image capturée
            element_config (dict): Configuration de l'élément

        Returns:
            list: Liste des contours détectés avec leurs coordonnées
        """
        try:
            # Récupération des plages de couleurs de la configuration
            color_range = element_config.get('detection', {}).get('color_range', {})
            lower_color = np.array(color_range.get('lower', [0, 0, 0]))
            upper_color = np.array(color_range.get('upper', [255, 255, 255]))

            # Création du masque basé sur la plage de couleurs
            mask = cv2.inRange(image, lower_color, upper_color)

            # Trouver les contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Filtrer les contours par taille
            min_area = element_config.get('detection', {}).get('min_area', 100)
            filtered_contours = []

            for contour in contours:
                area = cv2.contourArea(contour)
                if area > min_area:
                    x, y, w, h = cv2.boundingRect(contour)
                    filtered_contours.append({
                        'contour': contour,
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                        'center_x': x + w // 2,
                        'center_y': y + h // 2,
                        'area': area
                    })

            logger.debug(f"Détecté {len(filtered_contours)} contours pour l'élément {element_config.get('type')}")
            return filtered_contours

        except Exception as e:
            logger.error(f"Erreur dans la détection par contour: {str(e)}")
            raise InterfaceDetectionError(f"Échec de la détection par contour: {str(e)}")

    def _detect_by_template(self, image, element_config):
        """
        Détecte les éléments en utilisant le template matching d'OpenCV

        Args:
            image (numpy.ndarray): Image capturée
            element_config (dict): Configuration de l'élément

        Returns:
            dict: Position et dimensions de l'élément trouvé ou None
        """
        try:
            detection_config = element_config.get('detection', {})
            template_path = detection_config.get('template_path')
            threshold = detection_config.get('threshold', 0.8)

            if not template_path:
                logger.error("Chemin du template non spécifié pour la détection par template")
                return None

            # Charger le template (avec cache)
            if template_path in self.template_cache:
                template = self.template_cache[template_path]
            else:
                if not os.path.exists(template_path):
                    logger.error(f"Template non trouvé: {template_path}")
                    return None

                template = cv2.imread(template_path)
                if template is None:
                    logger.error(f"Impossible de charger le template: {template_path}")
                    return None

                self.template_cache[template_path] = template

            # Obtenir les dimensions du template
            h, w = template.shape[:2]

            # Appliquer le template matching
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                x, y = max_loc
                return {
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h,
                    'center_x': x + w // 2,
                    'center_y': y + h // 2,
                    'confidence': max_val
                }

            return None

        except Exception as e:
            logger.error(f"Erreur dans la détection par template: {str(e)}")
            return None

    def _detect_by_text(self, image, element_config):
        """
        Détecte les éléments en utilisant la reconnaissance de texte (OCR)

        Args:
            image (numpy.ndarray): Image capturée
            element_config (dict): Configuration de l'élément

        Returns:
            dict: Position et dimensions de l'élément trouvé ou None
        """
        try:
            detection_config = element_config.get('detection', {})
            text_to_find = detection_config.get('text')
            ocr_config = detection_config.get('ocr_config', {})

            if not text_to_find:
                logger.error("Texte à rechercher non spécifié pour la détection par OCR")
                return None

            # Prétraiter l'image pour améliorer l'OCR si demandé
            processed_image = image.copy()

            if ocr_config.get('improve_ocr', True):
                # Convertir en niveaux de gris
                gray = cv2.cvtColor(processed_image, cv2.COLOR_BGR2GRAY)

                # Appliquer un flou gaussien pour réduire le bruit
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)

                # Appliquer un seuillage adaptatif
                thresh = cv2.adaptiveThreshold(
                    blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, 11, 2
                )

                # Dilater légèrement pour connecter les composants des caractères
                kernel = np.ones((2, 2), np.uint8)
                processed_image = cv2.dilate(thresh, kernel, iterations=1)

            # Récupérer le texte et les boîtes englobantes par OCR
            custom_config = r'--oem 3 --psm 11'
            data = pytesseract.image_to_data(processed_image, config=custom_config, output_type=pytesseract.Output.DICT)

            # Chercher le texte correspondant
            matches = []
            case_sensitive = ocr_config.get('case_sensitive', False)
            use_regex = ocr_config.get('use_regex', False)
            similarity_threshold = ocr_config.get('similarity_threshold', 0.7)

            # Pour simplifier, on utilise une recherche de similarité de chaîne
            # On pourrait implémenter la recherche regex si nécessaire
            for i in range(len(data['text'])):
                word = data['text'][i]

                if not word.strip():
                    continue

                # Comparer les textes
                if not case_sensitive:
                    word = word.lower()
                    text_compare = text_to_find.lower()
                else:
                    text_compare = text_to_find

                # Calculer la similarité
                similarity = SequenceMatcher(None, word, text_compare).ratio()

                if similarity >= similarity_threshold:
                    x = data['left'][i]
                    y = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]

                    matches.append({
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                        'center_x': x + w // 2,
                        'center_y': y + h // 2,
                        'confidence': similarity,
                        'text': word
                    })

            # Prendre le meilleur match
            if matches:
                best_match = max(matches, key=lambda x: x['confidence'])
                return best_match

            return None

        except Exception as e:
            logger.error(f"Erreur dans la détection par texte: {str(e)}")
            return None

    def _get_best_match(self, contours, target_type=None):
        """
        Retourne le meilleur contour correspondant au type d'élément cible

        Args:
            contours (list): Liste des contours détectés
            target_type (str, optional): Type d'élément recherché

        Returns:
            dict: Le meilleur contour correspondant
        """
        if not contours:
            return None

        # Tri des contours par taille
        sorted_contours = sorted(contours, key=lambda x: x['area'], reverse=True)

        if target_type == 'button':
            # Pour les boutons, privilégier les formes plus carrées
            for contour in sorted_contours:
                ratio = contour['width'] / contour['height'] if contour['height'] != 0 else 0
                if 0.5 <= ratio <= 2.0:  # Ratio largeur/hauteur entre 0.5 et 2.0
                    return contour

        # Par défaut, retourner le plus grand contour
        return sorted_contours[0]

    def validate_detection(self, positions):
        """
        Valide que tous les éléments requis ont été détectés

        Args:
            positions (dict): Positions détectées

        Returns:
            tuple: (bool, list) Si la détection est valide et liste des éléments manquants
        """
        required_elements = ['prompt_field', 'submit_button', 'response_area']
        missing_elements = [e for e in required_elements if e not in positions]

        return len(missing_elements) == 0, missing_elements

    def extract_text_from_html(self, html_content):
        """
        Parse HTML et extrait le texte pur
        Args:
            html_content (str): HTML brut copié depuis console
        Returns:
            str: Texte nettoyé
        """
        try:
            # Nettoyage initial
            if not html_content or not html_content.strip():
                return ""

            # Parser avec BeautifulSoup si disponible, sinon regex simple
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')

                # Extraire tout le texte visible
                text = soup.get_text(separator=' ', strip=True)

                # Nettoyer les espaces multiples
                import re
                text = re.sub(r'\s+', ' ', text)
                text = text.strip()

                return text

            except ImportError:
                # Fallback sans BeautifulSoup - regex simple
                import re

                # Supprimer les balises HTML
                text = re.sub(r'<[^>]+>', '', html_content)

                # Décoder les entités HTML basiques
                html_entities = {
                    '&lt;': '<', '&gt;': '>', '&amp;': '&',
                    '&quot;': '"', '&#39;': "'", '&nbsp;': ' '
                }
                for entity, char in html_entities.items():
                    text = text.replace(entity, char)

                # Nettoyer les espaces
                text = re.sub(r'\s+', ' ', text)
                text = text.strip()

                return text

        except Exception as e:
            logger.error(f"Erreur extraction HTML: {str(e)}")
            return ""

    def extract_text_from_area(self, area_position, use_clipboard=True):
        """
        Extrait le texte d'une zone spécifiée de l'écran

        Args:
            area_position (dict): Position et dimensions de la zone
            use_clipboard (bool): Utiliser le presse-papiers pour l'extraction (sinon OCR)

        Returns:
            str: Texte extrait
        """
        try:
            if use_clipboard:
                # Méthode par copier-coller (plus précise)
                x = area_position['x']
                y = area_position['y']
                width = area_position['width']
                height = area_position['height']

                # Effacer le presse-papiers actuel
                pyperclip.copy('')

                # Triple-cliquer pour sélectionner tout le texte dans la zone
                pyautogui.click(area_position['center_x'], area_position['center_y'], clicks=3)
                time.sleep(0.2)

                # Copier le texte
                pyautogui.hotkey('ctrl', 'c')
                time.sleep(0.5)  # Attendre que le texte soit copié

                # Récupérer depuis le presse-papiers
                text = pyperclip.paste()

                # Cliquer ailleurs pour désélectionner
                pyautogui.click(10, 10)

                return text
            else:
                # Méthode par OCR (moins précise)
                # Capturer l'écran
                screenshot = self.capture_screen()

                # Recadrer sur la zone de réponse
                x = area_position['x']
                y = area_position['y']
                w = area_position['width']
                h = area_position['height']

                # Vérifier que les coordonnées sont dans l'image
                if x < 0 or y < 0 or x + w > screenshot.shape[1] or y + h > screenshot.shape[0]:
                    logger.warning("Coordonnées hors limites pour l'extraction de texte")
                    return ""

                roi = screenshot[y:y + h, x:x + w]

                # Prétraiter l'image pour améliorer l'OCR
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

                # Extraire le texte
                custom_config = r'--oem 3 --psm 6'
                text = pytesseract.image_to_string(thresh, config=custom_config)

                return text

        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de texte: {str(e)}")
            return ""
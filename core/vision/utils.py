#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/core/vision/utils.py
Utilitaires pour le traitement d'images et la vision par ordinateur
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import logging

logger = logging.getLogger(__name__)


class ImageProcessingUtils:
    """Utilitaires pour le traitement d'images"""

    @staticmethod
    def resize_image(image, width, height, maintain_aspect_ratio=True):
        """
        Redimensionne une image

        Args:
            image: Image à redimensionner (numpy array ou PIL Image)
            width (int): Largeur cible
            height (int): Hauteur cible
            maintain_aspect_ratio (bool): Maintenir le ratio d'aspect

        Returns:
            Image redimensionnée
        """
        try:
            if isinstance(image, np.ndarray):
                # OpenCV format
                if maintain_aspect_ratio:
                    h, w = image.shape[:2]
                    aspect = w / h
                    if width / height > aspect:
                        width = int(height * aspect)
                    else:
                        height = int(width / aspect)
                return cv2.resize(image, (width, height))
            else:
                # PIL format
                if maintain_aspect_ratio:
                    image.thumbnail((width, height), Image.Resampling.LANCZOS)
                    return image
                else:
                    return image.resize((width, height), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.error(f"Erreur lors du redimensionnement: {str(e)}")
            return image

    @staticmethod
    def convert_to_grayscale(image):
        """
        Convertit une image en niveaux de gris

        Args:
            image: Image à convertir

        Returns:
            Image en niveaux de gris
        """
        try:
            if isinstance(image, np.ndarray):
                if len(image.shape) == 3:
                    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                return image
            else:
                return image.convert('L')
        except Exception as e:
            logger.error(f"Erreur lors de la conversion en niveaux de gris: {str(e)}")
            return image

    @staticmethod
    def apply_threshold(image, threshold=127, max_value=255, threshold_type=cv2.THRESH_BINARY):
        """
        Applique un seuillage à une image

        Args:
            image: Image à seuiller
            threshold (int): Valeur de seuil
            max_value (int): Valeur maximale
            threshold_type: Type de seuillage OpenCV

        Returns:
            Image seuillée
        """
        try:
            if isinstance(image, np.ndarray):
                gray = ImageProcessingUtils.convert_to_grayscale(image)
                _, thresholded = cv2.threshold(gray, threshold, max_value, threshold_type)
                return thresholded
            else:
                # PIL format
                gray = image.convert('L')
                return gray.point(lambda x: 255 if x > threshold else 0, mode='1')
        except Exception as e:
            logger.error(f"Erreur lors du seuillage: {str(e)}")
            return image

    @staticmethod
    def enhance_contrast(image, factor=1.5):
        """
        Améliore le contraste d'une image

        Args:
            image: Image à traiter
            factor (float): Facteur de contraste (1.0 = pas de changement)

        Returns:
            Image avec contraste amélioré
        """
        try:
            if isinstance(image, np.ndarray):
                # Conversion OpenCV vers PIL pour le traitement
                pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                enhancer = ImageEnhance.Contrast(pil_image)
                enhanced = enhancer.enhance(factor)
                # Retour en format OpenCV
                return cv2.cvtColor(np.array(enhanced), cv2.COLOR_RGB2BGR)
            else:
                enhancer = ImageEnhance.Contrast(image)
                return enhancer.enhance(factor)
        except Exception as e:
            logger.error(f"Erreur lors de l'amélioration du contraste: {str(e)}")
            return image

    @staticmethod
    def apply_gaussian_blur(image, kernel_size=(5, 5), sigma=0):
        """
        Applique un flou gaussien

        Args:
            image: Image à traiter
            kernel_size (tuple): Taille du noyau
            sigma (float): Écart-type du noyau gaussien

        Returns:
            Image floutée
        """
        try:
            if isinstance(image, np.ndarray):
                return cv2.GaussianBlur(image, kernel_size, sigma)
            else:
                return image.filter(ImageFilter.GaussianBlur(radius=kernel_size[0] // 2))
        except Exception as e:
            logger.error(f"Erreur lors de l'application du flou: {str(e)}")
            return image

    @staticmethod
    def detect_edges(image, threshold1=50, threshold2=150):
        """
        Détecte les contours avec l'algorithme de Canny

        Args:
            image: Image à traiter
            threshold1 (int): Premier seuil
            threshold2 (int): Deuxième seuil

        Returns:
            Image des contours
        """
        try:
            if isinstance(image, np.ndarray):
                gray = ImageProcessingUtils.convert_to_grayscale(image)
                return cv2.Canny(gray, threshold1, threshold2)
            else:
                # Conversion PIL vers OpenCV pour Canny
                cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, threshold1, threshold2)
                return Image.fromarray(edges)
        except Exception as e:
            logger.error(f"Erreur lors de la détection des contours: {str(e)}")
            return image

    @staticmethod
    def find_contours(image, mode=cv2.RETR_EXTERNAL, method=cv2.CHAIN_APPROX_SIMPLE):
        """
        Trouve les contours dans une image

        Args:
            image: Image binaire
            mode: Mode de récupération des contours
            method: Méthode d'approximation des contours

        Returns:
            Liste des contours
        """
        try:
            if not isinstance(image, np.ndarray):
                image = np.array(image)

            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            contours, _ = cv2.findContours(image, mode, method)
            return contours
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de contours: {str(e)}")
            return []

    @staticmethod
    def crop_image(image, x, y, width, height):
        """
        Recadre une image

        Args:
            image: Image à recadrer
            x, y (int): Coordonnées du coin supérieur gauche
            width, height (int): Dimensions du recadrage

        Returns:
            Image recadrée
        """
        try:
            if isinstance(image, np.ndarray):
                return image[y:y + height, x:x + width]
            else:
                return image.crop((x, y, x + width, y + height))
        except Exception as e:
            logger.error(f"Erreur lors du recadrage: {str(e)}")
            return image

    @staticmethod
    def convert_pil_to_cv(pil_image):
        """
        Convertit une image PIL en format OpenCV

        Args:
            pil_image: Image PIL

        Returns:
            Image au format OpenCV (numpy array)
        """
        try:
            if pil_image.mode == 'RGB':
                return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            elif pil_image.mode == 'RGBA':
                return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGBA2BGRA)
            else:
                return np.array(pil_image)
        except Exception as e:
            logger.error(f"Erreur lors de la conversion PIL vers OpenCV: {str(e)}")
            return np.array(pil_image)

    @staticmethod
    def convert_cv_to_pil(cv_image):
        """
        Convertit une image OpenCV en format PIL

        Args:
            cv_image: Image OpenCV (numpy array)

        Returns:
            Image PIL
        """
        try:
            if len(cv_image.shape) == 3:
                if cv_image.shape[2] == 3:
                    return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
                elif cv_image.shape[2] == 4:
                    return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGRA2RGBA))
            return Image.fromarray(cv_image)
        except Exception as e:
            logger.error(f"Erreur lors de la conversion OpenCV vers PIL: {str(e)}")
            return Image.fromarray(cv_image)

    @staticmethod
    def get_image_info(image):
        """
        Récupère les informations d'une image

        Args:
            image: Image à analyser

        Returns:
            dict: Informations sur l'image
        """
        try:
            if isinstance(image, np.ndarray):
                height, width = image.shape[:2]
                channels = image.shape[2] if len(image.shape) == 3 else 1
                return {
                    'width': width,
                    'height': height,
                    'channels': channels,
                    'type': 'numpy.ndarray',
                    'dtype': str(image.dtype)
                }
            else:
                return {
                    'width': image.width,
                    'height': image.height,
                    'channels': len(image.getbands()),
                    'type': 'PIL.Image',
                    'mode': image.mode
                }
        except Exception as e:
            logger.error(f"Erreur lors de la récupération d'informations: {str(e)}")
            return {}

    @staticmethod
    def normalize_image(image, min_val=0, max_val=255):
        """
        Normalise les valeurs d'une image

        Args:
            image: Image à normaliser
            min_val (int): Valeur minimale
            max_val (int): Valeur maximale

        Returns:
            Image normalisée
        """
        try:
            if isinstance(image, np.ndarray):
                normalized = cv2.normalize(image, None, min_val, max_val, cv2.NORM_MINMAX)
                return normalized.astype(np.uint8)
            else:
                # Pour PIL, on convertit en numpy, normalise, puis reconvertit
                np_image = np.array(image)
                normalized = cv2.normalize(np_image, None, min_val, max_val, cv2.NORM_MINMAX)
                return Image.fromarray(normalized.astype(np.uint8))
        except Exception as e:
            logger.error(f"Erreur lors de la normalisation: {str(e)}")
            return image

    @staticmethod
    def apply_morphology(image, operation, kernel_size=(5, 5), iterations=1):
        """
        Applique des opérations morphologiques

        Args:
            image: Image binaire
            operation: Type d'opération (cv2.MORPH_OPEN, cv2.MORPH_CLOSE, etc.)
            kernel_size (tuple): Taille du noyau
            iterations (int): Nombre d'itérations

        Returns:
            Image traitée
        """
        try:
            if not isinstance(image, np.ndarray):
                image = np.array(image)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
            return cv2.morphologyEx(image, operation, kernel, iterations=iterations)
        except Exception as e:
            logger.error(f"Erreur lors de l'opération morphologique: {str(e)}")
            return image

    @staticmethod
    def template_match(image, template, method=cv2.TM_CCOEFF_NORMED):
        """
        Recherche de motif par template matching

        Args:
            image: Image source
            template: Template à rechercher
            method: Méthode de matching

        Returns:
            Résultat du matching et coordonnées du meilleur match
        """
        try:
            if not isinstance(image, np.ndarray):
                image = np.array(image)
            if not isinstance(template, np.ndarray):
                template = np.array(template)

            result = cv2.matchTemplate(image, template, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # Pour les méthodes TM_SQDIFF et TM_SQDIFF_NORMED, le minimum est le meilleur match
            if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                best_match = min_loc
                confidence = 1 - min_val
            else:
                best_match = max_loc
                confidence = max_val

            return {
                'result': result,
                'best_match': best_match,
                'confidence': confidence,
                'template_size': template.shape[:2]
            }
        except Exception as e:
            logger.error(f"Erreur lors du template matching: {str(e)}")
            return None
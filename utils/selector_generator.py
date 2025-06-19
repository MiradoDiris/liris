#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
utils/selector_generator.py
Générateur universel COMPLET avec support THINKING + DÉTECTION + EXTRACTION
Version corrigée qui restaure le support thinking + améliorations Gemini réelles
"""

import re
from typing import Dict, List, Tuple, Optional


class UniversalSelectorGenerator:
    """
    Générateur intelligent de sélecteurs pour THINKING + DÉTECTION + EXTRACTION
    """
    
    def __init__(self):
        self.platform_patterns = {
            'claude': [
                'data-is-streaming',
                'claude-message',
                'anthropic',
                'claude.ai',
                'antml:thinking'  # 🆕 Pattern thinking
            ],
            'chatgpt': [
                'data-message-author-role="assistant"',
                'data-start',
                'data-end',
                'openai',
                'chatgpt',
                'data-testid="conversation-turn'
            ],
            'gemini': [
                'ms-text-chunk',           # ✅ Garde
                'ms-cmark-node',           # ✅ Garde  
                'ms-chat-turn',            # 🆕 AJOUTÉ - conteneur principal
                'ms-thought-chunk',        # 🆕 AJOUTÉ - thinking réel
                'ms-prompt-chunk',         # 🆕 AJOUTÉ - conteneur prompt
                '_ngcontent-ng-c',         # ✅ Garde
                'aistudio.google.com',     # ✅ Garde
                'gemini',                  # ✅ Garde
                'model-run-time-pill'      # 🆕 AJOUTÉ - indicateur temps
            ],
            'grok': [
                'response-content-markdown',
                'grok',
                'x.ai',
                'text-current'
            ],
            'deepseek': [
                'ds-markdown',
                'deepseek',
                'ds-markdown--block'
            ]
        }
        
        # 🆕 RESTAURÉ : Patterns de détection thinking
        self.thinking_patterns = {
            'claude': ['antml:thinking', 'thinking-block', 'reasoning-phase'],
            'chatgpt': ['thinking-indicator', 'o1-thinking'],  # Pour o1
            'gemini': [
                'ms-thought-chunk',              # 🆕 RÉEL - trouvé dans HTML
                'thinking-progress-icon',        # 🆕 RÉEL - icône thinking
                'thought-panel',                 # 🆕 RÉEL - panel thinking
                'mat-expansion-panel',           # 🆕 RÉEL - conteneur expandable
                'thinking-process',              # ✅ Garde (générique)
                'reasoning-step'                 # ✅ Garde (générique)
            ],
            'grok': ['thought-process', 'reasoning-mode'],
            'deepseek': ['thinking-stage', 'analysis-phase']
        }
    
    def analyze_html_and_generate_selectors(self, html_content: str) -> Dict:
        """
        🆕 RESTAURÉ : Analyse avec support thinking
        
        Returns:
            {
                'platform': 'claude|chatgpt|gemini|grok|deepseek',
                'has_thinking_phase': bool,  # 🆕 RESTAURÉ
                'thinking': {  # 🆕 RESTAURÉ
                    'selector': 'sélecteur pour phase thinking',
                    'completion_indicator': 'comment détecter fin thinking'
                } | None,
                'detection': {
                    'method': 'thinking_then_streaming|attribute_monitoring|etc',
                    'primary_selector': 'sélecteur pour détecter fin response',
                    'fallback_selectors': ['fallbacks'],
                    'script_type': 'specialized|generic'
                },
                'extraction': {
                    'primary_selector': 'sélecteur pour extraire texte final',
                    'fallback_selectors': ['fallbacks'],
                    'text_cleaning': 'méthode de nettoyage'
                }
            }
        """
        
        # 1. Détection automatique de la plateforme
        platform = self._detect_platform(html_content)
        
        # 2. 🆕 RESTAURÉ : Détection phase thinking
        has_thinking = self._detect_thinking_phase(platform, html_content)
        
        # 3. Génération des sélecteurs selon la plateforme et thinking
        if platform == 'claude':
            return self._generate_claude_selectors(html_content, has_thinking)
        elif platform == 'chatgpt':
            return self._generate_chatgpt_selectors(html_content, has_thinking)
        elif platform == 'gemini':
            return self._generate_gemini_selectors(html_content, has_thinking)
        elif platform == 'grok':
            return self._generate_grok_selectors(html_content, has_thinking)
        elif platform == 'deepseek':
            return self._generate_deepseek_selectors(html_content, has_thinking)
        else:
            return self._generate_generic_selectors(html_content, has_thinking)
    
    def _detect_platform(self, html_content: str) -> str:
        """Détecte automatiquement la plateforme basée sur les patterns HTML"""
        html_lower = html_content.lower()
        
        scores = {'claude': 0, 'chatgpt': 0, 'gemini': 0, 'grok': 0, 'deepseek': 0}
        
        for platform, patterns in self.platform_patterns.items():
            for pattern in patterns:
                if pattern.lower() in html_lower:
                    scores[platform] += 1
        
        detected = max(scores, key=scores.get)
        print(f"🔍 Plateforme détectée: {detected} (scores: {scores})")
        return detected
    
    def _detect_thinking_phase(self, platform: str, html_content: str) -> bool:
        """🆕 RESTAURÉ : Détecte si l'IA utilise une phase thinking"""
        if platform not in self.thinking_patterns:
            return False
            
        html_lower = html_content.lower()
        patterns = self.thinking_patterns[platform]
        
        for pattern in patterns:
            if pattern.lower() in html_lower:
                print(f"🧠 Phase thinking détectée: {pattern} pour {platform}")
                return True
                
        return False
    
    def _generate_claude_selectors(self, html_content: str, has_thinking: bool) -> Dict:
        """🆕 RESTAURÉ : Générateur Claude amélioré avec support thinking"""
        
        base_config = {
            'platform': 'claude',
            'has_thinking_phase': has_thinking
        }
        
        if has_thinking:
            # 🧠 CAS THINKING → RESPONSE
            base_config.update({
                'thinking': {
                    'selector': 'antml\\:thinking',
                    'completion_indicator': 'antml\\:thinking[complete="true"]',
                    'description': 'Phase de réflexion Claude'
                },
                'detection': {
                    'method': 'thinking_then_streaming',
                    'primary_selector': 'antml\\:thinking[complete="true"] ~ [data-is-streaming="false"]',
                    'fallback_selectors': [
                        '[data-is-streaming="false"]:has(+ antml\\:thinking[complete])',
                        'antml\\:thinking[complete] + .font-claude-message'
                    ],
                    'script_type': 'thinking_specialized',
                    'description': 'Attendre thinking complete PUIS streaming false'
                }
            })
        else:
            # ✅ CAS NORMAL (pas de régression)
            base_config.update({
                'thinking': None,
                'detection': {
                    'method': 'attribute_monitoring',
                    'primary_selector': '[data-is-streaming="false"]',
                    'fallback_selectors': [
                        '[data-is-streaming]',
                        '.font-claude-message',
                        'div[data-test-render-count]'
                    ],
                    'script_type': 'specialized',
                    'description': 'Surveille l\'attribut data-is-streaming'
                }
            })
        
        # Extraction reste identique
        base_config['extraction'] = {
            'primary_selector': '.font-claude-message:last-child',
            'fallback_selectors': [
                '[data-is-streaming="false"] .font-claude-message',
                'div[data-test-render-count] div:last-child',
                '.group.relative:last-child'
            ],
            'text_cleaning': 'remove_ui_elements',
            'description': 'Extrait depuis le conteneur de message Claude'
        }
        
        return base_config
    
    def _generate_chatgpt_selectors(self, html_content: str, has_thinking: bool) -> Dict:
        """🆕 RESTAURÉ : Générateur ChatGPT avec support o1 thinking"""
        
        base_config = {
            'platform': 'chatgpt',
            'has_thinking_phase': has_thinking
        }
        
        if has_thinking:
            # 🧠 CAS O1 THINKING → RESPONSE
            base_config.update({
                'thinking': {
                    'selector': '.thinking-indicator, .o1-thinking',
                    'completion_indicator': '.thinking-indicator[complete], .o1-thinking[data-complete="true"]',
                    'description': 'Phase thinking o1'
                },
                'detection': {
                    'method': 'thinking_then_data_stability',
                    'primary_selector': '.thinking-indicator[complete] ~ [data-start][data-end]',
                    'fallback_selectors': [
                        '[data-start][data-end]:not(:has(.thinking-indicator:not([complete])))',
                        '.o1-thinking[data-complete] + [data-message-author-role="assistant"]'
                    ],
                    'script_type': 'thinking_specialized',
                    'description': 'Attendre thinking complete PUIS data stability'
                }
            })
        else:
            # ✅ CAS NORMAL ChatGPT
            base_config.update({
                'thinking': None,
                'detection': {
                    'method': 'chatgpt_data_stability',
                    'primary_selector': '[data-start][data-end]',
                    'fallback_selectors': [
                        '[data-message-author-role="assistant"]:last-child [data-start]',
                        'div[data-message-id]:last-child [data-start]'
                    ],
                    'script_type': 'specialized',
                    'description': 'Surveille stabilité data-start/data-end'
                }
            })
        
        base_config['extraction'] = {
            'primary_selector': 'article[data-testid*="conversation-turn"]:last-child',
            'fallback_selectors': [
                '[data-message-author-role="assistant"]:last-child .markdown',
                'div[data-message-id]:last-child .prose'
            ],
            'text_cleaning': 'preserve_markdown_structure',
            'description': 'Extrait depuis conteneur markdown ChatGPT'
        }
        
        return base_config
    
    def _generate_gemini_selectors(self, html_content: str, has_thinking: bool) -> Dict:
        """🔧 GÉNÉRATEUR GEMINI AMÉLIORÉ basé sur HTML réel"""
        
        base_config = {
            'platform': 'gemini',
            'has_thinking_phase': has_thinking
        }
        
        if has_thinking:
            # 🧠 CAS THINKING GEMINI RÉEL
            base_config.update({
                'thinking': {
                    'selector': 'ms-thought-chunk',                           # 🆕 RÉEL
                    'completion_indicator': 'ms-thought-chunk:not(:has(.thinking-progress-icon.in-progress))',  # 🆕 RÉEL
                    'alternative_completion': 'mat-expansion-panel.thought-panel:not(:has(.in-progress))',       # 🆕 RÉEL
                    'description': 'Phase thinking Gemini réelle'
                },
                'detection': {
                    'method': 'thinking_then_element_absence',
                    'primary_selector': 'ms-thought-chunk:not(:has(.thinking-progress-icon.in-progress)) ~ ms-chat-turn:not(:has(loading-indicator))',
                    'fallback_selectors': [
                        'ms-chat-turn:has(ms-thought-chunk):not(:has(loading-indicator))',   # 🆕 Chat-turn avec thinking complete
                        'ms-chat-turn:has(.model-run-time-pill)',                           # 🆕 Présence indicateur temps = fini
                        'ms-prompt-chunk:not(:has(.thinking-progress-icon.in-progress))',   # 🆕 Prompt chunk sans thinking actif
                        'ms-text-chunk:last-child:not(:has(.in-progress))'                  # 🆕 Dernier text-chunk stable
                    ],
                    'script_type': 'thinking_specialized',
                    'description': 'Attendre thinking complete PUIS absence loading'
                }
            })
        else:
            # ✅ CAS NORMAL GEMINI (amélioré)
            base_config.update({
                'thinking': None,
                'detection': {
                    'method': 'gemini_completion_detection',
                    'primary_selector': 'ms-chat-turn:not(:has(loading-indicator)):has(.model-run-time-pill)',  # 🆕 AMÉLIORÉ
                    'fallback_selectors': [
                        'ms-chat-turn:not(:has(loading-indicator))',                     # ✅ Original
                        'ms-text-chunk:not(:has(.in-progress))',                        # ✅ Original
                        'ms-prompt-chunk:has(.model-run-time-pill)',                    # 🆕 Avec temps = fini
                        '.model-response:last-child',                                   # ✅ Original
                        'ms-chat-turn:has(.turn-footer)'                               # 🆕 Footer présent = fini
                    ],
                    'script_type': 'specialized',
                    'description': 'Surveille absence loading + présence temps exécution'
                }
            })
        
        # 🔧 EXTRACTION AMÉLIORÉE
        base_config['extraction'] = {
            'primary_selector': 'ms-text-chunk:last-child',                          # ✅ Garde
            'fallback_selectors': [
                'ms-text-chunk ms-cmark-node span.ng-star-inserted',                # ✅ Garde
                'ms-cmark-node span',                                               # ✅ Garde
                'ms-prompt-chunk ms-text-chunk:last-child',                        # 🆕 AJOUTÉ
                'ms-chat-turn .model-prompt-container ms-text-chunk:last-child'    # 🆕 AJOUTÉ
            ],
            'text_cleaning': 'gemini_enhanced_extraction',                          # 🆕 AMÉLIORÉ
            'description': 'Extrait depuis spans imbriqués Gemini avec fallbacks renforcés'
        }
        
        return base_config
    
    def _generate_grok_selectors(self, html_content: str, has_thinking: bool) -> Dict:
        """Générateur Grok (thinking potentiel futur)"""
        base_config = {
            'platform': 'grok',
            'has_thinking_phase': has_thinking,
            'thinking': None if not has_thinking else {
                'selector': '.thought-process, .reasoning-mode',
                'completion_indicator': '.thought-process[complete]',
                'description': 'Phase thinking Grok (futur)'
            }
        }
        
        method = 'thinking_then_class_absence' if has_thinking else 'class_absence'
        selector = '.thought-process[complete] ~ .response-content-markdown' if has_thinking else '.response-content-markdown:not(:has(.generating))'
        
        base_config['detection'] = {
            'method': method,
            'primary_selector': selector,
            'fallback_selectors': [
                '.response-content-markdown',
                'div[class*="response"]:not(:has(.loading))'
            ],
            'script_type': 'thinking_specialized' if has_thinking else 'specialized',
            'description': 'Surveille thinking puis absence generating' if has_thinking else 'Surveille absence generating'
        }
        
        base_config['extraction'] = {
            'primary_selector': '.response-content-markdown',
            'fallback_selectors': [
                '.response-content-markdown p:last-child'
            ],
            'text_cleaning': 'grok_text_extraction',
            'description': 'Extrait depuis conteneur markdown Grok'
        }
        
        return base_config
    
    def _generate_deepseek_selectors(self, html_content: str, has_thinking: bool) -> Dict:
        """Générateur DeepSeek (thinking potentiel futur)"""
        base_config = {
            'platform': 'deepseek',
            'has_thinking_phase': has_thinking,
            'thinking': None if not has_thinking else {
                'selector': '.thinking-stage, .analysis-phase',
                'completion_indicator': '.thinking-stage[complete]',
                'description': 'Phase thinking DeepSeek (futur)'
            }
        }
        
        method = 'thinking_then_element_stability' if has_thinking else 'element_stability'
        
        base_config['detection'] = {
            'method': method,
            'primary_selector': '.ds-markdown.ds-markdown--block',
            'fallback_selectors': [
                '.ds-markdown:last-child',
                'div[class*="ds-"]:last-child'
            ],
            'script_type': 'thinking_specialized' if has_thinking else 'specialized',
            'description': 'Surveille thinking puis stabilité' if has_thinking else 'Surveille stabilité'
        }
        
        base_config['extraction'] = {
            'primary_selector': '.ds-markdown.ds-markdown--block',
            'fallback_selectors': [
                '.ds-markdown:last-child'
            ],
            'text_cleaning': 'deepseek_text_extraction',
            'description': 'Extrait depuis conteneur markdown DeepSeek'
        }
        
        return base_config
    
    def _generate_generic_selectors(self, html_content: str, has_thinking: bool) -> Dict:
        """Générateur générique"""
        classes = re.findall(r'class="([^"]*)"', html_content)
        primary_selector = 'div'
        if classes:
            for class_list in classes:
                for class_name in class_list.split():
                    if class_name and len(class_name) > 3:
                        primary_selector = f'.{class_name}'
                        break
                if primary_selector != 'div':
                    break
        
        return {
            'platform': 'generic',
            'has_thinking_phase': has_thinking,
            'thinking': None,
            'detection': {
                'method': 'element_stability',
                'primary_selector': primary_selector,
                'fallback_selectors': [
                    'div:last-child',
                    'p:last-child'
                ],
                'script_type': 'generic',
                'description': 'Détection générique stabilité'
            },
            'extraction': {
                'primary_selector': primary_selector,
                'fallback_selectors': [
                    'div:last-child',
                    'p:last-child'
                ],
                'text_cleaning': 'basic_text_extraction',
                'description': 'Extraction générique'
            }
        }
    
    def generate_detection_script(self, detection_config: Dict) -> str:
        """🆕 RESTAURÉ : Génère script avec support thinking → response"""
        
        has_thinking = detection_config.get('has_thinking_phase', False)
        platform = detection_config.get('platform', 'generic')
        method = detection_config['detection']['method']
        
        if has_thinking:
            # 🧠 SCRIPTS THINKING → RESPONSE
            if platform == 'claude' and 'thinking_then' in method:
                return self._get_claude_thinking_script()
            elif platform == 'chatgpt' and 'thinking_then' in method:
                return self._get_chatgpt_thinking_script()
            elif platform == 'gemini' and 'thinking_then' in method:
                return self._get_gemini_thinking_script()
            else:
                return self._get_generic_thinking_script(detection_config)
        else:
            # ✅ SCRIPTS NORMAUX (pas de régression)
            if platform == 'claude':
                return self._get_claude_detection_script()
            elif platform == 'chatgpt':
                return self._get_chatgpt_detection_script()
            elif platform == 'gemini':
                return self._get_gemini_detection_script()
            elif platform == 'grok':
                return self._get_grok_detection_script()
            elif platform == 'deepseek':
                return self._get_deepseek_detection_script()
            else:
                return self._get_generic_detection_script(detection_config['detection']['primary_selector'])
    
    # 🆕 RESTAURÉ : Scripts thinking
    def _get_claude_thinking_script(self) -> str:
        """🧠 Script Claude avec thinking → streaming"""
        return '''
        (function() {
            let phase = 'waiting_thinking';
            let checkCount = 0;
            let maxChecks = 120;  // Plus long pour thinking
            
            function checkClaudeThinkingCompletion() {
                try {
                    checkCount++;
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }
                    
                    if (phase === 'waiting_thinking') {
                        // Phase 1: Attendre que thinking soit complete
                        let thinkingComplete = document.querySelector('antml\\\\:thinking[complete="true"]');
                        
                        if (thinkingComplete) {
                            console.log("Claude thinking phase complete, checking streaming...");
                            phase = 'waiting_streaming';
                        }
                    }
                    
                    if (phase === 'waiting_streaming') {
                        // Phase 2: Attendre que streaming soit false
                        let streamingElements = document.querySelectorAll('[data-is-streaming="true"]');
                        let completedElements = document.querySelectorAll('[data-is-streaming="false"]');
                        
                        if (streamingElements.length === 0 && completedElements.length > 0) {
                            console.log("LIRIS_GENERATION_COMPLETE:true");
                            return;
                        }
                    }
                    
                    setTimeout(checkClaudeThinkingCompletion, 400);
                } catch(e) {
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }
            }

            checkClaudeThinkingCompletion();
            return "Claude thinking detection started";
        })();
        '''
    
    def _get_chatgpt_thinking_script(self) -> str:
        """🧠 Script ChatGPT o1 avec thinking → response"""
        return '''
        (function() {
            let phase = 'waiting_thinking';
            let checkCount = 0;
            let maxChecks = 120;
            let lastDataState = '';
            let stableCount = 0;
            
            function checkChatGPTThinkingCompletion() {
                try {
                    checkCount++;
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }
                    
                    if (phase === 'waiting_thinking') {
                        // Phase 1: Attendre thinking complete
                        let thinkingComplete = document.querySelector('.thinking-indicator[complete], .o1-thinking[data-complete="true"]');
                        
                        if (thinkingComplete) {
                            console.log("ChatGPT thinking phase complete, checking response...");
                            phase = 'waiting_response';
                        }
                    }
                    
                    if (phase === 'waiting_response') {
                        // Phase 2: Attendre stabilité data-start/data-end
                        let elements = document.querySelectorAll('[data-start][data-end]');
                        let currentState = '';
                        elements.forEach(el => {
                            let start = el.getAttribute('data-start') || '';
                            let end = el.getAttribute('data-end') || '';
                            currentState += start + ':' + end + ';';
                        });
                        
                        if (currentState === lastDataState && currentState.length > 0) {
                            stableCount++;
                            if (stableCount >= 3) {
                                console.log("LIRIS_GENERATION_COMPLETE:true");
                                return;
                            }
                        } else {
                            lastDataState = currentState;
                            stableCount = 0;
                        }
                    }
                    
                    setTimeout(checkChatGPTThinkingCompletion, 400);
                } catch(e) {
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }
            }

            checkChatGPTThinkingCompletion();
            return "ChatGPT thinking detection started";
        })();
        '''
    
    def _get_gemini_thinking_script(self) -> str:
        """🆕 SCRIPT THINKING GEMINI basé sur HTML réel"""
        return '''
        (function() {
            let phase = 'waiting_thinking';
            let checkCount = 0;
            let maxChecks = 120;  // Thinking peut être long
            let lastContentLength = 0;
            let stableCount = 0;
            
            function checkGeminiThinkingCompletion() {
                try {
                    checkCount++;
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }
                    
                    if (phase === 'waiting_thinking') {
                        // Phase 1: Attendre que thinking soit complete
                        let thinkingChunks = document.querySelectorAll('ms-thought-chunk');
                        let thinkingInProgress = document.querySelectorAll('ms-thought-chunk .thinking-progress-icon.in-progress');
                        
                        // Thinking complete si chunks présents mais plus d'indicateur "in-progress"
                        if (thinkingChunks.length > 0 && thinkingInProgress.length === 0) {
                            console.log("Gemini thinking phase complete, checking response...");
                            phase = 'waiting_response';
                        }
                    }
                    
                    if (phase === 'waiting_response') {
                        // Phase 2: Attendre que la réponse soit stable
                        
                        // Vérifier temps d'exécution (plus fiable)
                        let timePills = document.querySelectorAll('.model-run-time-pill');
                        if (timePills.length > 0) {
                            let latestPill = timePills[timePills.length - 1];
                            let timeText = latestPill.textContent.trim();
                            if (timeText && timeText.includes('s')) {
                                console.log("LIRIS_GENERATION_COMPLETE:true (thinking + time)");
                                return;
                            }
                        }
                        
                        // Vérifier stabilité contenu
                        let textChunks = document.querySelectorAll('ms-text-chunk');
                        let currentLength = 0;
                        textChunks.forEach(chunk => {
                            currentLength += (chunk.textContent || '').length;
                        });
                        
                        let loadingIndicators = document.querySelectorAll('loading-indicator, .in-progress');
                        
                        if (loadingIndicators.length === 0 && textChunks.length > 0) {
                            if (currentLength === lastContentLength && currentLength > 100) {
                                stableCount++;
                                if (stableCount >= 3) {
                                    console.log("LIRIS_GENERATION_COMPLETE:true (thinking + stable)");
                                    return;
                                }
                            } else {
                                lastContentLength = currentLength;
                                stableCount = 0;
                            }
                        }
                    }
                    
                    setTimeout(checkGeminiThinkingCompletion, 600);
                } catch(e) {
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }
            }

            checkGeminiThinkingCompletion();
            return "Gemini thinking detection started";
        })();
        '''
    
    def _get_generic_thinking_script(self, config: Dict) -> str:
        """🧠 Script générique thinking → response"""
        thinking_selector = config.get('thinking', {}).get('selector', '.thinking')
        response_selector = config['detection']['primary_selector']
        
        return f'''
        (function() {{
            let phase = 'waiting_thinking';
            let checkCount = 0;
            let maxChecks = 100;
            let lastText = '';
            let stableCount = 0;
            
            function checkGenericThinkingCompletion() {{
                try {{
                    checkCount++;
                    
                    if (checkCount > maxChecks) {{
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }}
                    
                    if (phase === 'waiting_thinking') {{
                        // Phase 1: Attendre thinking complete
                        let thinking = document.querySelector("{thinking_selector}");
                        
                        if (!thinking || thinking.getAttribute('complete') === 'true') {{
                            console.log("Generic thinking phase complete");
                            phase = 'waiting_response';
                        }}
                    }}
                    
                    if (phase === 'waiting_response') {{
                        // Phase 2: Attendre stabilité response
                        let element = document.querySelector("{response_selector}");
                        let currentText = element ? (element.textContent || '').trim() : '';
                        
                        if (currentText === lastText && currentText.length > 30) {{
                            stableCount++;
                            if (stableCount >= 3) {{
                                console.log("LIRIS_GENERATION_COMPLETE:true");
                                return;
                            }}
                        }} else {{
                            lastText = currentText;
                            stableCount = 0;
                        }}
                    }}
                    
                    setTimeout(checkGenericThinkingCompletion, 500);
                }} catch(e) {{
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }}
            }}

            checkGenericThinkingCompletion();
            return "Generic thinking detection started";
        }})();
        '''
    
    # ✅ Scripts normaux inchangés (pas de régression)
    def _get_claude_detection_script(self) -> str:
        return '''
        (function() {
            let checkCount = 0;
            let maxChecks = 60;
            
            function checkClaudeCompletion() {
                try {
                    checkCount++;
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }
                    
                    let streamingElements = document.querySelectorAll('[data-is-streaming="true"]');
                    let completedElements = document.querySelectorAll('[data-is-streaming="false"]');
                    
                    if (streamingElements.length === 0 && completedElements.length > 0) {
                        console.log("LIRIS_GENERATION_COMPLETE:true");
                        return;
                    }
                    
                    setTimeout(checkClaudeCompletion, 300);
                } catch(e) {
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }
            }

            checkClaudeCompletion();
            return "Claude detection started";
        })();
        '''
    
    def _get_chatgpt_detection_script(self) -> str:
        return '''
        (function() {
            let lastDataState = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 60;
            
            function checkChatGPTCompletion() {
                try {
                    checkCount++;
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }
                    
                    let elements = document.querySelectorAll('[data-start][data-end]');
                    let currentState = '';
                    elements.forEach(el => {
                        let start = el.getAttribute('data-start') || '';
                        let end = el.getAttribute('data-end') || '';
                        currentState += start + ':' + end + ';';
                    });
                    
                    if (currentState === lastDataState && currentState.length > 0) {
                        stableCount++;
                        if (stableCount >= 3) {
                            console.log("LIRIS_GENERATION_COMPLETE:true");
                            return;
                        }
                    } else {
                        lastDataState = currentState;
                        stableCount = 0;
                    }
                    
                    setTimeout(checkChatGPTCompletion, 300);
                } catch(e) {
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }
            }

            checkChatGPTCompletion();
            return "ChatGPT detection started";
        })();
        '''
    
    def _get_gemini_detection_script(self) -> str:
        """🔧 SCRIPT DÉTECTION GEMINI AMÉLIORÉ"""
        return '''
        (function() {
            let checkCount = 0;
            let maxChecks = 80;  // Plus long pour Gemini
            let lastContentLength = 0;
            let stableCount = 0;
            
            function checkGeminiCompletion() {
                try {
                    checkCount++;
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }
                    
                    // 🆕 MÉTHODE 1: Vérifier présence temps exécution (le plus fiable)
                    let timePills = document.querySelectorAll('.model-run-time-pill');
                    if (timePills.length > 0) {
                        // S'il y a un temps affiché, c'est probablement fini
                        let latestPill = timePills[timePills.length - 1];
                        let timeText = latestPill.textContent.trim();
                        if (timeText && timeText.includes('s')) {
                            console.log("LIRIS_GENERATION_COMPLETE:true (time indicator)");
                            return;
                        }
                    }
                    
                    // 🆕 MÉTHODE 2: Vérifier absence d'indicateurs de chargement
                    let loadingIndicators = document.querySelectorAll(
                        'loading-indicator, .thinking-progress-icon.in-progress, .generating, .in-progress'
                    );
                    
                    // 🆕 MÉTHODE 3: Vérifier stabilité du contenu
                    let textChunks = document.querySelectorAll('ms-text-chunk');
                    let currentLength = 0;
                    textChunks.forEach(chunk => {
                        currentLength += (chunk.textContent || '').length;
                    });
                    
                    // ✅ CONDITION COMBINÉE
                    let hasContent = textChunks.length > 0;
                    let noLoading = loadingIndicators.length === 0;
                    let contentStable = currentLength === lastContentLength && currentLength > 50;
                    
                    if (hasContent && noLoading) {
                        if (contentStable) {
                            stableCount++;
                            if (stableCount >= 3) {
                                console.log("LIRIS_GENERATION_COMPLETE:true (stable content)");
                                return;
                            }
                        } else {
                            lastContentLength = currentLength;
                            stableCount = 0;
                        }
                    }
                    
                    setTimeout(checkGeminiCompletion, 500);  // Plus lent pour Gemini
                } catch(e) {
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }
            }

            checkGeminiCompletion();
            return "Enhanced Gemini detection started";
        })();
        '''
    
    def _get_grok_detection_script(self) -> str:
        return '''
        (function() {
            let checkCount = 0;
            let maxChecks = 60;
            
            function checkGrokCompletion() {
                try {
                    checkCount++;
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }
                    
                    let generatingElements = document.querySelectorAll('.generating, .loading');
                    let contentElements = document.querySelectorAll('.response-content-markdown');
                    
                    if (generatingElements.length === 0 && contentElements.length > 0) {
                        console.log("LIRIS_GENERATION_COMPLETE:true");
                        return;
                    }
                    
                    setTimeout(checkGrokCompletion, 400);
                } catch(e) {
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }
            }

            checkGrokCompletion();
            return "Grok detection started";
        })();
        '''
    
    def _get_deepseek_detection_script(self) -> str:
        return '''
        (function() {
            let lastLength = 0;
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 60;
            
            function checkDeepSeekCompletion() {
                try {
                    checkCount++;
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }
                    
                    let elements = document.querySelectorAll('.ds-markdown.ds-markdown--block');
                    let totalLength = 0;
                    
                    for (let el of elements) {
                        totalLength += (el.textContent || '').length;
                    }
                    
                    if (totalLength === lastLength && totalLength > 50) {
                        stableCount++;
                        if (stableCount >= 3) {
                            console.log("LIRIS_GENERATION_COMPLETE:true");
                            return;
                        }
                    } else {
                        lastLength = totalLength;
                        stableCount = 0;
                    }
                    
                    setTimeout(checkDeepSeekCompletion, 400);
                } catch(e) {
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }
            }

            checkDeepSeekCompletion();
            return "DeepSeek detection started";
        })();
        '''
    
    def _get_generic_detection_script(self, selector: str) -> str:
        return f'''
        (function() {{
            let lastText = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 50;
            
            function checkGenericCompletion() {{
                try {{
                    checkCount++;
                    
                    if (checkCount > maxChecks) {{
                        console.log("LIRIS_GENERATION_COMPLETE:timeout");
                        return;
                    }}
                    
                    let element = document.querySelector("{selector}");
                    let currentText = element ? (element.textContent || '').trim() : '';
                    
                    if (currentText === lastText && currentText.length > 30) {{
                        stableCount++;
                        if (stableCount >= 3) {{
                            console.log("LIRIS_GENERATION_COMPLETE:true");
                            return;
                        }}
                    }} else {{
                        lastText = currentText;
                        stableCount = 0;
                    }}
                    
                    setTimeout(checkGenericCompletion, 500);
                }} catch(e) {{
                    console.log("LIRIS_GENERATION_COMPLETE:false");
                }}
            }}

            checkGenericCompletion();
            return "Generic detection started";
        }})();
        '''


# ✅ Test avec thinking et sans thinking
def test_thinking_support():
    generator = UniversalSelectorGenerator()
    
    print("=== TEST CLAUDE SANS THINKING ===")
    claude_normal = '''<div data-is-streaming="false" class="font-claude-message">Réponse simple</div>'''
    config_normal = generator.analyze_html_and_generate_selectors(claude_normal)
    print(f"Has thinking: {config_normal['has_thinking_phase']}")
    print(f"Detection method: {config_normal['detection']['method']}")
    print(f"Primary selector: {config_normal['detection']['primary_selector']}")
    
    print("\n=== TEST CLAUDE AVEC THINKING ===")
    claude_thinking = '''<thinking complete="true">Analysons cela...</thinking><div data-is-streaming="false" class="font-claude-message">Voici ma réponse</div>'''
    config_thinking = generator.analyze_html_and_generate_selectors(claude_thinking)
    print(f"Has thinking: {config_thinking['has_thinking_phase']}")
    print(f"Thinking selector: {config_thinking['thinking']['selector']}")
    print(f"Detection method: {config_thinking['detection']['method']}")
    print(f"Primary selector: {config_thinking['detection']['primary_selector']}")

    print("\n=== TEST GEMINI THINKING RÉEL ===")
    gemini_thinking_html = '''
    <ms-chat-turn _ngcontent-ng-c4177798910="" _nghost-ng-c3182747720="" id="turn-B0E69BC4-4973-44D6-82BD-85431F1E9A09" class="ng-star-inserted">
        <ms-thought-chunk _ngcontent-ng-c1743823686="" _nghost-ng-c166611644="" class="ng-tns-c166611644-11 ng-star-inserted">
            <mat-accordion _ngcontent-ng-c166611644="" displaymode="flat" class="mat-accordion compact-accordion ng-tns-c166611644-11">
                <mat-expansion-panel _ngcontent-ng-c166611644="" class="mat-expansion-panel thought-panel">
                    <img _ngcontent-ng-c166611644="" class="thinking-progress-icon ng-tns-c166611644-11">
                </mat-expansion-panel>
            </mat-accordion>
        </ms-thought-chunk>
        <span class="model-run-time-pill"> 17,4s </span>
    </ms-chat-turn>
    '''
    config_gemini = generator.analyze_html_and_generate_selectors(gemini_thinking_html)
    print(f"Platform: {config_gemini['platform']}")
    print(f"Has thinking: {config_gemini['has_thinking_phase']}")
    if config_gemini['thinking']:
        print(f"Thinking selector: {config_gemini['thinking']['selector']}")
        print(f"Completion indicator: {config_gemini['thinking']['completion_indicator']}")
    print(f"Detection method: {config_gemini['detection']['method']}")
    print(f"Primary selector: {config_gemini['detection']['primary_selector']}")


if __name__ == "__main__":
    test_thinking_support()
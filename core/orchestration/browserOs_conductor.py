"""
browserOs_conductor.py - VERSION COMPLÈTE CORRIGÉE

Correction de TOUTES les méthodes pour gérer correctement le tabId
"""

import requests
import json
import time
from typing import Optional, Dict, Any

class BrowserOSMCPClient:
    """Client HTTP pour BrowserOS MCP Server avec gestion robuste"""
    
    def __init__(self, host="127.0.0.1", port=9100, timeout=30, max_retries=3):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        })
        self._request_id = 0
        self._initialized = False
        self._current_tab_id = None
    
    def _get_next_id(self):
        """Génère un ID unique pour chaque requête"""
        self._request_id += 1
        return self._request_id
    
    def health_check(self, timeout: int = 3) -> bool:
        """Vérifie que le serveur BrowserOS est accessible"""
        try:
            response = self.session.get(
                f"{self.base_url}/health", 
                timeout=timeout
            )
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def wait_for_server(self, max_wait: int = 10, check_interval: float = 0.5) -> bool:
        """Attend que le serveur soit disponible"""
        print(f"⏳ Attente du serveur BrowserOS ({self.base_url})...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if self.health_check(timeout=2):
                print(f"✅ Serveur BrowserOS disponible!")
                return True
            time.sleep(check_interval)
        
        print(f"❌ Serveur BrowserOS non disponible après {max_wait}s")
        return False
    
    def send_mcp_request(
        self, 
        method: str, 
        params: Optional[Dict] = None, 
        endpoint: str = "/mcp",
        timeout: Optional[int] = None,
        retry_on_failure: bool = True
    ) -> Dict[str, Any]:
        """Envoie une requête MCP JSON-RPC avec retry logic"""
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._get_next_id()
        }
        
        request_timeout = timeout or self.timeout
        retries = self.max_retries if retry_on_failure else 1
        last_error = None
        
        for attempt in range(retries):
            try:
                if attempt > 0:
                    wait_time = min(2 ** attempt, 5)
                    print(f"⏳ Retry {attempt}/{retries-1} après {wait_time}s...")
                    time.sleep(wait_time)
                
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    timeout=request_timeout
                )
                
                print(f"📡 {method} -> HTTP {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if "error" in result:
                        error_msg = result["error"].get("message", "Unknown error")
                        print(f"❌ Erreur MCP: {error_msg}")
                        last_error = error_msg
                        continue
                    
                    print(f"✅ Succès!")
                    return result
                else:
                    error_text = response.text[:200]
                    print(f"❌ Erreur HTTP {response.status_code}: {error_text}")
                    last_error = f"HTTP {response.status_code}"
                    continue
                    
            except requests.exceptions.Timeout as e:
                print(f"⏱️ Timeout après {request_timeout}s")
                last_error = f"Timeout ({request_timeout}s)"
                
            except requests.exceptions.ConnectionError as e:
                print(f"🔌 Erreur de connexion: {e}")
                last_error = f"Connection error: {str(e)}"
                
            except Exception as e:
                print(f"❌ Exception: {e}")
                last_error = str(e)
        
        return {
            "error": last_error or "Request failed",
            "details": f"Failed after {retries} attempts"
        }
    
    def get_url(self, tab_id: Optional[int] = None) -> Dict[str, Any]:
        """
        🆕 Récupère l'URL de la page active (VERSION FINALE - ROBUSTE)
    
        Returns:
            {"result": {"url": "https://...", "title": "...", "tabId": ...}}
        """
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
    
        use_tab_id = tab_id if tab_id is not None else self._current_tab_id
    
        if use_tab_id is None:
            print("⚠️  Pas de tabId, récupération du tab actif...")
            self.get_active_tab()
            use_tab_id = self._current_tab_id
    
        if use_tab_id is None:
            return {"error": "No valid tabId available"}
    
        print(f"🔗 Récupération URL (tabId={use_tab_id})...")
    
        # 🎯 STRATÉGIE 1 : Utiliser get_page_content qui retourne les métadonnées
        content_result = self.get_page_content(content_type="text", tab_id=use_tab_id)
        
        if "error" not in content_result and "result" in content_result:
            result_data = content_result["result"]
            
            # Chercher l'URL dans les métadonnées ou le contenu
            if isinstance(result_data, dict):
                # Cas 1 : URL directement dans le résultat
                if "url" in result_data:
                    return {
                        "result": {
                            "url": result_data["url"],
                            "title": result_data.get("title", ""),
                            "tabId": use_tab_id
                        }
                    }
                
                # Cas 2 : Parser le contenu
                content_list = result_data.get("content", [])
                if isinstance(content_list, list) and len(content_list) > 0:
                    first_item = content_list[0]
                    
                    if isinstance(first_item, dict) and "text" in first_item:
                        text = first_item["text"]
                        
                        # Chercher une URL dans le texte
                        import re
                        
                        # Pattern pour extraire l'URL de Claude
                        # Format attendu : https://claude.ai/chat/[uuid]
                        url_pattern = r'https://claude\.ai/chat/[a-f0-9-]+'
                        match = re.search(url_pattern, text)
                        
                        if match:
                            url = match.group(0)
                            print(f"✅ URL extraite du contenu: {url}")
                            return {
                                "result": {
                                    "url": url,
                                    "title": "",
                                    "tabId": use_tab_id
                                }
                            }
                        
                        # Fallback : Chercher n'importe quelle URL
                        general_url_pattern = r'https?://[^\s<>"\']+claude\.ai[^\s<>"\']+'
                        match = re.search(general_url_pattern, text)
                        
                        if match:
                            url = match.group(0)
                            print(f"✅ URL générique extraite: {url}")
                            return {
                                "result": {
                                    "url": url,
                                    "title": "",
                                    "tabId": use_tab_id
                                }
                            }
    
        # 🎯 STRATÉGIE 2 : Utiliser browser_get_active_tab
        print("⚠️ Fallback: Utilisation de get_active_tab")
        tab_result = self.send_mcp_request("tools/call", {
            "name": "browser_get_active_tab",
            "arguments": {}
        })
        
        if "error" not in tab_result and "result" in tab_result:
            content = tab_result["result"].get("content", [])
            
            if isinstance(content, list) and len(content) > 0:
                first = content[0]
                
                if isinstance(first, dict) and "text" in first:
                    text = first["text"]
                    
                    # Extraire URL de Claude
                    import re
                    url_pattern = r'https://claude\.ai/chat/[a-f0-9-]+'
                    match = re.search(url_pattern, text)
                    
                    if match:
                        url = match.group(0)
                        print(f"✅ URL extraite de get_active_tab: {url}")
                        return {
                            "result": {
                                "url": url,
                                "title": "",
                                "tabId": use_tab_id
                            }
                        }
    
        # 🎯 STRATÉGIE 3 : JavaScript avec wrapping explicite
        print("⚠️ Fallback: JavaScript avec wrapping")
        js_result = self.execute_javascript("""
            (function() {
                try {
                    var data = {
                        url: window.location.href,
                        pathname: window.location.pathname,
                        hostname: window.location.hostname
                    };
                    return 'URL:' + data.url;
                } catch(e) {
                    return 'ERROR:' + e.message;
                }
            })();
        """, tab_id=use_tab_id)
        
        if "error" not in js_result and "result" in js_result:
            content = js_result["result"].get("content", [])
            
            if isinstance(content, list) and len(content) > 0:
                first = content[0]
                
                if isinstance(first, dict) and "text" in first:
                    text = first["text"]
                    
                    # Parser le résultat
                    if text.startswith("URL:"):
                        url = text[4:].strip()
                        if url.startswith("http"):
                            print(f"✅ URL extraite via JS: {url}")
                            return {
                                "result": {
                                    "url": url,
                                    "title": "",
                                    "tabId": use_tab_id
                                }
                            }
    
        print("❌ Impossible d'extraire l'URL avec toutes les méthodes")
        return {"error": "Unable to extract URL from page"}

    def initialize(self, force: bool = False) -> Dict[str, Any]:
        """Initialise la connexion MCP"""
        if self._initialized and not force:
            print("ℹ️  Client déjà initialisé")
            return {"result": "already_initialized"}
        
        print("🔧 Initialisation du client MCP...")
        result = self.send_mcp_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "BrowserOS-Python-Client",
                "version": "1.0.0"
            }
        })
        
        if "error" not in result:
            self._initialized = True
            print("✅ Client MCP initialisé")
        else:
            print(f"❌ Échec d'initialisation: {result.get('error')}")
        
        return result
    
    def ensure_initialized(self) -> bool:
        """Garantit que le client est initialisé"""
        if not self._initialized:
            result = self.initialize()
            return "error" not in result
        return True
    
    def _extract_tab_id(self, result: Dict[str, Any]) -> Optional[int]:
        """Extrait le tabId depuis la réponse MCP"""
        if "result" not in result:
            return None
        
        content = result["result"].get("content", [])
        
        if isinstance(content, list) and len(content) > 0:
            first_item = content[0]
            
            if isinstance(first_item, dict):
                tab_id = first_item.get("tabId") or first_item.get("id")
                if tab_id is not None:
                    return int(tab_id)
                
                text = first_item.get("text", "")
                if text:
                    import re
                    match = re.search(r'[Tt]ab\s*ID[:\s]+(\d+)', text)
                    if match:
                        return int(match.group(1))
                    
                    try:
                        data = json.loads(text)
                        if isinstance(data, dict):
                            tab_id = data.get("tabId") or data.get("id")
                            if tab_id is not None:
                                return int(tab_id)
                    except:
                        pass
                    
            elif isinstance(first_item, str):
                try:
                    data = json.loads(first_item)
                    if isinstance(data, dict):
                        tab_id = data.get("tabId") or data.get("id")
                        if tab_id is not None:
                            return int(tab_id)
                except:
                    import re
                    match = re.search(r'[Tt]ab\s*ID[:\s]+(\d+)', first_item)
                    if match:
                        return int(match.group(1))
        
        elif isinstance(content, dict):
            tab_id = content.get("tabId") or content.get("id")
            if tab_id is not None:
                return int(tab_id)
        
        return None
    
    def navigate(self, url: str, tab_id: Optional[int] = None, wait_load: float = 2.0) -> Dict[str, Any]:
        """Navigue vers une URL"""
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
        
        args = {"url": url}
        if tab_id is not None:
            args["tabId"] = tab_id
        
        print(f"🌐 Navigation vers: {url}")
        result = self.send_mcp_request("tools/call", {
            "name": "browser_navigate",
            "arguments": args
        })
        
        if "error" not in result:
            extracted_id = self._extract_tab_id(result)
            if extracted_id is not None:
                self._current_tab_id = extracted_id
                print(f"📌 Tab ID extrait de navigate: {self._current_tab_id}")
        
        if "error" not in result and wait_load > 0:
            print(f"⏳ Attente du chargement ({wait_load}s)...")
            time.sleep(wait_load)
        
        return result
    
    def get_active_tab(self) -> Dict[str, Any]:
        """Récupère le tab actif"""
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
        
        print("🔍 Récupération du tab actif...")
        result = self.send_mcp_request("tools/call", {
            "name": "browser_get_active_tab",
            "arguments": {}
        })
        
        if "error" not in result:
            extracted_id = self._extract_tab_id(result)
            if extracted_id is not None:
                self._current_tab_id = extracted_id
                print(f"📌 Tab actif récupéré: {self._current_tab_id}")
            else:
                print(f"⚠️  Impossible d'extraire le tabId")
        
        return result
    
    def get_interactive_elements(self, max_wait: float = 5.0, tab_id: Optional[int] = None) -> Dict[str, Any]:
        """Récupère les éléments interactifs"""
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
        
        use_tab_id = tab_id if tab_id is not None else self._current_tab_id
        
        if use_tab_id is None:
            print("⚠️  Pas de tabId, récupération du tab actif...")
            self.get_active_tab()
            use_tab_id = self._current_tab_id
        
        if use_tab_id is None:
            return {"error": "No valid tabId available"}
        
        print(f"🔍 Récupération des éléments interactifs (tabId={use_tab_id})...")
        return self.send_mcp_request(
            "tools/call",
            {
                "name": "browser_get_interactive_elements",
                "arguments": {"tabId": use_tab_id}
            },
            timeout=int(max_wait)
        )
    
    def type_text(self, node_id: int, text: str, clear_first: bool = True, tab_id: Optional[int] = None) -> Dict[str, Any]:
        """Tape du texte dans un élément"""
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
        
        # 🔧 CORRECTION: Ajouter tabId
        use_tab_id = tab_id if tab_id is not None else self._current_tab_id
        
        if clear_first and use_tab_id:
            self.click_element(node_id, tab_id=use_tab_id)
            time.sleep(0.2)
            self.execute_javascript("""
                document.activeElement.select();
                document.execCommand('delete');
            """, tab_id=use_tab_id)
            time.sleep(0.2)
        
        print(f"⌨️  Saisie de texte (nodeId={node_id}): {text[:50]}...")
        
        args = {"nodeId": node_id, "text": text}
        if use_tab_id:
            args["tabId"] = use_tab_id
        
        return self.send_mcp_request("tools/call", {
            "name": "browser_type_text",
            "arguments": args
        })
    
    def click_element(self, node_id: int, tab_id: Optional[int] = None) -> Dict[str, Any]:
        """Clique sur un élément"""
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
        
        # 🔧 CORRECTION: Ajouter tabId
        use_tab_id = tab_id if tab_id is not None else self._current_tab_id
        
        print(f"🖱️  Clic sur élément (nodeId={node_id})")
        
        args = {"nodeId": node_id}
        if use_tab_id:
            args["tabId"] = use_tab_id
        
        return self.send_mcp_request("tools/call", {
            "name": "browser_click_element",
            "arguments": args
        })
    
    def execute_javascript(self, code: str, tab_id: Optional[int] = None) -> Dict[str, Any]:
        """
        🔧 CORRIGÉ: Exécute du JavaScript avec tabId
        """
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
        
        use_tab_id = tab_id if tab_id is not None else self._current_tab_id
        
        if use_tab_id is None:
            print("⚠️  Pas de tabId pour execute_javascript, récupération...")
            self.get_active_tab()
            use_tab_id = self._current_tab_id
        
        if use_tab_id is None:
            return {"error": "No valid tabId available for execute_javascript"}
        
        return self.send_mcp_request("tools/call", {
            "name": "browser_execute_javascript",
            "arguments": {
                "code": code,
                "tabId": use_tab_id  # 🔧 CRITIQUE: Ajout du tabId
            }
        })
    
    def screenshot(self, tab_id: Optional[int] = None) -> Dict[str, Any]:
        """Prend un screenshot"""
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
        
        # 🔧 CORRECTION: Ajouter tabId si nécessaire
        use_tab_id = tab_id if tab_id is not None else self._current_tab_id
        
        print("📸 Capture d'écran...")
        
        args = {}
        if use_tab_id:
            args["tabId"] = use_tab_id
        
        return self.send_mcp_request("tools/call", {
            "name": "browser_get_screenshot",
            "arguments": args
        })
    
    def get_page_content(self, content_type: str = "text", tab_id: Optional[int] = None) -> Dict[str, Any]:
        """Récupère le contenu de la page"""
        if not self.ensure_initialized():
            return {"error": "Client not initialized"}
        
        use_tab_id = tab_id if tab_id is not None else self._current_tab_id
        
        if use_tab_id is None:
            print("⚠️  Pas de tabId, récupération du tab actif...")
            self.get_active_tab()
            use_tab_id = self._current_tab_id
        
        if use_tab_id is None:
            return {"error": "No valid tabId available"}
        
        args = {
            "type": content_type,
            "tabId": use_tab_id
        }
        
        print(f"📄 Récupération du contenu (type={content_type}, tabId={use_tab_id})...")
        
        return self.send_mcp_request("tools/call", {
            "name": "browser_get_page_content",
            "arguments": args
        })
    
    def close(self):
        """Ferme proprement la session"""
        try:
            self.session.close()
            self._initialized = False
            self._current_tab_id = None
            print("✅ Session BrowserOS fermée")
        except Exception as e:
            print(f"⚠️  Erreur lors de la fermeture: {e}")
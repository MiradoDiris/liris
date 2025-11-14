import requests
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class VSCodeResponse:
    """Réponse de l'API VS Code"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    file: Optional[str] = None


class VSCodeClient:
    """Client pour communiquer avec l'extension VS Code Liris"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        """
        Initialise le client VS Code
        
        Args:
            host: Adresse du serveur (par défaut: 127.0.0.1)
            port: Port du serveur (par défaut: 9000)
        """
        self.base_url = f"http://{host}:{port}"
        self.timeout = 10  # secondes
    
    def ping(self) -> bool:
        """
        Vérifie si le serveur VS Code est accessible
        
        Returns:
            True si le serveur répond, False sinon
        """
        try:
            response = requests.get(
                f"{self.base_url}/ping",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "ok"
            return False
        except requests.exceptions.RequestException:
            return False
    
    def get_server_info(self) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations du serveur VS Code
        
        Returns:
            Dictionnaire avec les infos du serveur ou None si erreur
        """
        try:
            response = requests.get(
                f"{self.base_url}/ping",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.RequestException:
            return None
    
    def insert_code(
        self,
        file_path: str,
        code: str,
        line_number: Optional[int] = None,
        class_name: Optional[str] = None,
        method_name: Optional[str] = None
    ) -> VSCodeResponse:
        """
        Insère du code dans un fichier VS Code
        
        Args:
            file_path: Chemin relatif du fichier (ex: "src/main.py")
            code: Code à insérer
            line_number: Numéro de ligne où insérer (optionnel)
            class_name: Nom de la classe où insérer (optionnel)
            method_name: Nom de la méthode où insérer (optionnel)
        
        Returns:
            VSCodeResponse avec le résultat de l'opération
        """
        payload = {
            "action": "insert",
            "filePath": file_path,
            "code": code
        }
        
        if line_number is not None:
            payload["lineNumber"] = line_number
        if class_name:
            payload["className"] = class_name
        if method_name:
            payload["methodName"] = method_name
        
        return self._send_request(payload)
    
    def replace_code(
        self,
        file_path: str,
        target: str,
        code: str,
        class_name: Optional[str] = None,
        method_name: Optional[str] = None
    ) -> VSCodeResponse:
        """
        Remplace du code dans un fichier VS Code
        
        Args:
            file_path: Chemin relatif du fichier (ex: "src/main.py")
            target: Code à remplacer (doit être unique dans le fichier)
            code: Nouveau code
            class_name: Nom de la classe (optionnel)
            method_name: Nom de la méthode (optionnel)
        
        Returns:
            VSCodeResponse avec le résultat de l'opération
        """
        payload = {
            "action": "replace",
            "filePath": file_path,
            "target": target,
            "code": code
        }
        
        if class_name:
            payload["className"] = class_name
        if method_name:
            payload["methodName"] = method_name
        
        return self._send_request(payload)
    
    def _send_request(self, payload: Dict[str, Any]) -> VSCodeResponse:
        """
        Envoie une requête à l'API VS Code
        
        Args:
            payload: Données à envoyer
        
        Returns:
            VSCodeResponse avec le résultat
        """
        try:
            response = requests.post(
                f"{self.base_url}/update",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            data = response.json()
            
            return VSCodeResponse(
                success=data.get("success", False),
                message=data.get("message"),
                error=data.get("error"),
                file=data.get("file")
            )
            
        except requests.exceptions.Timeout:
            return VSCodeResponse(
                success=False,
                error="Timeout: Le serveur VS Code ne répond pas"
            )
        except requests.exceptions.ConnectionError:
            return VSCodeResponse(
                success=False,
                error="Erreur de connexion: VS Code n'est pas accessible"
            )
        except requests.exceptions.RequestException as e:
            return VSCodeResponse(
                success=False,
                error=f"Erreur réseau: {str(e)}"
            )
        except json.JSONDecodeError:
            return VSCodeResponse(
                success=False,
                error="Erreur: Réponse invalide du serveur"
            )


# Exemples d'utilisation
if __name__ == "__main__":
    # Créer le client
    client = VSCodeClient()
    
    # Vérifier la connexion
    print("Test de connexion à VS Code...")
    if client.ping():
        print("✅ VS Code est accessible")
        
        # Obtenir les infos du serveur
        info = client.get_server_info()
        if info:
            print(f"   Version: {info.get('version')}")
            print(f"   Workspace: {info.get('workspace')}")
    else:
        print("❌ VS Code n'est pas accessible")
        print("   Vérifiez que l'extension Liris est installée et démarrée")
        exit(1)
    
    print("\n--- Exemple 1: Insérer à la fin du fichier ---")
    response = client.insert_code(
        file_path="test.py",
        code="def hello():\n    print('Hello from Liris!')"
    )
    print(f"Succès: {response.success}")
    if response.success:
        print(f"Message: {response.message}")
    else:
        print(f"Erreur: {response.error}")
    
    print("\n--- Exemple 2: Insérer à une ligne spécifique ---")
    response = client.insert_code(
        file_path="test.py",
        code="# Commentaire ajouté par Liris",
        line_number=0
    )
    print(f"Succès: {response.success}")
    
    print("\n--- Exemple 3: Remplacer du code ---")
    response = client.replace_code(
        file_path="test.py",
        target="print('Hello from Liris!')",
        code="print('Hello from Liris - Updated!')"
    )
    print(f"Succès: {response.success}")
    
    print("\n--- Exemple 4: Insérer dans une classe ---")
    response = client.insert_code(
        file_path="src/models.py",
        code="    def new_method(self):\n        pass",
        class_name="MyClass"
    )
    print(f"Succès: {response.success}")
"""
Gerenciador Central de IAM (Identity & Access Management)
Suporta múltiplos provedores: Mock, Keycloak, Google, etc.
"""
import os
import logging
from typing import Optional, Dict, List
from fastapi import HTTPException, status, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from keycloak import KeycloakOpenID
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Configuração de Logs
logger = logging.getLogger("IAM")

# Esquema de segurança (Bearer Token)
security = HTTPBearer()

class IAMManager:
    def __init__(self):
        self.provider = os.getenv("AUTH_PROVIDER", "mock").lower()
        logger.info(f"🔐 IAM Manager inicializado. Provedor: {self.provider.upper()}")
        
        # Configurações Keycloak
        self.keycloak_url = os.getenv("KEYCLOAK_URL")
        self.keycloak_realm = os.getenv("KEYCLOAK_REALM")
        self.keycloak_client_id = os.getenv("KEYCLOAK_CLIENT_ID")
        self.keycloak_client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET")
        
        # Configurações Google
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")

    def verify_token(self, credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict:
        """
        Valida o token com base no provedor configurado.
        Retorna o payload do token (dict) se válido.
        """
        token = credentials.credentials
        
        try:
            if self.provider == "mock":
                return self._validate_mock(token)
            elif self.provider == "keycloak":
                return self._validate_keycloak(token)
            elif self.provider == "google":
                return self._validate_google(token)
            else:
                logger.error(f"Provedor de autenticação desconhecido: {self.provider}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Erro de configuração de autenticação"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erro na validação do token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def _validate_mock(self, token: str) -> Dict:
        """
        Validador para desenvolvimento.
        Aceita qualquer token que comece com 'mock-'.
        Se for 'mock-admin', dá permissão de admin.
        """
        if token.startswith("mock-"):
            roles = ["user"]
            if "admin" in token:
                roles.append("admin")
                
            return {
                "sub": "user-mock-123",
                "name": "Usuário Mock",
                "roles": roles,
                "email": "mock@teste.com"
            }
        raise HTTPException(status_code=401, detail="Token Mock inválido (deve começar com 'mock-')")

    def _validate_keycloak(self, token: str) -> Dict:
        """Valida token via Introspection ou decodificação local"""
        if not self.keycloak_url:
            raise ValueError("KEYCLOAK_URL não configurada")

        try:
            keycloak_openid = KeycloakOpenID(
                server_url=self.keycloak_url,
                client_id=self.keycloak_client_id,
                realm_name=self.keycloak_realm,
                client_secret_key=self.keycloak_client_secret
            )
            
            token_info = keycloak_openid.introspect(token)
            
            if not token_info.get("active"):
                raise Exception("Token inativo")
            
            # Normaliza roles do Keycloak (realm_access.roles)
            roles = token_info.get("realm_access", {}).get("roles", [])
            token_info["roles"] = roles
                
            return token_info
            
        except Exception as e:
            logger.warning(f"Falha na validação Keycloak: {e}")
            raise HTTPException(status_code=401, detail="Token Keycloak inválido")

    def _validate_google(self, token: str) -> Dict:
        """Valida token ID do Google"""
        if not self.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID não configurado")
            
        try:
            id_info = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                self.google_client_id
            )
            # Google não tem roles padrão, assume user
            id_info["roles"] = ["user"]
            return id_info
        except ValueError as e:
            raise HTTPException(status_code=401, detail=f"Token Google inválido: {str(e)}")

# Instância global
iam = IAMManager()

# Dependência base
def get_current_user(token_payload: Dict = Security(iam.verify_token)):
    return token_payload

# Dependência para verificar roles (Factory)
class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Dict = Depends(get_current_user)):
        user_roles = user.get("roles", [])
        # Verifica se tem pelo menos uma das roles permitidas
        if not any(role in user_roles for role in self.allowed_roles):
            logger.warning(f"Acesso negado. Usuário {user.get('sub')} não tem roles {self.allowed_roles}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso insuficiente"
            )
        return user

# Atalho para admin
admin_required = RoleChecker(["admin"])
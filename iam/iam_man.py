from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer
from typing import Optional, Callable
import os
import jwt  # Para modo local/JWT

# from keycloak import KeycloakOpenID  # Para Keycloak
# Outras importações para Google, Auth0, etc.

app = FastAPI()

# 1. Configuração via Ambiente
AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "mock")  # Padrão: modo simulado
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


# 2. Funções Validadoras por Provedor

def validate_mock_token(token: str) -> dict:
    """Validador para ambiente local/desenvolvimento."""
    # Exemplo simples: verifica se o token é um 'magic string'
    # Em produção, substitua por validação JWT local real [citation:1][citation:7]
    if token == "meu-token-de-teste-secreto":
        return {"sub": "usuario_teste", "email": "teste@exemplo.com"}
    raise HTTPException(status_code=401, detail="Token de teste inválido")


def validate_keycloak_token(token: str) -> dict:
    """Validador para Keycloak[citation:2]."""
    # Configuração (buscar de variáveis de ambiente)
    server_url = os.getenv("KEYCLOAK_SERVER_URL")
    realm = os.getenv("KEYCLOAK_REALM")
    client_id = os.getenv("KEYCLOAK_CLIENT_ID")
    client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET")

    # keycloak_openid = KeycloakOpenID(...)
    try:
        # user_info = keycloak_openid.userinfo(token)
        user_info = {"sub": "usuario_keycloak", "preferred_username": "alice"}  # Exemplo
        return user_info
    except Exception:
        raise HTTPException(status_code=401, detail="Token Keycloak inválido")


def validate_google_token(token: str) -> dict:
    """Validador para Google[citation:9]."""
    from google.oauth2 import id_token
    from google.auth.transport import requests
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
        return {"sub": idinfo["sub"], "email": idinfo.get("email")}
    except ValueError:
        raise HTTPException(status_code=401, detail="Token Google inválido")


# 3. Roteador Principal (Factory Function)
def get_auth_validator() -> Callable[[str], dict]:
    """Retorna a função de validação baseada no provedor configurado."""
    provider_map = {
        "mock": validate_mock_token,
        "keycloak": validate_keycloak_token,
        "google": validate_google_token,
        # Adicione novos provedores aqui: "azure": validate_azure_token, ...
    }
    validator = provider_map.get(AUTH_PROVIDER)
    if not validator:
        raise ValueError(f"Provedor de autenticação '{AUTH_PROVIDER}' não suportado")
    return validator


# 4. Dependência Principal do FastAPI
async def get_current_user(
        token: Optional[str] = Depends(oauth2_scheme),
        credentials: Optional[HTTPBearer] = Depends(http_bearer)
) -> dict:
    """Dependência para extrair e validar o token com o provedor ativo."""
    # Tenta obter o token de 'oauth2_scheme' ou 'http_bearer'
    token = token or (credentials.credentials if credentials else None)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso não fornecido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    validator = get_auth_validator()  # Obtém o validador correto
    user_info = validator(token)  # Valida o token
    return user_info  # Retorna as informações do usuário


# 5. Exemplo de Uso em uma Rota Protegida
@app.get("/protegido")
async def rota_protegida(usuario: dict = Depends(get_current_user)):
    return {
        "mensagem": "Acesso concedido!",
        "usuario": usuario.get("sub"),
        "provedor": AUTH_PROVIDER
    }
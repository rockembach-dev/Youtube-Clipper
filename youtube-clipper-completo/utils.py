"""
utils.py
Funções pequenas e utilitárias, reutilizadas por mais de um módulo do projeto.
"""
import re
import unicodedata


def slugificar(texto: str, tamanho_max: int = 60) -> str:
    """
    Converte um texto livre (ex: título de vídeo ou de corte) em um nome de
    pasta/arquivo seguro: minúsculas, sem acentos/símbolos, espaços viram hífen.
    Ex: "Título com Ação!" -> "titulo-com-acao"
    """
    texto = texto.strip().lower()
    # remove acentos (á -> a, ç -> c, ã -> a, etc.) em vez de simplesmente apagar a letra
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9\s-]", "", texto)
    texto = re.sub(r"\s+", "-", texto)
    texto = re.sub(r"-{2,}", "-", texto).strip("-")
    return texto[:tamanho_max] or "video"

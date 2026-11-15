"""Identificação do formato dos arquivos de edital.

Módulo leve, sem dependências de IA, para poder ser usado tanto pela API (upload)
quanto pelo worker (download do PNCP).
"""
import io
import zipfile

TAMANHO_MAXIMO_BYTES = 50 * 1024 * 1024
_ZIP = b"PK\x03\x04"


class ErroDefinitivo(Exception):
    """Falha que não se resolve tentando de novo (arquivo em formato não suportado,
    PDF sem texto, compra sem arquivos). O worker não repete a tarefa e mostra a
    mensagem ao usuário como está."""


def eh_pdf(conteudo: bytes | None) -> bool:
    if not conteudo or conteudo[:4] == _ZIP:
        # Um ZIP sem compressão traz o PDF interno legível logo no início; não é um PDF.
        return False
    # A especificação permite lixo antes do cabeçalho; leitores aceitam %PDF nos primeiros 1024 bytes.
    return b"%PDF" in conteudo[:1024]


def extrair_pdf(conteudo: bytes | None) -> bytes | None:
    """Devolve os bytes de um PDF, ou None se o conteúdo não for (nem contiver) um PDF.

    O PNCP às vezes publica o edital dentro de um ZIP com anexos; nesse caso devolve
    o PDF interno, dando preferência a um arquivo com 'edital' no nome.
    """
    if not conteudo:
        return None
    if eh_pdf(conteudo):
        return conteudo
    if conteudo[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
                pdfs = [n for n in z.namelist() if n.lower().endswith(".pdf")]
                if not pdfs:
                    return None
                alvo = next((n for n in pdfs if "edital" in n.lower()), pdfs[0])
                interno = z.read(alvo)
                return interno if eh_pdf(interno) else None
        except zipfile.BadZipFile:
            return None
    return None


def descrever_formato(conteudo: bytes | None, nome: str | None = None) -> str:
    """Nome legível do formato, para explicar ao usuário por que o arquivo não serve."""
    ext = (nome or "").lower().rsplit(".", 1)[-1] if nome and "." in nome else ""
    inicio = (conteudo or b"")[:8]
    if eh_pdf(conteudo):
        return "PDF"
    if inicio.startswith(b"\xd0\xcf\x11\xe0"):
        return {"xls": "planilha Excel antiga (.xls)", "ppt": "apresentação PowerPoint antiga (.ppt)"}.get(
            ext, "documento Word antigo (.doc)")
    if inicio.startswith(b"PK\x03\x04"):
        return {
            "docx": "documento Word (.docx)", "xlsx": "planilha Excel (.xlsx)",
            "odt": "documento OpenDocument (.odt)", "ods": "planilha OpenDocument (.ods)",
        }.get(ext, "arquivo compactado (.zip) sem PDF")
    if inicio.startswith(b"Rar!"):
        return "arquivo compactado (.rar)"
    if inicio.startswith(b"7z\xbc\xaf"):
        return "arquivo compactado (.7z)"
    if inicio.lstrip().lower().startswith((b"<!doc", b"<html")):
        return "página HTML"
    if inicio.startswith((b"\xff\xd8", b"\x89PNG")):
        return "imagem"
    return f"formato desconhecido (.{ext})" if ext else "formato desconhecido"

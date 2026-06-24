from __future__ import annotations

from typing import Any, Dict, Optional


try:
    from tools.lang.answer_language import normalize_answer_lang, resolve_answer_lang
except Exception:
    normalize_answer_lang = None
    resolve_answer_lang = None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _normalize_lang(value: Any) -> str:
    if callable(normalize_answer_lang):
        try:
            normalized = normalize_answer_lang(value)
            if normalized:
                return normalized
        except Exception:
            pass

    raw = _safe_str(value).lower().replace("_", "-")
    if not raw:
        return ""
    if "-" in raw:
        raw = raw.split("-", 1)[0]
    if raw.isalpha() and 2 <= len(raw) <= 3:
        return raw
    return ""


def mcp_response_lang(
    question: Any,
    request_args: Optional[Dict[str, Any]] = None,
    default_lang: str = "en",
) -> str:
    args = _safe_dict(request_args)

    metadata_lang = _normalize_lang(args.get("_answer_lang"))
    if metadata_lang:
        return metadata_lang

    q = _safe_str(question)
    if callable(resolve_answer_lang):
        try:
            lang, _dbg = resolve_answer_lang(
                question=q,
                args={},
                default_lang=default_lang,
            )
            normalized = _normalize_lang(lang)
            if normalized:
                return normalized
        except Exception:
            pass

    return _normalize_lang(default_lang) or "en"


_TEMPLATES: Dict[str, Dict[str, str]] = {
    "en": {
        "provider_failed": "{provider} provider failed: {error}",
        "provider_completed": "{provider} search completed.",
        "pexels_empty": "No Pexels images found for “{query}”.",
        "pexels_found": "Found {count} Pexels images related to “{query}”:",
        "pexels_image": "Image {index}",
        "pexels_page": "View source page",
        "photographer": "Photographer",
        "exa_empty": "No Exa results found for “{query}”.",
        "exa_found": "Found {count} Exa results related to “{query}”:",
        "arxiv_empty": "No arXiv papers found for “{query}”.",
        "arxiv_found": "Found {count} arXiv papers related to “{query}”:",
        "summary": "Summary",
        "link": "Link",
        "et_al": "et al.",
    },
    "zh": {
        "provider_failed": "{provider} 提供方失败：{error}",
        "provider_completed": "{provider} 搜索已完成。",
        "pexels_empty": "未找到与“{query}”相关的 Pexels 图片。",
        "pexels_found": "我在 Pexels 找到 {count} 张与“{query}”相关的图片：",
        "pexels_image": "图片 {index}",
        "pexels_page": "查看原页",
        "photographer": "作者",
        "exa_empty": "未找到与“{query}”相关的 Exa 结果。",
        "exa_found": "我在 Exa 找到 {count} 条与“{query}”相关的结果：",
        "arxiv_empty": "未找到与“{query}”相关的 arXiv 论文。",
        "arxiv_found": "我在 arXiv 找到 {count} 篇与“{query}”相关的论文：",
        "summary": "摘要",
        "link": "链接",
        "et_al": "等",
    },
    "ja": {
        "provider_failed": "{provider}プロバイダーでエラーが発生しました：{error}",
        "provider_completed": "{provider}の検索が完了しました。",
        "pexels_empty": "Pexelsで「{query}」に関連する画像は見つかりませんでした。",
        "pexels_found": "Pexelsで「{query}」に関連する画像を{count}件見つけました：",
        "pexels_image": "画像 {index}",
        "pexels_page": "元ページを見る",
        "photographer": "撮影者",
        "exa_empty": "Exaで「{query}」に関連する結果は見つかりませんでした。",
        "exa_found": "Exaで「{query}」に関連する結果を{count}件見つけました：",
        "arxiv_empty": "arXivで「{query}」に関連する論文は見つかりませんでした。",
        "arxiv_found": "arXivで「{query}」に関連する論文を{count}件見つけました：",
        "summary": "概要",
        "link": "リンク",
        "et_al": "ほか",
    },
    "ko": {
        "provider_failed": "{provider} 제공자 오류: {error}",
        "provider_completed": "{provider} 검색이 완료되었습니다.",
        "pexels_empty": "Pexels에서 “{query}”와 관련된 이미지를 찾지 못했습니다.",
        "pexels_found": "Pexels에서 “{query}”와 관련된 이미지 {count}개를 찾았습니다:",
        "pexels_image": "이미지 {index}",
        "pexels_page": "원본 페이지 보기",
        "photographer": "촬영자",
        "exa_empty": "Exa에서 “{query}”와 관련된 결과를 찾지 못했습니다.",
        "exa_found": "Exa에서 “{query}”와 관련된 결과 {count}개를 찾았습니다:",
        "arxiv_empty": "arXiv에서 “{query}”와 관련된 논문을 찾지 못했습니다.",
        "arxiv_found": "arXiv에서 “{query}”와 관련된 논문 {count}편을 찾았습니다:",
        "summary": "요약",
        "link": "링크",
        "et_al": "외",
    },
    "de": {
        "provider_failed": "{provider}-Anbieter fehlgeschlagen: {error}",
        "provider_completed": "{provider}-Suche abgeschlossen.",
        "pexels_empty": "Keine Pexels-Bilder zu „{query}“ gefunden.",
        "pexels_found": "{count} Pexels-Bilder zu „{query}“ gefunden:",
        "pexels_image": "Bild {index}",
        "pexels_page": "Quellseite öffnen",
        "photographer": "Fotograf",
        "exa_empty": "Keine Exa-Ergebnisse zu „{query}“ gefunden.",
        "exa_found": "{count} Exa-Ergebnisse zu „{query}“ gefunden:",
        "arxiv_empty": "Keine arXiv-Paper zu „{query}“ gefunden.",
        "arxiv_found": "{count} arXiv-Paper zu „{query}“ gefunden:",
        "summary": "Zusammenfassung",
        "link": "Link",
        "et_al": "u. a.",
    },
    "es": {
        "provider_failed": "El proveedor {provider} falló: {error}",
        "provider_completed": "Búsqueda de {provider} completada.",
        "pexels_empty": "No se encontraron imágenes de Pexels relacionadas con «{query}».",
        "pexels_found": "Se encontraron {count} imágenes de Pexels relacionadas con «{query}»:",
        "pexels_image": "Imagen {index}",
        "pexels_page": "Ver página original",
        "photographer": "Fotógrafo",
        "exa_empty": "No se encontraron resultados de Exa relacionados con «{query}».",
        "exa_found": "Se encontraron {count} resultados de Exa relacionados con «{query}»:",
        "arxiv_empty": "No se encontraron artículos de arXiv relacionados con «{query}».",
        "arxiv_found": "Se encontraron {count} artículos de arXiv relacionados con «{query}»:",
        "summary": "Resumen",
        "link": "Enlace",
        "et_al": "et al.",
    },
    "fr": {
        "provider_failed": "Le fournisseur {provider} a échoué : {error}",
        "provider_completed": "Recherche {provider} terminée.",
        "pexels_empty": "Aucune image Pexels liée à « {query} » n’a été trouvée.",
        "pexels_found": "{count} images Pexels liées à « {query} » ont été trouvées :",
        "pexels_image": "Image {index}",
        "pexels_page": "Voir la page source",
        "photographer": "Photographe",
        "exa_empty": "Aucun résultat Exa lié à « {query} » n’a été trouvé.",
        "exa_found": "{count} résultats Exa liés à « {query} » ont été trouvés :",
        "arxiv_empty": "Aucun article arXiv lié à « {query} » n’a été trouvé.",
        "arxiv_found": "{count} articles arXiv liés à « {query} » ont été trouvés :",
        "summary": "Résumé",
        "link": "Lien",
        "et_al": "et al.",
    },
    "pt": {
        "provider_failed": "O provedor {provider} falhou: {error}",
        "provider_completed": "Pesquisa do {provider} concluída.",
        "pexels_empty": "Nenhuma imagem do Pexels relacionada a “{query}” foi encontrada.",
        "pexels_found": "Foram encontradas {count} imagens do Pexels relacionadas a “{query}”:",
        "pexels_image": "Imagem {index}",
        "pexels_page": "Ver página original",
        "photographer": "Fotógrafo",
        "exa_empty": "Nenhum resultado do Exa relacionado a “{query}” foi encontrado.",
        "exa_found": "Foram encontrados {count} resultados do Exa relacionados a “{query}”:",
        "arxiv_empty": "Nenhum artigo do arXiv relacionado a “{query}” foi encontrado.",
        "arxiv_found": "Foram encontrados {count} artigos do arXiv relacionados a “{query}”:",
        "summary": "Resumo",
        "link": "Link",
        "et_al": "et al.",
    },
    "it": {
        "provider_failed": "Il provider {provider} non è riuscito: {error}",
        "provider_completed": "Ricerca {provider} completata.",
        "pexels_empty": "Nessuna immagine Pexels trovata per “{query}”.",
        "pexels_found": "Trovate {count} immagini Pexels correlate a “{query}”:",
        "pexels_image": "Immagine {index}",
        "pexels_page": "Apri pagina originale",
        "photographer": "Fotografo",
        "exa_empty": "Nessun risultato Exa trovato per “{query}”.",
        "exa_found": "Trovati {count} risultati Exa correlati a “{query}”:",
        "arxiv_empty": "Nessun articolo arXiv trovato per “{query}”.",
        "arxiv_found": "Trovati {count} articoli arXiv correlati a “{query}”:",
        "summary": "Sintesi",
        "link": "Link",
        "et_al": "et al.",
    },
}


def mcp_text(
    question: Any,
    key: str,
    request_args: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    lang = mcp_response_lang(question, request_args=request_args)
    template = _TEMPLATES.get(lang, _TEMPLATES["en"]).get(key)
    if not template:
        template = _TEMPLATES["en"].get(key, "")
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def mcp_provider_error_response(
    question: Any,
    provider: str,
    error: str,
    request_args: Optional[Dict[str, Any]] = None,
) -> str:
    return mcp_text(
        question,
        "provider_failed",
        request_args=request_args,
        provider=_safe_str(provider, "MCP"),
        error=_safe_str(error),
    )


__all__ = [
    "mcp_provider_error_response",
    "mcp_response_lang",
    "mcp_text",
]

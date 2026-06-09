"""Tests phase A (tests-first) — extraction d'images (photo-evidence).

Contrat : docs/specs/photo-evidence-SPEC.md §3.1 + §4 criteres 9 a 12.
`extract_image_urls(html, base_url) -> list[str]` n'existe pas encore dans
`app.url_fetch` : l'import echoue (ImportError) -> rouge legitime attendu.

Isolation : conftest.py force une base SQLite jetable + OPENAI_API_KEY factice
AVANT tout import app. Aucun appel reseau ici (extraction purement locale).
"""

import pytest


# --- critere 9 : og:image + JSON-LD lus sur le HTML BRUT -------------------
def test_extract_reads_og_image_and_jsonld_from_raw_html():
    """Le JSON-LD vit dans <script type="application/ld+json"> que le nettoyage
    de fetch_listing_text decompose. L'extraction doit lire le HTML AVANT cette
    decomposition : on prouve que la cle `image` du JSON-LD est bien recuperee
    EN MEME TEMPS que l'og:image."""
    from app.url_fetch import extract_image_urls

    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.agence.fr/principale.jpg">
      <script type="application/ld+json">
      {"@type": "Product", "image": "https://cdn.agence.fr/jsonld.jpg"}
      </script>
    </head><body><p>annonce</p></body></html>
    """
    urls = extract_image_urls(html, "https://agence.fr/annonce")

    assert "https://cdn.agence.fr/principale.jpg" in urls
    assert "https://cdn.agence.fr/jsonld.jpg" in urls


# --- critere 10 : galerie <img> + URL relative resolue via urljoin --------
def test_extract_resolves_relative_gallery_urls():
    from app.url_fetch import extract_image_urls

    html = '<html><body><img src="/photos/1.jpg"></body></html>'
    urls = extract_image_urls(html, "https://agence.fr/annonce")

    assert "https://agence.fr/photos/1.jpg" in urls


def test_extract_resolves_data_src_fallback():
    """A defaut de src, l'attribut data-src (lazy-loading) est utilise (§3.1)."""
    from app.url_fetch import extract_image_urls

    html = '<html><body><img data-src="/photos/lazy.jpg"></body></html>'
    urls = extract_image_urls(html, "https://agence.fr/annonce")

    assert "https://agence.fr/photos/lazy.jpg" in urls


# --- critere 11 : dedup en preservant l'ordre de priorite -----------------
def test_extract_dedups_same_url_across_sources():
    from app.url_fetch import extract_image_urls

    shared = "https://cdn.agence.fr/principale.jpg"
    html = f"""
    <html><head>
      <meta property="og:image" content="{shared}">
    </head><body>
      <img src="{shared}">
    </body></html>
    """
    urls = extract_image_urls(html, "https://agence.fr/annonce")

    assert urls.count(shared) == 1


def test_extract_og_image_kept_before_gallery():
    """L'ordre de priorite (§2 decision 2) : og:image avant les <img> galerie."""
    from app.url_fetch import extract_image_urls

    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.agence.fr/principale.jpg">
    </head><body>
      <img src="https://cdn.agence.fr/galerie1.jpg">
    </body></html>
    """
    urls = extract_image_urls(html, "https://agence.fr/annonce")

    assert urls.index("https://cdn.agence.fr/principale.jpg") < urls.index(
        "https://cdn.agence.fr/galerie1.jpg"
    )


# --- critere 12 : robustesse — aucune image -> [] sans lever --------------
def test_extract_no_image_returns_empty_list():
    from app.url_fetch import extract_image_urls

    html = "<html><body><p>Aucune image ici, juste du texte.</p></body></html>"
    assert extract_image_urls(html, "https://agence.fr/annonce") == []


def test_extract_malformed_html_does_not_raise():
    from app.url_fetch import extract_image_urls

    malformed = "<html><body><img src=<<>> <meta property=og:image"
    # Ne doit jamais lever : au pire une liste (eventuellement vide).
    result = extract_image_urls(malformed, "https://agence.fr/annonce")
    assert isinstance(result, list)


# --- critere 11 (renfort) : twitter:image pris en compte ------------------
def test_extract_includes_twitter_image():
    from app.url_fetch import extract_image_urls

    html = """
    <html><head>
      <meta name="twitter:image" content="https://cdn.agence.fr/tw.jpg">
    </head><body></body></html>
    """
    urls = extract_image_urls(html, "https://agence.fr/annonce")
    assert "https://cdn.agence.fr/tw.jpg" in urls

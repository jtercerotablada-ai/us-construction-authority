"""Static site generator for U.S. Construction & Plumbing Authority.

All client-editable copy lives in ../content/*.yml (edited through Pages CMS, see ../.pages.yml).
Layout, styles, scripts and diagram pin positions live here and in ../assets.

Run:   pip install -r requirements.txt && python3 _source/build.py
Output: ../dist  (deploy this folder; Cloudflare Pages / Vercel run the same command)
Env:    SITE_URL=https://www.example.com   -> canonical URLs, og:url/og:image, sitemap.xml
        OUT_DIR=/some/path                 -> alternative output folder

If the content has a problem (missing field, unknown icon, missing photo...) the build stops with
a clear message and exit code 1, so the host keeps serving the last good version of the site.
"""
import os, re, sys, json, shutil
from html import unescape, escape
from urllib.parse import quote, quote_plus, unquote

import yaml
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "_source")
CONTENT = os.path.join(ROOT, "content")
OUT = os.path.abspath(os.environ.get("OUT_DIR") or os.path.join(ROOT, "dist"))
UPLOADS = "assets/img/uploads"          # client photo uploads (Pages CMS media folder)
PHOTOS = "assets/img/projects"          # where the resized gallery photos are published

def _inside(path, parent):
    return path == parent or path.startswith(parent.rstrip(os.sep) + os.sep)

_out = os.path.realpath(OUT)
if _inside(os.path.realpath(ROOT), _out) or any(
        _inside(_out, os.path.realpath(os.path.join(ROOT, d))) for d in ("content", "_source", "assets", ".git")):
    sys.exit(f"OUT_DIR={OUT} would overwrite the project; use a separate folder such as dist/.")

# Production URL (no trailing slash). Leave empty until the domain is confirmed;
# canonical, og:url, absolute og:image and sitemap.xml are emitted only when set.
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
# Cloudflare Pages (CF_PAGES=1) serves /page.html at /page, so canonical URLs and the sitemap drop ".html" there.
PRETTY_URLS = os.environ.get("CF_PAGES") == "1"

def public_url(path):
    if path in ("", "index.html"):
        path = ""
    elif PRETTY_URLS and path.endswith(".html"):
        path = path[:-5]
    return f"{SITE_URL}/{path}"

# ================================================================== content loading & validation
ERRORS = []
PARTIAL = OUT + ".partial"   # pages are written here and replace OUT only when the whole build succeeded

def fail(msg):
    ERRORS.append(msg)

def stop_on_errors():
    if not ERRORS:
        return
    print("\nNO SE PUBLICÓ: hay que corregir el contenido / BUILD STOPPED: fix the content below\n", file=sys.stderr)
    for msg in ERRORS:
        print("  - " + msg, file=sys.stderr)
    print("\nLa versión anterior del sitio sigue en línea. / The previous version stays online.\n", file=sys.stderr)
    shutil.rmtree(PARTIAL, ignore_errors=True)
    sys.exit(1)

def load_required(rel):
    """A file the whole site depends on: stop right away if it can't be read."""
    data = load_yaml(rel)
    if data is None:
        stop_on_errors()
    return data

class Loader(yaml.SafeLoader):
    """YAML 1.2 core schema, like the files Pages CMS writes: Yes/No/On/Off and 8:30 stay text."""

Loader.yaml_implicit_resolvers = {
    ch: [r for r in rs if r[0].rsplit(":", 1)[1] not in ("bool", "int", "float", "timestamp", "value", "merge")]
    for ch, rs in yaml.SafeLoader.yaml_implicit_resolvers.items()}
Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))
Loader.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^(?:[-+]?[0-9]+|0x[0-9a-fA-F]+)$"), list("-+0123456789"))
Loader.add_implicit_resolver("tag:yaml.org,2002:float", re.compile(
    r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"), list("-+0123456789."))

def load_yaml(rel):
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        # U+2028/U+2029/U+0085 (pasted from Pages, Keynote, PDFs) are line breaks to PyYAML but not to Pages CMS
        data = yaml.load(re.sub("[\u2028\u2029\x85]", " ", text), Loader=Loader)
    except FileNotFoundError:
        fail(f"{rel}: no existe el archivo.")
        return {}
    except yaml.YAMLError as err:
        mark = getattr(err, "problem_mark", None)
        near = f" cerca de la línea {mark.line + 1}" if mark else ""
        fail(f"{rel}: el archivo tiene un formato inválido{near}.")
        return None
    if not isinstance(data, dict):
        fail(f"{rel}: el archivo está vacío o tiene un formato inválido.")
        return None
    return data

def get(d, key, where, kind=str, required=True, default=None):
    """Read one field, checking its type. Strings are stripped."""
    v = d.get(key, default) if isinstance(d, dict) else default
    if kind is str:
        if v is None:
            v = ""
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            v = str(v)
        if not isinstance(v, str):
            fail(f"{where}: el campo '{key}' debe ser texto.")
            return default or ""
        v = v.strip()
        if required and not v:
            fail(f"{where}: el campo '{key}' está vacío.")
        return v
    if kind is list:
        if v is None:
            v = []
        if not isinstance(v, list):
            fail(f"{where}: el campo '{key}' debe ser una lista.")
            return []
        if required and not v:
            fail(f"{where}: la lista '{key}' está vacía.")
        return v
    if kind is bool:
        return bool(v)
    if kind is dict:
        if not isinstance(v, dict):
            if required:
                fail(f"{where}: falta la sección '{key}'.")
            return {}
        return v
    if kind is int:
        try:
            return int(v)
        except (TypeError, ValueError):
            if required:
                fail(f"{where}: el campo '{key}' debe ser un número.")
            return default if default is not None else 0
    return v

def texts(d, key, where, required=True):
    """A list of non-empty strings."""
    items = [str(x).strip() for x in get(d, key, where, list, False) if x is not None and str(x).strip()]
    if required and not items:
        fail(f"{where}: la lista '{key}' está vacía.")
    return items

# ---------------------------------------------------------------- formatting helpers
def e(s):
    """Plain client text -> safe HTML text."""
    return escape(str(s), quote=True)

def hd(s):
    """Heading: *words* become the red italic accent."""
    return re.sub(r"\*(?!\s)(.+?)(?<!\s)\*", r"<em>\1</em>", e(s))

def rich(s):
    """Paragraph: **bold** and *italic*."""
    s = re.sub(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", r"<strong>\1</strong>", e(s))
    return re.sub(r"\*(?!\s)(.+?)(?<!\s)\*", r"<em>\1</em>", s)

def plain(s):
    return re.sub(r"\*+", "", str(s))

def attr(text):
    """Text (plain or already escaped) safe for an HTML attribute or <title>."""
    return escape(unescape(text), quote=True)

def tel(phone, where):
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return "tel:+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "tel:+" + digits
    fail(f"{where}: el teléfono '{phone}' no parece un número válido de 10 dígitos.")
    return "tel:" + digits

def safe_link(url, where):
    url = (url or "").strip()
    if not url:
        return ""
    if re.match(r"^(https?://|mailto:|tel:|/|#)", url) or re.match(r"^[\w\-./]+\.html(#[\w-]+)?$", url):
        return url
    fail(f"{where}: el enlace '{url}' no es válido (usa una dirección que empiece con https://).")
    return ""

ICONS = {  # value -> Font Awesome solid icon name (the CMS offers exactly these)
    "faucet": "faucet", "faucet-drip": "faucet-drip", "droplet": "droplet", "shower": "shower", "toilet": "toilet",
    "sink": "sink", "fire-flame-simple": "fire-flame-simple", "filter": "filter", "house-flood-water": "house-flood-water",
    "grip-lines": "grip-lines", "gauge-simple": "gauge-simple", "gears": "gears", "soap": "soap", "glass-water": "glass-water",
    "wrench": "wrench", "screwdriver-wrench": "screwdriver-wrench", "toolbox": "toolbox", "bolt": "bolt", "plug": "plug",
    "lightbulb": "lightbulb", "fan": "fan", "sun": "sun", "power-off": "power-off", "toggle-on": "toggle-on",
    "table-cells": "table-cells", "server": "server", "ethernet": "ethernet", "code-branch": "code-branch",
    "car-battery": "car-battery", "temperature-arrow-up": "temperature-arrow-up", "temperature-half": "temperature-half",
    "triangle-exclamation": "triangle-exclamation", "house-chimney-window": "house-chimney-window",
    "trowel-bricks": "trowel-bricks", "magnifying-glass": "magnifying-glass", "file-signature": "file-signature",
    "helmet-safety": "helmet-safety", "hammer": "hammer", "paint-roller": "paint-roller", "ruler-combined": "ruler-combined",
    "building": "building", "city": "city", "shield-halved": "shield-halved", "clipboard-check": "clipboard-check",
}
LICENSE_ICONS = {"building": "fa-building", "electrical": "fa-bolt", "plumbing": "fa-faucet", "other": "fa-certificate"}

def icon(value, where):
    v = (value or "").strip()
    if v not in ICONS:
        if v:  # an empty value was already reported by get()
            fail(f"{where}: el ícono '{v}' no está en la lista permitida.")
        return "fa-wrench"
    return "fa-" + ICONS[v]

# ---------------------------------------------------------------- site.yml
SITE = load_required("content/site.yml")
W = "content/site.yml"
SITE_NAME = get(SITE, "company_name", W)
ABOUT_LINE = get(SITE, "about_line", W)
LEGAL_NAME = get(SITE, "legal_name", W)
EMAIL = get(SITE, "email", W)
if EMAIL and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", EMAIL):
    fail(f"{W}: el correo '{EMAIL}' no es válido.")

OFFICES = []
for i, o in enumerate(get(SITE, "offices", W, list), 1):
    w = f"{W} → oficina {i}"
    if not isinstance(o, dict):
        fail(f"{w}: formato inválido.")
        continue
    phone = get(o, "phone", w)
    OFFICES.append({
        "region": get(o, "region", w), "phone": phone, "tel": tel(phone, w) if phone else "",
        "street": get(o, "street", w), "city": get(o, "city", w), "state": get(o, "state", w),
        "zip": get(o, "zip", w),
    })
if not OFFICES:
    OFFICES.append({"region": "", "phone": "", "tel": "", "street": "", "city": "", "state": "", "zip": ""})
PRIMARY = OFFICES[0]

LICENSES = []
for i, l in enumerate(get(SITE, "licenses", W, list), 1):
    w = f"{W} → licencia {i}"
    if not isinstance(l, dict):
        fail(f"{w}: formato inválido.")
        continue
    kind = get(l, "type", w, required=False) or "other"
    LICENSES.append({"type": kind if kind in LICENSE_ICONS else "other", "label": get(l, "label", w), "number": get(l, "number", w)})
LIC = " &middot; ".join(e(l["number"]) for l in LICENSES)

ANN = get(SITE, "announcement", W, dict, required=False)
ANNOUNCE = None
a_text = get(ANN, "text", W + " → aviso", required=False)
if get(ANN, "show", W, bool) and a_text:
    a_link = safe_link(get(ANN, "link", W + " → aviso", required=False), W + " → aviso")
    ANNOUNCE = {"text": a_text, "link": a_link, "link_text": get(ANN, "link_text", W + " → aviso", required=False) or "Learn more"}

CTA = get(SITE, "final_cta", W, dict)
CTA_HEADING = get(CTA, "heading", W + " → final_cta")
CTA_LEAD = get(CTA, "lead", W + " → final_cta")

# ---------------------------------------------------------------- home.yml / pages.yml / gallery.yml
HOME = load_required("content/home.yml")
PAGES_TXT = load_required("content/pages.yml")
GALLERY = load_required("content/gallery.yml")

def section(data, key, where):
    return get(data, key, where, dict)

# ---------------------------------------------------------------- diagrams
STRUCT = load_required("_source/diagrams.yml")
DIAGRAMS, POINTS = {}, {}
for key, st in STRUCT.items():
    w = f"content/diagrams/{key}.yml"
    txt = load_required(w)
    title, desc = get(txt, "title", w), get(txt, "description", w)
    labels = texts(txt, "points", w, required=False)
    pins = st.get("pins") or []
    if len(labels) != len(pins):
        fail(f"{w}: el diagrama tiene {len(pins)} puntos numerados y necesita exactamente {len(pins)} nombres (hay {len(labels)}).")
    DIAGRAMS[key] = (st["image"], e(title), e(desc), st["division"])
    POINTS[key] = [(x, y, e(lbl)) for (x, y), lbl in zip(pins, labels)]
DIAGRAM_ORDER = list(STRUCT.keys())

# ---------------------------------------------------------------- services
def load_services(division):
    folder = os.path.join(CONTENT, "services", division)
    items = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith((".yml", ".yaml")):
            continue
        slug = os.path.splitext(name)[0]
        w = f"content/services/{division}/{name}"
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            fail(f"{w}: el nombre del archivo solo puede tener letras minúsculas, números y guiones.")
            continue
        d = load_yaml(w)
        if d is None:
            continue
        if not get(d, "visible", w, bool, default=True):
            continue
        dg = (get(d, "diagram", w, required=False) or "none")
        if dg != "none" and dg not in DIAGRAMS:
            fail(f"{w}: el diagrama '{dg}' no existe.")
            dg = "none"
        items.append((get(d, "order", w, int, required=False, default=999), slug, (
            slug, icon(get(d, "icon", w), w), e(get(d, "title", w)), e(get(d, "summary", w)),
            rich(get(d, "intro", w)), [e(x) for x in texts(d, "options", w)], [e(x) for x in texts(d, "reasons", w)],
            None if dg == "none" else dg)))
    if not items:
        fail(f"content/services/{division}: no hay ningún servicio visible.")
    return [s for _, _, s in sorted(items, key=lambda t: (t[0], t[1]))]

PLUMBING = load_services("plumbing")
ELECTRICAL = load_services("electrical")
SERVICE_SLUGS = {"plumbing": {s[0] for s in PLUMBING}, "electrical": {s[0] for s in ELECTRICAL}}

# ---------------------------------------------------------------- gallery
GALLERY_HEADING = get(GALLERY, "heading", "content/gallery.yml")
GALLERY_INTRO = get(GALLERY, "intro", "content/gallery.yml", required=False)
PROJECTS = []
for i, p in enumerate(get(GALLERY, "projects", "content/gallery.yml", list, required=False), 1):
    w = f"content/gallery.yml → proyecto {i}"
    if not isinstance(p, dict):
        fail(f"{w}: formato inválido.")
        continue
    img = get(p, "image", w)
    title = get(p, "title", w)
    if not img:
        continue
    rel = unquote(img).lstrip("/")
    if not rel.startswith(UPLOADS + "/") or ".." in rel or not os.path.isfile(os.path.join(ROOT, rel)):
        fail(f"{w}: la foto '{img}' no se encuentra. Súbela de nuevo desde el panel.")
        continue
    if os.path.splitext(rel)[1].lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        fail(f"{w}: la foto '{img}' debe ser JPG, PNG o WebP.")
        continue
    cat = get(p, "category", w, required=False) or "all"
    if cat not in ("all", "plumbing", "electrical", "building", "commercial"):
        fail(f"{w}: la categoría '{cat}' no es válida.")
        continue
    PROJECTS.append({"image": rel, "title": title, "category": cat})

# ================================================================== output folder
FINAL_OUT, OUT = OUT, PARTIAL
stop_on_errors()
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(os.path.join(OUT, "services"))
shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"),
                ignore=shutil.ignore_patterns("uploads", ".DS_Store"))
for name in ("favicon.ico",):
    shutil.copy(os.path.join(ROOT, name), os.path.join(OUT, name))

def img_size(name):
    with Image.open(os.path.join(OUT, "assets", "img", name)) as im:
        return im.size

def photo_name(rel, has_alpha, suffix=""):
    """uploads/cocina/Deck.JPG -> projects/cocina/Deck-jpg.jpg (the extension in the name keeps deck.jpg and
    deck.png apart; "-800" can't be produced from any upload, so the small copies never collide)."""
    base, ext = os.path.splitext(rel[len(UPLOADS) + 1:])
    return f"{PHOTOS}/{base}-{ext[1:].lower()}{suffix}{'.png' if has_alpha else '.jpg'}"

def to_srgb(im):
    """Rotate per EXIF, convert to 8-bit sRGB (keeping transparency) so every browser shows the same colours."""
    icc = im.info.get("icc_profile")
    im = ImageOps.exif_transpose(im)
    if im.mode in ("I;16", "I;16B", "I;16L", "I;16N", "I"):        # 16-bit greyscale: scale, don't clip
        im = im.convert("I").point(lambda v: v / 256).convert("L")
    has_alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
    if has_alpha:
        im = im.convert("RGBA")
        has_alpha = im.getchannel("A").getextrema()[0] < 255     # fully opaque PNGs become JPEGs
    mode = "RGBA" if has_alpha else "RGB"
    if icc:
        try:
            from io import BytesIO
            from PIL import ImageCms
            src = ImageCms.ImageCmsProfile(BytesIO(icc))
            return ImageCms.profileToProfile(im, src, ImageCms.createProfile("sRGB"), outputMode=mode), has_alpha
        except Exception:
            pass                                                  # unusual profile: plain conversion below
    return im.convert(mode), has_alpha

PHOTO = {}   # upload path -> (full path, small path, width, height, small width)

def process_photos():
    """Publish only the photos the gallery uses: capped at 2000px plus an 800px copy for phones."""
    taken = {}
    for p in PROJECTS:
        rel = p["image"]
        if rel in PHOTO:
            continue
        try:
            with Image.open(os.path.join(ROOT, rel)) as im:
                im, has_alpha = to_srgb(im)
        except Exception:
            fail(f"content/gallery.yml: la foto '/{rel}' no se puede abrir (archivo dañado o formato no compatible). "
                 "Súbela de nuevo como JPG.")
            continue
        full, small = photo_name(rel, has_alpha), photo_name(rel, has_alpha, "-800")
        if full.lower() in taken:
            fail(f"content/gallery.yml: las fotos '/{taken[full.lower()]}' y '/{rel}' tienen el mismo nombre. "
                 "Cambia el nombre de una de ellas.")
            continue
        taken[full.lower()] = rel
        sizes = []
        for path, cap in ((full, 2000), (small, 800)):
            out = im.copy()
            out.thumbnail((cap, cap), Image.LANCZOS)
            os.makedirs(os.path.dirname(os.path.join(OUT, path)), exist_ok=True)
            if has_alpha:
                out.save(os.path.join(OUT, path), "PNG", optimize=True)
            else:
                out.save(os.path.join(OUT, path), "JPEG", quality=82, optimize=True, progressive=True)
            sizes.append(out.size)
        PHOTO[rel] = (full, small, sizes[0][0], sizes[0][1], sizes[1][0])

process_photos()
stop_on_errors()

# ================================================================== layout
NAV = [("plumbing.html", "Plumbing"), ("electrical.html", "Electrical"), ("building.html", "Building &amp; Remodeling"),
       ("commercial.html", "Commercial"), ("index.html#about", "About")]

def jsonld():
    def office(o):
        digits = re.sub(r"\D", "", o["tel"])[-10:]
        d = {"@type": "HomeAndConstructionBusiness", "name": f"{SITE_NAME} — {o['region']}",
             "telephone": f"+1-{digits[:3]}-{digits[3:6]}-{digits[6:]}", "email": EMAIL,
             "address": {"@type": "PostalAddress", "streetAddress": o["street"], "addressLocality": o["city"],
                         "addressRegion": o["state"], "postalCode": o["zip"], "addressCountry": "US"},
             "areaServed": f"Florida {o['region']}" if o["state"].upper() in ("FL", "FLORIDA") else f"{o['region']}, {o['state']}"}
        if SITE_URL:
            d["url"] = SITE_URL + "/"
            d["image"] = SITE_URL + "/assets/img/logo.png"
        return d
    data = {
        "@context": "https://schema.org", "@type": "Organization", "name": SITE_NAME,
        "legalName": LEGAL_NAME, "email": EMAIL,
        "description": "Licensed & insured plumbing, electrical, remodeling, building inspection and trade work in Florida. Licenses "
                       + ", ".join(l["number"] for l in LICENSES) + ".",
        "department": [office(o) for o in OFFICES],
    }
    if SITE_URL:
        data["url"] = SITE_URL + "/"
        data["logo"] = SITE_URL + "/assets/img/logo.png"
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")

def head(b, title, desc, path="", schema=False):
    t, d = attr(title), attr(desc)
    canon = ""
    if SITE_URL:
        url = public_url(path)
        canon = f"""
  <link rel="canonical" href="{url}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{SITE_URL}/assets/img/og-image.jpg">
  <meta name="twitter:image" content="{SITE_URL}/assets/img/og-image.jpg">"""
    ld = f'\n  <script type="application/ld+json">{jsonld()}</script>' if schema else ""
    return f"""<!DOCTYPE html>
<html lang="en" class="no-js">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{t}</title>
  <meta name="description" content="{d}">
  <meta name="theme-color" content="#07111f">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{attr(SITE_NAME)}">
  <meta property="og:title" content="{t}">
  <meta property="og:description" content="{d}">
  <meta name="twitter:card" content="summary_large_image">{canon}
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" type="image/png" sizes="192x192" href="{b}assets/img/icon-192.png">
  <link rel="apple-touch-icon" href="{b}assets/img/apple-touch-icon.png">
  <link rel="preload" href="{b}assets/fonts/instrument-serif-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{b}assets/fonts/manrope-latin-600-normal.woff2" as="font" type="font/woff2" crossorigin>
  <script>document.documentElement.className='js';setTimeout(function(){{if(!window.__uscpa)document.documentElement.className+=' reveal-fallback'}},2500)</script>
  <link rel="stylesheet" href="{b}assets/css/icons.css">
  <link rel="stylesheet" href="{b}assets/css/styles.css">{ld}
</head>
<body>
  <a class="skip-link" href="#main">Skip to main content</a>
"""

def announcement(b):
    if not ANNOUNCE:
        return ""
    link = ANNOUNCE["link"]
    if link and not re.match(r"^(https?:|mailto:|tel:|/|#)", link):
        link = b + link
    a = f' <a href="{e(link)}">{e(ANNOUNCE["link_text"])} <i class="fa-solid fa-arrow-right"></i></a>' if link else ""
    return f"""
  <div class="announce" role="region" aria-label="Announcement">
    <div class="announce__inner"><span>{rich(ANNOUNCE["text"])}</span>{a}</div>
  </div>
"""

def header(b, active):
    act = ' class="is-active" aria-current="page"'
    links = "\n".join(f'        <a href="{b}{h}"{act if h == active else ""}>{t}</a>' for h, t in NAV)
    mlinks = "\n".join(f'    <a class="m-link" href="{b}{h}">{t} <i class="fa-solid fa-arrow-right"></i></a>' for h, t in NAV)
    dot = '<span class="dot"></span> '
    phones = "\n".join(
        f'        <a href="{o["tel"]}">{dot if i == 0 else ""}{e(o["region"])} <b>{e(o["phone"])}</b></a>'
        for i, o in enumerate(OFFICES))
    return f"""{announcement(b)}
  <div class="utility" role="complementary" aria-label="Contact information">
    <div class="utility__inner">
      <div class="utility__group">
{phones}
        <a class="hide-sm" href="mailto:{e(EMAIL)}"><i class="fa-regular fa-envelope"></i> {e(EMAIL)}</a>
      </div>
      <div class="utility__lic">Licensed &amp; Insured &middot; {LIC}</div>
    </div>
  </div>

  <header class="header">
    <div class="header__inner">
      <a href="{b}index.html" class="brand" aria-label="U.S. Construction &amp; Plumbing Authority — home">
        <img src="{b}assets/img/logo-108.png" alt="" width="54" height="49">
        <span class="brand__name"><strong>U.S. Construction &amp; Plumbing</strong><span>Authority</span></span>
      </a>
      <nav class="nav" aria-label="Main">
{links}
      </nav>
      <div class="header__actions">
        <a class="header__phone" href="{PRIMARY["tel"]}"><small>Call now</small><b>{e(PRIMARY["phone"])}</b></a>
        <a href="{b}schedule.html" class="btn btn--red btn--sm">Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
        <button class="hamburger" id="hamburger" aria-label="Open menu" aria-expanded="false" aria-controls="mobileMenu"><span></span><span></span><span></span></button>
      </div>
    </div>
  </header>

  <nav class="mobile-menu" id="mobileMenu" aria-label="Mobile">
{mlinks}
    <a href="{b}schedule.html" class="btn btn--red btn--block m-cta">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
    <a href="{PRIMARY["tel"]}" class="btn btn--glass btn--block"><i class="fa-solid fa-phone"></i> {e(PRIMARY["phone"])}</a>
  </nav>
"""

def final_cta(b, title=None, text=None):
    title = hd(CTA_HEADING) if title is None else title
    text = e(CTA_LEAD) if text is None else text
    cards = "\n".join(
        f'        <a class="contact-card" href="{o["tel"]}"><i class="ic fa-solid fa-phone"></i><div><small>{e(o["region"])}</small><strong>{e(o["phone"])}</strong></div><i class="go fa-solid fa-arrow-right"></i></a>'
        for o in OFFICES)
    return f"""
  <section class="final">
    <div class="container final__inner">
      <div class="reveal">
        <span class="kicker kicker--light">Free evaluation <span>&middot; No cost to you</span></span>
        <h2 class="h2">{title}</h2>
        <p class="lead">{text}</p>
        <div class="hero__actions"><a href="{b}schedule.html" class="btn btn--red">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a></div>
      </div>
      <div class="contact-cards reveal reveal-d1">
{cards}
        <a class="contact-card" href="mailto:{e(EMAIL)}"><i class="ic fa-solid fa-envelope"></i><div><small>Email</small><strong>{e(EMAIL).replace("@", "@<wbr>")}</strong></div><i class="go fa-solid fa-arrow-right"></i></a>
      </div>
    </div>
  </section>
"""

def footer(b):
    cols = []
    for i, o in enumerate(OFFICES):
        mail = f'\n            <li><a href="mailto:{e(EMAIL)}">{e(EMAIL)}</a></li>' if i == len(OFFICES) - 1 else ""
        cols.append(f"""        <div>
          <h2 class="footer__title">{e(o["region"])}</h2>
          <ul>
            <li>{e(o["street"])}<br>{e(o["city"])}, {e(o["state"])} {e(o["zip"])}</li>
            <li><a href="{o["tel"]}">{e(o["phone"])}</a></li>{mail}
          </ul>
        </div>""")
    office_cols = "\n".join(cols)
    return f"""
  <footer class="footer">
    <div class="container">
      <div class="footer__top"{f' style="--offices:{len(OFFICES)}"' if len(OFFICES) != 2 else ""}>
        <div class="footer__brand">
          <img src="{b}assets/img/logo-192.png" alt="U.S. Construction &amp; Plumbing Authority" width="96" height="87" loading="lazy">
          <p>{e(ABOUT_LINE)}</p>
          <a href="{b}schedule.html" class="btn btn--red btn--sm">Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
        </div>
        <div>
          <h2 class="footer__title">Divisions</h2>
          <ul>
            <li><a href="{b}plumbing.html">PSL Plumbing &amp; Drains</a></li>
            <li><a href="{b}electrical.html">Triphase Electrical</a></li>
            <li><a href="{b}building.html">U.S. Construction</a></li>
            <li><a href="{b}commercial.html">Commercial Clients</a></li>
            <li><a href="{b}schedule.html">Schedule an Evaluation</a></li>
          </ul>
        </div>
{office_cols}
      </div>
      <div class="footer__big" aria-hidden="true">U.S. Construction Authority</div>
      <div class="footer__bottom">
        <span>&copy; <span id="year">2026</span> {e(LEGAL_NAME)} All rights reserved.</span>
        <span>Licenses: {LIC}</span>
      </div>
    </div>
  </footer>

  <nav class="callbar" aria-label="Quick contact">
    <a href="{PRIMARY["tel"]}"><i class="fa-solid fa-phone"></i> Call Now</a>
    <a href="{b}schedule.html"><i class="fa-regular fa-calendar-check"></i> Free Estimate</a>
  </nav>

  <div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-labelledby="lbTitle" aria-hidden="true">
    <button type="button" class="lightbox__close" aria-label="Close diagram"><i class="fa-solid fa-xmark"></i></button>
    <div class="lightbox__inner">
      <div class="lightbox__stage"></div>
      <div class="lightbox__side"><h2 class="lightbox__title" id="lbTitle">Diagram</h2><p class="lightbox__text"></p><ol class="legend legend--dark"></ol></div>
    </div>
  </div>

  <script src="{b}assets/js/main.js"></script>
</body>
</html>
"""

HERO_RE = re.compile(r'(<section class="(?:hero|page-hero)"[\s\S]*?</section>)')

def _unreveal(m):
    # Hero content paints immediately (LCP); scroll reveals start below the fold.
    def clean(c):
        classes = [k for k in c.group(1).split() if k != "reveal" and not re.fullmatch(r"reveal-d\d", k)]
        return f' class="{" ".join(classes)}"' if classes else ""
    return re.sub(r' class="([^"]*)"', clean, m.group(1))

PAGES = []

def write(path, html):
    html = HERO_RE.sub(_unreveal, html, count=1)
    html = re.sub(r'<i class="([^"]*\bfa-[^"]*)">', r'<i class="\1" aria-hidden="true">', html)
    html = html.replace("<main>", '<main id="main" tabindex="-1">')
    with open(os.path.join(OUT, path), "w", encoding="utf-8") as f:
        f.write(html)
    PAGES.append(path)

def crumbs(items):
    """items: list of (href or None, label); the last one is the current page."""
    lis = []
    for i, (h, t) in enumerate(items):
        if i == len(items) - 1:
            lis.append(f'<li aria-current="page">{t}</li>')
        else:
            lis.append(f'<li><a href="{h}">{t}</a></li>')
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(lis)}</ol></nav>'

def kicker(num, label, light=False):
    return f'<span class="kicker{" kicker--light" if light else ""}">{num:02d} <span>&mdash; {e(label)}</span></span>'

def img_tag(src_name, b, alt, lazy=True, extra=""):
    for ext in (".jpg", ".png"):
        small = src_name[:-len(ext)] + "-800" + ext if src_name.endswith(ext) else None
        if small and os.path.exists(os.path.join(OUT, "assets", "img", small)):
            extra += f' srcset="{b}assets/img/{small} 800w, {b}assets/img/{src_name} {img_size(src_name)[0]}w" sizes="(max-width: 720px) 100vw, 800px"'
            break
    size = img_size(src_name)
    wh = f' width="{size[0]}" height="{size[1]}"' if size else ""
    lz = ' loading="lazy"' if lazy else ""
    return f'<img src="{b}assets/img/{src_name}" alt="{alt}"{wh}{lz}{extra}>'

def frame(key, b="", pins=True):
    """Diagram image, optionally with its numbered points layered on top."""
    img, title = DIAGRAMS[key][0], DIAGRAMS[key][1]
    layer = ""
    if pins and POINTS.get(key):
        items = "".join(
            f'<button type="button" class="pin{" pin--l" if x < 30 else " pin--r" if x > 70 else ""}{" pin--b" if y < 16 else ""}" style="left:{x}%;top:{y}%" data-n="{i}" aria-label="{i}. {label}">'
            f'<span aria-hidden="true">{i}</span><em class="pin__tip" aria-hidden="true">{label}</em></button>'
            for i, (x, y, label) in enumerate(POINTS[key], 1))
        layer = f'<div class="pins">{items}</div>'
    return f'<div class="dg-frame">{img_tag(img, b, title + " diagram")}{layer}</div>'

def legend(key, hidden=False):
    pts = POINTS.get(key, [])
    if not pts:
        return ""
    items = "".join(f'<li data-n="{i}"><b>{i}</b><span>{label}</span></li>' for i, (x, y, label) in enumerate(pts, 1))
    return f'<ol class="legend"{" hidden" if hidden else ""}>{items}</ol>'

def lb_attrs(key, button=True):
    _, title, text, _ = DIAGRAMS[key]
    role = f' role="button" tabindex="0" aria-label="Enlarge diagram: {attr(title)}"' if button else ""
    return f'data-lightbox data-title="{title}" data-text="{text}"{role}'

def lb_template(key, b=""):
    """Full-size diagram (with pins + legend) cloned into the lightbox on demand."""
    return f'<template class="dg-tpl">{frame(key, b)}{legend(key)}</template>'

def dg_card(key, tall=False):
    img, title, text, div = DIAGRAMS[key]
    n = len(POINTS.get(key, []))
    count = f'<span class="dg-card__count"><i class="fa-solid fa-location-dot"></i> {n} leak points</span>' if n else ""
    return f"""
        <article class="dg-card reveal{' dg-card--tall' if tall else ''}" id="dg-{key}">
          <div class="dg-card__img" {lb_attrs(key)}>
            {frame(key, pins=False)}{lb_template(key)}
            {count}<span class="dg-card__zoom"><i class="fa-solid fa-expand"></i></span>
          </div>
          <div class="dg-card__body"><small>{'Plumbing' if div == 'plumbing' else 'Electrical'}</small><h3>{title}</h3><p>{text}</p></div>
        </article>"""

def svc_card(division, s, b=""):
    slug, icon_cls, title, short = s[0], s[1], s[2], s[3]
    n = len(s[5])
    return f"""
        <a class="svc-card reveal" href="{b}services/{division}-{slug}.html">
          <span class="svc-card__icon"><i class="fa-solid {icon_cls}"></i></span>
          <h3>{title}</h3>
          <p>{short}</p>
          <span class="svc-card__foot">{n} service option{"" if n == 1 else "s"} <i class="fa-solid fa-arrow-right"></i></span>
        </a>"""

def gallery_section(category, num, b=""):
    """Project photos (all, or those of one division). Empty string when there are none."""
    items = [p for p in PROJECTS if category == "all" or p["category"] in (category, "all")]
    if not items:
        return ""
    figs = []
    for i, p in enumerate(items):
        full, small, w_, h_, sw = PHOTO[p["image"]]
        srcset = f' srcset="{b}{quote(small)} {sw}w, {b}{quote(full)} {w_}w" sizes="(max-width: 720px) 100vw, 400px"' if sw < w_ else ""
        cap = e(p["title"])
        figs.append(f"""
        <figure class="gallery__item reveal{' reveal-d1' if i % 3 == 1 else ' reveal-d2' if i % 3 == 2 else ''}" data-lightbox data-title="{cap}" data-text="" role="button" tabindex="0" aria-label="Enlarge photo: {cap}">
          <div class="dg-frame"><img src="{b}{quote(full)}" alt="{cap}" width="{w_}" height="{h_}" loading="lazy"{srcset}></div>
          <figcaption>{cap}</figcaption>
        </figure>""")
    intro = f'<p class="reveal reveal-d1">{e(GALLERY_INTRO)}</p>' if GALLERY_INTRO else ""
    return f"""
  <section class="section section--white" id="projects">
    <div class="container">
      <div class="head">
        <div class="reveal">{kicker(num, "Recent projects")}<h2 class="h2">{hd(GALLERY_HEADING)}</h2></div>
        {intro}
      </div>
      <div class="gallery">{"".join(figs)}
      </div>
    </div>
  </section>
"""

THERMAL_FILTER = """
  <svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
    <filter id="thermal-filter" color-interpolation-filters="sRGB">
      <feColorMatrix type="matrix" values="0.3 0.59 0.11 0 0  0.3 0.59 0.11 0 0  0.3 0.59 0.11 0 0  0 0 0 1 0"/>
      <feComponentTransfer>
        <feFuncR type="table" tableValues="1 1 1 0.85 0.45 0.12 0.03"/>
        <feFuncG type="table" tableValues="1 0.9 0.55 0.1 0.05 0.03 0.02"/>
        <feFuncB type="table" tableValues="0.9 0.35 0.02 0.16 0.45 0.35 0.14"/>
      </feComponentTransfer>
    </filter>
  </svg>"""

# ---------------------------------------------------------------- hero visual (illustrated cross-section)
HERO_SPOTS = [  # x %, y %, category, label, linked service (falls back to the division page if hidden/removed)
    (80, 22, "Plumbing", "Bathroom &amp; shower leaks", "plumbing", "shower-tub"),
    (37, 46, "Plumbing", "Kitchen plumbing", "plumbing", "faucets-fixtures"),
    (61, 66, "Plumbing", "Water heater", "plumbing", "water-heater"),
    (12, 64, "Plumbing", "Main shutoff valve", "plumbing", "main-shutoff-valve"),
    (91, 43, "Infrared", "Hidden leak detection", "plumbing", "leak-detection"),
    (40, 84, "Plumbing", "Sewer &amp; drain lines", "plumbing", "sewer-line"),
]

def service_href(division, slug, b=""):
    if slug in SERVICE_SLUGS.get(division, ()):
        return f"{b}services/{division}-{slug}.html"
    return f"{b}{division}.html"

def hero_visual():
    spots = "".join(
        f'<a class="hv-spot{" hv-spot--l" if x < 30 else " hv-spot--r" if x > 70 else ""}" href="{service_href(div, slug)}" style="left:{x}%;top:{y}%" aria-label="{attr(t)}">'
        f'<span class="hv-dot" aria-hidden="true"></span><span class="hv-tip" aria-hidden="true"><small>{c}</small>{t}</span></a>'
        for x, y, c, t, div, slug in HERO_SPOTS)
    return f"""
      <figure class="hero-visual">
        <div class="hero-visual__frame">
          {img_tag("dg-repiping.jpg", "", "Cross-section of a Florida home showing its plumbing system", lazy=False, extra=' fetchpriority="high"')}
          {spots}
        </div>
        <figcaption><span><i class="fa-solid fa-location-dot"></i> Select a point to see the related service</span><a href="plumbing.html">All services <i class="fa-solid fa-arrow-right"></i></a></figcaption>
      </figure>"""

# ================================================================== HOME
H = "content/home.yml"
hero = section(HOME, "hero", H)
stats = get(HOME, "stats", H, list)
divs = section(HOME, "divisions", H)
thermal = section(HOME, "thermal", H)
why = section(HOME, "why", H)
steps = section(HOME, "steps", H)
diag = section(HOME, "diagnostics", H)
com = section(HOME, "commercial", H)
about = section(HOME, "about", H)
areas = section(HOME, "areas", H)

def items(d, key, where):
    out = []
    for i, it in enumerate(get(d, key, where, list), 1):
        w = f"{where} → {key} {i}"
        out.append((get(it, "title", w), get(it, "text", w)))
    return out

DELAYS = ["", " reveal-d1", " reveal-d2", " reveal-d3"]
stat_html = "\n".join(
    f'        <div class="stat reveal{DELAYS[i % 4]}"><div class="stat__num">{e(get(s, "number", H + " → stats"))}{"<sup>+</sup>" if get(s, "plus", H, bool) else ""}</div><p>{e(get(s, "label", H + " → stats"))}</p></div>'
    for i, s in enumerate(stats))

def division_card(key, href, img, alt, icon_cls, tag_small, tag_strong, delay, extra_img=""):
    d = get(divs, key, H + " → divisions", dict)
    w = f"{H} → divisions → {key}"
    bullets = "".join(f"<li>{e(x)}</li>" for x in texts(d, "bullets", w))
    return f"""
        <a href="{href}" class="division reveal{delay}">
          <div class="division__media"><img src="assets/img/{img}" alt="{alt}" loading="lazy"{extra_img}>
            <span class="division__icon"><i class="fa-solid {icon_cls}"></i></span>
            <div class="division__tag"><small>{tag_small}</small><strong>{tag_strong}</strong></div></div>
          <div class="division__body">
            <h3>{e(get(d, "title", w))}</h3>
            <p>{e(get(d, "text", w))}</p>
            <ul class="division__list">{bullets}</ul>
            <span class="division__enter">Enter Here <i class="fa-solid fa-arrow-right"></i></span>
          </div>
        </a>"""

THERMAL_ICONS = ["fa-droplet", "fa-bolt", "fa-crosshairs", "fa-temperature-half"]
thermal_html = "\n".join(
    f'          <li><i class="fa-solid {THERMAL_ICONS[i % len(THERMAL_ICONS)]}"></i><div><strong>{e(t)}</strong><span>{e(x)}</span></div></li>'
    for i, (t, x) in enumerate(items(thermal, "points", H + " → thermal")))
why_html = "\n".join(
    f'        <li class="why__item reveal"><span class="why__num">{i:02d}</span><div><h3>{e(t)}</h3><p>{e(x)}</p></div></li>'
    for i, (t, x) in enumerate(items(why, "items", H + " → why"), 1))
steps_html = "\n".join(
    f'        <div class="process__step reveal{DELAYS[(i - 1) % 3]}"><div class="process__dot">{i}</div><h3>{e(t)}</h3><p>{e(x)}</p></div>'
    for i, (t, x) in enumerate(items(steps, "items", H + " → steps"), 1))
BENEFIT_ICONS = ["fa-person-digging", "fa-recycle", "fa-calendar-check", "fa-chart-line", "fa-clipboard-check", "fa-shield-halved"]
benefits_html = "\n".join(
    f'        <div class="benefit"><i class="fa-solid {BENEFIT_ICONS[i % len(BENEFIT_ICONS)]}"></i><strong>{e(t)}</strong><span>{e(x)}</span></div>'
    for i, (t, x) in enumerate(items(com, "benefits", H + " → commercial")))
about_paras = "\n".join(f"        <p>{rich(p)}</p>" for p in texts(about, "paragraphs", H + " → about"))
licenses_html = "\n".join(
    f'          <div class="license"><i class="fa-solid {LICENSE_ICONS[l["type"]]}"></i><small>{e(l["label"])}</small><strong>{e(l["number"])}</strong></div>'
    for l in LICENSES)

def map_src(o):
    q = f'{o["street"]}, {o["city"]}, {o["state"]} {o["zip"]}'
    return "https://maps.google.com/maps?q=" + quote_plus(q) + "&amp;z=13&amp;output=embed"

locations_html = "\n".join(f"""        <div class="location reveal{DELAYS[i % 2]}">
          <div class="location__map"><iframe title="Map — {attr(o["city"])} office" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="{map_src(o)}"></iframe></div>
          <div class="location__body"><div><small>{e(o["region"])}</small><h3>{e(o["city"])}</h3><p>{e(o["street"])}, {e(o["city"])}, {e(o["state"])} {e(o["zip"])}</p></div><a class="btn btn--dark btn--sm" href="{o["tel"]}"><i class="fa-solid fa-phone"></i> {e(o["phone"])}</a></div>
        </div>""" for i, o in enumerate(OFFICES))

home_gallery = gallery_section("all", 8)
areas_num = 9 if home_gallery else 8
trades = "".join(f"<span>{e(t)}</span>" for t in texts(hero, "trades", H + " → hero"))

home = f"""
  <main>
  <section class="hero">
    <div class="hero__bg"></div>
    <div class="container">
      <div class="hero__grid">
        <div>
          <span class="pill reveal"><b>{e(get(hero, "badge", H + " → hero"))}</b> {e(get(hero, "badge_text", H + " → hero"))}</span>
          <h1 class="reveal reveal-d1">{hd(get(hero, "heading", H + " → hero"))}</h1>
          <div class="hero__trades reveal reveal-d2">{trades}</div>
          <p class="hero__sub reveal reveal-d2">{rich(get(hero, "subtitle", H + " → hero"))}</p>
          <div class="hero__actions reveal reveal-d3">
            <a href="schedule.html" class="btn btn--red">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
            <a href="{PRIMARY["tel"]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {e(PRIMARY["phone"])}</a>
          </div>
        </div>
{hero_visual()}
      </div>

      <div class="stats">
{stat_html}
      </div>
    </div>
  </section>

  <section class="section">
    <div class="container">
      <div class="head">
        <div class="reveal">{kicker(1, get(divs, "label", H))}<h2 class="h2">{hd(get(divs, "heading", H))}</h2></div>
        <p class="reveal reveal-d1">{rich(get(divs, "intro", H))}</p>
      </div>
      <div class="divisions">{division_card("plumbing", "plumbing.html", "crop-kitchen.jpg", "Kitchen plumbing leak points", "fa-faucet-drip", "PSL Plumbing &amp; Drains", "Plumbing", "")}{division_card("electrical", "electrical.html", "crop-panel.jpg", "Electrical panel fault points", "fa-bolt", "Triphase", "Electrical", " reveal-d1", ' style="object-position:top"')}{division_card("building", "building.html", "crop-house.jpg", "Whole-house cross-section", "fa-helmet-safety", "U.S. Construction", "Building &amp; Remodeling", " reveal-d2")}
      </div>
    </div>
  </section>

  <section class="section dark">
    <div class="container thermal">
      <div class="reveal">
        {kicker(2, get(thermal, "label", H), light=True)}
        <h2 class="h2">{hd(get(thermal, "heading", H))}</h2>
        <p class="lead" style="margin-top:20px">{rich(get(thermal, "lead", H))}</p>
        <ul class="thermal__list">
{thermal_html}
        </ul>
        <a href="schedule.html" class="btn btn--white">Book an Infrared Evaluation <i class="fa-solid fa-arrow-right"></i></a>
      </div>
      <div class="reveal reveal-d1">
        <div class="compare" role="group" aria-label="Visual and infrared view comparison">
          <img src="assets/img/crop-water-heater.jpg" alt="Water heater, visual view" width="1254" height="1254" loading="lazy">
          <div class="compare__top"><img class="compare__ir" src="assets/img/crop-water-heater.jpg" alt="Water heater, simulated infrared view" width="1254" height="1254" loading="lazy"></div>
          <span class="compare__handle" aria-hidden="true"></span>
          <span class="compare__label compare__label--l" aria-hidden="true">Visual</span>
          <span class="compare__label compare__label--r" aria-hidden="true">Infrared</span>
          <div class="compare__scale" aria-hidden="true"><span>Cold</span><i></i><span>Hot</span></div>
          <input class="compare__range" type="range" min="0" max="100" value="46" aria-label="Slide to reveal the infrared view">
        </div>
        <p class="compare__note">Illustrative simulation of an infrared scan. Drag the handle to compare.</p>
      </div>
    </div>
  </section>

  <section class="section section--white">
    <div class="container why">
      <div class="why__sticky reveal">
        {kicker(3, get(why, "label", H))}
        <h2 class="h2">{hd(get(why, "heading", H))}</h2>
        <p class="lead">{rich(get(why, "lead", H))}</p>
        <a href="schedule.html" class="btn btn--dark">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
      </div>
      <ol class="why__list">
{why_html}
      </ol>
    </div>
  </section>

  <section class="section section--white" style="padding-top:0">
    <div class="container">
      <div class="head">
        <div class="reveal">{kicker(4, get(steps, "label", H))}<h2 class="h2">{hd(get(steps, "heading", H))}</h2></div>
        <p class="reveal reveal-d1">{rich(get(steps, "lead", H))}</p>
      </div>
      <div class="process">
{steps_html}
      </div>
    </div>
  </section>

  <section class="section">
    <div class="container">
      <div class="head">
        <div class="reveal">{kicker(5, get(diag, "label", H))}<h2 class="h2">{hd(get(diag, "heading", H))}</h2></div>
        <div class="reveal reveal-d1">
          <p style="margin-bottom:22px">{rich(get(diag, "lead", H))}</p>
          <div class="tabs" data-tabs role="tablist" aria-label="Diagram category">
            <button type="button" class="is-active" id="tab-plumbing" data-target="panel-plumbing" role="tab" aria-selected="true" aria-controls="panel-plumbing">Plumbing</button>
            <button type="button" id="tab-electrical" data-target="panel-electrical" role="tab" aria-selected="false" aria-controls="panel-electrical" tabindex="-1">Electrical</button>
          </div>
        </div>
      </div>
      <div class="dg-panel dg-grid is-active" id="panel-plumbing" role="tabpanel" aria-labelledby="tab-plumbing">{"".join(dg_card(k) for k in DIAGRAM_ORDER if DIAGRAMS[k][3] == "plumbing")}
      </div>
      <div class="dg-panel dg-grid dg-grid--4" id="panel-electrical" role="tabpanel" aria-labelledby="tab-electrical" hidden>{"".join(dg_card(k, True) for k in DIAGRAM_ORDER if DIAGRAMS[k][3] == "electrical")}
      </div>
    </div>
  </section>

  <section class="section dark dark--900">
    <div class="container commercial">
      <div class="reveal">
        {kicker(6, get(com, "label", H), light=True)}
        <h2 class="h2">{hd(get(com, "heading", H))}</h2>
        <p class="lead" style="margin-top:20px">{rich(get(com, "lead", H))}</p>
        <div class="hero__actions"><a href="commercial.html" class="btn btn--white">Commercial Services <i class="fa-solid fa-arrow-right"></i></a></div>
      </div>
      <div class="benefits reveal reveal-d1">
{benefits_html}
      </div>
    </div>
  </section>

  <section class="section" id="about">
    <div class="container about">
      <div class="about__text reveal">
        {kicker(7, get(about, "label", H))}
        <h2 class="h2">{hd(get(about, "heading", H))}</h2>
{about_paras}
        <div class="licenses">
{licenses_html}
        </div>
        <p class="corp">{e(get(about, "corporate_line", H))}</p>
      </div>
      <div class="about__card reveal reveal-d1">
        <img src="assets/img/logo-500.png" alt="U.S. Construction &amp; Plumbing Authority logo" width="400" height="364" loading="lazy">
        <blockquote>&ldquo;{e(get(about, "quote", H))}&rdquo;</blockquote>
        <cite>{e(SITE_NAME)}</cite>
      </div>
    </div>
  </section>
{home_gallery}
  <section class="section section--white">
    <div class="container">
      <div class="head">
        <div class="reveal">{kicker(areas_num, get(areas, "label", H))}<h2 class="h2">{hd(get(areas, "heading", H))}</h2></div>
        <p class="reveal reveal-d1">{rich(get(areas, "lead", H))}</p>
      </div>
      <div class="locations">
{locations_html}
      </div>
    </div>
  </section>
{final_cta("")}
  </main>
{THERMAL_FILTER}
"""

# ================================================================== DIVISION PAGES
P = "content/pages.yml"

def division_page(fname, active, crumb, page_key, media, media_cap, tall, services, division, cta_title, title, desc):
    txt = section(PAGES_TXT, page_key, P)
    w = f"{P} → {page_key}"
    diagrams = [k for k in DIAGRAM_ORDER if DIAGRAMS[k][3] == division]
    dg_note = "Click any diagram to explore every numbered leak point." if any(POINTS.get(k) for k in diagrams) else "Click any diagram to enlarge it and see where faults commonly occur."
    grid = "".join(svc_card(division, s) for s in services)
    dgs = "".join(dg_card(k, tall) for k in diagrams)
    media_key = next((k for k, v in DIAGRAMS.items() if v[0] == media), None)
    if media_key:
        media_attrs = lb_attrs(media_key)
        media_html = frame(media_key, pins=False) + lb_template(media_key)
    else:
        media_attrs = f'data-lightbox data-title="{media_cap}" data-text="" role="button" tabindex="0" aria-label="Enlarge image: {attr(media_cap)}"'
        media_html = f'<div class="dg-frame">{img_tag(media, "", attr(media_cap), lazy=False)}</div>'
    body = f"""
  <main>
  <section class="page-hero">
    <div class="hero__bg"></div>
    <div class="container page-hero__grid">
      <div>
        {crumbs([("index.html", "Home"), (None, crumb)])}
        <h1 class="reveal reveal-d1">{hd(get(txt, "heading", w))}</h1>
        <p class="lead reveal reveal-d2">{rich(get(txt, "lead", w))}</p>
        <div class="hero__actions reveal reveal-d3">
          <a href="schedule.html?division={division}" class="btn btn--red">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{PRIMARY["tel"]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {e(PRIMARY["phone"])}</a>
        </div>
        <div class="mini-trust reveal reveal-d3"><span><i class="fa-solid fa-shield-halved"></i> Licensed &amp; insured</span><span><i class="fa-solid fa-temperature-half"></i> Infrared diagnostics</span><span><i class="fa-solid fa-file-invoice-dollar"></i> Transparent estimates</span></div>
      </div>
      <figure class="page-hero__media{' page-hero__media--tall' if tall else ''} reveal reveal-d2" {media_attrs}>
        {media_html}
        <figcaption><span>{media_cap}</span><i class="fa-solid fa-expand"></i></figcaption>
      </figure>
    </div>
  </section>

  <section class="section">
    <div class="container">
      <div class="head">
        <div class="reveal"><span class="kicker">01 <span>&mdash; Services we provide</span></span><h2 class="h2">What can we <em>fix for you?</em></h2></div>
        <p class="reveal reveal-d1">A partial list of the services we offer. Select a service to see what&rsquo;s included, common reasons to call and related diagrams where available.</p>
      </div>
      <div class="svc-grid">{grid}
      </div>
    </div>
  </section>

  <section class="section section--white">
    <div class="container">
      <div class="head">
        <div class="reveal"><span class="kicker">02 <span>&mdash; Visual diagnostics</span></span><h2 class="h2">Know where <em>problems start.</em></h2></div>
        <p class="reveal reveal-d1">{dg_note}</p>
      </div>
      <div class="dg-panel dg-grid{' dg-grid--4' if tall else ''} is-active">{dgs}
      </div>
    </div>
  </section>
{gallery_section(division, 3)}{final_cta("", hd(get(txt, "cta_heading", w)))}
  </main>
"""
    write(fname, head("", title, desc, fname) + header("", active) + body + footer(""))

repiping_pins = len(POINTS.get("repiping", []))
division_page("plumbing.html", "plumbing.html", "Plumbing Division", "plumbing",
    "dg-repiping.jpg", f"Whole-house plumbing &mdash; {repiping_pins} leak points" if repiping_pins else "Whole-house plumbing", False, PLUMBING, "plumbing",
    None, "Plumbing Services | PSL Plumbing & Drains",
    "Leak detection, drain clearing, water heaters, re-piping, sewer lines, toilets and faucets. Licensed & insured plumbers serving Florida's Treasure Coast and Gold Coast.")

division_page("electrical.html", "electrical.html", "Electrical Division", "electrical",
    "crop-panel.jpg", "Circuit breaker panel &mdash; fault points", True, ELECTRICAL, "electrical",
    None, "Electrical Services | Triphase Electrical",
    "Breaker panel corrections, circuits, lighting, ceiling fans, receptacles, generators and thermal-imaging diagnostics by licensed electricians in Florida.")

# ================================================================== SERVICE PAGES
def service_page(division, s, siblings):
    slug, icon_cls, title, short, intro, options, signs, dg = s
    b = "../"
    div_name = "Plumbing" if division == "plumbing" else "Electrical"
    div_brand = "PSL Plumbing &amp; Drains" if division == "plumbing" else "Triphase Electrical"
    opts = "".join(f'<div class="option"><i class="fa-solid fa-check"></i>{o}</div>' for o in options)
    sg = "".join(f'<li><i class="fa-solid fa-circle-exclamation"></i>{x}</li>' for x in signs)
    fig = ""
    if dg:
        img, dtitle, dtext, _ = DIAGRAMS[dg]
        fig = f"""
        <div class="detail__block reveal">
          <span class="kicker">Diagram</span>
          <h2 style="margin-top:12px">{dtitle}</h2>
          <figure class="detail__figure{' detail__figure--tall' if DIAGRAMS[dg][3] == 'electrical' else ''}" {lb_attrs(dg, button=False)}>
            {frame(dg, b)}{lb_template(dg, b)}
            <figcaption><i class="fa-solid fa-circle-info"></i><span>{dtext} {'Hover or tap a number to see each point. ' if POINTS.get(dg) else ''}</span><button type="button" class="dg-enlarge" data-open-lightbox><i class="fa-solid fa-expand"></i> Enlarge</button></figcaption>
          </figure>
          {legend(dg)}
        </div>"""
    rel = "".join(f'<a href="{division}-{x[0]}.html">{x[2]} <i class="fa-solid fa-arrow-right"></i></a>' for x in siblings if x[0] != slug)
    related = f"""
  <section class="section section--white">
    <div class="container">
      <div class="head head--stack reveal"><span class="kicker">More {div_name.lower()} services</span><h2 class="h2">Other ways <em>we can help.</em></h2></div>
      <div class="related">{rel}</div>
    </div>
  </section>
""" if rel else ""
    plain_title = unescape(title)
    q = quote_plus(plain_title)
    phones = "\n".join(f'          <a href="{o["tel"]}">{e(o["region"])} <b>{e(o["phone"])}</b></a>' for o in OFFICES)
    body = f"""
  <main>
  <section class="page-hero">
    <div class="hero__bg"></div>
    <div class="container page-hero__grid page-hero__grid--solo">
      <div>
        {crumbs([(b + "index.html", "Home"), (b + division + ".html", div_name), (None, title)])}
        <h1 class="reveal reveal-d1">{title}</h1>
        <p class="lead reveal reveal-d2">{intro}</p>
        <div class="hero__actions reveal reveal-d3">
          <a href="{b}schedule.html?division={division}&amp;service={q}" class="btn btn--red">Request This Service <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{PRIMARY["tel"]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {e(PRIMARY["phone"])}</a>
        </div>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="container detail">
      <div>
        <div class="detail__block reveal">
          <span class="kicker">What we handle</span>
          <h2 style="margin-top:12px">Service options</h2>
          <div class="options">{opts}</div>
        </div>
        <div class="detail__block reveal">
          <span class="kicker">Common reasons to call</span>
          <h2 style="margin-top:12px">When to call us</h2>
          <ul class="signs">{sg}</ul>
        </div>{fig}
      </div>
      <aside class="aside reveal reveal-d1" aria-label="Free on-site evaluation">
        <span class="kicker kicker--light">{div_brand}</span>
        <h3 style="margin-top:12px">Free on-site evaluation</h3>
        <p>One of our officers will call you to schedule a visit to evaluate your project at no cost to you.</p>
        <a href="{b}schedule.html?division={division}&amp;service={q}" class="btn btn--red btn--block">Schedule Now <i class="fa-solid fa-arrow-right"></i></a>
        <div class="aside__phones">
{phones}
        </div>
        <div class="aside__lic">Licensed &amp; insured &middot; {LIC}</div>
      </aside>
    </div>
  </section>
{related}{final_cta(b)}
  </main>
"""
    short_plain = plain(unescape(short))
    states = sorted({o["state"] for o in OFFICES})
    cities = " & ".join(o["city"] for o in OFFICES) + (f", {states[0]}" if len(states) == 1 else "")
    desc = f"{plain_title} in {cities}. {short_plain} Licensed & insured {div_name.lower()} contractors. Free on-site evaluation."
    if len(desc) > 160:
        desc = f"{plain_title} in {cities}. {short_plain} Free on-site evaluation."
    if len(desc) > 160:
        desc = desc[:157].rsplit(" ", 1)[0] + "…"
    html = head(b, f"{plain_title} | {div_brand.replace('&amp;', '&')}", desc, f"services/{division}-{slug}.html") + header(b, f"{division}.html") + body + footer(b)
    write(f"services/{division}-{slug}.html", html)

for s in PLUMBING: service_page("plumbing", s, PLUMBING)
for s in ELECTRICAL: service_page("electrical", s, ELECTRICAL)

# ================================================================== BUILDING
BW = f"{P} → building"
btxt = section(PAGES_TXT, "building", P)
bcards = []
for i, c in enumerate(get(btxt, "services", BW, list), 1):
    w = f"{BW} → services {i}"
    t_ = get(c, "title", w)
    bcards.append(f"""
        <a class="svc-card reveal" href="schedule.html?division=building&amp;service={quote_plus(t_)}">
          <span class="svc-card__icon"><i class="fa-solid {icon(get(c, "icon", w), w)}"></i></span>
          <h3>{e(t_)}</h3><p>{e(get(c, "text", w))}</p>
          <span class="svc-card__foot">Request an Evaluation <i class="fa-solid fa-arrow-right"></i></span>
        </a>""")
insp_html = "\n".join(
    f'        <li class="why__item reveal"><span class="why__num">{i:02d}</span><div><h3>{e(t)}</h3><p>{e(x)}</p></div></li>'
    for i, (t, x) in enumerate(items(btxt, "inspections", BW), 1))
building_gallery = gallery_section("building", 3)
building = f"""
  <main>
  <section class="page-hero">
    <div class="hero__bg"></div>
    <div class="container page-hero__grid">
      <div>
        {crumbs([("index.html", "Home"), (None, "Building &amp; Remodeling Division")])}
        <h1 class="reveal reveal-d1">{hd(get(btxt, "heading", BW))}</h1>
        <p class="lead reveal reveal-d2">{rich(get(btxt, "lead", BW))}</p>
        <div class="hero__actions reveal reveal-d3">
          <a href="schedule.html?division=building" class="btn btn--red">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{PRIMARY["tel"]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {e(PRIMARY["phone"])}</a>
        </div>
        <div class="mini-trust reveal reveal-d3"><span><i class="fa-solid fa-building"></i> {next((e(l["number"]) for l in LICENSES if l["type"] == "building"), "Licensed &amp; insured")}</span><span><i class="fa-solid fa-clipboard-check"></i> Permitting support</span><span><i class="fa-solid fa-temperature-half"></i> Infrared inspections</span></div>
      </div>
      <figure class="page-hero__media page-hero__media--static">
        <div class="dg-frame">{img_tag("crop-house.jpg", "", "Cross-section of a home showing its plumbing and building systems", lazy=False)}</div>
        <figcaption><span>Every system, one team</span></figcaption>
      </figure>
    </div>
  </section>

  <section class="section">
    <div class="container">
      <div class="head">
        <div class="reveal"><span class="kicker">01 <span>&mdash; Services</span></span><h2 class="h2">{hd(get(btxt, "services_heading", BW))}</h2></div>
        <p class="reveal reveal-d1">{rich(get(btxt, "services_intro", BW))}</p>
      </div>
      <div class="svc-grid" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">{"".join(bcards)}
      </div>
    </div>
  </section>

  <section class="section section--white">
    <div class="container why">
      <div class="why__sticky reveal">
        <span class="kicker">02 <span>&mdash; Building inspections</span></span>
        <h2 class="h2">{hd(get(btxt, "inspections_heading", BW))}</h2>
        <p class="lead">{rich(get(btxt, "inspections_lead", BW))}</p>
      </div>
      <ol class="why__list">
{insp_html}
      </ol>
    </div>
  </section>
{building_gallery}{final_cta("", hd(get(btxt, "cta_heading", BW)))}
  </main>
"""
write("building.html", head("", "Building & Remodeling | U.S. Construction",
      "Remodeling, building inspections and trade work by licensed & insured builders on Florida's Treasure Coast and Gold Coast. Free on-site evaluations.", "building.html") + header("", "building.html") + building + footer(""))

# ================================================================== COMMERCIAL
CW = f"{P} → commercial"
ctxt = section(PAGES_TXT, "commercial", P)
pro_html = "\n".join(
    f'        <li class="why__item reveal"><span class="why__num">{i:02d}</span><div><h3>{e(t)}</h3><p>{e(x)}</p></div></li>'
    for i, (t, x) in enumerate(items(ctxt, "proactive", CW), 1))
RISK_ICONS = ["fa-house-flood-water", "fa-file-shield", "fa-lungs", "fa-person-digging", "fa-shield-halved", "fa-clipboard-check"]
risk_html = "\n".join(
    f'        <div class="benefit"><i class="fa-solid {RISK_ICONS[i % len(RISK_ICONS)]}"></i><strong>{e(t)}</strong><span>{e(x)}</span></div>'
    for i, (t, x) in enumerate(items(ctxt, "risks", CW)))
lic_of = {l["type"]: e(l["number"]) for l in LICENSES}
commercial = f"""
  <main>
  <section class="page-hero">
    <div class="hero__bg"></div>
    <div class="container page-hero__grid page-hero__grid--solo">
      <div>
        {crumbs([("index.html", "Home"), (None, "Commercial Clients")])}
        <h1 class="reveal reveal-d1">{hd(get(ctxt, "heading", CW))}</h1>
        <p class="lead reveal reveal-d2">{rich(get(ctxt, "lead", CW))}</p>
        <div class="hero__actions reveal reveal-d3">
          <a href="schedule.html?division=commercial" class="btn btn--red">Request a Site Evaluation <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{PRIMARY["tel"]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {e(PRIMARY["phone"])}</a>
        </div>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="container why">
      <div class="why__sticky reveal">
        <span class="kicker">01 <span>&mdash; Proactive evaluations</span></span>
        <h2 class="h2">{hd(get(ctxt, "proactive_heading", CW))}</h2>
        <p class="lead">{rich(get(ctxt, "proactive_lead", CW))}</p>
      </div>
      <ol class="why__list">
{pro_html}
      </ol>
    </div>
  </section>

  <section class="section dark dark--900">
    <div class="container commercial">
      <div class="reveal">
        <span class="kicker kicker--light">02 <span>&mdash; Risk reduction</span></span>
        <h2 class="h2">{hd(get(ctxt, "risk_heading", CW))}</h2>
      </div>
      <div class="benefits reveal reveal-d1">
{risk_html}
      </div>
    </div>
  </section>

  <section class="section">
    <div class="container">
      <div class="head">
        <div class="reveal"><span class="kicker">03 <span>&mdash; One partner, every trade</span></span><h2 class="h2">Plumbing, electrical <em>&amp; building.</em></h2></div>
        <p class="reveal reveal-d1">Licensed divisions that work together on your project.</p>
      </div>
      <div class="svc-grid">
        <a class="svc-card reveal" href="plumbing.html"><span class="svc-card__icon"><i class="fa-solid fa-faucet-drip"></i></span><h3>PSL Plumbing &amp; Drains</h3><p>Leak detection, re-piping, drains, sewer lines and water heaters.</p><span class="svc-card__foot">{lic_of.get("plumbing", "Licensed &amp; insured")} <i class="fa-solid fa-arrow-right"></i></span></a>
        <a class="svc-card reveal reveal-d1" href="electrical.html"><span class="svc-card__icon"><i class="fa-solid fa-bolt"></i></span><h3>Triphase Electrical</h3><p>Panels, circuits, lighting, generators and thermal diagnostics.</p><span class="svc-card__foot">{lic_of.get("electrical", "Licensed &amp; insured")} <i class="fa-solid fa-arrow-right"></i></span></a>
        <a class="svc-card reveal reveal-d2" href="building.html"><span class="svc-card__icon"><i class="fa-solid fa-helmet-safety"></i></span><h3>U.S. Construction</h3><p>Remodeling, building inspections, trade work and permitting.</p><span class="svc-card__foot">{lic_of.get("building", "Licensed &amp; insured")} <i class="fa-solid fa-arrow-right"></i></span></a>
      </div>
    </div>
  </section>
{gallery_section("commercial", 4)}{final_cta("", hd(get(ctxt, "cta_heading", CW)), rich(get(ctxt, "cta_lead", CW)))}
  </main>
"""
write("commercial.html", head("", "Commercial Services | U.S. Construction & Plumbing Authority",
      "Commercial plumbing, electrical and building services that reduce labor costs, on-site corrections and delays. Keep schedules on time and on budget.", "commercial.html") + header("", "commercial.html") + commercial + footer(""))

# ================================================================== SCHEDULE
SW = f"{P} → schedule"
stxt = section(PAGES_TXT, "schedule", P)
info_phones = "\n".join(
    f'          <li><i class="fa-solid fa-phone"></i><div><small>{e(o["region"])}</small><a href="{o["tel"]}">{e(o["phone"])}</a></div></li>'
    for o in OFFICES)
states = sorted({o["state"] for o in OFFICES})
offices_line = " &amp; ".join(e(o["city"]) for o in OFFICES) + (f", {e(states[0])}" if len(states) == 1 else "")
call_links = " or ".join(f'<a href="{o["tel"]}">{e(o["phone"])}</a>' for o in OFFICES)
schedule = f"""
  <main>
  <section class="page-hero" style="padding-bottom:120px">
    <div class="hero__bg"></div>
    <div class="container form-shell" style="position:relative">
      <div>
        {crumbs([("index.html", "Home"), (None, "Schedule")])}
        <h1 class="reveal reveal-d1">{hd(get(stxt, "heading", SW))}</h1>
        <p class="lead reveal reveal-d2">{rich(get(stxt, "lead", SW))}</p>
        <ul class="info-list reveal reveal-d3">
{info_phones}
          <li><i class="fa-solid fa-envelope"></i><div><small>Email</small><a href="mailto:{e(EMAIL)}">{e(EMAIL)}</a></div></li>
          <li><i class="fa-solid fa-location-dot"></i><div><small>Offices</small><strong>{offices_line}</strong></div></li>
        </ul>
      </div>
      <div class="form-card reveal reveal-d1">
        <h2>Free evaluation / estimate</h2>
        <p>No cost. No obligation. We&rsquo;ll call you to confirm your visit.</p>
        <form id="appointmentForm" novalidate data-email="{e(EMAIL)}">
          <fieldset class="field">
            <legend>What do you need help with?</legend>
            <div class="chips">
              <label><input type="radio" name="division" value="plumbing" checked><span><i class="fa-solid fa-faucet-drip"></i> Plumbing</span></label>
              <label><input type="radio" name="division" value="electrical"><span><i class="fa-solid fa-bolt"></i> Electrical</span></label>
              <label><input type="radio" name="division" value="building"><span><i class="fa-solid fa-helmet-safety"></i> Building &amp; Remodeling</span></label>
              <label><input type="radio" name="division" value="commercial"><span><i class="fa-solid fa-city"></i> Commercial</span></label>
            </div>
          </fieldset>
          <div class="field"><label for="firstName">First name</label><input id="firstName" name="firstName" required autocomplete="given-name"></div>
          <div class="field-row">
            <div class="field"><label for="email">Email address</label><input id="email" name="email" type="email" required autocomplete="email"></div>
            <div class="field"><label for="phone">Phone number</label><input id="phone" name="phone" type="tel" required autocomplete="tel"></div>
          </div>
          <div class="field"><label for="bestTime">Best time to call</label>
            <select id="bestTime" name="bestTime" required>
              <option value="">Select a time&hellip;</option><option>Morning (8am &ndash; 12pm)</option><option>Afternoon (12pm &ndash; 4pm)</option><option>Evening (4pm &ndash; 7pm)</option><option>Anytime</option>
            </select></div>
          <div class="field"><label for="details">Tell us about your project <span style="color:var(--muted);font-weight:500">(optional)</span></label><textarea id="details" name="details" rows="4"></textarea></div>
          <div class="captcha">
            <label><input type="checkbox" required> I&rsquo;m not a robot</label>
            <small><i class="fa-solid fa-rotate"></i><br>reCAPTCHA</small>
          </div>
          <button type="submit" class="btn btn--red btn--block">Request My Free Evaluation <i class="fa-solid fa-arrow-right"></i></button>
          <p class="form-note">Prefer to talk? Call {call_links}</p>
          <p class="form-privacy">We use your information only to respond to your request.</p>
        </form>
        <div class="form-success" role="status">
          <i class="fa-solid fa-circle-check"></i>
          <h2 tabindex="-1">Thank you!</h2>
          <p>Your email app should open with your request ready to send. Please press <strong>Send</strong> in your email app &mdash; one of our officers will then call you to schedule your free evaluation.</p>
          <p class="form-fallback">Email didn&rsquo;t open? Write to <a href="mailto:{e(EMAIL)}">{e(EMAIL)}</a> or call <a href="{PRIMARY["tel"]}">{e(PRIMARY["phone"])}</a>.</p>
          <button type="button" class="btn btn--line-dark btn--sm" data-edit-request>Edit My Request</button>
        </div>
      </div>
    </div>
  </section>
  </main>
"""
write("schedule.html", head("", "Schedule a Free Evaluation | U.S. Construction Authority",
      "Request a complimentary site visit. One of our officers will call you to schedule a free evaluation of your plumbing, electrical or building project.", "schedule.html") + header("", "") + schedule + footer(""))

# ================================================================== HOME (written after the division pages so all data is validated)
write("index.html", head("", "U.S. Construction & Plumbing Authority | Florida Contractor",
      "Licensed & insured plumbing, electrical, remodeling, building inspections and trade work on Florida's Treasure Coast and Gold Coast. Free on-site evaluations.",
      "index.html", schema=True)
      + header("", "index.html") + home + footer(""))

# ================================================================== 404
not_found = f"""
  <main>
  <section class="page-hero" style="padding-bottom:120px">
    <div class="hero__bg"></div>
    <div class="container page-hero__grid page-hero__grid--solo">
      <div>
        <span class="kicker kicker--light">Error 404</span>
        <h1>This page <em>isn&rsquo;t here.</em></h1>
        <p class="lead">The page you&rsquo;re looking for may have moved. Try one of our divisions below or call us &mdash; we&rsquo;re happy to help.</p>
        <div class="hero__actions">
          <a href="/index.html" class="btn btn--red">Back to Home <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{PRIMARY["tel"]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {e(PRIMARY["phone"])}</a>
        </div>
        <ul class="notfound-links">
          <li><a href="/plumbing.html">Plumbing</a></li><li><a href="/electrical.html">Electrical</a></li>
          <li><a href="/building.html">Building &amp; Remodeling</a></li><li><a href="/commercial.html">Commercial</a></li>
          <li><a href="/schedule.html">Schedule a Free Evaluation</a></li>
        </ul>
      </div>
    </div>
  </section>
  </main>
"""
# 404 is served for any missing path, so it uses root-absolute URLs.
nf = head("/", "Page Not Found | U.S. Construction & Plumbing Authority", "The page you were looking for could not be found.") \
     .replace("<head>", '<head>\n  <meta name="robots" content="noindex">') + header("/", "") + not_found + footer("/")
write("404.html", nf)
PAGES.remove("404.html")

# ================================================================== robots.txt + sitemap.xml + host headers
robots = "User-agent: *\nAllow: /\n"
if SITE_URL:
    robots += f"\nSitemap: {SITE_URL}/sitemap.xml\n"
    urls = "".join(f"  <url><loc>{public_url(p)}</loc></url>\n" for p in PAGES)
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
    f.write(robots)

# Cloudflare Pages reads _headers (Vercel reads vercel.json; both carry the same rules)
with open(os.path.join(OUT, "_headers"), "w", encoding="utf-8") as f:
    f.write("""/assets/fonts/*
  Cache-Control: public, max-age=31536000, immutable

/assets/img/*
  Cache-Control: public, max-age=86400, stale-while-revalidate=604800

/assets/css/*
  Cache-Control: public, max-age=86400, stale-while-revalidate=604800

/assets/js/*
  Cache-Control: public, max-age=86400, stale-while-revalidate=604800

/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
""")

# ================================================================== icon subset (Font Awesome, only glyphs in use)
def build_icons():
    fa_css = open(os.path.join(SRC, "fontawesome", "css", "all.min.css"), encoding="utf-8").read()
    used = set()
    for p in PAGES + ["404.html"]:
        used |= set(re.findall(r"\bfa-([a-z0-9-]+)", open(os.path.join(OUT, p), encoding="utf-8").read()))
    used -= {"solid", "regular", "brands"}
    rules, codes = [], set()
    glyph = {}
    for sels, code in re.findall(r'([^{}]+)\{content:"\\([0-9a-f]+)"\}', fa_css):
        for sel in sels.split(","):
            m = re.fullmatch(r"\s*\.fa-([a-z0-9-]+):before\s*", sel)
            if m:
                glyph.setdefault(m.group(1), code)
    for name in sorted(used):
        if name in glyph:
            rules.append(f'.fa-{name}:before{{content:"\\{glyph[name]}"}}')
            codes.add(int(glyph[name], 16))
    for extra in re.findall(r"content:\s*'\\(f[0-9a-f]{3})'", open(os.path.join(OUT, "assets", "css", "styles.css"), encoding="utf-8").read()):
        codes.add(int(extra, 16))
    from fontTools import subset
    for style, weight in (("solid", 900), ("regular", 400)):
        opts = subset.Options(); opts.flavor = "woff2"; opts.layout_features = ["*"]
        font = subset.load_font(os.path.join(SRC, "fontawesome", "webfonts", f"fa-{style}-{weight}.woff2"), opts)
        sub = subset.Subsetter(opts); sub.populate(unicodes=codes); sub.subset(font)
        subset.save_font(font, os.path.join(OUT, "assets", "fonts", f"fa-{style}-subset.woff2"), opts)
    css = ("/* Font Awesome Free 6.5.1 subset (icons: CC BY 4.0, fonts: SIL OFL 1.1, code: MIT). Generated by _source/build.py */\n"
           "@font-face{font-family:\"Font Awesome 6 Free\";font-style:normal;font-weight:900;font-display:block;src:url(../fonts/fa-solid-subset.woff2) format(\"woff2\")}\n"
           "@font-face{font-family:\"Font Awesome 6 Free\";font-style:normal;font-weight:400;font-display:block;src:url(../fonts/fa-regular-subset.woff2) format(\"woff2\")}\n"
           ".fa-solid,.fa-regular{-moz-osx-font-smoothing:grayscale;-webkit-font-smoothing:antialiased;display:inline-block;font-style:normal;font-variant:normal;line-height:1;text-rendering:auto;font-family:\"Font Awesome 6 Free\"}\n"
           ".fa-solid{font-weight:900}.fa-regular{font-weight:400}\n" + "".join(rules) + "\n")
    with open(os.path.join(OUT, "assets", "css", "icons.css"), "w", encoding="utf-8") as f:
        f.write(css)
    return len(rules)

n_icons = build_icons()
stop_on_errors()
shutil.rmtree(FINAL_OUT, ignore_errors=True)
os.rename(OUT, FINAL_OUT)
print(f"OK: {len(PAGES)} pages, {len(PLUMBING)} plumbing + {len(ELECTRICAL)} electrical services, "
      f"{len(PROJECTS)} gallery photos, {n_icons} icons -> {os.path.relpath(FINAL_OUT, ROOT)}/  (SITE_URL: {SITE_URL or 'not set'})")

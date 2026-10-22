"""Writes ../.pages.yml (Pages CMS editing panel, Spanish labels).

Run after changing ICONS in build.py or _source/diagrams.yml:  python3 _source/make_pages_config.py
"""
import os
import yaml

ACCENT = "Escribe entre *asteriscos* las palabras que quieres en rojo e itálica."
RICH = "Usa **doble asterisco** para negrita y *un asterisco* para itálica."

ICONS = [
    ("faucet", "Grifo"), ("faucet-drip", "Grifo goteando"), ("droplet", "Gota de agua"), ("shower", "Ducha"),
    ("toilet", "Inodoro"), ("sink", "Lavamanos"), ("fire-flame-simple", "Llama (calentador)"), ("filter", "Filtro de agua"),
    ("house-flood-water", "Inundación"), ("grip-lines", "Tuberías / líneas"), ("gauge-simple", "Medidor de presión"),
    ("gears", "Engranajes (triturador)"), ("soap", "Jabón (lavadora)"), ("glass-water", "Vaso de agua"),
    ("wrench", "Llave inglesa"), ("screwdriver-wrench", "Herramientas"), ("toolbox", "Caja de herramientas"),
    ("bolt", "Rayo (electricidad)"), ("plug", "Enchufe"), ("lightbulb", "Bombillo"), ("fan", "Ventilador de techo"),
    ("sun", "Sol / luz exterior"), ("power-off", "Sin electricidad"), ("toggle-on", "Interruptor"),
    ("table-cells", "Panel eléctrico"), ("server", "Gabinete / panel"), ("ethernet", "Tomacorriente"),
    ("code-branch", "Circuitos"), ("car-battery", "Generador / batería"), ("temperature-arrow-up", "Temperatura alta"),
    ("temperature-half", "Termómetro"), ("triangle-exclamation", "Advertencia / peligro"),
    ("house-chimney-window", "Casa"), ("trowel-bricks", "Ladrillos (remodelación)"), ("magnifying-glass", "Lupa (inspección)"),
    ("file-signature", "Documento firmado (permisos)"), ("helmet-safety", "Casco de obra"), ("hammer", "Martillo"),
    ("paint-roller", "Rodillo de pintura"), ("ruler-combined", "Regla (medidas)"), ("building", "Edificio"),
    ("city", "Ciudad (comercial)"), ("shield-halved", "Escudo (seguridad)"), ("clipboard-check", "Lista de verificación"),
]
DIAGRAMS = [  # key, Spanish label, number of numbered points on the image
    ("water-heater", "Calentador de agua", 21), ("bathtub", "Baño con tina", 20), ("shower", "Baño con ducha", 21),
    ("kitchen", "Cocina", 23), ("repiping", "Casa completa (re-piping)", 22), ("sewer", "Líneas de drenaje y alcantarillado", 0),
    ("panel", "Panel de breakers", 0), ("disconnect", "Interruptor de desconexión", 0),
    ("fixtures", "Lámparas y ventiladores de techo", 0), ("receptacles", "Tomacorrientes e interruptores", 0),
]

def opts(pairs):
    return {"values": [{"value": v, "label": l} for v, l in pairs]}

# Pages CMS counts a single space as "filled in"; the build doesn't, so required text must contain a character
NONBLANK = {"regex": r"\S", "message": "Escribe algo (no solo espacios)"}

def s(name, label, description=None, required=True, **extra):
    f = {"name": name, "label": label, "type": "string"}
    if description:
        f["description"] = description
    if required:
        f["required"] = True
        f["pattern"] = dict(NONBLANK)
    f.update(extra)
    return f

def t(name, label, description=None, required=True, **extra):
    f = s(name, label, description, required, **extra)
    f["type"] = "text"
    return f

def strings(name, label, description=None, required=True, item="text"):
    f = {"name": name, "label": label, "type": item, "list": True}
    if description:
        f["description"] = description
    if required:
        f["required"] = True
        f["pattern"] = dict(NONBLANK)
    return f

def obj(name, label, fields, description=None, required=True):
    # Required, so Pages CMS checks the inner fields even when every one of them was emptied
    f = {"name": name, "label": label, "type": "object", "fields": fields}
    if description:
        f["description"] = description
    if required:
        f["required"] = True
    return f

def objlist(name, label, fields, summary="{fields.title}", description=None, required=True):
    f = {"name": name, "label": label, "type": "object",
         "list": {"collapsible": {"collapsed": True, "summary": summary}}, "fields": fields}
    if description:
        f["description"] = description
    if required:
        f["required"] = True
    return f

def title_text(name, label, description=None):
    return objlist(name, label, [s("title", "Título"), t("text", "Texto")], description=description)

PHONE = {"regex": r"^\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$", "message": "Escribe el teléfono así: (772) 289-2344"}
EMAIL = {"regex": r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", "message": "Escribe un correo válido"}
LINK = {"regex": r"^(https?://\S+|mailto:\S+|tel:\S+|[\w\-./]+\.html(#[\w-]+)?|/\S*|#\S*)?$",
        "message": "Usa una dirección que empiece con https:// o el nombre de una página, por ejemplo schedule.html"}

site = {
    "name": "site", "operations": {"delete": False}, "label": "Datos de la empresa", "type": "file", "path": "content/site.yml", "format": "yaml",
    "description": "Teléfonos, direcciones, correo, licencias y aviso superior. Aparecen en todas las páginas.",
    "fields": [
        s("company_name", "Nombre de la empresa", "Se usa en Google y en la cita de «Sobre nosotros». El logo, el encabezado "
          "y los títulos de las pestañas los cambia tu desarrollador."),
        s("legal_name", "Razón social", "Aparece en el aviso de derechos al final de la página."),
        t("about_line", "Frase del pie de página"),
        s("email", "Correo de contacto", "Aquí llegan las solicitudes del formulario.", pattern=EMAIL),
        objlist("offices", "Oficinas", [
            s("region", "Región", "Ejemplo: Treasure Coast"),
            s("phone", "Teléfono", "Formato: (772) 289-2344", pattern=PHONE),
            s("street", "Dirección"), s("city", "Ciudad"), s("state", "Estado", "Ejemplo: FL"),
            s("zip", "Código postal"),
        ], summary="{fields.region} · {fields.phone}", description="La primera oficina es el teléfono principal de la web."),
        objlist("licenses", "Licencias", [
            {"name": "type", "label": "Tipo", "type": "select", "required": True,
             "options": opts([("building", "Construcción"), ("electrical", "Electricidad"), ("plumbing", "Plomería"), ("other", "Otra")])},
            s("label", "Nombre", "Ejemplo: Building"), s("number", "Número de licencia"),
        ], summary="{fields.label} · {fields.number}"),
        obj("announcement", "Aviso superior (barra roja)", [
            {"name": "show", "label": "Mostrar el aviso", "type": "boolean", "default": False},
            t("text", "Texto del aviso", RICH, required=False),
            s("link_text", "Texto del enlace (opcional)", "Ejemplo: Book now", required=False),
            s("link", "Enlace (opcional)", "Ejemplo: schedule.html o https://...", required=False, pattern=LINK),
        ], "Úsalo para promociones o avisos temporales (por ejemplo, temporada de huracanes).", required=False),
        obj("final_cta", "Llamado final (al pie de cada página)", [
            s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
        ]),
    ],
}

home = {
    "name": "home", "operations": {"delete": False}, "label": "Página de inicio", "type": "file", "path": "content/home.yml", "format": "yaml",
    "fields": [
        obj("hero", "Portada", [
            s("badge", "Etiqueta roja", "Ejemplo: Free"), s("badge_text", "Texto junto a la etiqueta"),
            s("heading", "Título principal", ACCENT),
            strings("trades", "Oficios (fila bajo el título)", item="string"),
            t("subtitle", "Subtítulo", RICH),
        ]),
        objlist("stats", "Cifras", [
            s("number", "Número", "Ejemplo: 35 o $0"),
            {"name": "plus", "label": "Mostrar un + después del número", "type": "boolean", "default": False},
            s("label", "Descripción"),
        ], summary="{fields.number} · {fields.label}"),
        obj("divisions", "01 · Divisiones", [
            s("label", "Etiqueta pequeña (sobre el título)"), s("heading", "Título", ACCENT), t("intro", "Texto", RICH),
            *[obj(k, n, [s("title", "Título"), t("text", "Texto"), strings("bullets", "Puntos de la lista", item="string")])
              for k, n in (("plumbing", "Tarjeta de plomería"), ("electrical", "Tarjeta de electricidad"),
                           ("building", "Tarjeta de construcción"))],
        ]),
        obj("thermal", "02 · Termografía infrarroja", [
            s("label", "Etiqueta pequeña (sobre el título)"), s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
            title_text("points", "Puntos"),
        ]),
        obj("why", "03 · Por qué elegirnos", [
            s("label", "Etiqueta pequeña (sobre el título)"), s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
            title_text("items", "Razones"),
        ]),
        obj("steps", "04 · Cómo funciona", [
            s("label", "Etiqueta pequeña (sobre el título)"), s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
            title_text("items", "Pasos"),
        ]),
        obj("diagnostics", "05 · Diagramas", [
            s("label", "Etiqueta pequeña (sobre el título)"), s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
        ]),
        obj("commercial", "06 · Clientes comerciales", [
            s("label", "Etiqueta pequeña (sobre el título)"), s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
            title_text("benefits", "Beneficios"),
        ]),
        obj("about", "07 · Sobre nosotros", [
            s("label", "Etiqueta pequeña (sobre el título)"), s("heading", "Título", ACCENT),
            strings("paragraphs", "Párrafos", RICH),
            s("corporate_line", "Línea corporativa"), t("quote", "Frase destacada"),
        ]),
        obj("areas", "Zonas de servicio", [
            s("label", "Etiqueta pequeña (sobre el título)"), s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
        ], "Las direcciones y teléfonos se editan en «Datos de la empresa»."),
    ],
}

gallery = {
    "name": "gallery", "operations": {"delete": False}, "label": "Fotos de proyectos", "type": "file", "path": "content/gallery.yml", "format": "yaml",
    "description": "Sube fotos de trabajos terminados. La sección aparece sola cuando hay al menos una foto.",
    "fields": [
        s("heading", "Título de la sección", ACCENT),
        t("intro", "Texto de la sección", required=False),
        objlist("projects", "Fotos", [
            {"name": "image", "label": "Foto", "type": "image", "required": True,
             "description": "JPG, PNG o WebP. La web la reduce y optimiza sola."},
            s("title", "Descripción corta", "Ejemplo: Kitchen re-piping in Port St. Lucie"),
            {"name": "category", "label": "Mostrar en", "type": "select", "required": True, "default": "all",
             "options": opts([("all", "Todas las páginas"), ("plumbing", "Plomería"), ("electrical", "Electricidad"),
                              ("building", "Construcción"), ("commercial", "Comercial")])},
        ], required=False),
    ],
}

def services(division, label):
    return {
        "name": division, "label": label, "type": "collection", "path": f"content/services/{division}", "format": "yaml",
        "description": "Cada servicio tiene su propia página. Desmarca «Mostrar en la web» para ocultarlo sin borrarlo.",
        "filename": "{fields.title}.yml",
        "subfolders": False,                    # the build reads only the top folder
        "operations": {"rename": False},        # the file name is the page URL
        "view": {"fields": ["title", "order", "visible"], "primary": "title", "sort": ["order", "title"],
                 "default": {"sort": "order", "order": "asc"}},
        "fields": [
            s("title", "Nombre del servicio"),
            s("summary", "Resumen corto", "Aparece en la tarjeta del servicio."),
            t("intro", "Introducción", RICH),
            strings("options", "Opciones del servicio", "Lo que incluye este servicio.", item="string"),
            strings("reasons", "Razones para llamar", item="string"),
            {"name": "icon", "label": "Ícono", "type": "select", "required": True, "default": "wrench", "options": opts(ICONS)},
            {"name": "diagram", "label": "Diagrama", "type": "select", "required": True, "default": "none",
             "options": opts([("none", "Sin diagrama")] + [(k, n) for k, n, _ in DIAGRAMS])},
            {"name": "order", "label": "Orden", "type": "number", "required": True, "default": 50,
             "description": "Los números más bajos aparecen primero.", "options": {"min": 1, "max": 999}},
            {"name": "visible", "label": "Mostrar en la web", "type": "boolean", "default": True},
        ],
    }

pages = {
    "name": "pages", "operations": {"delete": False}, "label": "Otras páginas", "type": "file", "path": "content/pages.yml", "format": "yaml",
    "description": "Textos de las páginas de plomería, electricidad, construcción, comercial y agenda.",
    "fields": [
        obj("plumbing", "Página de plomería", [s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
                                               s("cta_heading", "Título del llamado final", ACCENT)]),
        obj("electrical", "Página de electricidad", [s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
                                                     s("cta_heading", "Título del llamado final", ACCENT)]),
        obj("building", "Página de construcción", [
            s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
            s("services_heading", "Título de servicios", ACCENT), t("services_intro", "Texto de servicios", RICH),
            objlist("services", "Servicios", [
                {"name": "icon", "label": "Ícono", "type": "select", "required": True, "default": "hammer", "options": opts(ICONS)},
                s("title", "Título"), t("text", "Texto"),
            ]),
            s("inspections_heading", "Título de inspecciones", ACCENT), t("inspections_lead", "Texto de inspecciones", RICH),
            title_text("inspections", "Beneficios de las inspecciones"),
            s("cta_heading", "Título del llamado final", ACCENT),
        ]),
        obj("commercial", "Página comercial", [
            s("heading", "Título", ACCENT), t("lead", "Texto", RICH),
            s("proactive_heading", "Título «planifica»", ACCENT), t("proactive_lead", "Texto «planifica»", RICH),
            title_text("proactive", "Puntos «planifica»"),
            s("risk_heading", "Título «reduce riesgos»", ACCENT), title_text("risks", "Riesgos que se reducen"),
            s("cta_heading", "Título del llamado final", ACCENT), t("cta_lead", "Texto del llamado final", RICH),
        ]),
        obj("schedule", "Página de agenda (formulario)", [s("heading", "Título", ACCENT), t("lead", "Texto", RICH)]),
    ],
}

def diagram(key, label, n):
    fields = [s("title", "Título"), t("description", "Descripción")]
    if n:
        fields.append({"name": "points", "label": "Nombres de los puntos numerados", "type": "string",
                       "description": f"Uno por cada número del dibujo, en orden (exactamente {n}).",
                       "required": True, "pattern": dict(NONBLANK), "list": {"min": n, "max": n, "collapsible": False}})
    return {"name": f"diagram-{key}", "label": label, "type": "file", "path": f"content/diagrams/{key}.yml",
            "format": "yaml", "operations": {"delete": False}, "fields": fields}

config = {
    "media": {"input": "assets/img/uploads", "output": "/assets/img/uploads",
              "extensions": ["jpg", "jpeg", "png", "webp"], "rename": "safe"},
    "content": [
        site, home, gallery,
        services("plumbing", "Servicios de plomería"), services("electrical", "Servicios eléctricos"),
        pages,
        {"name": "diagrams", "label": "Diagramas", "type": "group",
         "description": "Títulos, descripciones y nombres de los puntos numerados de cada diagrama.",
         "items": [diagram(*d) for d in DIAGRAMS]},
    ],
    "settings": {"config": False},
}

header = """# Panel de edición de la web — Pages CMS (https://app.pagescms.org)
# Cada cambio guardado en el panel crea un commit en GitHub y la web se vuelve a publicar sola.
# Generado por _source/make_pages_config.py — los nombres de campos deben coincidir con content/*.yml y _source/build.py.
"""
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".pages.yml"), "w", encoding="utf-8") as f:
    f.write(header + yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=1000))
print("wrote .pages.yml")

"""Static site generator for U.S. Construction & Plumbing Authority.

Run:  python3 _source/build.py   (from anywhere). Writes every HTML page, the
icon subset, robots.txt, sitemap.xml and 404.html into the site root.
Needs: Pillow (image sizes) and fonttools+brotli (icon font subset).
"""
import os, re, json
from html import unescape

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(OUT, "services"), exist_ok=True)

# Production URL (no trailing slash). Leave empty until the domain is confirmed;
# canonical, og:url, absolute og:image and sitemap.xml are emitted only when set.
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
SITE_NAME = "U.S. Construction & Plumbing Authority"

try:
    from PIL import Image
    def img_size(name):
        with Image.open(os.path.join(OUT, "assets", "img", name)) as im:
            return im.size
except ImportError:  # sizes are an optimisation only
    def img_size(name):
        return None

TC = ("(772) 289-2344", "tel:+17722892344")
GC = ("(954) 991-9500", "tel:+19549919500")
EMAIL = "cia4solutions@gmail.com"
LIC = "CBC1264899 &middot; EC13003241 &middot; CFC1431064"

# ------------------------------------------------------------------ data
DIAGRAMS = {
    "water-heater": ("dg-water-heater.jpg", "Water Heater", "This diagram shows the various points where a water heater tank and its connections can leak and fail.", "plumbing"),
    "bathtub": ("dg-bathtub.jpg", "Bathroom with Bathtub", "This diagram shows the areas where leaks can occur at plumbing connection points in a typical bathroom with a bathtub.", "plumbing"),
    "shower": ("dg-shower.jpg", "Bathroom Shower", "This diagram shows the areas where leaks can occur at various points in a shower enclosure area and in the shower pan base.", "plumbing"),
    "kitchen": ("dg-kitchen.jpg", "Kitchen", "This diagram shows every possible area where the kitchen plumbing components may leak.", "plumbing"),
    "repiping": ("dg-repiping.jpg", "Re-Piping", "Homes built with aging water piping may require a full or partial re-piping. This illustration shows the typical pipe locations and the areas where a leak, deterioration or a break may occur.", "plumbing"),
    "sewer": ("dg-sewer.jpg", "Sewer &amp; Drain Lines", "This diagram illustrates the connection points of the interior drain lines and underground sewer lines.", "plumbing"),
    "panel": ("dg-panel.jpg", "Circuit Breaker Panel", "This diagram shows where faults may arise or may be present in an interior or exterior circuit breaker panel and its components.", "electrical"),
    "disconnect": ("dg-disconnect.jpg", "Service Disconnect Switch", "This diagram shows where faults may be found using thermal imaging equipment in an interior or exterior electrical service disconnect switch and its components.", "electrical"),
    "receptacles": ("dg-receptacles.jpg", "Receptacles &amp; Light Switches", "This image shows where electrical faults can be found in receptacles and/or in switches.", "electrical"),
    "fixtures": ("dg-fixtures.jpg", "Lamp Fixtures &amp; Ceiling Fans", "This diagram illustrates some of the areas where a lamp fixture or ceiling fan may fail, causing electrical issues.", "electrical"),
}

# Numbered leak / fault points drawn over each diagram: (x %, y %, label)
POINTS = {
    "water-heater": [
        (19, 7, "Shutoff valve (inlet)"), (32, 7, "Flexible connector (inlet)"), (20, 15, "Expansion tank connection"),
        (43, 12, "Cold-water inlet fitting"), (50, 15, "Anode rod port"), (58, 12, "Hot-water outlet fitting"),
        (65, 7, "Flexible connector (outlet)"), (86, 17, "Temperature &amp; pressure relief valve"), (90, 31, "T&amp;P discharge pipe joint"),
        (66, 23, "Upper side penetration fitting"), (55, 40, "Upper heating element gasket"), (75, 40, "Upper thermostat &amp; cover"),
        (41, 52, "Tank body corrosion pinhole"), (55, 53, "Lower heating element gasket"), (50, 68, "Sediment &amp; scale buildup"),
        (33, 71, "Drain valve &amp; threads"), (48, 80, "Bottom seam corrosion"), (63, 91, "Drain pan leak / overflow"),
        (82, 61, "Gas control valve"), (93, 66, "Gas connector (flex)"), (79, 76, "Burner &amp; pilot assembly"),
    ],
    "bathtub": [
        (13, 10, "Wall supply pipe joint (behind wall)"), (15, 30.5, "Toilet tank fill valve connection"), (11, 38, "Toilet shutoff valve"),
        (25, 51, "Toilet base / wax ring"), (47, 12, "Faucet handle &amp; spout"), (49, 27, "Drain flange under sink"),
        (38, 36, "Sink shutoff valves &amp; supply lines"), (51, 40, "P-trap slip nuts"), (49, 47, "Vanity drain connection"),
        (69, 6, "Showerhead connection"), (66, 21, "Shower valve (behind escutcheon)"), (70, 31, "Tub spout connection"),
        (69, 37, "Tub overflow gasket"), (72, 45, "Tub drain gasket / stopper"), (88, 54, "Tub waste pipe joint (behind wall)"),
        (43, 61, "Floor drain grate &amp; body"), (47, 74, "Floor drain trap slip nuts"), (70, 76, "Main waste stack joint (under floor)"),
        (15, 62, "Water heater flexible connections"), (22, 80, "Water heater T&amp;P discharge pipe"),
    ],
    "shower": [
        (37, 4, "Deteriorated caulk &mdash; wall corner"), (52, 4, "Shower arm penetration"), (56, 10, "Showerhead connection"),
        (52, 21, "Valve trim plate seal"), (44, 24, "Body spray fittings"), (64, 21, "Handheld hose connection"),
        (31, 24, "Niche shelf-to-wall joint"), (31, 30, "Niche bottom (ponding)"), (19, 21, "Waterproof membrane breach"),
        (24, 45, "Bench top &amp; seams"), (48, 49, "Wall-to-pan intersection"), (52, 59, "Shower drain grate"),
        (28, 63, "Curb &mdash; grout / slope failure"), (82, 36, "Supply pipes &amp; valve body (behind wall)"), (86, 17, "Glass door hinge / clamp"),
        (86, 58, "Glass-to-curb seal"), (17, 72, "Pan liner fold / wrinkle"), (50, 72, "Drain flange &amp; weep holes"),
        (43, 81, "Subfloor penetration / damage"), (50, 83, "Drain-to-trap connection"), (57, 94, "P-trap leak"),
    ],
    "kitchen": [
        (31, 17, "Side sprayer / soap dispenser"), (40, 14, "Pull-down faucet &amp; hose"), (51, 15, "Filtered-water tap"),
        (72, 8, "Pot filler joints"), (27, 24, "Sink rim &amp; caulk"), (76, 23, "Countertop dispenser / air gap"),
        (40, 26, "Basket strainer"), (45, 36, "Disposal mounting"), (51, 45, "Disposal dishwasher inlet"),
        (41, 56, "P-trap slip joints"), (16, 36, "Angle stop valves"), (31, 44, "Filter canisters"),
        (18, 52, "Instant hot-water unit"), (68, 35, "Reverse-osmosis filter housings"), (56, 50, "RO storage tank"),
        (67, 53, "Dishwasher supply &amp; drain connections"), (84, 55, "Dishwasher door seal / tub"), (46, 63, "Drain penetration (cabinet floor)"),
        (40, 71, "In-wall supply joints"), (52, 80, "In-wall drain joints"), (12, 74, "Washer supply box"),
        (88, 76, "Wall drain pipe penetration"), (79, 90, "Floor drain"),
    ],
    "repiping": [
        (8, 69, "Main line connection"), (12, 64, "Water meter &amp; main shutoff valve"), (25, 60, "Water softener connections"),
        (42, 61, "Supply manifold"), (61, 66, "Water heater connections"), (73, 68, "Expansion tank"),
        (67, 7, "Vent stack roof flashing"), (53, 14, "Attic / ceiling pipe joints"), (38, 26, "Toilet supply connections"),
        (52, 20, "Showerhead &amp; tub supply"), (80, 22, "Shower valve &amp; head"), (39, 33, "Floor-level supply lines"),
        (19, 44, "Refrigerator water line"), (37, 46, "Kitchen sink supply"), (58, 48, "Drain &amp; vent stack joints"),
        (66, 45, "Washer supply hoses"), (80, 46, "Utility sink"), (91, 43, "Hose bib (exterior)"),
        (96, 62, "Exterior wall penetration"), (38, 77, "Floor drain"), (41, 86, "Under-slab drain joints &amp; cleanout"),
        (92, 91, "Sewer line to street"),
    ],
}

# slug, icon, title, short, intro, options, signs, diagram
PLUMBING = [
    ("water-heater", "fa-fire-flame-simple", "Water Heater Repair &amp; Replacement",
     "Leaking tanks, failed elements and no hot water.",
     "From leaking tanks and faulty relief valves to failed heating elements, our licensed plumbers diagnose the problem and explain whether a repair or a replacement makes more sense for your home.",
     ["Repair", "Replace"],
     ["No hot water, or hot water that runs out quickly", "Water pooling around the base or in the drain pan", "Rust-colored water or rumbling and popping noises", "Dripping from the temperature &amp; pressure relief valve"], "water-heater"),
    ("leak-detection", "fa-droplet", "Leak Detection &amp; Repair",
     "Faucets, valves, pipes and hose bibs.",
     "Hidden leaks cause damage long before they are visible. Our infrared-certified thermography specialists help pinpoint where water is escaping, so repairs are precise and walls are opened only where needed.",
     ["Faucet", "Speedy Valve", "Pipe", "Hose Bib"],
     ["An unexplained increase in your water bill", "Damp spots or stains on walls, ceilings or floors", "Musty odors or signs of mold", "The sound of running water when every fixture is off"], "repiping"),
    ("drain-clearing", "fa-filter", "Drain Clearing",
     "Kitchen, bathroom sink, tub and shower drains.",
     "Slow or blocked drains are more than an inconvenience. We clear kitchen, bathroom, tub and shower drains and identify the cause so the problem doesn&rsquo;t keep coming back.",
     ["Kitchen", "Bathroom Sink", "Tub", "Shower"],
     ["Water draining slowly or standing in the fixture", "Gurgling sounds from drains", "Recurring clogs in the same fixture", "Unpleasant odors coming from drains"], "sewer"),
    ("sewer-line", "fa-house-flood-water", "Sewer Line Clogs &amp; Breaks",
     "Main line clogs and broken sewer lines.",
     "A clogged or broken sewer line affects the entire property. We evaluate the interior drain lines and underground sewer connections to locate the clog or break and restore proper flow.",
     ["Clog", "Break"],
     ["Several drains backing up at the same time", "Sewage odors inside or outside the home", "Soggy or sunken patches in the yard", "Toilets gurgling when other fixtures drain"], "sewer"),
    ("re-piping", "fa-grip-lines", "Re-Piping",
     "Full or partial whole-house re-piping.",
     "Homes built with steel, galvanized, lead or cast iron water piping may require a full or partial re-pipe. We evaluate the condition of your piping and walk you through your options.",
     ["Full Re-Pipe", "Partial Re-Pipe"],
     ["Low water pressure throughout the home", "Discolored or rusty water", "Frequent leaks in different locations", "Visible corrosion on exposed pipes"], "repiping"),
    ("low-water-pressure", "fa-gauge-simple", "Low Water Pressure",
     "Whole house or a single fixture.",
     "Low pressure can come from a clogged aerator, clogged lines or a broken water line. We find the cause — whether it affects one faucet or the whole house — and correct it.",
     ["Whole House", "Faucet / Fixture", "Clogged Lines", "Clogged Aerator", "Broken Water Line"],
     ["Weak flow at one or more fixtures", "Pressure drops when another fixture is used", "Sputtering or irregular water flow", "Pressure that has declined over time"], "repiping"),
    ("toilet", "fa-toilet", "Toilet Repair &amp; Replacement",
     "Clogs, leaks, running toilets and replacements.",
     "From a stubborn clog to a full replacement, we handle every part of the toilet — wax rings, tank kits, flappers, bolts, flanges and fill valves.",
     ["Unclog", "Replace Toilet", "Replace Wax Ring", "Replace Tank Kit", "Replace Flapper", "Replace Bolt Set", "Replace Flange", "Replace Fill Valve"],
     ["Toilet runs constantly or refills on its own", "Water around the base of the toilet", "Weak flush or frequent clogs", "Toilet rocks or feels loose"], "bathtub"),
    ("faucets-fixtures", "fa-faucet", "Faucets &amp; Fixtures",
     "Repair leaks or replace faucets and fixtures.",
     "A dripping faucet wastes water every day. We repair leaking faucets and fixtures or replace them with new ones, installed to code.",
     ["Repair Leak", "Replace"],
     ["Dripping faucet or spout", "Water leaking under the sink", "Loose or hard-to-turn handles", "Reduced or uneven flow"], "kitchen"),
    ("shower-tub", "fa-shower", "Shower Body Repair &amp; Replacement",
     "Shower valves, enclosures and shower pans.",
     "Leaks can occur at various points in a shower enclosure and in the shower pan base. We repair or replace the shower body and address the connections that commonly fail.",
     ["Repair", "Replace"],
     ["Dripping shower head when turned off", "Difficulty controlling water temperature", "Stains or damage on the ceiling below the bathroom", "Loose tiles or damaged grout in the shower"], "shower"),
    ("dishwasher", "fa-sink", "Dishwasher Plumbing",
     "Leaking or clogged dishwashers.",
     "We correct dishwasher leaks and clogs at the supply, drain and connection points under your kitchen sink.",
     ["Leaking", "Clogged"],
     ["Water on the floor in front of the dishwasher", "Standing water left in the dishwasher", "Dishwasher not draining", "Water damage in the cabinet next to it"], "kitchen"),
    ("food-disposal", "fa-gears", "Food Disposal",
     "Replace, repair or unjam disposals.",
     "Whether your disposal is jammed, leaking or simply worn out, we repair, unjam or replace it.",
     ["Replace", "Repair", "Unjam"],
     ["Humming but not turning", "Leaks under the sink", "Slow draining kitchen sink", "Unusual grinding noises"], "kitchen"),
    ("washer", "fa-soap", "Washer Plumbing",
     "Washer drains and leaking connections.",
     "We clear washing machine drains and repair leaking supply connections to protect your floors.",
     ["Clear Drain", "Leaking Connection(s)"],
     ["Water overflowing from the standpipe", "Water around the washer after a cycle", "Worn or bulging supply hoses", "Slow draining washer"], None),
    ("water-filtration", "fa-glass-water", "Water Filters &amp; Softeners",
     "Repair, replace or install new systems.",
     "We repair and replace water filters and softeners, and install new systems for better water in your home.",
     ["Repair", "Replace", "New Install"],
     ["Water tastes or smells unusual", "Scale buildup on fixtures", "System leaking or not regenerating", "Filters that need replacing"], None),
    ("main-shutoff-valve", "fa-wrench", "Main Shutoff Valve &amp; Hose Bibs",
     "Main valve replacement from &frac34;&Prime; to 2&Prime;.",
     "A working main shutoff valve is your first line of defense in a plumbing emergency. We replace main shutoff valves in common sizes from &frac34;&Prime; to 2&Prime; and replace hose bibs.",
     ["&frac34;&Prime; Valve", "1-&frac14;&Prime; Valve", "1-&frac12;&Prime; Valve", "2&Prime; Valve", "Replace Hose Bib"],
     ["The main valve is stuck or hard to turn", "The valve does not fully stop the water", "Leaks at the valve body or handle", "Dripping or broken outdoor hose bib"], "repiping"),
]

ELECTRICAL = [
    ("breaker-panel", "fa-table-cells", "Breaker Panel Corrections",
     "Double taps, grounds, neutrals and bonding.",
     "Many panel issues are invisible until they cause a failure. We correct double taps, separate grounds from neutrals, replace oxidized ground lugs, install ground bars, clean panel interiors and add bonding lugs where panels are not bonded.",
     ["Double Taps: Circuit Breakers", "Double Taps: Line / Load Wires", "Double Taps: Grounds", "Separate Grounds from Neutrals", "Replace Oxidized Ground Lug", "Install Ground Bar", "Clean Panel Interior", "Add Bonding Lug"],
     ["Breakers that trip frequently", "Warm panel cover or a burning smell", "Visible rust or corrosion inside the panel", "Buzzing or crackling sounds"], "panel"),
    ("circuit-breakers", "fa-toggle-on", "Circuit Breaker Replacement",
     "Oxidized, broken or incorrectly sized breakers.",
     "A breaker must match the wire it protects. We replace oxidized and broken breakers, and replace undersized or oversized breakers with the correct size for the existing wire.",
     ["Replace Oxidized Breaker(s)", "Replace Broken Breaker", "Undersized Breaker: Correct Size", "Oversized Breaker: Correct Size"],
     ["A breaker that won&rsquo;t reset or stay on", "Breakers that feel hot to the touch", "Scorch marks on a breaker", "Lights dimming when appliances start"], "panel"),
    ("panel-replacement", "fa-server", "Panel Replacement",
     "Oxidized, warped, broken or undersized panels.",
     "When a panel is oxidized, warped, has broken breaker retainers or is undersized for the home, we replace it with a properly sized panel.",
     ["Oxidized Panel", "Warped Panel", "Broken Breaker Retainers", "Undersized Panel", "Other"],
     ["Breakers that don&rsquo;t seat firmly", "Not enough space for new circuits", "Corrosion or heat damage in the panel", "An older panel that is no longer serviceable"], "panel"),
    ("panel-wiring", "fa-ethernet", "Panel Wiring Corrections",
     "Bushings, connectors and wire sizing.",
     "Wires entering a panel need the correct protection and size. We install missing anti-short bushings, connectors and connector nuts, and correct wiring that is undersized for the load or incorrect for the application — including exposed live line wires.",
     ["Missing Anti-Short Bushings", "Missing Connectors", "Missing Connector Nuts", "Undersized for the Load", "Incorrect for the Application", "Exposed Live Line Wires"],
     ["Wires entering the panel without connectors", "Wires that are warm or discolored", "Exposed conductors at the panel", "Circuits that overload regularly"], "panel"),
    ("circuits", "fa-code-branch", "Circuits &amp; New Circuit Additions",
     "Repair, replace, add or troubleshoot circuits.",
     "Whether you need a new dedicated circuit or a faulty circuit repaired, we design, install and troubleshoot circuits safely and to code.",
     ["New Circuit Addition", "Repair", "Replace", "Troubleshoot"],
     ["Breakers tripping when appliances run", "Outlets or lights that stop working", "Adding new appliances or equipment", "Extension cords used as permanent wiring"], "panel"),
    ("no-power", "fa-power-off", "No or Intermittent Power",
     "Troubleshooting power loss and flickering.",
     "Partial or intermittent power loss often points to a loose connection or a failing component. We use thermal imaging to locate faults in the panel and service disconnect.",
     ["No Power", "Intermittent Power", "Troubleshoot"],
     ["Part of the home without power", "Flickering or dimming lights", "Power that comes and goes", "Warm outlets, switches or panel covers"], "disconnect"),
    ("receptacles-switches", "fa-plug", "Receptacles &amp; Switches",
     "Repair, replace, relocate or add.",
     "We repair, replace, relocate and add receptacles and switches — and find the faults that make them fail.",
     ["Repair", "Replace", "Relocate", "New Addition"],
     ["Outlets or switches that are warm to the touch", "Sparks when plugging in", "Loose plugs or cracked covers", "Dead outlets"], "receptacles"),
    ("lighting", "fa-lightbulb", "Lighting Issues",
     "Switches, fixtures and bulbs.",
     "From a faulty switch to a failing fixture, we diagnose lighting issues and replace the switch, fixture or bulb as needed.",
     ["Replace Switch", "Replace Fixture", "Replace Bulb"],
     ["Lights flickering or buzzing", "Bulbs burning out quickly", "Switches that don&rsquo;t work consistently", "Discoloration around a fixture"], "fixtures"),
    ("interior-lighting", "fa-house-chimney-window", "Interior Lighting Fixtures",
     "Repair, replace, relocate, add or remove.",
     "We repair, replace, relocate, add and remove interior lighting fixtures to improve the safety and look of every room.",
     ["Repair", "Replace", "Relocate", "New Addition", "Remove"],
     ["Fixtures that flicker or stop working", "Loose or sagging fixtures", "Heat damage around a fixture", "Rooms that need better lighting"], "fixtures"),
    ("exterior-lighting", "fa-sun", "Exterior Lighting Fixtures",
     "Repair, replace, relocate, add or remove.",
     "Exterior lighting adds security and curb appeal. We repair, replace, relocate, add and remove exterior fixtures.",
     ["Repair", "Replace", "Relocate", "New Addition", "Remove"],
     ["Outdoor lights not working", "Water or corrosion inside fixtures", "Areas of the property left dark", "Fixtures damaged by weather"], "fixtures"),
    ("ceiling-fans", "fa-fan", "Ceiling Fans",
     "Replace, repair or install new fans.",
     "We repair and replace ceiling fans and install new ones — properly supported, balanced and wired.",
     ["Replace", "Repair", "New Install"],
     ["Wobbling or noisy fan", "Fan or light kit not responding", "Fan running at only one speed", "Burning smell from the fan"], "fixtures"),
    ("water-heater-circuits", "fa-temperature-arrow-up", "Water Heater Circuits",
     "Re-wiring, new circuits and tankless expansion.",
     "Water heaters need a correctly sized, dedicated circuit. We re-wire water heater circuits, add new circuits and expand circuits for tankless water heaters.",
     ["Re-Wiring", "New Circuit", "Tankless Circuit Expansion"],
     ["Breaker trips when the water heater runs", "Switching to a tankless water heater", "Warm or discolored wiring at the heater", "No hot water with power issues"], None),
    ("generators", "fa-car-battery", "Generators",
     "Transfer switches, maintenance and panel connection.",
     "Be ready for Florida storms. We install transfer switches, help with generator starting and maintenance, and connect generators safely to your home through a transfer switch.",
     ["Transfer Switch Installation", "Starting / Maintenance", "Connection to Panel Circuit"],
     ["Preparing for hurricane season", "Generator won&rsquo;t start or run properly", "Generator not connected safely to the home", "No transfer switch installed"], "disconnect"),
    ("dangerous-conditions", "fa-triangle-exclamation", "Dangerous Conditions",
     "Conditions that require immediate attention.",
     "Some electrical conditions require immediate attention. <strong>If you see smoke, flames or sparking, leave the area and call 911 first &mdash; do not touch the panel.</strong> For any of the warning signs below, contact us to schedule an evaluation as soon as possible.",
     ["Evaluation", "Troubleshoot", "Repair"],
     ["A burning smell or smoke from outlets or the panel", "Scorch marks, sparks or melted wire", "A panel that is hot to the touch", "Exposed live wires"], "panel"),
]

BUILDING = [
    ("fa-trowel-bricks", "Remodeling", "Kitchens, bathrooms and interior renovations crafted to enhance the elegance and functionality of your home."),
    ("fa-magnifying-glass", "Building Inspections", "We evaluate critical components, identify deficiencies and highlight areas that may require attention."),
    ("fa-screwdriver-wrench", "Trade Work", "Licensed plumbing, electrical and building trades working together on one project."),
    ("fa-file-signature", "Permits &amp; Inspections", "Our operation supports efficient building department permitting &amp; inspections."),
]

# ------------------------------------------------------------------ layout
NAV = [("plumbing.html", "Plumbing"), ("electrical.html", "Electrical"), ("building.html", "Building &amp; Remodeling"),
       ("commercial.html", "Commercial"), ("index.html#about", "About")]

def attr(text):
    """Plain text safe for an HTML attribute (tags stripped, entities decoded then re-escaped)."""
    t = unescape(re.sub(r"<[^>]+>", "", text))
    return t.replace("&", "&amp;").replace('"', "&quot;")

def jsonld():
    def office(name, street, city, zipc, phone, area):
        d = {"@type": "HomeAndConstructionBusiness", "name": name, "telephone": phone, "email": EMAIL,
             "address": {"@type": "PostalAddress", "streetAddress": street, "addressLocality": city,
                         "addressRegion": "FL", "postalCode": zipc, "addressCountry": "US"},
             "areaServed": area}
        if SITE_URL:
            d["url"] = SITE_URL + "/"
            d["image"] = SITE_URL + "/assets/img/logo.png"
        return d
    data = {
        "@context": "https://schema.org", "@type": "Organization", "name": SITE_NAME,
        "legalName": "CIA Solutions, Corp.", "email": EMAIL,
        "description": "Licensed & insured plumbing, electrical, remodeling, building inspection and trade work in Florida. Licenses CBC1264899, EC13003241, CFC1431064.",
        "department": [
            office("U.S. Construction & Plumbing Authority — Treasure Coast", "4166 SW Endicott St.", "Port St. Lucie", "34953", "+1-772-289-2344", "Florida Treasure Coast"),
            office("U.S. Construction & Plumbing Authority — Gold Coast", "20423 State Rd. 7, Suite F6-245", "Boca Raton", "33498", "+1-954-991-9500", "Florida Gold Coast"),
        ],
    }
    if SITE_URL:
        data["url"] = SITE_URL + "/"
        data["logo"] = SITE_URL + "/assets/img/logo.png"
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

def head(b, title, desc, path="", schema=False):
    t, d = attr(title), attr(desc)
    canon = ""
    if SITE_URL:
        url = SITE_URL + "/" + ("" if path in ("", "index.html") else path)
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

def header(b, active):
    act = ' class="is-active" aria-current="page"'
    links = "\n".join(f'        <a href="{b}{h}"{act if h == active else ""}>{t}</a>' for h, t in NAV)
    mlinks = "\n".join(f'    <a class="m-link" href="{b}{h}">{t} <i class="fa-solid fa-arrow-right"></i></a>' for h, t in NAV)
    return f"""
  <div class="utility" role="complementary" aria-label="Contact information">
    <div class="utility__inner">
      <div class="utility__group">
        <a href="{TC[1]}"><span class="dot"></span> Treasure Coast <b>{TC[0]}</b></a>
        <a href="{GC[1]}">Gold Coast <b>{GC[0]}</b></a>
        <a class="hide-sm" href="mailto:{EMAIL}"><i class="fa-regular fa-envelope"></i> {EMAIL}</a>
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
        <a class="header__phone" href="{TC[1]}"><small>Call now</small><b>{TC[0]}</b></a>
        <a href="{b}schedule.html" class="btn btn--red btn--sm">Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
        <button class="hamburger" id="hamburger" aria-label="Open menu" aria-expanded="false" aria-controls="mobileMenu"><span></span><span></span><span></span></button>
      </div>
    </div>
  </header>

  <nav class="mobile-menu" id="mobileMenu" aria-label="Mobile">
{mlinks}
    <a href="{b}schedule.html" class="btn btn--red btn--block m-cta">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
    <a href="{TC[1]}" class="btn btn--glass btn--block"><i class="fa-solid fa-phone"></i> {TC[0]}</a>
  </nav>
"""

def final_cta(b, title="Ready to evaluate your plumbing, electrical <em>or building concerns?</em>",
              text="Get fast, precise, and correct evaluations from Florida&rsquo;s trusted experts."):
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
        <a class="contact-card" href="{TC[1]}"><i class="ic fa-solid fa-phone"></i><div><small>Treasure Coast</small><strong>{TC[0]}</strong></div><i class="go fa-solid fa-arrow-right"></i></a>
        <a class="contact-card" href="{GC[1]}"><i class="ic fa-solid fa-phone"></i><div><small>Gold Coast</small><strong>{GC[0]}</strong></div><i class="go fa-solid fa-arrow-right"></i></a>
        <a class="contact-card" href="mailto:{EMAIL}"><i class="ic fa-solid fa-envelope"></i><div><small>Email</small><strong>{EMAIL.replace("@", "@<wbr>")}</strong></div><i class="go fa-solid fa-arrow-right"></i></a>
      </div>
    </div>
  </section>
"""

def footer(b):
    return f"""
  <footer class="footer">
    <div class="container">
      <div class="footer__top">
        <div class="footer__brand">
          <img src="{b}assets/img/logo-192.png" alt="U.S. Construction &amp; Plumbing Authority" width="96" height="87" loading="lazy">
          <p>U.S. Construction &amp; Plumbing Authority and PSL Plumbing &amp; Drains are divisions of CIA Solutions, Corp. JV Triphase Development Corp. Licensed &amp; insured.</p>
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
        <div>
          <h2 class="footer__title">Treasure Coast</h2>
          <ul>
            <li>4166 SW Endicott St.<br>Port St. Lucie, FL 34953</li>
            <li><a href="{TC[1]}">{TC[0]}</a></li>
          </ul>
        </div>
        <div>
          <h2 class="footer__title">Gold Coast</h2>
          <ul>
            <li>20423 State Rd. 7, Suite F6-245<br>Boca Raton, FL 33498</li>
            <li><a href="{GC[1]}">{GC[0]}</a></li>
            <li><a href="mailto:{EMAIL}">{EMAIL}</a></li>
          </ul>
        </div>
      </div>
      <div class="footer__big" aria-hidden="true">U.S. Construction Authority</div>
      <div class="footer__bottom">
        <span>&copy; <span id="year">2026</span> CIA Solutions, Corp. All rights reserved.</span>
        <span>Licenses: {LIC}</span>
      </div>
    </div>
  </footer>

  <nav class="callbar" aria-label="Quick contact">
    <a href="{TC[1]}"><i class="fa-solid fa-phone"></i> Call Now</a>
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

def write(path, html):
    html = HERO_RE.sub(_unreveal, html, count=1)
    html = re.sub(r'<i class="([^"]*\bfa-[^"]*)">', r'<i class="\1" aria-hidden="true">', html)
    html = html.replace("<main>", '<main id="main" tabindex="-1">')
    with open(os.path.join(OUT, path), "w", encoding="utf-8") as f:
        f.write(html)
    PAGES.append(path)

PAGES = []

def crumbs(items):
    """items: list of (href or None, label); the last one is the current page."""
    lis = []
    for i, (h, t) in enumerate(items):
        if i == len(items) - 1:
            lis.append(f'<li aria-current="page">{t}</li>')
        else:
            lis.append(f'<li><a href="{h}">{t}</a></li>')
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(lis)}</ol></nav>'

def img_tag(src_name, b, alt, lazy=True, extra=""):
    small = src_name.replace(".jpg", "-800.jpg")
    if src_name.endswith(".jpg") and os.path.exists(os.path.join(OUT, "assets", "img", small)):
        extra += f' srcset="{b}assets/img/{small} 800w, {b}assets/img/{src_name} {img_size(src_name)[0]}w" sizes="(max-width: 720px) 100vw, 800px"'
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
    slug, icon, title, short = s[0], s[1], s[2], s[3]
    return f"""
        <a class="svc-card reveal" href="{b}services/{division}-{slug}.html">
          <span class="svc-card__icon"><i class="fa-solid {icon}"></i></span>
          <h3>{title}</h3>
          <p>{short}</p>
          <span class="svc-card__foot">{len(s[5])} service options <i class="fa-solid fa-arrow-right"></i></span>
        </a>"""

# ------------------------------------------------------------------ blueprint
HOTSPOTS = [
    (128, 252, "Plumbing", "Bathroom &amp; shower leaks", "Tub, shower pan and fixture connections.", "services/plumbing-shower-tub.html"),
    (96, 326, "Plumbing &middot; Infrared", "Hidden leaks in walls", "Located with infrared thermography.", "services/plumbing-leak-detection.html"),
    (166, 342, "Plumbing", "Kitchen plumbing", "Faucets, disposals and dishwashers.", "services/plumbing-faucets-fixtures.html"),
    (422, 336, "Plumbing", "Water heater", "Repair or replacement of leaking and failing tanks.", "services/plumbing-water-heater.html"),
    (333, 318, "Electrical &middot; Infrared", "Breaker panel", "Double taps, oxidized breakers, bonding and more.", "services/electrical-breaker-panel.html"),
    (365, 190, "Electrical", "Ceiling fans &amp; lighting", "Repair, replace or install new fixtures.", "services/electrical-ceiling-fans.html"),
    (455, 258, "Electrical", "Receptacles &amp; switches", "Warm, dead or sparking outlets.", "services/electrical-receptacles-switches.html"),
    (340, 408, "Plumbing", "Sewer &amp; drain lines", "Clogs and breaks in underground lines.", "services/plumbing-sewer-line.html"),
    (530, 398, "Plumbing", "Main shutoff valve", "Replacement from &frac34;&Prime; to 2&Prime;.", "services/plumbing-main-shutoff-valve.html"),
]

def blueprint():
    spots = "\n".join(
        f'        <a class="hotspot" href="{h}" aria-label="{attr(t)}: {attr(x)}" data-cat="{c}" data-title="{t}" data-text="{x}">'
        f'<circle class="hit" cx="{cx}" cy="{cy}" r="16"/><circle class="ring" cx="{cx}" cy="{cy}" r="9"/><circle class="core" cx="{cx}" cy="{cy}" r="6"/></a>'
        for cx, cy, c, t, x, h in HOTSPOTS)
    hatch = "".join(f'<line x1="{x}" y1="388" x2="{x-14}" y2="430" class="bp-thin"/>' for x in range(14, 600, 18))
    return f"""
      <div class="blueprint reveal">
        <div class="blueprint__bar"><span>Interactive guide &middot; Cross-section</span><span class="live">Interactive</span></div>
        <svg viewBox="0 0 600 440" role="group" aria-label="Home cross-section: select a point to see the related service">
          <g aria-hidden="true">
          <defs>
            <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stop-color="#ff5a70" stop-opacity="0"/><stop offset=".5" stop-color="#ff5a70" stop-opacity=".22"/><stop offset="1" stop-color="#ff5a70" stop-opacity="0"/>
            </linearGradient>
            <radialGradient id="heat" cx=".5" cy=".5" r=".5">
              <stop offset="0" stop-color="#fff3a0" stop-opacity=".95"/><stop offset=".35" stop-color="#ff9a3c" stop-opacity=".7"/><stop offset=".7" stop-color="#c8102e" stop-opacity=".35"/><stop offset="1" stop-color="#4b0c7a" stop-opacity="0"/>
            </radialGradient>
            <clipPath id="houseClip"><path d="M50,170 L270,70 L490,170 L490,440 L50,440 Z"/></clipPath>
          </defs>

          <!-- ground -->
          <g>{hatch}</g>
          <line x1="0" y1="380" x2="600" y2="380" class="bp-line"/>
          <text x="8" y="374" class="bp-text">Grade</text>

          <!-- utility pole + service drop -->
          <line x1="572" y1="380" x2="572" y2="150" class="bp-line"/>
          <line x1="560" y1="160" x2="584" y2="160" class="bp-line"/>
          <path d="M572,162 Q530,220 478,292" class="bp-wire draw"/>
          <rect x="470" y="288" width="14" height="20" rx="2" class="bp-fill"/>
          <text x="500" y="210" class="bp-text">Service</text>

          <!-- house shell -->
          <path d="M50,170 L270,70 L490,170" class="bp-line draw"/>
          <path d="M70,170 V380 M470,170 V380 M70,170 H470 M70,275 H470 M260,170 V275 M300,275 V380" class="bp-line draw"/>
          <text x="80" y="186" class="bp-text">2nd floor</text>
          <text x="80" y="291" class="bp-text">1st floor</text>

          <!-- bathroom -->
          <rect x="84" y="240" width="92" height="26" rx="10" class="bp-fill"/>
          <path d="M200,222 h24 v18 h-24 z M198,242 h30 q0,20 -15,22 q-15,-2 -15,-22 z" class="bp-fill"/>
          <!-- bedroom: fan + receptacle -->
          <path d="M365,170 V182 M335,184 H395" class="bp-line"/>
          <ellipse cx="365" cy="186" rx="8" ry="4" class="bp-fill"/>
          <rect x="449" y="250" width="12" height="16" rx="2" class="bp-fill"/>
          <!-- kitchen -->
          <rect x="88" y="290" width="120" height="20" rx="2" class="bp-fill"/>
          <path d="M86,346 H270 V380 H86 Z" class="bp-fill"/>
          <path d="M150,346 v8 h32 v-8" class="bp-line"/>
          <path d="M166,346 v-16 q0,-6 8,-6" class="bp-line"/>
          <rect x="214" y="350" width="44" height="30" rx="2" class="bp-fill"/>
          <!-- utility: heater + panel + washer -->
          <rect x="400" y="300" width="44" height="78" rx="8" class="bp-fill"/>
          <rect x="320" y="298" width="26" height="40" rx="2" class="bp-fill"/>
          <path d="M325,306 h16 M325,312 h16 M325,318 h16 M325,324 h16 M325,330 h16" class="bp-thin"/>
          <rect x="352" y="344" width="36" height="36" rx="4" class="bp-fill"/>
          <circle cx="370" cy="362" r="10" class="bp-thin"/>

          <!-- drain / vent stack + sewer -->
          <path d="M240,62 V404 H600" class="bp-drain draw d2"/>
          <path d="M150,266 V272 H240 M166,354 V368 H240 M214,264 V270" class="bp-drain draw d2"/>
          <text x="248" y="420" class="bp-text">Drain / sewer</text>

          <!-- cold supply -->
          <path d="M600,396 H452 V292 H428 V300 M452,368 H96 V236 M96,262 H212 V240 M166,368 V330" class="bp-cold draw d3"/>
          <circle cx="530" cy="396" r="5" class="bp-fill"/>
          <text x="505" y="416" class="bp-text">Supply</text>
          <!-- hot supply -->
          <path d="M438,300 V284 H108 V236 M176,284 V330" class="bp-hot draw d3"/>

          <!-- electrical -->
          <path d="M478,300 H346 M333,298 V172 H365 M340,298 V282 H455 V266 M320,318 H148 V310" class="bp-wire draw d4"/>

          <!-- thermal anomalies -->
          <circle cx="96" cy="326" r="26" fill="url(#heat)"><animate attributeName="r" values="22;30;22" dur="3s" repeatCount="2"/></circle>
          <circle cx="333" cy="318" r="22" fill="url(#heat)" opacity=".85"><animate attributeName="r" values="18;26;18" dur="3.4s" repeatCount="2"/></circle>

          <!-- IR scan line -->
          <g clip-path="url(#houseClip)"><rect class="scanline" x="50" y="60" width="440" height="40" fill="url(#scanGrad)"/></g>

          </g>
          <!-- hotspots -->
{spots}
        </svg>
        <div class="bp-tip" aria-hidden="true"></div>
        <div class="blueprint__legend">
          <span><i style="background:var(--blue)"></i>Cold water</span>
          <span><i style="background:#ff6b6b"></i>Hot water</span>
          <span><i style="background:#9fb0c8"></i>Drain / sewer</span>
          <span><i style="background:var(--amber)"></i>Electrical</span>
          <span class="hint"><i class="fa-solid fa-hand-pointer"></i> Select a point to explore</span>
        </div>
      </div>"""

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

# ------------------------------------------------------------------ hero visual
HERO_SPOTS = [
    (80, 22, "Plumbing", "Bathroom &amp; shower leaks", "services/plumbing-shower-tub.html"),
    (37, 46, "Plumbing", "Kitchen plumbing", "services/plumbing-faucets-fixtures.html"),
    (61, 66, "Plumbing", "Water heater", "services/plumbing-water-heater.html"),
    (12, 64, "Plumbing", "Main shutoff valve", "services/plumbing-main-shutoff-valve.html"),
    (91, 43, "Infrared", "Hidden leak detection", "services/plumbing-leak-detection.html"),
    (40, 84, "Plumbing", "Sewer &amp; drain lines", "services/plumbing-sewer-line.html"),
]

def hero_visual():
    spots = "".join(
        f'<a class="hv-spot{" hv-spot--l" if x < 30 else " hv-spot--r" if x > 70 else ""}" href="{h}" style="left:{x}%;top:{y}%" aria-label="{attr(t)}">'
        f'<span class="hv-dot" aria-hidden="true"></span><span class="hv-tip" aria-hidden="true"><small>{c}</small>{t}</span></a>'
        for x, y, c, t, h in HERO_SPOTS)
    return f"""
      <figure class="hero-visual">
        <div class="hero-visual__frame">
          {img_tag("dg-repiping.jpg", "", "Cross-section of a Florida home showing its plumbing system", lazy=False, extra=' fetchpriority="high"')}
          {spots}
        </div>
        <figcaption><span><i class="fa-solid fa-location-dot"></i> Select a point to see the related service</span><a href="plumbing.html">All services <i class="fa-solid fa-arrow-right"></i></a></figcaption>
      </figure>"""

# ------------------------------------------------------------------ HOME
def p_services_list(items):
    return "".join(f"<li>{s[2]}</li>" for s in items)

home = f"""
  <main>
  <section class="hero">
    <div class="hero__bg"></div>
    <div class="container">
      <div class="hero__grid">
        <div>
          <span class="pill reveal"><b>Free</b> On-site evaluations &amp; estimates</span>
          <h1 class="reveal reveal-d1">Florida&rsquo;s trusted, <em>licensed &amp; insured</em> experts.</h1>
          <div class="hero__trades reveal reveal-d2"><span>Plumbing</span><span>Electrical</span><span>Remodeling</span><span>Building Inspections</span><span>Trade Work</span></div>
          <p class="hero__sub reveal reveal-d2">Our quality craftsmanship enhances the safety, elegance and functionality of your home or property.</p>
          <div class="hero__actions reveal reveal-d3">
            <a href="schedule.html" class="btn btn--red">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
            <a href="{TC[1]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {TC[0]}</a>
          </div>
        </div>
{hero_visual()}
      </div>

      <div class="stats">
        <div class="stat reveal"><div class="stat__num">35<sup>+</sup></div><p>Years of experience serving Florida homes &amp; properties</p></div>
        <div class="stat reveal reveal-d1"><div class="stat__num">50<sup>+</sup></div><p>Years of combined experience across our team</p></div>
        <div class="stat reveal reveal-d2"><div class="stat__num">3</div><p>Contractor licenses &mdash; building, electrical &amp; plumbing</p></div>
        <div class="stat reveal reveal-d3"><div class="stat__num">$0</div><p>Cost for your on-site evaluation &amp; estimate</p></div>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="container">
      <div class="head">
        <div class="reveal"><span class="kicker">01 <span>&mdash; Our divisions</span></span><h2 class="h2">Three divisions. <em>One standard.</em></h2></div>
        <p class="reveal reveal-d1">Licensed plumbers, electricians and builders under one company &mdash; so your project is evaluated, permitted and completed by specialists in every trade.</p>
      </div>
      <div class="divisions">
        <a href="plumbing.html" class="division reveal">
          <div class="division__media"><img src="assets/img/crop-kitchen.jpg" alt="Kitchen plumbing leak points" loading="lazy">
            <span class="division__icon"><i class="fa-solid fa-faucet-drip"></i></span>
            <div class="division__tag"><small>PSL Plumbing &amp; Drains</small><strong>Plumbing</strong></div></div>
          <div class="division__body">
            <h3>Plumbing Division</h3>
            <p>Leaks, drains, water heaters, re-piping and sewer lines.</p>
            <ul class="division__list"><li>Leak detection &amp; repair</li><li>Water heaters</li><li>Drain &amp; sewer lines</li><li>Re-piping</li></ul>
            <span class="division__enter">Enter Here <i class="fa-solid fa-arrow-right"></i></span>
          </div>
        </a>
        <a href="electrical.html" class="division reveal reveal-d1">
          <div class="division__media"><img src="assets/img/crop-panel.jpg" alt="Electrical panel fault points" loading="lazy" style="object-position:top">
            <span class="division__icon"><i class="fa-solid fa-bolt"></i></span>
            <div class="division__tag"><small>Triphase</small><strong>Electrical</strong></div></div>
          <div class="division__body">
            <h3>Electrical Division</h3>
            <p>Panels, circuits, lighting, fans and generators.</p>
            <ul class="division__list"><li>Breaker panel corrections</li><li>Circuits &amp; troubleshooting</li><li>Lighting &amp; ceiling fans</li><li>Generators &amp; transfer switches</li></ul>
            <span class="division__enter">Enter Here <i class="fa-solid fa-arrow-right"></i></span>
          </div>
        </a>
        <a href="building.html" class="division reveal reveal-d2">
          <div class="division__media"><img src="assets/img/crop-house.jpg" alt="Whole-house cross-section" loading="lazy">
            <span class="division__icon"><i class="fa-solid fa-helmet-safety"></i></span>
            <div class="division__tag"><small>U.S. Construction</small><strong>Building &amp; Remodeling</strong></div></div>
          <div class="division__body">
            <h3>Building &amp; Remodeling Division</h3>
            <p>Remodeling, building inspections and trade work.</p>
            <ul class="division__list"><li>Remodeling</li><li>Building inspections</li><li>Trade work</li><li>Permits &amp; inspections</li></ul>
            <span class="division__enter">Enter Here <i class="fa-solid fa-arrow-right"></i></span>
          </div>
        </a>
      </div>
    </div>
  </section>

  <section class="section dark">
    <div class="container thermal">
      <div class="reveal">
        <span class="kicker kicker--light">02 <span>&mdash; Infrared thermography</span></span>
        <h2 class="h2">See what the <em>eye can&rsquo;t.</em></h2>
        <p class="lead" style="margin-top:20px">Our in-house infrared-certified thermography specialists diagnose hidden plumbing leaks and electrical faults &mdash; helping pinpoint what&rsquo;s wrong before anything is opened up.</p>
        <ul class="thermal__list">
          <li><i class="fa-solid fa-droplet"></i><div><strong>Hidden plumbing leaks</strong><span>Moisture behind walls, floors and ceilings shows up as a temperature difference.</span></div></li>
          <li><i class="fa-solid fa-bolt"></i><div><strong>Electrical faults</strong><span>Overheating breakers, loose connections and overloaded circuits stand out immediately.</span></div></li>
          <li><i class="fa-solid fa-crosshairs"></i><div><strong>Precise evaluations</strong><span>Pinpointing the problem means fewer surprises and more accurate estimates.</span></div></li>
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
        <span class="kicker">03 <span>&mdash; Trust &amp; credentials</span></span>
        <h2 class="h2">Why homeowners, property managers &amp; contractors <em>choose us.</em></h2>
        <p class="lead">Experience, credentials and transparency on every project &mdash; large or small.</p>
        <a href="schedule.html" class="btn btn--dark">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
      </div>
      <ol class="why__list">
        <li class="why__item reveal"><span class="why__num">01</span><div><h3>Over 35 years of experience</h3><p>Decades of plumbing, electrical and building work across Florida&rsquo;s Treasure Coast and Gold Coast.</p></div></li>
        <li class="why__item reveal"><span class="why__num">02</span><div><h3>Licensed, insured &amp; code compliant</h3><p>Experienced, competent &amp; detail-oriented licensed &amp; insured code-compliant plumbers, electricians and builders.</p></div></li>
        <li class="why__item reveal"><span class="why__num">03</span><div><h3>In-house infrared thermography</h3><p>Infrared-certified thermography specialists for diagnosing plumbing leaks or electrical faults.</p></div></li>
        <li class="why__item reveal"><span class="why__num">04</span><div><h3>Transparent estimates</h3><p>Clear, detailed estimates &mdash; no surprises.</p></div></li>
        <li class="why__item reveal"><span class="why__num">05</span><div><h3>Efficient permitting &amp; inspections</h3><p>Our operation supports efficient building department permitting &amp; inspections.</p></div></li>
      </ol>
    </div>
  </section>

  <section class="section section--white" style="padding-top:0">
    <div class="container">
      <div class="head">
        <div class="reveal"><span class="kicker">04 <span>&mdash; How it works</span></span><h2 class="h2">Three simple <em>steps.</em></h2></div>
        <p class="reveal reveal-d1">From your first call to the finished repair, you stay informed and in control of every decision.</p>
      </div>
      <div class="process">
        <div class="process__step reveal"><div class="process__dot">1</div><h3>Schedule your visit</h3><p>We assess your plumbing or electrical needs.</p></div>
        <div class="process__step reveal reveal-d1"><div class="process__dot">2</div><h3>Detailed evaluation with options</h3><p>Our licensed contractors will explain your options and you will decide whether to repair or replace any damaged item.</p></div>
        <div class="process__step reveal reveal-d2"><div class="process__dot">3</div><h3>We repair or replace</h3><p>We repair or replace the damaged equipment.</p></div>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="container">
      <div class="head">
        <div class="reveal"><span class="kicker">05 <span>&mdash; Visual diagnostics</span></span><h2 class="h2">Know where <em>problems start.</em></h2></div>
        <div class="reveal reveal-d1">
          <p style="margin-bottom:22px">Our diagrams help you identify the areas where a leak, deterioration, break or electrical fault can occur.</p>
          <div class="tabs" data-tabs role="tablist" aria-label="Diagram category">
            <button type="button" class="is-active" id="tab-plumbing" data-target="panel-plumbing" role="tab" aria-selected="true" aria-controls="panel-plumbing">Plumbing</button>
            <button type="button" id="tab-electrical" data-target="panel-electrical" role="tab" aria-selected="false" aria-controls="panel-electrical" tabindex="-1">Electrical</button>
          </div>
        </div>
      </div>
      <div class="dg-panel dg-grid is-active" id="panel-plumbing" role="tabpanel" aria-labelledby="tab-plumbing">{"".join(dg_card(k) for k in ["water-heater", "bathtub", "shower", "kitchen", "repiping", "sewer"])}
      </div>
      <div class="dg-panel dg-grid dg-grid--4" id="panel-electrical" role="tabpanel" aria-labelledby="tab-electrical" hidden>{"".join(dg_card(k, True) for k in ["panel", "disconnect", "receptacles", "fixtures"])}
      </div>
    </div>
  </section>

  <section class="section dark dark--900">
    <div class="container commercial">
      <div class="reveal">
        <span class="kicker kicker--light">06 <span>&mdash; Commercial clients</span></span>
        <h2 class="h2">On time. <em>On budget.</em></h2>
        <p class="lead" style="margin-top:20px">Our meticulous work reduces labor costs, on-site corrections and roughing relocations that cause delays, material waste and unnecessary costs &mdash; keeping schedules flowing uninterrupted.</p>
        <div class="hero__actions"><a href="commercial.html" class="btn btn--white">Commercial Services <i class="fa-solid fa-arrow-right"></i></a></div>
      </div>
      <div class="benefits reveal reveal-d1">
        <div class="benefit"><i class="fa-solid fa-person-digging"></i><strong>Fewer corrections</strong><span>Reduced on-site corrections and roughing relocations.</span></div>
        <div class="benefit"><i class="fa-solid fa-recycle"></i><strong>Less waste</strong><span>Less material waste and unnecessary costs.</span></div>
        <div class="benefit"><i class="fa-solid fa-calendar-check"></i><strong>Schedules on track</strong><span>Work that keeps schedules flowing uninterrupted.</span></div>
        <div class="benefit"><i class="fa-solid fa-chart-line"></i><strong>Predictable budgets</strong><span>Plan repairs and budget effectively.</span></div>
      </div>
    </div>
  </section>

  <section class="section" id="about">
    <div class="container about">
      <div class="about__text reveal">
        <span class="kicker">07 <span>&mdash; About us</span></span>
        <h2 class="h2">Your partner in plumbing, electrical <em>or building repairs.</em></h2>
        <p>U.S. Construction &amp; Plumbing Authority and PSL Plumbing &amp; Drains are dedicated to protecting Florida homes through advanced diagnostics, engineering expertise, and reliable repair services.</p>
        <p>Our team, with over 50 years of combined experience, will provide the quality craftsmanship you expect and deserve.</p>
        <div class="licenses">
          <div class="license"><i class="fa-solid fa-building"></i><small>Building</small><strong>CBC1264899</strong></div>
          <div class="license"><i class="fa-solid fa-bolt"></i><small>Electrical</small><strong>EC13003241</strong></div>
          <div class="license"><i class="fa-solid fa-faucet"></i><small>Plumbing</small><strong>CFC1431064</strong></div>
        </div>
        <p class="corp">Divisions of CIA Solutions, Corp. JV Triphase Development Corp.</p>
      </div>
      <div class="about__card reveal reveal-d1">
        <img src="assets/img/logo-500.png" alt="U.S. Construction &amp; Plumbing Authority logo" width="400" height="364" loading="lazy">
        <blockquote>&ldquo;The quality craftsmanship you expect and deserve.&rdquo;</blockquote>
        <cite>U.S. Construction &amp; Plumbing Authority</cite>
      </div>
    </div>
  </section>

  <section class="section section--white">
    <div class="container">
      <div class="head">
        <div class="reveal"><span class="kicker">08 <span>&mdash; Service areas</span></span><h2 class="h2">Two coasts. <em>One standard of quality.</em></h2></div>
        <p class="reveal reveal-d1">Servicing Florida&rsquo;s Treasure Coast from Port St. Lucie and Florida&rsquo;s Gold Coast from Boca Raton.</p>
      </div>
      <div class="locations">
        <div class="location reveal">
          <div class="location__map"><iframe title="Map — Port St. Lucie office" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://maps.google.com/maps?q=4166+SW+Endicott+St,+Port+St.+Lucie,+FL+34953&amp;z=13&amp;output=embed"></iframe></div>
          <div class="location__body"><div><small>Treasure Coast</small><h3>Port St. Lucie</h3><p>4166 SW Endicott St., Port St. Lucie, FL 34953</p></div><a class="btn btn--dark btn--sm" href="{TC[1]}"><i class="fa-solid fa-phone"></i> {TC[0]}</a></div>
        </div>
        <div class="location reveal reveal-d1">
          <div class="location__map"><iframe title="Map — Boca Raton office" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://maps.google.com/maps?q=20423+State+Rd+7,+Boca+Raton,+FL+33498&amp;z=13&amp;output=embed"></iframe></div>
          <div class="location__body"><div><small>Gold Coast</small><h3>Boca Raton</h3><p>20423 State Rd. 7, Suite F6-245, Boca Raton, FL 33498</p></div><a class="btn btn--dark btn--sm" href="{GC[1]}"><i class="fa-solid fa-phone"></i> {GC[0]}</a></div>
        </div>
      </div>
    </div>
  </section>
{final_cta("")}
  </main>
{THERMAL_FILTER}
"""
write("index.html", head("", "U.S. Construction & Plumbing Authority | Florida Contractor",
      "Licensed & insured plumbing, electrical, remodeling, building inspections and trade work on Florida's Treasure Coast and Gold Coast. Free on-site evaluations.",
      "index.html", schema=True)
      + header("", "index.html") + home + footer(""))

# ------------------------------------------------------------------ DIVISION PAGES
def division_page(fname, active, kicker, h1, lead, media, media_cap, tall, services, division, diagrams, cta_title, title, desc, extra=""):
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
        {crumbs([("index.html", "Home"), (None, kicker)])}
        <h1 class="reveal reveal-d1">{h1}</h1>
        <p class="lead reveal reveal-d2">{lead}</p>
        <div class="hero__actions reveal reveal-d3">
          <a href="schedule.html?division={division}" class="btn btn--red">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{TC[1]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {TC[0]}</a>
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
{extra}
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
{final_cta("", cta_title)}
  </main>
"""
    write(fname, head("", title, desc, fname) + header("", active) + body + footer(""))

division_page("plumbing.html", "plumbing.html", "Plumbing Division",
    "PSL Plumbing <em>&amp; Drains.</em>",
    "Leak detection, drains, water heaters, re-piping and sewer lines &mdash; handled by licensed &amp; insured, code-compliant plumbers. We also have diagrams that may assist you in identifying areas where a leak, deterioration or break can occur.",
    "dg-repiping.jpg", "Whole-house plumbing &mdash; 22 leak points", False, PLUMBING, "plumbing",
    ["water-heater", "bathtub", "shower", "kitchen", "repiping", "sewer"],
    "Ready to evaluate your <em>plumbing concerns?</em>",
    "Plumbing Services | PSL Plumbing & Drains",
    "Leak detection, drain clearing, water heaters, re-piping, sewer lines, toilets and faucets. Licensed & insured plumbers serving Florida's Treasure Coast and Gold Coast.")

division_page("electrical.html", "electrical.html", "Electrical Division",
    "Triphase <em>Electrical.</em>",
    "Breaker panels, circuits, lighting, ceiling fans and generators. Our infrared-certified thermography specialists help locate electrical faults early.",
    "crop-panel.jpg", "Circuit breaker panel &mdash; fault points", True, ELECTRICAL, "electrical",
    ["panel", "disconnect", "receptacles", "fixtures"],
    "Ready to evaluate your <em>electrical concerns?</em>",
    "Electrical Services | Triphase Electrical",
    "Breaker panel corrections, circuits, lighting, ceiling fans, receptacles, generators and thermal-imaging diagnostics by licensed electricians in Florida.")

# ------------------------------------------------------------------ SERVICE PAGES
def service_page(division, s, siblings):
    slug, icon, title, short, intro, options, signs, dg = s
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
          <figure class="detail__figure{' detail__figure--tall' if division == 'electrical' else ''}" {lb_attrs(dg, button=False)}>
            {frame(dg, b)}{lb_template(dg, b)}
            <figcaption><i class="fa-solid fa-circle-info"></i><span>{dtext} {'Hover or tap a number to see each point. ' if POINTS.get(dg) else ''}</span><button type="button" class="dg-enlarge" data-open-lightbox><i class="fa-solid fa-expand"></i> Enlarge</button></figcaption>
          </figure>
          {legend(dg)}
        </div>"""
    rel = "".join(f'<a href="{division}-{x[0]}.html">{x[2]} <i class="fa-solid fa-arrow-right"></i></a>' for x in siblings if x[0] != slug)
    plain_title = title.replace("&amp;", "&")
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
          <a href="{b}schedule.html?division={division}&amp;service={plain_title.replace(' ', '+').replace('&', '%26')}" class="btn btn--red">Request This Service <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{TC[1]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {TC[0]}</a>
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
        <a href="{b}schedule.html?division={division}&amp;service={plain_title.replace(' ', '+').replace('&', '%26')}" class="btn btn--red btn--block">Schedule Now <i class="fa-solid fa-arrow-right"></i></a>
        <div class="aside__phones">
          <a href="{TC[1]}">Treasure Coast <b>{TC[0]}</b></a>
          <a href="{GC[1]}">Gold Coast <b>{GC[0]}</b></a>
        </div>
        <div class="aside__lic">Licensed &amp; insured &middot; {LIC}</div>
      </aside>
    </div>
  </section>

  <section class="section section--white">
    <div class="container">
      <div class="head head--stack reveal"><span class="kicker">More {div_name.lower()} services</span><h2 class="h2">Other ways <em>we can help.</em></h2></div>
      <div class="related">{rel}</div>
    </div>
  </section>
{final_cta(b)}
  </main>
"""
    desc = f"{plain_title} in Port St. Lucie & Boca Raton, FL. {unescape(short)} Licensed & insured {div_name.lower()} contractors. Free on-site evaluation."
    if len(desc) > 160:
        desc = f"{plain_title} in Port St. Lucie & Boca Raton, FL. {unescape(short)} Free on-site evaluation."
    html = head(b, f"{plain_title} | {div_brand.replace('&amp;', '&')}", desc, f"services/{division}-{slug}.html") + header(b, f"{division}.html") + body + footer(b)
    # service pages live one folder down: fix relative asset links in diagram cards / lightbox
    write(f"services/{division}-{slug}.html", html)

for s in PLUMBING: service_page("plumbing", s, PLUMBING)
for s in ELECTRICAL: service_page("electrical", s, ELECTRICAL)

# ------------------------------------------------------------------ BUILDING
bcards = "".join(f"""
        <a class="svc-card reveal" href="schedule.html?division=building&amp;service={t.replace('&amp;', '%26').replace(' ', '+')}">
          <span class="svc-card__icon"><i class="fa-solid {i}"></i></span>
          <h3>{t}</h3><p>{d}</p>
          <span class="svc-card__foot">Request an Evaluation <i class="fa-solid fa-arrow-right"></i></span>
        </a>""" for i, t, d in BUILDING)
building = f"""
  <main>
  <section class="page-hero">
    <div class="hero__bg"></div>
    <div class="container page-hero__grid">
      <div>
        {crumbs([("index.html", "Home"), (None, "Building &amp; Remodeling Division")])}
        <h1 class="reveal reveal-d1">U.S. <em>Construction.</em></h1>
        <p class="lead reveal reveal-d2">Remodeling, building inspections and trade work by licensed &amp; insured, code-compliant builders. Our quality craftsmanship enhances the safety, elegance and functionality of your home or property.</p>
        <div class="hero__actions reveal reveal-d3">
          <a href="schedule.html?division=building" class="btn btn--red">Schedule a Free Evaluation <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{TC[1]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {TC[0]}</a>
        </div>
        <div class="mini-trust reveal reveal-d3"><span><i class="fa-solid fa-building"></i> CBC1264899</span><span><i class="fa-solid fa-clipboard-check"></i> Permitting support</span><span><i class="fa-solid fa-temperature-half"></i> Infrared inspections</span></div>
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
        <div class="reveal"><span class="kicker">01 <span>&mdash; Services</span></span><h2 class="h2">Building &amp; <em>remodeling.</em></h2></div>
        <p class="reveal reveal-d1">Plumbing, electrical and building trades under one company &mdash; fewer handoffs, fewer delays.</p>
      </div>
      <div class="svc-grid" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">{bcards}
      </div>
    </div>
  </section>

  <section class="section section--white">
    <div class="container why">
      <div class="why__sticky reveal">
        <span class="kicker">02 <span>&mdash; Building inspections</span></span>
        <h2 class="h2">Address matters <em>before they become costly.</em></h2>
        <p class="lead">We evaluate critical components, identify deficiencies, and highlight areas that may require attention.</p>
      </div>
      <ol class="why__list">
        <li class="why__item reveal"><span class="why__num">01</span><div><h3>Plan repairs</h3><p>Know what needs attention and prioritize the work.</p></div></li>
        <li class="why__item reveal"><span class="why__num">02</span><div><h3>Budget effectively</h3><p>Transparent estimates so you can plan with confidence.</p></div></li>
        <li class="why__item reveal"><span class="why__num">03</span><div><h3>Reduce risk</h3><p>Lower the risk of floods, insurance claims, health risks associated with damp or humid conditions, and costly last-minute corrections.</p></div></li>
      </ol>
    </div>
  </section>
{final_cta("", "Ready to evaluate your <em>building concerns?</em>")}
  </main>
"""
write("building.html", head("", "Building & Remodeling | U.S. Construction",
      "Remodeling, building inspections and trade work by licensed & insured builders on Florida's Treasure Coast and Gold Coast. Free on-site evaluations.", "building.html") + header("", "building.html") + building + footer(""))

# ------------------------------------------------------------------ COMMERCIAL
commercial = f"""
  <main>
  <section class="page-hero">
    <div class="hero__bg"></div>
    <div class="container page-hero__grid page-hero__grid--solo">
      <div>
        {crumbs([("index.html", "Home"), (None, "Commercial Clients")])}
        <h1 class="reveal reveal-d1">Built for <em>commercial</em> schedules.</h1>
        <p class="lead reveal reveal-d2">Our meticulous work reduces labor costs, on-site corrections and roughing relocations that cause delays, material waste and unnecessary costs. This helps keep schedules flowing uninterrupted, on time and on budget.</p>
        <div class="hero__actions reveal reveal-d3">
          <a href="schedule.html?division=commercial" class="btn btn--red">Request a Site Evaluation <i class="fa-solid fa-arrow-right"></i></a>
          <a href="{TC[1]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {TC[0]}</a>
        </div>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="container why">
      <div class="why__sticky reveal">
        <span class="kicker">01 <span>&mdash; Proactive evaluations</span></span>
        <h2 class="h2">Plan ahead. <em>Avoid costly surprises.</em></h2>
        <p class="lead">We evaluate critical components, identify deficiencies, and highlight areas that may require attention, giving you the opportunity to:</p>
      </div>
      <ol class="why__list">
        <li class="why__item reveal"><span class="why__num">01</span><div><h3>Plan repairs</h3><p>Schedule work around your operations instead of reacting to failures.</p></div></li>
        <li class="why__item reveal"><span class="why__num">02</span><div><h3>Budget effectively</h3><p>Transparent estimates that let you allocate budget with confidence.</p></div></li>
        <li class="why__item reveal"><span class="why__num">03</span><div><h3>Address matters early</h3><p>Resolve issues before they become costly &mdash; for a smoother, more predictable experience.</p></div></li>
      </ol>
    </div>
  </section>

  <section class="section dark dark--900">
    <div class="container commercial">
      <div class="reveal">
        <span class="kicker kicker--light">02 <span>&mdash; Risk reduction</span></span>
        <h2 class="h2">A proactive approach <em>reduces:</em></h2>
      </div>
      <div class="benefits reveal reveal-d1">
        <div class="benefit"><i class="fa-solid fa-house-flood-water"></i><strong>The risk of floods</strong><span>Leaks and failures caught early.</span></div>
        <div class="benefit"><i class="fa-solid fa-file-shield"></i><strong>Insurance claims</strong><span>Fewer incidents, fewer claims.</span></div>
        <div class="benefit"><i class="fa-solid fa-lungs"></i><strong>Health risks</strong><span>Associated with damp or humid conditions.</span></div>
        <div class="benefit"><i class="fa-solid fa-person-digging"></i><strong>Last-minute corrections</strong><span>Costly corrections that stall schedules.</span></div>
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
        <a class="svc-card reveal" href="plumbing.html"><span class="svc-card__icon"><i class="fa-solid fa-faucet-drip"></i></span><h3>PSL Plumbing &amp; Drains</h3><p>Leak detection, re-piping, drains, sewer lines and water heaters.</p><span class="svc-card__foot">CFC1431064 <i class="fa-solid fa-arrow-right"></i></span></a>
        <a class="svc-card reveal reveal-d1" href="electrical.html"><span class="svc-card__icon"><i class="fa-solid fa-bolt"></i></span><h3>Triphase Electrical</h3><p>Panels, circuits, lighting, generators and thermal diagnostics.</p><span class="svc-card__foot">EC13003241 <i class="fa-solid fa-arrow-right"></i></span></a>
        <a class="svc-card reveal reveal-d2" href="building.html"><span class="svc-card__icon"><i class="fa-solid fa-helmet-safety"></i></span><h3>U.S. Construction</h3><p>Remodeling, building inspections, trade work and permitting.</p><span class="svc-card__foot">CBC1264899 <i class="fa-solid fa-arrow-right"></i></span></a>
      </div>
    </div>
  </section>
{final_cta("", "Keep your project <em>on time and on budget.</em>", "Talk to our licensed plumbing, electrical and building team about your next commercial project.")}
  </main>
"""
write("commercial.html", head("", "Commercial Services | U.S. Construction & Plumbing Authority",
      "Commercial plumbing, electrical and building services that reduce labor costs, on-site corrections and delays. Keep schedules on time and on budget.", "commercial.html") + header("", "commercial.html") + commercial + footer(""))

# ------------------------------------------------------------------ SCHEDULE
schedule = f"""
  <main>
  <section class="page-hero" style="padding-bottom:120px">
    <div class="hero__bg"></div>
    <div class="container form-shell" style="position:relative">
      <div>
        {crumbs([("index.html", "Home"), (None, "Schedule")])}
        <h1 class="reveal reveal-d1">Schedule your <em>appointment now.</em></h1>
        <p class="lead reveal reveal-d2">Fill out this form to request a complimentary visit to your site. One of our officers will call you to schedule a visit to evaluate your project at no cost to you.</p>
        <ul class="info-list reveal reveal-d3">
          <li><i class="fa-solid fa-phone"></i><div><small>Treasure Coast</small><a href="{TC[1]}">{TC[0]}</a></div></li>
          <li><i class="fa-solid fa-phone"></i><div><small>Gold Coast</small><a href="{GC[1]}">{GC[0]}</a></div></li>
          <li><i class="fa-solid fa-envelope"></i><div><small>Email</small><a href="mailto:{EMAIL}">{EMAIL}</a></div></li>
          <li><i class="fa-solid fa-location-dot"></i><div><small>Offices</small><strong>Port St. Lucie &amp; Boca Raton, FL</strong></div></li>
        </ul>
      </div>
      <div class="form-card reveal reveal-d1">
        <h2>Free evaluation / estimate</h2>
        <p>No cost. No obligation. We&rsquo;ll call you to confirm your visit.</p>
        <form id="appointmentForm" novalidate>
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
          <p class="form-note">Prefer to talk? Call <a href="{TC[1]}">{TC[0]}</a> or <a href="{GC[1]}">{GC[0]}</a></p>
          <p class="form-privacy">We use your information only to respond to your request.</p>
        </form>
        <div class="form-success" role="status">
          <i class="fa-solid fa-circle-check"></i>
          <h2 tabindex="-1">Thank you!</h2>
          <p>Your email app should open with your request ready to send. Please press <strong>Send</strong> in your email app &mdash; one of our officers will then call you to schedule your free evaluation.</p>
          <p class="form-fallback">Email didn&rsquo;t open? Write to <a href="mailto:{EMAIL}">{EMAIL}</a> or call <a href="{TC[1]}">{TC[0]}</a>.</p>
          <button type="button" class="btn btn--line-dark btn--sm" data-edit-request>Edit My Request</button>
        </div>
      </div>
    </div>
  </section>
  </main>
"""
write("schedule.html", head("", "Schedule a Free Evaluation | U.S. Construction Authority",
      "Request a complimentary site visit. One of our officers will call you to schedule a free evaluation of your plumbing, electrical or building project.", "schedule.html") + header("", "") + schedule + footer(""))

# ------------------------------------------------------------------ 404
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
          <a href="{TC[1]}" class="btn btn--glass"><i class="fa-solid fa-phone"></i> {TC[0]}</a>
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

# ------------------------------------------------------------------ robots.txt + sitemap.xml
robots = "User-agent: *\nAllow: /\n"
if SITE_URL:
    robots += f"\nSitemap: {SITE_URL}/sitemap.xml\n"
    urls = "".join(f"  <url><loc>{SITE_URL}/{'' if p == 'index.html' else p}</loc></url>\n" for p in PAGES)
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
elif os.path.exists(os.path.join(OUT, "sitemap.xml")):
    os.remove(os.path.join(OUT, "sitemap.xml"))
with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
    f.write(robots)

# ------------------------------------------------------------------ icon subset (Font Awesome, only glyphs in use)
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

try:
    n_icons = build_icons()
except ImportError:
    n_icons = "skipped (pip install fonttools brotli)"

print("pages:", len(PAGES), "| icons:", n_icons, "| SITE_URL:", SITE_URL or "(not set)")

"""Rebuild index.html from processing/app_template.html.

You only need this if you prefer editing the template (the page without the long map-library
stylesheet pasted in). Editing index.html directly also works.

    python processing/build_page.py
"""
from pathlib import Path

here = Path(__file__).resolve().parent
tpl = (here / "app_template.html").read_text(encoding="utf-8")
css = (here / "vendor" / "maplibre-gl.css").read_text(encoding="utf-8")
full = tpl.replace("/*MAPLIBRE_CSS*/", css)
i = full.index('<div id="app">')
head, body = full[:i], full[i:]
page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="Interactive map of Nigeria: 2025 population, age and sex, health facilities, '
        'poverty and displacement by state and LGA.">\n<meta name="theme-color" content="#121118">\n'
        + head + '<style>html,body{margin:0}img{max-width:100%}</style>\n</head>\n<body>\n' + body + '\n</body>\n</html>\n')
(here.parent / "index.html").write_text(page, encoding="utf-8")
print("Wrote", here.parent / "index.html")

# U.S. Construction & Plumbing Authority — website

Static site (HTML/CSS/JS). Deploys as-is on Vercel (no build step needed).

- Edit copy/markup in `_source/build.py`, then run `python3 _source/build.py` (needs `pip install pillow fonttools brotli`).
- Set the production domain before launch: `SITE_URL=https://www.example.com python3 _source/build.py`
  (adds canonical URLs, og:url/og:image and sitemap.xml).
- `_source/` and this README are excluded from deployment via `.vercelignore`.

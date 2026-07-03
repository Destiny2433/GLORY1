# Publication Readiness Fixes

## Step 1 — Repo review (done/in-progress)
- [x] Inspect remaining templates: `templates/admin.html`, `templates/gallery.html`, `templates/About.html`, `templates/support.html`, `templates/login.html`, `templates/thank-you.html`
- [ ] Inspect any static manifest/service-worker registration usage

## Step 2 — Backend hardening + correctness
- [ ] Fix duplicated/invalid code blocks in `app.py`
- [ ] Remove/disable `debug=True` for production
- [ ] Move secret values to environment variables
- [ ] Verify all routes render with correct template variables

## Step 3 — Frontend correctness
- [ ] Fix malformed HTML / mismatched closing tags in `templates/index.html`
- [ ] Ensure unique HTML IDs (fix duplicate `id` in `templates/volunteer.html`)

## Step 4 — Frontend JS sanity
- [ ] Ensure `static/script.js` only runs when required DOM nodes exist
- [ ] Confirm lightbox/gallery behavior does not throw when empty
- [ ] Confirm service worker registration (if present) works

## Step 5 — Sanity test
- [x] `python -m compileall .`
- [ ] Run Flask locally and load key routes without errors

## Step 6 — Final prep
- [ ] Confirm no hardcoded secrets remain
- [ ] Ensure static asset paths use `url_for('static', ...)` consistently


# IW Spatial Toolkit landing page

Static, dependency-free landing page prepared for GitHub Pages.

## Publish

Copy the contents of `dist/` to the root of the branch or folder served by GitHub Pages. All internal paths are relative, so the site works on both account-level and project-level Pages URLs.

## Configure links

Edit `dist/site-config.js`:

```js
window.IW_SITE_CONFIG = {
  docsUrl: "./docs/",
  downloadUrl: "./downloads/IW-Spatial-Context-1.0.RC3.zip",
  githubUrl: "https://github.com/your-account/iw-spatial-toolkit"
};
```

The included defaults already point to the bundled documentation and RC3 ZIP. Replace `githubUrl`, and replace the other two values if the files will live elsewhere.

## Contents

- `dist/index.html` — landing page
- `dist/site-config.js` — editable destinations
- `dist/assets/` — styles, behavior, logo, and hero artwork
- `dist/docs/` — self-contained full reference
- `dist/downloads/` — toolkit ZIP

No build step, framework, third-party fonts, analytics, or runtime network calls are required.

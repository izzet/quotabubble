# Agent and provider icons

The provider marks on the site identify the tools QuotaBubble can read usage
from. They are used only to indicate compatibility and are not part of
QuotaBubble's own branding.

- Icons come from the [`@lobehub/icons-static-svg`](https://github.com/lobehub/lobe-icons)
  npm package (MIT License), declared in `website/package.json` and imported by
  URL in `website/src/data/icons.ts`. Upstream files use `fill="currentColor"`,
  so the site renders them through a CSS `mask-image`.
- Zed has no icon upstream yet, so its tile renders the name as text. Add a slug
  to `icons.ts` and the matching `icon` value to `providers.json` once one exists.

All product names, logos, and brands are the property of their respective
owners and are used to identify the tools each integration talks to. Their use
does not imply any affiliation with or endorsement by the trademark holders.

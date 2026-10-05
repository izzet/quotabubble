# Agent and provider icons

The SVG marks in this directory identify the tools QuotaBubble can read usage
from. They are used only to indicate compatibility, in a monochrome mask, and
are not part of QuotaBubble's own branding.

- `claudecode.svg`, `codex.svg`, `githubcopilot.svg`, `cursor.svg`,
  `grok.svg`, `kimi.svg`, `deepseek.svg`, `openrouter.svg`, `zai.svg`,
  `opencode.svg`, `antigravity.svg` are from
  [`@lobehub/icons`](https://github.com/lobehub/lobe-icons) (`packages/static-svg`),
  licensed under the MIT License. Upstream files are `fill="currentColor"`, so
  the site renders them through a CSS `mask-image`.
- Zed has no icon upstream yet, so its tile renders the name as text. Add an
  icon here and a matching `icon` value in `website/src/data/providers.json`
  once one is available.

All product names, logos, and brands are the property of their respective
owners and are used to identify the tools each integration talks to. Their use
does not imply any affiliation with or endorsement by the trademark holders.

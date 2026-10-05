// Provider marks from @lobehub/icons-static-svg (MIT), imported by URL so Vite
// emits only the icons we actually use. They ship with fill="currentColor", so
// the site renders them through a CSS mask-image that inherits the tile colour.
//
// Zed has no upstream icon: its tile renders the provider name as text. Register
// a slug here and set the matching "icon" in providers.json if one is added.
import antigravity from "@lobehub/icons-static-svg/icons/antigravity.svg?url&no-inline";
import claudecode from "@lobehub/icons-static-svg/icons/claudecode.svg?url&no-inline";
import codex from "@lobehub/icons-static-svg/icons/codex.svg?url&no-inline";
import cursor from "@lobehub/icons-static-svg/icons/cursor.svg?url&no-inline";
import deepseek from "@lobehub/icons-static-svg/icons/deepseek.svg?url&no-inline";
import githubcopilot from "@lobehub/icons-static-svg/icons/githubcopilot.svg?url&no-inline";
import grok from "@lobehub/icons-static-svg/icons/grok.svg?url&no-inline";
import kimi from "@lobehub/icons-static-svg/icons/kimi.svg?url&no-inline";
import opencode from "@lobehub/icons-static-svg/icons/opencode.svg?url&no-inline";
import openrouter from "@lobehub/icons-static-svg/icons/openrouter.svg?url&no-inline";
import zai from "@lobehub/icons-static-svg/icons/zai.svg?url&no-inline";

export const providerIcons: Record<string, string> = {
  antigravity,
  claudecode,
  codex,
  cursor,
  deepseek,
  githubcopilot,
  grok,
  kimi,
  opencode,
  openrouter,
  zai,
};

# QuotaBubble

QuotaBubble is a lightweight cross-platform desktop utility that displays AI usage limits and remaining quota in a small floating widget.

The goal is to make usage information for tools such as Claude Code, OpenAI Codex, and eventually other AI coding assistants continuously visible without requiring the user to open a dashboard, terminal command, or browser page.

## Core concept

QuotaBubble should appear as a small frameless floating bubble or pill that can be placed anywhere on the desktop and moved freely between monitors.

The widget should remain visible above normal application windows, but stay visually unobtrusive.

When idle, it should fade to very low opacity so it is still faintly visible without becoming distracting. When the mouse moves over it, it should smoothly become fully visible and optionally expand to show additional usage details.

The experience should feel similar to a lightweight desktop HUD rather than a traditional application window.

## Primary UX

Idle state:

* Small floating bubble or compact pill
* Approximately 5–15% opacity
* Shows only the most important usage indicator
* Remains visible on the desktop
* Always-on-top
* Does not steal keyboard focus

Hover state:

* Smoothly fades to near-full opacity
* Expands if necessary
* Shows usage for each configured provider
* Displays percentage used or percentage remaining
* Shows reset countdowns where available
* Allows the widget to be dragged to another location or monitor

Example:

Claude   42% remaining
Codex    67% remaining
Reset    1h 24m

## Initial providers

Version 1 should support:

* Claude Code
* OpenAI Codex

The provider architecture should be modular so additional services can be added later without changing the UI architecture.

Possible future providers include:

* Gemini CLI
* Cursor
* GitHub Copilot
* OpenAI API
* Anthropic API
* other AI development tools

## Core requirements

The first usable version should include:

1. Frameless floating window
2. Transparent or translucent background
3. Rounded bubble/pill appearance
4. Always-on-top behavior
5. Dragging anywhere on the desktop
6. Correct behavior across multiple monitors
7. Smooth fade-in on hover
8. Smooth fade-out after the cursor leaves
9. Configurable idle opacity
10. Position persistence between launches
11. Claude Code usage display
12. Codex usage display
13. Usage percentage and reset time
14. Automatic periodic refresh
15. Right-click context menu
16. Quit option
17. Settings option
18. Start-at-login option
19. Minimal CPU usage while idle
20. No taskbar entry unless intentionally enabled

## Interaction details

Dragging:

The user should be able to click and drag the widget anywhere on the screen.

The widget should move seamlessly across multiple monitors.

Its last location should be restored after restarting the application.

Optional later behavior:

* snap to screen edges
* snap to corners
* lock position
* reset position
* remember separate positions for different monitor configurations

Hover behavior:

When the pointer enters the widget:

* animate opacity from idle opacity to approximately 95–100%
* optionally expand from compact mode to detailed mode

When the pointer leaves:

* wait for a short configurable delay
* collapse if expanded
* fade back to idle opacity

The fade should feel smooth and subtle rather than abrupt.

## Visual design

The interface should be minimal and modern.

Preferred style:

* rounded corners
* semi-transparent background
* subtle border
* compact typography
* small progress bars or rings
* no conventional title bar
* no unnecessary buttons while idle

The widget should be readable on both light and dark backgrounds.

A future option could automatically adjust styling depending on the desktop theme.

## Suggested display modes

Compact:

QuotaBubble only displays a small indicator such as:

Claude 42%

or:

C 42% · X 67%

Expanded:

Claude
5h      42% remaining
Weekly  71% remaining
Reset   1h 24m

Codex
5h      67% remaining
Weekly  54% remaining
Reset   2h 08m

The user should eventually be able to choose between:

* bubble
* horizontal pill
* vertical card
* compact percentage-only mode

## Architecture

Keep the application separated into three main areas:

### UI

Responsible for:

* floating window
* animation
* drag behavior
* hover behavior
* progress indicators
* settings UI

### Provider layer

Each AI provider should implement a common interface.

Conceptually:

Provider

* name
* icon
* fetch_usage()
* session_limit
* weekly_limit
* reset_time
* connection_status

Implementations:

* ClaudeProvider
* CodexProvider

Providers should be independent from the UI.

### Application services

Responsible for:

* polling providers
* caching results
* configuration
* persistence
* logging
* startup behavior
* platform-specific functionality

## Suggested project structure

quotabubble/

```
app/
    main
    state
    settings

ui/
    bubble
    expanded_panel
    animations
    context_menu

providers/
    base
    claude
    codex

platform/
    windows
    macos
    linux

services/
    usage_polling
    persistence
    startup

assets/

tests/
```

## Cross-platform considerations

The common application should remain platform-independent where possible.

Platform-specific behavior should live behind a small abstraction layer.

Examples include:

Windows:

* always-on-top window flags
* hiding the window from Alt-Tab
* login startup
* monitor work-area handling

macOS:

* NSWindow level
* Spaces behavior
* login items
* menu bar considerations

Linux:

* X11/Wayland differences
* always-on-top behavior
* compositor differences

Do not allow platform-specific code to leak heavily into the provider or application logic.

## Performance goals

QuotaBubble should behave like a small system utility.

Targets:

* near-zero CPU usage while idle
* low memory usage
* no constant redraw loop
* usage polling performed infrequently
* UI only updates when values change
* no unnecessary network calls

A reasonable default polling interval would be approximately 30–60 seconds unless a provider requires something different.

## Security

QuotaBubble should avoid collecting or transmitting user data.

Authentication credentials should never be uploaded to a QuotaBubble server.

Where possible, usage information should be read from:

* official APIs
* provider CLI commands
* local configuration
* locally stored authenticated sessions

Secrets should never be written to logs.

QuotaBubble should ideally function entirely locally.

## Settings

Initial settings should include:

* launch at login
* idle opacity
* fade delay
* refresh interval
* show percentage used vs percentage remaining
* compact vs expanded display
* always-on-top toggle
* provider visibility
* progress bar vs text-only display

Future settings could include:

* custom colors
* font size
* edge snapping
* click-through mode
* hotkeys
* notification thresholds

## Future ideas

Possible later features:

* usage history graphs
* burn-rate estimation
* predicted time until quota exhaustion
* alerts at configurable thresholds
* system tray integration
* provider health indicators
* session cost estimates
* token usage
* context-window usage
* per-project usage
* keyboard shortcut to reveal/hide the bubble
* multiple independent bubbles
* plugin/provider SDK

## MVP definition

The MVP is complete when a user can launch QuotaBubble, see Claude and Codex usage in a floating always-on-top widget, drag it between monitors, leave it somewhere on the desktop, have it fade almost invisible when idle, and have it become readable again when hovered.

The MVP should prioritize reliability and smooth desktop behavior over advanced settings or elaborate visual design.

The application should feel like something the user can leave running all day and forget about until they need to glance at their remaining AI usage.

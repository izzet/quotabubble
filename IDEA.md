If you genuinely want **Windows + macOS + Linux**, I’d probably choose **Python + PySide6/Qt** for this particular app.

Qt already gives you the exact primitives your widget needs across platforms: frameless windows, translucent backgrounds, always-on-top flags, mouse tracking, custom painting, animations, and multi-monitor APIs. Qt’s docs specifically support translucent top-level windows on Windows and macOS, with frameless-window behavior for this kind of UI. ([Qt Documentation][1])

For your project, I’d rank them:

| Stack                | Fit for your widget | Main tradeoff                                    |
| -------------------- | ------------------- | ------------------------------------------------ |
| **Python + PySide6** | ⭐⭐⭐⭐⭐               | Larger packaged app / Python runtime             |
| **Rust + Tauri**     | ⭐⭐⭐⭐                | More complexity, especially native window quirks |
| **C# + WPF**         | ⭐⭐⭐⭐⭐ on Windows    | Windows only                                     |
| **C# + Avalonia**    | ⭐⭐⭐⭐                | Cross-platform, but another framework to learn   |

### Why I'd lean PySide6

Your app isn't computationally demanding. It's essentially:

```text
API / local usage data
        ↓
small state model
        ↓
floating transparent widget
        ↓
fade / expand / drag / snap
```

Python is more than fast enough.

Your actual hard problems will be UI/window behavior and integrating with Claude/Codex authentication or local usage data. Qt handles the UI side very comfortably.

A PySide6 window can roughly be:

```python
self.setWindowFlags(
    Qt.FramelessWindowHint |
    Qt.WindowStaysOnTopHint |
    Qt.Tool
)

self.setAttribute(Qt.WA_TranslucentBackground)
```

Then you can make something visually like:

```text
Idle — 8% opacity

        ◉  47%


Hover

╭──────────────────────────────╮
│  Claude  ██████░░░  62%     │
│  Codex   ████░░░░░  41%     │
│                   ↻ 1h 42m   │
╰──────────────────────────────╯
```

And Qt's screen APIs make moving the same window between monitors pretty straightforward.

### Where Rust makes sense

Rust isn't crazy here, but I'd choose it for different reasons.

It makes sense if you care strongly about:

* tiny idle memory footprint
* a native standalone binary
* instant startup
* no Python runtime
* eventually distributing it publicly to lots of people
* enjoying Rust enough that the additional engineering isn't a burden

But Rust itself doesn't magically solve the UI problem. You still need something like Tauri, Slint, egui, GTK, iced, etc.

For this particular app, **Tauri** is probably what I'd use if choosing Rust. The frontend can be HTML/CSS, which makes your animated floating pill/bubble extremely easy to design.

That architecture would be:

```text
Rust
 ├── usage fetching
 ├── credential handling
 ├── settings
 └── native window management
          │
          ▼
     HTML / CSS / JS
     ┌──────────────┐
     │ Claude   48% │
     │ Codex    72% │
     └──────────────┘
```

That can produce an exceptionally polished UI.

The downside is that when you encounter something like:

> "On macOS I want this window above normal applications but below full-screen spaces, while on Windows I want it excluded from Alt-Tab..."

you're inevitably dipping into platform-specific APIs anyway.

And that's true regardless of framework.

### Cross-platform doesn't mean zero platform-specific code

For a normal desktop app, Qt abstracts almost everything.

For a **weird floating desktop widget**, you're deliberately interacting with the window manager in unusual ways.

You'll probably end up with:

```text
common/
    usage_provider
    settings
    widget_state

platform/
    windows.py
    macos.py
    linux.py
```

because the ideal behavior differs between:

**Windows**

* `WS_EX_TOOLWINDOW`
* maybe `WS_EX_NOACTIVATE`
* monitor/work-area APIs
* startup registration

**macOS**

* NSWindow levels
* Spaces behavior
* menu bar interaction
* login items

**Linux**

* X11 vs Wayland differences
* compositor-specific always-on-top behavior

That's normal and I wouldn't try too hard to avoid it.

### One thing I would *not* optimize for initially

Binary size.

PyInstaller/Nuitka + Qt can produce something much larger than a Rust executable. You might wind up distributing a 70–150 MB package for an app whose actual code is tiny.

For a desktop utility, I don't think that's particularly important initially.

I'd rather have:

```text
100 MB app
+ 2 days to prototype
+ easy iteration
```

than:

```text
10 MB app
+ a week wrestling with windowing behavior
```

You can optimize packaging later.

### There's also a compelling C# option

If you're comfortable with C#, **Avalonia** is worth considering. Conceptually it's the cross-platform cousin of WPF: C#/XAML with Windows, macOS and Linux support.

But if you don't already know Avalonia, I'd still take PySide6. Qt is much older and extremely battle-tested for strange desktop utility windows.

And WPF itself remains explicitly Windows-only despite modern .NET being cross-platform. ([Microsoft Learn][2])

### What I'd choose for *your* idea

I'd prototype it in **PySide6**.

Keep the architecture deliberately simple:

```text
usagebubble/
│
├── main.py
│
├── ui/
│   ├── bubble.py
│   └── expanded_panel.py
│
├── providers/
│   ├── claude.py
│   └── codex.py
│
├── platform/
│   ├── windows.py
│   ├── macos.py
│   └── linux.py
│
└── settings.py
```

And build only these features initially:

1. frameless transparent pill
2. drag anywhere
3. multi-monitor support
4. always-on-top
5. fade to ~10% after 2–3 seconds
6. restore to 100% on hover
7. Claude + Codex percentage
8. remember its position
9. right-click → settings / quit
10. start at login

That would give you the actual product very quickly.

**If it eventually becomes something you want to distribute seriously**, I'd then consider either keeping Qt and polishing the packaging, or rewriting the shell in Rust/Tauri if startup/memory/distribution become important.

I wouldn't start in Rust merely because other widget authors are using Rust. For a ~150×50 px floating usage HUD, **PySide6 is probably the highest productivity-to-pain ratio.**

[1]: https://doc.qt.io/qtforpython-6/PySide6/QtQuickWidgets/QQuickWidget.html?utm_source=chatgpt.com "PySide6.QtQuickWidgets.QQuickWidget - Qt for Python"
[2]: https://learn.microsoft.com/en-us/dotnet/desktop/wpf/overview/?utm_source=chatgpt.com "What is Windows Presentation Foundation - WPF | Microsoft Learn"

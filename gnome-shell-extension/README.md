# QuotaBubble GNOME Shell extension

This folder is the source of the `quotabubble@izzet.dev` GNOME Shell extension.
The Linux package installs it under:

```text
/usr/share/gnome-shell/extensions/quotabubble@izzet.dev/
```

The extension connects to the user-session D-Bus service
`dev.izzet.quotabubble.Service1`. It owns desktop rendering; the Python service owns
provider polling and persistence.

During development, package the extension with:

```bash
gnome-extensions pack --force gnome-shell-extension
```

Install the resulting archive through the Extensions application, then enable
QuotaBubble. Do not reload or restart the active GNOME Shell while developing
on Wayland; use an isolated nested session for integration testing instead.

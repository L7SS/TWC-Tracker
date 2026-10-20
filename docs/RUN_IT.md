# Ways to run it

| Way | Where your data lives | Use it for |
|---|---|---|
| **On your computer** (recommended) | `~/.twc-tracker/`, owner-only, never uploaded | Your real claim |
| **GitHub Codespaces** | GitHub's servers | Trying it out with the **sample data only** |

## On your computer

```bash
pipx run --spec "git+https://github.com/L7SS/TWC-Tracker" twc-tracker ui     # no install step
# or
pip install "git+https://github.com/L7SS/TWC-Tracker" && twc-tracker ui
# Word export too:
pip install "twc-tracker[docx] @ git+https://github.com/L7SS/TWC-Tracker"
```

Releases (wheel + source) are attached to tagged versions on the repository's Releases page.

## Try it in GitHub Codespaces

[Open in Codespaces](https://codespaces.new/L7SS/TWC-Tracker). The container installs the app, copies `examples/*.csv` (made-up data) in, starts the web app and forwards the port **privately** (only you can open it).

A Codespace runs on GitHub's servers. The app shows a red warning there and the README says the same: **do not enter your real claim in a Codespace.** The app only accepts the forwarded Codespaces address (and `--allow-host` values you pass), still behind its per-run token.

## Why there is no hosted website

A public site would mean your job search, employers and claim details sit on someone else's server. This project's rule is that they stay on your computer, so it is something you run, not a service.

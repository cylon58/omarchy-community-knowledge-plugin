# Omarchy Community Knowledge

A small Omarchy Quattro bar plugin for setting up and maintaining the local
Community Knowledge companion. The companion helps supported coding agents
consult reviewed community fixes and optional improvements. It does not run a
service, poll in the background, repair automatically, or share anything by
itself.

## Requirements

- Omarchy Quattro
- Python 3.11 or newer and Git
- A release containing `vendor/omarchy-knowledge-setup.py` and
  `vendor/omarchy_community_knowledge_tools-0.3.0-py3-none-any.whl`

Codex, Claude Code, OpenCode, and Gemini CLI are supported initially. The
plugin reads the current `omarchy-default-agent` setting and does not change
it. Other agents receive a manual-install message instead of a false success.

## Install and update

Install a reviewed release with Omarchy's normal plugin command:

```sh
omarchy plugin add https://github.com/cylon58/omarchy-community-knowledge-plugin.git --enable
```

Open the bar panel and choose **Setup**. This explicitly runs the bundled,
reviewable setup program. It creates an isolated environment under
`~/.local/share/omarchy-knowledge-next`, an owned launcher at
`~/.local/bin/omarchy-knowledge`, agent skill links and their ownership receipt,
and accepted public data under `~/.cache/omarchy-knowledge-next`. It does not
use sudo or replace unrelated files.

Codex, OpenCode, and Gemini CLI use `~/.agents/skills`; Claude Code uses
`~/.claude/skills`. Setup links only the two companion-owned skills and records
their ownership under `~/.local/state/omarchy-knowledge-next`.

Update the plugin with `omarchy plugin update io.github.cylon58.omarchy-knowledge`,
then choose **Repair** to apply its newly bundled companion. **Refresh** runs an
explicit public-data sync; there is no timer or background service. A failed
refresh leaves the prior accepted snapshot usable and reports the error.

The agent skills can prepare a sanitized contribution preview. Public sharing
is a separate workflow and always requires approval after inspecting the
actual contents, destination, and attribution. Reading public knowledge needs
no account; sharing uses the user's own GitHub account and normal `gh` login.

## Safe removal

Removal is deliberately two-step:

1. Open the panel and choose **Remove**. This removes only companion paths
   recorded as owned by setup, including its agent skill links.
2. Then run
   `omarchy plugin remove io.github.cylon58.omarchy-knowledge`.

The accepted cache and local contribution drafts are retained. Delete those
separately only after deciding they are no longer wanted. If ownership checks
find modified or unrelated files, removal preserves them and reports the
conflict.

## Development and release assembly

The development repository intentionally does not track built companion
artifacts. Stage the two exact reviewed inputs into an export with:

```sh
python3 scripts/stage_vendor.py \
  --wheel /path/to/omarchy_community_knowledge_tools-0.3.0-py3-none-any.whl \
  --setup /path/to/setup_companion.py \
  --destination /path/to/export/vendor
```

Then run:

```sh
python3 -m unittest discover -s tests -v
omarchy plugin validate .
/usr/lib/qt6/bin/qmllint -I /usr/share/omarchy/shell BarWidget.qml Panel.qml
```

The bar/popup host structure follows the installed Omarchy clock plugin. That
upstream work is copyright David Heinemeier Hansson and licensed under the MIT
License; its notice is preserved in `THIRD_PARTY_NOTICES.md`.

## License

MIT. See `LICENSE`.

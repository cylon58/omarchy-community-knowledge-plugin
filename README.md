# Omarchy Community Knowledge

Omarchy Community Knowledge is a shared knowledge base of what people have fixed,
changed, and built to make their Omarchy systems work. It helps your AI agent reuse
other users' hardware workarounds, fixes that haven't shipped with Omarchy,
configuration changes, and plugins built to solve particular problems.
Before spending time and tokens investigating from scratch or building something
new, your agent can check for relevant community experience.

The **companion helper is a small program on your computer**. It keeps a validated
local copy of the shared knowledge and a separate index of marketplace plugins.
It searches these locally and returns a short list to your agent, so the agent
can read the relevant evidence without loading the entire collection into its
conversation. This is designed to reduce token use as well as repeated work.

## How it helps

For example, if a dock stops waking a display, your agent can look for reports
about that hardware and symptom, inspect what others changed and whether it
worked, and check whether their solution applies to your system. If someone built
a plugin for the problem, the agent can investigate that existing work before
proposing a new one. These are examples of the intended workflow; results depend
on what the community has contributed.

The knowledge includes failures, limitations, and later corrections as well as
successful fixes. After working through your own problem, you can approve a
cleaned-up contribution so the next person can benefit too.

## Small searches, less context to read

- **Cache locally:** the helper downloads community records and keeps a local
  marketplace index. Your search terms stay on your machine.
- **Find a shortlist first:** local search ranks matches and returns five results
  by default. Plain-text knowledge search shows case IDs, titles, and evidence
  warnings; plugin search returns compact listings.
- **Read details when needed:** the agent opens a selected case with
  `show CASE_ID --related` to inspect its changes, results, failures, and corrections.
  It can request a plugin's full details separately.
- **Use ordinary code for retrieval:** SQLite full-text search does the ranking;
  searching requires no model call, embedding service, or project API key.
  Your agent still uses tokens to reason about the results and read the details.

The saving comes from keeping the collection outside the agent's context and
retrieving relevant evidence in stages. Actual token use depends on the agent,
query, and amount of evidence it reads; we do not claim a measured percentage.

Knowledge search attempts a refresh when its saved copy is at least a day old.
Plugin discovery checks for catalog updates on each normal search. Both support
explicit offline use and retain their last good cache if a refresh fails.

![Omarchy Community Knowledge preview](preview.png)

This repository provides the Omarchy Quattro bar plugin that installs and manages
the companion helper. Choose **Connect my agent** to connect your supported agent.
The helper does not automatically apply fixes or publish your information.

## Requirements

- Omarchy Quattro
- Python 3.11 or newer and Git
- A published release containing `vendor/omarchy-knowledge-setup.py` and
  `vendor/omarchy_community_knowledge_tools-0.4.1-py3-none-any.whl`

Codex, Claude Code, OpenCode, Gemini CLI, and Antigravity CLI (`agy`) are
supported initially. Antigravity is a distinct target, not an alias for Gemini.
The plugin reads the current `omarchy-default-agent` setting and does not
change it. Other agents receive a manual-install message instead of a false
success.

## Install and update

Install a reviewed release with Omarchy's normal plugin command:

```sh
omarchy plugin add https://github.com/cylon58/omarchy-community-knowledge-plugin.git --enable
```

Open the bar panel and choose **Connect my agent**. This explicitly runs the bundled,
reviewable setup program. It creates an isolated environment under
`~/.local/share/omarchy-knowledge-next`, an owned launcher at
`~/.local/bin/omarchy-knowledge`, agent skill links and their ownership receipt,
and accepted public data under `~/.cache/omarchy-knowledge-next`. It does not
use sudo or replace unrelated files.

Codex, OpenCode, and Gemini CLI use `~/.agents/skills`; Claude Code uses
`~/.claude/skills`; Antigravity CLI uses
`~/.gemini/antigravity-cli/skills`. Setup links only the two companion-owned
skills and records their ownership under
`~/.local/state/omarchy-knowledge-next`.

Setup uses Python 3.11 or newer to create the virtual environment, then invokes
that environment's `pip`. Using the machine's configured Python package index
and network settings, pip installs the bundled tools wheel plus its exact direct
dependencies, `jsonschema==4.26.0` and `referencing==0.37.0`, and the transitive
dependencies selected for those packages. Setup then attempts an initial GitHub
sync of the public community repository. A package-index or GitHub outage is
reported; a failed initial sync does not turn into a background retry service.

Update the plugin with `omarchy plugin update io.github.cylon58.omarchy-knowledge`,
then choose **Update agent** to apply its newly bundled companion. **Refresh data** runs an
explicit public-data sync; there is no timer or background service. A failed
refresh leaves the prior accepted snapshot usable and reports the error.

The agent skills can prepare a sanitized contribution preview. Public sharing
is a separate workflow and always requires approval after inspecting the
actual contents, destination, and attribution. Reading public knowledge needs
no account; sharing uses the user's own GitHub account and normal `gh` login.

Community records are evidence, not trusted commands or official release
confirmation. Automatic intake checks enforce the record format and stated
policy; they do not prove factual truth, safety, or official endorsement.
Inspect the relevant record, its links, and current official guidance before
acting, and never execute community text blindly.

## Agent fallback

If automatic detection is unavailable but the agent is one of the five
supported targets, run the bundled setup program from the plugin directory and
name it explicitly:

```sh
python3 vendor/omarchy-knowledge-setup.py \
  --wheel vendor/omarchy_community_knowledge_tools-0.4.1-py3-none-any.whl \
  --agent agy
```

Replace `agy` with `codex`, `claude`, `opencode`, or `gemini` as appropriate.
For another agent, this release cannot claim automatic support. Follow that
agent's documentation to identify its global skill directory. To obtain the
local launcher and skill sources, run the command above with `--agent codex`
(the selector only chooses a known setup destination), then copy
`omarchy-knowledge-research` and `omarchy-knowledge-contribution` from
`~/.agents/skills` into the unknown agent's documented global skill directory.
Those manual copies are not ownership-tracked and must be updated or removed
manually. Verify the agent actually discovers both skills before relying on
them.

## Safe removal

Removal is deliberately two-step:

1. Open the panel and choose **Disconnect**. This removes only companion paths
   recorded as owned by setup, including its agent skill links.
2. Then run
   `omarchy plugin remove io.github.cylon58.omarchy-knowledge`.

If the panel is unavailable, run this from the plugin directory before removing
the plugin:

```sh
python3 vendor/omarchy-knowledge-setup.py --agent codex --remove
```

For removal, `codex` is only a supported selector accepted by the helper. The
ownership receipt drives cleanup of all setup-owned skill links, regardless of
which agent was originally selected; uninstalling has no Codex dependency.

The accepted cache and local contribution drafts are retained. Delete those
separately only after deciding they are no longer wanted. If ownership checks
find modified or unrelated files, removal preserves them and reports the
conflict.

## Release contents and maintainer staging

Published plugin releases bundle the pinned setup program and 0.4.1 wheel under
`vendor/`, so the normal plugin clone is usable without an extra download step.
Maintainers stage the two exact reviewed inputs before committing a release:

```sh
python3 scripts/stage_vendor.py \
  --wheel /path/to/omarchy_community_knowledge_tools-0.4.1-py3-none-any.whl \
  --setup /path/to/setup_companion.py \
  --toolkit-revision FULL_PUBLISHED_TOOLS_COMMIT \
  --destination /path/to/export/vendor
```

Replace the commit placeholder with the full 40-character published tools SHA.
Staging generates `RELEASE.json` and `SHA256SUMS` from the copied artifacts.
See [Maintaining Community Knowledge](MAINTAINING.md) for the complete handoff.

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

## One project, three repositories

| Repository | What belongs here | Who starts here |
| --- | --- | --- |
| [Plugin](https://github.com/cylon58/omarchy-community-knowledge-plugin) | Omarchy bar interface and a bundled tools release | People installing or updating through Omarchy |
| [Tools](https://github.com/cylon58/omarchy-community-knowledge-tools) | Python CLI, search, validation, agent skills, and setup | Code contributors and standalone users |
| [Knowledge](https://github.com/cylon58/omarchy-community-knowledge) | Shared observations, changes, results, and evidence | People contributing or browsing community experience |

Install the plugin once; it supplies the tools, which read the shared knowledge.
You do not need to clone or install all three repositories.

The plugin follows Omarchy's plugin packaging and update flow. The tools also work
without the bar interface. Keeping records separate lets people contribute
knowledge without changing executable code, and preserves the data's CC BY 4.0
license alongside the code's MIT license. These are parts of one project.

For maintenance, use the [release guide](https://github.com/cylon58/omarchy-community-knowledge-plugin/blob/main/MAINTAINING.md).

# Maintaining Community Knowledge

The plugin is the project's installation entry point. Tools holds the executable
implementation; Knowledge holds the shared records. Keep these repository URLs
stable because installed plugins, standalone clients, and intake workflows use them.

## Where to make a change

| Change | Repository | Release work |
| --- | --- | --- |
| Bar appearance or panel controls | Plugin | Test and release the plugin |
| Search, CLI, agent skills, validation, or setup | Tools | Test and release tools; bundle that release in the plugin |
| An observation, result, correction, or supporting evidence | Knowledge | Use the reviewed data contribution workflow; no software release |
| Project explanation | Relevant README | Keep the short three-repository map consistent |

Plugin and tools version numbers are independent. A plugin release names exactly
which tools version it bundles in `vendor/RELEASE.json`. Data updates need no
plugin release; users obtain them through the normal refresh behavior.

## Bundle a tools release

Follow the [tools release procedure](https://github.com/cylon58/omarchy-community-knowledge-tools/blob/lean-release/docs/re-release.md)
to test and publish the reviewed wheel and setup script first. Then:

1. Update `WHEEL_NAME` in `bin/companion.py` and `scripts/stage_vendor.py`,
   and the version examples in the README and staging test when the tools version changes.
2. Run the staging command from the plugin README with the full published tools
   commit. It copies the two artifacts and generates their release metadata and checksums together.
3. Run `python3 -m unittest discover -s tests -v`. The bundle test checks actual
   artifact hashes, wheel metadata, and the runtime's selected filename.
4. Run `omarchy plugin validate .` and the README's QML check. For changes to
   installation or panel behavior, also exercise connect, update, refresh, and
   disconnect in an isolated test installation.
5. Review the complete diff, including the tracked files under `vendor/`, and
   publish the plugin update. Do not manually edit hashes.

The installed plugin ID stays `io.github.cylon58.omarchy-knowledge`. Preserve the
existing launcher, environment, cache, and ownership receipt paths. Existing users
continue to update with `omarchy plugin update io.github.cylon58.omarchy-knowledge`
and then choose **Update agent**. Updating the repository does not itself run setup.

For a metadata or documentation correction, leave the bundled executable artifacts
unchanged. A data intake code upgrade is a separate step only when required; it does
not follow automatically from a plugin release.

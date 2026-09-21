import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui

// Popup lifecycle and layout follow Omarchy's clock panel contract (MIT; see README).
Panel {
  id: root
  moduleName: "io.github.cylon58.omarchy-knowledge"
  ipcTarget: "io.github.cylon58.omarchy-knowledge"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root
  readonly property string companionPath: decodeURIComponent(String(Qt.resolvedUrl("bin/companion.py")).replace(/^file:\/\//, ""))
  property bool busy: false
  property string activeAction: ""
  property string outputText: "Open the panel to check setup status."
  property string pendingOutput: ""
  property bool processExited: false
  property bool streamFinished: false
  property int processExitCode: 0

  function open() {
    root.controller.show()
    root.runAction("status")
  }

  function close() { root.controller.hide() }
  function toggle() { root.opened ? root.close() : root.open() }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }

  function runAction(action) {
    if (root.busy) return
    root.busy = true
    root.activeAction = action
    root.pendingOutput = ""
    root.processExited = false
    root.streamFinished = false
    root.processExitCode = 0
    root.outputText = action === "status" ? "Checking local status…" : action.charAt(0).toUpperCase() + action.slice(1) + " in progress…"
    companion.command = ["python3", root.companionPath, action]
    companion.running = true
  }

  function finishAction() {
    if (!root.processExited || !root.streamFinished) return
    root.busy = false
    if (root.pendingOutput !== "") root.outputText = root.summarize(root.pendingOutput)
    else if (root.processExitCode !== 0)
      root.outputText = "The action failed without details. Try Repair or run the wrapper in a terminal."
  }

  function summarize(raw) {
    try {
      var value = JSON.parse(raw)
      if (!value.ok) return value.error || value.action_required || "Action needs attention."
      if (value.action === "status") {
        if (!value.installed) return "Ready to set up for " + (value.agent || "your agent") + "."
        var age = value.cache_age_seconds === null ? "No accepted snapshot yet" : "Cache age: " + Math.floor(value.cache_age_seconds / 3600) + "h"
        return "Companion installed. Current agent: " + value.agent + ". " + age + ". "
          + String(value.count || 0) + " community records. Choose Update / Repair to connect a newly selected supported agent."
      }
      return value.message || "Action complete."
    } catch (error) {
      return "The companion returned unreadable output. Try Repair."
    }
  }

  Process {
    id: companion
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.pendingOutput = String(text || "")
        root.streamFinished = true
        root.outputText = root.summarize(root.pendingOutput)
        root.finishAction()
      }
    }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) {
      root.processExited = true
      root.processExitCode = exitCode
      root.finishAction()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(470))
    contentHeight: panel.fittedContentHeight(content.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: content
        width: parent.width
        spacing: Style.space(14)

        PanelHero {
          title: "Community Knowledge"
          meta: root.busy ? root.activeAction + " running" : "local agent companion"
          detail: root.busy ? "BUSY" : "READY"
          foreground: root.bar ? root.bar.foreground : Color.foreground
          iconComponent: Component {
            Text {
              textFormat: Text.PlainText
              text: "󰋗"
              color: root.bar ? root.bar.foreground : Color.foreground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.display
            }
          }
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          text: root.outputText
          color: root.bar ? root.bar.foreground : Color.foreground
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.body
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          text: "Setup connects your agent to shared hardware and system fixes and creates a local plugin search index. Plugin searches check the marketplace for updates; offline use keeps the last good list. Refresh updates both community knowledge and plugins. Sharing anything publicly always requires a separate preview and your approval."
          color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.35)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Row {
          spacing: Style.space(8)
          Button { text: "Setup"; bordered: true; enabled: !root.busy; onClicked: root.runAction("setup") }
          Button { text: "Refresh"; bordered: true; enabled: !root.busy; onClicked: root.runAction("refresh") }
          Button { text: "Update / Repair"; bordered: true; enabled: !root.busy; onClicked: root.runAction("repair") }
          Button { text: "Remove"; bordered: true; enabled: !root.busy; onClicked: root.runAction("remove") }
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          text: "Remove the companion here before removing the plugin. Accepted cache and local drafts are kept."
          color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.35)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.caption
        }
      }
    }
  }
}

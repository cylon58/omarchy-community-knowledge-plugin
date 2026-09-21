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
  property bool isInstalled: false
  property bool statusKnown: false
  property bool actionFailed: false
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
    root.actionFailed = false
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
      root.outputText = "The action failed without details. Try Update agent."
  }

  function summarize(raw) {
    try {
      var value = JSON.parse(raw)
      root.actionFailed = !value.ok
      if (value.action === "status") {
        root.isInstalled = Boolean(value.installed)
        root.statusKnown = true
      }
      if (!value.ok) return value.display_message || (value.action === "status"
        ? "Could not confirm the agent connection. Use Update agent to repair it, or check your selected agent in Omarchy settings."
        : "The action could not finish. Try again or use Update agent to repair the connection.")
      if (value.action === "status") {
        if (!value.installed) return "Your agent is not connected yet. Choose Connect my agent to get started."
        var age = value.cache_age_seconds === null ? "No shared data downloaded yet."
          : "Shared data checked " + Math.floor(value.cache_age_seconds / 3600) + "h ago."
        return "Connected for " + value.agent + ". " + String(value.count || 0)
          + " community records. " + age
      }
      if (value.action === "setup" || value.action === "repair") root.isInstalled = true
      if (value.action === "remove") root.isInstalled = false

      return String(value.display_message || value.message || "Action complete.").slice(0, 480)
    } catch (error) {
      return "The companion returned unreadable output. Try Update agent."
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
          meta: root.busy ? "working…" : "fixes, workarounds and plugins"
          detail: root.busy ? "BUSY" : (root.actionFailed ? "CHECK" : (root.isInstalled ? "CONNECTED" : "SETUP"))
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
          text: "Help your agent find shared Omarchy hardware and system fixes, workarounds, and existing plugins."
          color: root.bar ? root.bar.foreground : Color.foreground
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.body
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          text: "Connect my agent installs two agent skills and downloads searchable community data. Sharing your experience always requires your approval."
          color: root.bar ? root.bar.foreground : Color.foreground
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          maximumLineCount: 6
          elide: Text.ElideRight
          textFormat: Text.PlainText
          text: root.outputText
          color: root.bar ? root.bar.foreground : Color.foreground
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.body
        }

        Flow {
          width: parent.width
          spacing: Style.space(8)
          Button { text: "Connect my agent"; visible: root.statusKnown && !root.isInstalled; bordered: true; enabled: !root.busy; onClicked: root.runAction("setup") }
          Button { text: "Refresh data"; bordered: true; enabled: !root.busy && root.isInstalled; onClicked: root.runAction("refresh") }
          Button { text: "Update agent"; bordered: true; enabled: !root.busy && root.isInstalled; onClicked: root.runAction("repair") }
          Button { text: "Disconnect"; bordered: true; enabled: !root.busy && root.isInstalled; onClicked: root.runAction("remove") }
        }

        Text {
          width: parent.width
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          text: "Refresh data updates fixes and the plugin list. Update agent installs newer skills or repairs setup. Disconnect keeps saved data and drafts."
          color: Qt.darker(root.bar ? root.bar.foreground : Color.foreground, 1.35)
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.caption
        }
      }
    }
  }
}

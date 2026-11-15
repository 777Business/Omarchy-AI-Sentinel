import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "omarchy-ai-sentinel"

  property var aiData: {
    "status": "idle",
    "badge_text": "AI",
    "server_count": 0,
    "total_ai_vram_gb": "0 MB",
    "gpu_used_gb": "0 GB",
    "gpu_total_gb": "12.0 GB",
    "gpu_used_pct": 0,
    "gpu_compute_pct": 0,
    "is_warning": false,
    "servers": []
  }

  readonly property string scriptPath: Qt.resolvedUrl("scripts/ai-sampler.py").toString().replace("file://", "")
  readonly property string ctlPath: Qt.resolvedUrl("scripts/ai-ctl.py").toString().replace("file://", "")

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function open() {
    if (panelLoader.item) {
      panelLoader.item.open()
      panelLoader.item.refresh()
    }
  }

  function close() {
    if (panelLoader.item) panelLoader.item.close()
  }

  function toggle() {
    if (panelLoader.item) {
      if (panelLoader.item.opened) {
        panelLoader.item.close()
      } else {
        panelLoader.item.open()
        panelLoader.item.refresh()
      }
    }
  }

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  function injectPanel() {
    if (!panelLoader.item) return
    panelLoader.item.bar = root.bar
    panelLoader.item.anchorItem = barPill
    panelLoader.item.hostWidget = root
    panelLoader.item.parentWidget = root
  }

  function refresh() {
    if (!samplerProcess.running) {
      samplerProcess.running = true
    }
  }

  onBarChanged: injectPanel()

  implicitWidth: barPill.implicitWidth
  implicitHeight: barPill.implicitHeight

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  Process {
    id: samplerProcess
    command: [root.scriptPath]
    stdout: StdioCollector {
      id: samplerOut
      waitForEnd: true
      onStreamFinished: {
        try {
          var res = JSON.parse(samplerOut.text)
          root.aiData = res
          if (panelLoader.item) {
            panelLoader.item.aiData = res
          }
        } catch (e) {}
      }
    }
  }

  Timer {
    id: pollTimer
    interval: root.opened ? 1500 : 3500
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Component.onCompleted: root.refresh()

  // Clickable Bar Button
  Rectangle {
    id: barPill
    implicitWidth: contentRow.implicitWidth + Style.space(16)
    implicitHeight: root.bar ? Math.min(root.bar.height - Style.space(8), Style.space(30)) : Style.space(30)
    anchors.verticalCenter: parent.verticalCenter
    radius: Style.rounding(8)
    color: {
      if (root.aiData.is_warning) return Color.alpha(Color.red, 0.25)
      if (root.aiData.server_count > 0) return Color.alpha(Color.accent, 0.20)
      return mouseArea.containsMouse ? Color.alpha(Color.foreground, 0.10) : Color.alpha(Color.foreground, 0.04)
    }
    border.width: 1
    border.color: {
      if (root.aiData.is_warning) return Color.red
      if (root.aiData.server_count > 0) return Color.accent
      return Color.alpha(Color.foreground, 0.12)
    }

    Behavior on color { ColorAnimation { duration: Style.duration(150) } }
    Behavior on border.color { ColorAnimation { duration: Style.duration(150) } }

    Row {
      id: contentRow
      anchors.centerIn: parent
      spacing: Style.space(6)

      // Status Indicator Dot or Brain Glyph
      Text {
        text: root.aiData.server_count > 0 ? "●" : "🧠"
        color: {
          if (root.aiData.is_warning) return Color.red
          if (root.aiData.server_count > 0) return Color.accent
          return Color.muted
        }
        font.pixelSize: Style.font.caption
        anchors.verticalCenter: parent.verticalCenter
      }

      // Live Text: e.g. "AI (1) • 5.8 GB" or "AI"
      Text {
        textFormat: Text.PlainText
        text: root.aiData.badge_text
        color: root.aiData.server_count > 0 ? Color.foreground : Color.muted
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        font.bold: root.aiData.server_count > 0
        anchors.verticalCenter: parent.verticalCenter
      }
    }

    MouseArea {
      id: mouseArea
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: root.toggle()
    }
  }
}

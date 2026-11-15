import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "omarchy-ai-sentinel"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  property var parentWidget: null

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
    "presets": [
      { "id": "ollama", "name": "Ollama", "cmd": "ollama serve" },
      { "id": "strata", "name": "Strata", "cmd": "strata launch" },
      { "id": "llama-router", "name": "Router", "cmd": "llama-router" }
    ],
    "servers": []
  }

  readonly property string ctlPath: Qt.resolvedUrl("scripts/ai-ctl.py").toString().replace("file://", "")

  function open() {
    root.controller.show()
    root.refresh()
  }

  function close() {
    root.controller.hide()
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.hostWidget || root, direction)
    return false
  }

  function refresh() {
    if (root.parentWidget && typeof root.parentWidget.refresh === "function") {
      root.parentWidget.refresh()
    }
  }

  function stopServer(pid) {
    Quickshell.execDetached([root.ctlPath, "stop", String(pid)])
    refreshTimer.restart()
  }

  function stopAll() {
    Quickshell.execDetached([root.ctlPath, "stop-all"])
    refreshTimer.restart()
  }

  function startEngine(engine) {
    Quickshell.execDetached([root.ctlPath, "start", engine])
    refreshTimer.restart()
  }

  function addPreset(id, name, pattern, cmd) {
    Quickshell.execDetached([root.ctlPath, "add-preset", id, name, pattern, cmd])
    refreshTimer.restart()
  }

  function removePreset(id) {
    Quickshell.execDetached([root.ctlPath, "remove-preset", id])
    refreshTimer.restart()
  }

  Timer {
    id: refreshTimer
    interval: 800
    repeat: false
    onTriggered: root.refresh()
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(420))
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, Style.space(600))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(dir) { root.switchPanel(dir) }

      Column {
        id: mainColumn
        width: parent.width
        spacing: Style.space(12)
        topPadding: Style.space(8)
        bottomPadding: Style.space(8)

        // ----------------- Header -----------------
        Row {
          width: parent.width
          spacing: Style.space(8)

          Text {
            text: "🧠 AI Sentinel"
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.subtitle
            font.bold: true
            anchors.verticalCenter: parent.verticalCenter
          }

          Item {
            Layout.fillWidth: true
            width: Math.max(0, mainColumn.width - (parent.children[0].implicitWidth + headerActions.implicitWidth + Style.space(24)))
            height: 1
          }

          Row {
            id: headerActions
            spacing: Style.space(6)
            anchors.verticalCenter: parent.verticalCenter

            PanelActionButton {
              iconText: "↻"
              tooltipText: "Refresh GPU and Server Status"
              onClicked: root.refresh()
            }
          }
        }

        // ----------------- GPU & VRAM Hero Card -----------------
        Rectangle {
          width: parent.width
          implicitHeight: heroCol.implicitHeight + Style.space(20)
          radius: Style.rounding(10)
          color: Util.alpha(Color.foreground, 0.06)
          border.width: 1
          border.color: root.aiData.is_warning ? "#ef4444" : Util.alpha(Color.foreground, 0.16)

          Column {
            id: heroCol
            anchors.fill: parent
            anchors.margins: Style.space(12)
            spacing: Style.space(10)

            Row {
              width: parent.width
              Text {
                text: "GPU VRAM USAGE"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                font.bold: true
                color: Util.alpha(Color.foreground, 0.70)
              }
              Item {
                width: Math.max(0, parent.width - (parent.children[0].implicitWidth + parent.children[2].implicitWidth))
                height: 1
              }
              Text {
                text: root.aiData.gpu_used_gb + " / " + root.aiData.gpu_total_gb + " (" + root.aiData.gpu_used_pct + "%)"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                font.bold: true
                color: root.aiData.is_warning ? "#f87171" : Color.accent
              }
            }

            // VRAM Progress Bar
            Rectangle {
              width: parent.width
              height: Style.space(8)
              radius: Style.rounding(4)
              color: Util.alpha(Color.foreground, 0.12)

              Rectangle {
                width: Math.min(parent.width, Math.max(4, parent.width * (root.aiData.gpu_used_pct / 100.0)))
                height: parent.height
                radius: parent.radius
                color: root.aiData.is_warning ? "#ef4444" : (root.aiData.server_count > 0 ? Color.accent : Util.alpha(Color.foreground, 0.40))
                Behavior on width { NumberAnimation { duration: Style.duration(200) } }
              }
            }

            Row {
              width: parent.width
              Text {
                text: "GPU Compute Activity: " + root.aiData.gpu_compute_pct + "%"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                color: Util.alpha(Color.foreground, 0.70)
              }
            }

            // Emergency Free All VRAM button
            Rectangle {
              width: parent.width
              height: Style.space(34)
              radius: Style.rounding(6)
              color: freeArea.containsMouse ? "#dc2626" : Util.alpha("#ef4444", 0.16)
              border.width: 1
              border.color: "#ef4444"

              Row {
                anchors.centerIn: parent
                spacing: Style.space(6)
                Text {
                  text: "⏹"
                  font.pixelSize: Style.font.caption
                  color: freeArea.containsMouse ? "#ffffff" : "#f87171"
                  anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                  text: "Release All VRAM & Stop AI Servers"
                  font.family: Style.font.family
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  color: freeArea.containsMouse ? "#ffffff" : "#f87171"
                  anchors.verticalCenter: parent.verticalCenter
                }
              }

              MouseArea {
                id: freeArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.stopAll()
              }
            }
          }
        }

        // ----------------- Active Servers Section -----------------
        Text {
          text: "ACTIVE AI SERVERS (" + root.aiData.server_count + ")"
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          font.bold: true
          color: Util.alpha(Color.foreground, 0.65)
        }

        // Empty state
        Rectangle {
          visible: root.aiData.server_count === 0
          width: parent.width
          height: Style.space(64)
          radius: Style.rounding(8)
          color: Util.alpha(Color.foreground, 0.04)
          border.width: 1
          border.color: Util.alpha(Color.foreground, 0.10)

          Column {
            anchors.centerIn: parent
            spacing: Style.space(3)
            Text {
              text: "No AI servers running"
              font.family: Style.font.family
              font.pixelSize: Style.font.body
              font.bold: true
              color: Color.foreground
              anchors.horizontalCenter: parent.horizontalCenter
            }
            Text {
              text: "VRAM is completely clear for games & apps"
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              color: Util.alpha(Color.foreground, 0.65)
              anchors.horizontalCenter: parent.horizontalCenter
            }
          }
        }

        // Active Servers List
        Repeater {
          model: root.aiData.servers
          delegate: Rectangle {
            width: mainColumn.width
            implicitHeight: sCol.implicitHeight + Style.space(20)
            radius: Style.rounding(8)
            color: Util.alpha(Color.accent, 0.10)
            border.width: 1
            border.color: Util.alpha(Color.accent, 0.35)

            Column {
              id: sCol
              anchors.fill: parent
              anchors.margins: Style.space(12)
              spacing: Style.space(8)

              // Header Row with STOP and optional PIN buttons
              Item {
                width: parent.width
                height: Style.space(26)

                Row {
                  anchors.left: parent.left
                  anchors.right: actionsRow.left
                  anchors.rightMargin: Style.space(8)
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(6)

                  Text {
                    text: "●"
                    color: Color.accent
                    font.pixelSize: Style.font.caption
                    anchors.verticalCenter: parent.verticalCenter
                  }
                  Text {
                    text: modelData.name + " (PID " + modelData.pid + ")"
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                    color: Color.foreground
                    elide: Text.ElideRight
                    anchors.verticalCenter: parent.verticalCenter
                  }
                }

                Row {
                  id: actionsRow
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(6)

                  // Save / Pin button if not already a saved preset
                  Rectangle {
                    visible: !modelData.is_saved
                    width: Style.space(68)
                    height: Style.space(24)
                    radius: Style.rounding(4)
                    color: pinArea.containsMouse ? Util.alpha(Color.accent, 0.35) : Util.alpha(Color.accent, 0.20)
                    border.width: 1
                    border.color: Color.accent

                    Text {
                      anchors.centerIn: parent
                      text: "+ Pin"
                      font.family: Style.font.family
                      font.pixelSize: Style.font.caption
                      font.bold: true
                      color: Color.accent
                    }

                    MouseArea {
                      id: pinArea
                      anchors.fill: parent
                      hoverEnabled: true
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.addPreset(modelData.comm.toLowerCase(), modelData.name, modelData.comm, modelData.cmd)
                    }
                  }

                  // Stop Button
                  Rectangle {
                    id: stopBtn
                    width: Style.space(60)
                    height: Style.space(24)
                    radius: Style.rounding(4)
                    color: stopArea.containsMouse ? "#dc2626" : "#ef4444"

                    Text {
                      anchors.centerIn: parent
                      text: "STOP"
                      font.family: Style.font.family
                      font.pixelSize: Style.font.caption
                      font.bold: true
                      color: "#ffffff"
                    }

                    MouseArea {
                      id: stopArea
                      anchors.fill: parent
                      hoverEnabled: true
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.stopServer(modelData.pid)
                    }
                  }
                }
              }

              // Model info
              Text {
                width: parent.width
                text: "Model: " + modelData.model
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                color: Color.foreground
                elide: Text.ElideRight
              }

              // Details badge row
              Row {
                spacing: Style.space(14)
                Text {
                  text: "VRAM: " + modelData.vram_gb
                  font.family: Style.font.family
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  color: Color.accent
                }
                Text {
                  text: "Port: " + modelData.port
                  font.family: Style.font.family
                  font.pixelSize: Style.font.caption
                  color: Util.alpha(Color.foreground, 0.70)
                }
                Text {
                  text: "CPU: " + modelData.cpu_pct + "%"
                  font.family: Style.font.family
                  font.pixelSize: Style.font.caption
                  color: Util.alpha(Color.foreground, 0.70)
                }
              }
            }
          }
        }

        // ----------------- Quick Start Presets -----------------
        Text {
          text: "QUICK START PRESETS"
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          font.bold: true
          color: Util.alpha(Color.foreground, 0.65)
        }

        Flow {
          width: parent.width
          spacing: Style.space(6)

          Repeater {
            model: root.aiData.presets || []
            delegate: Rectangle {
              width: (mainColumn.width - (Style.space(6) * (Math.min(3, root.aiData.presets.length) - 1))) / Math.min(3, root.aiData.presets.length)
              height: Style.space(34)
              radius: Style.rounding(6)
              color: pArea.containsMouse ? Util.alpha(Color.foreground, 0.16) : Util.alpha(Color.foreground, 0.08)
              border.width: 1
              border.color: Util.alpha(Color.foreground, 0.20)

              Row {
                anchors.centerIn: parent
                spacing: Style.space(4)
                Text {
                  text: "▶"
                  font.pixelSize: Style.font.caption
                  color: Color.accent
                  anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                  text: modelData.name
                  font.family: Style.font.family
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  color: Color.foreground
                  elide: Text.ElideRight
                  anchors.verticalCenter: parent.verticalCenter
                }
              }

              MouseArea {
                id: pArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.startEngine(modelData.id)
              }
            }
          }
        }
      }
    }
  }
}

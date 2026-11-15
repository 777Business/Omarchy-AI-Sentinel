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
        topPadding: Style.space(6)
        bottomPadding: Style.space(6)

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
          color: Util.alpha(Color.foreground, 0.05)
          border.width: 1
          border.color: root.aiData.is_warning ? Color.red : Util.alpha(Color.foreground, 0.12)

          Column {
            id: heroCol
            anchors.fill: parent
            anchors.margins: Style.space(10)
            spacing: Style.space(8)

            Row {
              width: parent.width
              Text {
                text: "GPU VRAM USAGE"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                font.bold: true
                color: Color.muted
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
                color: root.aiData.is_warning ? Color.red : Color.accent
              }
            }

            // VRAM Progress Bar
            Rectangle {
              width: parent.width
              height: Style.space(8)
              radius: Style.rounding(4)
              color: Util.alpha(Color.foreground, 0.10)

              Rectangle {
                width: Math.min(parent.width, Math.max(4, parent.width * (root.aiData.gpu_used_pct / 100.0)))
                height: parent.height
                radius: parent.radius
                color: root.aiData.is_warning ? Color.red : (root.aiData.server_count > 0 ? Color.accent : Color.muted)
                Behavior on width { NumberAnimation { duration: Style.duration(200) } }
              }
            }

            Row {
              width: parent.width
              Text {
                text: "GPU Compute Activity: " + root.aiData.gpu_compute_pct + "%"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                color: Color.muted
              }
            }

            // Emergency Free All VRAM button (only active if servers or VRAM used > 1.2 GB)
            Rectangle {
              width: parent.width
              height: Style.space(32)
              radius: Style.rounding(6)
              color: freeArea.containsMouse ? Util.alpha(Color.red, 0.3) : Util.alpha(Color.red, 0.15)
              border.width: 1
              border.color: Color.red

              Row {
                anchors.centerIn: parent
                spacing: Style.space(6)
                Text {
                  text: "⏹"
                  font.pixelSize: Style.font.caption
                  color: Color.red
                  anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                  text: "Release All VRAM & Stop AI Servers"
                  font.family: Style.font.family
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  color: Color.red
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
          color: Color.muted
        }

        // Empty state
        Rectangle {
          visible: root.aiData.server_count === 0
          width: parent.width
          height: Style.space(60)
          radius: Style.rounding(8)
          color: Util.alpha(Color.foreground, 0.03)
          border.width: 1
          border.color: Util.alpha(Color.foreground, 0.08)

          Column {
            anchors.centerIn: parent
            spacing: Style.space(2)
            Text {
              text: "No AI servers running"
              font.family: Style.font.family
              font.pixelSize: Style.font.body
              color: Color.foreground
              anchors.horizontalCenter: parent.horizontalCenter
            }
            Text {
              text: "VRAM is completely clear for games & apps"
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              color: Color.muted
              anchors.horizontalCenter: parent.horizontalCenter
            }
          }
        }

        // Active Servers List
        Repeater {
          model: root.aiData.servers
          delegate: Rectangle {
            width: mainColumn.width
            implicitHeight: sCol.implicitHeight + Style.space(16)
            radius: Style.rounding(8)
            color: Util.alpha(Color.accent, 0.08)
            border.width: 1
            border.color: Util.alpha(Color.accent, 0.3)

            Column {
              id: sCol
              anchors.fill: parent
              anchors.margins: Style.space(10)
              spacing: Style.space(6)

              Row {
                width: parent.width
                spacing: Style.space(6)

                Text {
                  text: "🟢"
                  font.pixelSize: Style.font.caption
                  anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                  text: modelData.name + " (PID " + modelData.pid + ")"
                  font.family: Style.font.family
                  font.pixelSize: Style.font.body
                  font.bold: true
                  color: Color.foreground
                  anchors.verticalCenter: parent.verticalCenter
                }
                Item {
                  Layout.fillWidth: true
                  width: Math.max(0, sCol.width - (parent.children[0].implicitWidth + parent.children[1].implicitWidth + stopBtn.implicitWidth + Style.space(30)))
                  height: 1
                }
                // Stop Button
                Rectangle {
                  id: stopBtn
                  width: Style.space(70)
                  height: Style.space(26)
                  radius: Style.rounding(4)
                  color: stopArea.containsMouse ? Color.red : Util.alpha(Color.red, 0.8)

                  Text {
                    anchors.centerIn: parent
                    text: "STOP"
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    color: "white"
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
                spacing: Style.space(12)
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
                  color: Color.muted
                }
                Text {
                  text: "CPU: " + modelData.cpu_pct + "%"
                  font.family: Style.font.family
                  font.pixelSize: Style.font.caption
                  color: Color.muted
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
          color: Color.muted
        }

        Row {
          width: parent.width
          spacing: Style.space(6)

          Rectangle {
            width: (parent.width - Style.space(12)) / 3
            height: Style.space(32)
            radius: Style.rounding(6)
            color: oArea.containsMouse ? Util.alpha(Color.foreground, 0.12) : Util.alpha(Color.foreground, 0.06)
            border.width: 1
            border.color: Util.alpha(Color.foreground, 0.15)

            Text {
              anchors.centerIn: parent
              text: "▶ Ollama"
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              color: Color.foreground
            }
            MouseArea {
              id: oArea
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.startEngine("ollama")
            }
          }

          Rectangle {
            width: (parent.width - Style.space(12)) / 3
            height: Style.space(32)
            radius: Style.rounding(6)
            color: sArea.containsMouse ? Util.alpha(Color.foreground, 0.12) : Util.alpha(Color.foreground, 0.06)
            border.width: 1
            border.color: Util.alpha(Color.foreground, 0.15)

            Text {
              anchors.centerIn: parent
              text: "▶ Strata"
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              color: Color.foreground
            }
            MouseArea {
              id: sArea
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.startEngine("strata")
            }
          }

          Rectangle {
            width: (parent.width - Style.space(12)) / 3
            height: Style.space(32)
            radius: Style.rounding(6)
            color: rArea.containsMouse ? Util.alpha(Color.foreground, 0.12) : Util.alpha(Color.foreground, 0.06)
            border.width: 1
            border.color: Util.alpha(Color.foreground, 0.15)

            Text {
              anchors.centerIn: parent
              text: "▶ Router"
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              color: Color.foreground
            }
            MouseArea {
              id: rArea
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.startEngine("llama-router")
            }
          }
        }
      }
    }
  }
}

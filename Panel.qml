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
  readonly property var barIdentity: hostWidget || root

  property var aiData: {
    "status": "idle",
    "badge_text": "AI",
    "server_count": 0,
    "total_ai_vram_gb": "0 MB",
    "system_vram_gb": "0 GB",
    "gpu_used_gb": "0 GB",
    "gpu_free_gb": "12.0 GB",
    "gpu_total_gb": "12.0 GB",
    "gpu_used_pct": 0,
    "ai_vram_pct": 0,
    "system_vram_pct": 0,
    "free_vram_pct": 100,
    "gpu_compute_pct": 0,
    "is_warning": false,
    "fit_recommendation": "Checking VRAM...",
    "presets": [],
    "servers": []
  }

  property bool isSamplerRefreshing: false
  property var pendingStops: ({})
  property bool releasingAll: false
  property string launchingPresetId: ""
  property string toastMessage: ""
  property bool showAddPresetForm: false

  readonly property string ctlPath: Qt.resolvedUrl("scripts/ai-ctl.py").toString().replace(/^(qs|file):\/\//, "")

  function getRounding(r) {
    return Style.cornerRadius > 0 ? Math.min(Style.cornerRadius, Style.space(r)) : Style.space(r)
  }

  function showToast(msg) {
    root.toastMessage = msg
    toastTimer.restart()
  }

  Timer {
    id: toastTimer
    interval: 2600
    repeat: false
    onTriggered: root.toastMessage = ""
  }

  function open() {
    root.controller.show()
    root.refresh()
  }

  function close() {
    root.controller.hide()
  }

  function toggle() {
    if (root.opened) {
      root.close()
    } else {
      root.open()
    }
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

  function triggerBurstRefresh() {
    root.refresh()
    burstTimer1.restart()
    burstTimer2.restart()
    burstTimer3.restart()
    burstTimer4.restart()
  }

  Timer {
    id: burstTimer1
    interval: 180
    repeat: false
    onTriggered: root.refresh()
  }

  Timer {
    id: burstTimer2
    interval: 500
    repeat: false
    onTriggered: root.refresh()
  }

  Timer {
    id: burstTimer3
    interval: 1100
    repeat: false
    onTriggered: {
      root.refresh()
      root.releasingAll = false
      root.launchingPresetId = ""
    }
  }

  Timer {
    id: burstTimer4
    interval: 2200
    repeat: false
    onTriggered: {
      root.refresh()
      root.pendingStops = ({})
    }
  }

  function isPendingStop(targetId) {
    return root.releasingAll || (root.pendingStops && root.pendingStops[String(targetId)] === true)
  }

  function stopServer(targetId) {
    var p = Object.assign({}, root.pendingStops)
    p[String(targetId)] = true
    root.pendingStops = p

    Quickshell.execDetached(["python3", root.ctlPath, "stop", String(targetId)])
    root.showToast("Stopping " + targetId + "...")
    root.triggerBurstRefresh()
  }

  function stopAll() {
    root.releasingAll = true
    Quickshell.execDetached(["python3", root.ctlPath, "stop-all"])
    root.showToast("Liberating GPU VRAM...")
    root.triggerBurstRefresh()
  }

  function startEngine(engine) {
    root.launchingPresetId = engine
    Quickshell.execDetached(["python3", root.ctlPath, "start", engine])
    root.showToast("Starting " + engine + "...")
    root.triggerBurstRefresh()
  }

  function addPreset(id, name, pattern, cmd) {
    Quickshell.execDetached(["python3", root.ctlPath, "add-preset", id, name, pattern, cmd])
    root.showToast("Added preset: " + name)
    root.showAddPresetForm = false
    root.triggerBurstRefresh()
  }

  function removePreset(id) {
    Quickshell.execDetached(["python3", root.ctlPath, "remove-preset", id])
    root.showToast("Removed preset: " + id)
    root.triggerBurstRefresh()
  }

  function copyToClipboard(url) {
    Quickshell.execDetached(["python3", root.ctlPath, "copy", url])
    root.showToast("Copied: " + url)
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(430))
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight + Style.space(16), Style.space(640))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(dir) { root.switchPanel(dir) }

      Flickable {
        id: scrollArea
        anchors.fill: parent
        contentWidth: width
        contentHeight: mainColumn.implicitHeight + Style.space(16)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        WheelHandler {
          target: null
          acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
          onWheel: function(event) {
            var dy = event.pixelDelta.y !== 0 ? event.pixelDelta.y : (event.angleDelta.y / 120) * Style.space(60)
            scrollArea.contentY = Math.max(0, Math.min(scrollArea.contentHeight - scrollArea.height, scrollArea.contentY - dy))
          }
        }

        Column {
          id: mainColumn
          width: scrollArea.width
          spacing: Style.space(12)
          topPadding: Style.space(8)
          bottomPadding: Style.space(8)

          // ----------------- Header -----------------
          Item {
            width: parent.width
            height: Style.space(26)

            Text {
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              text: "🧠 AI Sentinel"
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.subtitle
              font.bold: true
            }

            Row {
              id: headerActions
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(6)

              // Spinning 360 refresh button
              PanelActionButton {
                id: refreshBtn
                iconText: "↻"
                tooltipText: "Refresh GPU & AI Status"
                onClicked: {
                  spinAnim.restart()
                  root.triggerBurstRefresh()
                }

                RotationAnimation on rotation {
                  id: spinAnim
                  from: 0
                  to: 360
                  duration: Style.duration(400)
                  running: root.isSamplerRefreshing
                }
              }
            }
          }

          // ----------------- Optional Toast Banner -----------------
          Rectangle {
            visible: root.toastMessage.length > 0
            width: parent.width
            height: Style.space(26)
            radius: root.getRounding(5)
            color: Util.alpha(Color.accent, 0.20)
            border.width: 1
            border.color: Color.accent

            Text {
              anchors.centerIn: parent
              text: root.toastMessage
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              color: Color.accent
            }
          }

          // ----------------- GPU & VRAM Hero Card -----------------
          Rectangle {
            width: parent.width
            implicitHeight: heroCol.implicitHeight + Style.space(20)
            radius: root.getRounding(10)
            color: Util.alpha(Color.foreground, 0.06)
            border.width: 1
            border.color: root.aiData.is_warning ? "#ef4444" : Util.alpha(Color.foreground, 0.16)

            Column {
              id: heroCol
              anchors.fill: parent
              anchors.margins: Style.space(12)
              spacing: Style.space(10)

              // Usage & Total Row
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

              // 3-Tier Segmented VRAM Bar: [ System VRAM | AI VRAM | Free Track ]
              Rectangle {
                id: vramBarTrack
                width: parent.width
                height: Style.space(10)
                radius: root.getRounding(5)
                color: Util.alpha(Color.foreground, 0.10)
                clip: true

                Row {
                  anchors.fill: parent

                  // System / Desktop segment
                  Rectangle {
                    width: Math.max(0, (vramBarTrack.width * (root.aiData.system_vram_pct / 100.0)))
                    height: parent.height
                    color: Util.alpha(Color.foreground, 0.35)
                    Behavior on width { NumberAnimation { duration: Style.duration(180) } }
                  }

                  // AI Models segment
                  Rectangle {
                    width: Math.max(0, (vramBarTrack.width * (root.aiData.ai_vram_pct / 100.0)))
                    height: parent.height
                    color: root.aiData.is_warning ? "#ef4444" : Color.accent
                    Behavior on width { NumberAnimation { duration: Style.duration(180) } }
                  }
                }
              }

              // Legend and Headroom Info
              Row {
                width: parent.width
                spacing: Style.space(10)

                Row {
                  spacing: Style.space(4)
                  Rectangle {
                    width: Style.space(7)
                    height: Style.space(7)
                    radius: Style.space(3)
                    color: Color.accent
                    anchors.verticalCenter: parent.verticalCenter
                  }
                  Text {
                    text: "AI: " + (root.aiData.total_ai_vram_gb || "0 MB")
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    color: Color.foreground
                  }
                }

                Row {
                  spacing: Style.space(4)
                  Rectangle {
                    width: Style.space(7)
                    height: Style.space(7)
                    radius: Style.space(3)
                    color: Util.alpha(Color.foreground, 0.40)
                    anchors.verticalCenter: parent.verticalCenter
                  }
                  Text {
                    text: "System: " + (root.aiData.system_vram_gb || "0 GB")
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    color: Util.alpha(Color.foreground, 0.70)
                  }
                }

                Row {
                  spacing: Style.space(4)
                  Rectangle {
                    width: Style.space(7)
                    height: Style.space(7)
                    radius: Style.space(3)
                    color: "#10b981"
                    anchors.verticalCenter: parent.verticalCenter
                  }
                  Text {
                    text: "Free: " + (root.aiData.gpu_free_gb || "0 GB")
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    color: "#10b981"
                  }
                }
              }

              // Model Fit Advisor Pill
              Rectangle {
                width: parent.width
                height: Style.space(24)
                radius: root.getRounding(5)
                color: Util.alpha(Color.foreground, 0.05)
                border.width: 1
                border.color: Util.alpha(Color.foreground, 0.12)

                Row {
                  anchors.centerIn: parent
                  spacing: Style.space(6)
                  Text {
                    text: root.aiData.fit_recommendation || "Computing headroom..."
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    color: root.aiData.is_warning ? "#f87171" : Color.foreground
                  }
                }
              }

              // Emergency Free All VRAM button
              Rectangle {
                id: panicBtn
                width: parent.width
                height: Style.space(34)
                radius: root.getRounding(6)
                color: root.releasingAll ? "#991b1b" : (freeArea.containsMouse ? "#dc2626" : Util.alpha("#ef4444", 0.16))
                border.width: 1
                border.color: "#ef4444"

                Row {
                  anchors.centerIn: parent
                  spacing: Style.space(6)
                  Text {
                    text: root.releasingAll ? "⏳" : "⏹"
                    font.pixelSize: Style.font.caption
                    color: (freeArea.containsMouse || root.releasingAll) ? "#ffffff" : "#f87171"
                    anchors.verticalCenter: parent.verticalCenter
                  }
                  Text {
                    text: root.releasingAll ? "Liberating VRAM & Stopping All AI..." : "Release All VRAM & Stop AI Servers"
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    color: (freeArea.containsMouse || root.releasingAll) ? "#ffffff" : "#f87171"
                    anchors.verticalCenter: parent.verticalCenter
                  }
                }

                MouseArea {
                  id: freeArea
                  anchors.fill: parent
                  hoverEnabled: !root.releasingAll
                  cursorShape: root.releasingAll ? Qt.ArrowCursor : Qt.PointingHandCursor
                  onClicked: {
                    if (!root.releasingAll) root.stopAll()
                  }
                }
              }
            }
          }

          // ----------------- Active Servers Section -----------------
          Row {
            width: parent.width
            spacing: Style.space(6)

            Text {
              text: "ACTIVE AI SERVERS (" + root.aiData.server_count + ")"
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              color: Util.alpha(Color.foreground, 0.65)
              anchors.verticalCenter: parent.verticalCenter
            }
          }

          // Empty state
          Rectangle {
            visible: root.aiData.server_count === 0
            width: parent.width
            height: Style.space(64)
            radius: root.getRounding(8)
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
              id: serverCard
              readonly property bool isStopping: root.isPendingStop(modelData.target_id || modelData.pid)
              width: mainColumn.width
              implicitHeight: sCol.implicitHeight + Style.space(20)
              radius: root.getRounding(8)
              color: isStopping ? Util.alpha(Color.foreground, 0.05) : Util.alpha(Color.accent, 0.10)
              border.width: 1
              border.color: isStopping ? Util.alpha(Color.foreground, 0.20) : Util.alpha(Color.accent, 0.35)
              opacity: isStopping ? 0.65 : 1.0
              Behavior on opacity { NumberAnimation { duration: Style.duration(150) } }

              Column {
                id: sCol
                anchors.fill: parent
                anchors.margins: Style.space(12)
                spacing: Style.space(8)

                // Header Row with STOP and Action buttons
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
                      color: serverCard.isStopping ? "#f59e0b" : Color.accent
                      font.pixelSize: Style.font.caption
                      anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                      text: modelData.name + (modelData.pid ? " (PID " + modelData.pid + ")" : "")
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

                    // Copy Endpoint button
                    Rectangle {
                      visible: modelData.endpoint_url && modelData.endpoint_url.length > 0
                      width: Style.space(68)
                      height: Style.space(24)
                      radius: root.getRounding(4)
                      color: copyArea.containsMouse ? Util.alpha(Color.foreground, 0.22) : Util.alpha(Color.foreground, 0.12)
                      border.width: 1
                      border.color: Util.alpha(Color.foreground, 0.20)

                      Row {
                        anchors.centerIn: parent
                        spacing: Style.space(3)
                        Text {
                          text: "📋"
                          font.pixelSize: Style.font.caption
                          anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                          text: "URL"
                          font.family: Style.font.family
                          font.pixelSize: Style.font.caption
                          font.bold: true
                          color: Color.foreground
                          anchors.verticalCenter: parent.verticalCenter
                        }
                      }

                      MouseArea {
                        id: copyArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.copyToClipboard(modelData.endpoint_url)
                      }
                    }

                    // Save / Pin button if not already a saved preset
                    Rectangle {
                      visible: !modelData.is_saved
                      width: Style.space(56)
                      height: Style.space(24)
                      radius: root.getRounding(4)
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
                      width: serverCard.isStopping ? Style.space(78) : Style.space(56)
                      height: Style.space(24)
                      radius: root.getRounding(4)
                      color: serverCard.isStopping ? "#b45309" : (stopArea.containsMouse ? "#dc2626" : "#ef4444")

                      Text {
                        anchors.centerIn: parent
                        text: serverCard.isStopping ? "Stopping..." : "STOP"
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                        font.bold: true
                        color: "#ffffff"
                      }

                      MouseArea {
                        id: stopArea
                        anchors.fill: parent
                        hoverEnabled: !serverCard.isStopping
                        cursorShape: serverCard.isStopping ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onClicked: {
                          if (!serverCard.isStopping) {
                            root.stopServer(modelData.target_id || modelData.pid)
                          }
                        }
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
          Item {
            width: parent.width
            height: Style.space(24)

            Text {
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              text: "QUICK START PRESETS"
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
              color: Util.alpha(Color.foreground, 0.65)
            }

            // Inline "+ Add Preset" button
            Rectangle {
              id: addPresetBtn
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              width: addPresetText.implicitWidth + Style.space(16)
              height: Style.space(22)
              radius: root.getRounding(4)
              color: addPresetArea.containsMouse ? Util.alpha(Color.accent, 0.25) : Util.alpha(Color.accent, 0.12)
              border.width: 1
              border.color: Util.alpha(Color.accent, 0.30)

              Text {
                id: addPresetText
                anchors.centerIn: parent
                text: root.showAddPresetForm ? "✕ Cancel" : "+ Add Preset"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                font.bold: true
                color: Color.accent
              }

              MouseArea {
                id: addPresetArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.showAddPresetForm = !root.showAddPresetForm
              }
            }
          }

          // Expandable Add Preset Form
          Rectangle {
            visible: root.showAddPresetForm
            width: parent.width
            implicitHeight: formCol.implicitHeight + Style.space(16)
            radius: root.getRounding(8)
            color: Util.alpha(Color.foreground, 0.07)
            border.width: 1
            border.color: Util.alpha(Color.accent, 0.40)

            Column {
              id: formCol
              anchors.fill: parent
              anchors.margins: Style.space(10)
              spacing: Style.space(8)

              Text {
                text: "Create Custom AI Preset"
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                font.bold: true
                color: Color.foreground
              }

              Row {
                width: parent.width
                spacing: Style.space(8)

                Rectangle {
                  width: (parent.width - Style.space(8)) * 0.45
                  height: Style.space(30)
                  radius: root.getRounding(4)
                  color: Util.alpha(Color.foreground, 0.10)
                  border.width: 1
                  border.color: Util.alpha(Color.foreground, 0.20)

                  TextInput {
                    id: presetNameInput
                    anchors.fill: parent
                    anchors.margins: Style.space(6)
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    color: Color.foreground
                    clip: true
                    Text {
                      text: "Preset Name (e.g. Qwen)"
                      visible: !presetNameInput.text && !presetNameInput.activeFocus
                      color: Util.alpha(Color.foreground, 0.40)
                      font: presetNameInput.font
                    }
                  }
                }

                Rectangle {
                  width: (parent.width - Style.space(8)) * 0.55
                  height: Style.space(30)
                  radius: root.getRounding(4)
                  color: Util.alpha(Color.foreground, 0.10)
                  border.width: 1
                  border.color: Util.alpha(Color.foreground, 0.20)

                  TextInput {
                    id: presetCmdInput
                    anchors.fill: parent
                    anchors.margins: Style.space(6)
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    color: Color.foreground
                    clip: true
                    Text {
                      text: "Command (e.g. ollama run ...)"
                      visible: !presetCmdInput.text && !presetCmdInput.activeFocus
                      color: Util.alpha(Color.foreground, 0.40)
                      font: presetCmdInput.font
                    }
                  }
                }
              }

              Row {
                spacing: Style.space(8)

                Rectangle {
                  width: Style.space(64)
                  height: Style.space(24)
                  radius: root.getRounding(4)
                  color: Color.accent

                  Text {
                    anchors.centerIn: parent
                    text: "Save"
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    color: "#ffffff"
                  }

                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                      var n = presetNameInput.text.trim()
                      var c = presetCmdInput.text.trim()
                      if (n && c) {
                        var id = n.toLowerCase().replace(/[^a-z0-9]/g, "-")
                        root.addPreset(id, n, id, c)
                        presetNameInput.text = ""
                        presetCmdInput.text = ""
                      }
                    }
                  }
                }
              }
            }
          }

          Grid {
            id: presetsGrid
            width: parent.width
            columns: 3
            columnSpacing: Style.space(6)
            rowSpacing: Style.space(6)

            Repeater {
              model: root.aiData.presets || []
              delegate: Rectangle {
                readonly property bool isLaunching: root.launchingPresetId === modelData.id
                readonly property bool isOnline: modelData.is_active === true
                width: Math.floor((mainColumn.width - (Style.space(6) * 2)) / 3)
                height: Style.space(34)
                radius: root.getRounding(6)
                color: isLaunching ? Util.alpha(Color.accent, 0.25) : (pArea.containsMouse ? Util.alpha(Color.foreground, 0.16) : Util.alpha(Color.foreground, 0.08))
                border.width: 1
                border.color: isOnline ? Color.accent : Util.alpha(Color.foreground, 0.20)

                Row {
                  anchors.centerIn: parent
                  spacing: Style.space(4)
                  width: parent.width - Style.space(12)

                  Text {
                    text: isLaunching ? "⏳" : (isOnline ? "●" : "▶")
                    font.pixelSize: Style.font.caption
                    color: isOnline ? "#10b981" : Color.accent
                    anchors.verticalCenter: parent.verticalCenter
                  }
                  Text {
                    text: isLaunching ? "Starting..." : modelData.name
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                    font.bold: isOnline || isLaunching
                    color: Color.foreground
                    elide: Text.ElideRight
                    width: parent.width - Style.space(14)
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

                // Delete button for custom pinned presets
                Rectangle {
                  visible: modelData.is_custom === true
                  z: 2
                  width: Style.space(14)
                  height: Style.space(14)
                  radius: root.getRounding(3)
                  color: delArea.containsMouse ? "#ef4444" : Util.alpha(Color.foreground, 0.25)
                  anchors.top: parent.top
                  anchors.right: parent.right
                  anchors.topMargin: Style.space(2)
                  anchors.rightMargin: Style.space(2)

                  Text {
                    anchors.centerIn: parent
                    text: "×"
                    font.pixelSize: Style.font.caption
                    font.bold: true
                    color: "#ffffff"
                  }

                  MouseArea {
                    id: delArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.removePreset(modelData.id)
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}

import QtQuick
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

  readonly property string scriptPath: Qt.resolvedUrl("scripts/ai-sampler.py").toString().replace(/^(qs|file):\/\//, "")
  readonly property string ctlPath: Qt.resolvedUrl("scripts/ai-ctl.py").toString().replace(/^(qs|file):\/\//, "")

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  property bool refreshQueued: false
  readonly property bool isRefreshing: samplerProcess.running || refreshQueued

  function open() {
    if (panelLoader.item) {
      panelLoader.item.open()
      root.refresh()
    }
  }

  function close() {
    if (panelLoader.item) panelLoader.item.close()
  }

  function toggle() {
    if (panelLoader.item) {
      if (typeof panelLoader.item.toggle === "function") {
        panelLoader.item.toggle()
      } else if (panelLoader.item.opened) {
        panelLoader.item.close()
      } else {
        panelLoader.item.open()
      }
      if (panelLoader.item.opened) {
        root.refresh()
      }
    }
  }

  onOpenedChanged: {
    if (root.opened) {
      root.refresh()
    }
  }

  ShellIpc {
    target: "omarchy-ai-sentinel"

    function refresh(): void { root.refresh() }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
  }

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  function injectPanel() {
    if (!panelLoader.item) return
    panelLoader.item.bar = root.bar
    panelLoader.item.anchorItem = button
    panelLoader.item.hostWidget = root
    panelLoader.item.parentWidget = root
    panelLoader.item.aiData = root.aiData
    panelLoader.item.isSamplerRefreshing = root.isRefreshing
  }

  function refresh() {
    if (samplerProcess.running) {
      root.refreshQueued = true
    } else {
      samplerProcess.running = true
    }
  }

  onBarChanged: injectPanel()
  onAiDataChanged: {
    if (panelLoader.item) {
      panelLoader.item.aiData = root.aiData
    }
  }
  onIsRefreshingChanged: {
    if (panelLoader.item) {
      panelLoader.item.isSamplerRefreshing = root.isRefreshing
    }
  }

  function getRounding(r) {
    return Style.cornerRadius > 0 ? Math.min(Style.cornerRadius, Style.space(r)) : Style.space(r)
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

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
    command: ["python3", root.scriptPath]
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
        } catch (e) {
          if (samplerOut.text && samplerOut.text.trim().length > 0) {
            console.warn("[AI Sentinel] sampler JSON parse error:", e, "raw text:", samplerOut.text)
          }
        }

        if (root.refreshQueued) {
          root.refreshQueued = false
          Qt.callLater(function() {
            if (!samplerProcess.running) {
              samplerProcess.running = true
            }
          })
        }
      }
    }
    stderr: StdioCollector {
      id: samplerErr
      waitForEnd: true
      onStreamFinished: {
        if (samplerErr.text && samplerErr.text.trim().length > 0) {
          console.warn("[AI Sentinel] sampler stderr:", samplerErr.text.trim())
        }
      }
    }
  }

  Timer {
    id: pollTimer
    interval: root.opened ? 1200 : 3000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Component.onCompleted: root.refresh()

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "🧠"
    tooltipText: root.aiData.server_count > 0 ? "AI Sentinel: " + root.aiData.badge_text : "AI Sentinel (Idle)"
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.toggle()
    }

    // Active status dot indicator
    Rectangle {
      visible: root.aiData.server_count > 0
      width: Style.space(8)
      height: Style.space(8)
      radius: root.getRounding(4)
      color: root.aiData.is_warning ? Color.red : Color.accent
      anchors.top: parent.top
      anchors.right: parent.right
      anchors.topMargin: Style.space(4)
      anchors.rightMargin: Style.space(4)
    }
  }
}

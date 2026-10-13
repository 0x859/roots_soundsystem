// Nakładka nad kartami: HUD gestu MIDI (po ruchu elementem kontrolera, na `Theme.hudMs`) i ściąga
// warstwy SHIFT (SOLO trzymane). Żyje w Main.qml poza Repeaterem kart, więc przebudowa kart po zmianie
// profilu jej nie kasuje. Nie przechwytuje myszy (enabled: false, bez MouseArea); w edycji układu ukryta.
import QtQuick

Item {
    id: root
    enabled: false
    clip: true
    property bool editing: false

    readonly property real s: Theme.scale
    // stan HUD: cel i warstwa ostatniego gestu (z `Midi.lastTarget` w chwili komunikatu)
    property string target: ""
    property var info: ({})
    property bool shiftLayer: false
    property bool hudShown: false
    readonly property bool sheetShown: Theme.shiftSheet && Midi.hwShift && !editing && Midi.sheet.length > 0
    readonly property string hint: hud.hint  // podgląd dla testów: „▲ PODNIEŚ do …”
    readonly property string title: hud.title

    function gesture() {
        if (!Theme.hudMidi || root.editing || Midi.lastTarget === "") return
        root.target = Midi.lastTarget
        root.info = Midi.lastInfo
        root.shiftLayer = Midi.lastShift
        root.hudShown = true
        hideTimer.restart()
    }
    function hide() {
        hideTimer.stop()
        root.hudShown = false
    }

    onEditingChanged: if (editing) hide()
    Connections {
        target: Midi
        function onEventChanged() { root.gesture() }
    }
    Connections {
        target: Theme
        function onChanged() { if (!Theme.hudMidi) root.hide() }
    }
    Timer {
        id: hideTimer
        interval: Theme.hudMs
        onTriggered: root.hudShown = false
    }

    Column {
        id: stack
        readonly property real margin: 16 * root.s
        anchors.horizontalCenter: parent.horizontalCenter
        y: Theme.hudPosition === "top" ? margin
           : Theme.hudPosition === "bottom" ? root.height - height - margin
           : Math.max(margin, (root.height - height) / 2)
        spacing: 12 * root.s

        GestureHud {
            id: hud
            objectName: "gestureHud"
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(root.width - 2 * stack.margin, 640 * root.s)
            target: root.target
            info: root.info
            shiftLayer: root.shiftLayer
            compact: root.sheetShown
            opacity: root.hudShown ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 140 } }
        }

        ShiftSheet {
            id: sheet
            objectName: "shiftSheet"
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(root.width - 2 * stack.margin, 1180 * root.s)
            opacity: root.sheetShown ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 120 } }
        }
    }
}

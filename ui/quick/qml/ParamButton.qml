// Przycisk / pad: przełącznik, przycisk chwilowy (lewy = przytrzymanie, prawy = zatrzaśnięcie) albo akcja.
import QtQuick

Rectangle {
    id: root
    property string target: ""
    property string text: param ? param.label.toUpperCase() : Params.labelOf(target)
    property string keyHint: ""
    property color activeColor: Theme.accent
    property bool big: false
    property bool interactive: true

    readonly property var param: target !== "" ? Params.get(target) : null
    readonly property bool isAction: target.indexOf("action:") === 0
    readonly property bool active: param ? param.on : flash
    readonly property real s: Theme.scale
    property bool latched: false
    property bool flash: false

    implicitWidth: Math.max(64 * s, label.implicitWidth + 24 * s)
    clip: true
    implicitHeight: big ? Theme.padHeight : 44 * s
    radius: (big ? 10 : 8) * s
    color: active ? activeColor : (big ? Theme.raised : "transparent")
    border.width: 1
    border.color: active ? activeColor : (big ? Qt.darker(activeColor, 2.4) : Qt.lighter(Theme.line, 1.25))

    Connections {
        target: root.param
        ignoreUnknownSignals: true
        function onChanged() { if (!root.param.on) root.latched = false }
    }

    Column {
        anchors.centerIn: parent
        spacing: 4 * root.s
        Text {
            id: label
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(implicitWidth, root.width - 8 * root.s)
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: root.text
            color: root.active ? "#FFFFFF" : Theme.text
            font.family: Theme.labelFont
            font.weight: Font.Bold
            font.pixelSize: Math.round((root.big ? 18 : 16) * root.s)
            font.letterSpacing: 1.2
        }
        Text {
            visible: root.big && root.keyHint !== ""
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.keyHint
            color: root.active ? "#FFFFFF" : Theme.text
            opacity: 0.8
            font.family: Theme.valueFont
            font.pixelSize: Math.round(11 * root.s)
        }
    }

    function release() {
        flash = false
        if (param && param.hold && !latched)
            param.setValue(false)
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.interactive
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        preventStealing: true
        onPressed: (m) => {
            if (root.isAction) {
                root.flash = true
                Session.requestWith("action", root.target)
                return
            }
            if (!root.param) return
            if (root.param.hold) {
                if (m.button === Qt.RightButton) {
                    root.latched = !root.latched
                    root.param.setValue(root.latched)
                } else {
                    root.latched = false
                    root.param.setValue(true)
                }
            } else if (m.button === Qt.LeftButton) {
                root.param.toggle()
            }
        }
        onReleased: (m) => { if (m.button === Qt.LeftButton || root.isAction) root.release() }
        onCanceled: root.release()
    }
}

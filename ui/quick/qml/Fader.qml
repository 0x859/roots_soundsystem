// Suwak pionowy (izolator, EQ) z opcjonalnym przyciskiem KILL pod spodem.
import QtQuick

Item {
    id: root
    property var param: null
    property var killParam: null
    property string label: param ? param.label : ""
    property color color: Theme.accent
    property real track: 150
    property bool interactive: true

    readonly property real s: Theme.scale
    readonly property real norm: param ? param.norm : 0
    readonly property real origin: param ? param.originNorm : 0
    readonly property bool killed: (killParam && killParam.on) || (param && param.killed)

    implicitWidth: Math.max(36 * s, caption.implicitWidth)
    implicitHeight: col.implicitHeight

    Column {
        id: col
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 7 * root.s

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.killed ? "KILL" : (root.param ? root.param.text.replace(" dB", "") : "—")
            color: root.killed ? Theme.kill : Theme.text
            font.family: Theme.valueFont
            font.pixelSize: Math.round(12 * root.s)
        }

        Item {
            id: trackItem
            width: 34 * root.s
            height: root.track
            anchors.horizontalCenter: parent.horizontalCenter

            Rectangle {
                id: groove
                width: 10 * root.s
                height: parent.height
                radius: width / 2
                anchors.horizontalCenter: parent.horizontalCenter
                color: Theme.line
                Rectangle {
                    // symetryczny zakres (EQ) wypełnia od zera, pozostałe (izolator) od dołu
                    readonly property real base: Math.abs(root.origin - 0.5) < 0.01 ? root.origin : 0
                    readonly property real lo: Math.min(base, root.norm)
                    readonly property real hi: Math.max(base, root.norm)
                    visible: !root.killed
                    width: parent.width
                    radius: width / 2
                    y: parent.height * (1 - hi)
                    height: parent.height * (hi - lo)
                    color: root.color
                }
            }
            Rectangle {
                width: 30 * root.s
                height: 14 * root.s
                radius: 4 * root.s
                color: Theme.text
                anchors.horizontalCenter: parent.horizontalCenter
                y: (1 - root.norm) * trackItem.height - height / 2
            }
            // pozycja suwaka MIDI czekającego na przejęcie wartości (pickup)
            Rectangle {
                readonly property var pk: root.param ? Session.pickup[root.param.key] : undefined
                visible: pk !== undefined
                width: parent.width + 6 * root.s
                height: 3 * root.s
                radius: height / 2
                anchors.horizontalCenter: parent.horizontalCenter
                y: (1 - (pk === undefined ? 0 : pk)) * trackItem.height - height / 2
                color: Theme.color("blue", "fx")
            }
            MouseArea {
                anchors.fill: parent
                anchors.margins: -6 * root.s
                enabled: root.interactive && root.param !== null
                preventStealing: true
                cursorShape: Qt.SizeVerCursor
                property real startY: 0
                property real startNorm: 0
                onPressed: (m) => { startY = m.y; startNorm = root.norm }
                onPositionChanged: (m) => {
                    if (!pressed) return
                    const fine = (m.modifiers & Qt.ShiftModifier) ? 0.25 : 1.0
                    root.param.setNorm(startNorm + (startY - m.y) / root.track * fine)
                }
                onDoubleClicked: root.param.reset()
                onWheel: (w) => {
                    const fine = (w.modifiers & Qt.ShiftModifier) ? 0.2 : 1.0
                    root.param.setNorm(root.norm + w.angleDelta.y / 120 * 0.02 * fine)
                }
            }
        }

        Text {
            id: caption
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.label.toUpperCase()
            color: Theme.muted
            font.family: Theme.labelFont
            font.weight: Font.DemiBold
            font.pixelSize: Math.round(12 * root.s)
            font.letterSpacing: 0.5
        }

        ParamButton {
            visible: root.killParam !== null
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(40 * root.s, root.width)
            height: 34 * root.s
            target: root.killParam ? root.killParam.key : ""
            text: "K"
            activeColor: Theme.kill
            interactive: root.interactive
        }
    }
}

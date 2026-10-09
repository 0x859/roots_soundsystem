// Mierniki: wejście, drogi zwrotnicy i wyjście (czerwony pasek u góry = przesterowanie).
import QtQuick

Item {
    id: root
    property real barHeight: 120
    readonly property real s: Theme.scale
    implicitWidth: 6 * 22 * s
    implicitHeight: row.implicitHeight

    Row {
        id: row
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Math.max(4, (root.width - 6 * 16 * root.s) / 6)
        Repeater {
            model: Session.meterLabels
            delegate: Column {
                required property int index
                required property string modelData
                readonly property bool active: Session.meterActive[index]
                readonly property bool clip: Session.clips[index]
                spacing: 6 * root.s
                opacity: active ? 1 : 0.35
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 14 * root.s
                    height: root.barHeight
                    radius: 3
                    color: Theme.line
                    clip: true
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: parent.height * Session.levels[index]
                        color: Session.levels[index] > 0.9 ? Theme.kill
                               : (index === 0 || index === 5 ? Theme.accent : Theme.fx)
                    }
                    Rectangle {
                        width: parent.width
                        height: 4 * root.s
                        color: clip ? Theme.kill : "transparent"
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: modelData
                    color: Theme.muted
                    font.family: Theme.labelFont
                    font.weight: Font.DemiBold
                    font.pixelSize: Math.round(11 * root.s)
                }
            }
        }
    }
}

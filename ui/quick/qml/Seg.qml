// Przełącznik segmentowy: model = [{label, value}], `current` = wybrana wartość.
import QtQuick

Rectangle {
    id: root
    property var model: []
    property var current
    property bool accentCurrent: false
    property bool fill: false
    property real fontSize: 15
    signal picked(var value)

    readonly property real s: Theme.scale
    implicitWidth: row.implicitWidth + 8 * s
    implicitHeight: 48 * s
    radius: 8 * s
    color: Theme.raised

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 4 * root.s
        Repeater {
            model: root.model
            delegate: Rectangle {
                required property var modelData
                readonly property bool on: modelData.value === root.current
                width: root.fill ? (root.width - 8 * root.s - (root.model.length - 1) * 4 * root.s) / root.model.length
                                 : segLabel.implicitWidth + 28 * root.s
                height: root.height - 8 * root.s
                radius: 6 * root.s
                color: on ? (root.accentCurrent ? Theme.accent : Qt.lighter(Theme.line, 1.25)) : "transparent"
                Text {
                    id: segLabel
                    anchors.centerIn: parent
                    width: root.fill ? Math.min(implicitWidth, parent.width - 6) : implicitWidth
                    elide: Text.ElideRight
                    text: modelData.label
                    color: on && root.accentCurrent ? Theme.bg : on ? Theme.text : Qt.darker(Theme.text, 1.15)
                    font.family: Theme.labelFont
                    font.weight: on ? Font.Bold : Font.DemiBold
                    font.pixelSize: Math.round(root.fontSize * root.s)
                    font.letterSpacing: root.fill ? 0.4 : 1.2
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: root.picked(modelData.value)
                }
            }
        }
    }
}

// Wybór koloru z palety motywu („auto” = kolor karty).
import QtQuick

Row {
    id: root
    property string current: "auto"
    property bool allowAuto: true
    signal picked(string name)
    readonly property real s: Theme.scale
    spacing: 8 * s

    Repeater {
        model: root.allowAuto ? ["auto", "accent", "fx", "kill", "blue", "cream"] : ["accent", "fx", "kill", "blue", "cream"]
        delegate: Rectangle {
            required property string modelData
            width: 30 * root.s
            height: width
            radius: width / 2
            color: modelData === "auto" ? "transparent" : Theme.color(modelData, "accent")
            border.width: root.current === modelData ? 3 : (modelData === "auto" ? 1 : 0)
            border.color: root.current === modelData ? Theme.text : Theme.muted
            Text {
                visible: modelData === "auto"
                anchors.centerIn: parent
                text: "A"
                color: Theme.muted
                font.family: Theme.labelFont
                font.pixelSize: Math.round(13 * root.s)
            }
            MouseArea {
                anchors.fill: parent
                onClicked: root.picked(modelData)
            }
        }
    }
}

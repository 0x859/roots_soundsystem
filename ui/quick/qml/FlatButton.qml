// Przycisk nagłówka / inspektora (obrys, wypełniony „primary”, zaznaczony „checked”).
import QtQuick

Rectangle {
    id: root
    property string text: ""
    property bool primary: false
    property bool checked: false
    property bool danger: false
    property bool enabledLook: true
    property real fontSize: 15
    signal clicked()

    readonly property real s: Theme.scale
    implicitWidth: label.implicitWidth + 28 * s
    implicitHeight: 40 * s
    radius: 8 * s
    opacity: enabledLook ? 1 : 0.4
    color: primary ? Theme.accent : checked ? Qt.lighter(Theme.line, 1.25) : (area.containsMouse ? Theme.raised : "transparent")
    border.width: primary ? 0 : 1
    border.color: checked ? Theme.accent : danger ? Theme.kill : Qt.lighter(Theme.line, 1.3)

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.primary ? Theme.bg : root.danger ? Theme.kill : Theme.text
        font.family: Theme.labelFont
        font.weight: root.primary || root.checked ? Font.Bold : Font.DemiBold
        font.pixelSize: Math.round(root.fontSize * root.s)
        font.letterSpacing: 1
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabledLook
        onClicked: root.clicked()
    }
}

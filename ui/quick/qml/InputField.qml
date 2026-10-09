// Pole tekstowe w stylu stołu; `committed(text)` po Enter lub utracie fokusu.
import QtQuick
import QtQuick.Controls

TextField {
    id: root
    signal committed(string text)
    implicitHeight: 40 * Theme.scale
    color: Theme.text
    placeholderTextColor: Theme.muted
    selectByMouse: true
    font.family: Theme.valueFont
    font.pixelSize: Math.round(14 * Theme.scale)
    leftPadding: 10 * Theme.scale
    background: Rectangle {
        radius: 8 * Theme.scale
        color: Theme.raised
        border.color: root.activeFocus ? Theme.accent : Qt.lighter(Theme.line, 1.25)
    }
    onEditingFinished: committed(text)
}

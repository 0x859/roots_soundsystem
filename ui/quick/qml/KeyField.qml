// Przechwycenie klawisza skrótu: kliknij i naciśnij klawisz (Backspace/Delete = usuń).
import QtQuick

Rectangle {
    id: root
    property string keyName: ""
    signal captured(string name)
    readonly property real s: Theme.scale

    implicitHeight: 40 * s
    radius: 8 * s
    color: Theme.raised
    border.color: activeFocus ? Theme.accent : Qt.lighter(Theme.line, 1.25)
    activeFocusOnTab: true

    Text {
        anchors.centerIn: parent
        text: root.activeFocus ? "naciśnij klawisz…" : (root.keyName !== "" ? root.keyName : "—")
        color: root.activeFocus ? Theme.accent : Theme.text
        font.family: Theme.valueFont
        font.pixelSize: Math.round(14 * root.s)
    }
    MouseArea {
        anchors.fill: parent
        onClicked: root.forceActiveFocus()
    }
    Keys.onPressed: (e) => {
        let name = ""
        if (e.key === Qt.Key_Escape) { root.focus = false; e.accepted = true; return }
        if (e.key === Qt.Key_Backspace || e.key === Qt.Key_Delete) name = ""
        else if (e.key === Qt.Key_Space) name = "Space"
        else if (e.key >= Qt.Key_F1 && e.key <= Qt.Key_F12) name = "F" + (e.key - Qt.Key_F1 + 1)
        else if (e.text.length === 1 && e.text.trim() !== "") name = e.text.toUpperCase()
        else return
        e.accepted = true
        root.captured(name)
        root.focus = false
    }
}

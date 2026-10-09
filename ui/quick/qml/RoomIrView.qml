// Własna odpowiedź impulsowa miejsca: nazwa wczytanego pliku i wybór nowego.
import QtQuick

Column {
    id: root
    property bool interactive: true
    readonly property real s: Theme.scale
    readonly property string ir: Session.devices.ir || ""
    spacing: 6 * s

    Caption { text: "WŁASNA IR MIEJSCA" }
    Rectangle {
        width: root.width
        height: 40 * root.s
        radius: 8 * root.s
        color: Theme.raised
        Text {
            anchors.verticalCenter: parent.verticalCenter
            x: 10 * root.s
            width: parent.width - 20 * root.s
            elide: Text.ElideMiddle
            text: root.ir !== "" ? root.ir : "brak (wbudowane miejsca)"
            color: root.ir !== "" ? Theme.text : Theme.muted
            font.family: Theme.valueFont
            font.pixelSize: Math.round(13 * root.s)
        }
    }
    FlatButton {
        text: "WCZYTAJ IR (WAV/FLAC)…"
        enabledLook: root.interactive
        onClicked: Session.request("ir_load")
    }
}

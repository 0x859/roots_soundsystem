// Pamięci syreny M1–M4: klik = przywołaj, Ctrl+klik = zapisz bieżące ustawienia.
import QtQuick

Row {
    id: root
    property bool interactive: true
    property int current: -1
    readonly property real s: Theme.scale
    spacing: 6 * s

    Repeater {
        model: 4
        delegate: Rectangle {
            required property int index
            width: (root.width - 3 * root.spacing) / 4
            height: 36 * root.s
            radius: 6 * root.s
            color: "transparent"
            border.color: root.current === index ? Theme.fx : Qt.lighter(Theme.line, 1.25)
            Text {
                anchors.centerIn: parent
                text: "M" + (index + 1)
                color: root.current === index ? Theme.fx : Theme.text
                font.family: Theme.labelFont
                font.weight: Font.DemiBold
                font.pixelSize: Math.round(14 * root.s)
            }
            MouseArea {
                anchors.fill: parent
                enabled: root.interactive
                onClicked: (m) => {
                    if (m.modifiers & Qt.ControlModifier) {
                        Session.requestWith("siren_store", index)
                    } else {
                        Session.requestWith("action", "action:siren_mem:" + index)
                    }
                    root.current = index
                }
            }
        }
    }
}

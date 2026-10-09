// Poziom mikrofonu (poziomy pasek) i redukcja wzmocnienia kompresora.
import QtQuick

Column {
    id: root
    readonly property real s: Theme.scale
    spacing: 5 * s
    Row {
        width: parent.width
        Text {
            width: parent.width / 2
            text: "MIC"
            color: Theme.muted
            font.family: Theme.labelFont
            font.weight: Font.DemiBold
            font.pixelSize: Math.round(12 * root.s)
        }
        Text {
            width: parent.width / 2
            horizontalAlignment: Text.AlignRight
            text: "GR " + Session.micGr.toFixed(1) + " dB"
            color: Theme.muted
            font.family: Theme.valueFont
            font.pixelSize: Math.round(11 * root.s)
        }
    }
    Rectangle {
        width: parent.width
        height: 10 * root.s
        radius: height / 2
        color: Theme.line
        clip: true
        Rectangle {
            width: parent.width * Session.micLevel
            height: parent.height
            radius: height / 2
            color: Session.micLevel > 0.9 ? Theme.kill : Theme.fx
        }
    }
}

// Ściąga warstwy SHIFT (SOLO trzymane na kontrolerze): kolumny kontrolera z celami gałek i Rec Arm
// w drugiej warstwie. Elementy bez własnego przypisania w SHIFT (działają jak bez SOLO) są przygaszone.
// Tylko do odczytu; dane z `Midi.sheet` (ui/quick/midi.py). Edycja przypisań – karta „MIDI – KONTROLER”.
import QtQuick

Rectangle {
    id: root
    readonly property real s: Theme.scale
    readonly property real pad: 16 * s
    readonly property real gap: 6 * s
    readonly property int count: Math.max(1, Midi.sheet.length)
    readonly property real colW: Math.floor((width - 2 * pad - (count - 1) * gap) / count)
    // napisy dopasowane do szerokości kolumny (wąskie okno: mniejsze, ale bez rozjeżdżania się)
    readonly property real fs: Math.max(10, Math.min(15 * s, colW / 8))

    function toneColor(tone) {
        return tone === "kill" ? Theme.kill : tone === "fx" ? Theme.fx : tone === "accent" ? Theme.accent : Theme.muted
    }

    implicitHeight: body.implicitHeight + 2 * pad
    radius: 14 * s
    color: Theme.card
    border.width: Math.max(2, Math.round(2 * s))
    border.color: Theme.accent

    Column {
        id: body
        x: root.pad
        y: root.pad
        width: root.width - 2 * root.pad
        spacing: 10 * root.s

        Row {
            spacing: 10 * root.s
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: badge.implicitWidth + 14 * root.s
                height: badge.implicitHeight + 6 * root.s
                radius: 5 * root.s
                color: Theme.accent
                Text {
                    id: badge
                    anchors.centerIn: parent
                    text: "SHIFT"
                    color: Theme.bg
                    font.family: Theme.labelFont
                    font.weight: Font.Bold
                    font.pixelSize: Math.round(16 * root.s)
                    font.letterSpacing: 1
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: body.width - badge.implicitWidth - 34 * root.s
                text: "SOLO TRZYMANE · DRUGA WARSTWA GAŁEK I REC ARM"
                elide: Text.ElideRight
                color: Theme.text
                font.family: Theme.labelFont
                font.weight: Font.DemiBold
                font.pixelSize: Math.round(18 * root.s)
                font.letterSpacing: 1.5
            }
        }

        Row {
            spacing: root.gap
            Repeater {
                model: Midi.sheet
                delegate: Column {
                    id: strip
                    required property var modelData
                    width: root.colW
                    spacing: root.gap

                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: strip.modelData.name
                        color: Theme.muted
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(14 * root.s)
                    }

                    Repeater {
                        model: strip.modelData.elements
                        delegate: Rectangle {
                            id: cell
                            required property var modelData
                            readonly property bool own: modelData.own === true
                            readonly property bool knob: modelData.kind === "knob"
                            readonly property color tone: root.toneColor(modelData.tone)
                            width: strip.width
                            height: 62 * root.s
                            radius: 8 * root.s
                            color: Theme.raised
                            border.color: own && modelData.target !== "" ? cell.tone : Theme.line
                            opacity: own ? 1 : 0.35

                            // symbol elementu: kółko = gałka, kwadrat = przycisk (Rec Arm)
                            Rectangle {
                                x: 6 * root.s
                                y: 7 * root.s
                                width: 10 * root.s
                                height: width
                                radius: cell.knob ? width / 2 : 2 * root.s
                                color: "transparent"
                                border.width: Math.max(1.5, 2 * root.s)
                                border.color: cell.own ? cell.tone : Theme.muted
                            }
                            Text {
                                x: 22 * root.s
                                y: 4 * root.s
                                width: parent.width - x - 4 * root.s
                                text: cell.knob ? (cell.modelData.module || "—") : (cell.modelData.name || "PRZYCISK")
                                elide: Text.ElideRight
                                color: Theme.muted
                                font.family: Theme.labelFont
                                font.weight: Font.DemiBold
                                font.pixelSize: Math.round(root.fs * 0.8)
                                font.letterSpacing: 0.5
                            }
                            Text {
                                x: 6 * root.s
                                y: 22 * root.s
                                width: parent.width - 10 * root.s
                                height: parent.height - y - 4 * root.s
                                text: cell.modelData.target !== "" ? String(cell.modelData.label).toUpperCase() : "—"
                                wrapMode: Text.Wrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                color: cell.own ? cell.tone : Theme.text
                                font.family: Theme.labelFont
                                font.weight: Font.DemiBold
                                font.pixelSize: Math.round(root.fs)
                            }
                        }
                    }
                }
            }
        }
    }
}

// HUD gestu MIDI: cel (moduł · parametr), wartość i pasek wartości; gdy parametr czeka na przejęcie
// (pickup) – kierunek ruchu elementu i jego pozycja na pasku. Akcja `action:*`: sama nazwa, bez paska.
// Tylko do odczytu – stan (cel, czas wyświetlania) trzyma MidiOverlay.
import QtQuick

Rectangle {
    id: root
    property string target: ""
    property var info: ({})
    property bool shiftLayer: false
    property bool compact: false  // mniejszy, gdy pod spodem jest ściąga SHIFT

    readonly property real s: Theme.scale
    readonly property bool isAction: info.action === true
    readonly property var param: target !== "" && !isAction ? Params.get(target) : null
    readonly property bool isBool: param !== null && param.kind === "bool"
    readonly property bool hasBar: param !== null && !isBool
    // pozycja elementu kontrolera (0..1), gdy parametr czeka na przejęcie wartości
    readonly property var pk: hasBar ? Session.pickup[target] : undefined
    readonly property bool pending: pk !== undefined
    readonly property real norm: param !== null ? param.norm : 0
    // złoto = tor sygnału, turkus = efekty, czerwień = kill/stop (także suwak skręcony do KILL)
    readonly property color tone: info.tone === "kill" || (param !== null && param.killed) ? Theme.kill
                                  : info.tone === "fx" ? Theme.fx : Theme.accent
    readonly property color pickColor: Theme.color("blue", "fx")
    readonly property string title: isAction ? "AKCJA"
                                    : ((info.module ? info.module + " · " : "") + (info.label || target)).toUpperCase()
    readonly property string valueText: isAction ? String(info.label || target).toUpperCase() : param !== null ? param.text : ""
    readonly property string hint: !pending ? ""
                                   : (pk < norm ? "▲ PODNIEŚ do " : "▼ OPUŚĆ do ") + Math.round(norm * 100) + "%"
    readonly property real pad: (compact ? 14 : 20) * s

    implicitHeight: body.implicitHeight + 2 * pad
    radius: 14 * s
    color: Theme.card
    border.width: Math.max(2, Math.round(2 * s))
    border.color: pending ? pickColor : tone

    Column {
        id: body
        x: root.pad
        y: root.pad
        width: root.width - 2 * root.pad
        spacing: 8 * root.s

        // nazwa celu + znacznik warstwy SHIFT i element kontrolera
        Item {
            width: parent.width
            height: titleText.implicitHeight
            Text {
                id: titleText
                anchors.left: parent.left
                anchors.right: tags.left
                anchors.rightMargin: 12 * root.s
                text: root.title
                elide: Text.ElideRight
                color: root.isAction ? Theme.muted : root.tone
                font.family: Theme.labelFont
                font.weight: Font.DemiBold
                font.pixelSize: Math.round((root.compact ? 22 : 28) * root.s)
                font.letterSpacing: 1.5
            }
            Row {
                id: tags
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8 * root.s
                Rectangle {
                    visible: root.shiftLayer
                    anchors.verticalCenter: parent.verticalCenter
                    width: shiftText.implicitWidth + 14 * root.s
                    height: shiftText.implicitHeight + 6 * root.s
                    radius: 5 * root.s
                    color: Theme.accent
                    Text {
                        id: shiftText
                        anchors.centerIn: parent
                        text: "SHIFT"
                        color: Theme.bg
                        font.family: Theme.labelFont
                        font.weight: Font.Bold
                        font.pixelSize: Math.round(15 * root.s)
                        font.letterSpacing: 1
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.info.code || ""
                    color: Theme.muted
                    font.family: Theme.valueFont
                    font.pixelSize: Math.round(15 * root.s)
                }
            }
        }

        // wartość (parametr) albo nazwa akcji
        Text {
            width: parent.width
            text: root.valueText
            elide: Text.ElideRight
            color: root.isAction ? root.tone : root.isBool && root.param.on ? root.tone : Theme.text
            font.family: root.isAction ? Theme.labelFont : Theme.valueFont
            font.weight: root.isAction ? Font.Bold : Font.Medium
            font.pixelSize: Math.round((root.compact ? 34 : root.isAction ? 50 : 54) * root.s)
            font.letterSpacing: root.isAction ? 2 : 0
        }

        // pasek wartości; od zera dla parametrów dwubiegunowych (np. ±dB), znacznik pozycji elementu przy pickup
        Item {
            visible: root.hasBar
            width: parent.width
            height: (root.compact ? 18 : 26) * root.s
            Rectangle {
                id: track
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                height: 14 * root.s
                radius: height / 2
                color: Theme.raised
                border.color: Theme.line
                readonly property real origin: root.param !== null ? root.param.originNorm : 0
                Rectangle {
                    x: Math.min(track.origin, root.norm) * track.width
                    width: Math.max(track.height / 2, Math.abs(root.norm - track.origin) * track.width)
                    height: parent.height
                    radius: parent.radius
                    color: root.tone
                    opacity: root.pending ? 0.55 : 1
                }
            }
            // wartość parametru = miejsce, do którego trzeba doprowadzić element
            Rectangle {
                visible: root.pending
                x: root.norm * (parent.width - width)
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(3, Math.round(3 * root.s))
                height: parent.height - 6 * root.s
                color: Theme.text
            }
            Rectangle {
                visible: root.pending
                x: (root.pending ? root.pk : 0) * (parent.width - width)
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(6, Math.round(7 * root.s))
                height: parent.height
                radius: width / 2
                color: root.pickColor
                border.color: Theme.bg
                border.width: 2
            }
        }

        // przejęcie wartości: dokąd przesunąć element, żeby zaczął sterować
        Item {
            visible: root.pending
            width: parent.width
            height: hintText.implicitHeight
            Text {
                id: hintText
                anchors.left: parent.left
                anchors.right: posText.left
                anchors.rightMargin: 12 * root.s
                text: root.hint
                elide: Text.ElideRight
                color: root.pickColor
                font.family: Theme.labelFont
                font.weight: Font.Bold
                font.pixelSize: Math.round((root.compact ? 20 : 26) * root.s)
                font.letterSpacing: 1
            }
            Text {
                id: posText
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: "element " + Math.round((root.pending ? root.pk : 0) * 100) + "%"
                color: Theme.muted
                font.family: Theme.valueFont
                font.pixelSize: Math.round(15 * root.s)
            }
        }
    }
}

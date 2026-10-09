// Gałka powiązana z parametrem: przeciąganie w pionie, kółko, Shift = precyzyjnie, dwuklik = domyślna.
import QtQuick
import QtQuick.Shapes

Item {
    id: root
    property var param: null
    property string label: param ? param.label : ""
    property color color: Theme.accent
    property real dial: 60
    property bool interactive: true

    readonly property real s: Theme.scale
    readonly property real norm: param ? param.norm : 0
    readonly property real origin: param ? param.originNorm : 0
    readonly property real stroke: Math.max(3, dial * 0.1)

    implicitWidth: Math.max(dial, caption.implicitWidth)
    implicitHeight: col.implicitHeight

    Column {
        id: col
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 5 * root.s

        Item {
            id: dialItem
            width: root.dial
            height: root.dial
            anchors.horizontalCenter: parent.horizontalCenter

            Shape {
                anchors.fill: parent
                ShapePath {
                    strokeColor: Qt.lighter(Theme.line, 1.15)
                    strokeWidth: root.stroke
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: root.dial / 2
                        centerY: root.dial / 2
                        radiusX: (root.dial - root.stroke) / 2
                        radiusY: radiusX
                        startAngle: 135
                        sweepAngle: 270
                    }
                }
                ShapePath {
                    strokeColor: Theme.knobStyle === "pointer" ? "transparent" : root.color
                    strokeWidth: root.stroke
                    fillColor: "transparent"
                    capStyle: ShapePath.FlatCap
                    PathAngleArc {
                        centerX: root.dial / 2
                        centerY: root.dial / 2
                        radiusX: (root.dial - root.stroke) / 2
                        radiusY: radiusX
                        startAngle: 135 + 270 * root.origin
                        sweepAngle: 270 * (root.norm - root.origin)
                    }
                }
            }

            Rectangle {
                id: cap
                anchors.centerIn: parent
                width: root.dial - 2 * root.stroke - 2
                height: width
                radius: width / 2
                color: "#262420"
                border.color: "#0B0A09"
                rotation: -135 + 270 * root.norm
                Rectangle {
                    visible: Theme.knobStyle !== "arc"
                    width: Math.max(2, 3 * root.s)
                    height: parent.height * 0.3
                    radius: width / 2
                    x: (parent.width - width) / 2
                    y: 3 * root.s
                    color: Theme.knobStyle === "pointer" ? root.color : Theme.text
                }
            }

            // pozycja elementu kontrolera MIDI, który czeka na przejęcie wartości (pickup)
            Item {
                readonly property var pk: root.param ? Session.pickup[root.param.key] : undefined
                visible: pk !== undefined
                anchors.fill: parent
                rotation: 135 + 270 * (pk === undefined ? 0 : pk)
                Rectangle {
                    width: root.stroke + 4
                    height: width
                    radius: width / 2
                    x: parent.width - width + 2
                    y: (parent.height - height) / 2
                    color: Theme.color("blue", "fx")
                    border.color: Theme.bg
                    border.width: 2
                }
            }

            MouseArea {
                anchors.fill: parent
                enabled: root.interactive && root.param !== null
                preventStealing: true
                cursorShape: Qt.SizeVerCursor
                property real startY: 0
                property real startNorm: 0
                onPressed: (m) => { startY = m.y; startNorm = root.norm }
                onPositionChanged: (m) => {
                    if (!pressed) return
                    const fine = (m.modifiers & Qt.ShiftModifier) ? 0.25 : 1.0
                    root.param.setNorm(startNorm + (startY - m.y) / 200 * fine)
                }
                onDoubleClicked: root.param.reset()
                onWheel: (w) => {
                    const fine = (w.modifiers & Qt.ShiftModifier) ? 0.2 : 1.0
                    root.param.setNorm(root.norm + w.angleDelta.y / 120 * 0.02 * fine)
                }
            }
        }

        Text {
            id: caption
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.label.toUpperCase()
            color: Theme.muted
            font.family: Theme.labelFont
            font.weight: Font.DemiBold
            font.pixelSize: Math.round(13 * root.s)
            font.letterSpacing: 1
            elide: Text.ElideRight
            width: Math.min(implicitWidth, root.width)
            horizontalAlignment: Text.AlignHCenter
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.param ? root.param.text : "—"
            color: Theme.text
            font.family: Theme.valueFont
            font.pixelSize: Math.round(13 * root.s)
        }
    }
}

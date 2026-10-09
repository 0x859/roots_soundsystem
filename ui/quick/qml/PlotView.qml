// Wykres częstotliwościowy (odpowiedź toru, zwrotnica, analizator) z krzywych liczonych w Pythonie.
import QtQuick
import QtQuick.Shapes

Item {
    id: root
    property string kind: "response"
    property real plotHeight: 160
    readonly property real s: Theme.scale
    readonly property var curves: kind === "crossover" ? Plots.crossover : kind === "spectrum" ? Plots.spectrum : Plots.response
    readonly property var range: Plots.rangeOf(kind)
    readonly property string title: kind === "crossover" ? "ZWROTNICA" : kind === "spectrum" ? "ANALIZATOR" : "ODPOWIEDŹ TORU"
    readonly property bool watching: kind === "spectrum" && visible

    implicitWidth: 240 * s
    implicitHeight: col.implicitHeight

    onWatchingChanged: Plots.watch(watching ? 1 : -1)
    Component.onCompleted: if (watching) Plots.watch(1)
    Component.onDestruction: if (watching) Plots.watch(-1)

    function fx(f) { return Math.log(f / 20) / Math.LN10 / 3 }

    Column {
        id: col
        width: parent.width
        spacing: 6 * root.s

        Item {
            width: parent.width
            height: legend.height
            Text {
                text: root.title
                color: Theme.muted
                font.family: Theme.labelFont
                font.weight: Font.DemiBold
                font.pixelSize: Math.round(12 * root.s)
                font.letterSpacing: 1
            }
            Row {
                id: legend
                anchors.right: parent.right
                spacing: 8 * root.s
                Repeater {
                    model: root.curves
                    delegate: Text {
                        required property var modelData
                        text: modelData.name
                        color: modelData.color
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(11 * root.s)
                    }
                }
            }
        }

        Rectangle {
            id: area
            width: parent.width
            height: root.plotHeight
            radius: 6 * root.s
            color: Qt.darker(Theme.card, 1.35)
            border.color: Theme.line
            clip: true

            Repeater {
                model: [50, 100, 200, 500, 1000, 2000, 5000, 10000]
                delegate: Rectangle {
                    required property int modelData
                    readonly property bool major: modelData === 100 || modelData === 1000 || modelData === 10000
                    x: root.fx(modelData) * area.width
                    width: 1
                    height: area.height
                    color: Theme.line
                    opacity: major ? 1 : 0.45
                    Text {
                        visible: parent.major
                        x: 3
                        y: area.height - height - 2
                        text: modelData >= 1000 ? (modelData / 1000) + "k" : modelData
                        color: Theme.muted
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(10 * root.s)
                    }
                }
            }
            Repeater {
                model: {
                    const out = []
                    for (let db = Math.ceil(root.range[0] / 12) * 12; db <= root.range[1]; db += 12) out.push(db)
                    return out
                }
                delegate: Rectangle {
                    required property int modelData
                    y: (root.range[1] - modelData) / (root.range[1] - root.range[0]) * area.height
                    width: area.width
                    height: 1
                    color: Theme.line
                    opacity: modelData === 0 ? 1 : 0.45
                    Text {
                        x: 3
                        y: 1
                        text: modelData + " dB"
                        color: Theme.muted
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(10 * root.s)
                    }
                }
            }

            Repeater {
                model: root.curves
                delegate: Shape {
                    required property var modelData
                    anchors.fill: parent
                    ShapePath {
                        strokeColor: modelData.color
                        strokeWidth: modelData.width * root.s
                        strokeStyle: modelData.dashed ? ShapePath.DashLine : ShapePath.SolidLine
                        dashPattern: [4, 3]
                        fillColor: "transparent"
                        joinStyle: ShapePath.RoundJoin
                        PathPolyline {
                            path: modelData.points.map(p => Qt.point(p.x * area.width, p.y * area.height))
                        }
                    }
                }
            }

            Text {
                visible: root.curves.length === 0
                anchors.centerIn: parent
                text: root.kind === "spectrum" ? "Analizator działa po uruchomieniu (START)" : "—"
                color: Theme.muted
                font.family: Theme.labelFont
                font.pixelSize: Math.round(14 * root.s)
            }
        }
    }
}

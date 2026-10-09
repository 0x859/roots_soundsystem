// Wartość z przyciskami ‹ ›: wybór z listy (choice), krok (liczby) albo ON/OFF; klik w środek = lista.
import QtQuick
import QtQuick.Controls

Item {
    id: root
    property var param: null
    property string label: param ? param.label : ""
    property color color: Theme.accent
    property bool interactive: true
    readonly property real s: Theme.scale
    readonly property bool isChoice: param && param.kind === "choice"

    implicitWidth: 120 * s
    implicitHeight: col.implicitHeight

    Column {
        id: col
        width: parent.width
        spacing: 5 * root.s
        Text {
            text: root.label.toUpperCase()
            color: Theme.muted
            font.family: Theme.labelFont
            font.weight: Font.DemiBold
            font.pixelSize: Math.round(12 * root.s)
            font.letterSpacing: 1
            elide: Text.ElideRight
            width: parent.width
        }
        Rectangle {
            width: parent.width
            height: 40 * root.s
            radius: 8 * root.s
            color: Theme.raised
            border.color: Qt.lighter(Theme.line, 1.25)

            Row {
                anchors.fill: parent
                Repeater {
                    model: [-1, 0, 1]
                    delegate: Item {
                        required property int modelData
                        width: modelData === 0 ? parent.width - 2 * 32 * root.s : 32 * root.s
                        height: parent.height
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: modelData === 0 ? 4 : 0
                            anchors.rightMargin: modelData === 0 ? 4 : 0
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            text: modelData < 0 ? "‹" : modelData > 0 ? "›" : (root.param ? root.param.text : "—")
                            color: modelData === 0 && root.param && root.param.kind === "bool" && root.param.on ? root.color : Theme.text
                            elide: Text.ElideRight
                            font.family: modelData === 0 ? Theme.valueFont : Theme.labelFont
                            font.pixelSize: Math.round((modelData === 0 ? 13 : 20) * root.s)
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: root.interactive && root.param !== null
                            onClicked: {
                                if (modelData !== 0) root.param.step(modelData)
                                else if (root.isChoice) menu.open()
                                else if (root.param.kind === "bool") root.param.toggle()
                            }
                            onDoubleClicked: if (modelData === 0 && !root.isChoice) root.param.reset()
                            onWheel: (w) => root.param.step(w.angleDelta.y > 0 ? 1 : -1)
                        }
                    }
                }
            }

            Popup {
                id: menu
                y: parent.height + 2
                width: Math.max(parent.width, 200 * root.s)
                padding: 4
                background: Rectangle { color: Theme.raised; border.color: Theme.line; radius: 8 * root.s }
                contentItem: Column {
                    Repeater {
                        model: root.isChoice ? root.param.choices : []
                        delegate: Rectangle {
                            required property int index
                            required property string modelData
                            width: menu.width - 8
                            height: 34 * root.s
                            radius: 6 * root.s
                            color: hover.containsMouse ? Theme.line : "transparent"
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 10 * root.s
                                text: modelData
                                color: root.param && root.param.index === index ? root.color : Theme.text
                                font.family: Theme.valueFont
                                font.pixelSize: Math.round(13 * root.s)
                            }
                            MouseArea {
                                id: hover
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: { root.param.setValue(index); menu.close() }
                            }
                        }
                    }
                }
            }
        }
    }
}

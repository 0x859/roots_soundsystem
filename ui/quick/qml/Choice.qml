// Lista rozwijana w stylu stołu: model = [{label, value}], `current` = wybrana wartość.
import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    property var model: []
    property var current
    property string placeholder: "—"
    property bool interactive: true
    signal picked(var value)

    readonly property real s: Theme.scale
    readonly property int currentIndex: {
        for (let i = 0; i < model.length; i++) if (model[i].value === current) return i
        return -1
    }

    implicitWidth: 200 * s
    implicitHeight: 40 * s
    radius: 8 * s
    color: Theme.raised
    border.color: popup.opened ? Theme.accent : Qt.lighter(Theme.line, 1.25)
    opacity: interactive ? 1 : 0.5

    Text {
        anchors.verticalCenter: parent.verticalCenter
        x: 10 * root.s
        width: parent.width - 34 * root.s
        elide: Text.ElideRight
        text: root.currentIndex >= 0 ? root.model[root.currentIndex].label : root.placeholder
        color: root.currentIndex >= 0 ? Theme.text : Theme.muted
        font.family: Theme.valueFont
        font.pixelSize: Math.round(13 * root.s)
    }
    Text {
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: 10 * root.s
        text: "▾"
        color: Theme.muted
        font.pixelSize: Math.round(13 * root.s)
    }
    MouseArea {
        anchors.fill: parent
        enabled: root.interactive && root.model.length > 0
        onClicked: popup.open()
    }

    Popup {
        id: popup
        y: root.height + 2
        width: Math.max(root.width, 220 * root.s)
        height: Math.min(list.contentHeight + 8, 340 * root.s)
        padding: 4
        background: Rectangle { color: Theme.raised; border.color: Theme.line; radius: 8 * root.s }
        contentItem: ListView {
            id: list
            clip: true
            model: root.model
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                required property int index
                required property var modelData
                width: ListView.view.width
                height: 34 * root.s
                radius: 6 * root.s
                color: area.containsMouse ? Theme.line : "transparent"
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 10 * root.s
                    width: parent.width - 16 * root.s
                    elide: Text.ElideRight
                    text: modelData.label
                    color: index === root.currentIndex ? Theme.accent : Theme.text
                    font.family: Theme.valueFont
                    font.pixelSize: Math.round(13 * root.s)
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: { popup.close(); root.picked(modelData.value) }
                }
            }
        }
    }
}

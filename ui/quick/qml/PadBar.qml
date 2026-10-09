// Pasek padów wykonawczych (kill, throw, syrena, crash, tap…) ze skrótami klawiszowymi.
import QtQuick

Rectangle {
    id: root
    property var host: null
    property bool editing: false
    property int selected: -1
    readonly property real s: Theme.scale
    readonly property real gap: 8 * s
    readonly property real inner: width - 20 * s
    readonly property int perRow: Math.max(1, Math.min(Profile.pads.length, Math.floor((inner + gap) / (104 * s + gap))))
    readonly property real padW: Math.floor((inner - gap * (perRow - 1)) / perRow)

    color: Theme.card
    radius: 12 * s
    border.color: editing ? Qt.lighter(Theme.line, 1.4) : Theme.line
    implicitHeight: flow.implicitHeight + 20 * s

    function tint(target) {
        return target.indexOf("kill") >= 0 || target === "out.mute" ? Theme.kill : Qt.darker(Theme.fx, 1.3)
    }

    Flow {
        id: flow
        x: 10 * root.s
        y: 10 * root.s
        width: root.inner
        spacing: root.gap
        Repeater {
            model: Profile.pads
            delegate: Item {
                required property int index
                required property var modelData
                width: root.padW
                height: Theme.padHeight
                ParamButton {
                    anchors.fill: parent
                    big: true
                    target: modelData.param
                    text: modelData.label
                    keyHint: Profile.shortcutFor(modelData.param)
                    activeColor: root.tint(modelData.param)
                    interactive: !root.editing
                }
                Rectangle {
                    visible: root.editing
                    anchors.fill: parent
                    radius: 10 * root.s
                    color: "transparent"
                    border.width: root.selected === index ? 2 : 0
                    border.color: Theme.accent
                }
                MouseArea {
                    anchors.fill: parent
                    visible: root.editing
                    onClicked: root.host.selectPad(index)
                }
            }
        }
    }
}

// Nagłówek: START/STOP, sceny, status silnika, przełącznik LIVE/KONFIGURACJA, audio i edycja układu.
import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    readonly property real s: Theme.scale
    readonly property real pad: 10 * s
    readonly property real gap: 10 * s
    readonly property bool fits: left.implicitWidth + right.implicitW + gap + 2 * pad <= width

    color: Theme.card
    radius: 12 * s
    border.color: Theme.line
    implicitHeight: (fits ? Math.max(left.height, right.height) : left.height + gap + right.height) + 2 * pad

    Row {
        id: left
        x: root.pad
        y: root.pad
        spacing: 12 * root.s

        Rectangle {
            width: Math.max(128 * root.s, runLabel.implicitWidth + 36 * root.s)
            height: 52 * root.s
            radius: 10 * root.s
            color: Session.running ? Theme.kill : Qt.darker(Theme.fx, 1.35)
            Text {
                id: runLabel
                anchors.centerIn: parent
                text: Session.running ? "■ STOP" : "▶ START"
                color: "#FFFFFF"
                font.family: Theme.labelFont
                font.weight: Font.Bold
                font.pixelSize: Math.round(20 * root.s)
                font.letterSpacing: 2.4
            }
            MouseArea {
                anchors.fill: parent
                onClicked: Session.request("start_stop")
            }
        }

        Rectangle {
            height: 52 * root.s
            width: sceneRow.implicitWidth + 8 * root.s
            radius: 8 * root.s
            color: Theme.raised
            Row {
                id: sceneRow
                anchors.centerIn: parent
                spacing: 4 * root.s
                FlatButton {
                    text: "‹"
                    fontSize: 22
                    border.width: 0
                    width: 44 * root.s
                    height: 44 * root.s
                    onClicked: Session.request("scene_prev")
                }
                Item {
                    width: Math.max(168 * root.s, sceneName.implicitWidth + 12 * root.s)
                    height: 44 * root.s
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        x: 6 * root.s
                        Text {
                            text: "SCENA"
                            color: Theme.muted
                            font.family: Theme.labelFont
                            font.weight: Font.DemiBold
                            font.pixelSize: Math.round(11 * root.s)
                            font.letterSpacing: 1.3
                        }
                        Text {
                            id: sceneName
                            text: Session.scene
                            color: Theme.text
                            font.family: Theme.labelFont
                            font.weight: Font.DemiBold
                            font.pixelSize: Math.round(20 * root.s)
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: scenePopup.open()
                    }
                    Popup {
                        id: scenePopup
                        y: parent.height + 6
                        width: Math.max(parent.width, 240 * root.s)
                        padding: 4
                        background: Rectangle { color: Theme.raised; border.color: Theme.line; radius: 8 * root.s }
                        contentItem: Column {
                            Repeater {
                                model: Session.scenes
                                delegate: Rectangle {
                                    required property string modelData
                                    width: scenePopup.width - 8
                                    height: 36 * root.s
                                    radius: 6 * root.s
                                    color: sh.containsMouse ? Theme.line : "transparent"
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: 10 * root.s
                                        text: modelData
                                        color: modelData === Session.scene ? Theme.accent : Theme.text
                                        font.family: Theme.labelFont
                                        font.pixelSize: Math.round(17 * root.s)
                                    }
                                    MouseArea {
                                        id: sh
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: { Session.requestWith("scene", modelData); scenePopup.close() }
                                    }
                                }
                            }
                        }
                    }
                }
                FlatButton {
                    text: "›"
                    fontSize: 22
                    border.width: 0
                    width: 44 * root.s
                    height: 44 * root.s
                    onClicked: Session.request("scene_next")
                }
                FlatButton {
                    text: "ZAPISZ"
                    height: 44 * root.s
                    onClicked: Session.request("scene_save")
                }
            }
        }
    }

    Flow {
        id: right
        x: root.fits ? root.width - root.pad - width : root.pad
        y: root.fits ? root.pad + (left.height - height) / 2 : left.y + left.height + root.gap
        width: root.fits ? implicitW : root.width - 2 * root.pad
        spacing: 8 * root.s
        readonly property real implicitW: chips.implicitWidth + dsp.width + nav.implicitWidth + tools.implicitWidth + 3 * spacing

        Row {
            id: chips
            spacing: 8 * root.s
            height: 48 * root.s
            Repeater {
                model: Session.chips
                delegate: Rectangle {
                    required property string modelData
                    anchors.verticalCenter: parent.verticalCenter
                    width: chipText.implicitWidth + 20 * root.s
                    height: 30 * root.s
                    radius: 6 * root.s
                    color: Theme.raised
                    Text {
                        id: chipText
                        anchors.centerIn: parent
                        text: modelData
                        color: Qt.darker(Theme.text, 1.12)
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(13 * root.s)
                    }
                }
            }
            Rectangle {
                visible: Session.cpu !== ""
                anchors.verticalCenter: parent.verticalCenter
                width: cpuText.implicitWidth + 20 * root.s
                height: 30 * root.s
                radius: 6 * root.s
                color: Theme.raised
                Text {
                    id: cpuText
                    anchors.centerIn: parent
                    textFormat: Text.StyledText
                    text: "CPU <font color='" + Theme.accent + "'>" + Session.cpu + "</font>"
                    color: Qt.darker(Theme.text, 1.12)
                    font.family: Theme.valueFont
                    font.pixelSize: Math.round(13 * root.s)
                }
            }
        }

        Item {
            id: dsp
            readonly property bool any: Session.dspOn > 0
            width: dspBox.width
            height: 48 * root.s
            Rectangle {
                id: dspBox
                anchors.verticalCenter: parent.verticalCenter
                width: dspText.implicitWidth + 24 * root.s
                height: 40 * root.s
                radius: 8 * root.s
                color: dsp.any ? Qt.rgba(0.89, 0.65, 0.17, 0.16) : Theme.raised
                border.color: dsp.any ? Theme.accent : Qt.lighter(Theme.line, 1.3)
                Text {
                    id: dspText
                    anchors.centerIn: parent
                    text: "DSP " + Session.dspOn + "/" + Session.dspTotal
                    color: dsp.any ? Theme.accent : Theme.muted
                    font.family: Theme.labelFont
                    font.weight: Font.Bold
                    font.pixelSize: Math.round(15 * root.s)
                    font.letterSpacing: 1.2
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: Session.requestWith("action", "action:dsp_toggle")
                }
            }
        }

        Seg {
            id: nav
            accentCurrent: true
            model: [{ label: "LIVE", value: "live" }, { label: "KONFIGURACJA", value: "config" }]
            current: Session.screen
            onPicked: (v) => Session.screen = v
        }

        Row {
            id: tools
            spacing: 8 * root.s
            height: 48 * root.s
            FlatButton {
                anchors.verticalCenter: parent.verticalCenter
                visible: Session.screen === "config"
                text: "STÓŁ KLASYCZNY"
                onClicked: Session.request("classic")
            }
            FlatButton {
                anchors.verticalCenter: parent.verticalCenter
                text: "AUDIO"
                onClicked: Session.request("audio")
            }
            FlatButton {
                anchors.verticalCenter: parent.verticalCenter
                text: "✎ UKŁAD"
                onClicked: Session.editing = true
            }
        }
    }
}

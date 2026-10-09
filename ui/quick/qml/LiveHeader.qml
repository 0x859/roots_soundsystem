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
        readonly property real implicitW: chips.implicitWidth + (fx.visible ? fx.width + spacing : 0) + midi.width + dsp.width
                                          + nav.implicitWidth + tools.implicitWidth + 4 * spacing

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

        // echo się rozkręca: ostrzeżenie, przytrzymanie = FX PANIC (wyciszenie i czysta taśma)
        Item {
            id: fx
            visible: Session.fxHot
            width: fxBox.width
            height: 48 * root.s
            Rectangle {
                id: fxBox
                anchors.verticalCenter: parent.verticalCenter
                width: fxText.implicitWidth + 24 * root.s
                height: 40 * root.s
                radius: 8 * root.s
                color: fxArea.pressed ? Theme.kill : Qt.rgba(0.85, 0.2, 0.2, 0.22)
                border.color: Theme.kill
                SequentialAnimation on opacity {
                    running: fx.visible && !fxArea.pressed
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.55; duration: 450 }
                    NumberAnimation { to: 1.0; duration: 450 }
                    onRunningChanged: if (!running) fxBox.opacity = 1.0
                }
                Text {
                    id: fxText
                    anchors.centerIn: parent
                    text: "ECHO ↑ PANIC"
                    color: "#FFFFFF"
                    font.family: Theme.labelFont
                    font.weight: Font.Bold
                    font.pixelSize: Math.round(15 * root.s)
                    font.letterSpacing: 1.2
                }
                MouseArea {
                    id: fxArea
                    anchors.fill: parent
                    onPressed: Params.get("out.fx_panic").setValue(true)
                    onReleased: Params.get("out.fx_panic").setValue(false)
                    onCanceled: Params.get("out.fx_panic").setValue(false)
                }
            }
        }

        // stan kontrolera MIDI (kropka = połączony, SHIFT = trzymane SOLO); klik otwiera mapę
        Item {
            id: midi
            width: midiBox.width
            height: 48 * root.s
            Rectangle {
                id: midiBox
                anchors.verticalCenter: parent.verticalCenter
                width: midiRow.implicitWidth + 24 * root.s
                height: 40 * root.s
                radius: 8 * root.s
                color: Midi.hwShift ? Qt.rgba(0.89, 0.65, 0.17, 0.16) : Theme.raised
                border.color: Midi.hwShift ? Theme.accent : Qt.lighter(Theme.line, 1.3)
                Row {
                    id: midiRow
                    anchors.centerIn: parent
                    spacing: 7 * root.s
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 9 * root.s
                        height: width
                        radius: width / 2
                        color: Midi.connected ? Theme.fx : Qt.darker(Theme.muted, 1.3)
                    }
                    Text {
                        text: Midi.hwShift ? "MIDI · SHIFT" : "MIDI"
                        color: Midi.connected ? Theme.text : Theme.muted
                        font.family: Theme.labelFont
                        font.weight: Font.Bold
                        font.pixelSize: Math.round(15 * root.s)
                        font.letterSpacing: 1.2
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: Session.request("midi_map")
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

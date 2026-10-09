// Urządzenia, kanały i tryb wyjścia (wersja robocza – do silnika po ZASTOSUJ): muzyka i para kanałów,
// wyjście i gotowe układy (Scarlett 4i4), mikrofon i jego wejście, tryb, blok, mapowanie dróg w Multi.
import QtQuick

Column {
    id: root
    property bool interactive: true
    readonly property real s: Theme.scale
    readonly property bool wide: width > 520 * s
    readonly property real half: wide ? (width - 12 * s) / 2 : width
    spacing: 12 * s

    component Field: Column {
        property string caption: ""
        default property alias content: box.data
        width: root.half
        spacing: 4 * root.s
        Caption { text: parent.caption }
        Item {
            id: box
            width: parent.width
            height: childrenRect.height
        }
    }

    Flow {
        width: root.width
        spacing: 12 * root.s

        Field {
            caption: "MUZYKA (WEJŚCIE)"
            Choice {
                width: parent.width
                model: Audio.musicDevices
                current: Audio.music
                interactive: root.interactive
                onPicked: (v) => Audio.setMusic(v)
            }
        }
        Field {
            caption: "KANAŁY MUZYKI"
            Choice {
                width: parent.width
                model: Audio.musicPairs
                current: Audio.musicOffset
                interactive: root.interactive && Audio.musicPairs.length > 1
                onPicked: (v) => Audio.setMusicOffset(v)
            }
        }
        Field {
            caption: "WYJŚCIE (" + Audio.channelCount + " KAN.)"
            Choice {
                width: parent.width
                model: Audio.outputDevices
                current: Audio.output
                interactive: root.interactive
                onPicked: (v) => Audio.setOutput(v)
            }
        }
        Field {
            caption: "GOTOWY UKŁAD WYJŚĆ"
            Choice {
                width: parent.width
                model: Audio.presets
                current: ""
                interactive: root.interactive && Audio.presets.length > 1
                onPicked: (v) => Audio.applyPreset(v)
            }
        }
        Field {
            caption: "MIKROFON"
            Choice {
                width: parent.width
                model: Audio.micDevices
                current: Audio.mic
                interactive: root.interactive
                onPicked: (v) => Audio.setMic(v)
            }
        }
        Field {
            caption: "WEJŚCIE MIKROFONU"
            Choice {
                width: parent.width
                model: Audio.micChannels
                current: Audio.micChannel
                interactive: root.interactive && Audio.mic >= 0 && Audio.micChannels.length > 1
                onPicked: (v) => Audio.setMicChannel(v)
            }
        }
        Field {
            caption: "TRYB WYJŚCIA"
            Seg {
                width: parent.width
                fill: true
                height: 42 * root.s
                model: Audio.modes
                current: Audio.mode
                onPicked: (v) => { if (root.interactive) Audio.setMode(v) }
            }
        }
        Field {
            caption: "BLOK (PRÓBKI)"
            Seg {
                width: parent.width
                fill: true
                height: 42 * root.s
                model: Audio.blocks
                current: Audio.block
                onPicked: (v) => { if (root.interactive) Audio.setBlock(v) }
            }
        }
        Field {
            visible: Audio.mode === "sim" && Audio.mirrorAvailable
            caption: "SYMULACJA: KOPIA NA WYJŚCIA 3–4 (SŁUCHAWKI)"
            Seg {
                width: parent.width
                fill: true
                height: 42 * root.s
                fontSize: 13
                model: [{ label: "NIE", value: false }, { label: "TAK", value: true }]
                current: Audio.simMirror
                onPicked: (v) => { if (root.interactive) Audio.setMirror(v) }
            }
        }
        Field {
            caption: "PRZY STARCIE APLIKACJI"
            Seg {
                width: parent.width
                fill: true
                height: 42 * root.s
                fontSize: 13
                model: [{ label: "CZYSTY TOR", value: "clean" }, { label: "OSTATNI STAN", value: "last" }]
                current: Session.devices.startup || "clean"
                onPicked: (v) => { if (root.interactive) Session.requestWith("startup_dsp", v) }
            }
        }
    }

    // mapowanie dróg na kanały (Multi)
    Column {
        visible: Audio.mode === "multi"
        width: root.width
        spacing: 6 * root.s
        Caption { text: "MULTI: DROGI → KANAŁY WYJŚCIA (L / R; jeden kanał = mono)" }
        Repeater {
            model: Audio.ways
            delegate: Row {
                required property var modelData
                spacing: 8 * root.s
                Text {
                    width: 64 * root.s
                    height: 40 * root.s
                    verticalAlignment: Text.AlignVCenter
                    text: modelData.label
                    color: modelData.color
                    font.family: Theme.labelFont
                    font.weight: Font.Bold
                    font.pixelSize: Math.round(16 * root.s)
                    font.letterSpacing: 1.5
                }
                Choice {
                    width: (root.width - 64 * root.s - 16 * root.s) / 2
                    model: Audio.outChannels
                    current: modelData.left
                    interactive: root.interactive
                    onPicked: (v) => Audio.setChannel(modelData.way, "left", v)
                }
                Choice {
                    width: (root.width - 64 * root.s - 16 * root.s) / 2
                    model: Audio.outChannels
                    current: modelData.right
                    interactive: root.interactive
                    onPicked: (v) => Audio.setChannel(modelData.way, "right", v)
                }
            }
        }
    }

    Repeater {
        model: Audio.problems.concat(Audio.tips)
        delegate: Text {
            required property int index
            required property string modelData
            width: root.width
            wrapMode: Text.WordWrap
            text: (index < Audio.problems.length ? "⚠ " : "ⓘ ") + modelData
            color: index < Audio.problems.length ? Theme.color("kill", "kill") : Theme.muted
            font.family: Theme.valueFont
            font.pixelSize: Math.round(12 * root.s)
        }
    }
    Text {
        visible: Audio.mode === "multi" && Audio.problems.length === 0
        text: "● Mapowanie poprawne"
        color: Theme.fx
        font.family: Theme.valueFont
        font.pixelSize: Math.round(12 * root.s)
    }

    Flow {
        width: root.width
        spacing: 8 * root.s
        FlatButton {
            text: "ZASTOSUJ"
            primary: Audio.dirty
            enabledLook: root.interactive && Audio.dirty
            onClicked: Audio.apply()
        }
        FlatButton {
            text: "PRZYWRÓĆ"
            enabledLook: root.interactive && Audio.dirty
            onClicked: Audio.revert()
        }
        FlatButton {
            text: "ODŚWIEŻ URZĄDZENIA"
            enabledLook: root.interactive
            onClicked: Audio.refresh()
        }
        FlatButton {
            text: "OKNO AUDIO…"
            enabledLook: root.interactive
            onClicked: Session.request("audio")
        }
    }
}

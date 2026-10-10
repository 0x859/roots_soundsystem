// Kontroler MIDI: port, profil, warstwa NORMAL/SHIFT, mapa fizyczna (np. Akai MIDImix) z przypisaniami
// i wartościami na żywo, edycja przypisania klikniętego elementu oraz lista przypisań spoza mapy.
import QtQuick

Column {
    id: root
    property bool interactive: true
    readonly property real s: Theme.scale
    readonly property bool shiftLayer: Midi.shiftView || Midi.hwShift
    readonly property real stripW: Math.max(76 * s, (width - 2 * 12 * s - 8 * 6 * s) / Math.max(1, Midi.strips.length))
    readonly property var sel: findElement(Midi.selected)
    spacing: 12 * s

    function toneColor(tone) {
        return tone === "kill" ? Theme.kill : tone === "fx" ? Theme.fx : tone === "accent" ? Theme.accent : Theme.muted
    }
    function findElement(id) {
        if (id === "") return null
        for (const st of Midi.strips)
            for (const e of st.elements)
                if (e.id === id) return e
        for (const o of Midi.others)
            if (o.id === id) return {id: o.id, sid: o.id, kind: "other", name: "", code: o.name, isShift: false,
                                     normal: o.shift ? {target: ""} : o, shift: o.shift ? o : {target: ""}, shiftOwn: o.shift}
        return null
    }
    // „1 przypisanie”, „3 przypisania”, „83 przypisania”, „15 przypisań”
    function countText(n) {
        const d = n % 10, dd = n % 100
        return n + (n === 1 ? " przypisanie" : d >= 2 && d <= 4 && (dd < 12 || dd > 14) ? " przypisania" : " przypisań")
    }
    function pick(id) { if (root.interactive) Midi.select(Midi.selected === id ? "" : id) }

    // --- pasek: port, profil, warstwa, tryby ---
    Flow {
        width: root.width
        spacing: 8 * root.s
        Choice {
            width: Math.min(root.width, 230 * root.s)
            model: Midi.ports
            current: Midi.port
            placeholder: "Port MIDI…"
            interactive: root.interactive && Midi.available
            onPicked: (v) => Midi.openPort(v)
        }
        FlatButton {
            text: "↻"
            width: 40 * root.s
            fontSize: 18
            enabledLook: root.interactive && Midi.available
            onClicked: Midi.refreshPorts()
        }
        Choice {
            width: Math.min(root.width, 190 * root.s)
            model: Midi.profiles
            current: Midi.profileName
            placeholder: "Profil kontrolera…"
            interactive: root.interactive
            onPicked: (v) => Midi.applyProfile(v)
        }
        Seg {
            height: 40 * root.s
            fontSize: 14
            model: [{label: "NORMAL", value: false}, {label: "SHIFT (SOLO)", value: true}]
            current: root.shiftLayer
            accentCurrent: Midi.hwShift
            onPicked: (v) => { if (root.interactive) Midi.setShiftView(v) }
        }
        FlatButton {
            text: "LEARN"
            checked: Midi.learning
            enabledLook: root.interactive && Midi.available
            onClicked: Midi.setLearning(!Midi.learning)
        }
        FlatButton {
            text: "PRZEJĘCIE"
            checked: Midi.pickup
            enabledLook: root.interactive
            onClicked: Midi.setPickup(!Midi.pickup)
        }
        FlatButton {
            // animacja diod po podłączeniu kontrolera; włączenie pokazuje ją od razu
            text: "POWITANIE"
            checked: Midi.intro
            enabledLook: root.interactive
            onClicked: Midi.setIntro(!Midi.intro)
        }
        FlatButton { text: "EKSPORT"; enabledLook: root.interactive; onClicked: Midi.requestFile("export") }
        FlatButton { text: "IMPORT"; enabledLook: root.interactive; onClicked: Midi.requestFile("import") }
        FlatButton {
            text: "WYCZYŚĆ"
            danger: true
            enabledLook: root.interactive && Midi.mappedCount > 0
            onClicked: { Midi.clearMapping(); Midi.select("") }
        }
    }

    // --- stan połączenia ---
    Row {
        spacing: 8 * root.s
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 10 * root.s
            height: width
            radius: width / 2
            color: Midi.connected ? Theme.fx : Theme.kill
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: !Midi.available ? "MIDI niedostępne (brak python-rtmidi / pygame-ce)"
                  : Midi.connected ? Midi.port + (Midi.ledsOut ? " · diody aktywne" : " · bez diod (brak portu wyjściowego)")
                  : "Kontroler niepodłączony – połączy się sam po podłączeniu"
            color: Theme.text
            font.family: Theme.labelFont
            font.pixelSize: Math.round(14 * root.s)
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.countText(Midi.mappedCount) + (Midi.lastEvent !== "" ? "  ·  " + Midi.lastEvent : "")
            color: Theme.muted
            font.family: Theme.valueFont
            font.pixelSize: Math.round(13 * root.s)
        }
    }
    Text {
        visible: Midi.learning
        width: root.width
        wrapMode: Text.WordWrap
        text: "LEARN: porusz kontrolką w aplikacji (albo w inspektorze układu wybierz MIDI LEARN), potem elementem kontrolera. "
              + "Trzymaj SOLO, aby przypisać do warstwy SHIFT."
        color: Theme.accent
        font.family: Theme.labelFont
        font.pixelSize: Math.round(13 * root.s)
    }
    Text {
        visible: Midi.strips.length === 0
        width: root.width
        wrapMode: Text.WordWrap
        text: "Brak mapy fizycznej – wybierz profil kontrolera (np. Akai MIDImix). Przypisania z trybu learn są na liście poniżej."
        color: Theme.muted
        font.family: Theme.labelFont
        font.pixelSize: Math.round(14 * root.s)
    }

    // --- mapa kontrolera ---
    Flickable {
        visible: Midi.strips.length > 0
        width: root.width
        height: body.height
        contentWidth: body.width
        contentHeight: body.height
        clip: true
        interactive: contentWidth > width
        boundsBehavior: Flickable.StopAtBounds

        Rectangle {
            id: body
            width: Math.max(root.width, strips.implicitWidth + 24 * root.s)
            height: strips.implicitHeight + 24 * root.s
            radius: 14 * root.s
            color: Qt.darker(Theme.bg, 1.25)
            border.color: Theme.line

            Row {
                id: strips
                x: 12 * root.s
                y: 12 * root.s
                spacing: 6 * root.s
                Repeater {
                    model: Midi.strips
                    delegate: Rectangle {
                        id: strip
                        required property var modelData
                        readonly property bool master: modelData.name === "MASTER"
                        width: root.stripW
                        height: col.implicitHeight + 12 * root.s
                        radius: 10 * root.s
                        color: master ? Qt.darker(Theme.card, 1.1) : Theme.card
                        border.color: Theme.line
                        Column {
                            id: col
                            x: 0
                            y: 6 * root.s
                            width: parent.width
                            spacing: 6 * root.s
                            Text {
                                width: parent.width
                                horizontalAlignment: Text.AlignHCenter
                                text: strip.modelData.name
                                color: Theme.muted
                                font.family: Theme.labelFont
                                font.weight: Font.Bold
                                font.pixelSize: Math.round(13 * root.s)
                                font.letterSpacing: 1.5
                            }
                            Repeater {
                                model: strip.modelData.elements
                                delegate: MapElement {
                                    required property var modelData
                                    e: modelData
                                    width: col.width
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // --- wybrany element: przypisania i wybór celu ---
    Rectangle {
        visible: root.sel !== null
        width: root.width
        height: visible ? editor.implicitHeight + 24 * root.s : 0
        radius: 10 * root.s
        color: Theme.raised
        border.color: Theme.accent

        Column {
            id: editor
            x: 12 * root.s
            y: 12 * root.s
            width: parent.width - 24 * root.s
            spacing: 8 * root.s

            Row {
                spacing: 10 * root.s
                Text {
                    text: root.sel ? (root.sel.code + (root.sel.name ? " · " + root.sel.name : "")
                                      + (root.sel.kind === "knob" ? " · gałka" : root.sel.kind === "fader" ? " · suwak" : "")) : ""
                    color: Theme.text
                    font.family: Theme.labelFont
                    font.weight: Font.Bold
                    font.pixelSize: Math.round(16 * root.s)
                }
                FlatButton { text: "ZAMKNIJ"; height: 30 * root.s; fontSize: 12; onClicked: Midi.select("") }
            }
            Text {
                visible: root.sel !== null && root.sel.isShift
                text: "Ten przycisk działa jako SHIFT: trzymany przełącza gałki (i rząd MUTE) na drugą warstwę."
                color: Theme.muted
                font.family: Theme.labelFont
                font.pixelSize: Math.round(14 * root.s)
            }
            Repeater {
                model: root.sel && !root.sel.isShift ? [false, true] : []
                delegate: Row {
                    required property var modelData
                    readonly property bool layerShift: modelData
                    readonly property var a: root.sel ? (layerShift ? root.sel.shift : root.sel.normal) : null
                    readonly property bool own: !layerShift || (root.sel && root.sel.shiftOwn)
                    spacing: 8 * root.s
                    Rectangle {
                        width: 74 * root.s
                        height: 30 * root.s
                        radius: 6 * root.s
                        color: layerShift === root.shiftLayer ? Theme.accent : "transparent"
                        border.color: Qt.lighter(Theme.line, 1.3)
                        Text {
                            anchors.centerIn: parent
                            text: layerShift ? "SHIFT" : "NORMAL"
                            color: layerShift === root.shiftLayer ? Theme.bg : Theme.text
                            font.family: Theme.labelFont
                            font.weight: Font.Bold
                            font.pixelSize: Math.round(12 * root.s)
                        }
                        MouseArea { anchors.fill: parent; onClicked: Midi.setShiftView(layerShift) }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: !a || a.target === "" ? "— nieprzypisany —"
                              : (a.module ? a.module + " · " : "") + a.label + (own ? "" : "  (jak bez SHIFT)")
                        color: !a || a.target === "" || !own ? Theme.muted : root.toneColor(a.tone)
                        font.family: Theme.labelFont
                        font.weight: Font.DemiBold
                        font.pixelSize: Math.round(15 * root.s)
                    }
                    FlatButton {
                        visible: a !== null && a.target !== "" && own
                        text: "USUŃ"
                        danger: true
                        height: 30 * root.s
                        fontSize: 12
                        onClicked: Midi.unassign(layerShift ? root.sel.sid : root.sel.id, layerShift)
                    }
                }
            }
            Caption {
                visible: root.sel !== null && !root.sel.isShift
                text: "PRZYPISZ DO WARSTWY " + (root.shiftLayer ? "SHIFT" : "NORMAL") + " – wyszukaj parametr lub akcję:"
            }
            InputField {
                id: query
                visible: root.sel !== null && !root.sel.isShift
                width: Math.min(editor.width, 360 * root.s)
                placeholderText: "np. echo, syrena, kill, scena…"
            }
            Flow {
                visible: root.sel !== null && !root.sel.isShift
                width: editor.width
                spacing: 6 * root.s
                Repeater {
                    model: root.sel ? Midi.search(query.text) : []
                    delegate: Rectangle {
                        required property var modelData
                        width: chip.implicitWidth + 18 * root.s
                        height: 30 * root.s
                        radius: 6 * root.s
                        color: chipArea.containsMouse ? Theme.card : "transparent"
                        border.color: Qt.lighter(Theme.line, 1.3)
                        Text {
                            id: chip
                            anchors.centerIn: parent
                            text: (modelData.module ? modelData.module + " · " : "") + modelData.label
                            color: root.toneColor(modelData.tone)
                            font.family: Theme.labelFont
                            font.pixelSize: Math.round(13 * root.s)
                        }
                        MouseArea {
                            id: chipArea
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: Midi.assign(root.shiftLayer ? root.sel.sid : root.sel.id, modelData.value, root.shiftLayer)
                        }
                    }
                }
            }
        }
    }

    // --- przypisania spoza mapy (learn, inne kontrolery) ---
    Column {
        visible: Midi.others.length > 0
        width: root.width
        spacing: 4 * root.s
        Caption { text: "INNE PRZYPISANIA (" + Midi.others.length + ")" }
        Flow {
            width: root.width
            spacing: 6 * root.s
            Repeater {
                model: Midi.others
                delegate: Rectangle {
                    required property var modelData
                    width: otherText.implicitWidth + 18 * root.s
                    height: 30 * root.s
                    radius: 6 * root.s
                    color: Midi.selected === modelData.id ? Theme.card : "transparent"
                    border.color: Midi.selected === modelData.id ? Theme.accent : Qt.lighter(Theme.line, 1.3)
                    Text {
                        id: otherText
                        anchors.centerIn: parent
                        text: (modelData.shift ? "SHIFT + " : "") + modelData.name + " → " + modelData.label
                        color: root.toneColor(modelData.tone)
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(12 * root.s)
                    }
                    MouseArea { anchors.fill: parent; onClicked: root.pick(modelData.id) }
                }
            }
        }
    }

    // --- element mapy: gałka, przycisk z diodą albo suwak, z podpisem przypisania ---
    component MapElement: Item {
        id: el
        property var e
        readonly property var a: root.shiftLayer ? e.shift : e.normal
        readonly property bool dim: root.shiftLayer && !e.shiftOwn
        readonly property string hwId: root.shiftLayer ? e.sid : e.id
        readonly property var p: a.target !== "" && !a.action ? Params.get(a.target) : null
        readonly property var hwPos: Midi.hw[hwId]
        readonly property bool pending: p !== null && Session.pickup[a.target] !== undefined
        readonly property bool selected: Midi.selected === e.id
        readonly property color tone: root.toneColor(a.tone)
        readonly property int act: (Midi.activity[e.id] || 0) + (e.sid !== e.id ? (Midi.activity[e.sid] || 0) : 0)
        readonly property real w: width - 10 * root.s
        height: body.height + caption.height + 4 * root.s
        opacity: dim ? 0.55 : 1

        onActChanged: flash.restart()

        Item {
            id: body
            anchors.horizontalCenter: parent.horizontalCenter
            width: el.e.kind === "fader" ? 30 * root.s : el.e.kind === "button" ? el.w * 0.8 : 40 * root.s
            height: el.e.kind === "fader" ? 130 * root.s : el.e.kind === "button" ? 26 * root.s : 40 * root.s

            // gałka: obwódka w kolorze toru, wskazówka = wartość parametru, kropka = pozycja przed przejęciem
            Rectangle {
                visible: el.e.kind === "knob"
                anchors.fill: parent
                radius: width / 2
                color: Theme.raised
                border.width: 2 * root.s
                border.color: el.a.target !== "" ? el.tone : Theme.line
                Item {
                    anchors.fill: parent
                    visible: el.p !== null
                    rotation: -135 + 270 * (el.p ? el.p.norm : 0)
                    Rectangle {
                        x: parent.width / 2 - width / 2
                        y: 4 * root.s
                        width: 3 * root.s
                        height: parent.height * 0.34
                        radius: width / 2
                        color: Theme.text
                    }
                }
                Item {
                    anchors.fill: parent
                    visible: el.pending && el.hwPos !== undefined
                    rotation: -135 + 270 * (el.hwPos || 0)
                    Rectangle {
                        x: parent.width / 2 - width / 2
                        y: -3 * root.s
                        width: 6 * root.s
                        height: width
                        radius: width / 2
                        color: Theme.color("cream", "#D8D2C4")
                    }
                }
            }
            // przycisk z diodą (MUTE – bursztyn, REC ARM – czerwień, SOLO – świeci przy SHIFT)
            Rectangle {
                visible: el.e.kind === "button"
                anchors.fill: parent
                radius: 5 * root.s
                color: Theme.raised
                border.color: el.a.target !== "" || el.e.isShift ? Qt.lighter(Theme.line, 1.4) : Theme.line
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width * 0.5
                    height: 6 * root.s
                    radius: height / 2
                    readonly property bool lit: el.e.isShift ? Midi.hwShift : (el.p !== null && el.p.kind === "bool" && el.p.on)
                    color: lit ? (el.e.isShift || el.e.name === "MUTE" ? Theme.accent : Theme.kill) : Qt.darker(Theme.line, 1.2)
                }
            }
            // suwak: wypełnienie do wartości, kreska = pozycja przed przejęciem
            Rectangle {
                visible: el.e.kind === "fader"
                anchors.horizontalCenter: parent.horizontalCenter
                width: 6 * root.s
                height: parent.height
                radius: 3 * root.s
                color: Theme.raised
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: parent.height * (el.p ? el.p.norm : 0)
                    radius: parent.radius
                    color: el.tone
                    opacity: 0.8
                }
            }
            Rectangle {
                visible: el.e.kind === "fader" && el.p !== null
                anchors.horizontalCenter: parent.horizontalCenter
                y: (parent.height - height) * (1 - (el.p ? el.p.norm : 0))
                width: parent.width
                height: 12 * root.s
                radius: 3 * root.s
                color: Theme.color("cream", "#D8D2C4")
                border.color: Theme.bg
            }
            Rectangle {
                visible: el.e.kind === "fader" && el.pending && el.hwPos !== undefined
                anchors.horizontalCenter: parent.horizontalCenter
                y: (parent.height - height) * (1 - (el.hwPos || 0))
                width: parent.width + 8 * root.s
                height: 3 * root.s
                color: Theme.kill
            }
            // błysk przy komunikacie z kontrolera
            Rectangle {
                id: flashRect
                anchors.fill: parent
                anchors.margins: -4 * root.s
                radius: el.e.kind === "knob" ? width / 2 : 6 * root.s
                color: "transparent"
                border.width: 2 * root.s
                border.color: Theme.accent
                opacity: 0
                NumberAnimation on opacity { id: flash; running: false; from: 1; to: 0; duration: 450 }
            }
            Rectangle {
                visible: el.selected
                anchors.fill: parent
                anchors.margins: -5 * root.s
                radius: el.e.kind === "knob" ? width / 2 : 7 * root.s
                color: "transparent"
                border.width: 2 * root.s
                border.color: Theme.text
            }
        }
        Column {
            id: caption
            anchors.top: body.bottom
            anchors.topMargin: 4 * root.s
            width: parent.width
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                visible: text !== ""
                text: el.e.isShift ? "SHIFT" : el.e.kind === "button" ? el.e.name : el.a.module
                color: el.e.isShift ? Theme.accent : el.e.kind === "button" ? Theme.muted : el.tone
                font.family: Theme.labelFont
                font.weight: Font.Bold
                font.pixelSize: Math.round(10 * root.s)
                font.letterSpacing: 1
            }
            Text {
                width: parent.width - 4 * root.s
                x: 2 * root.s
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                text: el.e.isShift ? "druga warstwa" : el.a.target === "" ? "—" : el.a.label
                color: el.a.target === "" && !el.e.isShift ? Theme.muted : Theme.text
                font.family: Theme.labelFont
                font.pixelSize: Math.round(12 * root.s)
            }
        }
        MouseArea {
            anchors.fill: parent
            enabled: root.interactive
            onClicked: root.pick(el.e.id)
        }
    }
}

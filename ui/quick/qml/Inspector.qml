// Inspektor trybu edycji: kontrolka, karta, pady, motyw oraz wyszukiwarka parametrów.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var host: null
    property int selCard: -1
    property int selCtl: -1
    property int selPad: -1
    property string tab: "control"

    readonly property real s: Theme.scale
    readonly property var card: selCard >= 0 && selCard < Profile.cards.length ? Profile.cards[selCard] : null
    readonly property var ctl: card && selCtl >= 0 && selCtl < card.controls.length ? card.controls[selCtl] : null
    readonly property var pad: selPad >= 0 && selPad < Profile.pads.length ? Profile.pads[selPad] : null
    readonly property var typeNames: ({ knob: "Gałka", fader: "Suwak", button: "Przycisk", pad: "Pad", meter: "Widok", value: "Wartość" })

    function focusSearch() { search.forceActiveFocus() }

    color: Theme.card
    radius: 12 * s
    border.color: Theme.line

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14 * root.s
        spacing: 12 * root.s

        Seg {
            fill: true
            Layout.fillWidth: true
            height: 46 * root.s
            fontSize: 11
            model: [{ label: "KONTROLKA", value: "control" }, { label: "KARTA", value: "card" },
                    { label: "PADY", value: "pads" }, { label: "MOTYW", value: "theme" }]
            current: root.tab
            onPicked: (v) => root.tab = v
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: pages.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}

            Column {
                id: pages
                width: parent.width - 10 * root.s
                spacing: 12 * root.s

                // ---------- KONTROLKA ----------
                Column {
                    visible: root.tab === "control"
                    width: parent.width
                    spacing: 10 * root.s

                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: root.ctl ? "Zaznaczona: " + (root.ctl.label || Params.labelOf(root.ctl.param)) + "  ·  " + root.ctl.param
                                       : "Kliknij kontrolkę na karcie, aby ją zmienić. Przeciągnij, aby przenieść."
                        color: Theme.muted
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(12 * root.s)
                    }

                    Column {
                        visible: root.ctl !== null
                        width: parent.width
                        spacing: 10 * root.s

                        Caption { text: "CEL (PARAMETR / AKCJA / WIDOK)" }
                        InputField {
                            width: parent.width
                            text: root.ctl ? root.ctl.param : ""
                            onCommitted: (t) => {
                                if (root.ctl && t !== root.ctl.param && Params.typesFor(t).length > 0)
                                    Profile.setControlProp(root.selCard, root.selCtl, "param", t)
                            }
                        }

                        Caption { text: "TYP KONTROLKI" }
                        Flow {
                            width: parent.width
                            spacing: 6 * root.s
                            Repeater {
                                model: root.ctl ? Params.typesFor(root.ctl.param) : []
                                delegate: FlatButton {
                                    required property string modelData
                                    text: root.typeNames[modelData]
                                    height: 36 * root.s
                                    fontSize: 14
                                    checked: root.ctl && root.ctl.type === modelData
                                    onClicked: Profile.setControlProp(root.selCard, root.selCtl, "type", modelData)
                                }
                            }
                        }

                        Caption { text: "ROZMIAR" }
                        Seg {
                            fill: true
                            width: parent.width
                            height: 42 * root.s
                            model: [{ label: "S", value: "S" }, { label: "M", value: "M" }, { label: "L", value: "L" }]
                            current: root.ctl ? root.ctl.size : "M"
                            onPicked: (v) => Profile.setControlProp(root.selCard, root.selCtl, "size", v)
                        }

                        Caption { text: "ETYKIETA" }
                        InputField {
                            width: parent.width
                            text: root.ctl && root.ctl.label ? root.ctl.label : ""
                            placeholderText: root.ctl ? Params.labelOf(root.ctl.param) : ""
                            onCommitted: (t) => Profile.setControlProp(root.selCard, root.selCtl, "label", t)
                        }

                        Caption { text: "KOLOR" }
                        Swatches {
                            current: root.ctl && root.ctl.color ? root.ctl.color : "auto"
                            onPicked: (n) => Profile.setControlProp(root.selCard, root.selCtl, "color", n === "auto" ? "" : n)
                        }

                        Row {
                            width: parent.width
                            spacing: 10 * root.s
                            Column {
                                width: (parent.width - parent.spacing) / 2
                                spacing: 6 * root.s
                                Caption { text: "SKRÓT" }
                                KeyField {
                                    width: parent.width
                                    keyName: root.ctl ? Profile.shortcutFor(root.ctl.param) : ""
                                    onCaptured: (n) => Profile.setShortcut(root.ctl.param, n)
                                }
                            }
                            Column {
                                width: (parent.width - parent.spacing) / 2
                                spacing: 6 * root.s
                                Caption { text: "MIDI" }
                                FlatButton {
                                    width: parent.width
                                    readonly property string mid: root.ctl ? Session.midiFor(root.ctl.param) : ""
                                    text: mid !== "" ? mid : "PRZYPISZ (LEARN)"
                                    fontSize: 13
                                    enabledLook: root.ctl !== null && Params.isParam(root.ctl.param)
                                    onClicked: Session.requestWith("midi_learn", root.ctl.param)
                                }
                            }
                        }

                        Flow {
                            width: parent.width
                            spacing: 6 * root.s
                            FlatButton {
                                text: "◀"
                                enabledLook: root.selCtl > 0
                                onClicked: { Profile.moveControl(root.selCard, root.selCtl, root.selCard, root.selCtl - 1); root.host.selectControl(root.selCard, root.selCtl - 1) }
                            }
                            FlatButton {
                                text: "▶"
                                enabledLook: root.card !== null && root.selCtl < root.card.controls.length - 1
                                onClicked: { Profile.moveControl(root.selCard, root.selCtl, root.selCard, root.selCtl + 1); root.host.selectControl(root.selCard, root.selCtl + 1) }
                            }
                            FlatButton {
                                text: "DO PADÓW"
                                enabledLook: root.ctl !== null && root.ctl.param.indexOf("view:") !== 0
                                onClicked: Profile.addPad(root.ctl.param)
                            }
                            FlatButton {
                                text: "USUŃ"
                                danger: true
                                onClicked: { Profile.removeControl(root.selCard, root.selCtl); root.host.selectCard(root.selCard) }
                            }
                        }
                    }
                }

                // ---------- KARTA ----------
                Column {
                    visible: root.tab === "card"
                    width: parent.width
                    spacing: 10 * root.s

                    Text {
                        visible: root.card === null
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: "Kliknij kartę lub jej nagłówek. Przeciągnij za ⋮⋮, aby zmienić kolejność."
                        color: Theme.muted
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(12 * root.s)
                    }

                    Column {
                        visible: root.card !== null
                        width: parent.width
                        spacing: 10 * root.s

                        Caption { text: "TYTUŁ KARTY" }
                        InputField {
                            width: parent.width
                            text: root.card ? root.card.title : ""
                            onCommitted: (t) => Profile.setCardProp(root.selCard, "title", t)
                        }

                        Caption { text: "SZEROKOŚĆ (KOLUMNY SIATKI)" }
                        Seg {
                            fill: true
                            width: parent.width
                            height: 42 * root.s
                            model: [1, 2, 3, 4].map(n => ({ label: String(n), value: n }))
                            current: root.card ? root.card.span : 1
                            onPicked: (v) => Profile.setCardSize(root.selCard, v, root.card.rows)
                        }

                        Caption { text: "WYSOKOŚĆ KARTY (PX; AUTO = WG ZAWARTOŚCI)" }
                        Row {
                            spacing: 6 * root.s
                            FlatButton {
                                text: "AUTO"
                                checked: root.card !== null && root.card.height === 0
                                onClicked: Profile.setCardBox(root.selCard, root.card.span, root.card.rows, 0)
                            }
                            FlatButton { text: "−"; width: 44 * root.s; onClicked: root.host.nudgeHeight(root.selCard, -40) }
                            Text {
                                width: 64 * root.s
                                height: 40 * root.s
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                text: root.card && root.card.height > 0 ? root.card.height : "auto"
                                color: Theme.text
                                font.family: Theme.valueFont
                                font.pixelSize: Math.round(15 * root.s)
                            }
                            FlatButton { text: "+"; width: 44 * root.s; onClicked: root.host.nudgeHeight(root.selCard, 40) }
                        }

                        Caption { text: "RZĘDY SIATKI" }
                        Seg {
                            fill: true
                            width: parent.width
                            height: 42 * root.s
                            model: [1, 2, 3].map(n => ({ label: String(n), value: n }))
                            current: root.card ? root.card.rows : 1
                            onPicked: (v) => Profile.setCardSize(root.selCard, root.card.span, v)
                        }

                        Caption { text: "KONTROLEK W RZĘDZIE (AUTO = WG ROZMIARU)" }
                        Seg {
                            fill: true
                            width: parent.width
                            height: 42 * root.s
                            fontSize: 13
                            model: [{ label: "AUTO", value: 0 }].concat([2, 3, 4, 5, 6, 8].map(n => ({ label: String(n), value: n })))
                            current: root.card ? root.card.cols : 0
                            onPicked: (v) => Profile.setCardProp(root.selCard, "cols", v)
                        }

                        Caption { text: "W TRYBIE LIVE" }
                        Seg {
                            fill: true
                            width: parent.width
                            height: 42 * root.s
                            fontSize: 13
                            model: [{ label: "ROZWINIĘTA", value: false }, { label: "ZWINIĘTA", value: true }]
                            current: root.card ? root.card.collapsed : false
                            onPicked: (v) => Profile.setCardProp(root.selCard, "collapsed", v)
                        }

                        Caption { text: "WIDOCZNOŚĆ" }
                        Seg {
                            fill: true
                            width: parent.width
                            height: 42 * root.s
                            fontSize: 13
                            model: [{ label: "LIVE", value: "live" }, { label: "KONFIGURACJA", value: "config" }, { label: "OBIE", value: "both" }]
                            current: root.card ? root.card.visible : "live"
                            onPicked: (v) => Profile.setCardProp(root.selCard, "visible", v)
                        }

                        Caption { text: "ZWIJANIE: „WIĘCEJ” OD KONTROLKI NR (0 = BEZ ZWIJANIA)" }
                        Row {
                            spacing: 8 * root.s
                            FlatButton { text: "−"; width: 44 * root.s; onClicked: Profile.setCardProp(root.selCard, "more", Math.max(0, root.card.more - 1)) }
                            Text {
                                width: 48 * root.s
                                height: 40 * root.s
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                text: root.card ? root.card.more : 0
                                color: Theme.text
                                font.family: Theme.valueFont
                                font.pixelSize: Math.round(16 * root.s)
                            }
                            FlatButton { text: "+"; width: 44 * root.s; onClicked: Profile.setCardProp(root.selCard, "more", root.card.more + 1) }
                        }

                        Caption { text: "KOLOR KARTY" }
                        Swatches {
                            allowAuto: false
                            current: root.card ? root.card.color : "accent"
                            onPicked: (n) => Profile.setCardProp(root.selCard, "color", n)
                        }

                        Caption { text: "PRZEŁĄCZNIK ON/OFF W NAGŁÓWKU (PARAMETR)" }
                        InputField {
                            width: parent.width
                            text: root.card ? root.card.toggle : ""
                            placeholderText: "np. echo.enabled"
                            onCommitted: (t) => Profile.setCardProp(root.selCard, "toggle", t)
                        }

                        Caption { text: "INFORMACJA W NAGŁÓWKU (PARAMETR)" }
                        InputField {
                            width: parent.width
                            text: root.card ? root.card.info : ""
                            placeholderText: "np. echo.sync"
                            onCommitted: (t) => Profile.setCardProp(root.selCard, "info", t)
                        }

                        Flow {
                            width: parent.width
                            spacing: 6 * root.s
                            FlatButton {
                                text: "◀"
                                enabledLook: root.selCard > 0
                                onClicked: { Profile.moveCard(root.selCard, root.selCard - 1); root.host.selectCard(root.selCard - 1) }
                            }
                            FlatButton {
                                text: "▶"
                                enabledLook: root.selCard < Profile.cards.length - 1
                                onClicked: { Profile.moveCard(root.selCard, root.selCard + 1); root.host.selectCard(root.selCard + 1) }
                            }
                            FlatButton { text: "DUPLIKUJ"; onClicked: root.host.selectCard(Profile.duplicateCard(root.selCard)) }
                            FlatButton { text: "USUŃ KARTĘ"; danger: true; onClicked: root.host.removeCard(root.selCard) }
                        }
                    }
                }

                // ---------- PADY ----------
                Column {
                    visible: root.tab === "pads"
                    width: parent.width
                    spacing: 10 * root.s

                    Caption { text: "POŁOŻENIE PASKA PADÓW" }
                    Seg {
                        fill: true
                        width: parent.width
                        height: 42 * root.s
                        model: [{ label: "DÓŁ", value: "bottom" }, { label: "GÓRA", value: "top" }, { label: "UKRYTY", value: "hidden" }]
                        current: Theme.padPosition
                        onPicked: (v) => Profile.setTheme("pads.position", v)
                    }

                    Caption { text: "WYSOKOŚĆ PADÓW" }
                    Row {
                        spacing: 8 * root.s
                        FlatButton { text: "−"; width: 44 * root.s; onClicked: Profile.setTheme("pads.height", Number(Theme.raw("pads.height")) - 8) }
                        Text {
                            width: 64 * root.s
                            height: 40 * root.s
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            text: Theme.raw("pads.height") + " px"
                            color: Theme.text
                            font.family: Theme.valueFont
                            font.pixelSize: Math.round(14 * root.s)
                        }
                        FlatButton { text: "+"; width: 44 * root.s; onClicked: Profile.setTheme("pads.height", Number(Theme.raw("pads.height")) + 8) }
                    }

                    Caption { text: "PADY (KLIKNIJ, ABY ZAZNACZYĆ)" }
                    Repeater {
                        model: Profile.pads
                        delegate: Rectangle {
                            required property int index
                            required property var modelData
                            width: pages.width
                            height: 44 * root.s
                            radius: 6 * root.s
                            color: root.selPad === index ? Theme.raised : "transparent"
                            border.color: root.selPad === index ? Theme.accent : "transparent"
                            MouseArea { anchors.fill: parent; onClicked: root.host.selectPad(index) }
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 6 * root.s
                                spacing: 6 * root.s
                                InputField {
                                    width: pages.width - 4 * 34 * root.s - 40 * root.s
                                    height: 34 * root.s
                                    text: modelData.label
                                    onCommitted: (t) => { if (t !== modelData.label) Profile.setPadLabel(index, t) }
                                }
                                Text {
                                    width: 34 * root.s
                                    height: 34 * root.s
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    text: Profile.shortcutFor(modelData.param) || "—"
                                    color: Theme.muted
                                    font.family: Theme.valueFont
                                    font.pixelSize: Math.round(12 * root.s)
                                }
                                FlatButton { text: "▲"; width: 34 * root.s; height: 34 * root.s; fontSize: 12; onClicked: Profile.movePad(index, index - 1) }
                                FlatButton { text: "▼"; width: 34 * root.s; height: 34 * root.s; fontSize: 12; onClicked: Profile.movePad(index, index + 1) }
                                FlatButton { text: "×"; width: 34 * root.s; height: 34 * root.s; danger: true; onClicked: Profile.removePad(index) }
                            }
                        }
                    }

                    Column {
                        visible: root.pad !== null
                        width: parent.width
                        spacing: 6 * root.s
                        Caption { text: "SKRÓT ZAZNACZONEGO PADU" }
                        KeyField {
                            width: parent.width
                            keyName: root.pad ? Profile.shortcutFor(root.pad.param) : ""
                            onCaptured: (n) => Profile.setShortcut(root.pad.param, n)
                        }
                    }
                }

                // ---------- MOTYW ----------
                Column {
                    visible: root.tab === "theme"
                    width: parent.width
                    spacing: 10 * root.s

                    Caption { text: "SKALA INTERFEJSU: " + Math.round(Theme.scale * 100) + "%" }
                    Slider {
                        id: scaleSlider
                        width: parent.width
                        from: 0.8
                        to: 1.6
                        stepSize: 0.05
                        value: Theme.scale
                        onPressedChanged: if (!pressed) Profile.setTheme("scale", value)
                    }

                    Caption { text: "GĘSTOŚĆ" }
                    Seg {
                        fill: true
                        width: parent.width
                        height: 42 * root.s
                        fontSize: 13
                        model: [{ label: "ZWARTA", value: "compact" }, { label: "NORMALNA", value: "normal" }, { label: "DOTYKOWA", value: "touch" }]
                        current: Theme.density
                        onPicked: (v) => Profile.setTheme("density", v)
                    }

                    Caption { text: "STYL GAŁEK" }
                    Seg {
                        fill: true
                        width: parent.width
                        height: 42 * root.s
                        fontSize: 13
                        model: [{ label: "ŁUK", value: "arc" }, { label: "WSKAZÓWKA", value: "pointer" }, { label: "OBA", value: "both" }]
                        current: Theme.knobStyle
                        onPicked: (v) => Profile.setTheme("knobStyle", v)
                    }

                    Caption { text: "DOPASOWANIE DO OKNA" + (Theme.autoScale ? " (×" + Theme.fit.toFixed(2) + ")" : "") }
                    Seg {
                        fill: true
                        width: parent.width
                        height: 42 * root.s
                        fontSize: 13
                        model: [{ label: "SKALA AUTO", value: true }, { label: "STAŁA", value: false }]
                        current: Theme.autoScale
                        onPicked: (v) => Profile.setTheme("autoScale", v)
                    }
                    Seg {
                        fill: true
                        width: parent.width
                        height: 42 * root.s
                        fontSize: 13
                        model: [{ label: "ROZWIJAJ, GDY JEST MIEJSCE", value: true }, { label: "TYLKO RĘCZNIE", value: false }]
                        current: Theme.autoExpand
                        onPicked: (v) => Profile.setTheme("autoExpand", v)
                    }

                    Caption { text: "RAMKI KONTROLEK (TRYB GRY)" }
                    Seg {
                        fill: true
                        width: parent.width
                        height: 42 * root.s
                        fontSize: 13
                        model: [{ label: "BEZ RAMEK", value: false }, { label: "RAMKI", value: true }]
                        current: Theme.tiles
                        onPicked: (v) => Profile.setTheme("tiles", v)
                    }

                    Caption { text: "MIN. SZEROKOŚĆ KARTY: " + Theme.raw("minCardWidth") + " px" }
                    Slider {
                        width: parent.width
                        from: 180
                        to: 480
                        stepSize: 4
                        value: Number(Theme.raw("minCardWidth"))
                        onPressedChanged: if (!pressed) Profile.setTheme("minCardWidth", value)
                    }

                    Caption { text: "KOLORY (#RRGGBB)" }
                    Repeater {
                        model: [["accent", "Akcent (tor)"], ["fx", "Efekty"], ["kill", "Kill / stop"], ["bg", "Tło"],
                                ["card", "Karty"], ["raised", "Pola"], ["line", "Linie"], ["text", "Tekst"], ["muted", "Podpisy"],
                                ["blue", "Niebieski"], ["cream", "Kremowy"]]
                        delegate: Row {
                            required property var modelData
                            spacing: 8 * root.s
                            Rectangle {
                                width: 28 * root.s
                                height: 28 * root.s
                                radius: 14 * root.s
                                anchors.verticalCenter: parent.verticalCenter
                                color: Theme.color(modelData[0], "accent")
                                border.color: Theme.muted
                            }
                            Text {
                                width: 110 * root.s
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData[1]
                                color: Theme.text
                                font.family: Theme.labelFont
                                font.pixelSize: Math.round(15 * root.s)
                            }
                            InputField {
                                width: pages.width - 28 * root.s - 110 * root.s - 16 * root.s
                                height: 34 * root.s
                                text: Theme.raw("colors." + modelData[0])
                                onCommitted: (t) => Profile.setTheme("colors." + modelData[0], t.trim())
                            }
                        }
                    }

                    Caption { text: "CZCIONKA ETYKIET (teraz: " + Theme.labelFont + ")" }
                    InputField {
                        width: parent.width
                        text: Theme.raw("fonts.label")
                        onCommitted: (t) => Profile.setTheme("fonts.label", t)
                    }
                    Caption { text: "CZCIONKA WARTOŚCI (teraz: " + Theme.valueFont + ")" }
                    InputField {
                        width: parent.width
                        text: Theme.raw("fonts.value")
                        onCommitted: (t) => Profile.setTheme("fonts.value", t)
                    }
                    FlatButton { text: "PRZYWRÓĆ MOTYW DOMYŚLNY"; danger: true; onClicked: Profile.resetTheme() }
                }
            }
        }

        // ---------- wyszukiwarka ----------
        Caption {
            visible: root.tab !== "theme"
            text: root.tab === "pads" ? "DODAJ PAD" : (root.card ? "DODAJ DO KARTY „" + root.card.title + "”" : "DODAJ PARAMETR (ZAZNACZ KARTĘ)")
        }
        InputField {
            id: search
            visible: root.tab !== "theme"
            Layout.fillWidth: true
            placeholderText: "Szukaj: echo, kill, sweep…"
        }
        ListView {
            visible: root.tab !== "theme"
            Layout.fillWidth: true
            Layout.preferredHeight: 180 * root.s
            clip: true
            model: visible ? Params.search(search.text) : []
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width
                height: 34 * root.s
                radius: 6 * root.s
                color: rowArea.containsMouse ? Theme.raised : "transparent"
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: 8 * root.s
                    text: modelData.key
                    color: Theme.text
                    font.family: Theme.valueFont
                    font.pixelSize: Math.round(13 * root.s)
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    anchors.rightMargin: 8 * root.s
                    text: modelData.label
                    color: Theme.muted
                    font.family: Theme.valueFont
                    font.pixelSize: Math.round(12 * root.s)
                }
                MouseArea {
                    id: rowArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        if (root.tab === "pads") {
                            Profile.addPad(modelData.key)
                        } else if (root.selCard >= 0) {
                            const k = Profile.addControl(root.selCard, modelData.key)
                            if (k >= 0) root.host.selectControl(root.selCard, k)
                        }
                    }
                }
            }
        }
    }
}

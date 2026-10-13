// Nagłówek trybu „Edycja układu”: profil, ekran, cofnij/ponów, nowa karta, import/eksport, gotowe.
import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    property var host: null
    readonly property real s: Theme.scale

    color: Qt.tint(Theme.card, "#33E3A52B")
    radius: 12 * s
    border.color: Theme.accent
    implicitHeight: flow.implicitHeight + 20 * s

    Flow {
        id: flow
        x: 12 * root.s
        y: 10 * root.s
        width: root.width - 24 * root.s
        spacing: 10 * root.s

        Text {
            height: 40 * root.s
            verticalAlignment: Text.AlignVCenter
            text: "EDYCJA UKŁADU"
            color: Qt.lighter(Theme.accent, 1.2)
            font.family: Theme.labelFont
            font.weight: Font.Bold
            font.pixelSize: Math.round(20 * root.s)
            font.letterSpacing: 2.8
        }

        FlatButton {
            text: "PROFIL: " + Profile.profileName + " ▾"
            onClicked: profilePopup.open()
            Popup {
                id: profilePopup
                y: parent.height + 6
                width: 340 * root.s
                padding: 6
                background: Rectangle { color: Theme.raised; border.color: Theme.line; radius: 8 * root.s }
                contentItem: Column {
                    spacing: 4
                    Repeater {
                        model: Profile.profiles
                        // gotowe układy (szablony) z opisem i znacznikiem; wybór wczytuje zapisaną kopię lub szablon
                        delegate: Rectangle {
                            required property string modelData
                            readonly property string info: Profile.templateInfo(modelData)
                            width: profilePopup.width - 12
                            height: (info !== "" ? 46 : 34) * root.s
                            radius: 6 * root.s
                            color: ph.containsMouse ? Theme.line : "transparent"
                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 10 * root.s
                                width: parent.width - 20 * root.s - tag.width
                                spacing: 2
                                Text {
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: modelData
                                    color: modelData === Profile.profileName ? Theme.accent : Theme.text
                                    font.family: Theme.valueFont
                                    font.pixelSize: Math.round(13 * root.s)
                                }
                                Text {
                                    visible: text !== ""
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: info
                                    color: Theme.muted
                                    font.family: Theme.valueFont
                                    font.pixelSize: Math.round(10 * root.s)
                                }
                            }
                            Text {
                                id: tag
                                visible: info !== ""
                                anchors.right: parent.right
                                anchors.rightMargin: 8 * root.s
                                anchors.verticalCenter: parent.verticalCenter
                                text: "SZABLON"
                                color: Theme.fx
                                font.family: Theme.labelFont
                                font.weight: Font.DemiBold
                                font.pixelSize: Math.round(10 * root.s)
                                font.letterSpacing: 1
                            }
                            MouseArea {
                                id: ph
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: { Profile.switchProfile(modelData); profilePopup.close() }
                            }
                        }
                    }
                    Rectangle { width: profilePopup.width - 12; height: 1; color: Theme.line }
                    Row {
                        spacing: 6
                        TextField {
                            id: newName
                            width: profilePopup.width - 12 - saveAs.width - 6
                            height: 36 * root.s
                            placeholderText: "Nowa nazwa…"
                            color: Theme.text
                            placeholderTextColor: Theme.muted
                            font.family: Theme.valueFont
                            font.pixelSize: Math.round(13 * root.s)
                            background: Rectangle { color: Theme.card; radius: 6; border.color: Theme.line }
                            onAccepted: saveAs.clicked()
                        }
                        FlatButton {
                            id: saveAs
                            text: "ZAPISZ JAKO"
                            height: 36 * root.s
                            fontSize: 13
                            onClicked: { if (Profile.saveAs(newName.text)) { newName.text = ""; profilePopup.close() } }
                        }
                    }
                    // wbudowanego układu nie da się usunąć – RESET przywraca jego szablon
                    Text {
                        visible: Profile.isTemplate
                        width: profilePopup.width - 12
                        wrapMode: Text.WordWrap
                        text: "Gotowy układ – zmiany zapisują się w nim, RESET przywraca szablon."
                        color: Theme.muted
                        font.family: Theme.valueFont
                        font.pixelSize: Math.round(11 * root.s)
                    }
                    FlatButton {
                        visible: !Profile.isTemplate
                        width: profilePopup.width - 12
                        height: 34 * root.s
                        fontSize: 13
                        danger: true
                        text: "USUŃ PROFIL „" + Profile.profileName + "”"
                        onClicked: { Profile.deleteProfile(); profilePopup.close() }
                    }
                }
            }
        }

        Seg {
            height: 40 * root.s
            fontSize: 14
            model: [{ label: "LIVE", value: "live" }, { label: "KONFIGURACJA", value: "config" }]
            current: Session.screen
            onPicked: (v) => Session.screen = v
        }

        FlatButton { text: "COFNIJ"; enabledLook: Profile.canUndo; onClicked: Profile.undo() }
        FlatButton { text: "PONÓW"; enabledLook: Profile.canRedo; onClicked: Profile.redo() }
        FlatButton {
            text: "+ KARTA"
            onClicked: root.host.selectCard(Profile.addCard("", Session.screen === "config" ? "config" : "live"))
        }
        FlatButton { text: "IMPORT"; onClicked: Session.request("layout_import") }
        FlatButton { text: "EKSPORT"; onClicked: Session.request("layout_export") }
        FlatButton { text: "RESET"; danger: true; onClicked: Profile.resetProfile() }
        FlatButton {
            text: "GOTOWE"
            primary: true
            onClicked: { Profile.save(); Session.editing = false }
        }

        Text {
            width: flow.width
            wrapMode: Text.WordWrap
            text: "⋮⋮ przeciągnij kartę · prawa krawędź = szerokość, dolna = wysokość (dwuklik: auto) · ⋯ lub prawy przycisk = menu · "
                  + "uchwyt S/M/L zaznaczonej kontrolki · ←→ przesuń · Shift+←→ szerokość, Shift+↑↓ wysokość karty · +/− rozmiar kontrolki · "
                  + "Del usuń · Ctrl+Z/Y cofnij/ponów · Ctrl+D duplikuj · Esc"
            color: Theme.muted
            font.family: Theme.valueFont
            font.pixelSize: Math.round(11 * root.s)
        }
    }
}

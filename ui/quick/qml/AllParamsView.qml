// Wszystkie parametry toru (KONFIGURACJA): moduł do wyboru albo wyszukiwanie po nazwie lub kluczu.
// Lista pochodzi wprost z ParamStore, więc obejmuje także parametry, których nie ma w układzie.
// Wybór modułu i tekst wyszukiwania trzyma Main.qml (`host`), bo karty są przebudowywane.
import QtQuick

Column {
    id: root
    property var host: null
    property bool interactive: true

    readonly property real s: Theme.scale
    readonly property var groups: Params.groups()
    property string localGroup: groups.length ? groups[0].key : ""
    property string localFilter: ""
    readonly property string group: host && host.allGroup !== "" ? host.allGroup : localGroup
    readonly property string filter: host ? host.allFilter : localFilter
    readonly property var keys: Params.paramKeys(filter.trim() !== "" ? "" : group, filter)
    readonly property bool searching: filter.trim() !== ""

    function pick(g) { if (host) host.allGroup = g; else localGroup = g }
    function search(t) { if (host) host.allFilter = t; else localFilter = t }
    function groupColor(key) {
        const g = key.split(".")[0]
        for (let i = 0; i < groups.length; i++)
            if (groups[i].key === g) return Theme.color(groups[i].color, "accent")
        return Theme.accent
    }
    function groupTitle(key) {
        const g = key.split(".")[0]
        for (let i = 0; i < groups.length; i++)
            if (groups[i].key === g) return groups[i].title
        return g.toUpperCase()
    }

    spacing: 10 * s

    Row {
        width: root.width
        spacing: 8 * root.s
        InputField {
            id: field
            width: Math.min(root.width - clear.width - 8 * root.s, 380 * root.s)
            placeholderText: "Szukaj parametru (nazwa lub klucz)…"
            text: root.filter
            enabled: root.interactive
            onTextEdited: root.search(text)
        }
        FlatButton {
            id: clear
            text: "WYCZYŚĆ"
            enabledLook: root.interactive && root.searching
            implicitHeight: field.height
            onClicked: if (root.interactive) root.search("")
        }
    }

    Flow {
        width: root.width
        spacing: 6 * root.s
        visible: !root.searching
        Repeater {
            model: root.groups
            delegate: FlatButton {
                required property var modelData
                text: modelData.title + " · " + modelData.count
                checked: modelData.key === root.group
                fontSize: 13
                implicitHeight: 34 * root.s
                onClicked: if (root.interactive) root.pick(modelData.key)
            }
        }
    }

    Text {
        visible: root.searching
        width: root.width
        wrapMode: Text.WordWrap
        text: root.keys.length ? "Znaleziono: " + root.keys.length
                               : "Brak parametrów pasujących do „" + root.filter.trim() + "”."
        color: Theme.muted
        font.family: Theme.labelFont
        font.pixelSize: Math.round(13 * root.s)
    }

    Flow {
        width: root.width
        spacing: 14 * root.s
        Repeater {
            model: root.keys
            delegate: Item {
                id: cell
                required property string modelData
                readonly property var p: Params.get(modelData)
                readonly property string kind: p ? p.kind : ""
                readonly property bool killish: /kill|mute|cut|panic/.test(modelData)
                readonly property color tint: kind === "bool" && killish ? Theme.kill : root.groupColor(modelData)
                // przy wyszukiwaniu etykieta mówi też, z którego modułu jest parametr
                readonly property string label: p ? (root.searching ? root.groupTitle(modelData) + " · " + p.label : p.label) : modelData
                width: kind === "choice" ? 160 * root.s : Math.max((kind === "bool" ? 96 : 86) * root.s, loader.implicitWidth)
                height: loader.item ? loader.item.implicitHeight : 0
                Loader {
                    id: loader
                    width: cell.width
                    sourceComponent: cell.kind === "bool" ? buttonC : cell.kind === "choice" ? valueC : cell.kind !== "" ? knobC : null
                }
                Component {
                    id: knobC
                    Knob {
                        param: cell.p
                        label: cell.label
                        color: cell.tint
                        dial: 52 * root.s
                        interactive: root.interactive
                    }
                }
                Component {
                    id: valueC
                    ValueSelect {
                        param: cell.p
                        label: cell.label
                        color: cell.tint
                        interactive: root.interactive
                    }
                }
                Component {
                    id: buttonC
                    ParamButton {
                        target: cell.modelData
                        text: cell.label.toUpperCase()
                        activeColor: cell.tint
                        interactive: root.interactive
                        implicitHeight: 40 * root.s
                    }
                }
            }
        }
    }
}

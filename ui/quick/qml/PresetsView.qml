// Presety (EQ 12 pasm lub brzmienia syreny) w jednym rzędzie: lista (wybór od razu stosowany),
// ＋ zapis bieżących ustawień (pokazuje pole nazwy), × usunięcie własnego, ↺ reset do wartości domyślnych.
// Polecenia do okna: <kind>_apply / _save / _delete / _reset.
import QtQuick

Column {
    id: root
    property string kind: "eq"   // "eq" | "siren"
    property bool interactive: true
    property string selected: ""
    property bool saving: false
    readonly property real s: Theme.scale
    readonly property real gap: 6 * s
    readonly property real btn: 34 * s
    readonly property var presets: kind === "siren" ? Session.sirenPresets : Session.eqPresets
    readonly property var selectedItem: {
        const list = presets
        for (let i = 0; i < list.length; i++) if (list[i].value === selected) return list[i]
        return null
    }
    spacing: gap

    function save() {
        const name = nameField.text.trim()
        if (name === "") return
        Session.requestWith(kind + "_save", name)
        selected = name
        nameField.text = ""
        saving = false
    }

    Row {
        spacing: root.gap
        Choice {
            width: Math.max(80 * root.s, root.width - 3 * (root.btn + root.gap))
            model: root.presets
            current: root.selected
            placeholder: root.kind === "siren" ? "Brzmienie…" : "Preset EQ…"
            interactive: root.interactive
            onPicked: (v) => { root.selected = v; Session.requestWith(root.kind + "_apply", v) }
        }
        FlatButton {
            width: root.btn
            text: "+"
            fontSize: 20
            checked: root.saving
            enabledLook: root.interactive
            onClicked: {
                root.saving = !root.saving
                if (root.saving) nameField.forceActiveFocus()
            }
        }
        FlatButton {
            width: root.btn
            text: "×"
            fontSize: 20
            danger: true
            enabledLook: root.interactive && root.selectedItem !== null && !root.selectedItem.builtin
            onClicked: { Session.requestWith(root.kind + "_delete", root.selected); root.selected = "" }
        }
        FlatButton {
            width: root.btn
            text: "↺"
            fontSize: 18
            enabledLook: root.interactive
            onClicked: { Session.request(root.kind + "_reset"); root.selected = "" }
        }
    }
    Row {
        visible: root.saving
        spacing: root.gap
        InputField {
            id: nameField
            width: root.width - saveBtn.width - root.gap
            placeholderText: root.kind === "siren" ? "Nazwa brzmienia" : "Nazwa presetu EQ"
            enabled: root.interactive
            onAccepted: root.save()
        }
        FlatButton {
            id: saveBtn
            text: "ZAPISZ"
            primary: nameField.text.trim() !== ""
            enabledLook: root.interactive && nameField.text.trim() !== ""
            onClicked: root.save()
        }
    }
}

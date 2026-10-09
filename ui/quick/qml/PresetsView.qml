// Presety 12-pasmowego EQ: wybór (od razu stosowany), zapis bieżących ustawień, usuwanie własnych, reset.
import QtQuick

Column {
    id: root
    property bool interactive: true
    property string selected: ""
    readonly property real s: Theme.scale
    readonly property var selectedItem: {
        const list = Session.eqPresets
        for (let i = 0; i < list.length; i++) if (list[i].value === selected) return list[i]
        return null
    }
    spacing: 8 * s

    Flow {
        width: root.width
        spacing: 8 * root.s
        Choice {
            width: Math.min(root.width, 240 * root.s)
            model: Session.eqPresets
            current: root.selected
            placeholder: "Preset EQ…"
            interactive: root.interactive
            onPicked: (v) => { root.selected = v; Session.requestWith("eq_apply", v) }
        }
        FlatButton {
            text: "USUŃ"
            danger: true
            enabledLook: root.interactive && root.selectedItem !== null && !root.selectedItem.builtin
            onClicked: { Session.requestWith("eq_delete", root.selected); root.selected = "" }
        }
        FlatButton {
            text: "RESET"
            enabledLook: root.interactive
            onClicked: { Session.request("eq_reset"); root.selected = "" }
        }
    }
    Row {
        spacing: 8 * root.s
        InputField {
            id: nameField
            width: Math.min(root.width - saveBtn.width - 8 * root.s, 240 * root.s)
            placeholderText: "Nazwa nowego presetu"
            enabled: root.interactive
            onAccepted: saveBtn.clicked()
        }
        FlatButton {
            id: saveBtn
            text: "ZAPISZ"
            enabledLook: root.interactive && nameField.text.trim() !== ""
            onClicked: {
                Session.requestWith("eq_save", nameField.text.trim())
                root.selected = nameField.text.trim()
                nameField.text = ""
            }
        }
    }
}

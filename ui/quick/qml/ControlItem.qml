// Jedna kontrolka z profilu układu: wybiera komponent wg typu; w trybie edycji – zaznaczanie,
// przeciąganie (także do innej karty) i zmiana rozmiaru S/M/L uchwytem w rogu.
import QtQuick

Item {
    id: root
    property var ctl: ({})
    property int ci: -1
    property int k: -1
    property var host: null
    property color cardColor: Theme.accent
    property bool editing: false
    property bool selected: false
    property bool dropTarget: false
    property bool dropAfter: false

    readonly property real s: Theme.scale
    readonly property string target: ctl.param || ""
    readonly property string type: ctl.type || "knob"
    readonly property string size: ctl.size || "M"
    readonly property var param: Params.get(target)
    readonly property string label: ctl.label || Params.labelOf(target)
    readonly property color tint: ctl.color && ctl.color !== "auto" ? Theme.color(ctl.color, "accent") : cardColor
    readonly property var sizes: ["S", "M", "L"]
    property string previewSize: ""

    implicitHeight: loader.item ? loader.item.implicitHeight : 40 * s

    // ramka kontrolki w trybie gry (motyw → „Ramki kontrolek”)
    Rectangle {
        visible: Theme.tiles && !root.editing
        anchors.fill: parent
        anchors.margins: -4 * root.s
        radius: 8 * root.s
        color: Qt.darker(Theme.raised, 1.08)
        border.color: Theme.line
    }

    Loader {
        id: loader
        width: root.width
        sourceComponent: {
            switch (root.target) {
            case "view:meters": return metersC
            case "view:mic_meter": return micC
            case "view:siren_memories": return memC
            case "view:response":
            case "view:crossover":
            case "view:spectrum": return plotC
            case "view:devices": return devicesC
            case "view:room_ir": return irC
            case "view:eq_presets": return eqC
            case "view:siren_presets": return sirenPresetsC
            }
            switch (root.type) {
            case "fader": return faderC
            case "button": return buttonC
            case "pad": return padC
            case "value": return valueC
            default: return knobC
            }
        }
    }

    Component {
        id: knobC
        Knob {
            param: root.param
            label: root.label
            color: root.tint
            dial: ({ S: 52, M: 60, L: 72 })[root.size] * root.s
            interactive: !root.editing
        }
    }
    Component {
        id: faderC
        Fader {
            param: root.param
            killParam: root.ctl.kill ? Params.get(root.ctl.kill) : null
            label: root.label
            color: root.tint
            track: ({ S: 110, M: 150, L: 190 })[root.size] * root.s
            interactive: !root.editing
        }
    }
    Component {
        id: buttonC
        ParamButton {
            target: root.target
            text: root.label.toUpperCase()
            activeColor: root.tint
            interactive: !root.editing
            implicitHeight: (root.size === "L" ? 52 : 40) * root.s
        }
    }
    Component {
        id: padC
        ParamButton {
            target: root.target
            text: root.label.toUpperCase()
            keyHint: Profile.shortcutFor(root.target)
            activeColor: root.tint
            big: true
            interactive: !root.editing
        }
    }
    Component {
        id: valueC
        ValueSelect {
            param: root.param
            label: root.label
            color: root.tint
            interactive: !root.editing
        }
    }
    Component {
        id: metersC
        MetersView { barHeight: ({ S: 80, M: 100, L: 120 })[root.size] * root.s }
    }
    Component {
        id: micC
        MicMeter {}
    }
    Component {
        id: memC
        SirenMemories { interactive: !root.editing }
    }
    Component {
        id: plotC
        PlotView {
            kind: root.target.slice(5)
            plotHeight: ({ S: 110, M: 160, L: 240 })[root.size] * root.s
        }
    }
    Component {
        id: devicesC
        DevicesView { interactive: !root.editing }
    }
    Component {
        id: irC
        RoomIrView { interactive: !root.editing }
    }
    Component {
        id: eqC
        PresetsView { kind: "eq"; interactive: !root.editing }
    }
    Component {
        id: sirenPresetsC
        PresetsView { kind: "siren"; interactive: !root.editing }
    }

    // --- tryb edycji ---
    Rectangle {
        visible: root.editing
        anchors.fill: parent
        anchors.margins: -4 * root.s
        radius: 8 * root.s
        color: root.selected ? Qt.rgba(0.89, 0.65, 0.17, 0.13) : "transparent"
        border.width: root.selected ? 2 : 1
        border.color: root.selected ? Theme.accent : Qt.lighter(Theme.line, 1.3)
    }

    // wskaźnik miejsca wstawienia przy przeciąganiu
    Rectangle {
        visible: root.editing && root.dropTarget
        z: 5
        width: 4 * root.s
        radius: width / 2
        height: root.height + 8 * root.s
        y: -4 * root.s
        x: root.dropAfter ? root.width + 2 * root.s : -6 * root.s
        color: Theme.fx
    }

    MouseArea {
        anchors.fill: parent
        anchors.margins: -4 * root.s
        visible: root.editing
        enabled: root.editing
        preventStealing: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: dragging ? Qt.ClosedHandCursor : Qt.PointingHandCursor
        property point start
        property bool dragging: false
        onPressed: (m) => {
            start = Qt.point(m.x, m.y)
            dragging = false
            root.host.selectControl(root.ci, root.k)
        }
        onPositionChanged: (m) => {
            if (!dragging && Math.abs(m.x - start.x) + Math.abs(m.y - start.y) > 8) {
                dragging = true
                root.host.beginDrag({ kind: "control", ci: root.ci, k: root.k, label: root.label })
            }
            if (dragging) root.host.moveDrag(this, m.x, m.y)
        }
        onReleased: { if (dragging) root.host.endDrag(); dragging = false }
        onCanceled: { if (dragging) root.host.cancelDrag(); dragging = false }
    }

    // uchwyt rozmiaru S/M/L (zaznaczona kontrolka)
    Rectangle {
        visible: root.editing && root.selected && !root.target.startsWith("view:devices")
        z: 6
        width: 18 * root.s
        height: width
        radius: 4 * root.s
        x: root.width - width / 2
        y: root.height - height / 2
        color: Theme.accent
        Text {
            anchors.centerIn: parent
            text: root.previewSize !== "" ? root.previewSize : root.size
            color: Theme.bg
            font.family: Theme.labelFont
            font.weight: Font.Bold
            font.pixelSize: Math.round(11 * root.s)
        }
        MouseArea {
            anchors.fill: parent
            anchors.margins: -4
            preventStealing: true
            cursorShape: Qt.SizeFDiagCursor
            property point start
            onPressed: (m) => { start = mapToItem(root, m.x, m.y) }
            onPositionChanged: (m) => {
                const p = mapToItem(root, m.x, m.y)
                const steps = Math.round((p.x - start.x + p.y - start.y) / (36 * root.s))
                const i = Math.max(0, Math.min(2, root.sizes.indexOf(root.size) + steps))
                root.previewSize = root.sizes[i]
            }
            onReleased: {
                if (root.previewSize !== "" && root.previewSize !== root.size)
                    Profile.setControlProp(root.ci, root.k, "size", root.previewSize)
                root.previewSize = ""
            }
            onCanceled: root.previewSize = ""
        }
    }
}

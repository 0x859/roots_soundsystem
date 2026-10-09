// Karta stołu: nagłówek (tytuł, informacja, przełącznik ON), kontrolki w rzędach, zwijanie.
// W trybie edycji: uchwyt ⋮⋮ (przenoszenie), krawędzie (szerokość/wysokość), menu ⋯, usuwanie.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: card
    property var cardData: ({})
    property int ci: -1
    property var host: null
    property bool editing: false
    property bool selected: false
    property bool dropTarget: false
    property bool dropAfter: false
    property int dropK: -1
    property bool dropKAfter: false
    property int selK: -1
    property bool expanded: false

    readonly property real s: Theme.scale
    readonly property real pad: 14 * s
    readonly property real gap: Math.max(6, Theme.spacing - 2)
    readonly property real inner: width - 2 * pad
    readonly property color tint: Theme.color(cardData.color || "accent", "accent")
    readonly property var controls: cardData.controls || []
    readonly property int more: cardData.more || 0
    readonly property int fixedCols: cardData.cols || 0
    readonly property bool collapsible: more > 0 && more < controls.length
    readonly property bool collapsed: !editing && cardData.collapsed === true
    readonly property int shown: collapsed ? 0 : (editing || expanded || !collapsible ? controls.length : more)
    readonly property var toggleParam: cardData.toggle ? Params.get(cardData.toggle) : null
    readonly property var infoParam: cardData.info ? Params.get(cardData.info) : null
    // stała wysokość (px przy skali 100%); 0 = dopasowana do zawartości
    readonly property real fixedH: collapsed ? 0 : (cardData.height || 0) * s

    color: Theme.card
    radius: 12 * s
    border.width: selected ? 2 : 1
    border.color: selected ? Theme.accent : (editing ? Qt.lighter(Theme.line, 1.4) : Theme.line)
    implicitHeight: fixedH > 0 ? fixedH : col.implicitHeight + 2 * pad

    function cell(ctl) {
        const t = ctl.type, z = ctl.size
        if ((ctl.param || "").indexOf("view:") === 0) return -1
        if (t === "knob") return ({ S: 68, M: 80, L: 96 })[z]
        if (t === "fader") return ({ S: 30, M: 34, L: 44 })[z]
        if (z === "L") return -1
        if (t === "button") return ({ S: 64, M: 96 })[z]
        return ({ S: 60, M: 96 })[z]
    }

    // kolejne kontrolki o tej samej szerokości komórki tworzą rząd (duże gałki, małe gałki…);
    // przy stałej liczbie kolumn wszystkie (poza pełnej szerokości) tworzą jedną siatkę
    readonly property var groups: {
        const out = []
        let prev = null
        for (let i = 0; i < shown; i++) {
            const c = cell(controls[i])
            const key = c < 0 ? -1 : (fixedCols > 0 ? 0 : c)
            if (out.length === 0 || key !== prev || key < 0) out.push([])
            out[out.length - 1].push(i)
            prev = key
        }
        return out
    }
    property var registry: ({})

    function widthFor(ctl, groupSize) {
        const c = cell(ctl)
        if (c < 0) return inner
        let n
        if (fixedCols > 0) {
            n = fixedCols
        } else {
            const fit = Math.max(1, Math.floor((inner + gap) / (c * s + gap)))
            n = Math.max(1, Math.min(fit, groupSize || fit))
        }
        return Math.floor((inner - gap * (n - 1)) / n)
    }

    // kontrolka pod kursorem: { k, after } (k = -1: brak, wtedy na koniec)
    function controlAt(item, x, y) {
        for (let i = 0; i < shown; i++) {
            const it = registry[i]
            if (!it) continue
            const p = it.mapFromItem(item, x, y)
            if (p.x >= -gap / 2 && p.y >= -gap / 2 && p.x < it.width + gap / 2 && p.y < it.height + gap / 2)
                return { k: i, after: p.x > it.width / 2 }
        }
        return { k: -1, after: true }
    }

    MouseArea {
        anchors.fill: parent
        enabled: card.editing
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: (m) => {
            card.host.selectCard(card.ci)
            if (m.button === Qt.RightButton) card.host.openCardMenu(card.ci, card)
        }
    }

    // wskaźnik miejsca wstawienia karty
    Rectangle {
        visible: card.editing && card.dropTarget
        z: 5
        width: 5 * card.s
        radius: width / 2
        height: card.height
        x: card.dropAfter ? card.width + (card.host ? card.host.gap / 2 : 6) - width / 2 : -(card.host ? card.host.gap / 2 : 6) - width / 2
        color: Theme.fx
    }

    // treść przewija się, gdy karta ma ustawioną mniejszą wysokość niż potrzeba
    Flickable {
        id: body
        anchors.fill: parent
        contentWidth: width
        contentHeight: col.implicitHeight + 2 * card.pad
        interactive: contentHeight > height + 1
        clip: interactive
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: body.interactive ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }

    Column {
        id: col
        x: card.pad
        y: card.pad
        width: card.inner
        spacing: 14 * card.s

        RowLayout {
            id: header
            width: parent.width
            spacing: 8 * card.s

            Text {
                visible: card.editing
                text: "⋮⋮"
                color: Theme.muted
                font.family: Theme.valueFont
                font.weight: Font.Bold
                font.pixelSize: Math.round(16 * card.s)
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -8 * card.s
                    preventStealing: true
                    cursorShape: dragging ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    property point start
                    property bool dragging: false
                    onPressed: (m) => { start = Qt.point(m.x, m.y); dragging = false; card.host.selectCard(card.ci) }
                    onPositionChanged: (m) => {
                        if (!dragging && Math.abs(m.x - start.x) + Math.abs(m.y - start.y) > 8) {
                            dragging = true
                            card.host.beginDrag({ kind: "card", ci: card.ci, k: -1, label: card.cardData.title })
                        }
                        if (dragging) card.host.moveDrag(this, m.x, m.y)
                    }
                    onReleased: { if (dragging) card.host.endDrag(); dragging = false }
                    onCanceled: { if (dragging) card.host.cancelDrag(); dragging = false }
                }
            }

            Text {
                id: titleText
                Layout.fillWidth: true
                Layout.minimumWidth: card.editing ? 30 * card.s : Math.min(implicitWidth, card.inner * 0.6)
                text: card.cardData.title || ""
                color: Theme.text
                elide: Text.ElideRight
                font.family: Theme.labelFont
                font.weight: Font.Bold
                font.pixelSize: Math.round(18 * card.s)
                font.letterSpacing: 2.4
                MouseArea {
                    id: titleArea
                    anchors.fill: parent
                    enabled: !card.editing
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: card.host.toggleCollapsed(card.ci)
                }
                Text {
                    visible: !card.editing && (titleArea.containsMouse || card.collapsed)
                    x: Math.min(titleText.implicitWidth, titleText.width) + 6 * card.s
                    anchors.verticalCenter: parent.verticalCenter
                    text: card.collapsed ? "▸" : "▾"
                    color: Theme.muted
                    font.pixelSize: Math.round(14 * card.s)
                }
            }

            Text {
                visible: card.infoParam !== null && !card.editing
                Layout.fillWidth: true
                Layout.maximumWidth: implicitWidth
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
                text: card.infoParam ? card.infoParam.text : ""
                color: card.tint
                font.family: Theme.valueFont
                font.pixelSize: Math.round(12 * card.s)
            }

            Rectangle {
                visible: card.toggleParam !== null && !card.editing
                implicitWidth: chip.implicitWidth + 12 * card.s
                implicitHeight: chip.implicitHeight + 8 * card.s
                radius: 4 * card.s
                color: card.toggleParam && card.toggleParam.on ? card.tint : "transparent"
                border.color: card.toggleParam && card.toggleParam.on ? card.tint : Qt.lighter(Theme.line, 1.3)
                Text {
                    id: chip
                    anchors.centerIn: parent
                    text: card.toggleParam && card.toggleParam.on ? "ON" : "OFF"
                    color: card.toggleParam && card.toggleParam.on ? Theme.bg : Theme.muted
                    font.family: Theme.valueFont
                    font.weight: Font.Medium
                    font.pixelSize: Math.round(11 * card.s)
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: !card.editing
                    onClicked: card.toggleParam.toggle()
                }
            }

            Repeater {
                model: card.editing ? [["⋯", "menu"], ["×", "remove"]] : []
                delegate: Rectangle {
                    required property var modelData
                    implicitWidth: 26 * card.s
                    implicitHeight: 26 * card.s
                    radius: 6 * card.s
                    color: hb.containsMouse ? Theme.raised : "transparent"
                    border.color: modelData[1] === "remove" && hb.containsMouse ? Theme.kill : Qt.lighter(Theme.line, 1.3)
                    Text {
                        anchors.centerIn: parent
                        text: modelData[0]
                        color: Theme.text
                        font.pixelSize: Math.round(17 * card.s)
                    }
                    MouseArea {
                        id: hb
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            if (modelData[1] === "menu") { card.host.selectCard(card.ci); card.host.openCardMenu(card.ci, card) }
                            else card.host.removeCard(card.ci)
                        }
                    }
                }
            }
        }

        Repeater {
            model: card.groups
            delegate: Flow {
                id: groupFlow
                required property var modelData
                readonly property var members: modelData
                width: col.width
                spacing: card.gap

                Repeater {
                    model: groupFlow.members
                    delegate: ControlItem {
                        required property int modelData
                        ctl: card.controls[modelData]
                        ci: card.ci
                        k: modelData
                        host: card.host
                        width: card.widthFor(ctl, groupFlow.members.length)
                        cardColor: card.tint
                        editing: card.editing
                        selected: card.selected && card.selK === modelData
                        dropTarget: card.dropK === modelData
                        dropAfter: card.dropKAfter
                        Component.onCompleted: card.registry[modelData] = this
                        Component.onDestruction: if (card.registry[modelData] === this) delete card.registry[modelData]
                    }
                }
            }
        }

        Rectangle {
            visible: card.editing
            width: card.widthFor({ param: "", type: "button", size: "M" }, 1)
            height: 44 * card.s
            radius: 8 * card.s
            color: "transparent"
            border.color: Qt.darker(Theme.accent, 1.8)
            Text {
                anchors.centerIn: parent
                text: "+ DODAJ"
                color: Theme.accent
                font.family: Theme.labelFont
                font.weight: Font.DemiBold
                font.pixelSize: Math.round(14 * card.s)
            }
            MouseArea {
                anchors.fill: parent
                onClicked: card.host.addTo(card.ci)
            }
        }

        Rectangle {
            visible: card.collapsible && !card.editing && !card.collapsed
            width: parent.width
            height: 34 * card.s
            radius: 6 * card.s
            color: "transparent"
            border.color: Qt.lighter(Theme.line, 1.25)
            Text {
                anchors.centerIn: parent
                text: card.expanded ? "MNIEJ" : "WIĘCEJ · " + (card.controls.length - card.more)
                color: Theme.muted
                font.family: Theme.labelFont
                font.weight: Font.DemiBold
                font.pixelSize: Math.round(14 * card.s)
                font.letterSpacing: 1
            }
            MouseArea {
                anchors.fill: parent
                onClicked: card.host.toggleExpanded(card.cardData.id)
            }
        }
    }
    }

    // rozmiar karty w siatce (tryb edycji)
    Rectangle {
        visible: card.editing
        z: 3
        x: 10 * card.s
        y: card.height - height / 2
        width: sizeBadge.implicitWidth + 12 * card.s
        height: sizeBadge.implicitHeight + 4 * card.s
        radius: 4 * card.s
        color: Theme.raised
        border.color: card.selected ? Theme.accent : Theme.line
        Text {
            id: sizeBadge
            anchors.centerIn: parent
            text: Math.min(card.cardData.span, card.host ? card.host.columns : 4) + " × " + card.cardData.rows
                  + (card.cardData.height > 0 ? " · " + card.cardData.height + " px" : "")
                  + (card.cardData.visible === "both" ? " · LIVE+KONF" : "")
            color: Theme.muted
            font.family: Theme.valueFont
            font.pixelSize: Math.round(11 * card.s)
        }
    }

    // --- uchwyty rozmiaru (tryb edycji): prawa krawędź = kolumny, dolna = rzędy, róg = oba ---
    Repeater {
        model: card.editing ? ["w", "h", "wh"] : []
        delegate: Rectangle {
            required property string modelData
            readonly property real t: 10 * card.s
            z: 4
            x: modelData === "h" ? card.radius : card.width - t / 2 - (modelData === "wh" ? t / 2 : 0)
            y: modelData === "w" ? card.radius : card.height - t / 2 - (modelData === "wh" ? t / 2 : 0)
            width: modelData === "h" ? card.width - 2 * card.radius - 2 * t : (modelData === "wh" ? 2 * t : t)
            height: modelData === "w" ? card.height - 2 * card.radius - 2 * t : (modelData === "wh" ? 2 * t : t)
            radius: t / 2
            color: modelData === "wh" ? Theme.accent : (ra.containsMouse || ra.pressed ? Qt.rgba(0.89, 0.65, 0.17, 0.55) : "transparent")
            opacity: modelData === "wh" && !(ra.containsMouse || card.selected) ? 0.55 : 1
            MouseArea {
                id: ra
                anchors.fill: parent
                hoverEnabled: true
                preventStealing: true
                cursorShape: modelData === "w" ? Qt.SizeHorCursor : modelData === "h" ? Qt.SizeVerCursor : Qt.SizeFDiagCursor
                onPressed: card.host.beginResize(card.ci, modelData, card)
                onDoubleClicked: if (modelData !== "w") card.host.autoHeight(card.ci)
                onPositionChanged: (m) => { if (pressed) card.host.moveResize(this, m.x, m.y) }
                onReleased: card.host.endResize()
                onCanceled: card.host.cancelResize()
            }
        }
    }
}

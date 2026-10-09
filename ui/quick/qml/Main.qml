// Ekran główny: nagłówek, siatka kart (kolumny z szerokości okna), pasek padów, tryb edycji układu.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    color: Theme.bg
    focus: true

    readonly property real s: Theme.scale
    readonly property int gap: Theme.spacing
    readonly property bool editing: Session.editing
    property int selCard: -1
    property int selCtl: -1
    property int selPad: -1
    property var expanded: ({})
    // przeciąganie: dragInfo = {kind, ci, k, label}; cel = karta dropCi (przed/po) lub kontrolka dropK
    property var dragInfo: null
    property int dropCi: -1
    property bool dropAfter: false
    property int dropK: -1
    property bool dropKAfter: false
    property bool dropEnd: false
    // zmiana rozmiaru karty: {ci, mode, card, span, startSpan, rows, height, startHeight}
    property var rs: null
    property real inspW: Theme.inspectorWidth

    readonly property int columns: Math.max(1, Math.floor((grid.width + gap) / (Theme.minCardWidth + gap)))
    readonly property real colW: (grid.width - gap * (columns - 1)) / columns

    function cardShown(card) {
        return card.visible === "both" || card.visible === Session.screen
    }
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }
    function cardItem(ci) { return cardRep.itemAt(ci) }

    // --- interfejs dla kart, kontrolek i inspektora (host) ---
    function selectCard(ci) {
        selCard = ci
        selCtl = -1
        inspector.tab = "card"
        root.forceActiveFocus()
    }
    function selectControl(ci, k) {
        selCard = ci
        selCtl = k
        inspector.tab = "control"
        root.forceActiveFocus()
    }
    function selectPad(i) {
        selPad = i
        inspector.tab = "pads"
    }
    function addTo(ci) {
        selCard = ci
        selCtl = -1
        inspector.tab = "control"
        inspector.focusSearch()
    }
    function removeCard(ci) {
        Profile.removeCard(ci)
        selCard = -1
        selCtl = -1
    }
    function toggleExpanded(id) {
        const e = Object.assign({}, expanded)
        e[id] = !e[id]
        expanded = e
    }
    function toggleCollapsed(ci) {
        Profile.setCardState(ci, "collapsed", !Profile.cards[ci].collapsed)
    }
    function openCardMenu(ci, item) {
        cardMenu.ci = ci
        const p = item.mapToItem(root, item.width - cardMenu.width - 8, 52 * s)
        cardMenu.x = clamp(p.x, 8, root.width - cardMenu.width - 8)
        cardMenu.y = clamp(p.y, 8, Math.max(8, root.height - cardMenu.implicitHeight - 8))
        cardMenu.open()
    }

    // przeciąganie kart i kontrolek
    function beginDrag(info) {
        dragInfo = info
        ghostLabel.text = info.label
    }
    function moveDrag(item, x, y) {
        const p = item.mapToItem(root, x, y)
        ghost.x = p.x + 12
        ghost.y = p.y + 12
        const g = item.mapToItem(grid, x, y)
        dropCi = -1
        dropK = -1
        dropEnd = false
        for (let i = 0; i < cardRep.count; i++) {
            const c = cardRep.itemAt(i)
            if (c && c.visible && g.x >= c.x - gap / 2 && g.x < c.x + c.width + gap / 2 && g.y >= c.y && g.y < c.y + c.height) {
                dropCi = i
                dropAfter = g.x > c.x + c.width / 2
                if (dragInfo.kind === "control") {
                    const hit = c.controlAt(item, x, y)
                    dropK = hit.k
                    dropKAfter = hit.after
                }
                break
            }
        }
        if (dropCi < 0 && dragInfo.kind === "card") {
            const e = item.mapToItem(endZone, x, y)
            dropEnd = e.x >= 0 && e.y >= -gap && e.x < endZone.width && e.y < endZone.height
        }
        // przewijanie przy krawędzi
        const f = item.mapToItem(flick, x, y)
        if (f.y < 40) flick.contentY = Math.max(0, flick.contentY - 12)
        else if (f.y > flick.height - 40) flick.contentY = Math.min(flick.contentHeight - flick.height, flick.contentY + 12)
    }
    function endDrag() {
        const info = dragInfo
        if (info && info.kind === "card" && (dropCi >= 0 || dropEnd)) {
            let t = dropEnd ? Profile.cards.length : dropCi + (dropAfter ? 1 : 0)
            if (info.ci < t) t--
            Profile.moveCard(info.ci, t)
            selectCard(t)
        } else if (info && info.kind === "control" && dropCi >= 0) {
            const n = Profile.cards[dropCi].controls.length
            let t = dropK >= 0 ? dropK + (dropKAfter ? 1 : 0) : n
            if (dropCi === info.ci && info.k < t) t--
            Profile.moveControl(info.ci, info.k, dropCi, t)
            selectControl(dropCi, t)
        }
        cancelDrag()
    }
    function cancelDrag() {
        dragInfo = null
        dropCi = -1
        dropK = -1
        dropEnd = false
    }

    // zmiana rozmiaru karty (krawędzie)
    function beginResize(ci, mode, cardItem) {
        selectCard(ci)
        const d = Profile.cards[ci]
        const span = Math.min(d.span, columns)
        rs = {
            ci: ci, mode: mode, card: cardItem, span: span, startSpan: span, rows: d.rows,
            height: cardItem.height, startHeight: cardItem.height
        }
    }
    function nudgeHeight(ci, delta) {
        const d = Profile.cards[ci]
        const cur = d.height > 0 ? d.height : Math.round(cardItem(ci).height / s)
        Profile.setCardBox(ci, d.span, d.rows, clamp(cur + delta, 80, 2000))
    }
    function autoHeight(ci) {
        rs = null
        const d = Profile.cards[ci]
        if (d.height > 0) Profile.setCardBox(ci, d.span, d.rows, 0)
        toast.show("Wysokość karty: automatyczna")
    }
    function moveResize(item, x, y) {
        if (!rs) return
        const g = item.mapToItem(grid, x, y)
        const c = rs.card
        const r = Object.assign({}, rs)
        if (rs.mode !== "h") r.span = clamp(Math.round((g.x - c.x + gap) / (colW + gap)), 1, Math.min(4, columns))
        if (rs.mode !== "w") r.height = clamp(Math.round((g.y - c.y) / (10 * s)) * 10 * s, 80 * s, 2000 * s)
        if (r.span !== rs.span || r.height !== rs.height) rs = r
    }
    function endResize() {
        if (rs) {
            const hChanged = rs.mode !== "w" && Math.abs(rs.height - rs.startHeight) >= 1
            if (rs.span !== rs.startSpan || hChanged)
                Profile.setCardBox(rs.ci, rs.span, rs.rows, hChanged ? Math.round(rs.height / s) : -1)
        }
        rs = null
    }
    function cancelResize() { rs = null }

    // klawiatura w trybie edycji
    Keys.onPressed: (e) => {
        if (!editing) return
        const ctrl = e.modifiers & Qt.ControlModifier
        const shift = e.modifiers & Qt.ShiftModifier
        const card = selCard >= 0 && selCard < Profile.cards.length ? Profile.cards[selCard] : null
        const hasCtl = card && selCtl >= 0 && selCtl < card.controls.length
        e.accepted = true
        if (ctrl && e.key === Qt.Key_Z) { if (shift) Profile.redo(); else Profile.undo() }
        else if (ctrl && e.key === Qt.Key_Y) Profile.redo()
        else if (ctrl && e.key === Qt.Key_D && card) selectCard(Profile.duplicateCard(selCard))
        else if (e.key === Qt.Key_Escape) {
            if (selCard >= 0) { selCard = -1; selCtl = -1 } else Session.editing = false
        }
        else if ((e.key === Qt.Key_Delete || e.key === Qt.Key_Backspace) && hasCtl) {
            Profile.removeControl(selCard, selCtl)
            selectCard(selCard)
        }
        else if ((e.key === Qt.Key_Delete || e.key === Qt.Key_Backspace) && card) removeCard(selCard)
        else if (hasCtl && (e.key === Qt.Key_Left || e.key === Qt.Key_Right)) {
            const t = clamp(selCtl + (e.key === Qt.Key_Left ? -1 : 1), 0, card.controls.length - 1)
            Profile.moveControl(selCard, selCtl, selCard, t)
            selectControl(selCard, t)
        }
        else if (hasCtl && (e.key === Qt.Key_Plus || e.key === Qt.Key_Equal || e.key === Qt.Key_Minus)) {
            const sizes = ["S", "M", "L"]
            const i = clamp(sizes.indexOf(card.controls[selCtl].size) + (e.key === Qt.Key_Minus ? -1 : 1), 0, 2)
            Profile.setControlProp(selCard, selCtl, "size", sizes[i])
        }
        else if (card && shift && (e.key === Qt.Key_Left || e.key === Qt.Key_Right))
            Profile.setCardSize(selCard, clamp(Math.min(card.span, columns) + (e.key === Qt.Key_Left ? -1 : 1), 1, 4), card.rows)
        else if (card && shift && (e.key === Qt.Key_Up || e.key === Qt.Key_Down))
            nudgeHeight(selCard, e.key === Qt.Key_Up ? -20 : 20)
        else if (card && (e.key === Qt.Key_Left || e.key === Qt.Key_Right || e.key === Qt.Key_Up || e.key === Qt.Key_Down)) {
            const step = e.key === Qt.Key_Left ? -1 : e.key === Qt.Key_Right ? 1 : e.key === Qt.Key_Up ? -columns : columns
            const t = clamp(selCard + step, 0, Profile.cards.length - 1)
            Profile.moveCard(selCard, t)
            selectCard(t)
        }
        else e.accepted = false
    }

    Connections {
        target: Profile
        function onCardsChanged() {
            if (root.selCard >= Profile.cards.length) { root.selCard = -1; root.selCtl = -1 }
        }
        function onMessage(text) { toast.show(text) }
    }
    Connections {
        target: Session
        function onToast(text) { toast.show(text) }
        function onEditingChanged() {
            root.cancelDrag()
            root.rs = null
            cardMenu.close()
            if (Session.editing) root.forceActiveFocus()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 16 * root.s
        anchors.rightMargin: 16 * root.s
        anchors.topMargin: 14 * root.s
        anchors.bottomMargin: 18 * root.s
        spacing: 14 * root.s

        LiveHeader {
            visible: !root.editing
            Layout.fillWidth: true
        }
        EditHeader {
            visible: root.editing
            host: root
            Layout.fillWidth: true
        }

        PadBar {
            visible: Theme.padPosition === "top" && (Session.screen === "live" || root.editing) && Profile.pads.length > 0
            Layout.fillWidth: true
            host: root
            editing: root.editing
            selected: root.selPad
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Flickable {
                id: flick
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: grid.implicitHeight + (root.editing ? endZone.height + root.gap : 0) + 4
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                interactive: root.dragInfo === null && root.rs === null
                ScrollBar.vertical: ScrollBar { id: vbar }

                // tło: klik w puste miejsce zdejmuje zaznaczenie
                MouseArea {
                    width: flick.width
                    height: Math.max(flick.height, flick.contentHeight)
                    enabled: root.editing
                    onClicked: { root.selCard = -1; root.selCtl = -1; root.forceActiveFocus() }
                }

                // prowadnice kolumn siatki (tryb edycji)
                Repeater {
                    model: root.editing ? root.columns : 0
                    delegate: Rectangle {
                        required property int index
                        x: index * (root.colW + root.gap)
                        width: root.colW
                        height: Math.max(flick.height, flick.contentHeight)
                        radius: 12 * root.s
                        color: Qt.rgba(1, 1, 1, 0.025)
                        border.color: Qt.rgba(1, 1, 1, 0.04)
                    }
                }

                GridLayout {
                    id: grid
                    width: flick.width - (vbar.visible && vbar.size < 1 ? 12 : 0)
                    columns: root.columns
                    columnSpacing: root.gap
                    rowSpacing: root.gap

                    Repeater {
                        id: cardRep
                        model: Profile.cards
                        delegate: Card {
                            required property int index
                            required property var modelData
                            readonly property int span: Math.min(modelData.span, root.columns)
                            cardData: modelData
                            ci: index
                            host: root
                            visible: root.cardShown(modelData)
                            editing: root.editing
                            selected: root.editing && root.selCard === index
                            selK: root.selCtl
                            dropTarget: root.dragInfo !== null && root.dragInfo.kind === "card" && root.dropCi === index
                            dropAfter: root.dropAfter
                            dropK: root.dragInfo !== null && root.dragInfo.kind === "control" && root.dropCi === index ? root.dropK : -1
                            dropKAfter: root.dropKAfter
                            expanded: root.expanded[modelData.id] === true
                            Layout.columnSpan: span
                            Layout.rowSpan: modelData.rows
                            Layout.preferredWidth: root.colW * span + root.gap * (span - 1)
                            Layout.maximumWidth: Layout.preferredWidth
                            Layout.maximumHeight: fixedH > 0 ? fixedH : Number.POSITIVE_INFINITY
                            Layout.fillHeight: true
                            Layout.alignment: Qt.AlignTop
                        }
                    }
                }

                // strefa na końcu: nowa karta / upuszczenie karty na koniec
                Rectangle {
                    id: endZone
                    visible: root.editing
                    y: grid.implicitHeight + root.gap
                    width: grid.width
                    height: 64 * root.s
                    radius: 12 * root.s
                    color: root.dropEnd ? Qt.rgba(0.25, 0.71, 0.66, 0.15) : "transparent"
                    border.color: root.dropEnd ? Theme.fx : Qt.darker(Theme.accent, 1.8)
                    Text {
                        anchors.centerIn: parent
                        text: root.dragInfo && root.dragInfo.kind === "card" ? "UPUŚĆ TUTAJ, ABY PRZENIEŚĆ NA KONIEC" : "+ NOWA KARTA"
                        color: Theme.accent
                        font.family: Theme.labelFont
                        font.weight: Font.DemiBold
                        font.pixelSize: Math.round(15 * root.s)
                        font.letterSpacing: 1.5
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.selectCard(Profile.addCard("", Session.screen === "config" ? "config" : "live"))
                    }
                }

                // podgląd nowego rozmiaru karty
                Rectangle {
                    visible: root.rs !== null
                    z: 20
                    x: root.rs ? root.rs.card.x : 0
                    y: root.rs ? root.rs.card.y : 0
                    width: root.rs ? root.rs.span * root.colW + (root.rs.span - 1) * root.gap : 0
                    height: root.rs ? root.rs.height : 0
                    radius: 12 * root.s
                    color: Qt.rgba(0.89, 0.65, 0.17, 0.10)
                    border.width: 2
                    border.color: Theme.accent
                    Rectangle {
                        anchors.centerIn: parent
                        width: sizeLabel.implicitWidth + 24
                        height: sizeLabel.implicitHeight + 12
                        radius: 8
                        color: Theme.accent
                        Text {
                            id: sizeLabel
                            anchors.centerIn: parent
                            text: root.rs ? root.rs.span + " kol." + (root.rs.mode !== "w" ? " · " + Math.round(root.rs.height / root.s) + " px" : "") : ""
                            color: Theme.bg
                            font.family: Theme.labelFont
                            font.weight: Font.Bold
                            font.pixelSize: Math.round(22 * root.s)
                        }
                    }
                }

                Text {
                    visible: !root.editing && !hasVisibleCard()
                    function hasVisibleCard() {
                        for (let i = 0; i < Profile.cards.length; i++) if (root.cardShown(Profile.cards[i])) return true
                        return false
                    }
                    width: flick.width
                    topPadding: 40 * root.s
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: Session.screen === "config"
                          ? "Brak kart konfiguracji. Pełne ustawienia: STÓŁ KLASYCZNY; własne karty: ✎ UKŁAD → + NOWA KARTA."
                          : "Brak kart na tym ekranie. Dodaj je w trybie ✎ UKŁAD."
                    color: Theme.muted
                    font.family: Theme.labelFont
                    font.pixelSize: Math.round(18 * root.s)
                }
            }

            // uchwyt szerokości inspektora
            Item {
                visible: root.editing
                Layout.preferredWidth: 14 * root.s
                Layout.fillHeight: true
                Rectangle {
                    anchors.centerIn: parent
                    width: 4
                    height: 48 * root.s
                    radius: 2
                    color: splitArea.containsMouse || splitArea.pressed ? Theme.accent : Theme.line
                }
                MouseArea {
                    id: splitArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.SplitHCursor
                    property real startX: 0
                    property real startW: 0
                    onPressed: (m) => { startX = mapToItem(root, m.x, 0).x; startW = root.inspW }
                    onPositionChanged: (m) => {
                        if (pressed) root.inspW = root.clamp(startW - (mapToItem(root, m.x, 0).x - startX), 280, 640)
                    }
                    onReleased: {
                        Profile.setThemeQuiet("inspectorWidth", Math.round(root.inspW))
                        root.inspW = Qt.binding(() => Theme.inspectorWidth)
                    }
                }
            }

            Inspector {
                id: inspector
                objectName: "inspector"
                visible: root.editing
                host: root
                selCard: root.selCard
                selCtl: root.selCtl
                selPad: root.selPad
                Layout.preferredWidth: root.inspW
                Layout.fillHeight: true
            }
        }

        PadBar {
            visible: Theme.padPosition === "bottom" && (Session.screen === "live" || root.editing) && Profile.pads.length > 0
            Layout.fillWidth: true
            host: root
            editing: root.editing
            selected: root.selPad
        }
    }

    CardMenu {
        id: cardMenu
        host: root
    }

    Rectangle {
        id: ghost
        visible: root.dragInfo !== null
        z: 100
        width: ghostLabel.implicitWidth + 24
        height: 34
        radius: 8
        color: Theme.accent
        opacity: 0.9
        Text {
            id: ghostLabel
            anchors.centerIn: parent
            color: Theme.bg
            font.family: Theme.labelFont
            font.weight: Font.Bold
            font.pixelSize: 15
        }
    }

    Rectangle {
        id: toast
        z: 101
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24 * root.s
        width: toastText.implicitWidth + 32
        height: 40 * root.s
        radius: 8 * root.s
        color: Theme.raised
        border.color: Theme.accent
        opacity: 0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        function show(text) {
            toastText.text = text
            opacity = 1
            toastTimer.restart()
        }
        Text {
            id: toastText
            anchors.centerIn: parent
            color: Theme.text
            font.family: Theme.labelFont
            font.pixelSize: Math.round(16 * root.s)
        }
        Timer {
            id: toastTimer
            interval: 2600
            onTriggered: toast.opacity = 0
        }
    }
}

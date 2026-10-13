// TOR SYGNAŁU – „dlaczego cisza?”: schemat bloków w kolejności toru (złoto = tor aktywny, przygaszone =
// moduł wyłączony – przejście bez zmian, czerwień = cięcie) i lista powodów. Dane: `Session.flow`
// (engine/signal_flow.py), mierniki IN/OUT: `Session.levels`. Klik w blok lub powód = przewiń do karty
// z tym parametrem (`host.showTarget` w Main.qml). Tylko odczyt – nic nie przełącza (także w blokadzie LIVE).
import QtQuick

Column {
    id: root
    property var host: null
    property bool interactive: true

    readonly property real s: Theme.scale
    readonly property var flow: Session.flow
    readonly property var blocks: flow.blocks || []
    readonly property var reasons: flow.reasons || []
    readonly property var cut: flow.cut || ({})
    readonly property bool hasCut: cut.text !== undefined
    readonly property var issues: reasons.filter(r => r.level !== "off")
    readonly property var offs: reasons.filter(r => r.level === "off")

    function show(target) { if (root.interactive && root.host && target) root.host.showTarget(target) }
    function withKey(r) {
        const sc = r.target ? Profile.shortcutFor(r.target) : ""
        return r.text + (sc !== "" ? " (" + sc + ")" : "")
    }
    function tone(state) {
        return state === "cut" ? Theme.kill : state === "off" ? Theme.muted : Theme.accent
    }

    spacing: 10 * s

    // nagłówek stanu: pierwsze cięcie całego toru albo „tor drożny”
    Rectangle {
        width: root.width
        height: 40 * root.s
        radius: 8 * root.s
        color: root.hasCut ? Qt.rgba(0.72, 0.21, 0.16, 0.28) : Theme.raised
        border.color: root.hasCut ? Theme.kill : Theme.line
        Text {
            anchors.verticalCenter: parent.verticalCenter
            x: 12 * root.s
            width: parent.width - 24 * root.s
            elide: Text.ElideRight
            text: root.hasCut ? "⚠ CISZA: " + root.withKey(root.cut)
                  : root.blocks.length === 0 ? "TOR SYGNAŁU – brak danych"
                  : root.issues.length ? "TOR DROŻNY – " + root.issues.length + (root.issues.length === 1 ? " uwaga" : " uwagi")
                  : "TOR DROŻNY"
            color: root.hasCut ? "#FFFFFF" : Theme.accent
            font.family: Theme.labelFont
            font.weight: Font.Bold
            font.pixelSize: Math.round(17 * root.s)
            font.letterSpacing: 1.2
        }
        MouseArea {
            anchors.fill: parent
            enabled: root.hasCut && root.cut.target !== ""
            cursorShape: Qt.PointingHandCursor
            onClicked: root.show(root.cut.target)
        }
    }

    // schemat: bloki ze strzałkami, zawijane przy wąskiej karcie
    Flow {
        id: chain
        width: root.width
        spacing: 4 * root.s
        Repeater {
            model: root.blocks
            delegate: Row {
                id: cell
                required property int index
                required property var modelData
                readonly property var b: modelData
                readonly property color c: root.tone(b.state)
                readonly property bool meter: b.id === "in" || b.id === "out"
                spacing: 4 * root.s
                Text {
                    visible: cell.index > 0
                    anchors.verticalCenter: box.verticalCenter
                    text: "▶"
                    color: Theme.muted
                    font.pixelSize: Math.round(13 * root.s)
                }
                Rectangle {
                    id: box
                    objectName: "flowBlock_" + cell.b.id
                    width: Math.max(92 * root.s, col.implicitWidth + 18 * root.s + (cell.meter ? 14 * root.s : 0))
                    height: 80 * root.s
                    radius: 8 * root.s
                    opacity: cell.b.state === "off" ? 0.55 : 1
                    color: cell.b.state === "cut" ? Qt.rgba(0.72, 0.21, 0.16, 0.30)
                           : cell.b.state === "off" ? "transparent" : Qt.rgba(0.89, 0.65, 0.17, 0.10)
                    border.width: cell.b.state === "off" ? 1 : 2
                    border.color: cell.b.state === "off" ? Theme.line : cell.c
                    Column {
                        id: col
                        x: 8 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 3 * root.s
                        Text {
                            text: cell.b.label
                            color: cell.b.state === "cut" ? "#FFFFFF" : cell.c
                            font.family: Theme.labelFont
                            font.weight: Font.Bold
                            font.pixelSize: Math.round(15 * root.s)
                            font.letterSpacing: 1.1
                        }
                        Text {
                            text: cell.b.state === "off" ? "WYŁ. · BEZ ZMIAN" : (cell.b.note || " ")
                            color: cell.b.state === "cut" ? "#FFD9D3" : Theme.muted
                            font.family: Theme.valueFont
                            font.pixelSize: Math.round(11 * root.s)
                        }
                        // pasma izolatora, drogi zwrotnicy, kanały, wejścia i efekty miksu
                        Row {
                            spacing: 3 * root.s
                            visible: cell.b.items.length > 0
                            Repeater {
                                model: cell.b.items
                                delegate: Rectangle {
                                    required property var modelData
                                    readonly property bool fx: modelData.kind === "fx"
                                    readonly property color ic: modelData.state === "cut" ? Theme.kill
                                                                : modelData.state === "off" ? Theme.muted
                                                                : fx ? Theme.fx : Theme.accent
                                    width: tag.implicitWidth + 9 * root.s
                                    height: 19 * root.s
                                    radius: 3 * root.s
                                    color: modelData.state === "cut" ? Theme.kill : "transparent"
                                    border.color: ic
                                    opacity: modelData.state === "off" ? 0.6 : 1
                                    Text {
                                        id: tag
                                        anchors.centerIn: parent
                                        // ▲ = wejście miksu (MC, syrena); efekty (powroty) – turkus
                                        text: (modelData.kind === "in" ? "▲" : "") + modelData.label
                                        color: modelData.state === "cut" ? "#FFFFFF" : parent.ic
                                        font.family: Theme.valueFont
                                        font.weight: Font.DemiBold
                                        font.pixelSize: Math.round(11 * root.s)
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.show(modelData.target)
                                    }
                                }
                            }
                        }
                    }
                    // miernik IN / OUT (Session.levels: 0 = IN, 5 = OUT)
                    Rectangle {
                        visible: cell.meter
                        anchors.right: parent.right
                        anchors.rightMargin: 7 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        width: 7 * root.s
                        height: parent.height - 18 * root.s
                        radius: 2
                        color: Theme.line
                        clip: true
                        Rectangle {
                            readonly property real lv: Session.levels[cell.b.id === "in" ? 0 : 5] || 0
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: parent.height * lv
                            color: lv > 0.9 ? Theme.kill : Theme.accent
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        z: -1
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.show(cell.b.target)
                    }
                }
            }
        }
    }

    // powody (od najpoważniejszych) – klik = karta z parametrem
    Flow {
        width: root.width
        spacing: 6 * root.s
        visible: root.issues.length > 0
        Repeater {
            model: root.issues
            delegate: Rectangle {
                required property var modelData
                readonly property bool severe: modelData.level === "silent" || modelData.level === "music"
                width: Math.min(root.width, reasonText.implicitWidth + 22 * root.s)
                height: 28 * root.s
                radius: 6 * root.s
                color: severe ? Qt.rgba(0.72, 0.21, 0.16, 0.22) : Theme.raised
                border.color: severe ? Theme.kill : Qt.lighter(Theme.line, 1.3)
                Text {
                    id: reasonText
                    anchors.verticalCenter: parent.verticalCenter
                    x: 11 * root.s
                    width: parent.width - 22 * root.s
                    elide: Text.ElideRight
                    text: root.withKey(modelData)
                    color: severe ? "#FFFFFF" : Theme.text
                    font.family: Theme.valueFont
                    font.pixelSize: Math.round(12 * root.s)
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: modelData.target !== ""
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.show(modelData.target)
                }
            }
        }
    }

    Text {
        width: root.width
        visible: root.offs.length > 0
        wrapMode: Text.WordWrap
        text: "WYŁĄCZONE: " + root.offs.map(r => r.name).join(" · ")
        color: Theme.muted
        font.family: Theme.valueFont
        font.pixelSize: Math.round(11 * root.s)
    }
    Text {
        width: root.width
        wrapMode: Text.WordWrap
        text: "złoto = tor aktywny · przygaszone = wyłączony (bez zmian) · czerwień = cięcie · klik w blok = karta"
        color: Qt.darker(Theme.muted, 1.25)
        font.family: Theme.labelFont
        font.pixelSize: Math.round(12 * root.s)
        font.letterSpacing: 0.6
    }
}

// Menu karty w trybie edycji (⋯ lub prawy przycisk): rozmiar, ekran, kolor, zwijanie, duplikat, usuwanie.
// Żyje w Main.qml, więc nie zamyka się, gdy karty są przebudowywane po zmianie profilu.
import QtQuick
import QtQuick.Controls

Popup {
    id: menu
    property var host: null
    property int ci: -1
    readonly property var cardData: ci >= 0 && ci < Profile.cards.length ? Profile.cards[ci] : null
    readonly property real s: Theme.scale

    width: 270 * s
    padding: 10 * s
    background: Rectangle { color: Theme.raised; border.color: Theme.accent; radius: 10 * menu.s }
    onCardDataChanged: if (cardData === null) close()

    contentItem: Column {
        spacing: 8 * menu.s
        Text {
            text: menu.cardData ? menu.cardData.title : ""
            color: Theme.text
            font.family: Theme.labelFont
            font.weight: Font.Bold
            font.pixelSize: Math.round(16 * menu.s)
            font.letterSpacing: 2
        }
        Caption { text: "SZEROKOŚĆ (KOLUMNY SIATKI)" }
        Seg {
            width: parent.width
            fill: true
            height: 38 * menu.s
            fontSize: 14
            model: [1, 2, 3, 4].map(n => ({ label: String(n), value: n }))
            current: menu.cardData ? menu.cardData.span : 1
            onPicked: (v) => Profile.setCardSize(menu.ci, v, menu.cardData.rows)
        }
        Caption { text: "WYSOKOŚĆ KARTY (PX)" }
        Row {
            spacing: 6 * menu.s
            FlatButton {
                text: "AUTO"
                fontSize: 13
                height: 36 * menu.s
                checked: menu.cardData !== null && menu.cardData.height === 0
                onClicked: Profile.setCardBox(menu.ci, menu.cardData.span, menu.cardData.rows, 0)
            }
            FlatButton {
                text: "−"
                width: 40 * menu.s
                height: 36 * menu.s
                onClicked: menu.host.nudgeHeight(menu.ci, -40)
            }
            Text {
                width: 64 * menu.s
                height: 36 * menu.s
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: menu.cardData && menu.cardData.height > 0 ? menu.cardData.height : "auto"
                color: Theme.text
                font.family: Theme.valueFont
                font.pixelSize: Math.round(14 * menu.s)
            }
            FlatButton {
                text: "+"
                width: 40 * menu.s
                height: 36 * menu.s
                onClicked: menu.host.nudgeHeight(menu.ci, 40)
            }
        }
        Caption { text: "RZĘDY SIATKI (KARTA OBOK KILKU NIŻSZYCH)" }
        Seg {
            width: parent.width
            fill: true
            height: 38 * menu.s
            fontSize: 14
            model: [1, 2, 3].map(n => ({ label: String(n), value: n }))
            current: menu.cardData ? menu.cardData.rows : 1
            onPicked: (v) => Profile.setCardSize(menu.ci, menu.cardData.span, v)
        }
        Caption { text: "KONTROLEK W RZĘDZIE" }
        Seg {
            width: parent.width
            fill: true
            height: 38 * menu.s
            fontSize: 13
            model: [{ label: "AUTO", value: 0 }].concat([2, 3, 4, 5, 6].map(n => ({ label: String(n), value: n })))
            current: menu.cardData ? menu.cardData.cols : 0
            onPicked: (v) => Profile.setCardProp(menu.ci, "cols", v)
        }
        Caption { text: "POKAŻ NA EKRANIE" }
        Seg {
            width: parent.width
            fill: true
            height: 38 * menu.s
            fontSize: 13
            model: [{ label: "LIVE", value: "live" }, { label: "KONFIG.", value: "config" }, { label: "OBU", value: "both" }]
            current: menu.cardData ? menu.cardData.visible : "live"
            onPicked: (v) => Profile.setCardProp(menu.ci, "visible", v)
        }
        Caption { text: "KOLOR" }
        Swatches {
            allowAuto: false
            current: menu.cardData ? menu.cardData.color : "accent"
            onPicked: (n) => Profile.setCardProp(menu.ci, "color", n)
        }
        Flow {
            width: parent.width
            spacing: 6 * menu.s
            FlatButton {
                text: menu.cardData && menu.cardData.collapsed ? "ROZWIŃ W LIVE" : "ZWIŃ W LIVE"
                fontSize: 13
                height: 36 * menu.s
                onClicked: Profile.setCardProp(menu.ci, "collapsed", !menu.cardData.collapsed)
            }
            FlatButton {
                text: "DUPLIKUJ"
                fontSize: 13
                height: 36 * menu.s
                onClicked: { menu.close(); menu.host.selectCard(Profile.duplicateCard(menu.ci)) }
            }
            FlatButton {
                text: "USUŃ"
                danger: true
                fontSize: 13
                height: 36 * menu.s
                onClicked: { menu.close(); menu.host.removeCard(menu.ci) }
            }
        }
    }
}

// Obszar kliknięcia; przy `hold` (blokada LIVE) działa dopiero po przytrzymaniu – pasek postępu na dole,
// krótkie kliknięcie pokazuje tylko podpowiedź. Bez `hold` zwykłe kliknięcie (długie też się liczy).
import QtQuick

MouseArea {
    id: root
    property bool hold: false
    property string hint: "BLOKADA LIVE – przytrzymaj, aby użyć"
    property real progress: 0
    signal activated()

    pressAndHoldInterval: Theme.lockHoldMs
    onPressed: if (hold) fill.restart()
    onReleased: reset()
    onCanceled: reset()
    onClicked: hold ? Session.hint(hint) : activated()
    // po przytrzymaniu MouseArea nie wysyła już clicked – akcja wykona się dokładnie raz
    onPressAndHold: activated()

    function reset() {
        fill.stop()
        progress = 0
    }

    NumberAnimation {
        id: fill
        target: root
        property: "progress"
        from: 0
        to: 1
        duration: root.pressAndHoldInterval
    }

    Rectangle {
        visible: root.progress > 0
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        width: parent.width * root.progress
        height: Math.max(3, 4 * Theme.scale)
        radius: height / 2
        color: Theme.accent
    }
}

window.onload = function() {

    var vid = document.getElementById("mainPlayer");
    vid.playbackRate = 1.25;

    const player = document.querySelector('.player')
    const lyrics = document.querySelector('.lyrics')
    const summary = document.querySelector('.summary')
    const lines = lyrics.textContent.trim().split('\n')

    lyrics.removeAttribute('style')
    lyrics.innerText = ''

    let syncData = []

    lines.map((line, index) => {
        const [time, durr] = line.trim().split('|')
        syncData.push({'start': time.trim(), 'duration': durr.trim()})
    })

    player.addEventListener('timeupdate', () => {

        syncData.forEach((item) => {
            if ((player.currentTime >= item.start) && (player.currentTime <= parseFloat(item.start) + parseFloat(item.duration)) ) {
                document.getElementById(item.start).style.backgroundColor = "yellow";
            } else {
                document.getElementById(item.start).style.backgroundColor = "white"
            }
        })

    })
}

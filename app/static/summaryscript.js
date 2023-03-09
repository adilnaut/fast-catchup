window.onload = function() {
    const player = document.querySelector('.player')
    const lyrics = document.querySelector('.lyrics')
    const lines = lyrics.textContent.trim().split('\n')

    lyrics.removeAttribute('style')
    lyrics.innerText = ''

    let syncData = []

    lines.map((line, index) => {
        const [time, text] = line.trim().split('|')
        syncData.push({'start': time.trim(), 'text': text.trim()})
    })

    player.addEventListener('timeupdate', () => {
        syncData.forEach((item) => {
            console.log(item)
            if (player.currentTime >= item.start) lyrics.innerText = item.text
        })
    })
}

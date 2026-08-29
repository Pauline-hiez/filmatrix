(function () {
    function formatTime(seconds) {
        if (!Number.isFinite(seconds)) {
            return "--:--";
        }
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return String(minutes).padStart(2, "0") + ":" + String(remainingSeconds).padStart(2, "0");
    }

    document.querySelectorAll("[data-audio-player]").forEach(function (player) {
        const audio = player.querySelector(".audio-player__native");
        const toggle = player.querySelector("[data-audio-toggle]");
        const playIcon = player.querySelector("[data-audio-play-icon]");
        const pauseIcon = player.querySelector("[data-audio-pause-icon]");
        const seek = player.querySelector("[data-audio-seek]");
        const volume = player.querySelector("[data-audio-volume]");
        const mute = player.querySelector("[data-audio-mute]");
        const current = player.querySelector("[data-audio-current]");
        const duration = player.querySelector("[data-audio-duration]");

        if (!audio || !toggle) {
            return;
        }

        function setPlaying(playing) {
            player.classList.toggle("is-playing", playing);
            playIcon.hidden = playing;
            pauseIcon.hidden = !playing;
            toggle.setAttribute("aria-label", playing ? "Mettre l'extrait en pause" : "Lire l'extrait");
        }

        toggle.addEventListener("click", function () {
            if (audio.paused) {
                audio.play().catch(function () {
                    setPlaying(false);
                });
            } else {
                audio.pause();
            }
        });

        audio.addEventListener("loadedmetadata", function () {
            duration.textContent = formatTime(audio.duration);
        });

        audio.addEventListener("timeupdate", function () {
            current.textContent = formatTime(audio.currentTime);
            if (audio.duration) {
                seek.value = (audio.currentTime / audio.duration) * 100;
            }
        });

        audio.addEventListener("play", function () { setPlaying(true); });
        audio.addEventListener("pause", function () { setPlaying(false); });
        audio.addEventListener("ended", function () {
            setPlaying(false);
            seek.value = 0;
        });

        seek.addEventListener("input", function () {
            if (audio.duration) {
                audio.currentTime = (Number(seek.value) / 100) * audio.duration;
            }
        });

        volume.addEventListener("input", function () {
            audio.volume = Number(volume.value);
            audio.muted = audio.volume === 0;
            mute.textContent = audio.muted ? "🔇" : "🔊";
            mute.setAttribute("aria-label", audio.muted ? "Activer le son" : "Couper le son");
        });

        mute.addEventListener("click", function () {
            audio.muted = !audio.muted;
            mute.textContent = audio.muted ? "🔇" : "🔊";
            mute.setAttribute("aria-label", audio.muted ? "Activer le son" : "Couper le son");
        });

        setPlaying(!audio.paused);
    });
})();

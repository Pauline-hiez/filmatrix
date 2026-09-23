// Pendant utilisée en repli quand aucun extrait iTunes exploitable n'existe :
// un lecteur YouTube IFrame réduit à quasi rien visuellement (voir
// .audio-player__native dans base.html), piloté pour ressembler en tout point
// au lecteur natif de static/js/audio_player.js. Les deux scripts coexistent
// sans se marcher dessus : chacun ne touche que les instances correspondant à
// sa source (data-audio-source).
(function () {
    function formatTime(seconds) {
        if (!Number.isFinite(seconds)) {
            return "--:--";
        }
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return String(minutes).padStart(2, "0") + ":" + String(remainingSeconds).padStart(2, "0");
    }

    const players = document.querySelectorAll('[data-audio-player][data-audio-source="youtube"]');
    if (!players.length) {
        return;
    }

    function loadIframeApi() {
        return new Promise(function (resolve) {
            if (window.YT && window.YT.Player) {
                resolve();
                return;
            }
            const previousCallback = window.onYouTubeIframeAPIReady;
            window.onYouTubeIframeAPIReady = function () {
                if (previousCallback) previousCallback();
                resolve();
            };
            if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
                const tag = document.createElement("script");
                tag.src = "https://www.youtube.com/iframe_api";
                document.head.appendChild(tag);
            }
        });
    }

    function setupPlayer(container) {
        const mount = container.querySelector("[data-youtube-mount]");
        const toggle = container.querySelector("[data-audio-toggle]");
        const playIcon = container.querySelector("[data-audio-play-icon]");
        const pauseIcon = container.querySelector("[data-audio-pause-icon]");
        const seek = container.querySelector("[data-audio-seek]");
        const volume = container.querySelector("[data-audio-volume]");
        const muteButton = container.querySelector("[data-audio-mute]");
        const current = container.querySelector("[data-audio-current]");
        const duration = container.querySelector("[data-audio-duration]");

        if (!mount || !toggle) {
            return;
        }

        const videoId = mount.dataset.youtubeId;
        const start = parseInt(mount.dataset.youtubeStart, 10) || 0;
        const end = parseInt(mount.dataset.youtubeEnd, 10) || start + 30;
        const clipDuration = Math.max(end - start, 1);
        const autoplay = container.dataset.autoplay === "true";

        if (!videoId) {
            return;
        }

        duration.textContent = formatTime(clipDuration);

        function setPlaying(playing) {
            container.classList.toggle("is-playing", playing);
            playIcon.hidden = playing;
            pauseIcon.hidden = !playing;
            toggle.setAttribute("aria-label", playing ? "Mettre l'extrait en pause" : "Lire l'extrait");
        }

        let pollTimer = null;

        function stopPolling() {
            if (pollTimer) {
                clearInterval(pollTimer);
                pollTimer = null;
            }
        }

        function startPolling(player) {
            stopPolling();
            pollTimer = setInterval(function () {
                const elapsed = Math.max(player.getCurrentTime() - start, 0);
                current.textContent = formatTime(elapsed);
                seek.value = Math.min((elapsed / clipDuration) * 100, 100);
            }, 250);
        }

        const player = new YT.Player(mount, {
            width: "2",
            height: "2",
            videoId: videoId,
            playerVars: {
                start: start,
                end: end,
                controls: 0,
                disablekb: 1,
                modestbranding: 1,
                rel: 0,
                iv_load_policy: 3,
                fs: 0,
                playsinline: 1,
            },
            events: {
                onReady: function () {
                    player.setVolume(Number(volume.value) * 100);
                    if (autoplay) {
                        // Comme pour l'audio natif, l'autoplay peut être bloqué par le
                        // navigateur : le joueur reste alors simplement en pause, le
                        // bouton de lecture manuel prend le relais.
                        player.playVideo();
                    }
                },
                onStateChange: function (event) {
                    if (event.data === YT.PlayerState.PLAYING) {
                        setPlaying(true);
                        startPolling(player);
                    } else if (event.data === YT.PlayerState.PAUSED) {
                        setPlaying(false);
                        stopPolling();
                    } else if (event.data === YT.PlayerState.ENDED) {
                        setPlaying(false);
                        stopPolling();
                        current.textContent = formatTime(0);
                        seek.value = 0;
                    }
                },
            },
        });

        toggle.addEventListener("click", function () {
            if (player.getPlayerState() === YT.PlayerState.PLAYING) {
                player.pauseVideo();
            } else {
                player.playVideo();
            }
        });

        seek.addEventListener("input", function () {
            const target = start + (Number(seek.value) / 100) * clipDuration;
            player.seekTo(target, true);
        });

        volume.addEventListener("input", function () {
            const value = Number(volume.value);
            player.setVolume(value * 100);
            if (value === 0) {
                player.mute();
            } else {
                player.unMute();
            }
            muteButton.textContent = value === 0 ? "🔇" : "🔊";
            muteButton.setAttribute("aria-label", value === 0 ? "Activer le son" : "Couper le son");
        });

        muteButton.addEventListener("click", function () {
            if (player.isMuted()) {
                player.unMute();
                muteButton.textContent = "🔊";
                muteButton.setAttribute("aria-label", "Couper le son");
            } else {
                player.mute();
                muteButton.textContent = "🔇";
                muteButton.setAttribute("aria-label", "Activer le son");
            }
        });
    }

    loadIframeApi().then(function () {
        players.forEach(setupPlayer);
    });
})();

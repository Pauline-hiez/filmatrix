const TOTAL_DURATION = 10;
let remainingTime = TOTAL_DURATION;
let alreadyAnswered = false;

const timeBar = document.getElementById("time-bar");

function goToNextQuestion() {
    setTimeout(function () {
        window.location.href = window.location.href.replace(
            /\/(\d+)(\?|$)/,
            function (match, position, end) {
                return "/" + (parseInt(position) + 1) + end;
            }
        );
    }, 1500);
}

async function sendAnswer(body) {
    if (alreadyAnswered) {
        return;
    }
    alreadyAnswered = true;
    clearInterval(timerInterval);

    document.querySelectorAll(".answer-button").forEach(function (b) {
        b.disabled = true;
    });

    const url = window.location.pathname + window.location.search;
    const serverResponse = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body,
    });

    const result = await serverResponse.json();
    return result;
}

document.querySelectorAll(".answer-button").forEach(function (button) {
    button.addEventListener("click", async function (event) {
        event.preventDefault();
        let answer = button.dataset.answer;
        const freeTextField = document.getElementById("free-text-answer");
        if (freeTextField) {
            answer = freeTextField.value;
        }

        const result = await sendAnswer(`answer=${encodeURIComponent(answer)}`);

        if (result) {
            button.classList.remove("bg-cyan-400", "hover:bg-cyan-300");

            const freeTextField = document.getElementById("free-text-answer");
            if (freeTextField) {
                freeTextField.classList.remove("border-cyan-400/30");
            }

            if (result.is_correct) {
                button.classList.add("bg-emerald-500/30", "border-emerald-400");
                if (freeTextField) {
                    freeTextField.classList.add("border-emerald-400");
                }
            } else {
                button.classList.add("bg-red-500/30", "border-red-400");
                if (freeTextField) {
                    freeTextField.classList.add("border-red-400");
                }
            }
            goToNextQuestion();
        }
    });
});

const timerInterval = setInterval(async function () {
    remainingTime -= 1;
    const percentage = (remainingTime / TOTAL_DURATION) * 100;
    timeBar.style.width = percentage + "%";

    if (remainingTime <= 0) {
        await sendAnswer("timeout=true");
        goToNextQuestion();
    }
}, 1000);

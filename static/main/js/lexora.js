(function () {
    const root = document.querySelector("[data-lexora-root]");
    if (!root) {
        return;
    }

    const chatBox = root.querySelector("[data-lexora-box]");
    const input = root.querySelector("[data-lexora-input]");

    function addMessage(text, type) {
        const msg = document.createElement("div");
        msg.className = "chat-bubble " + (type === "user" ? "self" : "other");
        msg.textContent = text;
        chatBox.appendChild(msg);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function speakText(text) {
        const speech = new SpeechSynthesisUtterance(text);
        speech.lang = "en-US";
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(speech);
    }

    root.querySelector("[data-lexora-send]").addEventListener("click", function () {
        const question = input.value.trim();
        if (!question) {
            return;
        }

        addMessage(question, "user");
        input.value = "";

        fetch("/ask-lexora/", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": root.dataset.csrfToken,
            },
            body: "question=" + encodeURIComponent(question),
        })
            .then((response) => response.json())
            .then((data) => {
                addMessage(data.answer, "bot");
                speakText(data.answer);

                if (data.lawyers && data.lawyers.length > 0) {
                    const summary = data.lawyers
                        .map((lawyer) => `${lawyer.name} (${lawyer.experience} yrs) - ${lawyer.location}`)
                        .join("\n");
                    addMessage("Recommended lawyers:\n" + summary, "bot");
                }
            });
    });

    root.querySelector("[data-lexora-reset]").addEventListener("click", function () {
        window.speechSynthesis.cancel();
        chatBox.innerHTML = "";
        addMessage("Hello! Ask Lexora about your legal issue and I will guide you.", "bot");
    });
})();

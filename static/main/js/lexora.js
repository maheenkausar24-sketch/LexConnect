(function () {
    const roots = document.querySelectorAll("[data-lexora-root]");
    if (!roots.length) {
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    roots.forEach((root, index) => {
        const mode = root.dataset.lexoraMode || "page";
        const storageKey = "lexora-history-" + mode;
        const panel = root.querySelector("[data-lexora-panel]");
        const toggle = root.querySelector("[data-lexora-toggle]");
        const close = root.querySelector("[data-lexora-close]");
        const form = root.querySelector("[data-lexora-form]");
        const chatBox = root.querySelector("[data-lexora-box]");
        const input = root.querySelector("[data-lexora-input]");
        const sendButton = root.querySelector("[data-lexora-send]");
        const resetButton = root.querySelector("[data-lexora-reset]");
        const status = root.querySelector("[data-lexora-status]");
        const voiceButton = root.querySelector("[data-lexora-voice]");

        if (!chatBox || !input || !form) {
            return;
        }

        let messages = loadHistory();
        let busy = false;

        function loadHistory() {
            try {
                return JSON.parse(window.localStorage.getItem(storageKey) || "[]");
            } catch (error) {
                return [];
            }
        }

        function saveHistory() {
            window.localStorage.setItem(storageKey, JSON.stringify(messages.slice(-24)));
        }

        function setStatus(text) {
            if (status) {
                status.textContent = text;
            }
        }

        function scrollToBottom() {
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function renderMessage(message) {
            const bubble = document.createElement("div");
            bubble.className = "lexora-message " + (message.role === "user" ? "lexora-message-user" : "lexora-message-bot");
            bubble.textContent = message.text;
            chatBox.appendChild(bubble);

            if (message.category) {
                const meta = document.createElement("div");
                meta.className = "lexora-meta";
                meta.textContent = "Category: " + message.category.name + " · " + message.category.confidence + " confidence";
                chatBox.appendChild(meta);
            }

            if (message.lawyers && message.lawyers.length) {
                const list = document.createElement("div");
                list.className = "lexora-lawyer-list";
                message.lawyers.forEach((lawyer) => {
                    const card = document.createElement("article");
                    card.className = "lexora-lawyer-card";

                    const title = document.createElement("strong");
                    title.textContent = lawyer.name;

                    const copy = document.createElement("span");
                    copy.textContent = `${lawyer.specialization} · ${lawyer.experience} yrs · ${lawyer.location || "Location available on profile"}`;

                    const actions = document.createElement("div");
                    actions.className = "lexora-lawyer-actions";

                    const profile = document.createElement("a");
                    profile.href = lawyer.profile_url;
                    profile.textContent = "Profile";

                    const consult = document.createElement("a");
                    consult.href = lawyer.consult_url;
                    consult.textContent = "Book";

                    actions.append(profile, consult);
                    card.append(title, copy, actions);
                    list.appendChild(card);
                });
                chatBox.appendChild(list);
            }

            scrollToBottom();
        }

        function renderHistory() {
            if (messages.length) {
                chatBox.innerHTML = "";
                messages.forEach(renderMessage);
            }
        }

        function addMessage(message, persist) {
            renderMessage(message);
            if (persist !== false) {
                messages.push(message);
                saveHistory();
            }
        }

        function typingNode() {
            const node = document.createElement("div");
            node.className = "lexora-message lexora-message-bot lexora-typing";
            node.innerHTML = "<span></span><span></span><span></span>";
            chatBox.appendChild(node);
            scrollToBottom();
            return node;
        }

        function setBusy(value) {
            busy = value;
            input.disabled = value;
            if (sendButton) {
                sendButton.disabled = value;
            }
            if (value) {
                setStatus("Lexora is analyzing...");
            }
        }

        function resetChat() {
            messages = [];
            saveHistory();
            chatBox.innerHTML = "";
            addMessage(
                {
                    role: "bot",
                    text: "Fresh chat started. Describe your legal issue and I will guide you.",
                },
                false
            );
            input.focus();
        }

        async function submitQuestion(value) {
            const question = (value || input.value || "").trim();
            if (!question || busy) {
                return;
            }

            addMessage({ role: "user", text: question });
            input.value = "";
            input.style.height = "";
            const loader = typingNode();
            setBusy(true);

            try {
                const response = await fetch("/ask-lexora/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": root.dataset.csrfToken || "",
                    },
                    body: JSON.stringify({ question }),
                });
                const data = await response.json();
                loader.remove();

                if (!response.ok) {
                    addMessage({ role: "bot", text: data.error || "Lexora could not process that yet. Please try again." });
                    return;
                }

                const botMessage = {
                    role: "bot",
                    text: data.answer || "Lexora prepared safe guidance for your issue.",
                    category: data.category,
                    lawyers: data.lawyers || [],
                };
                addMessage(botMessage);

                if (data.provider_error) {
                    setStatus(data.provider_error);
                } else if (data.provider_status === "gemini") {
                    setStatus("Gemini-enhanced guidance ready");
                } else {
                    setStatus("Local Lexora guidance ready");
                }
            } catch (error) {
                loader.remove();
                addMessage({
                    role: "bot",
                    text: "Lexora is having trouble connecting, but you can still collect your documents, write a timeline, and book a suitable lawyer from LexConnect.",
                });
                setStatus("Connection fallback shown");
            } finally {
                setBusy(false);
            }
        }

        if (toggle && panel) {
            toggle.addEventListener("click", () => {
                root.classList.toggle("is-open");
                panel.setAttribute("aria-hidden", root.classList.contains("is-open") ? "false" : "true");
                if (root.classList.contains("is-open")) {
                    input.focus();
                }
            });
        }

        if (close && panel) {
            close.addEventListener("click", () => {
                root.classList.remove("is-open");
                panel.setAttribute("aria-hidden", "true");
            });
        }

        form.addEventListener("submit", (event) => {
            event.preventDefault();
            submitQuestion();
        });

        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submitQuestion();
            }
        });

        input.addEventListener("input", () => {
            input.style.height = "auto";
            input.style.height = Math.min(input.scrollHeight, 130) + "px";
        });

        root.querySelectorAll("[data-lexora-suggestion]").forEach((button) => {
            button.addEventListener("click", () => {
                if (panel && mode === "floating") {
                    root.classList.add("is-open");
                    panel.setAttribute("aria-hidden", "false");
                }
                submitQuestion(button.dataset.lexoraSuggestion);
            });
        });

        if (resetButton) {
            resetButton.addEventListener("click", resetChat);
        }

        if (voiceButton && SpeechRecognition) {
            voiceButton.hidden = false;
            voiceButton.addEventListener("click", () => {
                const recognition = new SpeechRecognition();
                recognition.lang = "en-IN";
                recognition.interimResults = false;
                recognition.maxAlternatives = 1;
                setStatus("Listening...");
                recognition.onresult = (event) => {
                    input.value = event.results[0][0].transcript;
                    input.focus();
                    setStatus("Voice input captured");
                };
                recognition.onerror = () => setStatus("Voice input unavailable. Please type your question.");
                recognition.onend = () => {
                    if (!busy) {
                        setStatus("Ready to guide your next step");
                    }
                };
                recognition.start();
            });
        }

        renderHistory();
        setStatus(index === 0 ? "Ready to guide your next step" : "Ready to analyze");
    });
})();

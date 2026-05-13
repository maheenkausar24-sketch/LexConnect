(function () {
    const root = document.querySelector("[data-chat-root]");
    if (!root) {
        return;
    }

    const messagesBox = root.querySelector("[data-chat-messages]");
    const form = root.querySelector("[data-chat-form]");
    if (!messagesBox || !form) {
        return;
    }

    const currentUserId = root.dataset.currentUserId;
    const textInput = root.querySelector("[data-message-input]");
    const fileInput = root.querySelector("[data-file-input]");
    const preview = root.querySelector("[data-preview]");
    const previewImage = root.querySelector("[data-preview-image]");
    const previewName = root.querySelector("[data-preview-name]");
    const previewType = root.querySelector("[data-preview-type]");
    const removeButton = root.querySelector("[data-remove-preview]");
    const sendButton = root.querySelector("[data-send-button]");
    const micButton = root.querySelector("[data-mic-button]");
    const wsPath = root.dataset.wsPath;
    const sendUrl = root.dataset.sendUrl;
    const messagesUrl = root.dataset.messagesUrl;

    let socket = null;
    let reconnectTimer = null;
    let reconnectAttempts = 0;
    let pollingTimer = null;
    let closedManually = false;
    let isPolling = false;
    let lastMessageId = 0;
    const renderedIds = new Set();
    const pendingMessages = new Map();

    messagesBox.querySelectorAll("[data-message-id]").forEach(function (bubble) {
        const messageId = bubble.dataset.messageId;
        if (!messageId) {
            return;
        }
        renderedIds.add(String(messageId));
        lastMessageId = Math.max(lastMessageId, Number(messageId) || 0);
    });

    function getEmptyState() {
        return messagesBox.querySelector("[data-empty-state]");
    }

    function removeEmptyState() {
        const emptyState = getEmptyState();
        if (emptyState) {
            emptyState.remove();
        }
    }

    function scrollToBottom(force) {
        const shouldStick =
            force ||
            messagesBox.scrollHeight - (messagesBox.scrollTop + messagesBox.clientHeight) < 120;
        if (!shouldStick) {
            return;
        }
        window.requestAnimationFrame(function () {
            messagesBox.scrollTop = messagesBox.scrollHeight;
        });
    }

    function getFileExtension(name) {
        const parts = String(name || "").toLowerCase().split(".");
        return parts.length > 1 ? "." + parts.pop() : "";
    }

    function isImageFile(message) {
        if (message.file_is_image !== undefined) {
            return Boolean(message.file_is_image);
        }
        return [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"].includes(
            getFileExtension(message.file_name)
        );
    }

    function createAttachmentNode(message) {
        if (!message.file_name && !message.file_url && !message.local_file_url) {
            return null;
        }

        const wrapper = document.createElement("div");
        wrapper.className = "chat-attachment";

        const fileUrl = message.file_url || message.local_file_url || "";
        const imageAttachment = isImageFile(message) && fileUrl;

        if (imageAttachment) {
            const imageLink = document.createElement("a");
            imageLink.className = "chat-image-link";
            imageLink.href = fileUrl;
            imageLink.target = "_blank";
            imageLink.rel = "noopener";

            const image = document.createElement("img");
            image.className = "chat-image";
            image.src = fileUrl;
            image.alt = message.file_name || "Attachment";
            imageLink.appendChild(image);
            wrapper.appendChild(imageLink);
        }

        if (message.file_name) {
            const fileLink = document.createElement(fileUrl ? "a" : "div");
            fileLink.className = "file-link";
            fileLink.textContent = message.file_name;

            if (fileUrl) {
                fileLink.href = fileUrl;
                fileLink.target = "_blank";
                fileLink.rel = "noopener";
            }

            wrapper.appendChild(fileLink);
        }

        return wrapper;
    }

    function createStatusNode(statusText) {
        const status = document.createElement("div");
        status.className = "chat-status";
        status.textContent = statusText || "";
        return status;
    }

    function updateMessageStatus(target, statusText) {
        if (!target) {
            return;
        }

        let bubble = target;
        if (!bubble.classList || !bubble.classList.contains("chat-bubble")) {
            bubble = target.closest("[data-message-id], [data-temp-id]");
        }
        if (!bubble) {
            return;
        }

        let statusNode = bubble.querySelector("[data-message-status]");
        if (!statusNode && statusText) {
            statusNode = createStatusNode(statusText);
            statusNode.dataset.messageStatus = "true";
            bubble.appendChild(statusNode);
        }

        if (statusNode) {
            statusNode.textContent = statusText || "";
        }

        bubble.classList.toggle("pending", statusText === "sending...");
    }

    function buildMessageBubble(message, options) {
        const settings = options || {};
        const bubble = document.createElement("div");
        const isSelf = String(message.sender_id) === String(currentUserId);
        bubble.className = "chat-bubble " + (isSelf ? "self" : "other");

        if (message.id) {
            bubble.dataset.messageId = message.id;
        }
        if (settings.tempId) {
            bubble.dataset.tempId = settings.tempId;
            bubble.classList.add("pending");
        }

        if (message.text) {
            const body = document.createElement("div");
            body.textContent = message.text;
            bubble.appendChild(body);
        }

        const attachment = createAttachmentNode(message);
        if (attachment) {
            bubble.appendChild(attachment);
        }

        const meta = document.createElement("div");
        meta.className = "chat-meta";
        meta.textContent = message.timestamp || "";
        bubble.appendChild(meta);

        if (settings.statusText) {
            const status = createStatusNode(settings.statusText);
            status.dataset.messageStatus = "true";
            bubble.appendChild(status);
        }

        return bubble;
    }

    function appendBubble(bubble, forceScroll) {
        removeEmptyState();
        messagesBox.appendChild(bubble);
        scrollToBottom(forceScroll);
    }

    function removePendingMessage(tempId) {
        const pending = pendingMessages.get(tempId);
        if (!pending) {
            return null;
        }
        pendingMessages.delete(tempId);
        if (pending.previewUrl) {
            URL.revokeObjectURL(pending.previewUrl);
        }
        return pending;
    }

    function trackMessage(messageId) {
        if (!messageId) {
            return;
        }
        renderedIds.add(String(messageId));
        lastMessageId = Math.max(lastMessageId, Number(messageId) || 0);
    }

    function renderMessage(message, options) {
        if (!message) {
            return null;
        }

        const settings = options || {};
        const messageId = message.id ? String(message.id) : "";

        if (messageId && renderedIds.has(messageId)) {
            const existing = messagesBox.querySelector('[data-message-id="' + messageId + '"]');
            if (existing && settings.statusText) {
                updateMessageStatus(existing, settings.statusText);
            }
            return existing;
        }

        const bubble = buildMessageBubble(message, { statusText: settings.statusText });
        appendBubble(bubble, settings.forceScroll !== false);
        trackMessage(messageId);
        return bubble;
    }

    function reconcilePendingMessage(tempId, message) {
        const pending = removePendingMessage(tempId);
        const messageId = message && message.id ? String(message.id) : "";
        const existing = messageId
            ? messagesBox.querySelector('[data-message-id="' + messageId + '"]')
            : null;

        if (existing) {
            updateMessageStatus(existing, "sent");
            if (pending && pending.element && pending.element.isConnected) {
                pending.element.remove();
            }
            trackMessage(messageId);
            scrollToBottom(true);
            return existing;
        }

        const bubble = buildMessageBubble(message, { statusText: "sent" });
        if (pending && pending.element && pending.element.isConnected) {
            pending.element.replaceWith(bubble);
        } else {
            appendBubble(bubble, true);
        }

        trackMessage(messageId);
        return bubble;
    }

    function renderOptimisticMessage(text, file) {
        const tempId =
            "temp-" + Date.now() + "-" + Math.random().toString(16).slice(2);
        const previewUrl = file && file.type && file.type.startsWith("image/")
            ? URL.createObjectURL(file)
            : "";
        const optimisticMessage = {
            sender_id: currentUserId,
            text: text,
            file_name: file ? file.name : "",
            file_url: "",
            local_file_url: previewUrl,
            file_is_image: Boolean(file && file.type && file.type.startsWith("image/")),
            timestamp: "Just now",
        };
        const bubble = buildMessageBubble(optimisticMessage, {
            tempId: tempId,
            statusText: "sending...",
        });
        appendBubble(bubble, true);
        pendingMessages.set(tempId, { element: bubble, previewUrl: previewUrl });
        return tempId;
    }

    function resetPreview() {
        if (fileInput) {
            fileInput.value = "";
        }
        if (preview) {
            preview.classList.remove("active");
        }
        if (previewImage) {
            previewImage.src = "";
            previewImage.style.display = "none";
        }
        if (previewName) {
            previewName.textContent = "";
        }
        if (previewType) {
            previewType.textContent = "";
        }
    }

    function startPolling() {
        if (!messagesUrl || pollingTimer) {
            return;
        }
        pollingTimer = window.setInterval(function () {
            fetchMissedMessages();
        }, 3000);
    }

    function stopPolling() {
        if (!pollingTimer) {
            return;
        }
        window.clearInterval(pollingTimer);
        pollingTimer = null;
    }

    function fetchMissedMessages() {
        if (!messagesUrl || isPolling) {
            return;
        }

        isPolling = true;
        const separator = messagesUrl.indexOf("?") === -1 ? "?" : "&";
        fetch(messagesUrl + separator + "after=" + encodeURIComponent(lastMessageId), {
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Unable to fetch chat messages.");
                }
                return response.json();
            })
            .then(function (data) {
                (data.messages || []).forEach(function (message) {
                    renderMessage(message, {
                        statusText:
                            String(message.sender_id) === String(currentUserId) ? "sent" : "",
                    });
                });
            })
            .catch(function () {
                // Keep quiet and try again on the next poll interval.
            })
            .finally(function () {
                isPolling = false;
            });
    }

    function scheduleReconnect() {
        if (closedManually || reconnectTimer) {
            return;
        }
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 5000);
        reconnectAttempts += 1;
        reconnectTimer = window.setTimeout(function () {
            reconnectTimer = null;
            setupSocket();
        }, delay);
    }

    function setupSocket() {
        if (!wsPath || closedManually) {
            return;
        }

        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        socket = new WebSocket(protocol + "://" + window.location.host + wsPath);
        socket.onopen = function () {
            reconnectAttempts = 0;
            stopPolling();
            fetchMissedMessages();
        };
        socket.onmessage = function (event) {
            const payload = JSON.parse(event.data);
            if (payload.client_temp_id && pendingMessages.has(payload.client_temp_id)) {
                reconcilePendingMessage(payload.client_temp_id, payload);
                return;
            }
            renderMessage(payload, {
                statusText: String(payload.sender_id) === String(currentUserId) ? "sent" : "",
            });
        };
        socket.onerror = function () {
            startPolling();
        };
        socket.onclose = function () {
            socket = null;
            startPolling();
            scheduleReconnect();
        };
    }

    function previewFile(file) {
        if (!file || !preview) {
            resetPreview();
            return;
        }

        preview.classList.add("active");
        previewName.textContent = file.name;
        previewType.textContent = file.type || "Attachment";

        if (file.type.startsWith("image/")) {
            const reader = new FileReader();
            reader.onload = function (event) {
                previewImage.src = event.target.result;
                previewImage.style.display = "block";
            };
            reader.readAsDataURL(file);
        } else {
            previewImage.style.display = "none";
        }
    }

    if (fileInput) {
        fileInput.addEventListener("change", function () {
            previewFile(fileInput.files[0]);
        });
    }

    if (removeButton) {
        removeButton.addEventListener("click", resetPreview);
    }

    if (micButton) {
        micButton.addEventListener("click", function () {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                alert("Voice input is not supported in this browser.");
                return;
            }

            const recognition = new SpeechRecognition();
            recognition.lang = "en-IN";
            recognition.start();
            recognition.onresult = function (event) {
                textInput.value = event.results[0][0].transcript;
            };
        });
    }

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        const text = textInput.value.trim();
        const file = fileInput && fileInput.files ? fileInput.files[0] : null;

        if (!text && !file) {
            return;
        }

        const tempId = renderOptimisticMessage(text, file);
        const payload = new FormData(form);
        payload.set("text", text);
        payload.append("client_temp_id", tempId);

        sendButton.disabled = true;

        fetch(sendUrl, {
            method: "POST",
            body: payload,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok) {
                        const error = new Error(data.error || "Unable to send message.");
                        error.payload = data;
                        throw error;
                    }
                    return data;
                });
            })
            .then(function (data) {
                if (data.error) {
                    return;
                }
                reconcilePendingMessage(tempId, data.message);
                textInput.value = "";
                resetPreview();
            })
            .catch(function (error) {
                const pending = pendingMessages.get(tempId);
                if (pending) {
                    updateMessageStatus(pending.element, "failed to send");
                }
                alert(error.message || "Unable to send message.");
            })
            .finally(function () {
                sendButton.disabled = false;
                textInput.focus();
            });
    });

    textInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    window.addEventListener("beforeunload", function () {
        closedManually = true;
        stopPolling();
        if (reconnectTimer) {
            window.clearTimeout(reconnectTimer);
        }
        if (socket) {
            socket.close();
        }
    });

    scrollToBottom(true);
    setupSocket();
    startPolling();
})();

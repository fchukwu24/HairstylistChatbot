const chatLog = document.querySelector("#chatLog");
const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const sendBtn = document.querySelector("#sendBtn");
const resetBtn = document.querySelector("#resetBtn");

const SESSION_KEY = "haircare_assistant_session_id";
let sessionId = localStorage.getItem(SESSION_KEY);

function appendMessage(role, text, extraClass = "") {
  const article = document.createElement("article");
  article.className = `message ${role} ${extraClass}`.trim();

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  article.appendChild(bubble);
  chatLog.appendChild(article);
  chatLog.scrollTop = chatLog.scrollHeight;

  return article;
}

function setLoading(isLoading) {
  sendBtn.disabled = isLoading;
  messageInput.disabled = isLoading;
  resetBtn.disabled = isLoading;
  sendBtn.textContent = isLoading ? "Sending..." : "Send";
}

async function loadIntroMessage() {
  const loadingIntro = appendMessage("assistant", "Loading intro...", "typing");

  try {
    const response = await fetch("/api/intro");

    if (!response.ok) {
      throw new Error(await response.text());
    }

    const data = await response.json();
    loadingIntro.querySelector(".bubble").textContent = data.reply;
    loadingIntro.classList.remove("typing");
  } catch (error) {
    loadingIntro.querySelector(".bubble").textContent =
      "Hi! I can help with haircare advice, salon services, hours, availability, and appointments.";
    loadingIntro.classList.remove("typing");
    console.error(error);
  }
}

async function sendMessage(message) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Request failed.");
  }

  return response.json();
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message) return;

  appendMessage("user", message);
  messageInput.value = "";
  setLoading(true);

  const typingBubble = appendMessage("assistant", "Thinking...", "typing");

  try {
    const data = await sendMessage(message);
    sessionId = data.session_id;
    localStorage.setItem(SESSION_KEY, sessionId);
    typingBubble.querySelector(".bubble").textContent = data.reply;
    typingBubble.classList.remove("typing");
  } catch (error) {
    typingBubble.querySelector(".bubble").textContent =
      "Sorry, something went wrong. Check your terminal logs and try again.";
    console.error(error);
  } finally {
    setLoading(false);
    messageInput.focus();
  }
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

resetBtn.addEventListener("click", async () => {
  setLoading(true);

  try {
    const response = await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });

    const data = await response.json();
    sessionId = data.session_id;
    localStorage.setItem(SESSION_KEY, sessionId);

    chatLog.innerHTML = "";
    await loadIntroMessage();
  } catch (error) {
    appendMessage("assistant", "Could not reset the chat. Try refreshing the page.");
    console.error(error);
  } finally {
    setLoading(false);
    messageInput.focus();
  }
});

loadIntroMessage();
messageInput.focus();

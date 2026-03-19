document.addEventListener("DOMContentLoaded", function () {
  var chatForm = document.getElementById("chat-form");
  if (!chatForm) return;

  var messages = document.getElementById("chat-messages");
  var input = document.getElementById("chat-input");
  var modificationId = chatForm.querySelector('input[name="modification_id"]').value;

  // Scroll to bottom on load (for restored history)
  messages.scrollTop = messages.scrollHeight;

  chatForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var message = input.value.trim();
    if (!message) return;

    // Show user message immediately
    var userBubble = document.createElement("div");
    userBubble.className = "chat-bubble chat-bubble--user";
    userBubble.textContent = message;
    messages.appendChild(userBubble);
    messages.scrollTop = messages.scrollHeight;
    input.value = "";

    // Send to backend
    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modification_id: modificationId, message: message }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        var botBubble = document.createElement("div");
        botBubble.className = "chat-bubble chat-bubble--assistant";
        botBubble.textContent = data.reply;
        messages.appendChild(botBubble);
        messages.scrollTop = messages.scrollHeight;
      })
      .catch(function () {
        var errorBubble = document.createElement("div");
        errorBubble.className = "chat-bubble chat-bubble--assistant";
        errorBubble.textContent = "Sorry, something went wrong. Please try again.";
        messages.appendChild(errorBubble);
        messages.scrollTop = messages.scrollHeight;
      });
  });
});

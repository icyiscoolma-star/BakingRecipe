// Placeholder — full chat functionality will be added in Feature 4
document.addEventListener("DOMContentLoaded", function () {
  var chatForm = document.getElementById("chat-form");
  if (chatForm) {
    chatForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var input = document.getElementById("chat-input");
      var message = input.value.trim();
      if (!message) return;

      var messages = document.getElementById("chat-messages");

      // Show user message
      var userBubble = document.createElement("div");
      userBubble.className = "chat-bubble chat-bubble--user";
      userBubble.textContent = message;
      messages.appendChild(userBubble);

      // Placeholder assistant reply
      var botBubble = document.createElement("div");
      botBubble.className = "chat-bubble chat-bubble--assistant";
      botBubble.textContent = "Thanks for your message! AI chat will be connected in a future update.";
      messages.appendChild(botBubble);

      // Scroll to bottom and clear input
      messages.scrollTop = messages.scrollHeight;
      input.value = "";
    });
  }
});

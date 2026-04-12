document.addEventListener("DOMContentLoaded", function () {
  var chatForm = document.getElementById("chat-form");
  if (!chatForm) return;

  var messages = document.getElementById("chat-messages");
  var input = document.getElementById("chat-input");
  var modificationId = chatForm.querySelector('input[name="modification_id"]').value;

  // Scroll to bottom on load (for restored history)
  messages.scrollTop = messages.scrollHeight;

  function addBubble(className, content) {
    var bubble = document.createElement("div");
    bubble.className = "chat-bubble " + className;
    if (typeof content === "string") {
      bubble.textContent = content;
    } else {
      bubble.appendChild(content);
    }
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }

  function renderChoices(data) {
    var container = document.createElement("div");
    container.className = "chat-choices";

    var question = document.createElement("p");
    question.className = "chat-choices-question";
    question.textContent = data.question;
    container.appendChild(question);

    data.options.forEach(function (opt) {
      var btn = document.createElement("button");
      btn.className = "chat-choice-btn";
      btn.innerHTML = "<strong>" + escapeHtml(opt.label) + "</strong><span>" + escapeHtml(opt.description) + "</span>";
      btn.addEventListener("click", function () {
        applyChoice(opt.label, data.question, container);
      });
      container.appendChild(btn);
    });

    return container;
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function applyChoice(label, question, container) {
    // Disable all choice buttons
    var btns = container.querySelectorAll(".chat-choice-btn");
    btns.forEach(function (b) {
      b.disabled = true;
      b.classList.add("chat-choice-btn--disabled");
    });

    // Highlight the selected one
    btns.forEach(function (b) {
      if (b.querySelector("strong").textContent === label) {
        b.classList.add("chat-choice-btn--selected");
      }
    });

    addBubble("chat-bubble--user", "Apply: " + label);

    var loadingBubble = addBubble("chat-bubble--assistant", "Applying change...");

    fetch("/api/chat/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        modification_id: modificationId,
        choice_label: label,
        question: question,
      }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.error) {
          loadingBubble.textContent = "Error: " + data.error;
          return;
        }

        loadingBubble.textContent = "Done! " + data.change_description;

        // Live update the recipe card
        var ingredientsEl = document.getElementById("mod-ingredients");
        var instructionsEl = document.getElementById("mod-instructions");
        if (ingredientsEl) {
          ingredientsEl.textContent = data.ingredients;
          ingredientsEl.classList.add("recipe-updated");
          setTimeout(function () { ingredientsEl.classList.remove("recipe-updated"); }, 1500);
        }
        if (instructionsEl) {
          instructionsEl.textContent = data.instructions;
          instructionsEl.classList.add("recipe-updated");
          setTimeout(function () { instructionsEl.classList.remove("recipe-updated"); }, 1500);
        }

        // Update chat modifications in criteria card
        var modsSection = document.getElementById("chat-modifications");
        var modsList = document.getElementById("chat-modifications-list");
        if (modsSection && modsList) {
          modsSection.style.display = "";
          var li = document.createElement("li");
          li.textContent = data.change_description;
          modsList.appendChild(li);
        }
      })
      .catch(function () {
        loadingBubble.textContent = "Something went wrong. Please try again.";
      });
  }

  function handleResponse(data) {
    if (data.type === "choices" && data.options && data.options.length > 0) {
      var choicesEl = renderChoices(data);
      addBubble("chat-bubble--assistant chat-bubble--choices", choicesEl);
    } else if (data.type === "message") {
      addBubble("chat-bubble--assistant", data.content || data.reply || "");
    } else if (data.reply) {
      // Fallback for non-JSON responses
      addBubble("chat-bubble--assistant", data.reply);
    } else if (data.content) {
      addBubble("chat-bubble--assistant", data.content);
    } else {
      addBubble("chat-bubble--assistant", JSON.stringify(data));
    }
  }

  // Parse stored chat messages that might be JSON
  var existingBubbles = messages.querySelectorAll(".chat-bubble--assistant");
  existingBubbles.forEach(function (bubble) {
    var text = bubble.textContent.trim();
    if (text.charAt(0) === "{") {
      try {
        var parsed = JSON.parse(text);
        if (parsed.type === "choices" && parsed.options) {
          bubble.textContent = "";
          bubble.classList.add("chat-bubble--choices");
          var choicesEl = renderChoices(parsed);
          bubble.appendChild(choicesEl);
          // Disable buttons on historical choices
          bubble.querySelectorAll(".chat-choice-btn").forEach(function (b) {
            b.disabled = true;
            b.classList.add("chat-choice-btn--disabled");
          });
        } else if (parsed.type === "message" && parsed.content) {
          bubble.textContent = parsed.content;
        }
      } catch (e) {
        // Not JSON, leave as-is
      }
    }
  });

  chatForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var message = input.value.trim();
    if (!message) return;

    addBubble("chat-bubble--user", message);
    input.value = "";

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modification_id: modificationId, message: message }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        handleResponse(data);
      })
      .catch(function () {
        addBubble("chat-bubble--assistant", "Sorry, something went wrong. Please try again.");
      });
  });
});

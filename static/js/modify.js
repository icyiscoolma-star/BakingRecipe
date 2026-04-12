document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("modify-form");

  // File upload preview
  const fileUpload = document.getElementById("file-upload");
  if (fileUpload) {
    fileUpload.addEventListener("change", function () {
      const preview = document.getElementById("upload-preview");
      const file = this.files[0];
      if (!file) {
        preview.classList.remove("active");
        preview.innerHTML = "";
        return;
      }
      preview.classList.add("active");
      if (file.type.startsWith("image/")) {
        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        preview.innerHTML = "";
        preview.appendChild(img);
      } else if (file.type === "application/pdf") {
        preview.textContent = "PDF selected: " + file.name + " — text will be extracted on submit.";
      } else {
        const reader = new FileReader();
        reader.onload = function (e) {
          preview.textContent = e.target.result;
        };
        reader.readAsText(file);
      }
    });
  }

  // URL fetch
  const fetchBtn = document.getElementById("fetch-url-btn");
  if (fetchBtn) {
    fetchBtn.addEventListener("click", function () {
      const urlInput = document.getElementById("recipe-url");
      const preview = document.getElementById("url-preview");
      const url = urlInput.value.trim();
      if (!url) {
        alert("Please enter a URL first.");
        return;
      }
      fetchBtn.disabled = true;
      fetchBtn.textContent = "Fetching...";
      fetch("/api/fetch-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url }),
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          var content = data.content || data.error;
          preview.classList.add("active");
          preview.textContent = content;
          document.getElementById("fetched-recipe-content").value = content;
        })
        .catch(function () {
          preview.classList.add("active");
          preview.textContent = "Failed to fetch URL.";
        })
        .finally(function () {
          fetchBtn.disabled = false;
          fetchBtn.textContent = "Fetch";
        });
    });
  }

  // Form validation — require at least one input method
  form.addEventListener("submit", function (e) {
    var title = document.getElementById("recipe-title").value.trim();
    var ingredients = document.getElementById("recipe-ingredients").value.trim();
    var instructions = document.getElementById("recipe-instructions").value.trim();
    var text = document.getElementById("recipe-text").value.trim();
    var file = document.getElementById("file-upload").files.length > 0;
    var url = document.getElementById("recipe-url").value.trim();
    var hasAny = title || ingredients || instructions || text || file || url;
    if (!hasAny) {
      e.preventDefault();
      alert("Please provide a recipe by typing it in, pasting text, uploading a file, or fetching a URL.");
    }
  });
});
